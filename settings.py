"""Config loader that works both locally (.env) and on Streamlit Cloud (st.secrets)."""
from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

try:
    import streamlit as st
    _SECRETS = dict(st.secrets) if hasattr(st, "secrets") else {}
except Exception:  # noqa: BLE001
    _SECRETS = {}


def cfg(key: str, default: str = "") -> str:
    if key in _SECRETS:
        return str(_SECRETS[key])
    return os.getenv(key, default)


def google_credentials(scopes: list[str]):
    """Service-account creds from a secrets table (cloud) or a key file (local)."""
    from google.oauth2 import service_account
    if "gcp_service_account" in _SECRETS:
        info = dict(_SECRETS["gcp_service_account"])
        return service_account.Credentials.from_service_account_info(info, scopes=scopes)
    path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
    if not path or not os.path.exists(path):
        raise FileNotFoundError(
            "No Google credentials. Set [gcp_service_account] in Streamlit secrets "
            "or GOOGLE_APPLICATION_CREDENTIALS to a JSON key file.")
    return service_account.Credentials.from_service_account_file(path, scopes=scopes)


def defaults() -> dict:
    return {
        "psi_key": cfg("PAGESPEED_API_KEY"),
        "ahrefs_token": cfg("AHREFS_API_TOKEN"),
        "dfs_login": cfg("DATAFORSEO_LOGIN"),
        "dfs_password": cfg("DATAFORSEO_PASSWORD"),
        "da_source": cfg("DA_SOURCE", "none").lower(),   # none | dataforseo
        "output_sheet_id": cfg("OUTPUT_SHEET_ID"),
        "llm_provider": cfg("LLM_PROVIDER", "none").lower(),
        "gemini_key": cfg("GEMINI_API_KEY"),
        "gemini_model": cfg("GEMINI_MODEL", "gemini-1.5-pro"),
        "anthropic_key": cfg("ANTHROPIC_API_KEY"),
        "anthropic_model": cfg("ANTHROPIC_MODEL", "claude-sonnet-5"),
    }
