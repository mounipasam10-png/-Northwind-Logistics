import json
import re
from openai import OpenAI
from dotenv import load_dotenv

from app.services.policy_service import search_policies

load_dotenv()
client = OpenAI()


SYSTEM_PROMPT = """
You answer questions using only the provided company policy excerpts.

Relevance:
- An excerpt is RELEVANT only if it directly addresses the question's subject. A chunk that mentions related vocabulary but does not state a rule, definition, or answer to the question is NOT relevant.
- If no provided excerpt is directly relevant, return: answer = "I cannot answer from the policy library.", confidence = 0, citations = [].

Citations:
- Citations must be exact contiguous quotes copied verbatim from the provided excerpts. Do not paraphrase or summarize.
- You may quote a cross-reference like "see TEP-003 §3.1" verbatim if it appears in an excerpt, but never invent text that summarizes what another policy says.

Confidence calibration:
- 0.9-1.0: Answer is directly stated in a relevant excerpt with no ambiguity.
- 0.6-0.8: Answer requires combining multiple excerpts, or relies on a cross-reference rather than the primary rule.
- 0.3-0.5: An excerpt is partially relevant but doesn't fully answer the question.
- 0.0: No relevant excerpt found.

Do not use outside knowledge. Return structured JSON only.
"""


QA_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "policy_answer",
        "schema": {
            "type": "object",
            "properties": {
                "answer": {"type": "string"},
                "confidence": {"type": "number"},
                "citations": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "policy_id": {"type": "string"},
                            "section": {"type": "string"},
                            "quoted_text": {"type": "string"}
                        },
                        "required": ["policy_id", "section", "quoted_text"],
                        "additionalProperties": False
                    }
                }
            },
            "required": ["answer", "confidence", "citations"],
            "additionalProperties": False
        }
    }
}


def normalize_text(text: str) -> str:
    if not text:
        return ""

    text = text.lower()
    text = text.replace("\\n", " ")
    text = text.replace("—", "-")
    text = text.replace("–", "-")
    text = text.replace("=", "-")
    text = " ".join(text.split())

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


def verify_citations(answer: dict, policies: list[dict]) -> dict:
    bad = 0

    for citation in answer.get("citations", []):
        quote = citation.get("quoted_text", "")

        found = False

        for policy in policies:
            if citation_appears_in(quote, policy["text"]):
                found = True
                break

        if not found:
            bad += 1

    if bad:
        answer["confidence"] = min(answer.get("confidence", 0.5), 0.3)
        answer["answer"] += f" Warning: {bad} citation(s) could not be verified."

    return answer


def answer_policy_question(question: str):
    policies = search_policies(question, top_k=5)

    if not policies:
        return {
            "answer": "I cannot answer this question from the current policy library.",
            "confidence": 0.0,
            "citations": []
        }

    policy_context = "\n\n".join([
        f"Policy: {p['metadata']['policy_id']} Section {p['metadata']['section']}\n{p['text']}"
        for p in policies
    ])

    prompt = f"""
Question:
{question}

Policy excerpts:
{policy_context}

Answer the question using only these excerpts.
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0,
        response_format=QA_SCHEMA,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ]
    )

    result = json.loads(response.choices[0].message.content)

    return verify_citations(result, policies)