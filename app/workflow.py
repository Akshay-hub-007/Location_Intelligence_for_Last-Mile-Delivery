"""LangGraph workflow: Gemini translation followed by libpostal parsing."""

from langgraph.graph import END, START, StateGraph

from app.address_cleaning import address_parsing, language_translation
from app.services.geocode_service import get_lat_lon
from app.states import AddressState, UserAddress


def _translate_node(state: AddressState) -> dict[str, str]:
    address = state.get("raw_address", "")
    source_language = state.get("detected_language", "tel_Telu")
    return {"translated_address": language_translation(address, source_language)} if address else {}


def _parse_node(state: AddressState) -> dict[str, dict[str, str]]:
    address = state.get("translated_address") or state.get("raw_address", "")
    return {"parsed_address": address_parsing(address)} if address else {}


address_cleaning = StateGraph(AddressState)
address_cleaning.add_node("translate_address", _translate_node)
address_cleaning.add_node("address_parsing", _parse_node)
address_cleaning.add_edge(START, "translate_address")
address_cleaning.add_edge("translate_address", "address_parsing")
address_cleaning.add_edge("address_parsing", END)
compiled_address_cleaning = address_cleaning.compile()


def _address_cleaning_node(state: UserAddress) -> dict[str, AddressState]:
    # The child graph works on AddressState; UserAddress holds it under `address`.
    return {"address": compiled_address_cleaning.invoke(state["address"])}


async def _geocode_node(state: UserAddress) -> dict[str, AddressState]:
    """Add a latitude/longitude result to the cleaned nested address state."""
    address_state = state["address"]
    address = address_state.get("translated_address") or address_state.get("raw_address", "")
    if not address:
        return {}

    result = await get_lat_lon(address)
    if result is None:
        return {}

    updated_address = dict(address_state)
    updated_address["latitude"] = result["latitude"]
    updated_address["longitude"] = result["longitude"]
    return {"address": updated_address}


main_workflow = StateGraph(UserAddress)
main_workflow.add_node("address_cleaning", _address_cleaning_node)
main_workflow.add_node("geocode", _geocode_node)
main_workflow.add_edge(START, "address_cleaning")
main_workflow.add_edge("address_cleaning", "geocode")
main_workflow.add_edge("geocode", END)
compiled_main_workflow = main_workflow.compile()


async def clean_user_address(request: dict[str, str]) -> dict:
    """Adapt the HTTP request shape to the parent workflow's nested state."""
    state: UserAddress = {
        "name": request.get("name", ""),
        "phone": request.get("phone", ""),
        "pincode": request.get("pincode", ""),
        "landmark": request.get("landmark", ""),
        "address": {"raw_address": request["address"]},
    }
    return await compiled_main_workflow.ainvoke(state)
