"""
╔══════════════════════════════════════════════════════════╗
║                  bomboclat_virus.py                      ║
║   Prank script — zero damage, 100% reversible            ║
╚══════════════════════════════════════════════════════════╝

FOLDER STRUCTURE (all in the same folder):
    bomboclat_virus.py
    bomboclat_intro.png   ← your intro image
    bomboclat.mp4         ← your video shown at the END (fades in + out)
    ltg-bomboclat.mp3     ← plays when intro image fades in  (optional)
    byebyte.wav           ← .wav noise file  (optional, auto-generated if missing)

REQUIREMENTS:
    pip install pygame pillow opencv-python numpy

TIMELINE:
    0s   — bomboclat_intro.png fades into centre of a 500x500 window
    ~2s  — ltg-bomboclat.mp3 starts playing
    ~4s  — GDI effects begin cycling on the real screen + bytebeat joins
    ~22s — GDI effects stop; bomboclat.mp4 plays in the 500x500 window
    end  — video fades out to black, window closes

GDI EFFECTS (real Windows GDI / ctypes):
    1. Screen inversion / color flip
    2. Horizontal sine wobble
    3. Zoom tunnel
    4. 90 degree rotation chunks
    5. Screen swirl (concentric ring warp)
    6. Random static / noise blocks
    7. Vertical flip strips
    8. Kaleidoscope mirror halves

NOTE: GDI effects draw directly on the Windows desktop DC.
      They are 100% temporary and vanish the moment the screen redraws.
      No files are modified. No system settings are changed.
"""

import os
import sys
import time
import ctypes
import struct
import random
import threading
import math
import wave
import io
import tkinter as tk

try:
    from PIL import Image, ImageTk, ImageOps, ImageDraw
    PIL_OK = True
except ImportError:
    PIL_OK = False
    print("[!] pip install pillow")

try:
    import pygame
    PYGAME_OK = True
except ImportError:
    PYGAME_OK = False
    print("[!] pip install pygame")

try:
    import numpy as np
    NP_OK = True
except ImportError:
    NP_OK = False
    print("[!] pip install numpy")

try:
    import cv2
    CV2_OK = True
except ImportError:
    CV2_OK = False
    print("[!] pip install opencv-python  (needed for video playback)")

# ─────────────────────────────────────────────────────────────────
#  PATHS
# ─────────────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

def find_file(*names):
    for name in names:
        p = os.path.join(SCRIPT_DIR, name)
        if os.path.exists(p):
            return p
    return None

VIDEO_FILE   = find_file("bomboclat.mp4")
AUDIO_FILE   = find_file("bomboclat.mp3")
BYEBYTE_FILE = find_file("byebyte.wav")

# ─────────────────────────────────────────────────────────────────
#  WINDOW SIZE
# ─────────────────────────────────────────────────────────────────
WIN_W = 500
WIN_H = 500

# How long (seconds) GDI effects run before video plays
GDI_DURATION = 18

# Video fade-out duration in seconds
FADE_OUT_SEC = 2.5

# ─────────────────────────────────────────────────────────────────
#  BYTEBEAT  10*(t>>7|t|t>>6)+4*(t&t>>13|t>>6)
# ─────────────────────────────────────────────────────────────────
SAMPLE_RATE = 8000

def _bytebeat(t):
    t = int(t) & 0xFFFFFFFF
    return (10 * ((t >> 7) | t | (t >> 6)) +
            4  * ((t & (t >> 13)) | (t >> 6))) & 0xFF

def _gen_bytebeat(duration_sec=4.0):
    n    = int(SAMPLE_RATE * duration_sec)
    data = bytes([_bytebeat(t) for t in range(n)])
    buf  = io.BytesIO()
    with wave.open(buf, 'w') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(1)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(data)
    buf.seek(0)
    return buf.read()

# ─────────────────────────────────────────────────────────────────
#  AUDIO  (extract from video via ffmpeg, play with pygame)
# ─────────────────────────────────────────────────────────────────
_byebyte_channel = None
_byebyte_sound   = None

def init_audio():
    if not PYGAME_OK:
        return
    pygame.mixer.pre_init(44100, -16, 2, 512)
    pygame.mixer.init()
    pygame.mixer.set_num_channels(8)

def play_video_audio(offset_sec=0.0):
    """Play bomboclat.mp3 via pygame.mixer.music."""
    if not PYGAME_OK or not AUDIO_FILE:
        if not AUDIO_FILE:
            print("[!] bomboclat.mp3 not found — place it next to the script")
        return
    try:
        pygame.mixer.music.load(AUDIO_FILE)
        pygame.mixer.music.set_volume(1.0)
        pygame.mixer.music.play(0, start=offset_sec)
        print(f"[*] Audio: {os.path.basename(AUDIO_FILE)}")
    except Exception as e:
        print(f"[!] Audio playback error: {e}")

def play_byebyte():
    global _byebyte_sound, _byebyte_channel
    if not PYGAME_OK:
        return
    try:
        if BYEBYTE_FILE:
            snd = pygame.mixer.Sound(BYEBYTE_FILE)
            print(f"[*] Byebyte: {os.path.basename(BYEBYTE_FILE)}")
        else:
            print("[!] byebyte.wav not found — generating from formula  10*(t>>7|t|t>>6)+4*(t&t>>13|t>>6)")
            snd = pygame.mixer.Sound(buffer=_gen_bytebeat(4.0))
        snd.set_volume(0.85)
        ch = pygame.mixer.find_channel(True)
        if ch:
            ch.play(snd, loops=-1)
            _byebyte_channel = ch
            _byebyte_sound   = snd
    except Exception as e:
        print(f"[!] Byebyte error: {e}")

def stop_all_audio():
    if not PYGAME_OK:
        return
    try:
        pygame.mixer.music.stop()
    except Exception:
        pass
    try:
        pygame.mixer.stop()
    except Exception:
        pass

def cleanup_audio_temp():
    try:
        if os.path.exists(AUDIO_TEMP):
            os.remove(AUDIO_TEMP)
    except Exception:
        pass

# ─────────────────────────────────────────────────────────────────
#  WINDOWS GDI EFFECTS  (real screen via ctypes)
# ─────────────────────────────────────────────────────────────────
user32 = ctypes.windll.user32
gdi32  = ctypes.windll.gdi32

SRCCOPY   = 0x00CC0020
SRCINVERT = 0x00550009
HALFTONE  = 4

def _sw_sh():
    return user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)

def _get_dc():
    return user32.GetDC(None)

def _rel_dc(hdc):
    user32.ReleaseDC(None, hdc)

def _make_mem(hdc, sw, sh):
    mem = gdi32.CreateCompatibleDC(hdc)
    bmp = gdi32.CreateCompatibleBitmap(hdc, sw, sh)
    gdi32.SelectObject(mem, bmp)
    return mem, bmp

def _free_mem(mem, bmp):
    gdi32.DeleteObject(bmp)
    gdi32.DeleteDC(mem)

# 1. Color inversion
def gdi_invert(sw, sh):
    hdc = _get_dc()
    gdi32.BitBlt(hdc, 0, 0, sw, sh, hdc, 0, 0, SRCINVERT)
    for _ in range(random.randint(3, 9)):
        x = random.randint(0, sw - 120)
        y = random.randint(0, sh - 120)
        w = random.randint(60, 320)
        h = random.randint(60, 220)
        gdi32.BitBlt(hdc, x, y, w, h, hdc, x, y, SRCINVERT)
    _rel_dc(hdc)

# 2. Horizontal sine wobble
_wobble_phase = 0.0
def gdi_wobble(sw, sh):
    global _wobble_phase
    hdc = _get_dc()
    mem, bmp = _make_mem(hdc, sw, sh)
    gdi32.BitBlt(mem, 0, 0, sw, sh, hdc, 0, 0, SRCCOPY)
    strip_h = 5
    for y in range(0, sh, strip_h):
        offset = int(math.sin(_wobble_phase + y * 0.025) * 28)
        gdi32.BitBlt(hdc, offset, y, sw, strip_h, mem, 0, y, SRCCOPY)
    _wobble_phase += 0.35
    _free_mem(mem, bmp)
    _rel_dc(hdc)

# 3. Zoom tunnel
def gdi_tunnel(sw, sh):
    hdc = _get_dc()
    mem, bmp = _make_mem(hdc, sw, sh)
    gdi32.BitBlt(mem, 0, 0, sw, sh, hdc, 0, 0, SRCCOPY)
    layers = random.randint(4, 7)
    for i in range(layers):
        scale = 1.0 - (i + 1) * (0.85 / layers)
        nw = int(sw * scale)
        nh = int(sh * scale)
        nx = (sw - nw) // 2
        ny = (sh - nh) // 2
        gdi32.SetStretchBltMode(hdc, HALFTONE)
        gdi32.StretchBlt(hdc, nx, ny, nw, nh, mem, 0, 0, sw, sh, SRCCOPY)
    _free_mem(mem, bmp)
    _rel_dc(hdc)

# 4. Rotation chunks
def gdi_rotation_chunks(sw, sh):
    hdc = _get_dc()
    mem, bmp = _make_mem(hdc, sw, sh)
    gdi32.BitBlt(mem, 0, 0, sw, sh, hdc, 0, 0, SRCCOPY)
    tw = sw // random.randint(3, 6)
    th = sh // random.randint(3, 6)
    for ty in range(0, sh - th, th):
        for tx in range(0, sw - tw, tw):
            rot = random.choice([0, 1, 2, 3])
            if rot == 0:
                continue
            elif rot == 1:
                sx = tx + tw if tx + tw < sw else tx
                sy = ty + th if ty + th < sh else ty
                gdi32.StretchBlt(hdc, tx, ty, tw, th, mem, sx, sy, -tw, -th, SRCCOPY)
            elif rot == 2:
                gdi32.StretchBlt(hdc, tx, ty, tw, th, mem, tx + tw, ty, -tw, th, SRCCOPY)
            elif rot == 3:
                gdi32.StretchBlt(hdc, tx, ty, tw, th, mem, tx, ty + th, tw, -th, SRCCOPY)
    _free_mem(mem, bmp)
    _rel_dc(hdc)

# 5. Screen swirl
_swirl_angle = 0.0
def gdi_swirl(sw, sh):
    global _swirl_angle
    hdc = _get_dc()
    mem, bmp = _make_mem(hdc, sw, sh)
    gdi32.BitBlt(mem, 0, 0, sw, sh, hdc, 0, 0, SRCCOPY)
    cx, cy = sw // 2, sh // 2
    ring_w = max(30, sw // 14)
    max_r  = min(cx, cy)
    for r in range(0, max_r, ring_w):
        ao = math.sin(_swirl_angle + r * 0.04) * 40
        ox = int(math.cos(math.radians(ao)) * r * 0.12)
        oy = int(math.sin(math.radians(ao)) * r * 0.12)
        x1 = max(0, cx - r - ring_w)
        y1 = max(0, cy - r - ring_w)
        x2 = min(sw, cx + r + ring_w)
        y2 = min(sh, cy + r + ring_w)
        rw, rh = x2 - x1, y2 - y1
        if rw > 0 and rh > 0:
            sx = max(0, min(sw - rw, x1 + ox))
            sy = max(0, min(sh - rh, y1 + oy))
            gdi32.BitBlt(hdc, x1, y1, rw, rh, mem, sx, sy, SRCCOPY)
    _swirl_angle += 0.2
    _free_mem(mem, bmp)
    _rel_dc(hdc)

# 6. Static noise blocks
def gdi_static(sw, sh):
    hdc = _get_dc()
    for _ in range(random.randint(30, 80)):
        x  = random.randint(0, sw - 60)
        y  = random.randint(0, sh - 40)
        w  = random.randint(5, 60)
        h  = random.randint(5, 40)
        gr = random.randint(0, 255)
        color = gr | (gr << 8) | (gr << 16)
        brush = gdi32.CreateSolidBrush(color)
        rect_bytes = struct.pack("iiii", x, y, x + w, y + h)
        ctypes.windll.user32.FillRect(
            hdc,
            ctypes.create_string_buffer(rect_bytes),
            brush
        )
        gdi32.DeleteObject(brush)
    _rel_dc(hdc)

# 7. Vertical flip strips
def gdi_vflip_strips(sw, sh):
    hdc = _get_dc()
    mem, bmp = _make_mem(hdc, sw, sh)
    gdi32.BitBlt(mem, 0, 0, sw, sh, hdc, 0, 0, SRCCOPY)
    strip_w = sw // random.randint(6, 14)
    for x in range(0, sw - strip_w, strip_w * 2):
        gdi32.StretchBlt(hdc, x, 0, strip_w, sh, mem, x, sh, strip_w, -sh, SRCCOPY)
    _free_mem(mem, bmp)
    _rel_dc(hdc)

# 8. Kaleidoscope mirror
def gdi_kaleidoscope(sw, sh):
    hdc = _get_dc()
    mem, bmp = _make_mem(hdc, sw, sh)
    gdi32.BitBlt(mem, 0, 0, sw, sh, hdc, 0, 0, SRCCOPY)
    mode = random.randint(0, 3)
    hw, hh = sw // 2, sh // 2
    if mode == 0:
        gdi32.StretchBlt(hdc, sw, 0, -sw, sh, mem, 0, 0, sw, sh, SRCCOPY)
    elif mode == 1:
        gdi32.StretchBlt(hdc, 0, sh, sw, -sh, mem, 0, 0, sw, sh, SRCCOPY)
    elif mode == 2:
        gdi32.StretchBlt(hdc, hw, 0, hw, sh, mem, hw, 0, -hw, sh, SRCCOPY)
    elif mode == 3:
        gdi32.StretchBlt(hdc, 0, hh, sw, hh, mem, 0, hh, sw, -hh, SRCCOPY)
    _free_mem(mem, bmp)
    _rel_dc(hdc)

GDI_EFFECTS = [
    gdi_invert,
    gdi_wobble,
    gdi_tunnel,
    gdi_rotation_chunks,
    gdi_swirl,
    gdi_static,
    gdi_vflip_strips,
    gdi_kaleidoscope,
    gdi_tunnel,   # extra weight — very impactful
    gdi_swirl,
    gdi_wobble,
]

_gdi_active = False

def start_gdi_effects():
    global _gdi_active
    _gdi_active = True
    sw, sh = _sw_sh()

    def _loop():
        idx   = 0
        burst = 0
        random.shuffle(GDI_EFFECTS)
        while _gdi_active:
            try:
                GDI_EFFECTS[idx % len(GDI_EFFECTS)](sw, sh)
            except Exception:
                pass
            burst += 1
            if burst >= random.randint(6, 18):
                burst = 0
                idx  += 1
            time.sleep(0.035)

    threading.Thread(target=_loop, daemon=True).start()
    print("[*] GDI effects started.")

def stop_gdi_effects():
    global _gdi_active
    _gdi_active = False
    time.sleep(0.15)
    print("[*] GDI effects stopped.")

# ─────────────────────────────────────────────────────────────────
#  PIL IMAGE EFFECTS  (applied inside the tkinter window only)
# ─────────────────────────────────────────────────────────────────

def pil_invert(img):
    r, g, b, a = img.split()
    inv = ImageOps.invert(Image.merge("RGB", (r, g, b)))
    ir, ig, ib = inv.split()
    return Image.merge("RGBA", (ir, ig, ib, a))

def pil_sine_wobble(img):
    if not NP_OK:
        return img
    arr = np.array(img)
    h, w = arr.shape[:2]
    out   = np.zeros_like(arr)
    amp   = random.randint(8, 22)
    freq  = random.uniform(0.03, 0.09)
    phase = random.uniform(0, math.pi * 2)
    for y in range(h):
        shift = int(amp * math.sin(freq * y + phase))
        out[y] = np.roll(arr[y], shift, axis=0)
    return Image.fromarray(out, "RGBA")

def pil_zoom_tunnel(img):
    w, h  = img.size
    scale = random.uniform(0.4, 0.82)
    small = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    base  = img.copy()
    ox = (w - small.width)  // 2
    oy = (h - small.height) // 2
    base.paste(small, (ox, oy), small)
    return base

def pil_rotation_chunks(img):
    if not NP_OK:
        return img
    arr = np.array(img)
    h, w = arr.shape[:2]
    nx, ny = random.randint(3, 7), random.randint(3, 7)
    out = arr.copy()
    for ry in range(ny):
        for rx in range(nx):
            y0 = ry * (h // ny)
            y1 = (ry+1)*(h//ny) if ry < ny-1 else h
            x0 = rx * (w // nx)
            x1 = (rx+1)*(w//nx) if rx < nx-1 else w
            k  = random.choice([0, 1, 2, 3])
            chunk = np.rot90(arr[y0:y1, x0:x1], k)
            ch, cw = y1-y0, x1-x0
            if chunk.shape[0] >= ch and chunk.shape[1] >= cw:
                out[y0:y1, x0:x1] = chunk[:ch, :cw]
    return Image.fromarray(out, "RGBA")

def pil_swirl(img):
    if not NP_OK:
        return img
    arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    cx, cy = w / 2.0, h / 2.0
    strength = random.uniform(2.0, 5.0)
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    dx, dy = xs - cx, ys - cy
    r     = np.sqrt(dx*dx + dy*dy)
    max_r = math.sqrt(cx*cx + cy*cy)
    angle = np.arctan2(dy, dx) + strength * (1.0 - r / (max_r + 1e-5))
    sx = np.clip((cx + r * np.cos(angle)).astype(np.int32), 0, w-1)
    sy = np.clip((cy + r * np.sin(angle)).astype(np.int32), 0, h-1)
    return Image.fromarray(arr[sy, sx].astype(np.uint8), "RGBA")

def pil_static(img):
    out  = img.copy()
    draw = ImageDraw.Draw(out)
    w, h = out.size
    for _ in range(random.randint(60, 160)):
        x = random.randint(0, w-1)
        y = random.randint(0, h-1)
        draw.rectangle(
            [x, y, x+random.randint(3,55), y+random.randint(2,20)],
            fill=(random.randint(0,255), random.randint(0,255),
                  random.randint(0,255), random.randint(120,230))
        )
    return out

def pil_vflip_strips(img):
    if not NP_OK:
        return img
    arr = np.array(img)
    h, w = arr.shape[:2]
    sw_  = random.randint(15, 80)
    out  = arr.copy()
    flip = False
    x    = 0
    while x < w:
        x2 = min(x + sw_, w)
        if flip:
            out[:, x:x2] = arr[::-1, x:x2]
        flip = not flip
        x = x2
    return Image.fromarray(out, "RGBA")

def pil_kaleidoscope(img):
    if not NP_OK:
        return img
    arr = np.array(img)
    h, w = arr.shape[:2]
    out  = arr.copy()
    mode = random.randint(0, 3)
    if mode == 0:
        out[:, w//2:] = arr[:, :w//2][:, ::-1]
    elif mode == 1:
        out[:, :w//2] = arr[:, w//2:][:, ::-1]
    elif mode == 2:
        out[h//2:, :] = arr[:h//2, :][::-1, :]
    else:
        q = arr[:h//2, :w//2]
        out[:h//2, w//2:] = q[:, ::-1]
        out[h//2:, :w//2] = q[::-1, :]
        out[h//2:, w//2:] = q[::-1, ::-1]
    return Image.fromarray(out, "RGBA")

PIL_EFFECTS = [
    ("INVERT",        pil_invert),
    ("SINE WOBBLE",   pil_sine_wobble),
    ("ZOOM TUNNEL",   pil_zoom_tunnel),
    ("CHUNK ROTATE",  pil_rotation_chunks),
    ("SCREEN SWIRL",  pil_swirl),
    ("STATIC NOISE",  pil_static),
    ("FLIP STRIPS",   pil_vflip_strips),
    ("KALEIDOSCOPE",  pil_kaleidoscope),
]

# ─────────────────────────────────────────────────────────────────
#  VIDEO READER  (OpenCV -> PIL frames, scaled to 500x500)
# ─────────────────────────────────────────────────────────────────
class VideoReader:
    def __init__(self, path):
        self.cap   = cv2.VideoCapture(path)
        self.fps   = self.cap.get(cv2.CAP_PROP_FPS) or 24.0
        self.total = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        w          = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h          = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        print(f"[+] Video: {os.path.basename(path)}  {w}x{h}  {self.fps:.1f}fps  {self.total} frames")

    def read_frame(self):
        """Return next frame as PIL RGBA image scaled to WIN_WxWIN_H, or None if done."""
        ret, frame = self.cap.read()
        if not ret:
            return None
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img   = Image.fromarray(frame).convert("RGBA")
        scale = min(WIN_W / img.width, WIN_H / img.height)
        nw    = int(img.width  * scale)
        nh    = int(img.height * scale)
        img   = img.resize((nw, nh), Image.LANCZOS)
        canvas = Image.new("RGBA", (WIN_W, WIN_H), (0, 0, 0, 255))
        ox = (WIN_W - nw) // 2
        oy = (WIN_H - nh) // 2
        canvas.paste(img, (ox, oy))
        return canvas

    def frames_played(self):
        return max(0, int(self.cap.get(cv2.CAP_PROP_POS_FRAMES)))

    def frames_remaining(self):
        return max(0, self.total - self.frames_played())

    def release(self):
        self.cap.release()

# ─────────────────────────────────────────────────────────────────
#  MAIN APP
# ─────────────────────────────────────────────────────────────────
class BomboclatVirus:
    TICK_MS = 42   # ~24 fps for tick loop

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("svchost.exe")
        self.root.resizable(False, False)
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)

        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x  = (sw - WIN_W) // 2
        y  = (sh - WIN_H) // 2
        self.root.geometry(f"{WIN_W}x{WIN_H}+{x}+{y}")
        self.root.configure(bg="black")

        self.canvas = tk.Canvas(
            self.root, bg="black", highlightthickness=0,
            width=WIN_W, height=WIN_H
        )
        self.canvas.pack(fill="both", expand=True)

        # State
        self.phase       = "intro_video"
        self.frame       = 0
        self.running     = True
        self.cur_effect  = PIL_EFFECTS[0]
        self.gdi_start_t = None

        # Shared video render state
        self.vid_frame_tk = None
        self.vid_last_ms  = 0
        self.vid_start_t  = 0.0
        self.FADE_IN_SEC  = 1.5

        # Intro video (plays once at start)
        self.intro_vid     = None
        self.intro_fade    = 0.0
        self.last_intro_frame = None  # holds last frame for glitch phase

        # Outro video (plays again at end)
        self.outro_vid  = None
        self.outro_fade = 0.0

        if not CV2_OK:
            print("[!] opencv-python not installed — video disabled.")
        elif not VIDEO_FILE:
            print("[!] bomboclat.mp4 not found — place it next to the script.")
        else:
            self.intro_vid = VideoReader(VIDEO_FILE)
            self.vid_frame_ms = max(16, int(1000 / self.intro_vid.fps))
            print(f"[*] Intro + outro video: {os.path.basename(VIDEO_FILE)}")

        self.vid_frame_ms = getattr(self, "vid_frame_ms", 42)

        init_audio()

        self.root.bind("<Escape>", lambda e: self._force_quit())
        self.root.after(300, self._tick)

    # ── RENDER HELPER ────────────────────────────────────────────

    def _render_video_frame(self, pil_img, fade=1.0):
        self.canvas.delete("all")
        if fade < 1.0:
            overlay = Image.new("RGBA", pil_img.size, (0, 0, 0, int((1.0 - fade) * 255)))
            pil_img = Image.alpha_composite(pil_img, overlay)
        self.vid_frame_tk = ImageTk.PhotoImage(pil_img)
        self.canvas.create_image(WIN_W // 2, WIN_H // 2,
                                 image=self.vid_frame_tk, anchor="center")

    def _render_pil_with_effect(self, pil_img, effect_fn=None):
        """Apply a PIL glitch effect to a frame and draw it."""
        self.canvas.delete("all")
        if effect_fn:
            try:
                pil_img = effect_fn(pil_img)
            except Exception:
                pass
        self.vid_frame_tk = ImageTk.PhotoImage(pil_img)
        self.canvas.create_image(WIN_W // 2, WIN_H // 2,
                                 image=self.vid_frame_tk, anchor="center")

    # ── MAIN TICK ────────────────────────────────────────────────

    def _tick(self):
        if not self.running:
            return
        self.frame += 1
        {
            "intro_video": self._phase_intro_video,
            "hold":        self._phase_hold,
            "glitch":      self._phase_glitch,
            "outro_video": self._phase_outro_video,
        }[self.phase]()
        self.root.after(self.TICK_MS, self._tick)

    def _transition(self, nxt):
        self.phase = nxt
        self.frame = 0
        print(f"[*] Phase -> {nxt}")

    # ── PHASE 1: bomboclat.mp4 fades in, audio plays in sync ─────

    def _phase_intro_video(self):
        if self.intro_vid is None:
            self._transition("glitch")
            return

        now_ms = int(time.time() * 1000)

        # First frame: kick off audio and video at the same instant
        if self.frame == 1:
            self.vid_start_t  = time.time()
            self.vid_last_ms  = now_ms
            play_video_audio(offset_sec=0.0)
            vid_frame = self.intro_vid.read_frame()
        else:
            # Throttle display to video fps, but keep audio in sync by
            # seeking to the elapsed time position whenever we're late
            elapsed   = time.time() - self.vid_start_t
            target_fn = int(elapsed * self.intro_vid.fps)
            current_fn = self.intro_vid.frames_played()
            # Skip frames if we've fallen behind
            while current_fn < target_fn - 1:
                self.intro_vid.read_frame()
                current_fn = self.intro_vid.frames_played()

            if (now_ms - self.vid_last_ms) < self.vid_frame_ms:
                return
            self.vid_last_ms = now_ms
            vid_frame = self.intro_vid.read_frame()

        if vid_frame is None:
            self._transition("hold")
            return

        self.last_intro_frame = vid_frame.copy()

        frames_played     = self.intro_vid.frames_played()
        frames_for_fadein = max(1, int(self.intro_vid.fps * self.FADE_IN_SEC))
        self.intro_fade   = min(1.0, frames_played / frames_for_fadein)

        self._render_video_frame(vid_frame, fade=self.intro_fade)

    # ── PHASE 2: gentle breathing hold on last intro frame ───────

    def _phase_hold(self):
        if self.last_intro_frame is not None:
            pulse = 0.88 + 0.12 * math.sin(self.frame * 0.32)
            self._render_video_frame(self.last_intro_frame, fade=pulse)
        if self.frame > 38:
            self._transition("glitch")

    # ── PHASE 3: GDI effects on desktop + PIL effects in window ──

    def _phase_glitch(self):
        if self.frame == 1:
            start_gdi_effects()
            play_byebyte()
            self.gdi_start_t = time.time()
            # Open a fresh copy of the video for the outro now
            if CV2_OK and VIDEO_FILE:
                self.outro_vid = VideoReader(VIDEO_FILE)

        if self.frame == 1 or self.frame % 20 == 0:
            self.cur_effect = random.choice(PIL_EFFECTS)

        # Use last intro frame as glitch canvas
        base = self.last_intro_frame
        if base is None:
            base = Image.new("RGBA", (WIN_W, WIN_H), (0, 0, 0, 255))

        _, fn = self.cur_effect
        self._render_pil_with_effect(base.copy(), effect_fn=fn)

        # Colour scanlines inside the window
        for _ in range(random.randint(3, 10)):
            y   = random.randint(0, WIN_H)
            col = random.choice([
                "#ff0000","#00ff00","#0000ff",
                "#ffff00","#ff00ff","#00ffff","#ff8800"
            ])
            self.canvas.create_rectangle(
                0, y, WIN_W, y + random.randint(1, 5),
                fill=col, outline="", stipple="gray50"
            )

        elapsed = time.time() - (self.gdi_start_t or time.time())
        if elapsed >= GDI_DURATION:
            stop_gdi_effects()
            stop_all_audio()
            self._transition("outro_video")

    # ── PHASE 4: bomboclat.mp4 fades in then fades out at end ────

    def _phase_outro_video(self):
        if self.outro_vid is None:
            self.root.after(800, self._force_quit)
            return

        now_ms = int(time.time() * 1000)

        if self.frame == 1:
            self.vid_start_t = time.time()
            self.vid_last_ms = now_ms
            play_video_audio(offset_sec=0.0)
            vid_frame = self.outro_vid.read_frame()
        else:
            elapsed   = time.time() - self.vid_start_t
            target_fn = int(elapsed * self.outro_vid.fps)
            current_fn = self.outro_vid.frames_played()
            while current_fn < target_fn - 1:
                self.outro_vid.read_frame()
                current_fn = self.outro_vid.frames_played()

            if (now_ms - self.vid_last_ms) < self.vid_frame_ms:
                return
            self.vid_last_ms = now_ms
            vid_frame = self.outro_vid.read_frame()

        vid_frame = self.outro_vid.read_frame()

        if vid_frame is None:
            black = Image.new("RGBA", (WIN_W, WIN_H), (0, 0, 0, 255))
            self._render_video_frame(black, fade=1.0)
            self.root.after(400, self._force_quit)
            return

        frames_played     = self.outro_vid.frames_played()
        frames_for_fadein = max(1, int(self.outro_vid.fps * self.FADE_IN_SEC))
        frames_left       = self.outro_vid.frames_remaining()
        frames_for_fadeout = max(1, int(self.outro_vid.fps * FADE_OUT_SEC))

        if frames_played <= frames_for_fadein:
            self.outro_fade = min(1.0, frames_played / frames_for_fadein)
        elif frames_left <= frames_for_fadeout:
            self.outro_fade = max(0.0, frames_left / frames_for_fadeout)
        else:
            self.outro_fade = 1.0

        self._render_video_frame(vid_frame, fade=self.outro_fade)

        if frames_left <= 1 and self.outro_fade <= 0.02:
            self.root.after(300, self._force_quit)

    # ── EXIT ─────────────────────────────────────────────────────

    def _force_quit(self):
        self.running = False
        stop_gdi_effects()
        stop_all_audio()
        for v in (self.intro_vid, self.outro_vid):
            if v:
                v.release()
        try:
            self.root.destroy()
        except Exception:
            pass

    def run(self):
        self.root.mainloop()


# ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 55)
    print("  BOMBOCLAT FAKE VIRUS  -  zero harm, 100% prank")
    print("  Windows only (GDI effects require ctypes/Win32)")
    print("  Press ESC at any time to exit immediately.")
    print("=" * 55)
    BomboclatVirus().run()
    print("\nDone! You got Bomboclat'd. Your computer is perfectly fine :)")