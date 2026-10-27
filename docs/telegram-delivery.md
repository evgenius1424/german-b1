# Telegram delivery

`scripts/exam telegram <id>` derives a Telegram manifest from a validated exam. Each part becomes one channel post: a single audio post for Parts 2–4 and an audio album for Part 1. Questions are attached as captions; answers and transcripts are comments in the linked discussion group.

Before live publishing, run:

```zsh
scripts/exam publish <id> --dry-run
```

Live publication needs `BOT_KEY`, a channel where the bot is an administrator, and a linked discussion group where it is also an administrator. `BOT_CHAT_ID` or `--chat` overrides the manifest's default channel.

The publisher records local state in `exams/<id>/published.json` after each successful post and comment, so rerunning after an interruption resumes instead of duplicating completed work. This state is intentionally ignored by Git because it is deployment history, not exam content.

## Vocabulary post

After the four Teil posts, the publisher sends one plain message with 10–15 high-value expressions from that exam, so the post sits between consecutive exams. `scripts/exam vocab <id> [--count N] [--show]` asks the model for ranked candidates (`scripts/hoeren/vocab.py`), validates and selects them in code (`vocab_rank.py`: each expression must occur in the transcript, no names or basic words, dedup, category diversity, a mild penalty for words in earlier posts), and stores the result in the tracked `exams/<id>/vocab.json`. `vocab_post.py` renders the HTML from that file, so publishing never calls the model. `exams/vocab-history.json` records what each exam's post used. `scripts/exam new` runs this step after audio; `--no-vocab` skips it there and in `publish`, and `spec.VOCAB_ENABLED` turns it off globally. In `published.json` the message is recorded as the `vocab` post.

After an exam's posts are out, the publisher pins its Teil 1 post silently and deletes the channel's "pinned" notice, so the pinned list works as an exam index. It records `pinned: true` on `teil1`. A failed pin only prints a warning.
