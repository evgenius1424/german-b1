# Goethe B1 Hören — generator ontology

Source of truth for generated Hören exams. `scripts/exam` sends this file verbatim as the system prompt, so edit the
rules here, not in code.

Derived from the structure of the official adult Modellsatz and Übungssatz (4 parts, 30 items). Two public sets reveal
how items are built; they do not support frequency claims ("x% of exams contain…"). All examples below are invented and
are not official items.

## Core principle

Goethe rarely tests whether a word was heard. It tests whether the heard information was attached to the correct *
*semantic slot**.

Model every important fact as a frame:

```
agent · action/state · object · recipient · time · place · cause
quantity · modality · polarity · status · condition · source/speaker
```

A good distractor is a **true fact with a corrupted slot** ("fact preservation + slot corruption"). All three options of
a multiple-choice item normally occur in the audio, but only one occupies the asked slot.

Example (invented): a bus announcement mentions line 12 to Nordpark (running normally), line 7 to Klinikum (cancelled)
and a replacement via Schillerplatz. Asked "Welche Linie fällt aus?", the options are 12 / 7 / the replacement, not
three random numbers.

## The four parts

| Part   | Audio                                                                        | Plays | Items                                                                | What it really tests                                                 |
|--------|------------------------------------------------------------------------------|-------|----------------------------------------------------------------------|----------------------------------------------------------------------|
| Teil 1 | 5 short monologues: voicemail, announcement, traffic, weather, radio notice  | 2     | per text: 1 Richtig/Falsch (global) + 1 a/b/c (one selective detail) | situation → one critical fact                                        |
| Teil 2 | 1 organised monologue: guided tour, programme introduction, orientation talk | 1     | 5 × a/b/c                                                            | an information map; each item = one block, in audio order            |
| Teil 3 | 1 informal conversation between a woman and a man                            | 1     | 7 × Richtig/Falsch                                                   | reconstruct what actually happened: who did what, planned vs. actual |
| Teil 4 | 1 radio discussion: moderator + 2 guests                                     | 2     | 8 statements → assign to one of the 3 speakers                       | who owns which claim; not factual truth                              |

### Teil 1

Typical internal flow: context → reason for the message → change or development → 1–3 competing details → requested
action → optional extra information.

- Question 1 (R/F) checks the overall situation. 5–8 words.
- Question 2 (a/b/c) isolates one slot: what should the listener do, why, which, where, when, what is included.
- Strong patterns: change/cancellation (the first state is superseded); several competing numbers, times or places; a
  required response (what the listener must do, not why the caller called); mentioned ≠ answer (an amount or place
  appears but answers a different slot).

### Teil 2

- The monologue is organised in blocks. Question N covers block N; the items follow the audio order strictly.
- Characteristic trap: three related truths (normally / today / previously), and only one fits the asked relationship.
- Adjacent places (meet at X, café opposite X, lockers next to X), adjacent times (07:00 activity, 08:00 breakfast), and
  modality (recommended ≠ compulsory; register the day before vs. the same morning).
- Options are short, parallel and of the same semantic class (three times, three places, three statuses).

### Teil 3

- Everyday storytelling between two people who know each other (du-form).
- The candidate builds an event graph: who did what, what was only wanted or planned, what someone else did, what was
  possible vs. chosen, what was forecast vs. real.
- Statements are 4–10 words and follow the audio order. The complexity lives in the audio, not in the statement.
- Roughly half the statements are true. False statements are near-misses, never absurd.

### Teil 4

- The moderator introduces, summarises and also owns real claims; the moderator is a valid answer for 1–2 statements.
- All speakers use the same nouns, so keyword matching must fail. A statement's keyword should appear in the turns of at
  least two speakers.
- A speaker can concede a point to the other side ("Das Argument verstehe ich, aber …") and so own a statement that
  sounds like the other side.
- Statements are summarised claims, 6–11 words, paraphrased rather than quoted, in roughly the audio order.

## Trap types

| Trap                 | Logic                                                                     |
|----------------------|---------------------------------------------------------------------------|
| `ACTOR_SWAP`         | right event, wrong person                                                 |
| `RECIPIENT_SWAP`     | action attached to the wrong recipient (A calls B vs. B calls A)          |
| `ROLE_SWAP`          | relationship or status confused (a friend's brother vs. the friend)       |
| `PLAN_ACTUAL`        | the plan differs from what happened                                       |
| `OLD_NEW`            | old information is superseded by new                                      |
| `FORECAST_ACTUAL`    | prediction differs from reality                                           |
| `WANT_DO`            | wish or intention mistaken for reality                                    |
| `AVAILABLE_CHOSEN`   | an available option mistaken for the chosen one                           |
| `MENTIONED_TRUE`     | the word or fact appears but does not answer the question                 |
| `CAUSE_SWAP`         | several causes; the wrong one is attached                                 |
| `PLACE_SWAP`         | nearby or related places exchanged                                        |
| `TIME_SWAP`          | several times attached to the wrong events                                |
| `QUANTITY_SCOPE`     | exact number, range or who it applies to                                  |
| `MODALITY`           | can / must / should / recommended confused                                |
| `NEGATION`           | explicit or contextual negation (kein, nicht mehr, nie)                   |
| `CONDITION`          | true only under a condition (wenn es regnet, falls angemeldet)            |
| `TEMPORAL_SCOPE`     | past, current or future confused (was closed vs. is closed)               |
| `PART_WHOLE`         | true of a part, not the whole                                             |
| `REQUEST_ACTION`     | what someone asks the listener to do                                      |
| `REQUEST_RESULT`     | a request mistaken for a completed action                                 |
| `SOURCE_ATTRIBUTION` | who actually expresses the proposition                                    |
| `QUOTE_ATTRIBUTION`  | a speaker reports a view without endorsing it ("Viele sagen ja, …")       |
| `STANCE_QUALIFIER`   | partial agreement only ("ja, aber …", "nicht grundsätzlich dagegen")      |
| `KEYWORD_OVERLAP`    | several speakers use the statement's keyword; only one owns the claim     |
| `PARAPHRASE`         | the item avoids the audio's wording ("fast niemand da" → "ziemlich leer") |
| `DISTRACTOR_DENSITY` | every option occurs in the audio                                          |

## Semantic slots to mutate

`WHO` (actor, speaker, recipient) · `WHAT` (action, state, object) · `WHEN` · `WHERE` · `WHY` · `HOW_MUCH` ·
`POLARITY` · `MODALITY` · `STATUS` (planned, current, completed, cancelled) · `SCOPE` (all, some, only, also) ·
`CONDITION` · `SOURCE`

Most items mutate exactly one slot. Hard items mutate two. More than two feels arbitrary.

## Difficulty scale

1. target stated almost literally
2. simple paraphrase
3. distractor mentioned elsewhere in the audio
4. same semantic category plus a contrast or change
5. actor, time or status attribution plus paraphrase

Typical Goethe B1 items are level 3–4: easy vocabulary, several plausible facts, one semantic distinction. Never raise
difficulty with rare vocabulary.

## Generation rules

1. **Facts first, questions second.** Write the fact frames, then the audio, then the items.
2. Every wrong option must be explainable by a specific fact or nearby inference in the audio. Never invent distractors
   from unrelated information.
3. Items are much shorter and simpler than the audio that answers them. Correct answers are paraphrases, not verbatim
   copies.
4. Teil 2, 3 and 4 items follow the chronological order of their evidence in the audio.
5. B1 everyday vocabulary, clear standard German, natural spoken register. Difficulty comes from discourse relations,
   not words.
6. Use corrections, contrasts, old/new information, intentions, alternatives, conditions and third-person references
   naturally, but not in every sentence. Most sentences are plain information.
7. Signal words that often shift a slot, to be used naturally: aber, doch, leider, eigentlich, erst, noch, schon, nur,
   trotzdem, sondern, wenn, falls, nicht, später, früher, stattdessen.
8. Each item has an evidence quote copied verbatim from the audio.

## Audio-script rules (local TTS)

The audio is synthesised by `scripts/tts` with a fixed, approved cast. The cast is assigned in code; the text only has
to be speakable.

- No exclamation marks and no interjections (Ach, Oh, Haha, Hm, Na ja, Mensch, Wow). They make the TTS voices act.
- No sound descriptions, stage directions, brackets or emoji.
- No abbreviations: write "zum Beispiel", "ungefähr", "Prozent". Times, prices and numbers may be digits ("14:35 Uhr", "
  8 Euro").
- One turn is at most about 80 words. Split a long monologue into several turns by the same speaker, one per information
  block.
- Teil 3 turns are short and conversational (mostly 1–4 sentences), with genuine back-and-forth.

## Topic pools

Topic is only the skin; the information transformation makes an item Goethe-like.

- Personal and everyday: meetings, weekend, family, friends, celebrations, shopping, hobbies, moving house, neighbours
- Services: doctor, repair, landlord, insurance, bank, course, employer, library, authorities
- Mobility: train, bus, traffic, directions, travel, tourist information, bicycle
- Public information: weather, radio notice, event, competition, store announcement
- Organised activity: tour, course, programme, orientation day, festival schedule
- Social discussion: work, education, technology, environment, health, housing, consumption, leisure

Do not reproduce the scenarios of the official adult sets. Avoid in particular: a guided museum tour, a sports-holiday
week programme, a party with a hired pianist, a hiking weekend with friends, a radio discussion on childcare, a radio
discussion on children learning foreign languages, a cancelled Intercity with a replacement connection, and a repair
shop saying a repair is not worth it.
