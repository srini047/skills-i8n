"""
Tests for the Lingo.dev REST API translation engine.

All tests mock httpx.AsyncClient so no real API key is needed.
The two real endpoints under test:
  POST https://api.lingo.dev/process/localize
  POST https://api.lingo.dev/process/recognize
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from skill_i18n.translator import (
    LOCALE_NAMES,
    LINGO_API_BASE,
    LOCALIZE_ENDPOINT,
    RECOGNIZE_ENDPOINT,
    SUPPORTED_LOCALES,
    LingoAPIError,
    SkillTranslator,
    _protect_code_blocks,
    _restore_code_blocks,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_response(json_data: dict, status_code: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.text = str(json_data)
    return resp


def _mock_async_client(response: MagicMock) -> MagicMock:
    client = AsyncMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    client.post = AsyncMock(return_value=response)
    return client


# ---------------------------------------------------------------------------
# Locale metadata
# ---------------------------------------------------------------------------

class TestSupportedLocales:
    def test_common_locales_present(self):
        for code in ("es", "fr", "de", "ja", "zh", "ar", "pt-BR", "ko"):
            assert code in SUPPORTED_LOCALES

    def test_locale_names_cover_all_supported(self):
        for code in SUPPORTED_LOCALES:
            assert code in LOCALE_NAMES, f"Missing locale name for: {code}"

    def test_at_least_80_locales(self):
        assert len(SUPPORTED_LOCALES) >= 80

    def test_api_constants_point_to_correct_base(self):
        assert LINGO_API_BASE == "https://api.lingo.dev"
        assert LOCALIZE_ENDPOINT == "https://api.lingo.dev/process/localize"
        assert RECOGNIZE_ENDPOINT == "https://api.lingo.dev/process/recognize"


# ---------------------------------------------------------------------------
# Code-block protection helpers
# ---------------------------------------------------------------------------

class TestCodeBlockProtection:
    def test_replaces_fenced_blocks_with_placeholders(self):
        md = "Before\n\n```python\nprint('hi')\n```\n\nAfter"
        protected, code_map = _protect_code_blocks(md)
        assert "print('hi')" not in protected
        assert len(code_map) == 1
        assert "<<CODE_BLOCK_0>>" in protected

    def test_multiple_blocks_get_unique_placeholders(self):
        md = "```bash\necho hi\n```\n\nText\n\n```python\npass\n```"
        protected, code_map = _protect_code_blocks(md)
        assert len(code_map) == 2
        assert "<<CODE_BLOCK_0>>" in protected
        assert "<<CODE_BLOCK_1>>" in protected

    def test_restore_roundtrip(self):
        md = "Intro\n\n```js\nconsole.log('x')\n```\n\nOutro"
        protected, code_map = _protect_code_blocks(md)
        restored = _restore_code_blocks(protected, code_map)
        assert restored == md

    def test_no_code_blocks_is_noop(self):
        md = "# Title\n\nJust markdown, no code."
        protected, code_map = _protect_code_blocks(md)
        assert protected == md
        assert code_map == {}

    def test_code_block_content_preserved_after_restore(self):
        md = "```sql\nSELECT * FROM users;\n```"
        protected, code_map = _protect_code_blocks(md)
        restored = _restore_code_blocks(protected, code_map)
        assert "SELECT * FROM users;" in restored


# ---------------------------------------------------------------------------
# SkillTranslator initialisation
# ---------------------------------------------------------------------------

class TestSkillTranslatorInit:
    def test_explicit_api_key(self):
        t = SkillTranslator(api_key="sk-test-123")
        assert t.api_key == "sk-test-123"

    def test_api_key_from_env(self, monkeypatch):
        monkeypatch.setenv("LINGODOTDEV_API_KEY", "env-key-999")
        t = SkillTranslator()
        assert t.api_key == "env-key-999"

    def test_engine_id_from_explicit(self):
        t = SkillTranslator(api_key="k", engine_id="eng_abc123")
        assert t.engine_id == "eng_abc123"

    def test_engine_id_from_env(self, monkeypatch):
        monkeypatch.setenv("LINGODOTDEV_ENGINE_ID", "eng_from_env")
        t = SkillTranslator(api_key="k")
        assert t.engine_id == "eng_from_env"

    def test_engine_id_defaults_to_none(self, monkeypatch):
        monkeypatch.delenv("LINGODOTDEV_ENGINE_ID", raising=False)
        t = SkillTranslator(api_key="k")
        assert t.engine_id is None

    def test_default_source_locale(self):
        t = SkillTranslator(api_key="k")
        assert t.source_locale == "en"

    def test_custom_source_locale(self):
        t = SkillTranslator(api_key="k", source_locale="fr")
        assert t.source_locale == "fr"

    def test_headers_contain_api_key_and_content_type(self):
        t = SkillTranslator(api_key="my-key")
        headers = t._headers()
        assert headers["X-API-Key"] == "my-key"
        assert headers["Content-Type"] == "application/json"


# ---------------------------------------------------------------------------
# /process/localize — internal _localize method
# ---------------------------------------------------------------------------

class TestLocalizeEndpoint:
    @pytest.mark.asyncio
    async def test_calls_correct_endpoint(self):
        mock_resp = _mock_response({"data": {"name": "Hola"}})
        mock_client = _mock_async_client(mock_resp)

        with patch("skill_i18n.translator.httpx.AsyncClient", return_value=mock_client):
            t = SkillTranslator(api_key="test-key")
            await t._localize({"name": "Hello"}, "es")

        call_url = mock_client.post.call_args[0][0]
        assert call_url == LOCALIZE_ENDPOINT

    @pytest.mark.asyncio
    async def test_payload_structure_without_engine_id(self):
        mock_resp = _mock_response({"data": {"greeting": "Hola"}})
        mock_client = _mock_async_client(mock_resp)

        with patch("skill_i18n.translator.httpx.AsyncClient", return_value=mock_client):
            t = SkillTranslator(api_key="key", engine_id=None)
            await t._localize({"greeting": "Hello"}, "es")

        payload = mock_client.post.call_args[1]["json"]
        assert payload["sourceLocale"] == "en"
        assert payload["targetLocale"] == "es"
        assert payload["data"] == {"greeting": "Hello"}
        assert "engineId" not in payload

    @pytest.mark.asyncio
    async def test_payload_includes_engine_id_when_set(self):
        mock_resp = _mock_response({"data": {"greeting": "Hola"}})
        mock_client = _mock_async_client(mock_resp)

        with patch("skill_i18n.translator.httpx.AsyncClient", return_value=mock_client):
            t = SkillTranslator(api_key="key", engine_id="eng_xyz")
            await t._localize({"greeting": "Hello"}, "es")

        payload = mock_client.post.call_args[1]["json"]
        assert payload["engineId"] == "eng_xyz"

    @pytest.mark.asyncio
    async def test_returns_translated_data_dict(self):
        mock_resp = _mock_response({
            "sourceLocale": "en",
            "targetLocale": "de",
            "data": {"title": "Hallo Welt", "desc": "Ein Test"},
        })
        mock_client = _mock_async_client(mock_resp)

        with patch("skill_i18n.translator.httpx.AsyncClient", return_value=mock_client):
            t = SkillTranslator(api_key="key")
            result = await t._localize({"title": "Hello World", "desc": "A test"}, "de")

        assert result == {"title": "Hallo Welt", "desc": "Ein Test"}

    @pytest.mark.asyncio
    async def test_raises_lingo_api_error_on_4xx(self):
        mock_resp = _mock_response({}, status_code=401)
        mock_resp.text = "Unauthorized"
        mock_client = _mock_async_client(mock_resp)

        with patch("skill_i18n.translator.httpx.AsyncClient", return_value=mock_client):
            t = SkillTranslator(api_key="bad-key")
            with pytest.raises(LingoAPIError) as exc_info:
                await t._localize({"k": "v"}, "es")

        assert exc_info.value.status == 401

    @pytest.mark.asyncio
    async def test_raises_lingo_api_error_on_5xx(self):
        mock_resp = _mock_response({}, status_code=500)
        mock_resp.text = "Internal Server Error"
        mock_client = _mock_async_client(mock_resp)

        with patch("skill_i18n.translator.httpx.AsyncClient", return_value=mock_client):
            t = SkillTranslator(api_key="key")
            with pytest.raises(LingoAPIError) as exc_info:
                await t._localize({"k": "v"}, "es")

        assert exc_info.value.status == 500


# ---------------------------------------------------------------------------
# translate_skill — the full skill translation flow
# ---------------------------------------------------------------------------

class TestTranslateSkill:
    @pytest.mark.asyncio
    async def test_translates_frontmatter_and_body(self):
        mock_resp = _mock_response({
            "data": {
                "name": "pdf-verarbeitung",
                "description": "Text aus PDFs extrahieren.",
                "__body__": "# PDF-Verarbeitung\n\nInhalt.",
            }
        })
        mock_client = _mock_async_client(mock_resp)

        with patch("skill_i18n.translator.httpx.AsyncClient", return_value=mock_client):
            t = SkillTranslator(api_key="key")
            fm, body = await t.translate_skill(
                frontmatter_dict={
                    "name": "pdf-processing",
                    "description": "Extract text from PDFs.",
                    "license": "Apache-2.0",
                },
                body="# PDF Processing\n\nContent.",
                target_locale="de",
            )

        assert fm["name"] == "pdf-verarbeitung"
        assert fm["description"] == "Text aus PDFs extrahieren."
        assert "PDF-Verarbeitung" in body

    @pytest.mark.asyncio
    async def test_license_field_excluded_from_api_payload(self):
        mock_resp = _mock_response({
            "data": {
                "name": "habilidad",
                "description": "Una descripción.",
                "__body__": "# Cuerpo",
            }
        })
        mock_client = _mock_async_client(mock_resp)

        with patch("skill_i18n.translator.httpx.AsyncClient", return_value=mock_client):
            t = SkillTranslator(api_key="key")
            await t.translate_skill(
                frontmatter_dict={
                    "name": "skill",
                    "description": "A description.",
                    "license": "Apache-2.0",
                },
                body="# Body",
                target_locale="es",
            )

        payload = mock_client.post.call_args[1]["json"]
        assert "license" not in payload["data"]

    @pytest.mark.asyncio
    async def test_license_preserved_unchanged_in_output(self):
        mock_resp = _mock_response({
            "data": {
                "name": "habilidad",
                "description": "Una descripción.",
                "__body__": "# Cuerpo",
            }
        })
        mock_client = _mock_async_client(mock_resp)

        with patch("skill_i18n.translator.httpx.AsyncClient", return_value=mock_client):
            t = SkillTranslator(api_key="key")
            fm, _ = await t.translate_skill(
                frontmatter_dict={
                    "name": "skill",
                    "description": "A description.",
                    "license": "Apache-2.0",
                },
                body="# Body",
                target_locale="es",
            )

        assert fm["license"] == "Apache-2.0"

    @pytest.mark.asyncio
    async def test_code_blocks_not_sent_to_api(self):
        """Raw code block content must NOT appear in the API request payload."""
        mock_resp = _mock_response({
            "data": {
                "name": "skill",
                "description": "desc.",
                "__body__": "Texto.\n\n<<CODE_BLOCK_0>>\n\nMás texto.",
            }
        })
        mock_client = _mock_async_client(mock_resp)

        with patch("skill_i18n.translator.httpx.AsyncClient", return_value=mock_client):
            t = SkillTranslator(api_key="key")
            _, body = await t.translate_skill(
                frontmatter_dict={"name": "skill", "description": "desc"},
                body="Text.\n\n```python\nprint('secret')\n```\n\nMore text.",
                target_locale="es",
            )

        payload = mock_client.post.call_args[1]["json"]
        assert "print('secret')" not in payload["data"]["__body__"]
        # But the restored body must contain it
        assert "print('secret')" in body

    @pytest.mark.asyncio
    async def test_single_api_request_for_whole_skill(self):
        """All fields go in one request — the engine handles context holistically."""
        mock_resp = _mock_response({
            "data": {
                "name": "habileté",
                "description": "Description.",
                "__body__": "# Corps",
            }
        })
        mock_client = _mock_async_client(mock_resp)

        with patch("skill_i18n.translator.httpx.AsyncClient", return_value=mock_client):
            t = SkillTranslator(api_key="key")
            await t.translate_skill(
                frontmatter_dict={"name": "skill", "description": "A description."},
                body="# Body",
                target_locale="fr",
            )

        assert mock_client.post.call_count == 1

    @pytest.mark.asyncio
    async def test_body_and_frontmatter_sent_together_in_data(self):
        """Body (__body__) and frontmatter fields share the same data object."""
        mock_resp = _mock_response({
            "data": {
                "name": "スキル",
                "description": "説明。",
                "__body__": "# 本文",
            }
        })
        mock_client = _mock_async_client(mock_resp)

        with patch("skill_i18n.translator.httpx.AsyncClient", return_value=mock_client):
            t = SkillTranslator(api_key="key")
            await t.translate_skill(
                frontmatter_dict={"name": "skill", "description": "A description."},
                body="# Body",
                target_locale="ja",
            )

        payload = mock_client.post.call_args[1]["json"]
        assert "name" in payload["data"]
        assert "description" in payload["data"]
        assert "__body__" in payload["data"]


# ---------------------------------------------------------------------------
# /process/recognize
# ---------------------------------------------------------------------------

class TestRecognizeEndpoint:
    @pytest.mark.asyncio
    async def test_calls_recognize_endpoint(self):
        mock_resp = _mock_response({
            "locale": "fr",
            "language": "fr",
            "region": None,
            "script": None,
            "label": "French",
            "direction": "ltr",
        })
        mock_client = _mock_async_client(mock_resp)

        with patch("skill_i18n.translator.httpx.AsyncClient", return_value=mock_client):
            t = SkillTranslator(api_key="key")
            locale = await t.detect_locale("Bonjour le monde")

        call_url = mock_client.post.call_args[0][0]
        assert call_url == RECOGNIZE_ENDPOINT
        assert locale == "fr"

    @pytest.mark.asyncio
    async def test_recognize_payload_structure(self):
        mock_resp = _mock_response({
            "locale": "de", "language": "de", "label": "German", "direction": "ltr"
        })
        mock_client = _mock_async_client(mock_resp)

        with patch("skill_i18n.translator.httpx.AsyncClient", return_value=mock_client):
            t = SkillTranslator(api_key="key")
            await t.detect_locale("Guten Tag")

        payload = mock_client.post.call_args[1]["json"]
        assert payload["text"] == "Guten Tag"
        assert payload["labelLocale"] == "en"

    @pytest.mark.asyncio
    async def test_returns_full_bcp47_for_regional_variant(self):
        mock_resp = _mock_response({
            "locale": "pt-BR",
            "language": "pt",
            "region": "BR",
            "label": "Portuguese (Brazil)",
            "direction": "ltr",
        })
        mock_client = _mock_async_client(mock_resp)

        with patch("skill_i18n.translator.httpx.AsyncClient", return_value=mock_client):
            t = SkillTranslator(api_key="key")
            locale = await t.detect_locale("Olá mundo, tudo bem?")

        assert locale == "pt-BR"

    @pytest.mark.asyncio
    async def test_recognize_api_error_raises(self):
        mock_resp = _mock_response({}, status_code=403)
        mock_resp.text = "Forbidden"
        mock_client = _mock_async_client(mock_resp)

        with patch("skill_i18n.translator.httpx.AsyncClient", return_value=mock_client):
            t = SkillTranslator(api_key="bad")
            with pytest.raises(LingoAPIError) as exc_info:
                await t.detect_locale("Hello")

        assert exc_info.value.status == 403
