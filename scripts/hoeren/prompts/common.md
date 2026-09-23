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

## Language: Goethe-Zertifikat B1 style

The audio script must read like the official Goethe-Zertifikat B1 Hörverstehen transcripts, not like written prose and not above B1.

- Vocabulary: Goethe B1 word list and everyday topics (Arbeit, Wohnen, Reisen, Gesundheit, Freizeit, Schule, Einkaufen, Verkehr). Prefer common words. Use a rarer word only when the situation demands it (a place name, a product), and keep it easy to hear.
- Grammar: Präsens, Perfekt, Futur with "werden", Modalverben, Konjunktiv II for polite requests and wishes ("Könnten Sie ...", "Ich hätte gern ..."), Nebensätze with weil, dass, wenn, obwohl, damit, Relativsätze, Passiv only occasionally. No Genitiv chains, no Partizipialattribute, no Nominalstil, no Konjunktiv I.
- Sentences: mostly 6–16 words; a main clause plus at most one subordinate clause. Split long ideas into two sentences.
- Register: spoken German. Announcements and guided tours are formal and polite (Sie, "Wir bitten um Ihr Verständnis"). Private calls and conversations are informal (du, "Hey", "Tja", "Na ja", "ähm", "also", "nicht wahr?", contractions like "hab", "nix", "'ne"), with occasional self-correction, a short reaction ("Ach so", "Echt?", "Mhm") or a topic detour.
- Discussions (Teil 4): each turn is a real reaction to the previous speaker, with "Aber", "Das stimmt, aber ...", "Ich sehe das anders", "Da haben Sie recht". No essay-style monologues.
- Content: concrete, checkable details (times, prices, places, names, numbers) placed inside natural talk, not listed. Some information the candidate does not need (small talk, a side remark) so that listening for the relevant detail is a real task.
- Distractors: keep wrong options anchored in the audio. Depending on the part and item difficulty, they may be stated and then corrected, cancelled or attributed to someone else, or be a plausible one-slot near-miss. They must not depend on vocabulary tricks above B1.
- Do not mention that this is an exam. No English in the German text.
