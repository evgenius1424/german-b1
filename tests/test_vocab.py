"""Vocabulary post: selection, history, validation, rendering, publishing. LLM is mocked."""

import json

import pytest

from hoeren import llm, publish, telegram, vocab, vocab_post, vocab_rank
from hoeren.spec import TG_MESSAGE
from hoeren.telegram import visible_len

TURNS = [
    "Guten Abend, ich bin Petra Lindner. Ich erkläre Ihnen, wie alles abläuft.",
    "Jeder macht zwei Schichten. Die Kleidung dürfen Sie danach behalten.",
    "Ihre Taschen können Sie nicht im Rathaus lassen, denn dort ist abends abgeschlossen. "
    "Dafür gibt es das Helferzelt.",
    "Um 14 Uhr beginnt aber pünktlich die Arbeit.",
    "Parken geht in diesem Jahr nicht mehr. Deshalb bekommen Sie eine Fahrkarte. "
    "Sie gilt für alle drei Festtage.",
    "Der Kurs beginnt nicht am Montag, sondern erst am Mittwoch. Die Führung findet morgen statt.",
    "Bitte geben Sie den Schlüssel <hier> & dort ab.",
]


def make_exam(turns=TURNS):
    unit = {
        "speakers": [{"id": "S1", "name": "Petra Lindner"}],
        "turns": [{"speaker": "S1", "text": t} for t in turns],
        "questions": [{"type": "true_false", "number": 1, "prompt": "?", "options": [],
                       "answer": "falsch", "evidence_quote": "Parken geht in diesem Jahr nicht mehr."}],
        "title": None,
    }
    return {"id": "2026-01-01-000001", "parts": {"2": {"part": 2, "units": [unit]}}}


def item(expression, surface, category="concept", english=None, **scores):
    base = dict(answer_relevance=7, cross_scenario=7, b1_likelihood=7,
                learner_confusion=7, context_clarity=7)
    return {"expression": expression, "surface": surface, "english": english or f"gloss {expression}",
            "category": category, "example": "", "trap_note": ""} | base | scores


@pytest.fixture
def exam():
    return make_exam()


# --- validation -------------------------------------------------------------

@pytest.mark.parametrize("expression,surface", [
    ("ablaufen", ["abläuft"]),             # separable verb, subordinate clause
    ("gelten", ["gilt"]),                  # ablaut
    ("abschließen", ["abgeschlossen"]),    # participle
    ("nicht mehr", ["nicht mehr"]),        # multiword unit
    ("nicht … sondern", ["nicht", "sondern"]),
    ("stattfinden", ["findet", "statt"]),  # split separable verb
    ("Schicht", ["Schichten"]),            # plural
    ("pünktlich", ["pünktlich"]),
])
def test_accepts_transcript_forms(exam, expression, surface):
    assert vocab_rank.check(item(expression, surface), vocab_rank.transcript_turns(exam),
                            vocab_rank.names(exam)) is None


@pytest.mark.parametrize("expression,surface,reason", [
    ("verschieben", ["verschoben"], "not found in transcript"),
    ("absagen", ["gilt"], "does not match"),
    ("Lindner", ["Lindner"], "proper name"),
    ("Mittwoch", ["Mittwoch"], "proper name"),
    ("14 Uhr", ["14 Uhr"], "number"),
    ("gut", ["gut"], "basic"),
    ("dann", ["dann"], "basic"),
    ("doch", ["dich"], "not found"),
    ("", ["x"], "empty"),
    ("sondern", [], "no transcript form"),
])
def test_rejects_bad_items(exam, expression, surface, reason):
    got = vocab_rank.check(item(expression, surface), vocab_rank.transcript_turns(exam),
                           vocab_rank.names(exam))
    assert got and reason in got


def test_fragments_must_be_in_order(exam):
    turns = vocab_rank.transcript_turns(exam)
    assert vocab_rank.check(item("sondern … nicht", ["sondern", "nicht"]), turns, set()) \
        == "not found in transcript"


def test_unknown_category_rejected(exam):
    got = vocab_rank.check(item("deshalb", ["Deshalb"], category="misc"),
                           vocab_rank.transcript_turns(exam), set())
    assert "category" in got


# --- ranking, dedup, history ------------------------------------------------

def test_score_weights_bonus_and_repeat_penalty(exam):
    quotes = vocab_rank.evidence(exam)
    top = item("deshalb", ["Deshalb"], answer_relevance=10, cross_scenario=0, b1_likelihood=0,
               learner_confusion=0, context_clarity=0)
    assert vocab_rank.score(top, [], set()) == 3.5
    linked = item("nicht mehr", ["nicht mehr"])
    assert vocab_rank.score(linked, quotes, set()) == 7.5
    assert vocab_rank.score(linked, quotes, {vocab_rank.key("nicht mehr")}) == 6.75


def test_answer_relevance_outranks_clarity(exam):
    a = item("deshalb", ["Deshalb"], answer_relevance=10, context_clarity=0)
    b = item("behalten", ["behalten"], answer_relevance=0, context_clarity=10)
    items, _, _ = vocab_rank.select([b, a], exam)
    assert [i["expression"] for i in items] == ["deshalb", "behalten"]


def test_dedup_by_key_and_gloss(exam):
    cands = [item("gelten", ["gilt"], english="to be valid", answer_relevance=9),
             item("gilt", ["gilt"], english="valid"),                 # same lemma key
             item("behalten", ["behalten"], english="To be valid!")]  # same job
    items, _, rejected = vocab_rank.select(cands, exam)
    assert [i["expression"] for i in items] == ["gelten"]
    assert [r["reason"] for r in rejected] == ["duplicate or synonym"] * 2


def test_history_key_is_inflection_tolerant():
    assert vocab_rank.key("Gelten") == vocab_rank.key("gelten")
    assert vocab_rank.key("nicht … sondern") == vocab_rank.key("nicht ... sondern")


def test_history_penalty_prefers_new_words(exam):
    old = item("deshalb", ["Deshalb"], category="cause", answer_relevance=8)
    new = item("behalten", ["behalten"], category="instruction")
    items, _, _ = vocab_rank.select([old, new], exam, {vocab_rank.key("deshalb")}, count=1)
    assert [i["expression"] for i in items] == ["behalten"]
    exceptional = item("deshalb", ["Deshalb"], category="cause", answer_relevance=10,
                       cross_scenario=10, b1_likelihood=10)
    items, _, _ = vocab_rank.select([exceptional, new], exam, {vocab_rank.key("deshalb")}, count=1)
    assert items[0]["expression"] == "deshalb" and items[0]["repeat"]


def test_category_diversity(exam):
    contrast = [item(e, s, category="contrast", answer_relevance=10, english=e) for e, s in [
        ("nicht … sondern", ["nicht", "sondern"]), ("dafür", ["Dafür"]),
        ("nicht mehr", ["nicht mehr"]), ("deshalb", ["Deshalb"])]]
    other = item("behalten", ["behalten"], category="instruction", answer_relevance=5)
    items, _, rejected = vocab_rank.select(contrast + [other], exam, count=4)
    cats = [i["category"] for i in items]
    assert "instruction" in cats and cats.count("contrast") == 2  # cap = ceil(4/4) → 2
    assert sum(r["reason"] == "ranked out" for r in rejected) == 2


def test_never_pads(exam):
    items, _, _ = vocab_rank.select([item("behalten", ["behalten"])], exam, count=15)
    assert len(items) == 1


def test_trap_requires_verbatim_example(exam):
    good = item("erst", ["erst"], category="time", answer_relevance=9,
                example="Der Kurs beginnt nicht am Montag, sondern erst am Mittwoch.",
                trap_note="Here, erst means not until Wednesday.")
    made_up = item("pünktlich", ["pünktlich"], answer_relevance=10,
                   example="Die Arbeit beginnt pünktlich um neun.", trap_note="x")
    items, trap, _ = vocab_rank.select([made_up, good], exam)
    assert len(items) == 2
    assert trap["expression"] == "erst"


# --- rendering ---------------------------------------------------------------

def test_render_format_and_escaping(exam):
    items, trap, _ = vocab_rank.select([
        item("abgeben", ["geben", "ab"], category="instruction", english="hand in <&> leave",
             answer_relevance=9, example="Bitte geben Sie den Schlüssel <hier> & dort ab.",
             trap_note="ab at the end <changes> the verb."),
        item("deshalb", ["Deshalb"], category="cause", english="that's why"),
    ], exam)
    text = vocab_post.render({"items": items, "trap": trap})
    assert text.startswith("🎧 <b>B1 Hören | Words Worth Knowing</b>\n2 high-value expressions")
    assert "1. <b>deshalb</b>" in text  # categories in spec order, not by score
    assert "2. <b>abgeben</b> — hand in &lt;&amp;&gt; leave" in text
    assert "<b>📋 Rules &amp; instructions</b>" in text
    assert "„Bitte <b>geben</b> Sie den Schlüssel &lt;hier&gt; &amp; dort <b>ab</b>.“" in text
    assert "ab at the end &lt;changes&gt; the verb." in text
    assert text.endswith("Recognize the signal. Find the answer.")
    assert text.count("💡") == 1


def test_render_single_category_has_no_header(exam):
    items, _, _ = vocab_rank.select([item("behalten", ["behalten"])], exam)
    text = vocab_post.render({"items": items, "trap": None})
    assert "1 high-value expression from" in text and "🎯" not in text


def test_render_fits_telegram_limit():
    long = [{"expression": f"wort{i}", "english": "x" * 50, "category": "concept", "score": 20 - i}
            for i in range(200)]
    trap = {"quote": "a", "surface": ["a"], "note": "n"}
    text = vocab_post.render({"items": long, "trap": trap})
    assert visible_len(text) <= TG_MESSAGE
    assert "wort0" in text and "Listening trap" not in text


def test_render_rejects_empty():
    with pytest.raises(ValueError):
        vocab_post.render({"items": [], "trap": None})


# --- generate(): LLM mocked ----------------------------------------------------

@pytest.fixture
def workdir(tmp_path, exam):
    d = tmp_path / exam["id"]
    d.mkdir()
    return d


def run(monkeypatch, workdir, exam, result, count=15):
    def fake(system, prompt, schema, model=None, effort=None):
        fake.prompt = prompt
        if isinstance(result, Exception):
            raise result
        return result, 0.01
    monkeypatch.setattr(llm, "complete_json", fake)
    hist = workdir.parent / "vocab-history.json"
    out = vocab.generate(exam, workdir, count, history_path=hist, log=lambda m: None)
    return out, fake, hist


def test_generate_writes_vocab_and_history(monkeypatch, workdir, exam):
    out, fake, hist = run(monkeypatch, workdir, exam, {"items": [
        item("gelten", ["gilt"]), item("Lindner", ["Lindner"]), item("behalten", ["behalten"])]})
    assert [i["expression"] for i in out["items"]] == ["gelten", "behalten"]
    assert json.loads((workdir / "vocab.json").read_text())["rejected"][0]["reason"] == "proper name or date"
    entries = json.loads(hist.read_text())["exams"][exam["id"]]
    assert [e["expression"] for e in entries] == ["gelten", "behalten"]
    assert "Petra Lindner: Guten Abend" in fake.prompt and "evidence:" in fake.prompt


def test_generate_feeds_and_penalises_history(monkeypatch, workdir, exam):
    hist = workdir.parent / "vocab-history.json"
    hist.write_text(json.dumps({"exams": {"2025-12-31-000000": [
        {"expression": "gelten", "key": vocab_rank.key("gelten")}]}}))
    out, fake, _ = run(monkeypatch, workdir, exam, {"items": [item("gelten", ["gilt"])]})
    assert "Previously published expressions: gelten" in fake.prompt
    assert out["items"][0]["repeat"]


def test_regenerate_replaces_own_history(monkeypatch, workdir, exam):
    run(monkeypatch, workdir, exam, {"items": [item("gelten", ["gilt"])]})
    out, fake, hist = run(monkeypatch, workdir, exam, {"items": [item("gelten", ["gilt"])]})
    assert "Previously published expressions: none" in fake.prompt
    assert not out["items"][0]["repeat"]
    assert len(json.loads(hist.read_text())["exams"]) == 1


@pytest.mark.parametrize("result,message", [
    (llm.LLMError("claude exited 1"), "extraction failed"),
    ({"items": []}, "no vocabulary candidates"),
    ({"items": [item("Lindner", ["Lindner"]), item("verschieben", ["verschoben"])]}, "no usable"),
])
def test_generate_failures_leave_files_untouched(monkeypatch, workdir, exam, result, message):
    with pytest.raises(vocab.VocabError, match=message):
        run(monkeypatch, workdir, exam, result)
    assert not (workdir / "vocab.json").exists()
    assert not (workdir.parent / "vocab-history.json").exists()


def test_generate_rejects_bad_count(workdir, exam):
    with pytest.raises(vocab.VocabError):
        vocab.generate(exam, workdir, 21)


# --- manifest and publishing ---------------------------------------------------

def teil_posts():
    return [{"id": f"teil{n}", "method": "sendMessage", "params": {"text": "x"}, "comments": []}
            for n in range(1, 5)]


def vocab_message(text="hi"):
    return {"id": "vocab", "method": "sendMessage", "params": {"text": text, "parse_mode": "HTML"}}


def test_manifest_with_and_without_vocab(tmp_path):
    assert publish.validate_manifest({"posts": teil_posts()}, tmp_path)["vocab"] == 0
    counts = publish.validate_manifest({"posts": teil_posts() + [vocab_message()]}, tmp_path)
    assert counts["posts"] == 5 and counts["vocab"] == 1


@pytest.mark.parametrize("posts", [
    teil_posts()[:3],
    teil_posts() + [vocab_message("x" * (TG_MESSAGE + 1))],
    teil_posts() + [vocab_message() | {"comments": [{"text": "c"}]}],
    [vocab_message()] + teil_posts(),
])
def test_manifest_rejects_bad_layouts(tmp_path, posts):
    with pytest.raises(publish.PublishError):
        publish.validate_manifest({"posts": posts}, tmp_path)


def test_build_appends_vocab_post(monkeypatch, workdir, exam):
    monkeypatch.setattr(telegram, "_audio_post", lambda part, d: {"id": f"teil{part['part']}"})
    assert [p["id"] for p in telegram.build(exam, workdir)["posts"]] == ["teil2"]
    run(monkeypatch, workdir, exam, {"items": [item("gelten", ["gilt"])]})
    posts = telegram.build(exam, workdir)["posts"]
    assert [p["id"] for p in posts] == ["teil2", "vocab"]
    assert posts[1]["method"] == "sendMessage" and "comments" not in posts[1]
    assert [p["id"] for p in telegram.build(exam, workdir, with_vocab=False)["posts"]] == ["teil2"]


def test_publisher_sends_vocab_last_and_resumes(tmp_path):
    manifest = {"exam_id": "e", "posts": teil_posts() + [vocab_message()]}
    for p in manifest["posts"][:4]:
        p["comments"] = [{"text": "key"}]
    state = {"exam_id": "e", "chat_id": "@c", "posts": {
        f"teil{n}": {"channel_message_ids": [n], "forwarded": {"chat_id": -1, "message_id": n},
                     "comment_message_ids": [100 + n]} for n in range(1, 5)}}
    pub = publish.Publisher(tmp_path, manifest, "t", "@c", state)
    sent = []

    def request(method, params=None, files=None):
        if method == "sendMessage":
            sent.append((method, params["text"]))
        return {"message_id": 99}
    pub._request = request
    pub._pin_first = lambda: None
    pub._webhook_guard = lambda: None
    pub._find_forward = lambda mid: (_ for _ in ()).throw(publish.PublishError("no forward"))
    pub.publish()
    pub.close()
    assert sent == [("sendMessage", "hi")]
    saved = json.loads((tmp_path / "published.json").read_text())["posts"]["vocab"]
    assert saved == {"channel_message_ids": [99], "forwarded": None}
    sent.clear()
    pub.publish()  # resumed: nothing re-sent, no second forward wait
    assert sent == []


def test_pins_teil1_once_and_deletes_notice(tmp_path):
    state = {"exam_id": "e", "chat_id": "@c", "posts": {"teil1": {"channel_message_ids": [7, 8]}}}
    pub = publish.Publisher(tmp_path, {"exam_id": "e", "posts": []}, "t", "@c", state)
    calls = []

    def request(method, params=None, files=None):
        calls.append((method, params))
        if method == "getUpdates":
            return [{"update_id": 5, "channel_post": {"message_id": 9, "chat": {"id": -100},
                                                      "pinned_message": {"message_id": 7}}}]
        return True
    pub._request = request
    pub._pin_first()
    assert [c[0] for c in calls] == ["pinChatMessage", "getUpdates", "deleteMessage"]
    assert calls[0][1]["message_id"] == 7 and calls[0][1]["disable_notification"]
    assert calls[2][1] == {"chat_id": -100, "message_id": 9}
    assert json.loads((tmp_path / "published.json").read_text())["posts"]["teil1"]["pinned"]
    calls.clear()
    pub._pin_first()
    pub.close()
    assert calls == []


def test_pin_failure_only_warns(tmp_path, capsys):
    state = {"exam_id": "e", "chat_id": "@c", "posts": {"teil1": {"channel_message_ids": [7]}}}
    pub = publish.Publisher(tmp_path, {"exam_id": "e", "posts": []}, "t", "@c", state)
    pub._request = lambda *a, **k: (_ for _ in ()).throw(publish.PublishError("no rights"))
    pub._pin_first()
    pub.close()
    assert "could not pin" in capsys.readouterr().out
    assert "pinned" not in state["posts"]["teil1"]
