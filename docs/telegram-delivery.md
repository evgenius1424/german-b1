# Telegram delivery

`scripts/exam telegram <id>` derives a Telegram manifest from a validated exam. Each part becomes one channel post: a single audio post for Parts 2–4 and an audio album for Part 1. Questions are attached as captions; answers and transcripts are comments in the linked discussion group.

Before live publishing, run:

```zsh
scripts/exam publish <id> --dry-run
```

Live publication needs `BOT_KEY`, a channel where the bot is an administrator, and a linked discussion group where it is also an administrator. `BOT_CHAT_ID` or `--chat` overrides the manifest's default channel.

The publisher records local state in `exams/<id>/published.json` after each successful post and comment, so rerunning after an interruption resumes instead of duplicating completed work. This state is intentionally ignored by Git because it is deployment history, not exam content.
