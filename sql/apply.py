"""Apply a setup script from sql/ to the Databricks workspace: python sql/apply.py sql/gold_daily_v2.sql"""

import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from db import DatabricksBackend  # noqa: E402

if __name__ == "__main__":
    for path in sys.argv[1:]:
        DatabricksBackend().execute_ddl(Path(path).read_text())
        print(f"applied {path}")
