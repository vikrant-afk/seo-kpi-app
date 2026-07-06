"""Connectors package. Each returns plain dicts with a status field."""
from __future__ import annotations


def ok(**data) -> dict:
    return {"status": "ok", **data}


def fail(reason: str) -> dict:
    return {"status": "error", "error": reason}


def not_configured(reason: str = "not configured") -> dict:
    return {"status": "not_configured", "error": reason}
