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
    latitude: NotRequired[float]
    longitude: NotRequired[float]
    confidence_score: NotRequired[float]


class UserAddress(TypedDict):
    name: str
    phone: str
    pincode: str
    landmark: str
    address: AddressState
