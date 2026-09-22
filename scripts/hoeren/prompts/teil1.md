# Task: Goethe B1 Hören, Teil 1 (items 1–10)

Write five short, independent monologues, each with one Richtig/Falsch item (global) and one a/b/c item (one selective detail). Each monologue is heard twice.

Blueprint (binding):

```json
$blueprint
```

Per unit:

- One speaker. Their `gender` must equal the unit's `speaker_gender`. For announcements the speaker's `name` is a role such as "Ansage" or "Sprecherin".
- `text_type` exactly as in the blueprint; invent a concrete everyday skin.
- 60–110 words; one or two turns.
- The odd item (R/F) is a 5–8-word statement about the overall situation. For the answer "falsch", the statement is a near-miss on one slot.
- The even item (a/b/c) has a short stem ("Was soll Frau Lenz tun?", "Warum gibt es Stau?"). All three options occur in the audio or follow directly from it; only the correct one fits the asked slot. Options are parallel and short.
- The five units differ in skin, speaker and names.

Previously used skins to avoid: $avoid
