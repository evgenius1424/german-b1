# Goethe B1 Hören Teil 2: realism benchmark

## Question

Does the generated Hören Teil 2 pack in more traps than an official Goethe task, and how should the prompt be calibrated?

## Scope and sources

This is a small-sample comparison, not a frequency claim about all live exams. It uses the two public adult sets that Goethe makes available:

- [B1 Modellsatz Erwachsene](https://www.goethe.de/pro/relaunch/prf/materialien/B1/b1_modellsatz_erwachsene.pdf)
- [B1 Übungssatz Erwachsene](https://www.goethe.de/pro/relaunch/prf/materialien/B1/B1_Uebungssatz_Erwachsene.pdf)
- [Goethe B1 practice-material page](https://www.goethe.de/ins/de/de/prf/prf/gzb1/ueb.html), which publishes both PDFs and their Hören media

Local copies under `materials/private/` were used for measurement only. No official passage is reproduced here.

The project comparison point is `scripts/hoeren/prompts/teil2.md` and Teil 2 of `exams/2026-09-21-264053/exam.json`.

## Measured structure

| Sample | Script words | Items | Script words per item | Broad shape |
| --- | ---: | ---: | ---: | --- |
| Official Modellsatz | about 396 | 5 | about 79 | museum-tour monologue |
| Official Übungssatz | about 413 | 5 | about 83 | organised sport-programme briefing |
| Current generated sample | 472 | 5 | about 94 | first-day workplace briefing |
| Current prompt | 450–600 required | 5 | 90–120 | 6–9 same-speaker turns |

Counts cover the spoken task text, excluding the recorded instructions and situation line. PDF line-break hyphenation makes the official counts approximate by a few words.

The generated sample is therefore about 14% longer than the official Übungssatz and 19% longer than the official Modellsatz. The prompt can require a text as much as roughly 45–50% longer than either public adult example.

## Distractor and evidence patterns

The concern is partly valid, but the distinction is important.

The official Modellsatz is itself quite distractor-dense. For each of its five items, the script places the correct fact near related facts that support the wrong choices. Its mechanisms include current versus usual or past state, main versus optional activity, adjacent locations, topic versus background associations, and recommendation among nearby alternatives. In abstract terms, it often does make all three options audible.

The official Übungssatz is more varied. Some items again use three nearby facts of one class, but others use a compact near-miss: optional versus required, an activity versus a related commercial visit, a performance versus a party, or a certificate whose condition makes an over-broad option false. Not every wrong option needs its own equally explicit fact.

Across both official sets:

- the five questions follow the order of the monologue;
- each question has one compact evidence area;
- one main distinction normally decides an item;
- normal explanatory and connective prose remains between tested facts;
- distractors are plausible, but the exact construction varies between items.

The generated sample is structurally close to the official material. Its evidence also appears in five ordered blocks, and its traps—today versus later, normal time versus first-week time, usual versus introductory price, old versus current location, bicycle versus car parking—are all Goethe-like.

What feels synthetic is the regularity. All five generated blocks deliberately enumerate three option-bearing facts, and every explanation resolves the same tidy three-way contrast. The current prompt mandates this with:

- two or three competing facts in every block; and
- all three options occurring in the audio for every item.

That rule captures the densest official pattern and turns it into a universal one. The ontology itself correctly warns that two public sets do not justify frequency claims, so a mandatory 5/5 pattern is stronger than the evidence supports.

## Suggested prompt direction (idea only)

For a default **exam-realistic mode**:

1. Reduce the target to roughly **380–450 words**. This brackets both adult public examples while leaving room for natural TTS pacing and an original scenario.
2. Preserve five ordered information blocks and one compact evidence locus per item.
3. Require **one decisive contrast per item**, not a high density of contrast cues throughout the block.
4. Vary distractor realisation:
   - in perhaps two or three items, all three options may be explicitly mentioned;
   - in the remaining items, mention the correct answer and only one nearby distractor, while the other wrong option is a plausible unsupported inference or a one-slot near-miss.
5. Require some neutral connective or contextual prose so the monologue sounds like a real briefing, not five consecutive puzzle constructions.
6. Avoid stacking several of `aber`, `früher`, `jetzt`, `normalerweise`, `nur`, conditions, exceptions, and competing numbers inside every tested block.
7. Keep short, parallel options and chronological question order; both are well supported by the official sets.

For preparation, the existing dense behaviour remains useful as an explicit **challenge mode**. That mode can retain 450–600 words and require all options to occur, but it should not define the only generated style.

## Bottom line

The current sample is not wildly unlike Goethe: its individual traps are realistic and the official Modellsatz can be similarly dense. The main calibration problems are the longer mandatory length and the lack of variation—the prompt forces the hardest, most engineered official pattern into every item. A shorter default with mixed distractor construction should feel more like an exam while preserving a separate dense mode for training.
