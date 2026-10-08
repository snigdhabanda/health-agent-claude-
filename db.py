"""Read-only SQL backends for the agent's run_sql tool."""

import json
import os
import re
import ssl
import time
import urllib.error
import urllib.request

import certifi

MAX_ROWS = 200
TIMEOUT_S = 60

_READ_ONLY = re.compile(r"^\s*(select|with)\b", re.IGNORECASE)
_WRITE_KEYWORDS = re.compile(
    r"\b(insert|update|delete|merge|drop|create|alter|truncate|grant|revoke|copy|optimize|vacuum)\b",
    re.IGNORECASE,
)


class QueryError(Exception):
    """A query was rejected or failed. The message goes back to Claude."""


def check_read_only(query: str) -> str:
    q = query.strip().rstrip(";").strip()
    if ";" in q:
        raise QueryError("Only one statement per call.")
    if not _READ_ONLY.match(q):
        raise QueryError("Only SELECT (or WITH ... SELECT) queries are allowed.")
    if _WRITE_KEYWORDS.search(q):
        raise QueryError("Query contains a write/DDL keyword; only reads are allowed.")
    return q


def format_rows(columns: list[str], rows: list[tuple], truncated: bool) -> str:
    """Render a result set as a compact pipe table for the model."""
    if not rows:
        return f"columns: {', '.join(columns)}\n(0 rows)"
    lines = [" | ".join(columns)]
    lines += [" | ".join("NULL" if v is None else str(v) for v in row) for row in rows]
    footer = f"({len(rows)} rows" + (f", truncated at {MAX_ROWS}; aggregate or add LIMIT)" if truncated else ")")
    return "\n".join(lines + [footer])


class DatabricksBackend:
    """Queries the same Databricks tables the Genie space uses, via the SQL Statement Execution API.

    (databricks-sql-connector hung on connect under Python 3.14, so this uses the REST API directly.)
    """

    def __init__(self):
        host = os.environ["DATABRICKS_SERVER_HOSTNAME"]
        self._url = f"https://{host}/api/2.0/sql/statements"
        self._warehouse_id = os.environ["DATABRICKS_HTTP_PATH"].rstrip("/").split("/")[-1]
        self._headers = {
            "Authorization": f"Bearer {os.environ['DATABRICKS_TOKEN']}",
            "Content-Type": "application/json",
        }
        # python.org builds don't read the macOS keychain; use certifi's CA bundle like the anthropic SDK does
        self._ssl = ssl.create_default_context(cafile=certifi.where())

    def _request(self, url: str, body: dict | None = None) -> dict:
        req = urllib.request.Request(
            url, data=json.dumps(body).encode() if body else None, headers=self._headers
        )
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_S + 10, context=self._ssl) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as e:
            raise QueryError(f"HTTP {e.code}: {e.read().decode(errors='replace')[:500]}") from e

    def run(self, query: str) -> tuple[list[str], list[tuple], bool]:
        return self._execute(check_read_only(query))

    def execute_ddl(self, statement: str) -> None:
        """Unguarded, for sql/*.sql setup scripts only. The agent's run_sql never reaches this."""
        self._execute(statement)

    def _execute(self, q: str) -> tuple[list[str], list[tuple], bool]:
        d = self._request(self._url, {
            "warehouse_id": self._warehouse_id,
            "statement": q,
            "wait_timeout": f"{TIMEOUT_S // 2}s",
            "on_wait_timeout": "CONTINUE",
            "row_limit": MAX_ROWS + 1,
        })
        deadline = time.monotonic() + TIMEOUT_S
        while d["status"]["state"] in ("PENDING", "RUNNING"):
            if time.monotonic() > deadline:
                self._request(f"{self._url}/{d['statement_id']}/cancel", {})
                raise QueryError(f"Query timed out after {TIMEOUT_S}s.")
            time.sleep(1)
            d = self._request(f"{self._url}/{d['statement_id']}")
        if d["status"]["state"] != "SUCCEEDED":
            err = d["status"].get("error", {})
            raise QueryError(f"{err.get('error_code', d['status']['state'])}: {err.get('message', '')}")
        columns = [c["name"] for c in d.get("manifest", {}).get("schema", {}).get("columns", [])]
        rows = [tuple(r) for r in d.get("result", {}).get("data_array", [])]
        return columns, rows[:MAX_ROWS], len(rows) > MAX_ROWS

    def close(self):
        pass


class DuckDBBackend:
    """Option B: local DuckDB rebuilt from the WHOOP CSV export. Not built yet."""

    def __init__(self):
        raise NotImplementedError("DuckDB backend isn't built yet; set SQL_BACKEND=databricks.")


def get_backend():
    name = os.environ.get("SQL_BACKEND", "databricks").lower()
    if name == "databricks":
        return DatabricksBackend()
    if name == "duckdb":
        return DuckDBBackend()
    raise ValueError(f"Unknown SQL_BACKEND: {name}")
