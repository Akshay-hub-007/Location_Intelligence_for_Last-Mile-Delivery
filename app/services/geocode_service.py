import asyncio

from geopy.geocoders import Nominatim


geolocator = Nominatim(user_agent="my_app")


async def get_lat_lon(address: str) -> dict[str, float | str] | None:
    location = await asyncio.to_thread(
        geolocator.geocode,
        address,
        exactly_one=True,
        addressdetails=True,
        language="en",
        country_codes="in",
        timeout=5,
    )
    print("nooo resulkt")
    if location is None:
        return None

    latitude = float(location.latitude)
    longitude = float(location.longitude)
    
    return {
        "lat": latitude,
        "lon": longitude,
        "latitude": latitude,
        "longitude": longitude,
        "display_name": location.address,
        "normalized_address": location.address,
    }
