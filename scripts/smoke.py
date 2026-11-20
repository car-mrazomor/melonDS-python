"""Smoke test: boot a ROM, run frames, press buttons, dump screenshots, roundtrip a savestate.

usage: python scripts/smoke.py roms/pokemon_white.nds [outdir]
"""

import sys
import time
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from melonds_python import _bindings as b  # noqa: E402


def dump(core, out: Path, name: str) -> None:
    top, bottom = core.screens()
    img = Image.new("RGB", (b.SCREEN_WIDTH, b.SCREEN_HEIGHT * 2))
    img.paste(Image.frombytes("RGBA", (256, 192), top).convert("RGB"), (0, 0))
    img.paste(Image.frombytes("RGBA", (256, 192), bottom).convert("RGB"), (0, 192))
    img.save(out / f"{name}.png")


def run(core, n: int, keys: int = 0) -> None:
    core.set_keys(keys)
    for _ in range(n):
        core.run_frame()
    core.set_keys(0)


def main() -> None:
    rom = Path(sys.argv[1])
    out = Path(sys.argv[2] if len(sys.argv) > 2 else "smoke_out")
    out.mkdir(exist_ok=True)

    core = b.Core(jit="--no-jit" not in sys.argv)
    core.load_rom(rom, out / (rom.stem + ".sav"))

    t = time.perf_counter()
    run(core, 600)
    dt = time.perf_counter() - t
    print(f"600 frames in {dt:.2f}s ({600 / dt:.0f} fps)")
    dump(core, out, "f0600")

    # mash A/Start through intro screens
    for i in range(10):
        run(core, 10, b.KEY_A)
        run(core, 50)
    dump(core, out, "f1200_after_A")

    core.touch(128, 96)
    run(core, 10)
    core.release_touch()
    run(core, 30)

    state = core.save_state()
    print(f"savestate: {len(state)} bytes")
    top_before, _ = core.screens()
    run(core, 120, b.KEY_A)
    core.load_state(state)
    run(core, 0)
    print("main RAM:", len(core.main_ram()), "bytes; frames:", core.frame_count())
    print("audio frames buffered:", core.audio_available())
    dump(core, out, "after_loadstate")
    core.close()


if __name__ == "__main__":
    main()
