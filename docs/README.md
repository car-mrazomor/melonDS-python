# PymelonDS documentation

PymelonDS lets you run Nintendo DS games from Python with the [melonDS](https://melonds.kuribo64.net) emulator.
It runs headless by default: you step frames, press buttons, grab the screens as PIL images and save or load states.
An optional SDL2 window lets you watch or play along.
The API is modelled on [PyBoy](https://docs.pyboy.dk/), so code written for PyBoy carries over with few changes.

```python
from melonds_python import PymelonDS

with PymelonDS("game.nds") as pm:
    pm.tick(300)                    # 5 seconds of game time
    pm.button("a")
    pm.tick(60)
    pm.screen.image.save("both_screens.png")
```

## Contents

| Page | What's in it |
|---|---|
| [Getting started](getting-started.md) | Install, build, first script |
| [Building](building.md) | Build steps for macOS, Linux and Windows, CMake details, build problems |
| [API reference](api.md) | Every class, method, attribute and error of `PymelonDS` |
| [Input](input.md) | Buttons and exactly when presses and releases happen |
| [Screens](screen.md) | Both screens, live images, raw buffers, numpy |
| [Window](window.md) | Optional SDL2 window, emulation speed, keyboard/mouse |
| [States and saves](states-and-saves.md) | Savestates vs. battery saves (`.sav`) |
| [Using it with AI agents](agents.md) | Patterns for an observe → act loop |
| [Coming from PyBoy](pyboy-differences.md) | What's the same and what's different |
| [Low-level API](low-level.md) | `_bindings.Core` and the C API (`native/melonds_shim.h`) |
| [How it works](architecture.md) | Shim, Platform layer, build layout |
| [Troubleshooting](troubleshooting.md) | Common errors and fixes |

## At a glance

- **Platforms:** macOS (arm64, tested), Linux x86_64/arm64 (tested), Windows via MSYS2 (untested).
- **Speed:** roughly 900 fps with the JIT and about 300 fps with the interpreter on an Apple Silicon Mac. Real time is 60 fps.
- **No BIOS needed:** melonDS's FreeBIOS and a generated firmware are used unless you pass your own dumps.
- **Requirements:** Python ≥ 3.10 and Pillow. For the optional window: PySDL2 (`pip install pysdl2 pysdl2-dll`).
- **License:** GPL-3.0 (melonDS is GPL-3.0).
