"""
Translation engine backed by Lingo.dev SDK.
Handles structured frontmatter objects and Markdown body text.
"""
from __future__ import annotations

import os
import re
from typing import Any

import httpx

# Lingo.dev Endpoint
LINGO_API_BASE = "https://api.lingo.dev"
LOCALIZE_ENDPOINT = f"{LINGO_API_BASE}/process/localize"
RECOGNIZE_ENDPOINT = f"{LINGO_API_BASE}/process/recognize"

# Locales supported by Lingo.dev (not all of them are present)
SUPPORTED_LOCALES = [
    "af", "sq", "am", "ar", "hy", "as", "az", "eu", "be", "bn", "bs", "bg",
    "ca", "zh", "zh-TW", "hr", "cs", "da", "nl", "en", "et", "fi", "fr",
    "gl", "ka", "de", "el", "gu", "he", "hi", "hu", "is", "id", "ga", "it",
    "ja", "kn", "kk", "km", "ko", "lo", "lv", "lt", "mk", "ms", "ml", "mt",
    "mr", "mn", "my", "ne", "nb", "or", "ps", "fa", "pl", "pt", "pt-BR",
    "pa", "ro", "ru", "sr", "si", "sk", "sl", "so", "es", "sw", "sv", "tl",
    "tg", "ta", "te", "th", "tr", "tk", "uk", "ur", "uz", "vi", "cy", "yo",
    "zu",
]

LOCALE_NAMES = {
    "af": "Afrikaans", "sq": "Albanian", "am": "Amharic", "ar": "Arabic",
    "hy": "Armenian", "as": "Assamese", "az": "Azerbaijani", "eu": "Basque",
    "be": "Belarusian", "bn": "Bengali", "bs": "Bosnian", "bg": "Bulgarian",
    "ca": "Catalan", "zh": "Chinese (Simplified)", "zh-TW": "Chinese (Traditional)",
    "hr": "Croatian", "cs": "Czech", "da": "Danish", "nl": "Dutch",
    "en": "English", "et": "Estonian", "fi": "Finnish", "fr": "French",
    "gl": "Galician", "ka": "Georgian", "de": "German", "el": "Greek",
    "gu": "Gujarati", "he": "Hebrew", "hi": "Hindi", "hu": "Hungarian",
    "is": "Icelandic", "id": "Indonesian", "ga": "Irish", "it": "Italian",
    "ja": "Japanese", "kn": "Kannada", "kk": "Kazakh", "km": "Khmer",
    "ko": "Korean", "lo": "Lao", "lv": "Latvian", "lt": "Lithuanian",
    "mk": "Macedonian", "ms": "Malay", "ml": "Malayalam", "mt": "Maltese",
    "mr": "Marathi", "mn": "Mongolian", "my": "Burmese", "ne": "Nepali",
    "nb": "Norwegian", "or": "Odia", "ps": "Pashto", "fa": "Persian",
    "pl": "Polish", "pt": "Portuguese", "pt-BR": "Portuguese (Brazil)",
    "pa": "Punjabi", "ro": "Romanian", "ru": "Russian", "sr": "Serbian",
    "si": "Sinhala", "sk": "Slovak", "sl": "Slovenian", "so": "Somali",
    "es": "Spanish", "sw": "Swahili", "sv": "Swedish", "tl": "Filipino",
    "tg": "Tajik", "ta": "Tamil", "te": "Telugu", "th": "Thai",
    "tr": "Turkish", "tk": "Turkmen", "uk": "Ukrainian", "ur": "Urdu",
    "uz": "Uzbek", "vi": "Vietnamese", "cy": "Welsh", "yo": "Yoruba",
    "zu": "Zulu",
}


class LingoAPIError(Exception):
    """Raised when the Lingo.dev API returns a non-2xx response."""
    def __init__(self, status: int, body: str):
        self.status = status
        super().__init__(f"Lingo.dev API error {status}: {body}")


class SkillTranslator:
    """
    Translates agent skill content using the Lingo.dev REST API (v1.0).

    Calls POST /process/localize with all translatable fields as a flat
    key-value data object. The API applies the configured engine's full
    pipeline: glossary rules, brand voice, per-locale LLM selection.

    Optionally accepts an engineId to route through a specific Lingo.dev
    Localization Engine (configured at lingo.dev/en/docs/engines).
    """

    def __init__(
        self,
        api_key: str | None = None,
        source_locale: str = "en",
        engine_id: str | None = None,
        timeout: float = 60.0,
    ):
        self.api_key = api_key or os.environ.get("LINGODOTDEV_API_KEY", "")
        self.source_locale = source_locale
        self.engine_id = engine_id or os.environ.get("LINGODOTDEV_ENGINE_ID")
        self.timeout = timeout

    def _headers(self) -> dict[str, str]:
        return {
            "X-API-Key": self.api_key,
            "Content-Type": "application/json",
        }

    async def _localize(
        self,
        data: dict[str, str],
        target_locale: str,
    ) -> dict[str, str]:
        """
        Call POST /process/localize.
        Sends flat key-value string pairs; returns translated key-value pairs.
        """
        payload: dict[str, Any] = {
            "sourceLocale": self.source_locale,
            "targetLocale": target_locale,
            "data": data,
        }
        if self.engine_id:
            payload["engineId"] = self.engine_id

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                LOCALIZE_ENDPOINT,
                headers=self._headers(),
                json=payload,
            )
            if resp.status_code >= 400:
                raise LingoAPIError(resp.status_code, resp.text)
            return resp.json()["data"]

    async def translate_skill(
        self,
        frontmatter_dict: dict[str, Any],
        body: str,
        target_locale: str,
    ) -> tuple[dict[str, Any], str]:
        """
        Translate frontmatter fields and markdown body via /process/localize.

        All translatable strings (frontmatter name, description + body) are
        sent as a single flat key-value object so the engine has full context
        across the whole skill when applying glossary rules and brand voice.

        Returns (translated_frontmatter_dict, translated_body).
        """
        # Extract string frontmatter fields that should be translated
        translatable_fm = {
            k: v
            for k, v in frontmatter_dict.items()
            if isinstance(v, str) and k not in ("license",)
        }

        # Protect code blocks before including body in the payload
        protected_body, code_map = _protect_code_blocks(body)

        # Build a single flat payload: fm fields + body as one request
        # This gives the engine full context (e.g. name + description + instructions)
        data_payload: dict[str, str] = {
            **translatable_fm,
            "__body__": protected_body,
        }

        translated_data = await self._localize(data_payload, target_locale)

        # Restore code blocks in the body
        translated_body_protected = translated_data.pop("__body__", protected_body)
        translated_body = _restore_code_blocks(translated_body_protected, code_map)

        # Merge translated fm fields back, keeping non-string fields unchanged
        merged_fm = {**frontmatter_dict}
        for k, v in translated_data.items():
            if k in frontmatter_dict:
                merged_fm[k] = v

        return merged_fm, translated_body

    async def detect_locale(self, text: str) -> str:
        """
        Detect source locale via POST /process/recognize.
        Returns a BCP-47 locale code (e.g. "en", "fr", "pt-BR").
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                RECOGNIZE_ENDPOINT,
                headers=self._headers(),
                json={"text": text, "labelLocale": "en"},
            )
            if resp.status_code >= 400:
                raise LingoAPIError(resp.status_code, resp.text)
            result = resp.json()
            return result.get("locale", "en")


# ---------------------------------------------------------------------------
# Code block protection helpers
# ---------------------------------------------------------------------------

_FENCE_RE = re.compile(r"(```[\s\S]*?```)", re.MULTILINE)
_PLACEHOLDER_TPL = "<<CODE_BLOCK_{idx}>>"


def _protect_code_blocks(md: str) -> tuple[str, dict[str, str]]:
    """
    Replace fenced code blocks with stable placeholders so they are never
    sent through the translation API.

    Returns (protected_md, {placeholder: original_code_block}).
    """
    code_map: dict[str, str] = {}

    def replace(m: re.Match) -> str:
        placeholder = _PLACEHOLDER_TPL.format(idx=len(code_map))
        code_map[placeholder] = m.group(0)
        return placeholder

    protected = _FENCE_RE.sub(replace, md)
    return protected, code_map


def _restore_code_blocks(md: str, code_map: dict[str, str]) -> str:
    """Swap placeholders back for their original code blocks."""
    for placeholder, original in code_map.items():
        md = md.replace(placeholder, original)
    return md
