from typing import NotRequired, TypedDict


class AddressState(TypedDict):
    raw_address: str
    detected_language: NotRequired[str]
    translated_address: NotRequired[str]
    cleaned_address: NotRequired[str]
    parsed_address: NotRequired[dict[str, str]]
    city: NotRequired[str]
    state: NotRequired[str]
    country: NotRequired[str]
    pincode: NotRequired[str]
    lat: NotRequired[float]
    lon: NotRequired[float]
    latitude: NotRequired[float]
    longitude: NotRequired[float]
    confidence_score: NotRequired[float]
    confidence_reason: NotRequired[str]
    pincode_valid: NotRequired[bool]
    pincode_city_match: NotRequired[bool]
    pincode_state_match: NotRequired[bool]
    pincode_match_reason: NotRequired[str]


class UserAddress(TypedDict):
    name: str
    phone: str
    pincode: str
    landmark: str
    address: AddressState