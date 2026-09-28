"""Speech from the watch: a WAV clip in, text out, transcribed on this Mac, so the audio never leaves the room
(docs/research/notes/G-watch-agent.md §7). The watch's own recognizer is not used, because it may call a cloud
service. What was said is either a note to remember or a question for the brain."""
from __future__ import annotations

import io
import re
import wave
from pathlib import Path

import numpy as np

RATE = 16_000                           # Whisper's input rate
REMEMBER = re.compile(r"^\s*(?:please\s+)?(?:remember(?:\s+that)?|(?:make|take)\s+a\s+note(?:\s+that)?|note\s+that)"
                      r"\b[\s,:.-]*", re.IGNORECASE)


class Unavailable(RuntimeError):
    """Speech recognition is not installed here, or its model has not been downloaded."""


def samples(wav: bytes) -> np.ndarray:
    """Mono float32 samples at 16 kHz from a 16-bit PCM WAV file (any rate, any number of channels)."""
    try:
        with wave.open(io.BytesIO(wav)) as w:
            width, rate, channels = w.getsampwidth(), w.getframerate(), w.getnchannels()
            frames = w.readframes(w.getnframes())
    except (wave.Error, EOFError) as e:
        raise ValueError(f"not a WAV file: {e}") from e
    if width != 2:
        raise ValueError("16-bit PCM WAV only")
    pcm = np.frombuffer(frames, dtype="<i2")
    x = pcm[: len(pcm) - len(pcm) % channels].reshape(-1, channels).mean(axis=1) / 32768.0
    if rate != RATE and len(x):
        x = np.interp(np.arange(0, len(x), rate / RATE), np.arange(len(x)), x)
    return x.astype(np.float32)


def route(text: str) -> tuple[str, str]:
    """('add', the note) for "remember …" / "note that …", else ('ask', the question). A clip that ends in a
    question mark is a question even when it starts with "remember" ("remember when Vince moved it?")."""
    m = REMEMBER.match(text)
    note = text[m.end():].strip() if m else ""
    if note and not text.rstrip().endswith("?"):
        return "add", note[0].upper() + note[1:]
    return "ask", text.strip()


class Transcriber:
    """Whisper on MLX (`uv sync --extra voice`). It uses only a model already on disk: a missing model is an error,
    never a download at runtime."""

    def __init__(self, model: str):
        self.model = model
        self._path: str | None = None

    def __call__(self, audio: np.ndarray) -> str:
        if self._path is None:                  # before the (slow) import: a missing model fails fast
            self._path = self._local(self.model)
        try:
            import mlx_whisper
        except ImportError as e:
            raise Unavailable("speech recognition is not installed: uv sync --extra voice") from e
        r = mlx_whisper.transcribe(audio, path_or_hf_repo=self._path, language="en",
                                   condition_on_previous_text=False, verbose=None)
        return r["text"].strip()

    @staticmethod
    def _local(model: str) -> str:
        if Path(model).is_dir():
            return model
        from huggingface_hub import snapshot_download
        from huggingface_hub.errors import LocalEntryNotFoundError

        try:
            return snapshot_download(model, local_files_only=True)
        except LocalEntryNotFoundError as e:
            raise Unavailable(f"speech model {model} is not downloaded (huggingface-cli download {model})") from e
