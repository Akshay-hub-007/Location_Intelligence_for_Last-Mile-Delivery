import httpx

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"


async def get_lat_lon(address: str) -> dict[str, float | str] | None:
    params = {
        "q": address,
        "format": "jsonv2",
        "limit": 3,
        "countrycodes": "in",
        "addressdetails": 1,
    }
    headers = {"User-Agent": "pata-address-geocoder/1.0"}

    async with httpx.AsyncClient(timeout=5) as client:
        response = await client.get(NOMINATIM_URL, params=params, headers=headers)
        response.raise_for_status()
        results = response.json()

    if not results:
        return None

    best = results[0]
    return {
        "latitude": float(best["lat"]),
        "longitude": float(best["lon"]),
        "display_name": best["display_name"],
        "importance": float(best.get("importance", 0)),
    }
