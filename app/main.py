"""FastAPI interface for libpostal's Python bindings (pypostal)."""

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
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
    address: str = Field(min_length=1, max_length=1_000, examples=["781 Franklin Ave, Brooklyn, NY 11216"])


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
