# Generation guide

## Prerequisites

- Python 3.12 environment at `.venv-tts`
- local TTS dependencies and voices
- the authenticated headless `claude` CLI for structured generation

## Operating model

Use `scripts/exam new --no-audio` when reviewing or iterating on text is the immediate goal. Use `scripts/exam validate <id> --details` only when it is acceptable to print exam content and validation context. After intentional edits, run validation before rendering.

`regen` replaces selected parts. Add `--reroll` only when the scenario itself should change; otherwise the blueprint remains stable and regeneration is focused on improving the writing.

Tracked exam JSON is useful both as a public product example and a regression fixture. Audio is not tracked: it is large, binary, and reproducible from the turns and voice assignment in `exam.json`.

## Failure behavior

Generation performs a bounded number of repair rounds. If errors remain, the command exits non-zero and identifies the affected part without requiring callers to understand the internal validation rules. Re-run generation for that part or correct the JSON, then validate again.
