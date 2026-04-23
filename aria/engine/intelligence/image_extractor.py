"""
Image Extractor — pulls image URLs from collected documents.

Two modes:
  1. HTML parsing: extract <img> src + alt from raw HTML or text
  2. Vision captioning: optional LLM describe of each image (requires API key)

Filters out icons, tracking pixels, and tiny images by URL heuristics.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Optional
from urllib.parse import urljoin, urlparse

logger = logging.getLogger("aria")

# URL patterns that indicate non-content images
_NOISE_PATTERNS = re.compile(
    r"(icon|logo|avatar|badge|pixel|tracker|analytics|beacon|spacer|"
    r"loading|spinner|placeholder|\.gif|adserv|doubleclick|googleadserv)",
    re.IGNORECASE,
)

# Likely content image extensions
_IMG_EXTENSIONS = re.compile(r"\.(jpg|jpeg|png|webp|svg|avif)(\?|$)", re.IGNORECASE)

_IMG_TAG_RE = re.compile(
    r'<img[^>]+src=["\']([^"\']+)["\'][^>]*(?:alt=["\']([^"\']*)["\'])?[^>]*>',
    re.IGNORECASE,
)
_ALT_RE = re.compile(r'alt=["\']([^"\']*)["\']', re.IGNORECASE)

# OG / Twitter card images from meta tags
_META_IMAGE_RE = re.compile(
    r'<meta[^>]+(?:property=["\']og:image["\']|name=["\']twitter:image["\'])'
    r'[^>]+content=["\']([^"\']+)["\']',
    re.IGNORECASE,
)
_META_IMAGE_RE2 = re.compile(
    r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+'
    r'(?:property=["\']og:image["\']|name=["\']twitter:image["\'])',
    re.IGNORECASE,
)

# Figure captions
_FIGCAPTION_RE = re.compile(
    r'<figcaption[^>]*>(.*?)</figcaption>',
    re.IGNORECASE | re.DOTALL,
)
_HTML_TAG_RE = re.compile(r"<[^>]+>")


def extract_images_from_doc(
    doc: dict[str, Any],
    max_images: int = 10,
) -> list[dict[str, Any]]:
    """
    Extract images from a single document.

    Returns list of image dicts:
      { url, alt_text, caption, source_url, source_title }
    """
    raw_html = doc.get("raw_html") or doc.get("html") or doc.get("text") or ""
    source_url = doc.get("url", "")
    source_title = doc.get("title", "")

    images: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    # ── 1. OG / Twitter card images (highest priority) ────────────────────────
    for pattern in (_META_IMAGE_RE, _META_IMAGE_RE2):
        for m in pattern.finditer(raw_html):
            url = _resolve_url(m.group(1).strip(), source_url)
            if url and url not in seen_urls and _is_content_image(url):
                seen_urls.add(url)
                images.append({
                    "url": url,
                    "alt_text": "",
                    "caption": "",
                    "source_url": source_url,
                    "source_title": source_title,
                    "image_type": "og_card",
                })

    # ── 2. <img> tags ────────────────────────────────────────────────────────
    # Build figcaption map: try to associate with nearby images
    captions = [
        _HTML_TAG_RE.sub("", c.group(1)).strip()
        for c in _FIGCAPTION_RE.finditer(raw_html)
    ]
    cap_idx = 0

    for m in _IMG_TAG_RE.finditer(raw_html):
        if len(images) >= max_images:
            break
        url = _resolve_url(m.group(1).strip(), source_url)
        if not url or url in seen_urls or not _is_content_image(url):
            continue

        # Extract alt from full tag (group 2 may miss if alt comes before src)
        full_tag = m.group(0)
        alt_m = _ALT_RE.search(full_tag)
        alt = alt_m.group(1).strip() if alt_m else ""

        caption = captions[cap_idx] if cap_idx < len(captions) else ""
        if caption:
            cap_idx += 1

        seen_urls.add(url)
        images.append({
            "url": url,
            "alt_text": alt,
            "caption": caption,
            "source_url": source_url,
            "source_title": source_title,
            "image_type": "inline",
        })

    return images[:max_images]


def extract_images_from_docs(
    docs: list[dict[str, Any]],
    max_total: int = 50,
    max_per_doc: int = 5,
) -> list[dict[str, Any]]:
    """
    Extract images from a collection of documents.
    Returns deduplicated list of image dicts.
    """
    all_images: list[dict[str, Any]] = []
    seen: set[str] = set()

    for doc in docs:
        if len(all_images) >= max_total:
            break
        doc_images = extract_images_from_doc(doc, max_images=max_per_doc)
        for img in doc_images:
            url = img["url"]
            if url not in seen:
                seen.add(url)
                all_images.append(img)
                if len(all_images) >= max_total:
                    break

    logger.info("Image extractor: found %d unique images across %d docs", len(all_images), len(docs))
    return all_images


async def caption_images_with_vision(
    images: list[dict[str, Any]],
    topic: str,
    max_to_caption: int = 5,
) -> list[dict[str, Any]]:
    """
    Optionally use vision-capable LLM to generate captions for images.
    Only captions images that lack alt_text/caption already.
    Requires ANTHROPIC_API_KEY (claude-3-haiku has vision).

    Modifies images in place, returns same list.
    """
    import os
    ant_key = os.getenv("ANTHROPIC_API_KEY")
    if not ant_key:
        logger.debug("Vision captioning skipped — no ANTHROPIC_API_KEY")
        return images

    to_caption = [
        img for img in images
        if not img.get("alt_text") and not img.get("caption")
    ][:max_to_caption]

    if not to_caption:
        return images

    try:
        import httpx
        import base64

        async with httpx.AsyncClient(timeout=15.0) as client:
            for img in to_caption:
                try:
                    resp = await client.get(img["url"], follow_redirects=True)
                    if resp.status_code != 200:
                        continue
                    content_type = resp.headers.get("content-type", "image/jpeg")
                    if "image" not in content_type:
                        continue
                    b64 = base64.standard_b64encode(resp.content).decode()

                    # Vision API call
                    caption = await _vision_caption(b64, content_type, topic, ant_key)
                    if caption:
                        img["caption"] = caption
                        logger.debug("Captioned image: %s → %s", img["url"][:60], caption[:80])
                except Exception as exc:
                    logger.debug("Vision caption failed for %s: %s", img["url"][:60], exc)

    except ImportError:
        logger.debug("httpx not available for vision captioning")
    except Exception as exc:
        logger.debug("Vision captioning batch failed: %s", exc)

    return images


async def _vision_caption(
    b64_image: str,
    media_type: str,
    topic: str,
    api_key: str,
) -> Optional[str]:
    """Call Anthropic vision to caption one image."""
    try:
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=api_key)
        msg = await client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=150,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type.split(";")[0].strip(),
                            "data": b64_image,
                        },
                    },
                    {
                        "type": "text",
                        "text": (
                            f"This image is from a research document about '{topic}'. "
                            "Describe what this image shows in 1-2 sentences, "
                            "focusing on research-relevant content."
                        ),
                    },
                ],
            }],
        )
        return msg.content[0].text.strip() if msg.content else None
    except Exception as exc:
        logger.debug("Anthropic vision call failed: %s", exc)
        return None


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _resolve_url(url: str, base_url: str) -> str:
    """Resolve relative URLs against the document's base URL."""
    if not url:
        return ""
    if url.startswith("data:"):
        return ""  # skip inline data URLs
    if url.startswith("//"):
        url = "https:" + url
    elif not url.startswith("http"):
        try:
            url = urljoin(base_url, url)
        except Exception:
            return ""
    return url


def _is_content_image(url: str) -> bool:
    """Return True if URL looks like a real content image (not icon/tracker)."""
    if _NOISE_PATTERNS.search(url):
        return False
    # Must have image-like extension or path segment
    parsed = urlparse(url)
    path = parsed.path.lower()
    if _IMG_EXTENSIONS.search(path):
        return True
    # Allow URLs with image in path but no extension (CDN pattern)
    if any(seg in path for seg in ["/image", "/photo", "/media", "/img", "/figure"]):
        return True
    return False
