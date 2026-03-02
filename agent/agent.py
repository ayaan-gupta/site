"""
Agentic IRW assistant: LLM with tool calling to locate and process data.
Supports OpenAI or Gemini via IRW_LLM_PROVIDER env var.
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

try:
    import google.generativeai as genai
    _GEMINI_AVAILABLE = True
except ImportError:
    genai = None
    _GEMINI_AVAILABLE = False

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


def _openai_to_gemini_tool_defs():
    """Convert OpenAI-format tool defs to Gemini function declarations."""
    decls = []
    for t in TOOL_DEFS:
        f = t["function"]
        decls.append({
            "name": f["name"],
            "description": f["description"],
            "parameters": f["parameters"],
        })
    return decls


GEMINI_TOOL_DECLARATIONS = _openai_to_gemini_tool_defs()


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


def _run_agent_openai(
    messages: list[dict[str, Any]],
    api_key: str,
    model: str,
    max_tool_rounds: int,
) -> tuple[str, list[dict[str, Any]]]:
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
    final = client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": SYSTEM_PROMPT}] + history,
    )
    final_content = final.choices[0].message.content or ""
    history.append({"role": "assistant", "content": final_content})
    return (final_content, history)


def _messages_to_gemini_contents(messages: list[dict[str, Any]]) -> list[Any]:
    """Convert our message list to Gemini contents (role + parts). Only user/assistant; skip system (use system_instruction on model)."""
    contents = []
    for m in messages:
        if m.get("role") == "user":
            contents.append({"role": "user", "parts": [m.get("content", "")]})
        elif m.get("role") == "assistant" and m.get("content"):
            contents.append({"role": "model", "parts": [m.get("content", "")]})
    return contents


def _run_agent_gemini(
    messages: list[dict[str, Any]],
    api_key: str,
    model: str,
    max_tool_rounds: int,
) -> tuple[str, list[dict[str, Any]]]:
    if not _GEMINI_AVAILABLE or genai is None:
        return (
            "Gemini is not available (install google-generativeai).",
            messages,
        )
    genai.configure(api_key=api_key)
    declarations = []
    for d in GEMINI_TOOL_DECLARATIONS:
        declarations.append(genai.protos.FunctionDeclaration(
            name=d["name"],
            description=d["description"],
            parameters=d["parameters"],
        ))
    tool = genai.protos.Tool(function_declarations=declarations)
    gemini_model = genai.GenerativeModel(
        model_name=model,
        system_instruction=SYSTEM_PROMPT,
        tools=[tool],
    )
    history = list(messages)
    contents = _messages_to_gemini_contents(history)
    last_assistant_content = ""

    for _ in range(max_tool_rounds):
        response = gemini_model.generate_content(contents, tool_config={"function_calling_config": {"mode": "AUTO"}})
        if not response.candidates or not response.candidates[0].content.parts:
            break
        parts = response.candidates[0].content.parts
        text_parts = []
        function_calls = []
        for part in parts:
            if getattr(part, "text", None):
                text_parts.append(part.text)
            if getattr(part, "function_call", None):
                function_calls.append(part.function_call)

        last_assistant_content = "\n".join(text_parts) if text_parts else ""
        history.append({"role": "assistant", "content": last_assistant_content})

        if not function_calls:
            return (last_assistant_content or "", history)

        contents.append({"role": "model", "parts": [{"function_call": fc} for fc in function_calls]})
        response_parts = []
        for fc in function_calls:
            name = fc.name
            args = getattr(fc, "args", None)
            if args is not None and hasattr(args, "items"):
                args = dict(args)
            elif args is not None:
                try:
                    args = json.loads(str(args)) if args else {}
                except Exception:
                    args = {}
            else:
                args = {}
            result = _call_tool(name, args, openai_api_key=None)
            response_parts.append({"function_response": {"name": name, "response": {"result": result[:8000]}}})
            history.append({"role": "tool", "content": result[:8000]})
        contents.append({"role": "user", "parts": response_parts})

    history.append({"role": "assistant", "content": last_assistant_content})
    return (last_assistant_content or "", history)


def run_agent(
    messages: list[dict[str, Any]],
    openai_api_key: str | None = None,
    google_api_key: str | None = None,
    model: str | None = None,
    max_tool_rounds: int = 5,
) -> tuple[str, list[dict[str, Any]]]:
    """
    Run the agentic loop. Provider is chosen by IRW_LLM_PROVIDER env var: "openai" or "gemini".
    """
    provider = (os.environ.get("IRW_LLM_PROVIDER") or "openai").strip().lower()
    if provider not in ("openai", "gemini"):
        provider = "openai"

    if provider == "openai":
        api_key = openai_api_key or os.environ.get("OPENAI_API_KEY")
        if not OpenAI or not api_key:
            return (
                "The IRW assistant is not configured (set IRW_LLM_PROVIDER=openai and OPENAI_API_KEY). "
                "You can still explore data on the Home page and use Getting Started for R/Python code.",
                messages,
            )
        model_name = model or os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
        return _run_agent_openai(messages, api_key, model_name, max_tool_rounds)

    if provider == "gemini":
        api_key = google_api_key or os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
        if not api_key:
            return (
                "The IRW assistant is not configured (set IRW_LLM_PROVIDER=gemini and GOOGLE_API_KEY or GEMINI_API_KEY).",
                messages,
            )
        model_name = model or os.environ.get("GEMINI_MODEL", "gemini-1.5-flash")
        return _run_agent_gemini(messages, api_key, model_name, max_tool_rounds)

    return ("The IRW assistant is not configured.", messages)


def run_agent_simple(
    user_message: str,
    openai_api_key: str | None = None,
    model: str = "gpt-4o-mini",
) -> str:
    """One-shot: user message -> final answer (no conversation history)."""
    messages = [{"role": "user", "content": user_message}]
    reply, _ = run_agent(messages, openai_api_key=openai_api_key, model=model)
    return reply
