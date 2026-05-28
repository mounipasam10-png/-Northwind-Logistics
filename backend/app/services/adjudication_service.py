import json
import re
from openai import OpenAI
from dotenv import load_dotenv

from app.services.policy_service import search_policies


load_dotenv()
client = OpenAI()


SYSTEM_PROMPT = """
You are a finance reviewer evaluating one expense receipt against company policy.

Use only the provided policy excerpts.

Rules:
- Return approved, denied, or needs_review.
- Quote policy text exactly from the excerpts.
- Do not invent citations.
- For every violation, provide receipt_value, policy_limit, comparison, and flagged_amount.
- Do not claim X exceeds Y unless X > Y.
- If math is ambiguous, return needs_review.
- List each distinct violation exactly once. Do not repeat duplicate violations.

For meals containing alcohol:
- Compute alcohol total by summing ONLY alcoholic line items: beer, wine, spirits, cocktails, hard seltzer, sake.
- The alcohol violation receipt_value must equal the alcohol total, not the receipt grand total.
- The alcohol violation flagged_amount must equal the alcohol total.
- Food portion equals grand total minus alcohol total.
- If food portion is within the meal cap, do not deny the food portion.
- If only alcohol is non-reimbursable, explain this as a partial denial: food is reimbursable, alcohol is not.
"""


VERDICT_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "expense_verdict",
        "schema": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["approved", "denied", "needs_review"]
                },
                "reasoning": {"type": "string"},
                "confidence": {"type": "number"},
                "violations": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "rule": {"type": "string"},
                            "policy_id": {"type": "string"},
                            "section": {"type": "string"},
                            "receipt_value": {"type": "number"},
                            "policy_limit": {"type": "number"},
                            "comparison": {
                                "type": "string",
                                "enum": [
                                    "greater_than",
                                    "less_than",
                                    "not_allowed"
                                ]
                            },
                            "flagged_amount": {"type": "number"}
                        },
                        "required": [
                            "rule",
                            "policy_id",
                            "section",
                            "receipt_value",
                            "policy_limit",
                            "comparison",
                            "flagged_amount"
                        ],
                        "additionalProperties": False
                    }
                },
                "citations": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "policy_id": {"type": "string"},
                            "section": {"type": "string"},
                            "quoted_text": {"type": "string"}
                        },
                        "required": [
                            "policy_id",
                            "section",
                            "quoted_text"
                        ],
                        "additionalProperties": False
                    }
                }
            },
            "required": [
                "status",
                "reasoning",
                "confidence",
                "violations",
                "citations"
            ],
            "additionalProperties": False
        }
    }
}


ALCOHOL_WORDS = [
    "beer",
    "wine",
    "cocktail",
    "vodka",
    "whiskey",
    "tequila",
    "rum",
    "gin",
    "sake",
    "hard seltzer",
    "hefeweizen",
    "fireman's",
    "red wine",
]


def build_query(receipt: dict) -> str:
    category = receipt.get("category", "expense")
    location = receipt.get("location", "")

    if category == "lodging":
        return f"lodging hotel rate cap tier city {location}"

    if category == "meal":
        if receipt.get("has_alcohol"):
            return "meal cap dinner alcohol solo travel reimbursement"
        return "meal cap breakfast lunch dinner reimbursement"

    if category == "flight":
        return "air travel flight business class approval"

    if category == "ground_transport":
        return "ground transportation taxi rideshare mileage reimbursement"

    return "expense reimbursement policy"


def normalize_text(text: str) -> str:
    if not text:
        return ""

    text = text.lower()
    text = text.replace("\\n", " ")
    text = text.replace("—", "-")
    text = text.replace("–", "-")
    text = text.replace("=", "-")
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def citation_appears_in(quote: str, chunk_text: str) -> bool:
    q = normalize_text(quote)
    c = normalize_text(chunk_text)

    if q in c:
        return True

    words = q.split()

    if len(words) < 3:
        return False

    return all(word in c for word in words)


def verify_citations(verdict: dict, policies: list[dict]) -> dict:
    bad_count = 0

    for citation in verdict.get("citations", []):
        quoted = citation.get("quoted_text", "")

        found = False

        for policy in policies:
            if citation_appears_in(quoted, policy["text"]):
                found = True
                break

        if not found:
            bad_count += 1

    if bad_count:
        verdict["confidence"] = min(
            verdict.get("confidence", 0.5),
            0.3
        )
        verdict["reasoning"] += (
            f" Warning: {bad_count} citation(s) could not be verified."
        )

    return verdict


def validate_math(verdict: dict) -> dict:
    bad = 0

    for violation in verdict.get("violations", []):
        receipt_value = float(violation.get("receipt_value", 0))
        policy_limit = float(violation.get("policy_limit", 0))
        comparison = violation.get("comparison")

        if comparison == "greater_than" and receipt_value <= policy_limit:
            bad += 1

        if comparison == "less_than" and receipt_value >= policy_limit:
            bad += 1

        if comparison == "not_allowed" and receipt_value <= 0:
            bad += 1

    if bad:
        verdict["status"] = "needs_review"
        verdict["confidence"] = min(
            verdict.get("confidence", 0.5),
            0.25
        )
        verdict["reasoning"] += (
            f" Warning: {bad} violation(s) failed deterministic math validation."
        )

    return verdict


def dedupe_violations(verdict: dict) -> dict:
    seen = set()
    unique = []

    for violation in verdict.get("violations", []):
        key = (
            violation.get("rule"),
            violation.get("policy_id"),
            violation.get("section"),
        )

        if key not in seen:
            seen.add(key)
            unique.append(violation)

    verdict["violations"] = unique

    return verdict


def compute_alcohol_total(receipt: dict) -> float:
    total = 0.0

    for item in receipt.get("line_items", []):
        description = (item.get("description") or "").lower()
        amount = float(item.get("amount") or 0)

        if any(word in description for word in ALCOHOL_WORDS):
            total += amount

    return round(total, 2)


def validate_alcohol_math(verdict: dict, receipt: dict) -> dict:
    if receipt.get("category") != "meal":
        return verdict

    alcohol_total = compute_alcohol_total(receipt)

    if alcohol_total <= 0:
        return verdict

    grand_total = float(receipt.get("amount") or 0)
    food_total = round(grand_total - alcohol_total, 2)
    verdict["status"] = "needs_review"

    for violation in verdict.get("violations", []):
        rule = (violation.get("rule") or "").lower()

        if "alcohol" in rule:
            violation["receipt_value"] = alcohol_total
            violation["policy_limit"] = 0
            violation["comparison"] = "not_allowed"
            violation["flagged_amount"] = alcohol_total

    verdict["reasoning"] += (
        f" Alcohol validation: alcoholic line items total ${alcohol_total:.2f}; "
        f"food/non-alcohol portion is ${food_total:.2f}. "
        f"Only the alcohol amount is non-reimbursable if the food portion is within policy."
    )

    return verdict


def adjudicate_receipt(
    receipt: dict,
    employee: dict = None,
    submission: dict = None
):
    query = build_query(receipt)

    policies = search_policies(query, top_k=6)

    policy_context = "\n\n".join([
        (
            f"Policy: {p['metadata']['policy_id']} "
            f"Section {p['metadata']['section']}\n"
            f"{p['text']}"
        )
        for p in policies
    ])

    prompt = f"""
Employee:
{employee}

Submission:
{submission}

Receipt:
{receipt}

Policy excerpts:
{policy_context}

Return the structured verdict.
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0,
        response_format=VERDICT_SCHEMA,
        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            },
            {
                "role": "user",
                "content": prompt
            }
        ]
    )

    verdict = json.loads(response.choices[0].message.content)

    verdict = dedupe_violations(verdict)
    verdict = validate_alcohol_math(verdict, receipt)
    verdict = verify_citations(verdict, policies)
    verdict = validate_math(verdict)

    return verdict