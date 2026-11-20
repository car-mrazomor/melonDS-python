# Screens

The DS has two 256×192 screens. The bottom one is the touch screen. PymelonDS gives you both together and each
one separately:

| Object | Size | Content |
|---|---|---|
| `pm.screen` | 256×384 | top screen above bottom screen |
| `pm.screen.top` | 256×192 | top screen |
| `pm.screen.bottom` | 256×192 | bottom screen |

Each has `.image`, `.raw_buffer`, `.raw_buffer_dims` and `.raw_buffer_format`.

```python
pm.tick()
pm.screen.image.save("both.png")
pm.screen.top.image.save("top.png")
pm.screen.bottom.image.save("bottom.png")
```

If a game swaps which screen shows what (some games put the main view on the bottom), `top` and `bottom`
still mean the physical top and bottom screen.

## PIL images

`.image` is a `PIL.Image.Image` in mode `RGBA`. Alpha is always 255. Convert if you need RGB:

```python
rgb = pm.screen.top.image.convert("RGB")
```

Anything PIL can do works: `resize`, `crop`, `save` (PNG, JPEG, ...), `getpixel`, `tobytes`.

### Live images: copy what you keep

Like PyBoy, the images are **views of one frame buffer**. After every rendered `tick()` the same image object
shows the new frame:

```python
a = pm.screen.image
pm.tick(60)
b = pm.screen.image
# a is b, and both show the newest frame
```

To keep a frame, copy it:

```python
frames = []
for _ in range(10):
    pm.tick(30)
    frames.append(pm.screen.top.image.copy())
```

If PIL turns an image into an independent copy (some in-place operations do that), PymelonDS notices on the next
tick and reconnects `.image` to the live buffer. The object you were holding then stops updating. Just read
`pm.screen.image` again instead of keeping a reference across ticks.

### When the screen updates

- After the last frame of each `tick(count, render=True)`.
- **Not** with `tick(..., render=False)`, and not after `load_state()`. Call `tick()` to see the loaded state.
- Before the first `tick()` it is black.

## Raw buffers

`.raw_buffer` is a `memoryview` over the RGBA bytes, row by row from the top-left:

| | `screen` | `top` / `bottom` |
|---|---|---|
| `raw_buffer_dims` | `(384, 256)` | `(192, 256)` |
| bytes | 393 216 | 196 608 |
| format | `"RGBA"` | `"RGBA"` |

Pixel `(x, y)` starts at byte `(y * 256 + x) * 4`. `screen.raw_buffer` is `top.raw_buffer` followed by
`bottom.raw_buffer` (they are slices of the same memory). The buffer is overwritten on each rendered tick, so copy it
(`bytes(...)`) to keep it.

## numpy

numpy isn't a dependency, but conversion is one line:

```python
import numpy as np

frame = np.asarray(pm.screen.image)                 # copy, shape (384, 256, 4), uint8
top   = np.asarray(pm.screen.top.image)[:, :, :3]   # (192, 256, 3) RGB

# no-copy live view of the raw buffer
live = np.frombuffer(pm.screen.raw_buffer, dtype=np.uint8).reshape(384, 256, 4)
```

## Common recipes

Side-by-side instead of stacked:

```python
from PIL import Image

def side_by_side(pm):
    img = Image.new("RGBA", (512, 192))
    img.paste(pm.screen.top.image, (0, 0))
    img.paste(pm.screen.bottom.image, (256, 0))
    return img
```

Upscale for viewing or for a vision model:

```python
big = pm.screen.image.resize((512, 768), Image.NEAREST)
```

Detect a black screen (loading or fade):

```python
def is_black(img, threshold=8):
    return max(img.convert("L").getextrema()) <= threshold
```

Has anything changed?

```python
before = pm.screen.image.tobytes()
pm.button("a"); pm.tick(30)
changed = pm.screen.image.tobytes() != before
```

Save a GIF of 5 seconds:

```python
frames = []
for _ in range(50):
    pm.tick(6)
    frames.append(pm.screen.image.convert("RGB"))   # convert() returns a new image
frames[0].save("clip.gif", save_all=True, append_images=frames[1:], duration=100, loop=0)
```
