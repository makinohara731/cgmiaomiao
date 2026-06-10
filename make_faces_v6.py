"""Paint 2 NEW face-atlas variants on top of the head diffuse, reusing the
make_faces_v5 eye-detection + cream-sampling technique (heart-eyes already exist
as face_love, so the genuinely-new galgame faces are blush + think):

  face_blush.webp  — shy pink cheeks (kept neutral eyes); the romance/羞 staple
  face_think.webp  — eyes glancing up-and-away (pondering / 思考)

Eyes are found by flood-filling the dark region near each known guess point.
Output → ar/public/textures/ (the Vite runtime texture dir), 1024² webp, same
encoding as v5 so the head-material swap lines up with the head UVs.
"""
import math
from PIL import Image, ImageDraw, ImageFilter

SRC = r"E:\05_claude\CGmiaomiao\_archive\head_diffuse.png"
OUTDIR = r"E:\05_claude\CGmiaomiao\ar\public\textures"

A = Image.open(SRC).convert("RGB")
W, H = A.size
px = A.load()
bright = lambda c: (c[0] + c[1] + c[2]) / 3

GUESSES = {"R": (1929, 636), "L": (1071, 1385)}
WIN = 165

# ---- detect each eye's bbox via dark-pixel flood fill (same as v5) ----
eyes = {}
for tag, (gx, gy) in GUESSES.items():
    x0, y0 = max(0, gx - WIN), max(0, gy - WIN)
    x1, y1 = min(W, gx + WIN), min(H, gy + WIN)
    dark = set()
    for y in range(y0, y1):
        for x in range(x0, x1):
            if bright(px[x, y]) < 100:
                dark.add((x, y))
    seen, best = set(), []
    for p in dark:
        if p in seen:
            continue
        comp, stack = [], [p]
        seen.add(p)
        while stack:
            cx, cy = stack.pop()
            comp.append((cx, cy))
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    q = (cx + dx, cy + dy)
                    if q in dark and q not in seen:
                        seen.add(q); stack.append(q)
        if len(comp) > len(best):
            best = comp
    xs = [c[0] for c in best]; ys = [c[1] for c in best]
    eyes[tag] = (min(xs), min(ys), max(xs), max(ys))
    print(f"  {tag}: bbox={eyes[tag]} area={len(best)}")


def sample_cream(bx0, by0, bx1, by1):
    cx, cy = (bx0 + bx1) // 2, (by0 + by1) // 2
    rr = max(bx1 - bx0, by1 - by0)
    acc, n = [0, 0, 0], 0
    for ang in range(0, 360, 15):
        x = int(cx + math.cos(math.radians(ang)) * rr * 0.95)
        y = int(cy + math.sin(math.radians(ang)) * rr * 0.95)
        if 0 <= x < W and 0 <= y < H:
            c = px[x, y]
            if bright(c) > 150:
                acc[0] += c[0]; acc[1] += c[1]; acc[2] += c[2]; n += 1
    return (acc[0] // n, acc[1] // n, acc[2] // n) if n else (224, 238, 156)


def eye_geom(bb):
    bx0, by0, bx1, by1 = bb
    cx, cy = (bx0 + bx1) / 2, (by0 + by1) / 2
    rx, ry = (bx1 - bx0) / 2, (by1 - by0) / 2
    return cx, cy, rx, ry, sample_cream(*bb)


def erase(d, cx, cy, rx, ry, cream, grow=0.5):
    pad = max(8, int(max(rx, ry) * (0.2 + grow)))
    d.ellipse([cx - rx - pad, cy - ry - pad, cx + rx + pad, cy + ry + pad], fill=cream)


# Blush sits just BELOW each eye (atlas +y == face-down for the eye region, as
# confirmed by the think eye-up render). Directly-below lands on the cheek for
# either eye regardless of which way the nose unwraps. Eye-radius units.
BLUSH_OFFSET = {"R": (0.0, 1.25), "L": (0.0, 1.25)}


def make_blush():
    base = A.copy().convert("RGBA")
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    PINK = (255, 110, 140, 205)
    for tag, bb in eyes.items():
        cx, cy, rx, ry, _ = eye_geom(bb)
        r = max(rx, ry)
        ox, oy = BLUSH_OFFSET.get(tag, (0, 1.25))
        bx, by = cx + ox * r, cy + oy * r
        bw, bh = r * 1.9, r * 1.25
        od.ellipse([bx - bw, by - bh, bx + bw, by + bh], fill=PINK)
    overlay = overlay.filter(ImageFilter.GaussianBlur(40))
    out = Image.alpha_composite(base, overlay).convert("RGB")
    out.resize((1024, 1024)).save(OUTDIR + r"\face_blush.webp", quality=85, method=6)
    print("wrote face_blush.webp")


def make_think():
    out = A.copy(); d = ImageDraw.Draw(out)
    for tag, bb in eyes.items():
        cx, cy, rx, ry, cream = eye_geom(bb)
        erase(d, cx, cy, rx, ry, cream, grow=0.6)
        r = max(rx, ry)
        # pupil glances UP-and-away: smaller, lifted high in the socket, with the
        # cream lower lid showing beneath → the universal "pondering" read.
        pr = r * 0.82
        side = -0.28 if tag == "R" else 0.28      # look slightly off to one side
        pcx, pcy = cx + side * r, cy - r * 0.5
        d.ellipse([pcx - pr, pcy - pr, pcx + pr, pcy + pr], fill=(28, 30, 24))
        hl = pr * 0.4
        d.ellipse([pcx - pr * 0.42, pcy - pr * 0.42, pcx - pr * 0.42 + hl, pcy - pr * 0.42 + hl],
                  fill=(255, 255, 255))
    out.resize((1024, 1024)).save(OUTDIR + r"\face_think.webp", quality=85, method=6)
    print("wrote face_think.webp")


make_blush()
make_think()
print("done — 2 new face atlases written")
