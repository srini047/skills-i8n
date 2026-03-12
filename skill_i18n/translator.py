"""
Translation engine backed by Lingo.dev SDK.
Handles structured frontmatter objects and Markdown body text.
"""
from __future__ import annotations

import os
from typing import Any

from lingodotdev import LingoDotDevEngine


# All locales supported by Lingo.dev (83+)
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


class SkillTranslator:
    """
    Translates agent skill content using the Lingo.dev Python SDK.

    Handles:
    - Frontmatter fields (name, description) as structured objects
    - Markdown body as HTML-aware text (preserves code blocks, headings)
    - Optional reference glossary for technical AI/agent terminology
    """

    # Agent/AI domain glossary — keeps technical terms consistent
    AGENT_GLOSSARY: dict[str, str] = {
        "skill": "skill",
        "SKILL.md": "SKILL.md",
        "agent": "agent",
        "frontmatter": "frontmatter",
        "Claude": "Claude",
        "Codex": "Codex",
        "MCP": "MCP",
        "bash": "bash",
        "Python": "Python",
        "JavaScript": "JavaScript",
        "TypeScript": "TypeScript",
        "GitHub": "GitHub",
        "Git": "Git",
        "API": "API",
        "SDK": "SDK",
        "LLM": "LLM",
        "AI": "AI",
    }

    def __init__(self, api_key: str | None = None, source_locale: str = "en"):
        self.api_key = api_key or os.environ.get("LINGODOTDEV_API_KEY", "")
        self.source_locale = source_locale

    async def translate_skill(
        self,
        frontmatter_dict: dict[str, Any],
        body: str,
        target_locale: str,
    ) -> tuple[dict[str, Any], str]:
        """
        Translate frontmatter fields and markdown body.
        Returns (translated_frontmatter_dict, translated_body).
        """
        async with LingoDotDevEngine({"api_key": self.api_key}) as engine:
            # Translate structured frontmatter (name + description) as an object
            # so Lingo.dev can use context across fields
            translatable_fm = {
                k: v
                for k, v in frontmatter_dict.items()
                if isinstance(v, str) and k not in ("license",)
            }

            translated_fm: dict[str, Any] = {}
            if translatable_fm:
                translated_fm = await engine.localize_object(
                    translatable_fm,
                    {
                        "source_locale": self.source_locale,
                        "target_locale": target_locale,
                    },
                    reference=self.AGENT_GLOSSARY,
                )

            # Translate the Markdown body as HTML (preserves structure)
            translated_body = await engine.localize_html(
                _md_to_translatable(body),
                {
                    "source_locale": self.source_locale,
                    "target_locale": target_locale,
                },
                reference=self.AGENT_GLOSSARY,
            )
            translated_body = _translatable_to_md(translated_body)

            # Merge non-string fields back unchanged
            merged_fm = {**frontmatter_dict}
            merged_fm.update(translated_fm)

            return merged_fm, translated_body

    async def detect_locale(self, text: str) -> str:
        """Auto-detect source locale of a skill."""
        async with LingoDotDevEngine({"api_key": self.api_key}) as engine:
            return await engine.detect_language(text)


def _md_to_translatable(md: str) -> str:
    """
    Wrap Markdown in minimal HTML so Lingo.dev can parse and preserve structure.
    Code blocks are wrapped in <pre><code> so they're not translated.
    """
    import re

    # Protect fenced code blocks
    code_block_re = re.compile(r"```[\s\S]*?```", re.MULTILINE)
    placeholders: list[str] = []

    def replace_code(m: re.Match) -> str:
        idx = len(placeholders)
        placeholders.append(m.group(0))
        return f'<pre><code data-i18n-skip="{idx}">{m.group(0)}</code></pre>'

    protected = code_block_re.sub(replace_code, md)
    return f"<div class='skill-body'>{protected}</div>"


def _translatable_to_md(html: str) -> str:
    """Strip the wrapper HTML and restore original code blocks."""
    import re

    # Remove wrapper div
    html = re.sub(r"<div class='skill-body'>|</div>$", "", html, flags=re.DOTALL).strip()

    # Restore code blocks from <pre><code> tags
    code_re = re.compile(r"<pre><code[^>]*>([\s\S]*?)</code></pre>")
    result = code_re.sub(lambda m: m.group(1), html)

    return result
