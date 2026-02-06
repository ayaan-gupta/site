"""
Agentic IRW assistant: LLM with tool calling to locate and process data.
Current Tools I've added so far: search_datasets, get_dataset_details, generate_r_code, get_docs.
"""
import json
import os
from typing import Any

from .tools import (
    search_datasets as tool_search_datasets,
    get_dataset_details as tool_get_dataset_details,
    generate_r_code as tool_generate_r_code,
    get_docs as tool_get_docs,
)

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

SYSTEM_PROMPT = """You are the Item Response Warehouse (IRW) assistant. You help researchers and practitioners locate and process the best IRW datasets for their project.

**IRW** is a collection of open, harmonized item-response datasets (psychometrics/education). Data are on Redivis. Users typically access data via:
- **R**: `library(irw)` then `irw_filter(...)` and `irw_fetch(irw_tables)`
- **Python**: `irw.filter(...)` and `irw.fetch(...)`
- **Web**: The site's Home page has an interactive explorer with filters; the Data page lets you pick one dataset and view it on Redivis.

**Your goals:**
1. **Locate**: Use the search_datasets tool with the user's project description to find semantically relevant datasets. Then use get_dataset_details for any tables you want to recommend so you can summarize description, variables, and size.
2. **Process**: Use generate_r_code to produce R snippets (irw_filter + irw_fetch, or irw_fetch with specific table names). Point users to getstarted.html for setup and standard.html for the data schema (id, item, resp; optional rt, date, qmatrix, etc.).
3. **Navigate**: Use get_docs when the user asks where to find something (e.g. "how do I cite?", "data standard", "tutorials"). Key pages: getstarted.html, index.html (explorer), data.html, standard.html, metadata.html, imv.html, diffsim.html, training.html, contact.html.

**Behavior:**
- Be concise and actionable. Recommend specific datasets by name when you find good matches, and always provide R (or Python) code when the user wants to fetch data.
- **General "what data" questions:** If the user asks what data exists, what's available, what's there, or for an overview, do NOT ask them to narrow it down. Call search_datasets with a broad query (e.g. "item response data, assessments, education, psychology, various domains, age groups, and sample types") and use the results to describe what the IRW contains—e.g. types of measures, age ranges, sizes—and name a few example datasets. Give a direct, helpful overview.
- **Specific requests:** When the user describes a project or criteria, call search_datasets with that description, then get_dataset_details for tables you want to recommend, and summarize with code if they want to fetch.
- When generating code, prefer specific table names from your search results when appropriate; otherwise use irw_filter() with the criteria the user described.
- Only ask a clarifying question when the user explicitly says they have a project but gives no hint of topic or criteria (e.g. "I need data for my project" with nothing else). For broad or exploratory questions, always use tools first and answer from the catalog.
- Do not make up dataset names or URLs; only use names and info from tool results.
"""

TOOL_DEFS = [
    {
        "type": "function",
        "function": {
            "name": "search_datasets",
            "description": "Search IRW datasets by semantic similarity to a query. Use this (1) when the user asks what data exists or wants an overview—pass a broad query like 'item response data, assessments, education, psychology, various domains' to get a representative sample; (2) when the user describes their project or criteria (e.g. 'child math assessment', 'longitudinal with response time'). Returns top matching datasets with short summaries.",
            "parameters": {
                "type": "object",
                "properties": {
                    "project_description": {
                        "type": "string",
                        "description": "The user's project description or data needs (e.g. 'I need child cognitive data with many participants').",
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Number of datasets to return (default 8).",
                        "default": 8,
                    },
                },
                "required": ["project_description"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_dataset_details",
            "description": "Get full metadata for specific dataset table names (e.g. after search). Use when you want to show description, variables, n_responses, n_participants, URL, reference for one or more tables.",
            "parameters": {
                "type": "object",
                "properties": {
                    "tables": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of IRW table names (e.g. ['4thgrade_math_sirt', 'chess_lnirt']).",
                    },
                },
                "required": ["tables"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_r_code",
            "description": "Generate R code to fetch IRW data. Use table_names when you have specific datasets to recommend; use filter_args when the user described criteria (e.g. n_participants, age_range, var='rt').",
            "parameters": {
                "type": "object",
                "properties": {
                    "table_names": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Specific table names to fetch (e.g. ['4thgrade_math_sirt']). Use when recommending specific datasets.",
                    },
                    "filter_args": {
                        "type": "object",
                        "description": "Arguments for irw_filter(): e.g. n_participants=[1000, Inf], age_range=['Child (<18y)'], var='rt', longitudinal=True. Range args use [min, max]; tag args use lists of strings.",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_docs",
            "description": "Get the relevant site page for a topic (e.g. 'getting started', 'data standard', 'metadata', 'imv', 'contact'). Use when the user asks where to find something or how to get started.",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "Topic or page name (e.g. 'getting started', 'cite', 'standard', 'tutorial').",
                    },
                },
                "required": ["topic"],
            },
        },
    },
]


def _call_tool(name: str, arguments: dict, openai_api_key: str | None = None) -> str:
    if name == "search_datasets":
        return tool_search_datasets(
            project_description=arguments.get("project_description", ""),
            top_k=int(arguments.get("top_k", 8)),
            use_embeddings=True,
            openai_api_key=openai_api_key,
        )
    if name == "get_dataset_details":
        return tool_get_dataset_details(tables=arguments.get("tables", []))
    if name == "generate_r_code":
        return tool_generate_r_code(
            filter_args=arguments.get("filter_args"),
            table_names=arguments.get("table_names"),
        )
    if name == "get_docs":
        return tool_get_docs(topic=arguments.get("topic", ""))
    return f"Unknown tool: {name}"


def run_agent(
    messages: list[dict[str, Any]],
    openai_api_key: str | None = None,
    model: str = "gpt-4o-mini",
    max_tool_rounds: int = 5,
) -> tuple[str, list[dict[str, Any]]]:
    """
    Run the agentic loop: LLM with tool calling until a final answer.
    messages: list of {"role": "user"|"assistant"|"system", "content": "..."}.
    Returns (final_assistant_message, updated_messages).
    """
    api_key = openai_api_key or os.environ.get("OPENAI_API_KEY")
    if not OpenAI or not api_key:
        return (
            "The IRW assistant is not configured (missing OPENAI_API_KEY). "
            "You can still explore data on the Home page and use Getting Started for R/Python code.",
            messages,
        )

    client = OpenAI(api_key=api_key)
    history = list(messages)

    for _ in range(max_tool_rounds):
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}] + history,
            tools=TOOL_DEFS,
            tool_choice="auto",
        )
        choice = response.choices[0]
        msg = choice.message

        # Append full assistant message (content + tool_calls if any)
        assistant_msg = {"role": "assistant", "content": msg.content or ""}
        if msg.tool_calls:
            assistant_msg["tool_calls"] = [
                {"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                for tc in msg.tool_calls
            ]
        history.append(assistant_msg)

        if not msg.tool_calls:
            return (msg.content or "", history)

        for tc in msg.tool_calls:
            name = tc.function.name
            try:
                args = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                args = {}
            result = _call_tool(name, args, openai_api_key=api_key)
            history.append({"role": "tool", "tool_call_id": tc.id, "content": result[:8000]})

    # Fallback if max_tool_rounds hit
    final = client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": SYSTEM_PROMPT}] + history,
    )
    final_content = final.choices[0].message.content or ""
    history.append({"role": "assistant", "content": final_content})
    return (final_content, history)


def run_agent_simple(
    user_message: str,
    openai_api_key: str | None = None,
    model: str = "gpt-4o-mini",
) -> str:
    """One-shot: user message -> final answer (no conversation history)."""
    messages = [{"role": "user", "content": user_message}]
    reply, _ = run_agent(messages, openai_api_key=openai_api_key, model=model)
    return reply
