"""Translation and deterministic libpostal address parsing nodes."""

import json
import re
from functools import lru_cache

from deep_translator import GoogleTranslator
from langchain_google_genai import ChatGoogleGenerativeAI

try:
    from postal.parser import parse_address
except (ImportError, OSError) as error:
    parse_address = None
    POSTAL_IMPORT_ERROR = str(error)
else:
    POSTAL_IMPORT_ERROR = None

def language_translation(addr: str) -> str:
    return GoogleTranslator(source="auto", target="en").translate(addr)


LANDMARK_PATTERNS = [
    r"\bnear\b", r"\bopp\.?\b", r"\bopposite\b", r"\bbehind\b",
    r"\bnext to\b", r"\badjacent to\b", r"\bbeside\b", r"\bclose to\b",
]


def strip_landmark_prefix(address: str) -> str:
    for pattern in LANDMARK_PATTERNS:
        address = re.sub(pattern, "", address, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", address).strip(" ,")


@lru_cache
def get_llm() -> ChatGoogleGenerativeAI:
    return ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)


LIBPOSTAL_LABELS = {
    "house_number": "house_number",
    "house": "building",
    "category": "building",
    "unit": "building",
    "road": "street",
    "near": "landmark",
    "suburb": "area",
    "neighbourhood": "area",
    "city": "city",
    "city_district": "district",
    "state_district": "district",
    "state": "state",
    "postcode": "postal_code",
    "country": "country",
}
PARSED_ADDRESS_FIELDS = (
    "house_number", "building", "street", "landmark", "area", "city",
    "district", "state", "postal_code", "country",
)


def address_parsing(address: str) -> dict[str, str]:
    """Map libpostal labels to the API's stable address schema without using an LLM."""
    if parse_address is None:
        raise RuntimeError(f"libpostal is unavailable: {POSTAL_IMPORT_ERROR}")

    parsed = {field: "" for field in PARSED_ADDRESS_FIELDS}
    for value, label in parse_address(address):
        field = LIBPOSTAL_LABELS.get(label)
        if field:
            parsed[field] = ", ".join(filter(None, (parsed[field], value)))
    return parsed


def add_confidence(parsed_address: dict) -> dict:
    prompt = f"""
You are an address validation expert.

Given this parsed address:

{parsed_address}

Evaluate how complete and reliable it is.

Scoring:
- 90-100: Complete and unambiguous.
- 70-89: Mostly complete with minor missing fields.
- 50-69: Missing important fields.
- Below 50: Incomplete or ambiguous.

Return ONLY valid JSON in this format:

{{
    "confidence_score": 92,
    "reason": "House number, road, city, state, postcode and country are present."
}}
"""

    response = get_llm().invoke(prompt)
    content = response.content if isinstance(response.content, str) else str(response.content)
    match = re.search(r"\{.*\}", content, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    required_fields = ("house_number", "street", "city", "state", "postal_code", "country")
    present_count = sum(1 for field in required_fields if parsed_address.get(field))
    confidence_score = max(0, min(100, 35 + present_count * 11))
    reason = f"Model returned non-JSON output; heuristic score based on {present_count} key fields being present."
    return {"confidence_score": confidence_score, "reason": reason}

