"""Render regenerable MP3s for listening units with the local TTS adapter."""

import sys

from .spec import ROOT

sys.path.insert(0, str(ROOT / "scripts"))
import tts  # noqa: E402


def unit_path(exam_dir, unit):
    return exam_dir / "audio" / f"{unit['id']}.mp3"


def render(exam, exam_dir, parts=None, force=False, speed=1.0, temperature=0.6):
    synth = tts.Synth(speed, temperature, tts.NEUTRAL)
    rendered = []
    for part in exam["parts"].values():
        if parts and part["part"] not in parts:
            continue
        for unit in part["units"]:
            out = unit_path(exam_dir, unit)
            if out.exists() and not force:
                continue
            speakers = {s["id"]: s for s in unit["speakers"]}
            turns = [
                (speakers[t["speaker"]]["name"], tts.VOICES[speakers[t["speaker"]]["voice"]], t["text"])
                for t in unit["turns"]
            ]
            print(f"== {unit['id']}", file=sys.stderr)
            tts.render(turns, out, synth, plays=part["plays"])
            rendered.append(out)
    return rendered
