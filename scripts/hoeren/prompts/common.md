## Output contract

Return one JSON object that matches the given schema. Work in this order inside the object: speakers, then `facts`, then `turns` (the audio script), then `questions`.

- `facts`: the fact frames the audio will contain, including every fact a distractor is built from. `id` like "F1"; `frame` as `slot=value; slot=value` (for example `agent=Tochter; action=abholen; time=17 Uhr; status=geplant, dann abgesagt`).
- `turns`: the complete audio script. `speaker` is a speaker `id`.
- `questions`: exactly as numbered in the blueprint, with exactly the blueprint's `answer`, `trap` and `difficulty`.
  - `prompt`: the statement or question stem the candidate reads, in German, without a number prefix.
  - `options`: three options a, b, c for multiple-choice items, each with the `fact_id` it comes from and, for wrong options, `why_wrong` (one short English phrase naming the corrupted slot). Empty array for other item types.
  - `answer`: from the blueprint.
  - `target_fact`: the fact id the item tests.
  - `evidence_quote`: a verbatim excerpt (5–25 words) of one turn that decides the item. Copy it character for character.
  - `slot`: the semantic slot the item tests.
  - `explanation`: German, at most 160 characters, shown after answering. Say why the answer is right and what the trap was, for example "Der Termin war um 9 Uhr geplant, wurde aber auf 11 Uhr verschoben."
- `situation`: one German sentence of context the candidate reads before listening, in exam style.
- `topic`: a short English label of the skin, for the index.

Numbers in the blueprint are item numbers in the full exam (1–30).
