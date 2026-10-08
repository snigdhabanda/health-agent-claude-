"""Run each question's reference_sql and write the results to answers.local.yaml for hand-checking.

    python evals/build_answers.py          # all questions
    python evals/build_answers.py q17 q19  # just these

Existing `checked: true` entries are kept unless their reference rows changed.
"""

import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from db import QueryError, get_backend  # noqa: E402

EVALS = Path(__file__).resolve().parent
QUESTIONS = EVALS / "questions.yaml"  # main set; also defines the shared ctes
LAB_QUESTIONS = EVALS / "questions_labs.yaml"
ANSWERS = EVALS / "answers.local.yaml"


def load_questions(include_labs: bool = True) -> list[dict]:
    spec = yaml.safe_load(QUESTIONS.read_text())
    ctes = {name: body.strip() for name, body in spec["ctes"].items()}
    questions = spec["questions"]
    if include_labs:
        questions += yaml.safe_load(LAB_QUESTIONS.read_text())["questions"]
    for q in questions:
        q["reference_sql"] = q["reference_sql"].format(**ctes)
    return questions


def main(only: list[str]):
    backend = get_backend()
    answers = yaml.safe_load(ANSWERS.read_text()) if ANSWERS.exists() else {}
    questions = load_questions()
    answers = {k: v for k, v in answers.items() if k in {q["id"] for q in questions}}  # drop removed questions
    failed = []
    for q in questions:
        if only and q["id"] not in only:
            continue
        try:
            columns, rows, _ = backend.run(q["reference_sql"])
        except QueryError as e:
            failed.append(q["id"])
            print(f"{q['id']}: FAILED {str(e)[:200]}")
            continue
        new = [dict(zip(columns, r)) for r in rows]
        old = answers.get(q["id"], {})
        answers[q["id"]] = {
            "question": q["question"],
            "rows": new,
            "checked": old.get("checked", False) and old.get("rows") == new,
            "expected": old.get("expected") if old.get("rows") == new else None,
        }
        print(f"{q['id']}: {len(rows)} rows")
    ANSWERS.write_text(yaml.safe_dump(answers, sort_keys=True, allow_unicode=True, width=120))
    print(f"\nwrote {ANSWERS.relative_to(ROOT)}" + (f"; failed: {failed}" if failed else ""))


if __name__ == "__main__":
    main(sys.argv[1:])
