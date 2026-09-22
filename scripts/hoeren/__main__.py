"""Generate Goethe B1 Hören practice exams: text → audio → Telegram manifest."""

import argparse
import datetime
import hashlib
import json
import random
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import audio, blueprint, publish, telegram
from .generate import generate_part, stderr_log
from .spec import EXAMS, ONTOLOGY
from .validate import check_part


def exam_dir(ref):
    path = Path(ref)
    if not path.is_dir():
        path = EXAMS / ref
    if not (path / "exam.json").exists():
        sys.exit(f"no exam at {path}")
    return path


def load(path):
    return json.loads((path / "exam.json").read_text())


def save(path, exam):
    (path / "exam.json").write_text(json.dumps(exam, ensure_ascii=False, indent=2) + "\n")


def parse_parts(spec):
    return sorted({int(p) for p in spec.split(",")}) if spec else [1, 2, 3, 4]


def summary(exam):
    errors = 0
    for key, part in sorted(exam["parts"].items()):
        v = part["validation"]
        errors += len(v["errors"])
        print(f"Teil {key}: {len(v['errors'])} errors, {len(v['warnings'])} warnings", file=sys.stderr)
    return errors


def generate(exam, path, parts, args):
    def one(n):
        return n, generate_part(n, exam["blueprint"], args.model, args.effort, args.retries, stderr_log)

    with ThreadPoolExecutor(len(parts)) as pool:
        for n, part in pool.map(one, parts):
            exam["parts"][str(n)] = part
    exam["parts"] = dict(sorted(exam["parts"].items()))
    save(path, exam)


def cmd_new(args):
    seed = args.seed if args.seed is not None else random.randrange(10**6)
    exam_id = f"{datetime.date.today()}-{seed:06d}"
    path = EXAMS / exam_id
    path.mkdir(parents=True, exist_ok=True)
    exam = {
        "id": exam_id,
        "created": datetime.datetime.now().isoformat(timespec="seconds"),
        "origin": "generated",
        "ontology_sha256": hashlib.sha256(ONTOLOGY.read_bytes()).hexdigest()[:12],
        "model": args.model or "default",
        "blueprint": blueprint.make(seed),
        "parts": {},
    }
    save(path, exam)
    generate(exam, path, [1, 2, 3, 4], args)
    index = EXAMS / "index.md"
    if not index.exists():
        index.write_text("# Generated Hören exams\n\n")
    with index.open("a") as f:
        f.write(f"- {datetime.date.today()} `{exam_id}` — origin: generated\n")
    errors = summary(exam)
    if not args.no_audio:
        audio.render(exam, path)
        write_telegram(exam, path)
    print(path)
    if errors:
        sys.exit(f"validation errors remain; fix with: scripts/exam regen {exam_id} --parts <n>")


def cmd_regen(args):
    path = exam_dir(args.exam)
    exam = load(path)
    parts = parse_parts(args.parts)
    if args.reroll:
        fresh = blueprint.make(random.randrange(10**6))
        for n in parts:
            exam["blueprint"][str(n)] = fresh[str(n)]
    generate(exam, path, parts, args)
    for n in parts:
        for unit in exam["parts"][str(n)]["units"]:
            audio.unit_path(path, unit).unlink(missing_ok=True)
    summary(exam)


def cmd_validate(args):
    path = exam_dir(args.exam)
    exam = load(path)
    for key, part in exam["parts"].items():
        errors, warnings = check_part(part, exam["blueprint"])
        part["validation"] = {"errors": errors, "warnings": warnings}
    save(path, exam)
    errors = summary(exam)
    if args.details:
        for key, part in exam["parts"].items():
            for e in part["validation"]["errors"]:
                print(f"error   Teil {key}: {e}")
            for w in part["validation"]["warnings"]:
                print(f"warning Teil {key}: {w}")
    sys.exit(1 if errors else 0)


def cmd_audio(args):
    path = exam_dir(args.exam)
    exam = load(path)
    audio.render(exam, path, parse_parts(args.parts) if args.parts else None, args.force,
                 args.speed, args.temperature)
    write_telegram(exam, path)


def write_telegram(exam, path):
    manifest = telegram.build(exam, path)
    missing = []
    for post in manifest["posts"]:
        files = []
        if "files" in post:
            files.append(post["files"]["audio"])
        files.extend(item["file"] for item in post.get("media", []))
        missing.extend(rel for rel in files if not (path / rel).exists())
    (path / "telegram.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    print(f"{path / 'telegram.json'}: {len(manifest['posts'])} posts"
          + (f", {len(missing)} audio files missing" if missing else ""), file=sys.stderr)


def cmd_telegram(args):
    path = exam_dir(args.exam)
    write_telegram(load(path), path)


def cmd_publish(args):
    path = exam_dir(args.exam)
    publish.publish(path, args.chat, args.dry_run)


def cmd_list(args):
    for path in sorted(EXAMS.glob("*/exam.json")):
        exam = json.loads(path.read_text())
        errors = sum(len(p["validation"]["errors"]) for p in exam["parts"].values())
        n_audio = len(list((path.parent / "audio").glob("*.mp3")))
        tg = (path.parent / "telegram.json").exists()
        print(f"{exam['id']}  parts={len(exam['parts'])}/4  errors={errors}  "
              f"audio={n_audio}/8  telegram={'yes' if tg else 'no'}")


def main():
    ap = argparse.ArgumentParser(prog="scripts/exam", description=__doc__)
    sub = ap.add_subparsers(required=True)

    def llm_opts(p):
        p.add_argument("--model", help="Claude model alias or id (default: CLI default)")
        p.add_argument("--effort", choices=["low", "medium", "high", "xhigh", "max"])
        p.add_argument("--retries", type=int, default=2, help="repair rounds per part")

    p = sub.add_parser("new", help="blueprint → text → validate → audio → telegram.json")
    p.add_argument("--seed", type=int)
    p.add_argument("--no-audio", action="store_true", help="stop after text generation")
    llm_opts(p)
    p.set_defaults(func=cmd_new)

    p = sub.add_parser("regen", help="regenerate some parts of an exam")
    p.add_argument("exam")
    p.add_argument("--parts", required=True, help="e.g. 3 or 1,4")
    p.add_argument("--reroll", action="store_true", help="also draw a new blueprint for these parts")
    llm_opts(p)
    p.set_defaults(func=cmd_regen)

    p = sub.add_parser("validate", help="re-run checks (after hand edits of exam.json)")
    p.add_argument("exam")
    p.add_argument("--details", action="store_true", help="print messages (may reveal content)")
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("audio", help="render missing audio, then rebuild telegram.json")
    p.add_argument("exam")
    p.add_argument("--parts")
    p.add_argument("--force", action="store_true", help="re-render existing files")
    p.add_argument("--speed", type=float, default=1.0)
    p.add_argument("--temperature", type=float, default=0.6)
    p.set_defaults(func=cmd_audio)

    p = sub.add_parser("telegram", help="rebuild telegram.json")
    p.add_argument("exam")
    p.set_defaults(func=cmd_telegram)

    p = sub.add_parser("publish", help="publish an exam to Telegram")
    p.add_argument("exam")
    p.add_argument("--chat", help="channel username or chat id (default: @german_b1_horen)")
    p.add_argument("--dry-run", action="store_true", help="validate and print counts without sending")
    p.set_defaults(func=cmd_publish)

    p = sub.add_parser("list", help="list generated exams")
    p.set_defaults(func=cmd_list)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
