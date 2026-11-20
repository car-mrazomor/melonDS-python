# Getting started

## 1. Get the code

```sh
git clone https://github.com/car-mrazomor/melonDS-python
cd melonDS-python
```

The melonDS source is included in `melonDS/`, so nothing else needs to be downloaded.

## 2. Build the native library

You need a C++17 compiler, CMake ≥ 3.16 and (recommended) Ninja. On macOS:

```sh
brew install cmake ninja
cmake -S . -B build -G Ninja
cmake --build build
```

For Linux and Windows see [Building](building.md). The result is
`melonds_python/_lib/libmelonds_py.dylib` (`.so` on Linux, `.dll` on Windows).
The first build takes a minute or two. Later builds only recompile what changed.

## 3. Install Pillow

```sh
pip install pillow
```

## 4. Check that it works

```sh
python scripts/smoke.py path/to/game.nds
```

This prints the emulation speed, saves screenshots to `smoke_out/` and tests savestates.

## 5. First script

Run it from the repository root, or put the repository on your `PYTHONPATH`:

```python
from melonds_python import PymelonDS

pm = PymelonDS("roms/game.nds")

pm.tick(600)                             # let the game boot (10 s of game time)
for _ in range(5):
    pm.button("a")                       # tap A
    pm.tick(60)                          # wait 1 s

pm.screen.image.save("both.png")         # 256x384, top screen above bottom
pm.screen.top.image.save("top.png")      # 256x192
pm.screen.bottom.image.save("bottom.png")

pm.stop()                                # also writes roms/game.sav
```

## What to read next

- [Input](input.md): how long buttons are held and when.
- [Screens](screen.md): why `pm.screen.image` changes by itself, and how to keep a frame.
- [States and saves](states-and-saves.md): savestates vs. in-game saves.
- [Using it with AI agents](agents.md): an example observe → act loop.

## ROMs, BIOS, firmware

- Use ROMs dumped from cartridges you own. `.nds`, `.sav` and `.bin` files are in `.gitignore`.
- A BIOS and firmware are **not** required. If a game misbehaves with FreeBIOS, pass your own dumps.
  See [API reference: constructor](api.md#constructor).
