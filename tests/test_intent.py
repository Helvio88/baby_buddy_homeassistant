"""Tests for Baby Buddy Assist intents."""

from __future__ import annotations

from typing import Any

import pytest
import yaml

from custom_components.babybuddy.const import (
    ATTR_ACTION_ADD_BMI,
    ATTR_ACTION_ADD_CHILD,
    ATTR_ACTION_ADD_DIAPER_CHANGE,
    ATTR_ACTION_ADD_FEEDING,
    ATTR_ACTION_ADD_HEAD_CIRCUMFERENCE,
    ATTR_ACTION_ADD_HEIGHT,
    ATTR_ACTION_ADD_MEDICATION,
    ATTR_ACTION_ADD_NOTE,
    ATTR_ACTION_ADD_PUMPING,
    ATTR_ACTION_ADD_SLEEP,
    ATTR_ACTION_ADD_TEMPERATURE,
    ATTR_ACTION_ADD_TUMMY_TIME,
    ATTR_ACTION_ADD_WEIGHT,
    ATTR_ACTION_DELETE_LAST_ENTRY,
    ATTR_ACTION_START_TIMER,
    ATTR_AMOUNT,
    ATTR_BABYBUDDY_CHILD,
    ATTR_BIRTH_DATE,
    ATTR_BMI,
    ATTR_CHILD,
    ATTR_COLOR,
    ATTR_FIRST_NAME,
    ATTR_HEAD_CIRCUMFERENCE_UNDERSCORE,
    ATTR_HEIGHT,
    ATTR_LAST_NAME,
    ATTR_METHOD,
    ATTR_NAP,
    ATTR_NOTE,
    ATTR_TYPE,
    ATTR_WEIGHT,
    DOMAIN,
)
from custom_components.babybuddy.intent import (
    INTENT_ADD_BMI,
    INTENT_ADD_CHILD,
    INTENT_ADD_DIAPER_CHANGE,
    INTENT_ADD_FEEDING,
    INTENT_ADD_HEAD_CIRCUMFERENCE,
    INTENT_ADD_HEIGHT,
    INTENT_ADD_MEDICATION,
    INTENT_ADD_NOTE,
    INTENT_ADD_PUMPING,
    INTENT_ADD_SLEEP,
    INTENT_ADD_TEMPERATURE,
    INTENT_ADD_TUMMY_TIME,
    INTENT_ADD_WEIGHT,
    INTENT_DELETE_LAST_ENTRY,
    INTENT_START_TIMER,
    INTENT_TYPES,
    LAST_ENTRY_ENDPOINTS,
    SENTENCES_DIR,
    _merge_sentence_dict,
    async_setup_intents,
    load_integration_sentences,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    ATTR_NAME,
    ATTR_TEMPERATURE,
)
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import entity_registry as er, intent

CHILD_ENTITY_ID = "sensor.arthur_smith_baby"
SECOND_CHILD_ENTITY_ID = "sensor.bea_jones_baby"
LAST_FEEDING_ENTITY_ID = "sensor.arthur_smith_last_feeding"

ACTION_IDS = (
    ATTR_ACTION_ADD_CHILD,
    ATTR_ACTION_ADD_BMI,
    ATTR_ACTION_ADD_DIAPER_CHANGE,
    ATTR_ACTION_ADD_FEEDING,
    ATTR_ACTION_ADD_HEAD_CIRCUMFERENCE,
    ATTR_ACTION_ADD_HEIGHT,
    ATTR_ACTION_ADD_MEDICATION,
    ATTR_ACTION_ADD_NOTE,
    ATTR_ACTION_ADD_PUMPING,
    ATTR_ACTION_ADD_SLEEP,
    ATTR_ACTION_ADD_TEMPERATURE,
    ATTR_ACTION_ADD_TUMMY_TIME,
    ATTR_ACTION_ADD_WEIGHT,
    ATTR_ACTION_DELETE_LAST_ENTRY,
    ATTR_ACTION_START_TIMER,
)


def _slots(**values: Any) -> dict[str, dict[str, Any]]:
    """Wrap raw values as intent slots."""
    return {key: {"value": value} for key, value in values.items()}


@pytest.fixture
def capture_services(hass: HomeAssistant) -> list[ServiceCall]:
    """Register Baby Buddy actions that record calls."""
    captured: list[ServiceCall] = []

    async def _capture(call: ServiceCall) -> None:
        captured.append(call)

    for service in ACTION_IDS:
        hass.services.async_register(DOMAIN, service, _capture)
    return captured


@pytest.fixture
async def setup_intents(hass: HomeAssistant) -> None:
    """Register Baby Buddy intent handlers."""
    await async_setup_intents(hass)


def _add_child_sensor(
    hass: HomeAssistant,
    entity_id: str,
    first_name: str,
    last_name: str,
    child_id: str,
) -> None:
    """Create a Baby Buddy child sensor and registry entry."""
    object_id = entity_id.split(".", 1)[1]
    er.async_get(hass).async_get_or_create(
        "sensor",
        DOMAIN,
        f"apikey-{child_id}",
        suggested_object_id=object_id,
    )
    hass.states.async_set(
        entity_id,
        "2024-01-01",
        {
            ATTR_DEVICE_CLASS: ATTR_BABYBUDDY_CHILD,
            ATTR_FIRST_NAME: first_name,
            ATTR_LAST_NAME: last_name,
        },
    )


@pytest.fixture
def one_child(hass: HomeAssistant) -> None:
    """Create a single child sensor."""
    _add_child_sensor(hass, CHILD_ENTITY_ID, "Arthur", "Smith", "1")


@pytest.fixture
def two_children(hass: HomeAssistant) -> None:
    """Create two child sensors."""
    _add_child_sensor(hass, CHILD_ENTITY_ID, "Arthur", "Smith", "1")
    _add_child_sensor(hass, SECOND_CHILD_ENTITY_ID, "Bea", "Jones", "2")


async def _handle(
    hass: HomeAssistant, intent_type: str, **values: Any
) -> intent.IntentResponse:
    """Handle an intent with raw slot values."""
    return await intent.async_handle(hass, "test", intent_type, _slots(**values))


def test_sentence_yaml_covers_every_action() -> None:
    """Shipped English sentences define one intent per existing action."""
    sentences = load_integration_sentences("en")
    assert set(sentences["intents"]) == set(INTENT_TYPES)
    assert len(INTENT_TYPES) == len(ACTION_IDS)

    yaml_path = SENTENCES_DIR / "en.yaml"
    loaded = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    for intent_name, intent_data in loaded["intents"].items():
        templates = [
            sentence for group in intent_data["data"] for sentence in group["sentences"]
        ]
        assert templates, f"{intent_name} has no sentences"


def test_delete_last_entry_covers_known_sensors() -> None:
    """Delete-last-entry maps explicit entry types to last-* endpoints."""
    assert LAST_ENTRY_ENDPOINTS["feeding"] == "feedings"
    assert LAST_ENTRY_ENDPOINTS["diaper change"] == "changes"
    assert LAST_ENTRY_ENDPOINTS["tummy time"] == "tummy-times"
    assert "undo" not in LAST_ENTRY_ENDPOINTS


@pytest.mark.usefixtures("setup_intents", "one_child", "capture_services")
async def test_add_diaper_change_defaults_single_child(
    hass: HomeAssistant, capture_services: list[ServiceCall]
) -> None:
    """A single child can be omitted from the intent."""
    response = await _handle(hass, INTENT_ADD_DIAPER_CHANGE, type="Wet", color="Yellow")

    assert response.response_type == intent.IntentResponseType.ACTION_DONE
    assert capture_services[0].service == ATTR_ACTION_ADD_DIAPER_CHANGE
    assert capture_services[0].data[ATTR_CHILD] == CHILD_ENTITY_ID
    assert capture_services[0].data[ATTR_TYPE] == "Wet"
    assert capture_services[0].data[ATTR_COLOR] == "Yellow"


@pytest.mark.usefixtures("setup_intents", "two_children", "capture_services")
async def test_add_diaper_change_resolves_child_name(
    hass: HomeAssistant, capture_services: list[ServiceCall]
) -> None:
    """A spoken first name resolves to the matching child sensor."""
    await _handle(hass, INTENT_ADD_DIAPER_CHANGE, child="Arthur", type="Solid")

    assert capture_services[0].data[ATTR_CHILD] == CHILD_ENTITY_ID
    assert capture_services[0].data[ATTR_TYPE] == "Solid"


@pytest.mark.usefixtures("setup_intents", "two_children")
async def test_add_diaper_change_requires_child_when_ambiguous(
    hass: HomeAssistant,
) -> None:
    """Multiple children require an explicit name."""
    with pytest.raises(intent.IntentHandleError, match="which child"):
        await _handle(hass, INTENT_ADD_DIAPER_CHANGE, type="Wet")


@pytest.mark.usefixtures("setup_intents", "one_child")
async def test_add_feeding_requires_type_and_method(hass: HomeAssistant) -> None:
    """Feeding type and method stay required when voice omits them."""
    with pytest.raises(intent.IntentHandleError, match="type and method"):
        await _handle(hass, INTENT_ADD_FEEDING)


@pytest.mark.usefixtures("setup_intents", "one_child", "capture_services")
async def test_add_feeding_with_slots(
    hass: HomeAssistant, capture_services: list[ServiceCall]
) -> None:
    """Feeding intents call add_feeding with the existing action ID."""
    await _handle(
        hass,
        INTENT_ADD_FEEDING,
        type="Formula",
        method="Bottle",
        amount="3.5",
    )

    assert capture_services[0].service == ATTR_ACTION_ADD_FEEDING
    assert capture_services[0].data[ATTR_TYPE] == "Formula"
    assert capture_services[0].data[ATTR_METHOD] == "Bottle"
    assert capture_services[0].data[ATTR_AMOUNT] == 3.5


@pytest.mark.usefixtures("setup_intents", "one_child", "capture_services")
async def test_measurement_intents_call_existing_actions(
    hass: HomeAssistant, capture_services: list[ServiceCall]
) -> None:
    """Numeric measurement intents call the matching actions."""
    cases = (
        (INTENT_ADD_BMI, ATTR_ACTION_ADD_BMI, {ATTR_BMI: "16.2"}),
        (INTENT_ADD_WEIGHT, ATTR_ACTION_ADD_WEIGHT, {ATTR_WEIGHT: "5.0"}),
        (INTENT_ADD_HEIGHT, ATTR_ACTION_ADD_HEIGHT, {ATTR_HEIGHT: "62"}),
        (
            INTENT_ADD_HEAD_CIRCUMFERENCE,
            ATTR_ACTION_ADD_HEAD_CIRCUMFERENCE,
            {ATTR_HEAD_CIRCUMFERENCE_UNDERSCORE: "38.1"},
        ),
        (
            INTENT_ADD_TEMPERATURE,
            ATTR_ACTION_ADD_TEMPERATURE,
            {ATTR_TEMPERATURE: "37.2"},
        ),
    )
    for intent_type, service, values in cases:
        capture_services.clear()
        await _handle(hass, intent_type, **values)
        assert capture_services[0].service == service
        assert capture_services[0].data[ATTR_CHILD] == CHILD_ENTITY_ID


@pytest.mark.usefixtures("setup_intents", "one_child", "capture_services")
async def test_add_sleep_tummy_time_and_timer(
    hass: HomeAssistant, capture_services: list[ServiceCall]
) -> None:
    """Sleep, tummy time, and timer intents call the existing actions."""
    await _handle(hass, INTENT_ADD_SLEEP, nap=True)
    await _handle(hass, INTENT_ADD_TUMMY_TIME)
    await _handle(hass, INTENT_START_TIMER)

    assert [call.service for call in capture_services] == [
        ATTR_ACTION_ADD_SLEEP,
        ATTR_ACTION_ADD_TUMMY_TIME,
        ATTR_ACTION_START_TIMER,
    ]
    assert capture_services[0].data[ATTR_NAP] is True


@pytest.mark.usefixtures("setup_intents", "one_child", "capture_services")
async def test_add_medication_note_and_pumping(
    hass: HomeAssistant, capture_services: list[ServiceCall]
) -> None:
    """Medication, note, and pumping intents pass required fields."""
    await _handle(hass, INTENT_ADD_MEDICATION, name="Tylenol", dosage="2.5")
    await _handle(hass, INTENT_ADD_NOTE, note="sleepy after bath")
    await _handle(hass, INTENT_ADD_PUMPING, amount="4")

    assert capture_services[0].data[ATTR_NAME] == "Tylenol"
    assert capture_services[1].data[ATTR_NOTE] == "sleepy after bath"
    assert capture_services[2].data[ATTR_AMOUNT] == 4.0


@pytest.mark.usefixtures("setup_intents", "capture_services")
async def test_add_child_intent(
    hass: HomeAssistant, capture_services: list[ServiceCall]
) -> None:
    """Add-child uses first and last name from a single spoken name."""
    await _handle(
        hass,
        INTENT_ADD_CHILD,
        child_name="Little Girl",
        birth_date="2022-06-20",
    )

    assert capture_services[0].service == ATTR_ACTION_ADD_CHILD
    assert capture_services[0].data[ATTR_FIRST_NAME] == "Little"
    assert capture_services[0].data[ATTR_LAST_NAME] == "Girl"
    assert capture_services[0].data[ATTR_BIRTH_DATE] == "2022-06-20"


@pytest.mark.usefixtures("setup_intents", "one_child", "capture_services")
async def test_delete_last_entry_targets_last_sensor(
    hass: HomeAssistant, capture_services: list[ServiceCall]
) -> None:
    """Delete last entry targets the last-* sensor, not a casual undo."""
    er.async_get(hass).async_get_or_create(
        "sensor",
        DOMAIN,
        "apikey-1-feedings",
        suggested_object_id="arthur_smith_last_feeding",
    )
    hass.states.async_set(
        LAST_FEEDING_ENTITY_ID, "2.0", {ATTR_NAME: "Arthur Smith last feeding"}
    )

    await _handle(hass, INTENT_DELETE_LAST_ENTRY, entry_type="feeding")

    assert capture_services[0].service == ATTR_ACTION_DELETE_LAST_ENTRY
    assert capture_services[0].data[ATTR_ENTITY_ID] == LAST_FEEDING_ENTITY_ID


@pytest.mark.usefixtures("setup_intents")
async def test_all_intent_handlers_are_registered(hass: HomeAssistant) -> None:
    """Every services.yaml action has a registered handler."""
    registered = {handler.intent_type for handler in intent.async_get(hass)}
    assert set(INTENT_TYPES) <= registered


async def test_conversation_loader_merges_without_replacing_user_intents() -> None:
    """User custom_sentences keep priority over shipped integration sentences."""
    shipped = load_integration_sentences("en")
    user = {
        "intents": {
            INTENT_ADD_DIAPER_CHANGE: {
                "data": [{"sentences": ["custom wet diaper phrase"]}]
            }
        }
    }
    merged: dict[str, Any] = {}
    _merge_sentence_dict(merged, user, overwrite=True)
    _merge_sentence_dict(merged, shipped, overwrite=False)

    assert merged["intents"][INTENT_ADD_DIAPER_CHANGE]["data"][0]["sentences"] == [
        "custom wet diaper phrase"
    ]
    assert INTENT_ADD_FEEDING in merged["intents"]
