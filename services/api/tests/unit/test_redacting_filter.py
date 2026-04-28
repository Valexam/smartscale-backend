"""Direct unit tests for RedactingFilter and _redact."""

from __future__ import annotations

import logging

from smartscale_api.auth import RedactingFilter, _redact

# ---------------------------------------------------------------------------
# _redact — pure function tests
# ---------------------------------------------------------------------------


def test_redact_device_key_header_name() -> None:
    assert _redact("x-device-key") == "[REDACTED]"


def test_redact_authorization_header_name() -> None:
    assert _redact("Authorization") == "[REDACTED]"


def test_redact_admin_key_header_name() -> None:
    assert _redact("x-admin-key") == "[REDACTED]"


def test_redact_substring_match_is_case_insensitive() -> None:
    # A log line that contains the header name as a substring
    assert _redact("header X-Device-Key: abc123") == "[REDACTED]"


def test_redact_leaves_safe_strings_unchanged() -> None:
    assert _redact("some normal log message") == "some normal log message"


def test_redact_leaves_non_strings_unchanged() -> None:
    assert _redact(42) == 42
    assert _redact(None) is None
    assert _redact(3.14) == 3.14


# ---------------------------------------------------------------------------
# RedactingFilter.filter() — exercises the LogRecord mutation path
# ---------------------------------------------------------------------------


def _make_record(msg: str, args: tuple[object, ...]) -> logging.LogRecord:
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=0,
        msg=msg,
        args=args,
        exc_info=None,
    )
    return record


def test_filter_redacts_sensitive_tuple_arg() -> None:
    flt = RedactingFilter()
    record = _make_record("header: %s", ("x-device-key: secret123",))
    result = flt.filter(record)
    assert result is True  # filter always allows the record through
    assert isinstance(record.args, tuple)
    assert record.args[0] == "[REDACTED]"


def test_filter_leaves_safe_tuple_arg_unchanged() -> None:
    flt = RedactingFilter()
    record = _make_record("user: %s", ("alice",))
    flt.filter(record)
    assert isinstance(record.args, tuple)
    assert record.args[0] == "alice"


def _make_dict_record(msg: str, args: dict[str, object]) -> logging.LogRecord:
    """Create a LogRecord with dict args.

    LogRecord.__init__ tries integer-key access on any mapping passed as
    args, which raises KeyError on plain dicts in Python ≥ 3.14.  Assign
    args after construction to avoid the issue.
    """
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=0,
        msg=msg,
        args=None,
        exc_info=None,
    )
    record.args = args
    return record


def test_filter_redacts_sensitive_dict_arg() -> None:
    flt = RedactingFilter()
    record = _make_dict_record("headers: %(hdr)s", {"hdr": "authorization: Bearer secret"})
    flt.filter(record)
    assert isinstance(record.args, dict)
    assert record.args["hdr"] == "[REDACTED]"


def test_filter_leaves_safe_dict_arg_unchanged() -> None:
    flt = RedactingFilter()
    record = _make_dict_record("user: %(name)s", {"name": "alice"})
    flt.filter(record)
    assert isinstance(record.args, dict)
    assert record.args["name"] == "alice"


def test_filter_always_returns_true() -> None:
    """RedactingFilter must not drop records — it only mutates them."""
    flt = RedactingFilter()
    record = _make_record("msg %s", ("x-device-key: secret",))
    assert flt.filter(record) is True
