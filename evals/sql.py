"""Run one SQL query against the configured backend and print the rows (for writing reference answers)."""

import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from db import format_rows, get_backend  # noqa: E402

if __name__ == "__main__":
    query = sys.argv[1] if len(sys.argv) > 1 else sys.stdin.read()
    print(format_rows(*get_backend().run(query)))
