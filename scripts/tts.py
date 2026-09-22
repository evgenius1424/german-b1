"""Turn a "Name: text" dialogue file into a German audio file (local TTS).

Run through scripts/tts, which uses the .venv-tts environment.
"""

import argparse
import datetime
import re
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PIPER_DIR = ROOT / ".tts-models" / "piper"
QWEN_MODEL = "mlx-community/Qwen3-TTS-12Hz-1.7B-CustomVoice-8bit"
RATE = 24000
# Keeps Qwen from acting: no laughing, sighing or exaggerated emphasis.
NEUTRAL = (
    "Sprich ruhig, sachlich und neutral, wie eine Sprecherin oder ein Sprecher "
    "in einem Sprachtest. Kein Lachen, kein Seufzen, keine übertriebene Betonung."
)

# Speaker label -> (engine, voice). Labels are case-insensitive.
# Approved roles: Petra = solo female,
# Markus = solo male, Anna = dialogues with Markus only (too emotional solo).
# Jonas, Herr Weber, Sabine and Thomas are untested extras.
# Temporarily all Piper (2026-09-22): the Qwen voices over-acted (laughing,
# "high"-sounding). To go back, set anna -> ("qwen", "Vivian"), markus -> ("qwen", "Ryan").
VOICES = {
    "anna": ("piper", "de_DE-ramona-low"),
    "markus": ("piper", "de_DE-thorsten-high"),
    "jonas": ("qwen", "Aiden"),
    "herr weber": ("qwen", "Uncle_Fu"),
    "petra": ("piper", "de_DE-kerstin-low"),
    "sabine": ("piper", "de_DE-ramona-low"),
    "thomas": ("piper", "de_DE-thorsten-high"),
}
# "Ansage" is a station/phone announcement voice.
VOICES["ansage"] = VOICES["petra"]

# Piper voices run fast; slow them to B1 pace on top of --speed.
PIPER_PACE = {"de_DE-kerstin-low": 0.85, "de_DE-ramona-low": 0.9, "de_DE-thorsten-high": 0.9}


# Qwen length guard: typical pace, and how often to redo a chunk that is far off it.
QWEN_SEC_PER_WORD = 0.45
QWEN_TRIES = 5
QWEN_CHUNK_WORDS = 30


def sentence_chunks(text, limit=QWEN_CHUNK_WORDS):
    """Split at sentence ends into chunks of at most ~limit words."""
    chunks, cur = [], []
    for sentence in re.split(r"(?<=[.?;:])\s+", text.strip()):
        if cur and len(" ".join(cur + [sentence]).split()) > limit:
            chunks.append(" ".join(cur))
            cur = []
        cur.append(sentence)
    chunks.append(" ".join(cur))
    return chunks


def trim_silence(audio, sr, threshold=0.01, margin=0.08, max_pause=0.8):
    """Cut edge silence and cap any inner pause at max_pause seconds."""
    import numpy as np

    frame = int(0.05 * sr)
    n = len(audio) // frame
    if not n:
        return audio
    loud = np.abs(audio[: n * frame]).reshape(n, frame).max(axis=1) > threshold
    if not loud.any():
        return audio
    first, last = loud.argmax(), n - 1 - loud[::-1].argmax()
    pad = int(margin * sr)
    out, quiet = [], 0
    for i in range(first, last + 1):
        quiet = 0 if loud[i] else quiet + 1
        if quiet * 0.05 <= max_pause:
            out.append(audio[i * frame : (i + 1) * frame])
    body = np.concatenate(out)
    return np.concatenate([audio[max(first * frame - pad, 0) : first * frame], body,
                           audio[(last + 1) * frame : (last + 1) * frame + pad]])


def parse(path: Path, cast):
    turns = []
    for n, raw in enumerate(path.read_text().splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r"^([^:]{1,30}):\s*(.+)$", line)
        if not m:
            sys.exit(f"{path}:{n}: expected 'Name: text', got: {line}")
        label, text = m.group(1).strip(), m.group(2).strip()
        key = cast.get(label.lower(), label.lower())
        if key in VOICES:
            voice = VOICES[key]
        else:
            sys.exit(
                f"{path}:{n}: unknown speaker '{label}'. Known: "
                + ", ".join(sorted(VOICES))
            )
        turns.append((label, voice, text))
    if not turns:
        sys.exit(f"{path}: no dialogue lines found")
    voices = {voice for _, voice, _ in turns}
    if VOICES["anna"] in voices and VOICES["markus"] not in voices:
        print("warning: Anna is only approved in dialogues with Markus", file=sys.stderr)
    return turns


class Synth:
    def __init__(self, speed, temperature, instruct):
        self.speed = speed
        self.temperature = temperature
        self.instruct = instruct
        self._qwen = None
        self._piper = {}

    def qwen(self, text, voice, out):
        """Qwen degenerates on long inputs (babble, long silences), so synthesise
        sentence chunks separately and redo any chunk with an implausible length."""
        if self._qwen is None:
            from mlx_audio.tts.utils import load_model

            self._qwen = load_model(QWEN_MODEL)
        import numpy as np
        import soundfile as sf

        sr = self._qwen.sample_rate
        pause = np.zeros(int(0.3 * sr), dtype=np.float32)
        pieces = []
        for chunk in sentence_chunks(text):
            n = len(chunk.split())
            expected = QWEN_SEC_PER_WORD * n / self.speed
            best = None
            for _ in range(QWEN_TRIES):
                audio = trim_silence(np.concatenate([
                    np.array(r.audio, dtype=np.float32)
                    for r in self._qwen.generate(
                        text=chunk,
                        voice=voice,
                        lang_code="german",
                        speed=self.speed,
                        temperature=self.temperature,
                        instruct=self.instruct or None,
                    )
                ]), sr)
                dur = len(audio) / sr
                if best is None or abs(dur - expected) < abs(len(best) / sr - expected):
                    best = audio
                if 0.45 * expected <= dur <= 1.8 * expected + 1.0:
                    break
                print(f"  retry: {dur:.1f}s for {n} words (expected ~{expected:.1f}s)", file=sys.stderr)
            pieces += [best, pause]
        sf.write(out, np.concatenate(pieces[:-1]), sr)

    def piper(self, text, voice, out):
        from piper import PiperVoice, SynthesisConfig

        if voice not in self._piper:
            self._piper[voice] = PiperVoice.load(PIPER_DIR / f"{voice}.onnx")
        cfg = SynthesisConfig(length_scale=1.0 / (self.speed * PIPER_PACE.get(voice, 1.0)))
        with wave.open(str(out), "wb") as w:
            self._piper[voice].synthesize_wav(text, w, syn_config=cfg)

    def say(self, engine, voice, text, out):
        getattr(self, engine)(text, voice, out)


def parse_cast(spec):
    """'Moderator=petra,Herr Klein=markus' -> {'moderator': 'petra', ...}"""
    cast = {}
    for pair in filter(None, (spec or "").split(",")):
        label, _, voice = pair.partition("=")
        if voice.strip().lower() not in VOICES:
            sys.exit(f"--cast: unknown voice '{voice}'. Known: " + ", ".join(sorted(VOICES)))
        cast[label.strip().lower()] = voice.strip().lower()
    return cast


def ffmpeg(*args):
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", *map(str, args)], check=True
    )


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("script", type=Path, help="text file with 'Name: text' lines")
    ap.add_argument("-o", "--output", type=Path, help="default: materials/generated/<name>.mp3")
    ap.add_argument("--cast", help="map script names to cast voices, e.g. 'Moderator=petra,Herr Klein=markus'")
    ap.add_argument("--speed", type=float, default=1.0)
    ap.add_argument("--temperature", type=float, default=0.6, help="lower = less expressive (Qwen)")
    ap.add_argument("--instruct", default=NEUTRAL, help="Qwen style prompt; '' to disable")
    ap.add_argument("--gap", type=float, default=0.6, help="seconds between turns")
    ap.add_argument("--plays", type=int, default=1, help="play the whole thing N times")
    ap.add_argument("--play-gap", type=float, default=5.0, help="seconds between plays")
    args = ap.parse_args()

    turns = parse(args.script, parse_cast(args.cast))
    out = args.output or ROOT / "materials" / "generated" / f"{args.script.stem}.mp3"
    out.parent.mkdir(parents=True, exist_ok=True)

    synth = Synth(args.speed, args.temperature, args.instruct)
    render(turns, out, synth, args.gap, args.plays, args.play_gap)
    log_generated(out)
    print(out)


def render(turns, out, synth, gap=0.6, plays=1, play_gap=5.0):
    """Synthesise (label, (engine, voice), text) turns into one mp3 at `out`."""
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        parts = []
        gap_wav = tmp / "gap.wav"
        ffmpeg("-f", "lavfi", "-i", f"anullsrc=r={RATE}:cl=mono", "-t", gap, gap_wav)
        for i, (label, (engine, voice), text) in enumerate(turns):
            raw, norm = tmp / f"{i}_raw.wav", tmp / f"{i}.wav"
            print(f"[{i + 1}/{len(turns)}] {label} ({engine}:{voice})", file=sys.stderr)
            synth.say(engine, voice, text, raw)
            ffmpeg("-i", raw, "-ar", RATE, "-ac", 1, norm)
            parts += [norm, gap_wav]

        def concat(files, dest):
            lst = tmp / "list.txt"
            lst.write_text("".join(f"file '{f}'\n" for f in files))
            ffmpeg("-f", "concat", "-safe", 0, "-i", lst, "-c", "copy", dest)

        once = tmp / "once.wav"
        concat(parts[:-1], once)
        if plays > 1:
            pgap = tmp / "pgap.wav"
            ffmpeg("-f", "lavfi", "-i", f"anullsrc=r={RATE}:cl=mono", "-t", play_gap, pgap)
            full = tmp / "full.wav"
            concat([once, pgap] * (plays - 1) + [once], full)
        else:
            full = once

        ffmpeg("-i", full, "-codec:a", "libmp3lame", "-q:a", "3", out)


def log_generated(out, index=None):
    index = index or out.parent / "index.md"
    if not index.exists():
        index.write_text("# Generated audio\n\n")
    with index.open("a") as f:
        f.write(f"- {datetime.date.today()} `{out.name}` — origin: generated\n")


if __name__ == "__main__":
    main()
