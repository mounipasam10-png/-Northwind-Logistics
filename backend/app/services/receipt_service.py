import base64
import json
from pathlib import Path

import fitz
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI()

SYSTEM_PROMPT = """You extract structured data from expense receipts.

Rules:
- date: ISO format YYYY-MM-DD. Use the service date: meal date, flight date, or check-out date for hotels.
- amount: final amount charged to the card, including tax and tip.
- subtotal, tax, tip: extract if present. Set null if not shown.
- category: choose exactly one of meal, lodging, flight, ground_transport, other.
- location: city and state/country if visible.
- card_last_four: last 4 digits of payment card if shown.
- has_alcohol: true only for beer, wine, spirits, cocktails, hard seltzer, or sake.
- Sparkling water, still water, and “no alc.” items are not alcohol.
- line_items: include itemized receipt lines where visible.
- confidence: 1.0 if all important fields are clear; below 0.6 means reviewer should double-check.

Return only the structured JSON object.
"""

RECEIPT_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "receipt_extraction",
        "schema": {
            "type": "object",
            "properties": {
                "merchant": {"type": ["string", "null"]},
                "date": {"type": ["string", "null"]},
                "amount": {"type": ["number", "null"]},
                "subtotal": {"type": ["number", "null"]},
                "tax": {"type": ["number", "null"]},
                "tip": {"type": ["number", "null"]},
                "currency": {"type": "string"},
                "category": {
                    "type": "string",
                    "enum": ["meal", "lodging", "flight", "ground_transport", "other"]
                },
                "description": {"type": "string"},
                "location": {"type": ["string", "null"]},
                "card_last_four": {"type": ["string", "null"]},
                "has_alcohol": {"type": "boolean"},
                "line_items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "description": {"type": "string"},
                            "amount": {"type": ["number", "null"]}
                        },
                        "required": ["description", "amount"],
                        "additionalProperties": False
                    }
                },
                "confidence": {"type": "number"}
            },
            "required": [
                "merchant", "date", "amount", "subtotal", "tax", "tip",
                "currency", "category", "description", "location",
                "card_last_four", "has_alcohol", "line_items", "confidence"
            ],
            "additionalProperties": False
        }
    }
}


def fallback_result(message: str):
    return {
        "merchant": None,
        "date": None,
        "amount": None,
        "subtotal": None,
        "tax": None,
        "tip": None,
        "currency": "USD",
        "category": "other",
        "description": message,
        "location": None,
        "card_last_four": None,
        "has_alcohol": False,
        "line_items": [],
        "confidence": 0.0
    }


def extract_text_from_pdf(file_path: str) -> str:
    text = ""
    doc = fitz.open(file_path)

    for page in doc:
        text += page.get_text() + "\n"

    return text.strip()


def extract_text_from_txt(file_path: str) -> str:
    return Path(file_path).read_text(encoding="utf-8").strip()


def extract_receipt_text(file_path: str) -> str:
    suffix = Path(file_path).suffix.lower()

    if suffix == ".pdf":
        return extract_text_from_pdf(file_path)

    if suffix == ".txt":
        return extract_text_from_txt(file_path)

    if suffix in [".jpg", ".jpeg", ".png"]:
        return ""

    return ""


def encode_image(file_path: str):
    image_bytes = Path(file_path).read_bytes()
    return base64.b64encode(image_bytes).decode("utf-8")


def parse_receipt_from_text(raw_text: str):
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0,
            response_format=RECEIPT_SCHEMA,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"Extract receipt fields from this text:\n\n{raw_text}"
                }
            ]
        )

        return json.loads(response.choices[0].message.content)

    except Exception as e:
        return fallback_result(f"Text extraction failed: {type(e).__name__}")


def parse_receipt_from_image(file_path: str):
    try:
        suffix = Path(file_path).suffix.lower().replace(".", "")
        image_base64 = encode_image(file_path)

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0,
            response_format=RECEIPT_SCHEMA,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Extract receipt fields from this receipt image."
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/{suffix};base64,{image_base64}"
                            }
                        }
                    ]
                }
            ]
        )

        return json.loads(response.choices[0].message.content)

    except Exception as e:
        return fallback_result(f"Image extraction failed: {type(e).__name__}")


def parse_receipt_with_llm(raw_text: str, file_path: str = None):
    suffix = Path(file_path).suffix.lower() if file_path else ""

    if suffix in [".jpg", ".jpeg", ".png"]:
        return parse_receipt_from_image(file_path)

    if not raw_text:
        return fallback_result("No receipt text extracted")

    return parse_receipt_from_text(raw_text)