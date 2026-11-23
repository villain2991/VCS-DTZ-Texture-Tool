# 🎮 VCS DTZ Texture Tool (PS2)

**A texture editing tool for Grand Theft Auto: Vice City Stories (PlayStation 2).**

Export, edit, and replace textures stored in the game's `.DTZ` and `.XTX` files.

---

## 🖼️ About

VCS DTZ Texture Tool is a fan-made utility designed to make texture editing in the PS2 version of **Grand Theft Auto: Vice City Stories** easier and more accessible.

The tool allows you to browse game textures, export them for external editing, and import your modified images back into the original game files.

The project was created with assistance from **Claude** and inspired by [gothamor's GTA VCS Recomp project](https://github.com/gothamor/gta-vcs-recomp/commits?author=gothamor)

## ✨ Features

- 📂 **DTZ & XTX Support** – Open and edit `GAME.DTZ`, loading screens, HUD textures, and other supported texture files.
- 📤 **Texture Export** – Export individual textures or entire collections.
- 📥 **Texture Replacement** – Import edited images and replace existing game textures.
- 🔄 **Batch Processing** – Export and import textures across entire folders of `.DTZ` and `.XTX` files.
- 🎨 **Multiple Image Formats** – PNG, BMP, TGA, TIFF, WEBP, JPG, and more.
- 🌓 **Alpha Channel Support** – View, export, and preserve texture transparency, including separate alpha maps.
- 🔍 **Texture Preview** – Compare original and modified textures, with colour and alpha viewing modes.
- 📐 **Image Conversion** – Resize, crop, stretch, fit, and convert images to supported texture dimensions.
- 💾 **Automatic Backups** – Existing files are backed up as `.bak` when overwritten.

## 🛠️ Getting Started

1. Download or clone this repository.
2. Run `Start.bat`.
3. Open a `.DTZ` or `.XTX` file.
4. Select and export the textures you want to modify.
5. Edit the exported images using your preferred image editor.
6. Import your modified textures and save the file.

**Requirements:**
- Windows
- Python (added to PATH)
- Internet connection on first launch (to install the required Pillow library automatically).

## ⚠️ Important Notes

- Always work with copies of your original game files.
- Textures are limited to their original colour palettes (4-bit / 16 colours or 8-bit / 256 colours).
- Textures with different dimensions are appended to the file and their texture entries are updated.
- Modified files should always be tested in-game.
- Keep font glyph layouts identical when editing font textures.

## 📌 Project Information

| | |
|---|---|
| **Game** | Grand Theft Auto: Vice City Stories |
| **Platform** | PlayStation 2 |
| **Supported formats** | `.DTZ`, `.XTX` |
| **Current version** | 0.4.1 |
| **Development assistance** | Claude AI |
| **Inspired by** | [GTA VCS Recomp](https://github.com/gothamor/gta-vcs-recomp) |

## 🚀 Upcoming

### Version 0.5 – VCS ReTex Tool

The next major update will introduce a new name and expanded capabilities.

**Planned features:**
- Expanded texture editing capabilities.
- Support for additional game files and texture formats.
- A foundation for broader GTA Stories modding support.

### Future Plans

The long-term goal is to expand the tool beyond the PS2 version of Vice City Stories.

Planned future support includes:

- **GTA: Vice City Stories (PSP)** – Texture file support.
- **GTA: Liberty City Stories (PS2)** – Texture file support.
- **GTA: Liberty City Stories (PSP)** – Texture file support.

The ultimate goal is to provide a unified texture editing tool for both GTA Stories titles across PlayStation 2 and PSP.

*More details and features will be announced as development progresses.*


## 💜 Credits & Acknowledgements

Special thanks to **[gothamor](https://github.com/gothamor)** for the GTA VCS Recomp project, which inspired this tool.

Created for the GTA modding and preservation community.

**Have fun modding Vice City Stories!** 🌴
