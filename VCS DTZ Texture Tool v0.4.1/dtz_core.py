"""
dtz_core.py - core logic for the VCS GAME.DTZ texture tool (no UI here).

Two containers share the same texture records:
  GAME.DTZ = one zlib stream -> 'GATG' memory image.
  *.XTX    = raw file, magic 'xet\\0': u32 size @8, relocation-table offset @12 and @16, entry count @20;
             the relocation table (u32 file offsets of pointer slots) sits at the very end of the file.
Textures are described by records in either. Each texture has a 16-byte descriptor:
    u32 0 | u16 width_in_bytes | u16 type | u32 data_offset | u32 flags
    type 0x25 = 8bpp (256-colour CLUT)   type 0x45 = 4bpp (16-colour CLUT)
    flags: bits 0-5 = log2(width px), bits 6-11 = log2(height px), top 16 bits = 0x001c
Pixel data is at data_offset, immediately followed by the CLUT (RGBA, alpha 0..0x80).
8bpp CLUTs use the PS2 CSM1 swizzle (entries 8-15 <-> 16-23 within each 32).
"""
import re, struct, zlib

VERSION = "0.4.1"
from PIL import Image

HDR_SIZE_OFFSET = 8          # u32 total image size in the GATG header


def _px(im):
    return list(im.get_flattened_data()) if hasattr(im, 'get_flattened_data') else list(im.getdata())


IMPORT_EXTS = ('.png', '.bmp', '.jpg', '.jpeg', '.tga', '.tif', '.tiff', '.webp', '.gif', '.dds')
EXPORT_FORMATS = {'PNG': '.png', 'BMP': '.bmp', 'TGA': '.tga', 'TIFF': '.tif', 'WEBP': '.webp', 'JPG (no alpha)': '.jpg'}
RESAMPLE = {'Smooth (Lanczos)': Image.LANCZOS, 'Bicubic': Image.BICUBIC, 'Bilinear': Image.BILINEAR,
            'Sharp / pixel art (Nearest)': Image.NEAREST}
MIN_SIDE, MAX_SIDE = 8, 2048
SIZES = [8, 16, 32, 64, 128, 256, 512, 1024, 2048]


def nearest_pow2(n):
    """Nearest power of two (by ratio) within MIN_SIDE..MAX_SIDE."""
    import math
    n = max(1, int(n))
    p = 2 ** round(math.log2(n))
    return min(MAX_SIDE, max(MIN_SIDE, p))


def has_alpha(im):
    a = im.convert('RGBA').getchannel('A')
    return a.getextrema()[0] < 255


def count_colours(im, limit=1 << 20):
    c = im.convert('RGBA').getcolors(maxcolors=limit)
    return None if c is None else len(c)


def load_image(path):
    """Open any supported image as RGBA. A companion '<name>_alpha.png/.bmp/.tga' (grey-scale) is
    merged in as the alpha channel when the main image itself has no transparency (e.g. JPG/BMP)."""
    import os
    im = Image.open(path); im.load(); im = im.convert('RGBA')
    stem, ext = os.path.splitext(path)
    if not stem.lower().endswith('_alpha') and not has_alpha(im):
        for e in ('.png', '.bmp', '.tga', '.tif'):
            ap = stem + '_alpha' + e
            if os.path.exists(ap):
                a = Image.open(ap).convert('L')
                if a.size != im.size:
                    a = a.resize(im.size, Image.BILINEAR)
                im.putalpha(a); break
    return im


def save_image(im, path, alpha_map=False):
    """Save RGBA image; formats without alpha (JPG) are flattened and always get a separate alpha map
    when the image has transparency. Returns list of files written."""
    import os
    stem, ext = os.path.splitext(path); ext = ext.lower()
    out = [path]
    transp = has_alpha(im)
    if ext in ('.jpg', '.jpeg'):
        bg = Image.new('RGB', im.size, (0, 0, 0)); bg.paste(im, mask=im.getchannel('A')); bg.save(path, quality=98)
        alpha_map = alpha_map or transp
    else:
        im.save(path)
    if alpha_map and transp:
        ap = stem + '_alpha.png'; im.getchannel('A').save(ap); out.append(ap)
    return out


def prepare(im, W, H, fit='stretch', resample=Image.LANCZOS):
    """Resize RGBA image to exactly WxH. fit: 'stretch' | 'fit' (keep aspect, transparent padding) |
    'fill' (keep aspect, centre crop)."""
    im = im.convert('RGBA')
    if im.size == (W, H):
        return im
    w, h = im.size
    if fit == 'stretch':
        return im.resize((W, H), resample)
    sc = min(W / w, H / h) if fit == 'fit' else max(W / w, H / h)
    nw, nh = max(1, round(w * sc)), max(1, round(h * sc))
    r = im.resize((nw, nh), resample)
    if fit == 'fit':
        out = Image.new('RGBA', (W, H), (0, 0, 0, 0)); out.paste(r, ((W - nw) // 2, (H - nh) // 2)); return out
    l, t = (nw - W) // 2, (nh - H) // 2
    return r.crop((l, t, l + W, t + H))


def alpha_view(im):
    a = im.getchannel('A'); return Image.merge('RGBA', (a, a, a, Image.new('L', im.size, 255)))


def opaque_view(im):
    out = im.copy(); out.putalpha(255); return out


class DtzFile:
    """Opens GAME.DTZ or a .XTX texture file (class name kept for compatibility)."""
    def __init__(self, path):
        self.path = path
        self.raw = open(path, 'rb').read()
        if self.raw[:4] == b'xet\0':
            self.kind = 'xtx'
            self.original = bytearray(self.raw)
            size, tab, tab2, cnt = struct.unpack_from('<IIII', self.original, 8)
            if size != len(self.original) or tab != tab2 or tab + 4 * cnt != size:
                raise ValueError('Unexpected XTX layout (header fields do not match the file).')
            self.orig_tab = tab
        else:
            self.kind = 'dtz'
            try:
                self.original = bytearray(zlib.decompress(self.raw))
            except zlib.error:
                raise ValueError('Not a GAME.DTZ or .XTX file.')
            if self.original[:4] != b'GATG':
                raise ValueError('Not a GAME.DTZ (inner magic is not GATG).')
        self.img = bytearray(self.original)
        self.textures = self._find_textures(self.original)
        self.changed = set()                      # indexes into self.textures
        self.resized = set()                      # descriptor offsets that were moved/enlarged

    # ---------- parsing ----------
    @staticmethod
    def _find_textures(img):
        n = len(img); out = []
        for m in re.finditer(rb'[A-Za-z_][A-Za-z0-9_.\-]{2,40}\x00+', bytes(img)):
            s = m.start()
            if s < 16 or s % 16:
                continue
            name = m.group().rstrip(b'\0').decode()
            p0 = struct.unpack_from('<I', img, s - 16)[0]
            if not (0 < p0 < n - 16):
                continue
            a, b, off, fl = struct.unpack_from('<IIII', img, p0)
            t = b >> 16; wb = b & 0xffff
            if a != 0 or t not in (0x25, 0x45) or (fl >> 16) not in (0x10, 0x1c):
                continue
            t_ = DtzFile._mk(name, p0, off, t, fl)
            if t_ and off + t_['psize'] + t_['ncol'] * 4 <= n:
                if (wb * (2 if t_['bpp'] == 4 else 1)) == t_['w']:
                    out.append(t_)
        return out

    @staticmethod
    def _mk(name, desc, off, t, fl):
        W = 1 << (fl & 0x3f); H = 1 << ((fl >> 6) & 0x3f)
        bpp = 4 if t == 0x45 else 8
        return dict(name=name, desc=desc, off=off, w=W, h=H, bpp=bpp,
                    psize=W * H // (2 if bpp == 4 else 1), ncol=16 if bpp == 4 else 256)

    def label(self, i):
        """Unique display name (duplicates get __2, __3 ...)."""
        nm = self.textures[i]['name']; k = sum(1 for j in range(i) if self.textures[j]['name'] == nm)
        return nm if k == 0 else f'{nm}__{k + 1}'

    # ---------- decode ----------
    @staticmethod
    def _swz(pal):
        o = list(pal)
        for b in range(0, 256, 32):
            for i in range(8):
                o[b + 8 + i], o[b + 16 + i] = pal[b + 16 + i], pal[b + 8 + i]
        return o

    def decode(self, i, source=None):
        t = self.textures[i]; img = source if source is not None else self.img
        return self._decode(img, t)

    def _decode(self, img, t):
        off = t['off']
        raw = img[off + t['psize']: off + t['psize'] + t['ncol'] * 4]
        pal = [tuple(raw[k * 4:k * 4 + 4]) for k in range(t['ncol'])]
        if t['bpp'] == 8:
            pal = self._swz(pal)
        pal = [(r, g, b, min(255, a * 2)) for r, g, b, a in pal]
        px = img[off:off + t['psize']]
        idx = [v for byte in px for v in (byte & 15, byte >> 4)] if t['bpp'] == 4 else list(px)
        im = Image.new('RGBA', (t['w'], t['h'])); im.putdata([pal[k] for k in idx])
        return im

    # ---------- encode ----------
    def _quantise(self, im, ncol, bpp, dither=False):
        """-> (pixel bytes, CLUT bytes, preview RGBA image of what the game will show)"""
        im = im.convert('RGBA')
        transp = has_alpha(im)
        if transp:
            q = im.quantize(colors=ncol, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.NONE)
        else:
            q = im.convert('RGB').quantize(colors=ncol, method=Image.Quantize.MEDIANCUT,
                                           dither=Image.Dither.FLOYDSTEINBERG if dither else Image.Dither.NONE)
        qp = q.getpalette()[:ncol * 3]; qp += [0] * (ncol * 3 - len(qp))
        idx = _px(q); rgba = _px(im)
        asum = [0] * ncol; cnt = [0] * ncol
        for k, p in zip(idx, rgba):
            asum[k] += p[3]; cnt[k] += 1
        pal = [(qp[k * 3], qp[k * 3 + 1], qp[k * 3 + 2], (asum[k] // cnt[k] if cnt[k] else 255)) for k in range(ncol)]
        pal = [(r, g, b, (a + 1) // 2) for r, g, b, a in pal]        # PS2 alpha 0..0x80
        shown = [(r, g, b, min(255, a * 2)) for r, g, b, a in pal]
        prev = Image.new('RGBA', im.size); prev.putdata([shown[k] for k in idx])
        if bpp == 8:
            pal = self._swz(pal)
        if bpp == 4:
            px = bytes((idx[k] & 15) | (idx[k + 1] << 4) for k in range(0, len(idx), 2))
        else:
            px = bytes(idx)
        return px, b''.join(bytes(c) for c in pal), prev

    def preview_conversion(self, i, im, dither=False):
        """What texture i would look like after importing im (same size as im)."""
        t = self.textures[i]
        return self._quantise(im, t['ncol'], t['bpp'], dither)[2]

    @staticmethod
    def _pow2(n):
        return n >= MIN_SIDE and (n & (n - 1)) == 0

    def import_image(self, i, im, allow_resize=True, dither=False):
        """Replace texture i with PIL image. Same size -> in place. Different size -> append & repoint.
        Returns 'same' | 'resized' | 'unchanged'."""
        t = self.textures[i]
        im = im.convert('RGBA')
        if im.size == (t['w'], t['h']):
            if _px(im) == _px(self._decode(self.img, t)):
                return 'unchanged'
            px, pal, _ = self._quantise(im, t['ncol'], t['bpp'], dither)
            self.img[t['off']:t['off'] + t['psize']] = px
            self.img[t['off'] + t['psize']:t['off'] + t['psize'] + len(pal)] = pal
            self.changed.add(i); return 'same'
        if not allow_resize:
            raise ValueError(f"{self.label(i)}: image is {im.size[0]}x{im.size[1]}, texture is {t['w']}x{t['h']}.")
        W, H = im.size
        if not (self._pow2(W) and self._pow2(H)) or W > MAX_SIDE or H > MAX_SIDE:
            raise ValueError(f'{self.label(i)}: size {W}x{H} must be power-of-two sides ({MIN_SIDE}..{MAX_SIDE}).')
        px, pal, _ = self._quantise(im, t['ncol'], t['bpp'], dither)
        if self.kind == 'xtx':
            # new pixels go in front of the relocation table, which moves to the end of the file
            tab = struct.unpack_from('<I', self.img, 12)[0]
            table = bytes(self.img[tab:]); del self.img[tab:]
        while len(self.img) % 64:
            self.img.append(0)
        new_off = len(self.img)
        self.img += px + pal
        while len(self.img) % 64:
            self.img.append(0)
        if self.kind == 'xtx':
            new_tab = len(self.img); self.img += table
            struct.pack_into('<III', self.img, 8, len(self.img), new_tab, new_tab)
        else:
            struct.pack_into('<I', self.img, HDR_SIZE_OFFSET, len(self.img))   # keep header size in sync
        wb = W // 2 if t['bpp'] == 4 else W
        lw = W.bit_length() - 1; lh = H.bit_length() - 1
        old_fl = struct.unpack_from('<I', self.img, t['desc'] + 12)[0]
        fl = (old_fl & ~0xFFF) | (lh << 6) | lw          # keep every flag bit except the two size fields
        typ = 0x45 if t['bpp'] == 4 else 0x25
        struct.pack_into('<IIII', self.img, t['desc'], 0, (typ << 16) | wb, new_off, fl)
        self.resized.add(t['desc'])
        for k, o in enumerate(self.textures):
            if o['desc'] == t['desc']:
                self.textures[k] = self._mk(o['name'], o['desc'], new_off, typ, fl)
                self.changed.add(k)
        return 'resized'

    def revert(self, i):
        t = self.textures[i]; d = t['desc']
        self.img[d:d + 16] = self.original[d:d + 16]
        a, b, off, fl = struct.unpack_from('<IIII', self.original, d)
        for k, o in enumerate(self.textures):
            if o['desc'] == d:
                self.textures[k] = self._mk(o['name'], d, off, b >> 16, fl)
                self.changed.discard(k)
        self.resized.discard(d)
        t = self.textures[i]
        end = t['off'] + t['psize'] + t['ncol'] * 4
        self.img[t['off']:end] = self.original[t['off']:end]
        if not self.resized:                       # nothing enlarged any more: drop appended data
            if self.kind == 'xtx':
                self.img = self.img[:self.orig_tab] + self.original[self.orig_tab:]
                self.img[8:20] = self.original[8:20]
            else:
                del self.img[len(self.original):]
                self.img[HDR_SIZE_OFFSET:HDR_SIZE_OFFSET + 4] = self.original[HDR_SIZE_OFFSET:HDR_SIZE_OFFSET + 4]

    # ---------- save ----------
    def build(self):
        return bytes(self.img) if self.kind == 'xtx' else zlib.compress(bytes(self.img), 9)

    def save(self, path):
        data = self.build()
        open(path, 'wb').write(data)
        return len(data)


# ======================================================================
# Batch mode: work on every .XTX / .DTZ in a folder
# ======================================================================
import os


def find_game_files(folder):
    return sorted(os.path.join(folder, f) for f in os.listdir(folder)
                  if f.lower().endswith(('.xtx', '.dtz')) and os.path.isfile(os.path.join(folder, f)))


def _stem(path):
    return os.path.splitext(os.path.basename(path))[0]


def batch_export(src, out, ext='.png', alpha_map=False, progress=None):
    """Export every texture of every .XTX/.DTZ in src to out/<file name without extension>/<texture><ext>."""
    files = find_game_files(src); n_tex = 0; problems = []
    for k, p in enumerate(files):
        if progress: progress(k, len(files), os.path.basename(p))
        try:
            f = DtzFile(p)
        except Exception as e:
            problems.append(f'{os.path.basename(p)}: {e}'); continue
        d = os.path.join(out, _stem(p)); os.makedirs(d, exist_ok=True)
        for i in range(len(f.textures)):
            save_image(f.decode(i), os.path.join(d, f.label(i) + ext), alpha_map); n_tex += 1
    if progress: progress(len(files), len(files), 'done')
    return dict(files=len(files), textures=n_tex, problems=problems)


def _image_index(folder):
    idx = {}
    if os.path.isdir(folder):
        for f in sorted(os.listdir(folder)):
            stem, ext = os.path.splitext(f)
            if ext.lower() in IMPORT_EXTS and not stem.lower().endswith('_alpha'):
                idx.setdefault(stem.lower(), os.path.join(folder, f))
    return idx


def _size_ok(w, h):
    return DtzFile._pow2(w) and DtzFile._pow2(h) and w <= MAX_SIDE and h <= MAX_SIDE


def batch_plan(src, imgs, progress=None):
    """Match edited images to textures. For file NAME.XTX images are looked up in imgs/NAME/ first, then in
    imgs/ itself; a file with a single texture also accepts imgs/NAME.png. Returns (plan, problems)."""
    files = find_game_files(src); plan = []; problems = []; cache = {}
    def idx(d):
        if d not in cache: cache[d] = _image_index(d)
        return cache[d]
    for k, p in enumerate(files):
        if progress: progress(k, len(files), os.path.basename(p))
        try:
            f = DtzFile(p)
        except Exception as e:
            problems.append(f'{os.path.basename(p)}: {e}'); continue
        stem = _stem(p); items = []
        for i, t in enumerate(f.textures):
            lab = f.label(i).lower(); found = None
            for d in (os.path.join(imgs, stem), imgs):
                found = idx(d).get(lab)
                if found: break
            if not found and len(f.textures) == 1:
                found = idx(imgs).get(stem.lower())
            if found:
                try: size = Image.open(found).size
                except Exception as e: problems.append(f'{os.path.basename(found)}: {e}'); continue
                items.append(dict(index=i, label=f.label(i), image=found, size=size, tex=(t['w'], t['h'])))
        if items:
            plan.append(dict(path=p, name=os.path.basename(p), items=items))
    return plan, problems


def plan_summary(plan):
    items = [(e['name'], it) for e in plan for it in e['items']]
    bad = [f"{n}:{it['label']}" for n, it in items if not _size_ok(*it['size'])]
    diff = [f"{n}:{it['label']}" for n, it in items if it['size'] != it['tex']]
    return dict(files=len(plan), images=len(items), non_pow2=bad, different=diff)


def batch_import(plan, src, out, nonpow2='convert', dither=False, progress=None):
    """Apply a plan; modified files are written to out with their original names (out must differ from src).
    nonpow2: 'convert' (stretch to nearest power of two) or 'skip'."""
    if os.path.abspath(out) == os.path.abspath(src):
        raise ValueError('The output folder must be different from the folder with the original files.')
    os.makedirs(out, exist_ok=True)
    rep = dict(files_written=[], textures_changed=0, unchanged=0, skipped=0, problems=[])
    for k, e in enumerate(plan):
        if progress: progress(k, len(plan), e['name'])
        try:
            f = DtzFile(e['path']); changed = 0
        except Exception as ex:
            rep['problems'].append(f"{e['name']}: {ex}"); continue
        for it in e['items']:
            try:
                im = load_image(it['image'])
                if not _size_ok(*im.size):
                    if nonpow2 != 'convert':
                        rep['skipped'] += 1; continue
                    im = prepare(im, nearest_pow2(im.width), nearest_pow2(im.height), 'stretch')
                r = f.import_image(it['index'], im, dither=dither)
                if r == 'unchanged': rep['unchanged'] += 1
                else: changed += 1
            except Exception as ex:
                rep['problems'].append(f"{e['name']} / {it['label']}: {ex}")
        if changed:
            f.save(os.path.join(out, e['name'])); rep['files_written'].append(e['name']); rep['textures_changed'] += changed
    if progress: progress(len(plan), len(plan), 'done')
    return rep
