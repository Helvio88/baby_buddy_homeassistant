"""Assist intent handlers for the babybuddy integration."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import voluptuous as vol
import yaml

from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    ATTR_NAME,
    ATTR_TEMPERATURE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_registry as er, intent

from .const import (
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
    ATTR_DOSAGE,
    ATTR_DOSAGE_UNIT,
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
    LOGGER,
)

INTENT_ADD_BMI = "BabyBuddyAddBmi"
INTENT_ADD_CHILD = "BabyBuddyAddChild"
INTENT_ADD_DIAPER_CHANGE = "BabyBuddyAddDiaperChange"
INTENT_ADD_FEEDING = "BabyBuddyAddFeeding"
INTENT_ADD_HEAD_CIRCUMFERENCE = "BabyBuddyAddHeadCircumference"
INTENT_ADD_HEIGHT = "BabyBuddyAddHeight"
INTENT_ADD_MEDICATION = "BabyBuddyAddMedication"
INTENT_ADD_NOTE = "BabyBuddyAddNote"
INTENT_ADD_PUMPING = "BabyBuddyAddPumping"
INTENT_ADD_SLEEP = "BabyBuddyAddSleep"
INTENT_ADD_TEMPERATURE = "BabyBuddyAddTemperature"
INTENT_ADD_TUMMY_TIME = "BabyBuddyAddTummyTime"
INTENT_ADD_WEIGHT = "BabyBuddyAddWeight"
INTENT_DELETE_LAST_ENTRY = "BabyBuddyDeleteLastEntry"
INTENT_START_TIMER = "BabyBuddyStartTimer"

INTENT_TYPES: tuple[str, ...] = (
    INTENT_ADD_CHILD,
    INTENT_ADD_BMI,
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
)

SENTENCES_DIR = Path(__file__).parent / "sentences"
DATA_INTENTS_SETUP = f"{DOMAIN}_intents_setup"

LAST_ENTRY_ENDPOINTS: dict[str, str] = {
    "bmi": ATTR_BMI,
    "change": "changes",
    "diaper": "changes",
    "diaper change": "changes",
    "feeding": "feedings",
    "head circumference": "head-circumference",
    "height": ATTR_HEIGHT,
    "medication": "medication",
    "note": "notes",
    "notes": "notes",
    "pumping": "pumping",
    "sleep": "sleep",
    "temperature": "temperature",
    "tummy time": "tummy-times",
    "weight": ATTR_WEIGHT,
}

_OPTIONAL_CHILD_SCHEMA = {
    vol.Optional(ATTR_CHILD): cv.string,
}


def _slot_value(slots: Mapping[str, Any], key: str, default: Any = None) -> Any:
    """Return a stripped slot value when present."""
    if key not in slots:
        return default
    raw = slots[key]
    value = raw.get("value", raw) if isinstance(raw, Mapping) else raw
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return default
    return value


def _as_float(value: Any) -> float:
    """Parse a spoken or typed number."""
    if isinstance(value, (int, float)):
        return float(value)
    return float(str(value).strip().replace(",", ""))


def _iter_child_states(hass: HomeAssistant) -> list[Any]:
    """Return Baby Buddy child sensors and timer switches."""
    registry = er.async_get(hass)
    found: dict[str, Any] = {}
    for state in hass.states.async_all("sensor"):
        if state.attributes.get(ATTR_DEVICE_CLASS) == ATTR_BABYBUDDY_CHILD:
            found[state.entity_id] = state
    for state in hass.states.async_all("switch"):
        entry = registry.async_get(state.entity_id)
        if entry is not None and entry.platform == DOMAIN:
            found[state.entity_id] = state
    return list(found.values())


def _state_name_tokens(state: Any) -> set[str]:
    """Return lowercase names that can resolve a child state."""
    tokens = {
        state.entity_id,
        state.name.casefold(),
    }
    first = str(state.attributes.get(ATTR_FIRST_NAME) or "").strip()
    last = str(state.attributes.get(ATTR_LAST_NAME) or "").strip()
    if first:
        tokens.add(first.casefold())
    if last:
        tokens.add(last.casefold())
    if first and last:
        tokens.add(f"{first} {last}".casefold())
    return tokens


def _resolve_child_entity_id(hass: HomeAssistant, spoken: str | None) -> str:
    """Resolve a spoken child name to a child sensor or timer switch."""
    states = _iter_child_states(hass)
    if spoken:
        spoken_cf = spoken.casefold()
        matches = [
            state
            for state in states
            if spoken_cf in _state_name_tokens(state)
            or spoken_cf in state.name.casefold()
        ]
        sensors = [state for state in matches if state.entity_id.startswith("sensor.")]
        chosen = sensors or matches
        if len(chosen) == 1:
            return chosen[0].entity_id
        if not chosen:
            raise intent.IntentHandleError(
                f"Could not find a Baby Buddy child named {spoken}."
            )
        raise intent.IntentHandleError(
            f"More than one Baby Buddy child matches {spoken}."
        )

    sensors = [state for state in states if state.entity_id.startswith("sensor.")]
    if len(sensors) == 1:
        return sensors[0].entity_id
    if len(sensors) == 0 and len(states) == 1:
        return states[0].entity_id
    if not states:
        raise intent.IntentHandleError("No Baby Buddy child is available.")
    raise intent.IntentHandleError(
        "Say which child, for example log a wet diaper for Arthur."
    )


def _resolve_last_entry_entity_id(
    hass: HomeAssistant, child_entity_id: str, endpoint: str
) -> str:
    """Resolve the last-entry sensor for a child and endpoint."""
    registry = er.async_get(hass)
    child_entry = registry.async_get(child_entity_id)
    if child_entry is not None:
        parts = child_entry.unique_id.split("-")
        if len(parts) >= 2:
            prefix = f"{parts[0]}-{parts[1]}-"
            for entry in registry.entities.values():
                if (
                    entry.platform == DOMAIN
                    and entry.domain == "sensor"
                    and entry.unique_id.startswith(prefix)
                    and entry.unique_id[len(prefix) :] == endpoint
                ):
                    return entry.entity_id

    label = {
        "changes": "change",
        "feedings": "feeding",
        "head-circumference": "head circumference",
        "tummy-times": "tummy time",
        "notes": "note",
    }.get(endpoint, endpoint.replace("-", " "))
    needle = f"last {label}"
    matches = [
        state
        for state in hass.states.async_all("sensor")
        if needle in state.name.casefold()
    ]
    if len(matches) == 1:
        return matches[0].entity_id
    child_state = hass.states.get(child_entity_id)
    if child_state is not None:
        first = str(child_state.attributes.get(ATTR_FIRST_NAME) or "").casefold()
        last = str(child_state.attributes.get(ATTR_LAST_NAME) or "").casefold()
        named = [
            state
            for state in matches
            if first in state.name.casefold() and last in state.name.casefold()
        ]
        if len(named) == 1:
            return named[0].entity_id
    raise intent.IntentHandleError(f"Could not find a last {label} sensor to delete.")


def _service_data_from_slots(
    slots: Mapping[str, Any],
    mapping: Mapping[str, str],
    numeric: set[str],
) -> dict[str, Any]:
    """Copy named slots into service data."""
    data: dict[str, Any] = {}
    for slot_name, field_name in mapping.items():
        value = _slot_value(slots, slot_name)
        if value is None:
            continue
        if field_name in numeric:
            value = _as_float(value)
        data[field_name] = value
    return data


@dataclass(frozen=True, slots=True)
class _ServiceIntentSpec:
    """Description of a Baby Buddy action intent."""

    intent_type: str
    service: str
    description: str
    speech: str
    slot_schema: dict[Any, Any]
    slot_mapping: dict[str, str]
    numeric_fields: frozenset[str] = frozenset()
    require_child: bool = True
    extra_slots: Callable[[Mapping[str, Any]], dict[str, Any]] | None = None


def _feeding_extra(slots: Mapping[str, Any]) -> dict[str, Any]:
    """Validate feeding type and method."""
    data = _service_data_from_slots(
        slots,
        {ATTR_TYPE: ATTR_TYPE, ATTR_METHOD: ATTR_METHOD, ATTR_AMOUNT: ATTR_AMOUNT},
        {ATTR_AMOUNT},
    )
    if ATTR_TYPE not in data or ATTR_METHOD not in data:
        raise intent.IntentHandleError(
            "Say the feeding type and method, for example log a formula bottle feeding."
        )
    return data


SERVICE_INTENT_SPECS: tuple[_ServiceIntentSpec, ...] = (
    _ServiceIntentSpec(
        intent_type=INTENT_ADD_BMI,
        service=ATTR_ACTION_ADD_BMI,
        description="Add a BMI entry in Baby Buddy",
        speech="Logged BMI",
        slot_schema={
            **_OPTIONAL_CHILD_SCHEMA,
            vol.Required(ATTR_BMI): cv.string,
        },
        slot_mapping={ATTR_BMI: ATTR_BMI},
        numeric_fields=frozenset({ATTR_BMI}),
    ),
    _ServiceIntentSpec(
        intent_type=INTENT_ADD_DIAPER_CHANGE,
        service=ATTR_ACTION_ADD_DIAPER_CHANGE,
        description="Add a diaper change entry in Baby Buddy",
        speech="Logged a diaper change",
        slot_schema={
            **_OPTIONAL_CHILD_SCHEMA,
            vol.Optional(ATTR_TYPE): cv.string,
            vol.Optional(ATTR_COLOR): cv.string,
            vol.Optional(ATTR_AMOUNT): cv.string,
        },
        slot_mapping={
            ATTR_TYPE: ATTR_TYPE,
            ATTR_COLOR: ATTR_COLOR,
            ATTR_AMOUNT: ATTR_AMOUNT,
        },
        numeric_fields=frozenset({ATTR_AMOUNT}),
    ),
    _ServiceIntentSpec(
        intent_type=INTENT_ADD_FEEDING,
        service=ATTR_ACTION_ADD_FEEDING,
        description="Add a feeding entry in Baby Buddy",
        speech="Logged a feeding",
        slot_schema={
            **_OPTIONAL_CHILD_SCHEMA,
            vol.Optional(ATTR_TYPE): cv.string,
            vol.Optional(ATTR_METHOD): cv.string,
            vol.Optional(ATTR_AMOUNT): cv.string,
        },
        slot_mapping={},
        extra_slots=_feeding_extra,
    ),
    _ServiceIntentSpec(
        intent_type=INTENT_ADD_HEAD_CIRCUMFERENCE,
        service=ATTR_ACTION_ADD_HEAD_CIRCUMFERENCE,
        description="Add a head circumference entry in Baby Buddy",
        speech="Logged head circumference",
        slot_schema={
            **_OPTIONAL_CHILD_SCHEMA,
            vol.Required(ATTR_HEAD_CIRCUMFERENCE_UNDERSCORE): cv.string,
        },
        slot_mapping={
            ATTR_HEAD_CIRCUMFERENCE_UNDERSCORE: ATTR_HEAD_CIRCUMFERENCE_UNDERSCORE
        },
        numeric_fields=frozenset({ATTR_HEAD_CIRCUMFERENCE_UNDERSCORE}),
    ),
    _ServiceIntentSpec(
        intent_type=INTENT_ADD_HEIGHT,
        service=ATTR_ACTION_ADD_HEIGHT,
        description="Add a height entry in Baby Buddy",
        speech="Logged height",
        slot_schema={
            **_OPTIONAL_CHILD_SCHEMA,
            vol.Required(ATTR_HEIGHT): cv.string,
        },
        slot_mapping={ATTR_HEIGHT: ATTR_HEIGHT},
        numeric_fields=frozenset({ATTR_HEIGHT}),
    ),
    _ServiceIntentSpec(
        intent_type=INTENT_ADD_MEDICATION,
        service=ATTR_ACTION_ADD_MEDICATION,
        description="Add a medication entry in Baby Buddy",
        speech="Logged medication",
        slot_schema={
            **_OPTIONAL_CHILD_SCHEMA,
            vol.Required(ATTR_NAME): cv.string,
            vol.Optional(ATTR_DOSAGE): cv.string,
            vol.Optional(ATTR_DOSAGE_UNIT): cv.string,
        },
        slot_mapping={
            ATTR_NAME: ATTR_NAME,
            ATTR_DOSAGE: ATTR_DOSAGE,
            ATTR_DOSAGE_UNIT: ATTR_DOSAGE_UNIT,
        },
        numeric_fields=frozenset({ATTR_DOSAGE}),
    ),
    _ServiceIntentSpec(
        intent_type=INTENT_ADD_NOTE,
        service=ATTR_ACTION_ADD_NOTE,
        description="Add a note entry in Baby Buddy",
        speech="Logged a note",
        slot_schema={
            **_OPTIONAL_CHILD_SCHEMA,
            vol.Required(ATTR_NOTE): cv.string,
        },
        slot_mapping={ATTR_NOTE: ATTR_NOTE},
    ),
    _ServiceIntentSpec(
        intent_type=INTENT_ADD_PUMPING,
        service=ATTR_ACTION_ADD_PUMPING,
        description="Add a pumping entry in Baby Buddy",
        speech="Logged pumping",
        slot_schema={
            **_OPTIONAL_CHILD_SCHEMA,
            vol.Required(ATTR_AMOUNT): cv.string,
        },
        slot_mapping={ATTR_AMOUNT: ATTR_AMOUNT},
        numeric_fields=frozenset({ATTR_AMOUNT}),
    ),
    _ServiceIntentSpec(
        intent_type=INTENT_ADD_SLEEP,
        service=ATTR_ACTION_ADD_SLEEP,
        description="Add a sleep entry in Baby Buddy",
        speech="Logged sleep",
        slot_schema={
            **_OPTIONAL_CHILD_SCHEMA,
            vol.Optional(ATTR_NAP): cv.boolean,
        },
        slot_mapping={ATTR_NAP: ATTR_NAP},
    ),
    _ServiceIntentSpec(
        intent_type=INTENT_ADD_TEMPERATURE,
        service=ATTR_ACTION_ADD_TEMPERATURE,
        description="Add a temperature entry in Baby Buddy",
        speech="Logged temperature",
        slot_schema={
            **_OPTIONAL_CHILD_SCHEMA,
            vol.Required(ATTR_TEMPERATURE): cv.string,
        },
        slot_mapping={ATTR_TEMPERATURE: ATTR_TEMPERATURE},
        numeric_fields=frozenset({ATTR_TEMPERATURE}),
    ),
    _ServiceIntentSpec(
        intent_type=INTENT_ADD_TUMMY_TIME,
        service=ATTR_ACTION_ADD_TUMMY_TIME,
        description="Add a tummy time entry in Baby Buddy",
        speech="Logged tummy time",
        slot_schema={**_OPTIONAL_CHILD_SCHEMA},
        slot_mapping={},
    ),
    _ServiceIntentSpec(
        intent_type=INTENT_ADD_WEIGHT,
        service=ATTR_ACTION_ADD_WEIGHT,
        description="Add a weight entry in Baby Buddy",
        speech="Logged weight",
        slot_schema={
            **_OPTIONAL_CHILD_SCHEMA,
            vol.Required(ATTR_WEIGHT): cv.string,
        },
        slot_mapping={ATTR_WEIGHT: ATTR_WEIGHT},
        numeric_fields=frozenset({ATTR_WEIGHT}),
    ),
    _ServiceIntentSpec(
        intent_type=INTENT_START_TIMER,
        service=ATTR_ACTION_START_TIMER,
        description="Start a Baby Buddy timer",
        speech="Started the timer",
        slot_schema={**_OPTIONAL_CHILD_SCHEMA},
        slot_mapping={},
    ),
)


class BabyBuddyServiceIntentHandler(intent.IntentHandler):
    """Call an existing Baby Buddy action from an Assist intent."""

    platforms = {DOMAIN}

    def __init__(self, spec: _ServiceIntentSpec) -> None:
        """Initialize the handler from a spec."""
        self.intent_type = spec.intent_type
        self.description = spec.description
        self._spec = spec

    @property
    def slot_schema(self) -> dict[Any, Any]:
        """Return the slot schema for this action."""
        return self._spec.slot_schema

    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        """Resolve slots and call the matching Baby Buddy action."""
        slots = self.async_validate_slots(intent_obj.slots)
        data = _service_data_from_slots(
            slots, self._spec.slot_mapping, self._spec.numeric_fields
        )
        if self._spec.extra_slots is not None:
            data.update(self._spec.extra_slots(slots))
        if self._spec.require_child:
            data[ATTR_CHILD] = _resolve_child_entity_id(
                intent_obj.hass, _slot_value(slots, ATTR_CHILD)
            )

        await intent_obj.hass.services.async_call(
            DOMAIN,
            self._spec.service,
            data,
            blocking=True,
            context=intent_obj.context,
        )
        response = intent_obj.create_response()
        response.async_set_speech(self._spec.speech)
        return response


class BabyBuddyAddChildIntentHandler(intent.IntentHandler):
    """Handle add-child intents."""

    intent_type = INTENT_ADD_CHILD
    description = "Add a child to Baby Buddy"
    platforms = {DOMAIN}
    slot_schema = {
        vol.Optional("child_name"): cv.string,
        vol.Optional(ATTR_FIRST_NAME): cv.string,
        vol.Optional(ATTR_LAST_NAME): cv.string,
        vol.Required(ATTR_BIRTH_DATE): cv.string,
    }

    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        """Add a child using first and last name plus birth date."""
        slots = self.async_validate_slots(intent_obj.slots)
        first_name = _slot_value(slots, ATTR_FIRST_NAME)
        last_name = _slot_value(slots, ATTR_LAST_NAME)
        child_name = _slot_value(slots, "child_name")
        if (not first_name or not last_name) and child_name:
            parts = str(child_name).split()
            if len(parts) < 2:
                raise intent.IntentHandleError("Say the child's first and last name.")
            first_name = parts[0]
            last_name = " ".join(parts[1:])
        if not first_name or not last_name:
            raise intent.IntentHandleError("Say the child's first and last name.")

        await intent_obj.hass.services.async_call(
            DOMAIN,
            ATTR_ACTION_ADD_CHILD,
            {
                ATTR_FIRST_NAME: first_name,
                ATTR_LAST_NAME: last_name,
                ATTR_BIRTH_DATE: _slot_value(slots, ATTR_BIRTH_DATE),
            },
            blocking=True,
            context=intent_obj.context,
        )
        response = intent_obj.create_response()
        response.async_set_speech(f"Added child {first_name} {last_name}")
        return response


class BabyBuddyDeleteLastEntryIntentHandler(intent.IntentHandler):
    """Handle delete-last-entry intents."""

    intent_type = INTENT_DELETE_LAST_ENTRY
    description = "Delete the last Baby Buddy entry for a named sensor type"
    platforms = {DOMAIN}
    slot_schema = {
        **_OPTIONAL_CHILD_SCHEMA,
        vol.Required("entry_type"): cv.string,
    }

    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        """Delete the last entry for an explicit last-* sensor type."""
        slots = self.async_validate_slots(intent_obj.slots)
        entry_type = str(_slot_value(slots, "entry_type")).casefold()
        endpoint = LAST_ENTRY_ENDPOINTS.get(entry_type)
        if endpoint is None:
            raise intent.IntentHandleError(
                "Say which last entry to delete, for example delete the last feeding."
            )
        child_entity_id = _resolve_child_entity_id(
            intent_obj.hass, _slot_value(slots, ATTR_CHILD)
        )
        entity_id = _resolve_last_entry_entity_id(
            intent_obj.hass, child_entity_id, endpoint
        )
        await intent_obj.hass.services.async_call(
            DOMAIN,
            ATTR_ACTION_DELETE_LAST_ENTRY,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
            context=intent_obj.context,
        )
        response = intent_obj.create_response()
        response.async_set_speech(f"Deleted the last {entry_type}")
        return response


def load_integration_sentences(language: str) -> dict[str, Any]:
    """Load shipped Hassil YAML for a language code."""
    lang = language.split("-", maxsplit=1)[0].lower()
    merged: dict[str, Any] = {}
    paths: list[Path] = []
    language_file = SENTENCES_DIR / f"{lang}.yaml"
    if language_file.is_file():
        paths.append(language_file)
    language_dir = SENTENCES_DIR / lang
    if language_dir.is_dir():
        paths.extend(sorted(language_dir.glob("*.yaml")))
    for path in paths:
        with path.open(encoding="utf-8") as handle:
            loaded = yaml.safe_load(handle) or {}
        if isinstance(loaded, dict):
            _merge_sentence_dict(merged, loaded, overwrite=True)
    return merged


def _merge_sentence_dict(
    base: dict[str, Any], extra: dict[str, Any], *, overwrite: bool
) -> bool:
    """Merge sentence YAML. When overwrite is false, existing intent names win."""
    changed = False
    extra_intents = extra.get("intents") or {}
    base_intents = base.setdefault("intents", {})
    for name, data in extra_intents.items():
        if overwrite or name not in base_intents:
            base_intents[name] = data
            changed = True
    extra_lists = extra.get("lists") or {}
    base_lists = base.setdefault("lists", {})
    for name, data in extra_lists.items():
        if overwrite or name not in base_lists:
            base_lists[name] = data
            changed = True
    extra_rules = extra.get("expansion_rules") or {}
    base_rules = base.setdefault("expansion_rules", {})
    for name, data in extra_rules.items():
        if overwrite or name not in base_rules:
            base_rules[name] = data
            changed = True
    extra_skip = extra.get("skip_words") or []
    if extra_skip:
        skip = list(base.get("skip_words") or [])
        for word in extra_skip:
            if word not in skip:
                skip.append(word)
                changed = True
        base["skip_words"] = skip
    extra_responses = (extra.get("responses") or {}).get("intents") or {}
    if extra_responses:
        base_responses = base.setdefault("responses", {}).setdefault("intents", {})
        for name, data in extra_responses.items():
            if overwrite or name not in base_responses:
                base_responses[name] = data
                changed = True
    return changed


def _hook_conversation_sentences() -> None:
    """Inject shipped sentences into the default conversation agent.

    Current Home Assistant loads built-in intents plus
    config/custom_sentences/<lang>/. It does not scan custom integration
    folders. Patch the loader so custom_components/babybuddy/sentences/ is
    merged first and user custom_sentences files still replace those intents.
    """
    try:
        from hassil.intents import Intents  # noqa: PLC0415

        from homeassistant.components.conversation.default_agent import (  # noqa: PLC0415
            DefaultAgent,
            LanguageIntents,
        )
    except ImportError:
        LOGGER.debug("Conversation agent unavailable; skipping sentence injection")
        return

    original = getattr(DefaultAgent, "_load_intents")
    if getattr(original, "_babybuddy_patched", False):
        return

    def _load_intents(self: Any, language: str) -> Any:
        result = original(self, language)
        extra = load_integration_sentences(language)
        if not extra.get("intents"):
            return result
        intents_dict: dict[str, Any]
        language_variant: str | None
        if result is None:
            intents_dict = {}
            language_variant = language
        else:
            intents_dict = result.intents_dict
            language_variant = result.language_variant
        if not _merge_sentence_dict(intents_dict, extra, overwrite=False):
            return result
        compiled = Intents.from_dict(intents_dict)
        responses = intents_dict.get("responses") or {}
        return LanguageIntents(
            compiled,
            intents_dict,
            responses.get("intents") or {},
            responses.get("errors") or {},
            language_variant,
        )

    setattr(_load_intents, "_babybuddy_patched", True)
    setattr(DefaultAgent, "_load_intents", _load_intents)


async def async_setup_intents(hass: HomeAssistant) -> None:
    """Register Baby Buddy Assist intent handlers."""
    if hass.data.get(DATA_INTENTS_SETUP):
        return
    hass.data[DATA_INTENTS_SETUP] = True

    for spec in SERVICE_INTENT_SPECS:
        intent.async_register(hass, BabyBuddyServiceIntentHandler(spec))
    intent.async_register(hass, BabyBuddyAddChildIntentHandler())
    intent.async_register(hass, BabyBuddyDeleteLastEntryIntentHandler())
    _hook_conversation_sentences()
