"""Claude agent over the WHOOP + labs tables in Databricks.

By default Claude queries Databricks through the workspace's managed SQL MCP server, via the
Claude API's MCP connector. Only the read-only tools are enabled. `--tools run_sql` switches back
to the hand-built run_sql tool (db.py) that produced the published eval results.

    python agent.py "how did HRV change after my last lab draw?"
    python agent.py --model claude-haiku-4-5 "avg recovery in March 2025"
    python agent.py --tools run_sql "avg recovery in March 2025"
"""

import argparse
import os
import time
from dataclasses import dataclass, field
from pathlib import Path

import anthropic
from dotenv import load_dotenv

from db import QueryError, format_rows, get_backend

DEFAULT_MODEL = "claude-sonnet-5-5"
MAX_TURNS = 12
SYSTEM_PROMPT = (Path(__file__).parent / "system_prompt.md").read_text()

# $ per 1M tokens: input, output, cache write (5m), cache read
PRICES = {
    "claude-opus-5-5": (4.00, 20.00, 5.00, 0.20),
    "claude-sonnet-5-5": (2.00, 10.00, 2.50, 0.20),
    "claude-haiku-4-5": (1.00, 5.00, 1.25, 0.10),
}

# Server-side refusal fallback is only offered on the 5.5 models.
FALLBACK_MODELS = {"claude-opus-5-5", "claude-sonnet-5-5"}

TOOL_MODES = ("mcp", "run_sql")
DEFAULT_TOOLS = "mcp"

# Databricks managed MCP server for SQL. It also exposes execute_sql, which can write;
# allowlist mode keeps it off, so Claude only sees the read-only tools.
MCP_SERVER_NAME = "databricks-sql"
MCP_ALLOWED_TOOLS = ("execute_sql_read_only", "poll_sql_result")


def mcp_params() -> dict:
    return dict(
        mcp_servers=[{
            "type": "url",
            "url": f"https://{os.environ['DATABRICKS_SERVER_HOSTNAME']}/api/2.0/mcp/sql",
            "name": MCP_SERVER_NAME,
            "authorization_token": os.environ["DATABRICKS_TOKEN"],
        }],
        tools=[{
            "type": "mcp_toolset",
            "mcp_server_name": MCP_SERVER_NAME,
            "default_config": {"enabled": False},
            "configs": {name: {"enabled": True} for name in MCP_ALLOWED_TOOLS},
        }],
    )


RUN_SQL_TOOL = {
    "name": "run_sql",
    "description": (
        "Run one read-only Databricks SQL query (SELECT or WITH ... SELECT) against "
        "the workspace.whoop_data tables and return the rows as a pipe-delimited table. "
        "Results are capped at 200 rows, so aggregate in SQL rather than pulling raw days. "
        "On a SQL error you get the error message back; fix the query and retry."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "A single SELECT statement."},
        },
        "required": ["query"],
        "additionalProperties": False,
    },
    "strict": True,
}


@dataclass
class Result:
    answer: str
    model: str
    queries: list[str] = field(default_factory=list)
    sql_errors: int = 0
    mcp_polls: int = 0  # poll_sql_result calls for queries the MCP server didn't finish inline
    turns: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_write_tokens: int = 0
    cache_read_tokens: int = 0
    latency_s: float = 0.0
    stop_reason: str = ""

    @property
    def cost_usd(self) -> float:
        p_in, p_out, p_cw, p_cr = PRICES[self.model]
        return (
            self.input_tokens * p_in
            + self.output_tokens * p_out
            + self.cache_write_tokens * p_cw
            + self.cache_read_tokens * p_cr
        ) / 1_000_000


def ask(
    question: str,
    model: str = DEFAULT_MODEL,
    backend=None,
    client=None,
    system_prompt: str = SYSTEM_PROMPT,
    tools: str = DEFAULT_TOOLS,
) -> Result:
    if tools not in TOOL_MODES:
        raise ValueError(f"tools must be one of {TOOL_MODES}")
    client = client or anthropic.Anthropic()
    if tools == "run_sql":
        backend = backend or get_backend()
    result = Result(answer="", model=model)
    messages = [{"role": "user", "content": question}]

    params = dict(
        model=model,
        max_tokens=16000,
        system=system_prompt,
        cache_control={"type": "ephemeral"},  # caches the growing prefix each turn
        betas=[],
    )
    if tools == "mcp":
        params |= mcp_params()
        params["betas"].append("mcp-client-2025-11-20")
    else:
        params["tools"] = [RUN_SQL_TOOL]
    if model in FALLBACK_MODELS:
        params["betas"].append("server-side-fallback-2026-07-01")
        params |= dict(
            extra_body={"fallbacks": "default"},  # not a typed kwarg in older SDKs
            output_config={"effort": "medium"},
        )

    start = time.monotonic()
    for _ in range(MAX_TURNS):
        response = client.beta.messages.create(messages=messages, **params)
        result.turns += 1
        u = response.usage
        result.input_tokens += u.input_tokens
        result.output_tokens += u.output_tokens
        result.cache_write_tokens += u.cache_creation_input_tokens or 0
        result.cache_read_tokens += u.cache_read_input_tokens or 0
        result.stop_reason = response.stop_reason

        # MCP tool calls run server-side and come back already resolved in the response.
        for block in response.content:
            if block.type == "mcp_tool_use":
                if block.name == "poll_sql_result":
                    result.mcp_polls += 1
                else:
                    result.queries.append(block.input.get("query", ""))
            elif block.type == "mcp_tool_result" and block.is_error:
                result.sql_errors += 1

        if response.stop_reason == "pause_turn":  # server-side tool loop paused; resend to continue
            messages.append({"role": "assistant", "content": response.content})
            continue
        if response.stop_reason != "tool_use":
            break

        messages.append({"role": "assistant", "content": response.content})
        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            query = block.input.get("query", "")
            result.queries.append(query)
            try:
                content, is_error = format_rows(*backend.run(query)), False
            except QueryError as e:
                content, is_error = f"Error: {e}", True
                result.sql_errors += 1
            tool_results.append(
                {"type": "tool_result", "tool_use_id": block.id, "content": content, "is_error": is_error}
            )
        messages.append({"role": "user", "content": tool_results})
    else:
        result.stop_reason = "max_turns"

    result.latency_s = time.monotonic() - start
    if result.stop_reason == "refusal":
        result.answer = "[refused]"
    else:
        result.answer = "\n".join(b.text for b in response.content if b.type == "text").strip()
    return result


def main():
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("question")
    parser.add_argument("--model", default=DEFAULT_MODEL, choices=sorted(PRICES))
    parser.add_argument("--prompt", type=Path, help="system prompt file (default: system_prompt.md)")
    parser.add_argument("--tools", default=DEFAULT_TOOLS, choices=TOOL_MODES,
                        help="mcp: Databricks managed MCP server (default); run_sql: the hand-built tool")
    args = parser.parse_args()

    r = ask(args.question, model=args.model, tools=args.tools,
            **({"system_prompt": args.prompt.read_text()} if args.prompt else {}))
    print(r.answer)
    print("\n--- SQL ---")
    for i, q in enumerate(r.queries, 1):
        print(f"[{i}] {q.strip()}\n")
    print(
        f"--- {r.model} | {r.turns} turns | {len(r.queries)} queries ({r.sql_errors} errors, {r.mcp_polls} polls) | "
        f"in {r.input_tokens} / out {r.output_tokens} / cache w {r.cache_write_tokens} r {r.cache_read_tokens} | "
        f"${r.cost_usd:.4f} | {r.latency_s:.1f}s | stop: {r.stop_reason}"
    )


if __name__ == "__main__":
    main()
