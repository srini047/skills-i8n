"""Tests for the translation engine (mocked — no API key required)."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from skill_i18n.translator import LOCALE_NAMES, SUPPORTED_LOCALES, SkillTranslator, _md_to_translatable, _translatable_to_md


class TestSupportedLocales:
    def test_common_locales_present(self):
        for code in ("es", "fr", "de", "ja", "zh", "ar", "pt-BR", "ko"):
            assert code in SUPPORTED_LOCALES

    def test_locale_names_match_supported(self):
        for code in SUPPORTED_LOCALES:
            assert code in LOCALE_NAMES, f"Missing name for locale: {code}"

    def test_at_least_80_locales(self):
        assert len(SUPPORTED_LOCALES) >= 80


class TestMarkdownTransformHelpers:
    def test_md_to_translatable_wraps_in_div(self):
        result = _md_to_translatable("# Hello\n\nWorld")
        assert "<div class='skill-body'>" in result
        assert "# Hello" in result

    def test_code_blocks_protected(self):
        md = "Some text\n\n```python\nprint('hello')\n```\n\nMore text"
        result = _md_to_translatable(md)
        assert "<pre><code" in result
        assert "data-i18n-skip" in result

    def test_roundtrip_no_code(self):
        md = "# Hello\n\nThis is a paragraph."
        html = _md_to_translatable(md)
        restored = _translatable_to_md(html)
        assert "# Hello" in restored
        assert "paragraph" in restored

    def test_roundtrip_with_code(self):
        md = "Before\n\n```bash\necho hello\n```\n\nAfter"
        html = _md_to_translatable(md)
        restored = _translatable_to_md(html)
        assert "echo hello" in restored


class TestSkillTranslator:
    def test_init_with_explicit_key(self):
        t = SkillTranslator(api_key="test-key-123")
        assert t.api_key == "test-key-123"

    def test_init_from_env(self, monkeypatch):
        monkeypatch.setenv("LINGODOTDEV_API_KEY", "env-key-456")
        t = SkillTranslator()
        assert t.api_key == "env-key-456"

    def test_default_source_locale(self):
        t = SkillTranslator(api_key="test")
        assert t.source_locale == "en"

    def test_glossary_preserves_technical_terms(self):
        t = SkillTranslator(api_key="test")
        # Key technical terms must be in the glossary (as pass-through)
        for term in ("SKILL.md", "Claude", "MCP", "API", "LLM"):
            assert term in t.AGENT_GLOSSARY
            assert t.AGENT_GLOSSARY[term] == term

    @pytest.mark.asyncio
    async def test_translate_skill_mocked(self):
        """Test translation flow with mocked Lingo.dev engine."""
        mock_engine = AsyncMock()
        mock_engine.__aenter__ = AsyncMock(return_value=mock_engine)
        mock_engine.__aexit__ = AsyncMock(return_value=False)
        mock_engine.localize_object = AsyncMock(return_value={
            "name": "procesamiento-de-pdf",
            "description": "Extrae texto de archivos PDF.",
        })
        mock_engine.localize_html = AsyncMock(
            return_value="<div class='skill-body'># Procesamiento de PDF\n\nContenido.</div>"
        )

        with patch("skill_i18n.translator.LingoDotDevEngine", return_value=mock_engine):
            translator = SkillTranslator(api_key="test-key")
            fm, body = await translator.translate_skill(
                frontmatter_dict={"name": "pdf-processing", "description": "Extract text from PDFs."},
                body="# PDF Processing\n\nContent.",
                target_locale="es",
            )

        assert fm["name"] == "procesamiento-de-pdf"
        assert fm["description"] == "Extrae texto de archivos PDF."
        assert "Procesamiento de PDF" in body
