# Audio rendering

Audio is a local adapter from validated turns to MP3 files. It assigns a small fixed cast of voices based on the speaker records in `exam.json`, renders one file per listening unit, and applies each part's required replay count.

Audio files live in `exams/<id>/audio/` and are ignored by Git. They can be recreated with:

```zsh
scripts/exam audio <id>
```

Cast (`scripts/tts.py`, `VOICES`): Markus and Petra use Piper; Anna uses a local Chatterbox Multilingual voice clone (MLX weights in `.tts-models/chatterbox/mlx-v3/`, reference clip in `materials/private/voices/laura_ref.wav`). Both paths are gitignored, so a fresh checkout needs them copied in before it can render Anna.

The renderer exists to make generated text usable as listening material. It is not a general-purpose audio archive, and no generated MP3s are required to inspect, test, or contribute to the generator.
