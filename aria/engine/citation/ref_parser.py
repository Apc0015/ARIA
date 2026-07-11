"""Reference list parser — converts raw formatted reference strings into structured records.

Handles author-date style references (APA/Harvard) as used in Scientia Militaria
and most social science / military studies journals.

Usage::

    from aria.engine.citation.ref_parser import ReferenceParser

    parser = ReferenceParser()
    records = parser.parse_list(raw_text_block)
    # Each record is a RefRecord TypedDict
"""

from __future__ import annotations

import re
from typing import Any, TypedDict


# ---------------------------------------------------------------------------
# Output schema
# ---------------------------------------------------------------------------

class RefRecord(TypedDict, total=False):
    """Structured representation of a single bibliographic reference."""
    raw: str                   # original string, unmodified
    authors_raw: str           # author string as it appeared
    authors: list[str]         # normalised list: ["Last, F.M.", ...]
    year: str                  # 4-digit year, e.g. "2024" or "2024a"
    title: str
    journal: str
    volume: str
    issue: str
    pages: str
    publisher: str
    place: str
    url: str
    doi: str
    ref_type: str              # journal_article | book | book_chapter | report | web | unknown
    parse_notes: list[str]     # flags / warnings for downstream consumers


# ---------------------------------------------------------------------------
# Compiled patterns
# ---------------------------------------------------------------------------

# Year — 4-digit optionally followed by a/b/c suffix
_YEAR_RE = re.compile(r'\b((?:19|20)\d{2}[a-z]?)\b')

# DOI embedded in reference string
_DOI_RE = re.compile(r'10\.\d{4,9}/[^\s<>"\']+', re.IGNORECASE)

# URL
_URL_RE = re.compile(r'https?://[^\s<>"\']+')

# Journal volume(issue):pages  e.g.  42(2):151-183  or  42(2): 151-183
_VOL_ISSUE_PAGES_RE = re.compile(
    r'\b(\d+)\((\d+)\)[:\s]*([\d\-–]+)'
)

# Volume without issue:  vol. 52  /  52:61-89
_VOL_PAGES_RE = re.compile(
    r'\b(\d+)[:\s]+([\d\-–]+)\b'
)

# "pp. 233-282" or "p. 40" or ": 61-89"
_PAGES_RE = re.compile(r'pp?\.\s*([\d\-–]+)')

# "In ... (eds.)" — book chapter signal
_CHAPTER_RE = re.compile(r'\bIn\b.{5,80}\beds?\.?\)', re.IGNORECASE)

# Publisher patterns at end of reference
_PUBLISHER_RE = re.compile(
    r'(?:[:.])\s*([A-Z][^:\.]+(?:Press|Publisher|Books|University|Institute|'
    r'Scarecrow|Mouton|Routledge|Sage|Springer|Wiley|Elsevier|'
    r'Princeton|Oxford|Cambridge|MIT|Columbia|Johns Hopkins)[^\.]*)',
    re.IGNORECASE
)

# Place: Publisher  e.g.  "London: Routledge"  "Lanham, MD: Scarecrow Press"
_PLACE_PUBLISHER_RE = re.compile(
    r'([A-Z][a-zA-Z\s,]+?):\s*([A-Z][^\.]+(?:Press|Publisher|Books|University|'
    r'Institute|Scarecrow|Mouton|Routledge|Sage|Springer|Wiley|Elsevier|'
    r'Princeton|Oxford|Cambridge|MIT|Columbia|Heath)[^\.]*)',
    re.IGNORECASE
)

# "Retrieved from <url>" or "Retrieved from: url"
_RETRIEVED_RE = re.compile(r'[Rr]etrieved from\s*<?(\S+)>?')

# "Accessed dd Month yyyy" / "[Accessed 27 September 2024]"
_ACCESSED_RE = re.compile(r'\[?[Aa]ccessed[^\]]*?\]?\.?\s*$')


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clean(text: str) -> str:
    """Strip markdown artifacts, extra whitespace, and HTML."""
    text = re.sub(r'!\[.*?\]\(.*?\)', '', text)          # markdown images
    text = re.sub(r'\[([^\]]+)\]\([^)]*\)', r'\1', text)  # markdown links → text
    text = re.sub(r'\*+([^*]+)\*+', r'\1', text)          # bold/italic
    text = re.sub(r'<[^>]+>', '', text)                    # HTML tags
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def _split_authors(raw: str) -> list[str]:
    """Split an author string into individual names.

    Handles:
    - "Last, F.M. & Other, J."
    - "Last, First, Second, Third & Fourth, J."
    - "Org Name" (single institutional author)
    """
    if not raw:
        return []
    # Replace ' and ' with ' & '
    raw = re.sub(r'\s+and\s+', ' & ', raw, flags=re.IGNORECASE)
    parts = re.split(r'\s*&\s*', raw)
    authors = []
    for p in parts:
        p = p.strip().rstrip('.,')
        if p:
            authors.append(p)
    return authors


def _extract_url(text: str) -> str:
    """Extract the best URL from a reference string."""
    # Prefer "Retrieved from" URL
    m = _RETRIEVED_RE.search(text)
    if m:
        url = m.group(1).rstrip('.,>)')
        return url
    # Fall back to any URL
    m = _URL_RE.search(text)
    if m:
        return m.group(0).rstrip('.,>)')
    return ''


def _extract_doi(text: str) -> str:
    m = _DOI_RE.search(text)
    if m:
        return m.group(0).rstrip('.,)')
    return ''


def _determine_type(raw: str, has_journal: bool, has_url: bool) -> str:
    if _CHAPTER_RE.search(raw):
        return 'book_chapter'
    if has_journal:
        return 'journal_article'
    if re.search(r'\b(Press|Publisher|Books|University Press|Scarecrow|Routledge|'
                 r'Mouton|MIT Press|Princeton University|Oxford University|'
                 r'Cambridge University|Sage|Springer|Wiley)\b', raw, re.IGNORECASE):
        return 'book'
    if has_url or re.search(r'\b(Retrieved|Accessed|report|policy|press release)\b',
                             raw, re.IGNORECASE):
        return 'web_report'
    return 'unknown'


# ---------------------------------------------------------------------------
# Core parser
# ---------------------------------------------------------------------------

class ReferenceParser:
    """Parse raw reference strings into structured RefRecord dicts."""

    def parse_one(self, raw: str) -> RefRecord:
        """Parse a single raw reference string."""
        text = _clean(raw)
        notes: list[str] = []

        rec: RefRecord = {
            'raw': raw,
            'authors_raw': '',
            'authors': [],
            'year': '',
            'title': '',
            'journal': '',
            'volume': '',
            'issue': '',
            'pages': '',
            'publisher': '',
            'place': '',
            'url': '',
            'doi': '',
            'ref_type': 'unknown',
            'parse_notes': notes,
        }

        # --- URL & DOI ---
        rec['url'] = _extract_url(text)
        rec['doi'] = _extract_doi(text)

        # --- Year ---
        year_m = _YEAR_RE.search(text)
        if year_m:
            rec['year'] = year_m.group(1)
            author_block = text[:year_m.start()].strip().rstrip('.,')
            rec['authors_raw'] = author_block
            rec['authors'] = _split_authors(author_block)
            after_year = text[year_m.end():].strip().lstrip('.,: ')
        else:
            notes.append('no_year_found')
            after_year = text

        # --- Remove "Retrieved from ..." and "[Accessed ...]" from body ---
        body = _ACCESSED_RE.sub('', after_year).strip()
        body = _RETRIEVED_RE.sub('', body).strip()
        body = re.sub(r'https?://\S+', '', body).strip()

        # --- Volume / Issue / Pages ---
        vip = _VOL_ISSUE_PAGES_RE.search(body)
        if vip:
            rec['volume'] = vip.group(1)
            rec['issue'] = vip.group(2)
            rec['pages'] = vip.group(3).replace('–', '-')
            # Journal name is before the volume pattern
            before_vip = body[:vip.start()].strip().rstrip('.,')
            # Title ends at the last period or comma before journal
            # Heuristic: find last sentence-ender before journal
            title_journal = _split_title_journal(before_vip)
            rec['title'] = title_journal['title']
            rec['journal'] = title_journal['journal']
        else:
            # Try pages only
            pages_m = _PAGES_RE.search(body)
            if pages_m:
                rec['pages'] = pages_m.group(1)

            # Try vol:pages without issue
            vp = _VOL_PAGES_RE.search(body)
            if vp and not rec['pages']:
                rec['volume'] = vp.group(1)
                rec['pages'] = vp.group(2)

            # Title = first sentence / up to period
            if not rec['title']:
                rec['title'] = _extract_title(body)

        # --- Publisher / Place ---
        pp = _PLACE_PUBLISHER_RE.search(body)
        if pp:
            rec['place'] = pp.group(1).strip().rstrip(',')
            rec['publisher'] = pp.group(2).strip().rstrip('.')
        else:
            pub = _PUBLISHER_RE.search(body)
            if pub:
                rec['publisher'] = pub.group(1).strip().rstrip('.')

        # --- Type ---
        rec['ref_type'] = _determine_type(
            text,
            has_journal=bool(rec['journal']),
            has_url=bool(rec['url']),
        )

        # --- Fallback title from body if still empty ---
        if not rec['title'] and body:
            rec['title'] = body[:200].rstrip('.,')
            notes.append('title_fallback')

        # Truncate overly long titles (parse artifact)
        if len(rec['title']) > 300:
            rec['title'] = rec['title'][:300]
            notes.append('title_truncated')

        return rec

    def parse_list(self, raw_refs: list[str]) -> list[RefRecord]:
        """Parse a list of raw reference strings."""
        return [self.parse_one(r) for r in raw_refs]

    def parse_text_block(self, block: str) -> list[RefRecord]:
        """Split a raw reference section text into individual references and parse each.

        Splits on blank lines or on lines that start a new author-year pattern.
        """
        lines = block.splitlines()
        entries: list[str] = []
        current: list[str] = []

        for line in lines:
            line = line.strip()
            if not line:
                if current:
                    entries.append(' '.join(current))
                    current = []
                continue
            # A new reference starts when a line begins with an uppercase word
            # followed eventually by a year — but only if we have content already
            if current and _looks_like_new_ref(line):
                entries.append(' '.join(current))
                current = [line]
            else:
                current.append(line)

        if current:
            entries.append(' '.join(current))

        # Filter junk (too short, no year)
        valid = [e for e in entries if len(e) > 30 and _YEAR_RE.search(e)]
        return self.parse_list(valid)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _looks_like_new_ref(line: str) -> bool:
    """Heuristic: does this line start a new bibliographic entry?"""
    # Starts with capital letter word (author last name or org)
    if not line or not line[0].isupper():
        return False
    # Contains a year somewhere in the first 120 chars
    if _YEAR_RE.search(line[:120]):
        return True
    return False


def _split_title_journal(text: str) -> dict[str, str]:
    """Given text before volume/issue/pages, split into title and journal.

    Strategy: journal name is typically the last italicised element or
    the last comma-separated segment that looks like a journal name.
    We use a simple heuristic: last sentence = journal; everything before = title.
    """
    text = text.strip().rstrip('.,')
    # Split on '. ' to find sentence boundaries
    parts = re.split(r'\.\s+', text)
    if len(parts) >= 2:
        # Last part is the journal, everything before is the title
        journal = parts[-1].strip()
        title = '. '.join(parts[:-1]).strip().rstrip('.,')
        return {'title': title, 'journal': journal}
    # Fall back: split on last comma
    idx = text.rfind(',')
    if idx > 0:
        return {'title': text[:idx].strip(), 'journal': text[idx+1:].strip()}
    return {'title': text, 'journal': ''}


def _extract_title(text: str) -> str:
    """Extract a title from body text when no journal/volume info found."""
    # Remove publisher/place info
    text = _PLACE_PUBLISHER_RE.sub('', text).strip()
    text = _PUBLISHER_RE.sub('', text).strip()
    # Take first sentence
    m = re.match(r'^([^.]+\.)', text)
    if m:
        return m.group(1).rstrip('.,').strip()
    # Take up to first comma or 120 chars
    return text[:150].rstrip('.,').strip()
