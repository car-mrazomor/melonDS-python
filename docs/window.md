# Window (optional)

By default PymelonDS has no window. If you want to **watch** a script or agent play, or play yourself, open an SDL2
window:

```python
from melonds_python import PymelonDS

pm = PymelonDS("game.nds", window="SDL2")
while pm.tick():          # returns False once the window is closed
    pass
pm.stop()
```

## Install

The window uses [PySDL2](https://pypi.org/project/PySDL2/), the same library PyBoy uses. It's optional:

```sh
pip install pysdl2 pysdl2-dll
# or: pip install -r requirements-window.txt
```

`pysdl2-dll` ships the SDL2 library itself, so nothing else is needed. Without it,
`PymelonDS(..., window="SDL2")` raises `PymelonDSDependencyError` with the install command.

## Options

```python
PymelonDS(rom, window="SDL2", scale=2)
```

| Argument | Values | Default |
|---|---|---|
| `window` | `"null"` (no window; `"headless"` and `"dummy"` are aliases), `"SDL2"` | `"null"` |
| `scale` | integer ≥ 1. Initial window size is 256·scale × 384·scale. | `2` (512×768) |

The window can be resized. The picture scales with nearest-neighbour filtering and keeps its aspect ratio.

## Speed

| | Default speed |
|---|---|
| `window="null"` | unlimited (as fast as possible) |
| `window="SDL2"` | 1× real time (about 60 fps) |

Change it at any time:

```python
pm.set_emulation_speed(1)    # real time
pm.set_emulation_speed(4)    # 4x
pm.set_emulation_speed(0)    # unlimited
```

The limit applies to every frame inside `tick(n)`, so `tick(60)` takes about one second at speed 1.
`set_emulation_speed` also works without a window, for example to slow a headless script down to real time.

## What the window shows

The window redraws **every emulated frame**, independent of `render=`. `render=False` still only means that
`pm.screen` isn't updated. Top screen above, bottom (touch) screen below.

## Keyboard and mouse

| DS | Key |
|---|---|
| A | `X` |
| B | `Z` |
| X | `S` |
| Y | `A` |
| L | `Q` |
| R | `W` |
| Start | `Enter` |
| Select | `Backspace` |
| D-pad | arrow keys |
| Touch screen | left mouse button on the bottom screen (click, hold, drag) |
| Close | `Esc` or the window's close button |

This is the same layout as desktop melonDS. Keyboard buttons and buttons pressed from code (`button`,
`button_press`) are combined: the game sees a button as held if either source holds it. Keys are released
automatically when the window loses focus.

## Closing the window

Closing the window (or pressing `Esc`) doesn't stop the emulator. From then on `tick()` returns `False`, the same
as PyBoy. Your loop should check it and call `stop()`:

```python
with PymelonDS("game.nds", window="SDL2") as pm:
    while pm.tick():
        ...
# stop() ran, the .sav is written and the window is gone
```

`stop()` closes the window.

## Watching an agent

```python
pm = PymelonDS("game.nds", window="SDL2")
pm.set_emulation_speed(0)          # don't slow the agent down; the window still shows every frame

while pm.tick():
    action = choose_action(pm.screen.image.copy())
    pm.button(action, 4)
    if not pm.tick(24):
        break
pm.stop()
```

## Things to know

- **Call `tick()` regularly.** The window processes input and redraws only inside `tick()`. While your code is
  busy elsewhere (for example waiting for a model), the window doesn't respond, and the OS may show it as
  "not responding". That's harmless, and it recovers on the next `tick()`.
- **macOS: use the main thread.** macOS only allows windows on the main thread. Create and tick a windowed
  `PymelonDS` from the main thread. Headless instances can run on any thread.
- **Several windows** can be open at the same time, one per `PymelonDS`.
- **No sound.** The window is picture and input only.
- **Remote/SSH or Docker without a display** can't open a window. Use the default `window="null"`.
