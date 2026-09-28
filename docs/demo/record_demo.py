"""Record the demo video: drive the page's presenter mode (engram/src/engram/web/demo.js) in a Chromium window and
capture every frame the page paints (Chrome DevTools screencast, JPEG q92), then encode a 1080p H.264 MP4. No screen
recording permission is needed: the frames come from the browser, not the screen. No sound; the voice-over is added
later, and `<name>.beats.txt` gives each beat's start time to line it up.

    ENGRAM_DEMO_PASSPHRASE=… uv run --no-project --with playwright --with imageio-ffmpeg \\
        python docs/demo/record_demo.py [--from 6] [--name engram-demo]

It needs `engram serve` on 127.0.0.1:8770 and Playwright's Chromium (`playwright install chromium --no-shell`). The
beats keep the lengths in docs/demo/demo-script.md; a beat still waiting on a model delays the rest."""
from __future__ import annotations

import argparse
import asyncio
import base64
import os
import shutil
import subprocess
import time
from pathlib import Path

import imageio_ffmpeg
from playwright.async_api import async_playwright

URL = "http://127.0.0.1:8770/"
TARGETS = [0, 15, 25, 55, 85, 105, 135, 150, 165, 185]     # each beat's start (s), as in demo-script.md
HOLD = {9: 12.0, 10: 6.0}                                  # linger on the watch hand-off and the closing card
W, H, SCALE = 1280, 720, 1.5                               # CSS pixels × scale = 1920 × 1080 frames


async def record(first: int, frames: Path) -> list[tuple[int, float]]:
    passphrase = os.environ["ENGRAM_DEMO_PASSPHRASE"]
    shots: list[tuple[float, Path]] = []
    beats: list[tuple[int, float]] = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, args=[
            f"--window-size={W},{H + 90}", "--hide-scrollbars", "--force-color-profile=srgb",
            "--disable-backgrounding-occluded-windows", "--disable-renderer-backgrounding",
            "--disable-background-timer-throttling"])       # keep painting while other windows cover it
        ctx = await browser.new_context(viewport={"width": W, "height": H}, device_scale_factor=SCALE,
                                        color_scheme="dark", bypass_csp=True)   # lets the recorder's own waits run
        page = await ctx.new_page()
        if first > 2:                                     # a reshoot from a later beat starts signed in
            await page.goto(URL)
            await page.wait_for_selector(".eg-profile[data-name=kaminski]")
            await sign_in(page, passphrase)
        await page.goto(URL + (f"?demo={first}" if first > 1 else "?demo"))
        await page.wait_for_function("window.engramDemo !== undefined")
        await page.wait_for_timeout(2500)                 # fonts, the tiles' constellations, the 3D brain

        cdp = await ctx.new_cdp_session(page)

        async def on_frame(ev: dict) -> None:
            path = frames / f"{len(shots):06d}.jpg"
            path.write_bytes(base64.b64decode(ev["data"]))
            shots.append((ev["metadata"]["timestamp"], path))
            await cdp.send("Page.screencastFrameAck", {"sessionId": ev["sessionId"]})

        cdp.on("Page.screencastFrame", lambda ev: asyncio.ensure_future(on_frame(ev)))
        await cdp.send("Page.startScreencast", {"format": "jpeg", "quality": 92, "maxWidth": int(W * SCALE),
                                                "maxHeight": int(H * SCALE), "everyNthFrame": 1})
        t0 = time.monotonic()
        start = t0                                        # when the previous beat started
        for n in range(first, len(TARGETS) + 1):
            if n > first:                                 # each beat gets its scripted length; a slow model shifts
                gap = TARGETS[n - 1] - TARGETS[n - 2]     # the rest later instead of squeezing them
                await asyncio.sleep(max(0.0, start + gap - time.monotonic()))
            start = time.monotonic()
            await page.keyboard.press("ArrowRight")
            beats.append((n, time.monotonic() - t0))
            print(f"beat {n} at {beats[-1][1]:.1f} s", flush=True)
            if n == 2:                                    # the passphrase, typed as a person would
                await page.wait_for_selector(".eg-profile[data-name=kaminski] input[type=password]", state="visible")
                await page.wait_for_timeout(600)
                await page.locator(".eg-profile[data-name=kaminski] input[type=password]").press_sequentially(
                    passphrase, delay=110)
                await page.keyboard.press("Enter")
            await page.wait_for_function("!window.engramDemo.busy", timeout=240_000, polling=250)
            await asyncio.sleep(HOLD.get(n, 0.0))
        await cdp.send("Page.stopScreencast")
        await asyncio.sleep(0.5)
        await browser.close()
    stamp(frames, shots)
    return beats


async def sign_in(page, passphrase: str) -> None:
    tile = page.locator(".eg-profile[data-name=kaminski]")
    await tile.click()
    await tile.locator("input[type=password]").fill(passphrase)
    await page.keyboard.press("Enter")
    await page.wait_for_function("document.body.dataset.mode === 'dashboard'", timeout=60_000)


def stamp(frames: Path, shots: list[tuple[float, Path]]) -> None:
    """The frames in the order they were painted, with their times: the page paints only when something changes."""
    shots = sorted(shots)
    (frames / "frames.txt").write_text("".join(f"{t - shots[0][0]:.4f} {path.name}\n" for t, path in shots))


def encode(frames: Path, out: Path, fps: int = 30) -> None:
    """A constant 30 fps: each output frame is the one on screen at that moment, piped to ffmpeg as JPEG."""
    shots = [(float(t), frames / name) for t, name in (line.split() for line in (frames / "frames.txt").read_text()
                                                        .splitlines())]
    ff = subprocess.Popen([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-f", "image2pipe",
                           "-framerate", str(fps), "-c:v", "mjpeg", "-i", "-",
                           "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease:flags=lanczos:out_range=tv,"
                                  "pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=0x07080B,format=yuv420p",
                           "-c:v", "libx264", "-preset", "slow", "-crf", "17", "-color_range", "tv",
                           "-movflags", "+faststart", str(out)], stdin=subprocess.PIPE)
    k, i, end = 0, 0, shots[-1][0] + 0.5
    while k / fps <= end:
        while i + 1 < len(shots) and shots[i + 1][0] <= k / fps:
            i += 1
        ff.stdin.write(shots[i][1].read_bytes())
        k += 1
    ff.stdin.close()
    if ff.wait():
        raise RuntimeError("ffmpeg failed")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--from", dest="first", type=int, default=1, help="start at this beat (1–10)")
    ap.add_argument("--name", default="engram-demo", help="output file name, without .mp4")
    ap.add_argument("--out", default=str(Path.home() / "Movies" / "engram-demo"), help="output folder")
    a = ap.parse_args()
    out = Path(a.out)
    frames = out / f"{a.name}-frames"
    shutil.rmtree(frames, ignore_errors=True)
    frames.mkdir(parents=True)
    beats = asyncio.run(record(a.first, frames))
    video = out / f"{a.name}.mp4"
    encode(frames, video)
    (out / f"{a.name}.beats.txt").write_text("".join(f"beat {n:2d}  {int(t // 60)}:{t % 60:04.1f}\n" for n, t in beats))
    shutil.rmtree(frames)
    print(f"{video}  ({video.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
