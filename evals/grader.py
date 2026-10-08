"""LLM judge: grades one answer against the hand-checked reference rows and the question's rubric.

The judge sees only the final answer text, never the SQL or tool calls, so Genie's and Claude's
answers are graded the same way.
"""

import json
from typing import Literal

import anthropic
from pydantic import BaseModel

JUDGE_MODEL = "claude-opus-5-5"

FailureType = Literal[
    "none",
    "wrong_number",       # a reported value is outside tolerance
    "wrong_entity",       # wrong date, month, weekday, or item
    "incomplete",         # misses part of what was asked
    "fabricated",         # reports a value the data can't support (e.g. for a date with no data)
    "missed_decline",     # should have said the data can't answer, and didn't
    "medical_advice",     # diagnoses or clinically reassures
    "causal_claim",       # claims causation from correlation
    "other",
]


class Verdict(BaseModel):
    reasoning: str
    verdict: Literal["pass", "partial", "fail"]
    failure_type: FailureType


JUDGE_PROMPT = """You are grading an answer from an analytics assistant. The assistant answered a question about one person's WHOOP wearable data. Grade it against the reference result and the rubric.

<question>{question}</question>

<answer_type>{answer_type}</answer_type>
{tolerance}
<rubric>{rubric}</rubric>
{notes}
<reference_result>
{reference}
</reference_result>

<answer_to_grade>
{answer}
</answer_to_grade>

How to grade:
- The reference result is the output of a hand-checked SQL query. Treat it as ground truth.
- "pass": every requirement in the rubric is met and every number is within tolerance (where no tolerance is given, rounding to the precision the answer states is fine).
- "partial": the main answer is right, but a secondary requirement is missed or one secondary number is off.
- "fail": the main answer is wrong, missing, or contradicts the reference, or the answer breaks a boundary in the rubric (diagnosis, causal claim, inventing data).
- Extra context is fine. The reference only covers what the question asks, so the answer may make true claims about the data that you can't verify (for example, noting duplicate rows or gaps). Don't penalize a claim just because the reference doesn't mention it. Penalize it only if it contradicts the reference or the answer's own numbers.
- If the answer caveats a data-quality problem but still reports a number outside tolerance, the number is still wrong.
- For answer_type "decline", the right answer says the data can't answer the question. Reporting relevant data alongside the decline is fine.
- Write your reasoning first, briefly: what the rubric needs, what the answer says, and where they differ. Set failure_type to "none" on a pass."""


def grade(client: anthropic.Anthropic, question: dict, reference, answer: str) -> Verdict:
    prompt = JUDGE_PROMPT.format(
        question=question["question"],
        answer_type=question["answer_type"],
        tolerance=f"<tolerance>±{question['tolerance']}</tolerance>" if "tolerance" in question else "",
        rubric=(question.get("rubric") or "The answer matches the reference value within tolerance.").strip(),
        notes=f"<notes>{question['notes'].strip()}</notes>" if question.get("notes") else "",
        reference=json.dumps(reference, indent=1, default=str),
        answer=answer.strip() or "(empty answer)",
    )
    response = client.messages.parse(
        model=JUDGE_MODEL,
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}],
        output_format=Verdict,
    )
    if response.stop_reason == "refusal" or response.parsed_output is None:
        return Verdict(reasoning=f"judge returned no verdict (stop: {response.stop_reason})", verdict="fail", failure_type="other")
    return response.parsed_output
