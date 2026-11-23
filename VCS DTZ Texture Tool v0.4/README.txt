VCS GAME.DTZ Texture Tool  -  version 0.4
=========================
(See CHANGELOG.txt for what changed in each version. When asking for changes in a new chat,
attach this whole zip and mention the version number.)

START
  Double-click Start.bat.
  First run installs the Pillow image library automatically (needs Python + internet once).
  If Python is missing: install from python.org and tick "Add python.exe to PATH".

BASIC USE
  1. Open GAME.DTZ / .XTX...   (use a COPY of your original; keep the original safe)
     .XTX files (loading screens in SPLASH, EMPHUD.XTX, ...) work exactly like GAME.DTZ.
  2. Pick a texture on the left (search box filters by name).
  3. Export selected... / Export ALL to folder...  -> edit the images in your editor.
  4. Import image... (one texture) or Import from folder... (files named exactly like the
     textures, e.g. bigtext.png, radardisc.bmp; textures without a matching file are untouched).
  5. Save file...              (keep the original file name, e.g. LOADSC0.XTX; an existing file you
                                overwrite is kept once as NAME.bak)
  Modified textures are marked with * in the list. "Revert selected" undoes one texture.

VIEWING ALPHA
  View: Colour + alpha (checkerboard shows transparency) / Colour only / Alpha only.
  "Show original" compares a modified texture with its state before your edits.

EXPORT
  Formats: PNG, BMP, TGA, TIFF, WEBP, JPG (JPG has no transparency).
  "also save alpha map" writes NAME_alpha.png (grey-scale: white = opaque, black = transparent).
  JPG always writes the alpha map when the texture has transparency.

IMPORT
  Accepts PNG, BMP, JPG, TGA, TIFF, WEBP, GIF, DDS.
  If NAME_alpha.png (or .bmp/.tga/.tif) sits next to NAME.jpg/.bmp and that image has no
  transparency of its own, it is used as the alpha channel automatically.

  Single import opens a conversion window:
    - Target size: dropdowns for width/height (powers of two, 8..2048). It starts at the nearest
      power of two to your image. Buttons: Nearest to source / Original size / 2x / 4x.
    - If the shape differs: Stretch, Fit inside (transparent padding), or Fill (crop).
    - Resize quality: Smooth, Bicubic, Bilinear or Sharp (Nearest, best for pixel art).
    - Dither: optional colour dithering (only for images without transparency).
    - Preview: "Converted" shows exactly what the game will get after reduction to the texture's
      palette (16 or 256 colours); also Resized full-colour and Alpha only.
  Folder import: images that are not power-of-two ask once: convert all automatically (stretched
  to the nearest power of two), skip them, or cancel.

RULES / LIMITS
  - Same size as the original: replaced in place (safest).
  - Different size: stored at the end of the file and the texture entry is repointed.
    Confirmed working in the recomp by the user (v0.3.2); test each new texture anyway. Keep the glyph grid identical for fonts.
  - Colours are reduced per texture: 16 colours (4-bit) or 256 (8-bit). Fonts and flat HUD icons
    survive this well; gradients and photos will band. Dither helps on opaque images.
  - GAME.DTZ: saving gives a slightly larger file than the original (different compressor).
  - .XTX is not compressed: an untouched XTX saves back byte-for-byte identical.
  - XTX loading screens are stored as 512x512 squares; check in game whether the original art is
    stretched on screen before deciding what aspect ratio to author at.
  - Keep a backup of every original file.

TEXTURE NOTES
  - gametext holds the PlayStation button glyphs; bigtext does not.
  - Test in small steps: change ONE texture, load the game, then continue.
