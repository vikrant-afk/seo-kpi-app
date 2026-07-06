"""Optional custom-prompt analysis over the KPI data (Gemini or Anthropic)."""
from __future__ import annotations

import json


def _message(prompt, kpi_dict, meta):
    return (
        "You are an SEO analyst. Below is a KPI dataset for one reporting period, "
        "pulled from Google Analytics, Search Console, PageSpeed Insights, Ahrefs and "
        "DataForSEO. Ground every statement in these numbers; never invent metrics.\n\n"
        f"Site: {meta['url']}\nRange: {meta['range']}\n\n"
        f"DATA (JSON):\n{json.dumps(kpi_dict, indent=2)}\n\n"
        f"INSTRUCTION:\n{prompt}"
    )


def run_prompt(prompt, kpi_dict, meta, provider, keys) -> str | None:
    if not prompt:
        return None
    provider = (provider or "none").lower()
    if provider == "none":
        return None
    msg = _message(prompt, kpi_dict, meta)
    try:
        if provider == "gemini":
            import google.generativeai as genai
            genai.configure(api_key=keys["gemini_key"])
            return genai.GenerativeModel(keys["gemini_model"]).generate_content(msg).text
        if provider == "anthropic":
            import anthropic
            client = anthropic.Anthropic(api_key=keys["anthropic_key"])
            resp = client.messages.create(
                model=keys["anthropic_model"], max_tokens=1500,
                messages=[{"role": "user", "content": msg}])
            return "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
        return f"[Unknown LLM provider '{provider}']"
    except Exception as e:  # noqa: BLE001
        return f"[AI analysis failed: {type(e).__name__}: {e}]"
