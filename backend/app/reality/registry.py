"""Fact Key Registry and Domain Value Validation for Reality Ledger facts.

Ensures runtime facts conform to strict type and range constraints, preventing
arbitrary or malformed data from entering the authoritative Character Core.
"""

from collections.abc import Callable
import json
from typing import Any


class InvalidFactValueError(ValueError):
    """Raised when a fact value violates the registered schema contract."""
    pass


def _validate_non_empty_str(name: str, max_len: int = 500) -> Callable[[Any], str]:
    def validator(val: Any) -> str:
        if not isinstance(val, str) or not val.strip():
            raise InvalidFactValueError(f"Fact '{name}' must be a non-empty string.")
        cleaned = val.strip()
        if len(cleaned) > max_len:
            raise InvalidFactValueError(f"Fact '{name}' exceeds maximum length of {max_len} characters.")
        return cleaned
    return validator


def _validate_int_range(name: str, min_v: int, max_v: int) -> Callable[[Any], int]:
    def validator(val: Any) -> int:
        if isinstance(val, bool) or not isinstance(val, int):
            raise InvalidFactValueError(f"Fact '{name}' must be an integer between {min_v} and {max_v}.")
        if val < min_v or val > max_v:
            raise InvalidFactValueError(f"Fact '{name}' must be between {min_v} and {max_v}, got {val}.")
        return val
    return validator


def _validate_str_list(name: str, min_items: int = 1, max_items: int = 50) -> Callable[[Any], list[str]]:
    def validator(val: Any) -> list[str]:
        if not isinstance(val, (list, tuple)):
            raise InvalidFactValueError(f"Fact '{name}' must be a sequence of strings.")
        cleaned: list[str] = []
        for item in val:
            if not isinstance(item, str) or not item.strip():
                raise InvalidFactValueError(f"Items in '{name}' must be non-empty strings.")
            cleaned.append(item.strip())
        if len(cleaned) < min_items:
            raise InvalidFactValueError(f"Fact '{name}' must contain at least {min_items} items.")
        if len(cleaned) > max_items:
            raise InvalidFactValueError(f"Fact '{name}' cannot exceed {max_items} items.")
        return cleaned
    return validator


class FactKeyRegistry:
    """Central registry of value validators for recognized Character Core fact keys."""

    _REGISTRY: dict[str, Callable[[Any], Any]] = {
        "identity.name": _validate_non_empty_str("identity.name", max_len=100),
        "identity.age": _validate_int_range("identity.age", 18, 100),
        "identity.occupation": _validate_non_empty_str("identity.occupation", max_len=200),
        "identity.background": _validate_non_empty_str("identity.background", max_len=2000),
        "family.background": _validate_non_empty_str("family.background", max_len=1000),
        "education.level": _validate_non_empty_str("education.level", max_len=100),
        "education.university": _validate_non_empty_str("education.university", max_len=200),
        "education.major": _validate_non_empty_str("education.major", max_len=200),
        "education.year": _validate_int_range("education.year", 1, 6),
        "location.residence": _validate_non_empty_str("location.residence", max_len=200),
        "interests": _validate_str_list("interests", min_items=1),
        "dislikes": _validate_str_list("dislikes", min_items=1),
        "lifestyle.transit": _validate_non_empty_str("lifestyle.transit", max_len=200),
        "lifestyle.beverage": _validate_non_empty_str("lifestyle.beverage", max_len=200),
    }

    @classmethod
    def register(cls, key: str, validator: Callable[[Any], Any]) -> None:
        """Register a custom validator for a fact key."""
        cls._REGISTRY[key] = validator

    @classmethod
    def validate(cls, key: str, value: Any) -> Any:
        """Validate and return normalized fact value.

        If key is registered, applies strict schema validator.
        If unregistered, enforces JSON-serializability and sane primitive types.
        """
        if key in cls._REGISTRY:
            return cls._REGISTRY[key](value)

        # Fallback contract for extensible / emergent keys
        return cls._validate_generic_value(key, value)

    @classmethod
    def _validate_generic_value(cls, key: str, value: Any) -> Any:
        """Validate unregistered or emergent fact values."""
        if value is None:
            raise InvalidFactValueError(f"Fact '{key}' value cannot be null.")
        # Ensure JSON-serializable
        try:
            json.dumps(value)
        except (TypeError, ValueError) as exc:
            raise InvalidFactValueError(f"Fact '{key}' value must be JSON-serializable: {exc}") from exc

        if isinstance(value, str):
            if not value.strip():
                raise InvalidFactValueError(f"Fact '{key}' string value cannot be empty.")
            return value.strip()

        if isinstance(value, (int, float, bool)):
            return value

        if isinstance(value, (list, tuple)):
            if len(value) == 0:
                raise InvalidFactValueError(f"Fact '{key}' sequence cannot be empty.")
            for item in value:
                if not isinstance(item, (str, int, float, bool)):
                    raise InvalidFactValueError(f"Fact '{key}' sequence elements must be primitive types.")
            return list(value)

        if isinstance(value, dict):
            if len(value) == 0:
                raise InvalidFactValueError(f"Fact '{key}' object cannot be empty.")
            return value

        raise InvalidFactValueError(f"Fact '{key}' value type '{type(value).__name__}' is not permitted.")
