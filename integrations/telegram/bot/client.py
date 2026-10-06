"""Async HTTP client for the Basira API. Request bodies are never logged or kept after the call."""

from __future__ import annotations

import asyncio
from typing import Any, cast

import httpx

from bot import __version__

JSON = dict[str, Any]


class BasiraError(Exception):
    """Base class; ``message_ar`` is safe to show to the user as is."""

    message_ar: str = ""


class ApiError(BasiraError):
    """The API answered with its error envelope ``{"error": {"code", "message_ar", "message_en"}}``."""

    def __init__(self, status: int, code: str, message_ar: str) -> None:
        super().__init__(f"HTTP {status} {code}")
        self.status = status
        self.code = code
        self.message_ar = message_ar


class UnreachableError(BasiraError):
    """Connection failure, or a response that is not the API's JSON."""


class ApiTimeoutError(BasiraError):
    """The request exceeded its deadline."""


class BasiraClient:
    def __init__(
        self,
        base_url: str,
        *,
        eval_key: str = "",
        text_timeout: float = 30.0,
        image_timeout: float = 60.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        headers = {"User-Agent": f"basira-telegram-bot/{__version__}", "Accept": "application/json"}
        if eval_key:
            headers["X-Eval-Key"] = eval_key
        self._text_timeout = text_timeout
        self._image_timeout = image_timeout
        self._http = httpx.AsyncClient(
            base_url=base_url,
            headers=headers,
            timeout=httpx.Timeout(text_timeout, connect=10.0),
            transport=transport,
            follow_redirects=False,
        )
        self._messages: dict[str, JSON] = {}
        self._lock = asyncio.Lock()

    async def aclose(self) -> None:
        await self._http.aclose()

    async def _request(self, method: str, path: str, *, timeout: float | None = None, **kw: Any) -> JSON:
        try:
            r = await self._http.request(method, path, timeout=timeout or self._text_timeout, **kw)
        except httpx.TimeoutException as e:
            raise ApiTimeoutError(type(e).__name__) from None
        except httpx.HTTPError as e:
            raise UnreachableError(type(e).__name__) from None
        try:
            body = r.json()
        except ValueError:
            raise UnreachableError(f"HTTP {r.status_code} non-JSON") from None
        if r.status_code >= 400:
            err = body.get("error") if isinstance(body, dict) else None
            if isinstance(err, dict) and isinstance(err.get("message_ar"), str):
                raise ApiError(r.status_code, str(err.get("code", "")), err["message_ar"])
            raise UnreachableError(f"HTTP {r.status_code} without error envelope")
        if not isinstance(body, dict | list):
            raise UnreachableError("unexpected JSON")
        return body if isinstance(body, dict) else {"items": body}

    async def check(self, text: str) -> JSON:
        return await self._request("POST", "/v1/check", json={"text": text, "ui_lang": "ar"})

    async def check_image(self, data: bytes, mime: str) -> JSON:
        ext = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}.get(mime, "bin")
        return await self._request(
            "POST",
            "/v1/check/image",
            timeout=self._image_timeout,
            files={"image": (f"image.{ext}", data, mime)},
            data={"ui_lang": "ar"},
        )

    async def rules(self) -> JSON:
        return await self._request("GET", "/v1/rules", params={"ui_lang": "ar"})

    async def sources(self) -> list[JSON]:
        body = await self._request("GET", "/v1/sources")
        return cast(list[JSON], body.get("items", []))

    async def health(self) -> JSON:
        return await self._request("GET", "/health", timeout=10.0)

    async def messages(self, lang: str = "ar") -> JSON:
        """``messages/{lang}.json`` as served by the API; cached for the process lifetime once fetched."""
        if lang in self._messages:
            return self._messages[lang]
        async with self._lock:
            if lang not in self._messages:
                self._messages[lang] = await self._request("GET", f"/v1/messages/{lang}")
        return self._messages[lang]
