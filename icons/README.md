# App icon assets

Source files for the `usage_monitor_for_claude.ico` shipped at the project
root.

## Files

| File | What it is |
|---|---|
| `usage_monitor_for_claude.svg` | Vector source of truth (240 x 240 viewBox, rendered at 1024 px). |
| `usage_monitor_for_claude-1024.png` | High-resolution raster preview rendered from the SVG. Useful when reviewing the design without an SVG-capable viewer. |
| `../usage_monitor_for_claude.ico` | Multi-size Windows icon (16, 24, 32, 48, 64, 128, 256 px) used by PyInstaller for the EXE icon and by Inno Setup for the installer / Add-Remove Programs entry. Built from the SVG with each frame rendered natively at its target pixel size (no downsampling blur on the small frames). |

## Design

Rounded-square diagonal gradient (indigo to cyan) with a central white
"coin" disc and two concentric 270-degree open-bottom progress arcs.

The outer arc symbolises a longer-term quota (the weekly window in this
app's case); the inner arc symbolises the current 5-hour session. Arc
fill ratios in the static art are illustrative only - the live tray icon
is drawn programmatically by `usage_monitor_for_claude/tray_icon.py` and
reflects actual usage in real time.

## Regenerating the .ico from the SVG

Any standard SVG-to-ICO tool works. A reasonable Pillow + cairosvg recipe:

```python
import io
from pathlib import Path

import cairosvg
from PIL import Image

SIZES = (16, 24, 32, 48, 64, 128, 256)
svg = Path('usage_monitor_for_claude.svg').read_text(encoding='utf-8')

def render(size: int) -> Image.Image:
    buf = io.BytesIO()
    cairosvg.svg2png(bytestring=svg.encode('utf-8'),
                     output_width=size, output_height=size,
                     write_to=buf)
    buf.seek(0)
    return Image.open(buf).convert('RGBA')

frames = [render(s) for s in SIZES]
frames[-1].save('../usage_monitor_for_claude.ico',
                format='ICO',
                sizes=[(s, s) for s in SIZES],
                append_images=frames[:-1])
```

Rendering each frame at its native size (instead of downsampling the
1024 master) keeps small icons crisp in Explorer thumbnails and the tray.

## Provenance

The icon was designed in collaboration with Claude (Anthropic). The
design intent (a coin with progress arcs on a gradient ground) was
iterated through several palettes before landing on the indigo-to-cyan
"ocean" variant shipped here.
