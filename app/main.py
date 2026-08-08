"""FastAPI interface for libpostal's Python bindings (pypostal)."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.workflow import clean_user_address

try:
    from postal.expand import expand_address
    from postal.parser import parse_address
    POSTAL_IMPORT_ERROR: str | None = None
except (ImportError, OSError) as error:
    # OSError is raised when postal is installed but libpostal.dll/.so is absent.
    POSTAL_IMPORT_ERROR = str(error)


class AddressRequest(BaseModel):
    address: str = Field(min_length=1, max_length=1_000, examples=["781 Franklin Ave, Brooklyn, NY 11216"])


class Component(BaseModel):
    value: str
    label: str


class ParseResponse(BaseModel):
    components: list[Component]


class CleanAddressRequest(BaseModel):
    name: str = ""
    phone: str = ""
    pincode: str = ""
    landmark: str = ""
    lat: float | None = None
    lon: float | None = None
    address: str = Field(min_length=1, max_length=1_000, examples=["781 Franklin Ave, Brooklyn, NY 11216"])
    

# Temporary sample records. Replace this dictionary with a database repository.
DUMMY_USERS: dict[int, dict[str, str]] = {
    1: {
        "name": "Anjali",
        "phone": "9876543210",
        "pincode": "500002",
        "landmark": "Charminar",
        "address": "చార్మినార్  హైదరాబాద్, తెలంగాణ 500002",
    },
    2: {
    "name": "Ravi",
    "phone": "9876501234",
    "pincode": "560001",
    "landmark": "Cubbon Park",
    "address": "22, Museum of Art & Photography, Kasturba Road, Shanthala Nagar, Bengaluru, Bengaluru Urban, Karnataka 560001",
    },
    3 :    {
      "name": "Priya",
      "phone": "9012345678",
      "pincode": "560038",
      "landmark": "Indiranagar Metro",
      "address": "H.No 78, Sai Residency, 12th Main Rd, Indiranagar Metro daggara, HAL 2nd Stage, Bengaluru, Karnataka 560038"
    },
    4 : {
      "name": "Naresh",
      "phone": "9123456789",
      "pincode": "400001",
      "landmark": "Gateway of India",
      "address": "Flat 12, Sea View Building, Colaba Causeway, Gateway of India ke paas, Colaba, Mumbai, Maharashtra 400001"
    },
    5 : {
      "name": "Kiran",
      "phone": "9988776655",
      "pincode": "600001",
      "landmark": "Chennai Central",
      "address": "No 48, Sri Lakshmi Complex, Poonamallee High Rd, Chennai Central daggara, Park Town, Chennai, Tamil Nadu 600001"
    },
}



def require_libpostal() -> None:
    if POSTAL_IMPORT_ERROR:
        raise HTTPException(
            status_code=503,
            detail=(
                "libpostal is unavailable. Install the native libpostal library and the "
                f"postal Python binding. Loader error: {POSTAL_IMPORT_ERROR}"
            ),
        )


@asynccontextmanager
async def lifespan(_: FastAPI):
    # pypostal initializes libpostal lazily on first use. Importing it at startup
    # makes DLL/shared-library configuration problems visible immediately.
    yield


app = FastAPI(title="Address parser API", version="1.0.0", lifespan=lifespan)
STATIC_DIR = Path(__file__).parent / "static"


@app.get("/", include_in_schema=False)
def dashboard() -> FileResponse:
    """Serve the clickable dummy-user address dashboard."""
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/map", include_in_schema=False)
def map_page() -> FileResponse:
    """Serve the map route for viewing route and distance to a selected user point."""
    return FileResponse(STATIC_DIR / "map.html")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok" if not POSTAL_IMPORT_ERROR else "libpostal-unavailable"}


@app.post("/parse", response_model=ParseResponse)
def parse(request: AddressRequest) -> ParseResponse:
    require_libpostal()
    return ParseResponse(components=[Component(value=value, label=label) for value, label in parse_address(request.address)])


@app.post("/expand", response_model=list[str])
def expand(request: AddressRequest) -> list[str]:
    require_libpostal() 
    return expand_address(request.address)


@app.post("/workflow/clean")
@app.post("/clean", include_in_schema=False)
async def clean(request: CleanAddressRequest) -> dict:
    """Translate (Gemini) and parse (libpostal) an address through LangGraph."""
    require_libpostal()
    try:
        return await clean_user_address(request.model_dump())
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@app.get("/users")
def list_users() -> list[dict[str, str | int]]:
    """List temporary users. Call the returned detail URL when a user is selected."""
    return [
        {
            "id": user_id,
            "name": user["name"],
            "phone": user["phone"],
            "pincode": user["pincode"],
            "address": user["address"],
            "detail_url": f"/users/{user_id}/address",
        }
        for user_id, user in DUMMY_USERS.items()
    ]


@app.get("/users/{user_id}/address")
async def user_address(user_id: int) -> dict:
    """Return the selected user's original address and the LangGraph-modified address."""
    user = DUMMY_USERS.get(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    require_libpostal()
    try:
        workflow_result = await clean_user_address(user)
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error

    return {
        "user_id": user_id,
        "name": user["name"],
        "original_address": user["address"],
        "modified_address": workflow_result["address"],
    }
