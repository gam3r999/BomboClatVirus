# 💣 BomboClatVirus

> **100% harmless prank. No files are modified. No system settings are changed. Everything is reversible.**

A fake "virus" prank script for Windows that plays a video, goes absolutely insane with real GDI screen effects, blasts a bytebeat formula through your speakers, then plays the video again and fades out cleanly.

---

## 📁 File Structure

Place all of these in the same folder:

```
bomboclat_virus.py
bomboclat.mp4        ← your video (plays at start AND end)
bomboclat.mp3        ← audio extracted from your video
byebyte.wav          ← optional: custom bytebeat sound (auto-generated if missing)
```

---

## ⚙️ Requirements

```bash
pip install pygame pillow opencv-python numpy
```

> **Windows only** — GDI effects use `ctypes` / Win32 and will not work on Mac or Linux.

---

## ▶️ Usage

```bash
py bomboclat_virus.py
```

Press **ESC** at any time to exit immediately.

---

## 🎬 Timeline

| Time | What happens |
|------|-------------|
| `0s` | `bomboclat.mp4` fades in to a centered 500×500 window |
| `~2s` | `bomboclat.mp3` starts playing in sync with the video |
| end of video | GDI effects and bytebeat kick in |
| `~18s` | GDI effects stop |
| next | `bomboclat.mp4` plays again — fades **in**, plays, fades **out** to black |
| end | Window closes |

---

## 💀 GDI Effects

These are drawn directly onto the **real Windows desktop DC** via `ctypes`. They are completely temporary — they vanish the instant anything redraws the screen and leave zero trace.

| # | Effect |
|---|--------|
| 1 | Screen color inversion |
| 2 | Horizontal sine wobble |
| 3 | Zoom tunnel |
| 4 | 90° rotation chunks |
| 5 | Concentric ring swirl |
| 6 | Random static / noise blocks |
| 7 | Vertical flip strips |
| 8 | Kaleidoscope mirror halves |

Inside the 500×500 window, matching PIL effects are applied to the video frame in real time, along with colorful scanline rain.

---

## 🎵 Bytebeat Formula

```
10*(t>>7|t|t>>6)+4*(t&t>>13|t>>6)
```

Auto-generated and looped during the GDI effect phase. Drop a `byebyte.wav` in the folder to use your own sound instead.

---

## ⚠️ Disclaimer

This is a **joke/prank tool**. It does not:
- Modify any files
- Change any system settings
- Damage anything
- Actually do anything malicious

Only use this on people who will find it funny. **Do not use this maliciously.**

---

## 📄 License

This project is licensed under the **Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International (CC BY-NC-SA 4.0)** license.

You are free to:
- **Share** — copy and redistribute the material in any medium or format
- **Adapt** — remix, transform, and build upon the material

Under the following terms:
- **Attribution** — You must give appropriate credit and indicate if changes were made
- **NonCommercial** — You may not use the material for commercial purposes
- **ShareAlike** — If you remix or build upon this material, you must distribute your contributions under the same license

[![License: CC BY-NC-SA 4.0](https://img.shields.io/badge/License-CC%20BY--NC--SA%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by-nc-sa/4.0/)

Full license text: https://creativecommons.org/licenses/by-nc-sa/4.0/legalcode
