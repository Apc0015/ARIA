"""Browser session manager — uses Playwright to authenticate users on real platforms."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger("aria")

# Where to persist login cookies so users don't re-login every time
_SESSIONS_DIR = Path(os.getenv("ARIA_DATA_DIR", str(Path.home() / ".aria"))) / "sessions"


class BrowserSessionManager:
    """Manages authenticated browser sessions for platforms that require login.

    Uses Playwright to:
    1. Open a real Chromium browser
    2. Log in with the user's credentials
    3. Extract session cookies
    4. Persist cookies to disk so future requests reuse the session
    5. Provide authenticated httpx sessions for collectors
    """

    def __init__(self) -> None:
        _SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
        self._cookies: dict[str, list[dict]] = {}  # platform -> cookie list
        self._load_saved_sessions()

    def _cookie_path(self, platform: str) -> Path:
        return _SESSIONS_DIR / f"{platform}_cookies.json"

    def _load_saved_sessions(self) -> None:
        """Load previously saved cookies from disk."""
        for path in _SESSIONS_DIR.glob("*_cookies.json"):
            platform = path.stem.replace("_cookies", "")
            try:
                data = json.loads(path.read_text())
                self._cookies[platform] = data
                logger.debug("SessionManager: loaded saved session for %s", platform)
            except Exception:
                pass

    def _save_session(self, platform: str, cookies: list[dict]) -> None:
        """Persist cookies to disk."""
        self._cookies[platform] = cookies
        try:
            self._cookie_path(platform).write_text(json.dumps(cookies, indent=2))
        except Exception as exc:
            logger.debug("SessionManager: could not save session for %s: %s", platform, exc)

    def has_session(self, platform: str) -> bool:
        return bool(self._cookies.get(platform))

    def get_cookies_header(self, platform: str) -> str:
        """Return cookies as a Cookie header string for httpx requests."""
        cookies = self._cookies.get(platform, [])
        return "; ".join(f"{c['name']}={c['value']}" for c in cookies)

    def get_cookies_dict(self, platform: str) -> dict[str, str]:
        """Return cookies as a dict for httpx."""
        return {c["name"]: c["value"] for c in self._cookies.get(platform, [])}

    def clear_session(self, platform: str) -> None:
        self._cookies.pop(platform, None)
        path = self._cookie_path(platform)
        if path.exists():
            path.unlink()

    async def login(self, platform: str, credentials: dict) -> dict:
        """Attempt browser login for a platform.

        Returns:
            Dict with keys: success (bool), message (str), cookies_saved (bool)
        """
        handlers = {
            "reddit":    self._login_reddit,
            "linkedin":  self._login_linkedin,
            "twitter":   self._login_twitter,
            "medium":    self._login_medium,
            "substack":  self._login_substack,
            "ieee":      self._login_ieee,
            "springer":  self._login_springer,
            "elsevier":  self._login_elsevier,
            "jstor":     self._login_jstor,
            "notion":    self._validate_notion_token,
            "slack":     self._validate_slack_token,
            "vimeo":     self._validate_vimeo_token,
            "zotero":    self._validate_zotero_token,
        }
        handler = handlers.get(platform)
        if not handler:
            return {"success": False, "message": f"No login handler for platform: {platform}"}
        try:
            return await handler(credentials)
        except Exception as exc:
            logger.warning("SessionManager: login failed for %s: %s", platform, exc)
            return {"success": False, "message": str(exc)}

    # ── Reddit ──────────────────────────────────────────────────────────────

    async def _login_reddit(self, credentials: dict) -> dict:
        """Login to Reddit via official API (PRAW) or browser fallback."""
        username = credentials.get("username", "")
        password = credentials.get("password", "")
        client_id = credentials.get("client_id", "")
        client_secret = credentials.get("client_secret", "")

        if client_id and client_secret and username and password:
            # Use PRAW (official Reddit API — best approach)
            try:
                import praw
                reddit = praw.Reddit(
                    client_id=client_id,
                    client_secret=client_secret,
                    username=username,
                    password=password,
                    user_agent=f"ARIA Research Collector/1.0 by u/{username}",
                )
                # Verify by accessing user info
                me = reddit.user.me()
                if me:
                    os.environ["REDDIT_CLIENT_ID"] = client_id
                    os.environ["REDDIT_CLIENT_SECRET"] = client_secret
                    os.environ["REDDIT_USERNAME"] = username
                    os.environ["REDDIT_PASSWORD"] = password
                    return {
                        "success": True,
                        "message": f"Reddit authenticated via API as u/{me.name}",
                        "username": me.name,
                        "method": "praw_api",
                        "cookies_saved": False,
                    }
            except Exception as exc:
                logger.debug("PRAW login failed: %s", exc)

        # Fallback: Reddit public API works without auth for most data
        if username:
            os.environ["REDDIT_USERNAME"] = username
        return {
            "success": True,
            "message": "Reddit connected (public API — provide client_id/client_secret for full access)",
            "method": "public_api",
            "cookies_saved": False,
        }

    # ── LinkedIn ─────────────────────────────────────────────────────────────

    async def _login_linkedin(self, credentials: dict) -> dict:
        """Login to LinkedIn via Playwright browser automation."""
        email = credentials.get("username") or credentials.get("email", "")
        password = credentials.get("password", "")
        if not email or not password:
            return {"success": False, "message": "LinkedIn requires email and password"}

        try:
            from playwright.async_api import async_playwright, TimeoutError as PWTimeout

            async with async_playwright() as pw:
                browser = await pw.chromium.launch(headless=True)
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    viewport={"width": 1280, "height": 800},
                )
                page = await context.new_page()

                await page.goto("https://www.linkedin.com/login", wait_until="networkidle", timeout=30000)
                await asyncio.sleep(1.5)

                await page.fill("#username", email)
                await asyncio.sleep(0.5)
                await page.fill("#password", password)
                await asyncio.sleep(0.5)
                await page.click('[data-litms-control-urn="login-submit"]')

                try:
                    await page.wait_for_url("**/feed/**", timeout=15000)
                except PWTimeout:
                    # Check if we're on a verification/captcha page
                    url = page.url
                    if "checkpoint" in url or "challenge" in url:
                        await browser.close()
                        return {
                            "success": False,
                            "message": "LinkedIn requires verification (CAPTCHA or email/SMS code). Try again or use a less bot-detected network.",
                        }
                    if "login" in url:
                        await browser.close()
                        return {"success": False, "message": "LinkedIn login failed — check your email and password"}

                # Success — save cookies
                cookies = await context.cookies()
                await browser.close()
                self._save_session("linkedin", cookies)
                os.environ["LINKEDIN_EMAIL"] = email

                return {
                    "success": True,
                    "message": f"LinkedIn authenticated as {email}",
                    "method": "browser_session",
                    "cookies_saved": True,
                }
        except ImportError:
            return {"success": False, "message": "Playwright not installed"}
        except Exception as exc:
            return {"success": False, "message": f"LinkedIn login error: {exc}"}

    # ── Twitter / X ──────────────────────────────────────────────────────────

    async def _login_twitter(self, credentials: dict) -> dict:
        """Login to Twitter/X — bearer token preferred, browser fallback."""
        token = credentials.get("token") or credentials.get("api_key", "")
        username = credentials.get("username", "")
        password = credentials.get("password", "")

        if token:
            # Validate bearer token
            try:
                import httpx
                async with httpx.AsyncClient(timeout=10) as client:
                    resp = await client.get(
                        "https://api.twitter.com/2/users/me",
                        headers={"Authorization": f"Bearer {token}"},
                    )
                if resp.status_code == 200:
                    user = resp.json().get("data", {})
                    os.environ["TWITTER_BEARER_TOKEN"] = token
                    return {
                        "success": True,
                        "message": f"Twitter connected as @{user.get('username', 'unknown')}",
                        "method": "bearer_token",
                        "cookies_saved": False,
                    }
                elif resp.status_code == 401:
                    return {"success": False, "message": "Invalid Twitter Bearer Token"}
            except Exception as exc:
                logger.debug("Twitter token validation error: %s", exc)

        if username and password:
            # Browser login for cookie-based access
            try:
                from playwright.async_api import async_playwright, TimeoutError as PWTimeout

                async with async_playwright() as pw:
                    browser = await pw.chromium.launch(headless=True)
                    context = await browser.new_context(
                        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                    )
                    page = await context.new_page()

                    await page.goto("https://twitter.com/login", wait_until="networkidle", timeout=30000)
                    await asyncio.sleep(2)

                    # Enter username
                    await page.fill('input[autocomplete="username"]', username)
                    await page.keyboard.press("Enter")
                    await asyncio.sleep(1.5)

                    # Sometimes Twitter asks for phone/email verification step
                    try:
                        verify_input = await page.wait_for_selector('input[data-testid="ocfEnterTextTextInput"]', timeout=3000)
                        if verify_input:
                            await browser.close()
                            return {
                                "success": False,
                                "message": "Twitter requires additional verification (phone/email code). Use a Bearer Token instead.",
                            }
                    except PWTimeout:
                        pass

                    # Enter password
                    await page.fill('input[name="password"]', password)
                    await page.keyboard.press("Enter")

                    try:
                        await page.wait_for_url("**/home", timeout=15000)
                        cookies = await context.cookies()
                        await browser.close()
                        self._save_session("twitter", cookies)
                        return {
                            "success": True,
                            "message": f"Twitter authenticated as @{username}",
                            "method": "browser_session",
                            "cookies_saved": True,
                        }
                    except PWTimeout:
                        await browser.close()
                        return {"success": False, "message": "Twitter login failed — check credentials or use Bearer Token"}
            except Exception as exc:
                return {"success": False, "message": f"Twitter browser login error: {exc}"}

        return {"success": False, "message": "Provide a Bearer Token or username + password for Twitter"}

    # ── Medium ───────────────────────────────────────────────────────────────

    async def _login_medium(self, credentials: dict) -> dict:
        """Login to Medium via browser (Google SSO or email magic link)."""
        email = credentials.get("username") or credentials.get("email", "")
        password = credentials.get("password", "")

        if not email:
            return {"success": False, "message": "Medium requires an email address"}

        try:
            from playwright.async_api import async_playwright, TimeoutError as PWTimeout

            async with async_playwright() as pw:
                browser = await pw.chromium.launch(headless=True)
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                )
                page = await context.new_page()

                await page.goto("https://medium.com/m/signin", wait_until="networkidle", timeout=30000)
                await asyncio.sleep(1.5)

                # Click "Sign in with email"
                try:
                    email_btn = await page.wait_for_selector('button:has-text("Sign in with email")', timeout=8000)
                    await email_btn.click()
                    await asyncio.sleep(1)
                    await page.fill('input[type="email"]', email)
                    await page.keyboard.press("Enter")
                    await asyncio.sleep(2)

                    await browser.close()
                    # Medium uses magic links — can't fully automate without email access
                    return {
                        "success": False,
                        "message": "Medium uses magic link login — check your email for the sign-in link. Once logged in manually, cookies will be saved automatically.",
                        "method": "magic_link",
                    }
                except PWTimeout:
                    await browser.close()
                    # Medium public content works fine without auth
                    return {
                        "success": True,
                        "message": "Medium: public articles are accessible without login. Member-only content requires manual browser login.",
                        "method": "public",
                        "cookies_saved": False,
                    }
        except Exception as exc:
            return {"success": False, "message": f"Medium login error: {exc}"}

    # ── Substack ─────────────────────────────────────────────────────────────

    async def _login_substack(self, credentials: dict) -> dict:
        """Login to Substack via browser."""
        email = credentials.get("username") or credentials.get("email", "")
        password = credentials.get("password", "")

        if not email or not password:
            return {"success": False, "message": "Substack requires email and password"}

        try:
            from playwright.async_api import async_playwright, TimeoutError as PWTimeout

            async with async_playwright() as pw:
                browser = await pw.chromium.launch(headless=True)
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                )
                page = await context.new_page()

                await page.goto("https://substack.com/sign-in", wait_until="networkidle", timeout=30000)
                await asyncio.sleep(1.5)

                await page.fill('input[type="email"]', email)
                await page.keyboard.press("Enter")
                await asyncio.sleep(1)

                try:
                    pwd_input = await page.wait_for_selector('input[type="password"]', timeout=5000)
                    await pwd_input.fill(password)
                    await page.keyboard.press("Enter")
                    await page.wait_for_url("**/inbox**", timeout=15000)

                    cookies = await context.cookies()
                    await browser.close()
                    self._save_session("substack", cookies)
                    return {
                        "success": True,
                        "message": f"Substack authenticated as {email}",
                        "method": "browser_session",
                        "cookies_saved": True,
                    }
                except PWTimeout:
                    await browser.close()
                    return {"success": False, "message": "Substack login failed or required email verification"}
        except Exception as exc:
            return {"success": False, "message": f"Substack login error: {exc}"}

    # ── Academic API key platforms ────────────────────────────────────────────

    async def _login_ieee(self, credentials: dict) -> dict:
        api_key = credentials.get("api_key") or credentials.get("token", "")
        if not api_key:
            return {"success": False, "message": "IEEE Xplore requires an API key from developer.ieee.org"}
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"https://ieeexploreapi.ieee.org/api/v1/articles?apikey={api_key}&querytext=test&max_records=1"
                )
            if resp.status_code == 200:
                os.environ["IEEE_API_KEY"] = api_key
                data = resp.json()
                total = data.get("total_records", "?")
                return {"success": True, "message": f"IEEE Xplore API key valid — {total} records accessible", "method": "api_key", "cookies_saved": False}
            elif resp.status_code == 401:
                return {"success": False, "message": "IEEE API key invalid (401)"}
            else:
                # Key may be valid but returning other status
                os.environ["IEEE_API_KEY"] = api_key
                return {"success": True, "message": "IEEE Xplore API key stored (could not verify — save and try a run)", "method": "api_key", "cookies_saved": False}
        except Exception as exc:
            return {"success": False, "message": f"IEEE validation error: {exc}"}

    async def _login_springer(self, credentials: dict) -> dict:
        api_key = credentials.get("api_key") or credentials.get("token", "")
        if not api_key:
            return {"success": False, "message": "Springer requires an API key from dev.springernature.com"}
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"https://api.springernature.com/meta/v2/json?api_key={api_key}&q=test&p=1"
                )
            if resp.status_code == 200:
                os.environ["SPRINGER_API_KEY"] = api_key
                return {"success": True, "message": "Springer API key valid and stored", "method": "api_key", "cookies_saved": False}
            elif resp.status_code == 401:
                return {"success": False, "message": "Springer API key invalid (401)"}
            else:
                os.environ["SPRINGER_API_KEY"] = api_key
                return {"success": True, "message": "Springer API key stored", "method": "api_key", "cookies_saved": False}
        except Exception as exc:
            return {"success": False, "message": f"Springer validation error: {exc}"}

    async def _login_elsevier(self, credentials: dict) -> dict:
        api_key = credentials.get("api_key") or credentials.get("token", "")
        if not api_key:
            return {"success": False, "message": "Elsevier requires an API key from dev.elsevier.com"}
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    "https://api.elsevier.com/content/search/sciencedirect",
                    params={"query": "test", "count": 1},
                    headers={"X-ELS-APIKey": api_key, "Accept": "application/json"},
                )
            if resp.status_code == 200:
                os.environ["ELSEVIER_API_KEY"] = api_key
                return {"success": True, "message": "Elsevier / ScienceDirect API key valid", "method": "api_key", "cookies_saved": False}
            else:
                os.environ["ELSEVIER_API_KEY"] = api_key
                return {"success": True, "message": "Elsevier API key stored (validate with a run)", "method": "api_key", "cookies_saved": False}
        except Exception as exc:
            return {"success": False, "message": f"Elsevier validation error: {exc}"}

    async def _login_jstor(self, credentials: dict) -> dict:
        # JSTOR has no public API — requires institutional access
        username = credentials.get("username", "")
        password = credentials.get("password", "")
        institution = credentials.get("institution", "")
        if institution:
            os.environ["JSTOR_INSTITUTION"] = institution
            return {
                "success": True,
                "message": f"JSTOR institutional access stored for: {institution}. Full-text access requires your institution's IP range or VPN.",
                "method": "institutional",
                "cookies_saved": False,
            }
        return {
            "success": False,
            "message": "JSTOR requires institutional access. Enter your institution name and ensure you're on their network/VPN.",
        }

    # ── Token-based platforms ─────────────────────────────────────────────────

    async def _validate_notion_token(self, credentials: dict) -> dict:
        token = credentials.get("token") or credentials.get("api_key", "")
        if not token:
            return {"success": False, "message": "Notion requires an integration token from notion.so/my-integrations"}
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    "https://api.notion.com/v1/users/me",
                    headers={"Authorization": f"Bearer {token}", "Notion-Version": "2022-06-28"},
                )
            if resp.status_code == 200:
                user = resp.json().get("bot", {}).get("owner", {}).get("user", {})
                name = user.get("name", "unknown")
                os.environ["NOTION_TOKEN"] = token
                return {"success": True, "message": f"Notion token valid — connected as {name}", "method": "integration_token", "cookies_saved": False}
            return {"success": False, "message": f"Notion token invalid (HTTP {resp.status_code})"}
        except Exception as exc:
            return {"success": False, "message": f"Notion validation error: {exc}"}

    async def _validate_slack_token(self, credentials: dict) -> dict:
        token = credentials.get("token") or credentials.get("api_key", "")
        if not token:
            return {"success": False, "message": "Slack requires a token with search:read scope from api.slack.com/apps"}
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    "https://slack.com/api/auth.test",
                    headers={"Authorization": f"Bearer {token}"},
                )
            data = resp.json()
            if data.get("ok"):
                workspace = data.get("team", "")
                user = data.get("user", "")
                os.environ["SLACK_TOKEN"] = token
                return {"success": True, "message": f"Slack token valid — connected as {user} in {workspace}", "method": "oauth_token", "cookies_saved": False}
            return {"success": False, "message": f"Slack token invalid: {data.get('error', 'unknown')}"}
        except Exception as exc:
            return {"success": False, "message": f"Slack validation error: {exc}"}

    async def _validate_zotero_token(self, credentials: dict) -> dict:
        """Validate a Zotero API key and probe the target library.

        Accepts optional ``library_id`` and ``library_type`` (user|group).
        If omitted, uses the key owner's personal library.
        """
        api_key = credentials.get("api_key") or credentials.get("token", "")
        library_id = (credentials.get("library_id") or "").strip()
        library_type = (credentials.get("library_type") or "").strip().lower() or "user"
        if library_type not in {"user", "group"}:
            library_type = "user"
        if not api_key:
            return {"success": False, "message": "Zotero requires an API key from zotero.org/settings/keys"}
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10) as client:
                key_resp = await client.get(
                    "https://api.zotero.org/keys/current",
                    headers={"Zotero-API-Key": api_key},
                )
            if key_resp.status_code != 200:
                return {"success": False, "message": f"Zotero API key invalid (HTTP {key_resp.status_code})"}
            key_data = key_resp.json()
            user_id = str(key_data.get("userID", ""))
            username = key_data.get("username") or key_data.get("displayName") or "unknown"
            if not library_id:
                library_id = user_id
                library_type = "user"

            async with httpx.AsyncClient(timeout=10) as client:
                count_resp = await client.get(
                    f"https://api.zotero.org/{library_type}s/{library_id}/items?limit=1",
                    headers={"Zotero-API-Key": api_key, "Zotero-API-Version": "3"},
                )
            if count_resp.status_code != 200:
                return {
                    "success": False,
                    "message": (
                        f"Zotero library {library_type}/{library_id} not accessible "
                        f"(HTTP {count_resp.status_code})"
                    ),
                }
            total = count_resp.headers.get("Total-Results", "?")
            os.environ["ZOTERO_API_KEY"] = api_key
            os.environ["ZOTERO_LIBRARY_ID"] = library_id
            os.environ["ZOTERO_LIBRARY_TYPE"] = library_type
            return {
                "success": True,
                "message": f"Zotero connected — {username} ({library_type}/{library_id}, {total} items)",
                "username": username,
                "method": "api_key",
                "cookies_saved": False,
            }
        except Exception as exc:
            return {"success": False, "message": f"Zotero validation error: {exc}"}

    async def _validate_vimeo_token(self, credentials: dict) -> dict:
        token = credentials.get("token") or credentials.get("api_key", "")
        if not token:
            return {"success": False, "message": "Vimeo requires an access token from developer.vimeo.com"}
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    "https://api.vimeo.com/me",
                    headers={"Authorization": f"bearer {token}", "Accept": "application/vnd.vimeo.*+json;version=3.4"},
                )
            if resp.status_code == 200:
                user = resp.json().get("name", "unknown")
                os.environ["VIMEO_ACCESS_TOKEN"] = token
                return {"success": True, "message": f"Vimeo token valid — connected as {user}", "method": "access_token", "cookies_saved": False}
            return {"success": False, "message": f"Vimeo token invalid (HTTP {resp.status_code})"}
        except Exception as exc:
            return {"success": False, "message": f"Vimeo validation error: {exc}"}


# Backward-compatible alias for code that imports SessionManager directly
SessionManager = BrowserSessionManager


# Global singleton
_session_manager: Optional[BrowserSessionManager] = None


def get_session_manager() -> BrowserSessionManager:
    global _session_manager
    if _session_manager is None:
        _session_manager = BrowserSessionManager()
    return _session_manager
