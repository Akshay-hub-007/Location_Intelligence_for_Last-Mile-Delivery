"""Translation and deterministic libpostal address parsing nodes."""

from functools import lru_cache

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

try:
    from postal.parser import parse_address
except (ImportError, OSError) as error:
    parse_address = None
    POSTAL_IMPORT_ERROR = str(error)
else:
    POSTAL_IMPORT_ERROR = None

load_dotenv()


@lru_cache
def get_llm() -> ChatGoogleGenerativeAI:
    """Create Gemini only when translation is requested."""
    return ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)


def language_translation(addr: str) -> str:
    prompt = f"""You are an expert address translator.

Convert only non-English parts of this address to English. Preserve its original
structure and order. Do not add, remove, infer, or correct address data. If it
is already English, return it unchanged. Return only the translated address.

Address:
{addr}
"""
    try:
        return get_llm().invoke(prompt).content.strip()
    except Exception as error:
        raise RuntimeError("Address translation failed. Set GOOGLE_API_KEY and verify Gemini access.") from error


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
