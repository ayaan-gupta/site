# IRW Chat Agent Setup

Agentic AI assistant that helps users **locate and process** the best IRW datasets for their project. The agent uses an LLM with **tool calling** (search datasets, get details, generate R code, get doc links) and optional **semantic search** over dataset cards (RAG).

## Quick start

### 1. Export metadata (optional but recommended)

From the **site root** (with R and redivis configured):

```bash
Rscript scripts/export_metadata_for_agent.R
```

This writes `agent/data/irw_metadata.json` and `agent/data/irw_cards.json`. Without it, the agent uses a small sample (2 datasets). Run this when the IRW catalog changes.

### 2. Backend

From the **site root** (parent of `agent/`):

```bash
pip install -r agent/requirements.txt
```

Set your OpenAI API key and start the server:

**Windows (PowerShell):**

```powershell
$env:OPENAI_API_KEY = "sk-..."
uvicorn agent.main:app --reload --host 0.0.0.0 --port 8000
```

**Linux/macOS:**

```bash
export OPENAI_API_KEY=sk-...
uvicorn agent.main:app --reload --host 0.0.0.0 --port 8000
```

Or copy `agent/.env.example` to `agent/.env`, add `OPENAI_API_KEY`, then run from site root: `uvicorn agent.main:app --reload --host 0.0.0.0 --port 8000`.

### 3. Point the widget at the API

The chat widget is included on every page. By default it POSTs to `/api/chat`. To use a separate backend (e.g. `http://localhost:8000`):

- **Option A:** Before the widget script runs, set:
  ```html
  <script>window.IRW_CHAT_API_URL = "http://localhost:8000/chat";</script>
  ```
  Add this in `_quarto.yml` via `include-before-body` so it runs before the chat script.
- **Option B:** Proxy `/api` to your backend in development (e.g. Vite, or Quarto preview with a proxy).

### 4. Build and preview the site

From the site root:

```bash
quarto preview
```

Open the site (e.g. [http://localhost:4200](http://localhost:4200)). Click the chat button (bottom-right) and ask e.g. "I need child math assessment data with many participants" or "How do I fetch datasets with response time in R?"

## Architecture

- **RAG:** Dataset "cards" (one text blob per dataset: description, variables, stats, tags) are optionally embedded with OpenAI; the user's message is embedded and top-k cards are retrieved so the agent recommends from real catalog data.
- **Tools:** The LLM can call `search_datasets(project_description)`, `get_dataset_details(tables)`, `generate_r_code(table_names|filter_args)`, `get_docs(topic)`.
- **Agent loop:** Messages + tool results are passed back to the LLM until it returns a final answer (no more tool calls).

## Environment


| Variable         | Description                                               |
| ---------------- | --------------------------------------------------------- |
| `OPENAI_API_KEY` | Required for the LLM and optional semantic search.        |
| `OPENAI_MODEL`   | Optional; default `gpt-4o-mini`.                          |
| `CORS_ORIGINS`   | Optional; comma-separated origins for CORS (default `*`). |


## Files

- `main.py` — FastAPI app, `POST /chat`.
- `agent.py` — Agentic loop and tool-calling.
- `tools.py` — Tool implementations (search, details, R code, docs).
- `rag.py` — Load metadata/cards; embed + retrieve (or keyword fallback).
- `data/` — `irw_metadata.json`, `irw_cards.json` (from R script); sample files used if these are missing.

