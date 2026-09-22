# Exam design

The generator produces 30-item, B1-style Hören practice exams in four parts. It uses a code-owned blueprint before any LLM call so structural quality does not depend solely on prompting.

## Product rules

- The blueprint balances multiple-choice answers, true/false answers, distractor patterns, and speaker genders.
- The model writes only the content required to satisfy that blueprint, using a JSON schema for each part.
- Validation checks item numbering, answer ownership, verbatim audio evidence, item order, speaker distribution, TTS-safe wording, and Telegram length limits.
- Failed validation is returned to the model for bounded repair rounds. Validation results remain stored with the exam.
- `exam.json` contains the generated script, questions, answers, evidence, difficulty, and fact annotations. It is the durable source artifact.

The full prompt policy is maintained in [`../plan/hoeren-exam-ontology.md`](../plan/hoeren-exam-ontology.md).

## Why the blueprint comes first

Answer-key balance, trap coverage, and speaker assignment are deterministic constraints. Putting them behind the generator's interface produces consistent exams, prevents repeated manual review at every call site, and leaves the LLM focused on its comparative strength: natural German text.

## Quality limits

Generated material is practice content, not an official exam. A successful validation means the content satisfies this project's structural and delivery rules; it does not make a claim of official certification or psychometric calibration.
