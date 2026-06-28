"""Generate frontend/public/maestro.ico from the same design as maestro-logo.svg.

The desktop-shortcut icon needs a real .ico; this redraws the SVG's geometry
(steering wheel + infotainment head unit + knob) with Pillow so every surface —
app, favicon, docs and the desktop shortcut — shows the same mark.
"""

from pathlib import Path

from PIL import Image, ImageDraw

S = 256
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "frontend" / "public" / "maestro.ico"

WHEEL = (34, 170, 232, 255)   # cyan→blue gradient, mid
SCREEN = (109, 81, 238, 255)  # purple→indigo gradient, mid
KNOB = (245, 158, 11, 255)
WHITE = (255, 255, 255, 235)
LINK = (90, 150, 230, 255)


def sc(v: float) -> float:
    return v * (S / 64.0)


def main() -> None:
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # contour link line (wheel rim → head unit)
    d.line([sc(27), sc(22), sc(42), sc(18), sc(57), sc(24)], fill=LINK, width=int(sc(2.4)), joint="curve")

    # steering wheel
    cx, cy, r = sc(20), sc(36), sc(13)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=WHEEL, width=int(sc(3.4)))
    hub = sc(3.4)
    d.ellipse([cx - hub, cy - hub, cx + hub, cy + hub], fill=WHEEL)
    lw = int(sc(3))
    d.line([sc(9), sc(36), sc(16.8), sc(36)], fill=WHEEL, width=lw)
    d.line([sc(23.2), sc(36), sc(31), sc(36)], fill=WHEEL, width=lw)
    d.line([sc(20), sc(39.4), sc(20), sc(47)], fill=WHEEL, width=lw)

    # infotainment head unit + button grid
    d.rounded_rectangle([sc(35), sc(27), sc(56), sc(43)], radius=sc(3.2), fill=SCREEN)
    for ry in (30.5, 36.0):
        for rx in (38.0, 43.0, 48.0):
            d.rounded_rectangle([sc(rx), sc(ry), sc(rx + 3.2), sc(ry + 3.2)], radius=sc(1), fill=WHITE)

    # control knob
    d.ellipse([sc(56.1), sc(36.6), sc(62.9), sc(43.4)], fill=KNOB)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUT, sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print("wrote", OUT)


if __name__ == "__main__":
    main()
