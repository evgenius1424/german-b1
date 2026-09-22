# Task: Goethe B1 Hören, Teil 4 (items 23–30)

Write one radio discussion (heard twice) between a moderator and two guests, and eight statements, each owned by exactly one of the three speakers.

Blueprint (binding):

```json
$blueprint
```

- Speakers: ids "moderator", "guest1", "guest2", with genders as in `genders`. Moderator: first and last name, role "Moderator" or "Moderatorin". Guests: a first and last name and a concrete role (for example a teacher, a shop owner, a student, a doctor). Guests are addressed as Herr or Frau plus surname.
- Topic: the blueprint's `topic`. Positions are nuanced: one guest leans pro and one contra, but each concedes at least one point to the other side.
- 650–900 words, 14–22 turns. Each guest has at least 5 turns; the moderator opens, asks, summarises and owns real claims.
- Statement ownership is fixed by the blueprint `answer`. Statements come in roughly the audio order.
- Statements are summarised claims of 6–11 words, paraphrased (not quoted). The keyword of each statement also occurs in another speaker's turns, so keyword matching fails.
- The `evidence_quote` must come from a turn of the speaker who owns the statement.
- Traps: `STANCE_QUALIFIER` means the owner only partly agrees; `QUOTE_ATTRIBUTION` means a different speaker reports this view without holding it; `SOURCE_ATTRIBUTION` means another speaker says something close.

Previously used skins to avoid: $avoid
