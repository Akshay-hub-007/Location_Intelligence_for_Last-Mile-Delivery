# Pata — Indian Address Cleaning & Geocoding API

Pata is an MVP for converting messy Indian delivery addresses into structured address fields, confidence data, and geographic coordinates. It is designed for last-mile delivery use cases where addresses can include mixed scripts, local landmarks, informal areas, landmark prefixes, and incomplete information.

## What is completed

- FastAPI backend with interactive Swagger documentation.
- Address expansion and parsing using **libpostal**.
- LangGraph workflow for address translation, landmark cleanup, parsing, confidence scoring, and geocoding.
- Translation node for converting regional-language input to English before parsing.
- Landmark-prefix stripping for phrases such as near, opposite, behind, beside, and close to.
- Structured address output: house number, building, street, landmark, area, city, district, state, postal code, and country.
- Confidence score and reason for the parsed address.
- Latitude/longitude lookup through `geopy` + OpenStreetMap Nominatim, restricted to India.
- Health endpoint that reports whether the native libpostal dependency is available.

## Workflow

```text
Raw address
  → Translate address
  → Strip landmark prefix
  → Parse with libpostal
  → Score confidence
  → Geocode with Nominatim
  → Structured address + latitude + longitude + confidence
```

The workflow is implemented in `app/workflow.py`. The parent LangGraph workflow runs the nested address-cleaning graph first, then the asynchronous geocoding node.

## API routes

| Method | Route | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Checks whether libpostal is available. |
| `POST` | `/parse` | Returns raw libpostal address components. |
| `POST` | `/expand` | Returns normalized address expansions. |
| `POST` | `/workflow/clean` | Runs the complete LangGraph workflow. |
| `GET` | `/users` | Lists temporary dummy users. |
| `GET` | `/users/{user_id}/address` | Returns a user's original address and workflow-modified address. |

After starting the app, open `http://localhost:8000/docs` to test these routes from Swagger UI.

## Demo UI

Open `http://localhost:8000/` for a clickable user dashboard. Select a dummy
user to view their original address beside the address produced by the main
LangGraph workflow, including parsed fields, coordinates, and confidence data when available.

The first dummy address loads by default, and each user card includes a button to get the exact address result.

To simulate selecting a user, first call `GET /users`, then open the returned
`detail_url`, for example `GET /users/1/address`.

### Complete workflow request

```json
{
  "name": "John Doe",
  "phone": "9999999999",
  "pincode": "500001",
  "landmark": "Near Charminar",
  "address": "Charminar ke paas, Hyderabad"
}
```

Example response shape:

```json
{
  "name": "John Doe",
  "phone": "9999999999",
  "pincode": "500001",
  "landmark": "Near Charminar",
  "address": {
    "raw_address": "Charminar ke paas, Hyderabad",
    "cleaned_address": "Charminar ke paas, Hyderabad",
    "translated_address": "...",
    "parsed_address": {
      "house_number": "",
      "building": "",
      "street": "",
      "landmark": "",
      "area": "",
      "city": "Hyderabad",
      "district": "",
      "state": "",
      "postal_code": "",
      "country": "India"
    },
    "confidence_score": 92,
    "confidence_reason": "House number, road, city, state, postcode and country are present.",
    "lat": 17.3616,
    "lon": 78.4747,
    "latitude": 17.3616,
    "longitude": 78.4747
  }
}
```

## Project structure

```text
app/
├── main.py                    # FastAPI application and routes
├── workflow.py                # Main and nested LangGraph workflows
├── address_cleaning.py        # Translation, landmark cleanup, confidence scoring, and parsing functions
├── states.py                  # LangGraph state definitions
└── services/
    └── geocode_service.py     # Geopy + Nominatim latitude/longitude lookup
```

## Run with Docker (recommended on Windows)

libpostal needs a native C library, so Docker is the simplest way to run the project on Windows.

```powershell
cd C:\Users\dell\Documents\ChatGPT\hack
docker build -t pata-address-api .
docker run --rm -p 8000:8000 pata-address-api
```

The first build downloads the libpostal address model and can take time. Then visit:

```text
http://localhost:8000/docs
```

The translation step now uses `deep-translator`, so you do not need a Hugging Face token for the app to run.

## Test from PowerShell

```powershell
Invoke-RestMethod http://localhost:8000/workflow/clean `
  -Method Post `
  -ContentType "application/json" `
  -Body '{"name":"John Doe","phone":"9999999999","pincode":"500001","landmark":"Near Charminar","address":"Near Charminar, Hyderabad"}'
```

## Current limitations and next steps

- Public Nominatim is suitable for a small demo only; production should use a geocoding provider or self-hosted service with caching and rate limits.
- Improve confidence scoring with deterministic rules and test coverage alongside the LLM prompt.
- Validate returned coordinates against pincode, city, and state data from the India Pincode Directory.
- Query nearby OpenStreetMap landmarks to resolve phrases such as “opposite temple” or “near gate 2”.
- Let customers or delivery agents confirm/correct the predicted map pin.

## Privacy

Keep the original address only for the time needed to create the geocode. Store any corrections as auditable, reversible structured data rather than silently replacing the user’s input.
