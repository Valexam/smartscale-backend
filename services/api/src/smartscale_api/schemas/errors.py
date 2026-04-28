"""RFC 7807 problem+json builder."""

from __future__ import annotations

from typing import Any

from fastapi.responses import JSONResponse

_TITLES: dict[int, str] = {
    400: "Bad Request",
    401: "Unauthorized",
    409: "Conflict",
    422: "Unprocessable Entity",
}


def problem_response(status: int, code: str, detail: str, **extra: Any) -> JSONResponse:
    body: dict[str, Any] = {
        "type": f"https://smartscale.example/errors/{code.lower().replace('_', '-')}",
        "title": _TITLES.get(status, "Error"),
        "status": status,
        "code": code,
        "detail": detail,
    }
    body.update(extra)
    return JSONResponse(status_code=status, content=body, media_type="application/problem+json")
