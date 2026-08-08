"""Translation and deterministic libpostal address parsing nodes."""

import json
import re
from functools import lru_cache
import csv
from pathlib import Path

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
    return ChatGoogleGenerativeAI(model="gemini-3.5-flash", temperature=0)


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

def _extract_text(response) -> str:
    content = response.content
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
            elif isinstance(block, str):
                parts.append(block)
        return "\n".join(parts)
    return str(content)


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
    content = _extract_text(response)
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


PINCODE_DATA_PATH = Path(__file__).parent / "india_data.csv"
print(PINCODE_DATA_PATH)

@lru_cache
def _load_pincode_index() -> dict[str, list[dict[str, str]]]:
    """Load india_data.csv once and index rows by pincode for O(1) lookups."""
    index: dict[str, list[dict[str, str]]] = {}
    if not PINCODE_DATA_PATH.exists():
        print("not exists")
        return index
    with PINCODE_DATA_PATH.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            pincode = (row.get("pincode") or "").strip()
            if pincode:
                index.setdefault(pincode, []).append(row)
    return index


def _normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def _location_matches(candidate: str, records: list[dict[str, str]], fields: tuple[str, ...]) -> bool:
    normalized_candidate = _normalize(candidate)
    if not normalized_candidate:
        return False
    for record in records:
        for field in fields:
            record_value = _normalize(record.get(field, ""))
            if record_value and (record_value in normalized_candidate or normalized_candidate in record_value):
                return True
    return False


def validate_pincode(parsed_address: dict[str, str], provided_pincode: str = "") -> dict:
    """Cross-check the parsed/provided pincode against the India post office dataset.

    Confirms the pincode actually exists and that the parsed city/district and
    state are consistent with what that pincode maps to.
    """
    pincode = (parsed_address.get("postal_code") or provided_pincode or "").strip()
    if not pincode:
        return {
            "pincode_valid": False,
            "pincode_city_match": False,
            "pincode_state_match": False,
            "pincode_match_reason": "No pincode was found in the parsed address or the provided details.",
        }
    print(pincode)
    records = _load_pincode_index().get(pincode)
    if not records:
        return {
            "pincode_valid": False,
            "pincode_city_match": False,
            "pincode_state_match": False,
            "pincode_match_reason": f"Pincode {pincode} was not found in the postal directory dataset.",
        }

    city_candidate = parsed_address.get("city") or parsed_address.get("area") or parsed_address.get("district") or ""
    state_candidate = parsed_address.get("state") or ""

    city_match = _location_matches(city_candidate, records, ("officename", "district", "divisionname"))
    state_match = _location_matches(state_candidate, records, ("statename",))

    known_districts = ", ".join(sorted({r.get("district", "") for r in records if r.get("district")}))
    known_states = ", ".join(sorted({r.get("statename", "") for r in records if r.get("statename")}))

    if city_match and state_match:
        reason = f"Pincode {pincode} matches the parsed city/district and state ({known_districts}, {known_states})."
    elif state_match:
        reason = (
            f"Pincode {pincode} belongs to {known_states}, which matches the parsed state, "
            f"but the parsed city/district doesn't match the known district(s) {known_districts}."
        )
    elif city_match:
        reason = (
            f"Pincode {pincode} matches the parsed city/district {known_districts}, "
            f"but the parsed state doesn't match the known state(s) {known_states}."
        )
    else:
        reason = (
            f"Pincode {pincode} belongs to {known_districts}, {known_states}, "
            "which doesn't match the parsed city/district or state."
        )

    return {
        "pincode_valid": True,
        "pincode_city_match": city_match,
        "pincode_state_match": state_match,
        "pincode_match_reason": reason,
    }