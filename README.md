# Goethe B1 Hören Exam Generator

Generate complete, B1-style German listening practice exams and prepare them for publication to a Telegram channel.

Published exams: [@german_b1_horen on Telegram](https://t.me/german_b1_horen)

The project treats an exam as structured data first. A deterministic blueprint fixes coverage, answer-key balance, speaker constraints, and distractor types; an LLM writes the German content; validation checks the result against the blueprint and against audio and Telegram constraints. Audio and delivery artifacts can always be rebuilt from the tracked exam text.

> This is an independent practice-material generator. It is not affiliated with, endorsed by, or an official product of Goethe-Institut. Do not redistribute copyrighted source materials through this repository.

## What is tracked

- `exams/<id>/exam.json` — generated exam text plus hidden validation annotations
- `exams/<id>/telegram.json` — derived Telegram delivery manifest
- `docs/` and `materials/` — reusable format references, generation guidance, and copyright-safe source notes

Generated MP3s, downloaded media, credentials, and Telegram publication state are deliberately local-only. Render them again from `exam.json` whenever needed.

## Pipeline

```text
blueprint -> constrained LLM generation + repair -> validation
          -> local TTS audio -> Telegram manifest -> resumable publication
```

The command-line interface is intentionally small:

```zsh
scripts/exam new
scripts/exam new --no-audio
scripts/exam validate <id>
scripts/exam audio <id>
scripts/exam telegram <id>
scripts/exam publish <id> --dry-run
scripts/exam publish <id>
scripts/exam list
```

`scripts/exam` uses `.venv-tts/bin/python`; generation additionally requires the headless `claude` CLI, and audio rendering uses the local TTS setup described in [audio rendering](docs/audio-rendering.md).

For Telegram publishing, copy `.env.example` to the ignored `.env` file and set `BOT_KEY`. Optionally set `BOT_CHAT_ID` to override the manifest's default channel.

## Design

`scripts/hoeren/` is the core module. Its interface is the `scripts/exam` command above. The blueprint, LLM client, validator, TTS renderer, Telegram-manifest builder, and Telegram publisher are internal implementations behind that interface. This concentrates format knowledge and recovery behavior in one place while keeping external dependencies replaceable at their seams.

Read [exam design](docs/exam-design.md) for the generation rules, [generation guide](docs/generation-guide.md) for operating guidance, and [Telegram delivery](docs/telegram-delivery.md) for publishing behavior.
