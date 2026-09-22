"""Strict JSON input for evidence and policies used in release decisions."""

import json
import math
from pathlib import Path
from typing import Any, Dict, List, Tuple


def _unique_object(pairs: List[Tuple[str, Any]]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            # A key can contain private content. Report the condition, not its value.
            raise ValueError("duplicate JSON object keys are not allowed")
        result[key] = value
    return result


def _reject_constant(value: str) -> Any:
    raise ValueError("JSON numbers must be finite numbers")


def _finite_float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("JSON numbers must be finite numbers")
    return number


def _validate_unicode(payload: Any) -> None:
    pending = [payload]
    while pending:
        value = pending.pop()
        if isinstance(value, str):
            try:
                value.encode("utf-8")
            except UnicodeEncodeError as exc:
                raise ValueError("JSON strings must contain valid Unicode scalar values") from exc
        elif isinstance(value, dict):
            pending.extend(value.keys())
            pending.extend(value.values())
        elif isinstance(value, list):
            pending.extend(value)


def load_json(path: Path, *, label: str) -> Any:
    """Read unambiguous UTF-8 JSON, including fields later ignored by a consumer."""
    try:
        source = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError("Could not read %s %s: %s" % (label.lower(), path, exc)) from exc
    except UnicodeDecodeError as exc:
        raise ValueError("%s %s is not valid UTF-8 JSON" % (label, path)) from exc

    try:
        payload = json.loads(
            source,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
            parse_float=_finite_float,
        )
        _validate_unicode(payload)
        return payload
    except json.JSONDecodeError as exc:
        raise ValueError(
            "%s %s is not valid JSON (line %s, column %s)"
            % (label, path, exc.lineno, exc.colno)
        ) from exc
    except ValueError as exc:
        raise ValueError("%s %s is not valid JSON: %s" % (label, path, exc)) from exc
