"""VCS GAME.DTZ / .XTX Texture Tool - window app. Run via Start.bat."""
import os, sys, shutil, struct, tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dtz_core as core
from dtz_core import DtzFile

_exts = ' '.join('*' + e for e in core.IMPORT_EXTS)
IMG_TYPES = [('All supported images', _exts), ('PNG', '*.png'), ('BMP', '*.bmp'), ('JPEG', '*.jpg *.jpeg'),
             ('TGA', '*.tga'), ('TIFF', '*.tif *.tiff'), ('WEBP', '*.webp'), ('DDS', '*.dds'), ('All files', '*.*')]
VIEW_MODES = [('Colour + alpha', 'both'), ('Colour only', 'colour'), ('Alpha only', 'alpha')]


def checker(w, h, cs=8):
    bg = Image.new('RGBA', (w, h)); tile = Image.new('RGBA', (cs * 2, cs * 2), (60, 60, 60, 255))
    tile.paste((90, 90, 90, 255), (cs, 0, cs * 2, cs)); tile.paste((90, 90, 90, 255), (0, cs, cs, cs * 2))
    for ty in range(0, h, cs * 2):
        for tx in range(0, w, cs * 2):
            bg.paste(tile, (tx, ty))
    return bg


def render(im, mode, w, h):
    """Return a PhotoImage of im scaled to w x h in the given alpha view mode."""
    if mode == 'alpha':
        im = core.alpha_view(im)
    elif mode == 'colour':
        im = core.opaque_view(im)
    bg = checker(w, h); bg.alpha_composite(im.resize((w, h), Image.NEAREST))
    return ImageTk.PhotoImage(bg)


class ImportDialog(tk.Toplevel):
    """Shows the source image, lets you choose the target size / fit / resampling and previews the
    palette-reduced result. .result = (RGBA image at final size, dither flag) or None."""
    def __init__(self, parent, dtz, idx, src, srcname):
        super().__init__(parent)
        self.title('Import: ' + dtz.label(idx)); self.geometry('1000x680'); self.minsize(820, 560)
        self.transient(parent); self.result = None
        self.dtz, self.idx, self.src = dtz, idx, src
        t = dtz.textures[idx]; self.t = t
        sw, sh = src.size; self.srcalpha = core.has_alpha(src); self.photo = None; self._job = None
        left = ttk.Frame(self, padding=8); left.pack(side='left', fill='y')
        ttk.Label(left, text=f'File: {srcname}\nSource: {sw} x {sh}  ({core.count_colours(src) or "many"} colours, '
                             f'{"has" if self.srcalpha else "no"} transparency)\n'
                             f'Texture: {t["w"]} x {t["h"]}, {t["bpp"]}-bit ({t["ncol"]} colours)', justify='left').pack(anchor='w')
        ttk.Separator(left).pack(fill='x', pady=6)
        ttk.Label(left, text='Target size (power of two)').pack(anchor='w')
        row = ttk.Frame(left); row.pack(anchor='w', pady=2)
        nw, nh = core.nearest_pow2(sw), core.nearest_pow2(sh)
        self.vw = tk.StringVar(value=str(nw)); self.vh = tk.StringVar(value=str(nh))
        ttk.Combobox(row, textvariable=self.vw, values=core.SIZES, width=6, state='readonly').pack(side='left')
        ttk.Label(row, text=' x ').pack(side='left')
        ttk.Combobox(row, textvariable=self.vh, values=core.SIZES, width=6, state='readonly').pack(side='left')
        pr = ttk.Frame(left); pr.pack(anchor='w', pady=2)
        for txt, f in (('Nearest to source', lambda: self.setsize(nw, nh)),
                       ('Original size', lambda: self.setsize(t['w'], t['h'])),
                       ('2x', lambda: self.setsize(t['w'] * 2, t['h'] * 2)),
                       ('4x', lambda: self.setsize(t['w'] * 4, t['h'] * 4))):
            ttk.Button(pr, text=txt, command=f).pack(side='left', padx=(0, 4))
        ttk.Label(left, text='If the shape differs from the target').pack(anchor='w', pady=(8, 0))
        self.fit = tk.StringVar(value='stretch')
        for txt, v in (('Stretch to fill', 'stretch'), ('Fit inside (keep shape, transparent padding)', 'fit'),
                       ('Fill (keep shape, crop the overflow)', 'fill')):
            ttk.Radiobutton(left, text=txt, value=v, variable=self.fit, command=self.schedule).pack(anchor='w')
        ttk.Label(left, text='Resize quality').pack(anchor='w', pady=(8, 0))
        self.rs = tk.StringVar(value=list(core.RESAMPLE)[0])
        cb = ttk.Combobox(left, textvariable=self.rs, values=list(core.RESAMPLE), state='readonly', width=28); cb.pack(anchor='w')
        cb.bind('<<ComboboxSelected>>', lambda e: self.schedule())
        self.dither = tk.BooleanVar(value=False)
        self.dcb = ttk.Checkbutton(left, text='Dither colour reduction (opaque images only)', variable=self.dither, command=self.schedule)
        self.dcb.pack(anchor='w', pady=(8, 0))
        if self.srcalpha: self.dcb.state(['disabled'])
        ttk.Label(left, text='Preview').pack(anchor='w', pady=(8, 0))
        self.pshow = tk.StringVar(value='conv')
        for txt, v in (('Converted (what the game gets)', 'conv'), ('Resized, full colour', 'full'), ('Alpha only', 'alpha')):
            ttk.Radiobutton(left, text=txt, value=v, variable=self.pshow, command=self.draw).pack(anchor='w')
        ttk.Separator(left).pack(fill='x', pady=6)
        self.msg = ttk.Label(left, text='', justify='left', wraplength=330, foreground='#444'); self.msg.pack(anchor='w')
        bb = ttk.Frame(left); bb.pack(side='bottom', anchor='e', pady=6, fill='x')
        ttk.Button(bb, text='Cancel', command=self.destroy).pack(side='right')
        ttk.Button(bb, text='Import', command=self.ok).pack(side='right', padx=6)
        self.canvas = tk.Canvas(self, bg='#303030', highlightthickness=0); self.canvas.pack(side='left', fill='both', expand=True)
        self.canvas.bind('<Configure>', lambda e: self.draw())
        self.vw.trace_add('write', lambda *a: self.schedule()); self.vh.trace_add('write', lambda *a: self.schedule())
        self.schedule(0)
        self.grab_set(); self.wait_window(self)

    def setsize(self, w, h):
        w = min(core.MAX_SIDE, max(core.MIN_SIDE, w)); h = min(core.MAX_SIDE, max(core.MIN_SIDE, h))
        self.vw.set(str(w)); self.vh.set(str(h))

    def schedule(self, delay=200):
        if self._job: self.after_cancel(self._job)
        self._job = self.after(delay, self.update_preview)

    def update_preview(self):
        self._job = None
        try: W, H = int(self.vw.get()), int(self.vh.get())
        except ValueError: return
        self.prepared = core.prepare(self.src, W, H, self.fit.get(), core.RESAMPLE[self.rs.get()])
        pv = self.prepared
        approx = W * H > 512 * 512
        if approx:                       # keep the dialog responsive: preview the conversion on a smaller copy
            s = 512 / max(W, H); pv = self.prepared.resize((max(8, int(W * s)), max(8, int(H * s))), Image.LANCZOS)
        self.conv = self.dtz.preview_conversion(self.idx, pv, self.dither.get() and not self.srcalpha)
        t = self.t; same = (W, H) == (t['w'], t['h'])
        n = core.count_colours(self.prepared) if W * H <= 1 << 20 else None
        txt = f'Result: {W} x {H}.  Colours {n if n else "many"} -> {t["ncol"]}.'
        txt += ('\nSame size as the original: replaced in place (safest).' if same else
                '\nDIFFERENT size: stored as an enlarged texture at the end of the file (experimental; the game/recomp must accept it).')
        if approx: txt += '\n(Preview of the colour conversion is approximate for large images; the import itself is exact.)'
        self.msg.config(text=txt); self.draw()

    def draw(self):
        if not getattr(self, 'prepared', None): return
        im = {'conv': self.conv, 'full': self.prepared, 'alpha': self.prepared}[self.pshow.get()]
        cw, ch = max(self.canvas.winfo_width(), 50), max(self.canvas.winfo_height(), 50)
        z = min(cw / im.width, ch / im.height); w, h = max(1, int(im.width * z)), max(1, int(im.height * z))
        self.photo = render(im, 'alpha' if self.pshow.get() == 'alpha' else 'both', w, h)
        self.canvas.delete('all'); self.canvas.create_image(cw // 2, ch // 2, image=self.photo)

    def ok(self):
        if self._job: self.after_cancel(self._job); self.update_preview()
        self.result = (self.prepared, self.dither.get() and not self.srcalpha); self.destroy()


class Progress(tk.Toplevel):
    """Small 'working' window for batch jobs."""
    def __init__(self, parent, title):
        super().__init__(parent); self.title(title); self.geometry('420x110'); self.resizable(False, False)
        self.transient(parent)
        self.lbl = ttk.Label(self, text='Starting...', padding=10); self.lbl.pack(fill='x')
        self.bar = ttk.Progressbar(self, maximum=100, length=380); self.bar.pack(padx=10)
        self.update()

    def step(self, i, n, text):
        self.lbl.config(text=f'{i}/{n}   {text}'); self.bar.config(value=100 * i / max(1, n)); self.update()


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f'VCS GAME.DTZ / XTX Texture Tool v{core.VERSION}')
        self.geometry('1150x760'); self.minsize(950, 600)
        self.dtz = None; self.zoom = None; self.eff = 1.0; self.photo = None; self.view = []   # zoom None = fit
        self.compare = tk.BooleanVar(value=False); self.vmode = tk.StringVar(value='both')
        self.xfmt = tk.StringVar(value='PNG'); self.xalpha = tk.BooleanVar(value=False)
        self._build_ui()
        self.protocol('WM_DELETE_WINDOW', self.on_close)

    # ---------- UI ----------
    def _build_ui(self):
        bar = ttk.Frame(self, padding=6); bar.pack(fill='x')
        ttk.Button(bar, text='Open GAME.DTZ / .XTX...', command=self.open_dtz).pack(side='left')
        ttk.Button(bar, text='Save file...', command=self.save_dtz).pack(side='left', padx=(6, 0))
        self.status = ttk.Label(bar, text='No file loaded.'); self.status.pack(side='left', padx=12)

        main = ttk.PanedWindow(self, orient='horizontal'); main.pack(fill='both', expand=True, padx=6, pady=(0, 6))
        left = ttk.Frame(main); main.add(left, weight=1)
        sf = ttk.Frame(left); sf.pack(fill='x')
        ttk.Label(sf, text='Search:').pack(side='left')
        self.q = tk.StringVar(); self.q.trace_add('write', lambda *a: self.refresh_list())
        ttk.Entry(sf, textvariable=self.q).pack(side='left', fill='x', expand=True, padx=4)
        lf = ttk.Frame(left); lf.pack(fill='both', expand=True, pady=4)
        self.lb = tk.Listbox(lf, activestyle='dotbox', exportselection=False, font=('Consolas', 10))
        sb = ttk.Scrollbar(lf, command=self.lb.yview); self.lb.config(yscrollcommand=sb.set)
        self.lb.pack(side='left', fill='both', expand=True); sb.pack(side='right', fill='y')
        self.lb.bind('<<ListboxSelect>>', lambda e: self.show())

        right = ttk.Frame(main); main.add(right, weight=3)
        self.info = ttk.Label(right, text='', justify='left'); self.info.pack(anchor='w')
        ex = ttk.Frame(right); ex.pack(fill='x', pady=(4, 0))
        ttk.Label(ex, text='Export format:').pack(side='left')
        ttk.Combobox(ex, textvariable=self.xfmt, values=list(core.EXPORT_FORMATS), width=14, state='readonly').pack(side='left', padx=4)
        ttk.Checkbutton(ex, text='also save alpha map (NAME_alpha.png)', variable=self.xalpha).pack(side='left', padx=6)
        ttk.Button(ex, text='Export selected...', command=self.export_sel).pack(side='left', padx=(10, 6))
        ttk.Button(ex, text='Export ALL to folder...', command=self.export_all).pack(side='left')
        im = ttk.Frame(right); im.pack(fill='x', pady=4)
        for txt, cmd in (('Import image...', self.import_sel), ('Import from folder...', self.import_folder),
                         ('Revert selected', self.revert_sel)):
            ttk.Button(im, text=txt, command=cmd).pack(side='left', padx=(0, 6))
        bt = ttk.Frame(right); bt.pack(fill='x', pady=(0, 4))
        ttk.Label(bt, text='Whole folder (e.g. SPLASH):').pack(side='left')
        ttk.Button(bt, text='Batch export folder...', command=self.batch_export_ui).pack(side='left', padx=6)
        ttk.Button(bt, text='Batch import into new folder...', command=self.batch_import_ui).pack(side='left')
        opts = ttk.Frame(right); opts.pack(fill='x')
        ttk.Button(opts, text='Zoom -', width=7, command=lambda: self.set_zoom(self.eff / 1.5)).pack(side='left')
        ttk.Button(opts, text='Zoom +', width=7, command=lambda: self.set_zoom(self.eff * 1.5)).pack(side='left', padx=4)
        ttk.Button(opts, text='Fit', width=5, command=lambda: self.set_zoom(None)).pack(side='left')
        ttk.Label(opts, text='   View:').pack(side='left')
        for txt, v in VIEW_MODES:
            ttk.Radiobutton(opts, text=txt, value=v, variable=self.vmode, command=self.show).pack(side='left', padx=2)
        ttk.Checkbutton(opts, text='Show original', variable=self.compare, command=self.show).pack(side='left', padx=10)
        self.canvas = tk.Canvas(right, bg='#303030', highlightthickness=0); self.canvas.pack(fill='both', expand=True, pady=4)
        self.canvas.bind('<Configure>', lambda e: self.show())
        ttk.Label(right, text='Import accepts PNG, BMP, JPG, TGA, TIFF, WEBP, GIF, DDS. Sizes are offered as powers of two '
                              '(256, 512, 1024...); colours are reduced to the texture\'s palette (16 or 256).',
                  foreground='#555', wraplength=760, justify='left').pack(anchor='w')

    # ---------- helpers ----------
    def need(self):
        if not self.dtz:
            messagebox.showinfo('No file', 'Open a GAME.DTZ or .XTX file first.'); return False
        return True

    def cur(self):
        s = self.lb.curselection()
        return self.view[s[0]] if s and self.view else None

    def refresh_list(self, keep=None):
        if not self.dtz: return
        q = self.q.get().lower().strip(); self.lb.delete(0, 'end'); self.view = []
        for i in range(len(self.dtz.textures)):
            nm = self.dtz.label(i)
            if q and q not in nm.lower(): continue
            t = self.dtz.textures[i]; mark = '*' if i in self.dtz.changed else ' '
            self.lb.insert('end', f"{mark} {nm:30s} {t['w']}x{t['h']}")
            self.view.append(i)
        if keep in self.view:
            self.lb.selection_set(self.view.index(keep)); self.lb.see(self.view.index(keep))
        self.update_status()

    def update_status(self):
        n = len(self.dtz.changed) if self.dtz else 0
        self.status.config(text=(f"{os.path.basename(self.dtz.path)}  -  {len(self.dtz.textures)} textures, {n} modified" if self.dtz else 'No file loaded.'))

    def set_zoom(self, z):
        self.zoom = z; self.show()

    def show(self):
        i = self.cur(); self.canvas.delete('all')
        if i is None: self.info.config(text=''); return
        t = self.dtz.textures[i]
        im = self.dtz.decode(i)
        tr = 'has transparency' if core.has_alpha(im) else 'opaque'
        self.info.config(text=f"{self.dtz.label(i)}    {t['w']} x {t['h']}    {t['bpp']}-bit indexed ({t['ncol']} colours)    {tr}    data @ 0x{t['off']:X}"
                              + ('    [MODIFIED]' if i in self.dtz.changed else ''))
        if self.compare.get() and i in self.dtz.changed:
            a, b, off, fl = struct.unpack_from('<IIII', self.dtz.original, t['desc'])
            im = self.dtz._decode(self.dtz.original, self.dtz._mk(t['name'], t['desc'], off, b >> 16, fl))
        cw, ch = max(self.canvas.winfo_width(), 50), max(self.canvas.winfo_height(), 50)
        z = self.zoom if self.zoom else min(cw / im.width, ch / im.height)
        self.eff = z
        w, h = max(1, int(im.width * z)), max(1, int(im.height * z))
        self.photo = render(im, self.vmode.get(), w, h)
        self.canvas.create_image(cw // 2, ch // 2, image=self.photo)

    # ---------- export ----------
    def export_sel(self):
        if not self.need(): return
        i = self.cur()
        if i is None: return
        ext = core.EXPORT_FORMATS[self.xfmt.get()]
        p = filedialog.asksaveasfilename(defaultextension=ext, initialfile=self.dtz.label(i) + ext,
                                         filetypes=[(k, '*' + v) for k, v in core.EXPORT_FORMATS.items()])
        if not p: return
        try:
            files = core.save_image(self.dtz.decode(i), p, self.xalpha.get())
        except Exception as e:
            messagebox.showerror('Export failed', str(e)); return
        messagebox.showinfo('Exported', '\n'.join(files))

    def export_all(self):
        if not self.need(): return
        d = filedialog.askdirectory(title='Export all textures to folder')
        if not d: return
        ext = core.EXPORT_FORMATS[self.xfmt.get()]; n = 0
        for i in range(len(self.dtz.textures)):
            n += len(core.save_image(self.dtz.decode(i), os.path.join(d, self.dtz.label(i) + ext), self.xalpha.get()))
        messagebox.showinfo('Exported', f'{n} file(s) written to:\n{d}')

    # ---------- import ----------
    def import_sel(self):
        if not self.need(): return
        i = self.cur()
        if i is None: return
        p = filedialog.askopenfilename(title='Import image for ' + self.dtz.label(i), filetypes=IMG_TYPES)
        if not p: return
        try:
            src = core.load_image(p)
        except Exception as e:
            messagebox.showerror('Cannot read image', str(e)); return
        dlg = ImportDialog(self, self.dtz, i, src, os.path.basename(p))
        if not dlg.result: return
        im, dither = dlg.result
        try:
            r = self.dtz.import_image(i, im, dither=dither)
        except Exception as e:
            messagebox.showerror('Import failed', str(e)); return
        if r == 'unchanged': messagebox.showinfo('Import', 'Image is identical to the current texture; nothing changed.')
        self.refresh_list(keep=i); self.show()

    def import_folder(self):
        if not self.need(): return
        d = filedialog.askdirectory(title='Folder with edited images (named like the textures)')
        if not d: return
        files = {}
        for f in sorted(os.listdir(d)):
            stem, ext = os.path.splitext(f)
            if ext.lower() in core.IMPORT_EXTS and not stem.lower().endswith('_alpha'):
                files.setdefault(stem.lower(), os.path.join(d, f))
        todo = [(i, files[self.dtz.label(i).lower()]) for i in range(len(self.dtz.textures)) if self.dtz.label(i).lower() in files]
        if not todo:
            messagebox.showinfo('Import', 'No files in that folder match texture names.'); return
        loaded = []; errs = []
        for i, p in todo:
            try: loaded.append((i, core.load_image(p)))
            except Exception as e: errs.append(f'{os.path.basename(p)}: {e}')
        bad = {i for i, im in loaded if not (DtzFile._pow2(im.width) and DtzFile._pow2(im.height) and im.width <= core.MAX_SIDE and im.height <= core.MAX_SIDE)}
        diff = [self.dtz.label(i) for i, im in loaded if im.size != (self.dtz.textures[i]['w'], self.dtz.textures[i]['h'])]
        auto = False
        if bad:
            ans = messagebox.askyesnocancel('Sizes are not powers of two',
                f'{len(bad)} image(s) are not power-of-two sizes ({", ".join(self.dtz.label(i) for i in sorted(bad)[:8])}...).\n\n'
                'YES = convert them automatically to the nearest power of two (stretched)\n'
                'NO = skip those images\nCANCEL = abort the whole import')
            if ans is None: return
            auto = ans
        elif diff and not messagebox.askyesno('Different sizes',
                'These images differ in size from the originals and will be stored as enlarged textures (experimental):\n\n'
                + ', '.join(diff[:15]) + (' ...' if len(diff) > 15 else '') + '\n\nContinue?'):
            return
        ok = skipped = 0
        for i, im in loaded:
            try:
                if i in bad:
                    if not auto: skipped += 1; continue
                    im = core.prepare(im, core.nearest_pow2(im.width), core.nearest_pow2(im.height), 'stretch')
                if self.dtz.import_image(i, im) in ('same', 'resized'): ok += 1
            except Exception as e:
                errs.append(str(e))
        self.refresh_list(); self.show()
        messagebox.showinfo('Import finished', f'{ok} texture(s) imported' + (f', {skipped} skipped' if skipped else '') + '.'
                            + (('\n\nProblems:\n' + '\n'.join(errs[:10])) if errs else ''))

    def revert_sel(self):
        if not self.need(): return
        i = self.cur()
        if i is None: return
        self.dtz.revert(i); self.refresh_list(keep=i); self.show()

    # ---------- batch ----------
    def batch_export_ui(self):
        src = filedialog.askdirectory(title='Folder with the .XTX / .DTZ files (e.g. SPLASH)')
        if not src: return
        if not core.find_game_files(src):
            messagebox.showinfo('Batch export', 'No .XTX or .DTZ files in that folder.'); return
        out = filedialog.askdirectory(title='Folder to write the images into (one sub-folder per file)')
        if not out: return
        pg = Progress(self, 'Exporting...')
        try:
            r = core.batch_export(src, out, core.EXPORT_FORMATS[self.xfmt.get()], self.xalpha.get(), progress=pg.step)
        except Exception as e:
            pg.destroy(); messagebox.showerror('Batch export failed', str(e)); return
        pg.destroy()
        messagebox.showinfo('Batch export finished', f"{r['textures']} texture(s) from {r['files']} file(s) exported to:\n{out}"
                            + (('\n\nProblems:\n' + '\n'.join(r['problems'][:10])) if r['problems'] else ''))

    def batch_import_ui(self):
        src = filedialog.askdirectory(title='1/3  Folder with the ORIGINAL .XTX / .DTZ files')
        if not src: return
        imgs = filedialog.askdirectory(title='2/3  Folder with your edited images (sub-folder per file, as exported)')
        if not imgs: return
        out = filedialog.askdirectory(title='3/3  NEW folder for the modified files (not the originals folder)')
        if not out: return
        if os.path.abspath(out) == os.path.abspath(src):
            messagebox.showerror('Batch import', 'The output folder must be different from the folder with the original files.'); return
        pg = Progress(self, 'Matching images...')
        try:
            plan, probs = core.batch_plan(src, imgs, progress=pg.step)
        except Exception as e:
            pg.destroy(); messagebox.showerror('Batch import failed', str(e)); return
        pg.destroy()
        if not plan:
            messagebox.showinfo('Batch import', 'No images in that folder match textures in the original files.'
                                + (('\n\n' + '\n'.join(probs[:5])) if probs else '')); return
        sm = core.plan_summary(plan); mode = 'convert'
        if sm['non_pow2']:
            ans = messagebox.askyesnocancel('Sizes are not powers of two',
                f"{len(sm['non_pow2'])} image(s) are not power-of-two sizes ({', '.join(sm['non_pow2'][:6])}...).\n\n"
                'YES = convert them to the nearest power of two (stretched)\nNO = skip those images\nCANCEL = abort')
            if ans is None: return
            mode = 'convert' if ans else 'skip'
        elif sm['different'] and not messagebox.askyesno('Different sizes',
                f"{len(sm['different'])} image(s) differ in size from the originals and will be stored as enlarged textures "
                f"(experimental): {', '.join(sm['different'][:6])}...\n\nContinue?"):
            return
        pg = Progress(self, 'Importing...')
        try:
            r = core.batch_import(plan, src, out, mode, progress=pg.step)
        except Exception as e:
            pg.destroy(); messagebox.showerror('Batch import failed', str(e)); return
        pg.destroy()
        messagebox.showinfo('Batch import finished',
            f"{r['textures_changed']} texture(s) changed; {len(r['files_written'])} file(s) written to:\n{out}\n\n"
            f"Unchanged images: {r['unchanged']}   Skipped: {r['skipped']}\n"
            'Copy the files you want into the game folder (keep a backup of the originals).'
            + (('\n\nProblems:\n' + '\n'.join((r['problems'] + probs)[:10])) if (r['problems'] or probs) else ''))

    def open_dtz(self):
        p = filedialog.askopenfilename(title='Open GAME.DTZ or .XTX', filetypes=[('Game texture files', '*.dtz *.DTZ *.xtx *.XTX'), ('DTZ', '*.dtz *.DTZ'), ('XTX', '*.xtx *.XTX'), ('All files', '*.*')])
        if not p: return
        try:
            self.dtz = DtzFile(p)
        except Exception as e:
            messagebox.showerror('Cannot open', str(e)); return
        self.zoom = None; self.refresh_list()
        if self.view: self.lb.selection_set(0); self.show()

    def save_dtz(self):
        if not self.need(): return
        ext = '.XTX' if self.dtz.kind == 'xtx' else '.DTZ'
        p = filedialog.asksaveasfilename(title='Save modified file (keep the original file name for the game)', defaultextension=ext,
                                         initialfile=os.path.basename(self.dtz.path),
                                         filetypes=[('Game texture file', '*' + ext), ('All files', '*.*')])
        if not p: return
        try:
            if os.path.exists(p) and not os.path.exists(p + '.bak'):
                shutil.copy2(p, p + '.bak')                       # one-time backup of whatever you overwrite
            n = self.dtz.save(p)
        except Exception as e:
            messagebox.showerror('Save failed', str(e)); return
        messagebox.showinfo('Saved', f'Saved {p}\n({n:,} bytes, {len(self.dtz.changed)} modified texture(s)).\n'
                                     'If a file was overwritten, the old one was kept as .bak.')

    def on_close(self):
        if self.dtz and self.dtz.changed and not messagebox.askyesno('Quit', 'You have unsaved changes. Quit anyway?'): return
        self.destroy()


if __name__ == '__main__':
    App().mainloop()
