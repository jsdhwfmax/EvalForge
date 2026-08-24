from typing import Optional


def format_metric(value: Optional[float], format_spec: str) -> str:
    """Format dashboard values without mixing display units into Python format specs."""
    if value is None:
        return "—"
    if format_spec.endswith(" ms"):
        return "%s ms" % format(value, format_spec.removesuffix(" ms"))
    return format(value, format_spec)
