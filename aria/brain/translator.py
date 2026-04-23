"""Translation helpers — LLM-based with deep_translator fallback."""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger("aria")

_ENGLISH_CODES = {"en", "en-us", "en-gb", "en-au", "en-ca"}


def translate_text(
    text: str,
    source_language: Optional[str] = None,
    target_language: str = "en",
) -> str:
    """Translate text to the target language.

    Translation priority:
    1. Skip if source == target (or source is English variant)
    2. Try deep_translator (GoogleTranslator) — fast, no API key
    3. Fall back to returning original text with a warning

    For large texts only the first 8000 chars are translated to stay within
    free-tier limits; the remainder is appended untranslated.

    Args:
        text: Input text to translate.
        source_language: ISO 639-1 language code (e.g. 'de', 'fr').
                         Pass None to auto-detect.
        target_language: Target language code (default 'en').

    Returns:
        Translated text, or original if translation is unavailable.
    """
    if not text or not text.strip():
        return text

    src = (source_language or "auto").lower().strip()
    tgt = target_language.lower().strip()

    if src in _ENGLISH_CODES and tgt == "en":
        return text
    if src == tgt:
        return text

    truncated = len(text) > 8000
    text_to_translate = text[:8000] if truncated else text
    remainder = text[8000:] if truncated else ""

    translated = _try_deep_translator(text_to_translate, src, tgt)
    if translated:
        return (translated + "\n\n" + remainder).strip() if remainder else translated

    logger.warning(
        "translator: could not translate from '%s' to '%s' — "
        "install deep_translator: pip install deep-translator",
        src,
        tgt,
    )
    return text


def _try_deep_translator(text: str, source: str, target: str) -> Optional[str]:
    """Attempt translation via deep_translator (GoogleTranslator)."""
    try:
        from deep_translator import GoogleTranslator

        # deep_translator uses "auto" for auto-detect
        src = source if source != "auto" else "auto"

        translator = GoogleTranslator(source=src, target=target)
        result = translator.translate(text)
        if result and result.strip():
            return result.strip()
        return None

    except ImportError:
        return None  # package not installed — fall through
    except Exception as exc:
        logger.debug("deep_translator error: %s", exc)
        return None


def is_translation_available() -> bool:
    """Return True if at least one translation backend is available."""
    try:
        from deep_translator import GoogleTranslator  # noqa: F401
        return True
    except ImportError:
        return False
