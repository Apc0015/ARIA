# Credentials

This directory is gitignored except for this file and `example.json`.

Copy `example.json` to `credentials.json` and fill in only the platforms you use. ARIA silently skips any source whose credentials are missing.

## credentials.json format

```json
{
  "platforms": {
    "twitter": {
      "bearer_token": ""
    },
    "linkedin": {
      "email": "",
      "password": ""
    },
    "notion": {
      "token": ""
    },
    "slack": {
      "token": ""
    },
    "vimeo": {
      "access_token": ""
    },
    "zotero": {
      "api_key": "",
      "library_id": "",
      "library_type": "user"
    },
    "ieee": {
      "username": "",
      "password": ""
    },
    "acm": {
      "username": "",
      "password": ""
    },
    "springer": {
      "api_key": ""
    },
    "elsevier": {
      "api_key": "",
      "institution_token": ""
    },
    "jstor": {
      "username": "",
      "password": ""
    },
    "university_library": {
      "proxy_url": "",
      "username": "",
      "password": ""
    }
  }
}
```

## Environment variable equivalents

All credentials can also be set via environment variables in your `.env` file:

```env
# Web sources
TWITTER_BEARER_TOKEN=
SERPAPI_KEY=

# LLM providers
OPENROUTER_API_KEY=
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
MISTRAL_API_KEY=
GOOGLE_API_KEY=
TOGETHER_API_KEY=

# Zotero
ZOTERO_API_KEY=
ZOTERO_LIBRARY_ID=
ZOTERO_LIBRARY_TYPE=user     # user | group

# Academic
UNPAYWALL_EMAIL=
CORE_API_KEY=
```

Environment variables take precedence over the credentials JSON file.

## Zotero setup

**Local mode** (recommended for desktop users):
- Install Zotero desktop from [zotero.org](https://www.zotero.org)
- No API key needed — ARIA connects to the local Zotero app on `localhost:23119`
- Enable the Zotero source in the UI and select "Local app"

**Cloud mode**:
1. Log in at [zotero.org](https://www.zotero.org)
2. Go to **Settings → Feeds/API → Create new private key**
3. Grant "Allow library access"
4. Copy your **API key** and **User ID** (shown on the same page)
5. Set `ZOTERO_API_KEY` and `ZOTERO_LIBRARY_ID` in your `.env`, or paste into the ARIA UI

To find a **collection key**: open Zotero, right-click a collection → "Copy Collection Link". The key is the last segment of the URL (`zotero://select/library/collections/ABC123EF` → `ABC123EF`).

## Session cache

`credentials/sessions/` stores cached browser sessions for Playwright-based sources (LinkedIn). These are also gitignored and are reused across runs to avoid repeated logins.
