"""Start the API or dashboard without shell-dependent command quoting."""

import argparse
import os
import sys
from typing import Optional, Sequence


def main(argv: Optional[Sequence[str]] = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("role", choices=("api", "dashboard"))
    args = parser.parse_args(argv)
    default_port = 8000 if args.role == "api" else 8501
    try:
        port = int(os.environ.get("PORT") or default_port)
    except ValueError:
        parser.error("PORT must be an integer between 1 and 65535")
    if not 1 <= port <= 65535:
        parser.error("PORT must be an integer between 1 and 65535")

    if args.role == "api":
        command = [
            "uvicorn", "evalforge.api:app", "--host", "0.0.0.0", "--port", str(port),
        ]
    else:
        command = [
            "streamlit", "run", "dashboard/app.py", "--server.address=0.0.0.0",
            "--server.port=" + str(port), "--server.headless=true",
        ]
    # Replace this process so the server receives container termination signals.
    os.execv(sys.executable, [sys.executable, "-m", *command])


if __name__ == "__main__":
    main()
