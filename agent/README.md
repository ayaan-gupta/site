# IRW Chat Agent Setup

Agentic AI assistant that helps users **locate and process** the best IRW datasets for their project. The agent uses an LLM with **tool calling** (search datasets, get details, generate R code, get doc links) and optional **semantic search** over dataset cards (RAG).

## Choosing the LLM provider (OpenAI or Gemini)

The agent can use **OpenAI** (e.g. GPT-4o-mini) or **Google Gemini** (e.g. Gemini 1.5 Flash) for the same tool-calling behavior. You choose the provider with the **`IRW_LLM_PROVIDER`** environment variable:

- **`IRW_LLM_PROVIDER=openai`** (default) — uses the OpenAI API. Set `OPENAI_API_KEY` and optionally `OPENAI_MODEL`.
- **`IRW_LLM_PROVIDER=gemini`** — uses the Gemini API. Set `GOOGLE_API_KEY` (or `GEMINI_API_KEY`) and optionally `GEMINI_MODEL`.

The same tools (search, get details, generate R code, get docs) and system prompt are used for both; only the underlying model and API change. Use whichever provider you have access to or prefer. If `IRW_LLM_PROVIDER` is unset or invalid, the agent falls back to `openai`.

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

Choose **OpenAI** or **Gemini** and set the matching env vars (or use `agent/.env`).

**Option A – OpenAI (default)**  
Set `IRW_LLM_PROVIDER=openai` and your OpenAI key:

```powershell
# Windows
$env:IRW_LLM_PROVIDER = "openai"
$env:OPENAI_API_KEY = "sk-..."
uvicorn agent.main:app --reload --host 0.0.0.0 --port 8000
```

```bash
# Linux/macOS
export IRW_LLM_PROVIDER=openai
export OPENAI_API_KEY=sk-...
uvicorn agent.main:app --reload --host 0.0.0.0 --port 8000
```

**Option B – Gemini**  
Set `IRW_LLM_PROVIDER=gemini` and your Google API key:

```powershell
# Windows
$env:IRW_LLM_PROVIDER = "gemini"
$env:GOOGLE_API_KEY = "your-google-api-key"
uvicorn agent.main:app --reload --host 0.0.0.0 --port 8000
```

```bash
# Linux/macOS
export IRW_LLM_PROVIDER=gemini
export GOOGLE_API_KEY=your-google-api-key
uvicorn agent.main:app --reload --host 0.0.0.0 --port 8000
```

You can also use `GEMINI_API_KEY` instead of `GOOGLE_API_KEY`. Optional: `OPENAI_MODEL` (e.g. `gpt-4o-mini`) or `GEMINI_MODEL` (e.g. `gemini-1.5-flash`).

Or copy `agent/.env.example` to `agent/.env`, set `IRW_LLM_PROVIDER` and the right API key(s), then run: `uvicorn agent.main:app --reload --host 0.0.0.0 --port 8000`.

### 3. Point the widget at the API

The chat widget is included on every page. By default it POSTs to `/api/chat`. To use a separate backend (e.g. `http://localhost:8000`):

- **Option A:** Before the widget script runs, set:
  ```html
  <script>window.IRW_CHAT_API_URL = "http://localhost:8000/chat";</script>
  ```
  Add this in `_quarto.yml` via `include-before-body` so it runs before the chat script: include-before-body: resources/chat/irw-chat-api-dev.html
- **Option B:** Proxy `/api` to your backend in development (e.g. Vite, or Quarto preview with a proxy).

### 4. Build and preview the site

From the site root:

```bash
quarto preview
```

Open the site (e.g. [http://localhost:4200](http://localhost:4200)). Click the chat button (bottom-right) and ask e.g. "I need child math assessment data with many participants" or "How do I fetch datasets with response time in R?"

## Production

For production you want the widget to call the chat API on the **same origin** (no `IRW_CHAT_API_URL`), so requests go to `/api/chat` and avoid CORS.

1. **In `_quarto.yml`:** Comment out or remove the dev include so the widget uses the default:
   ```yaml
   # include-before-body: resources/chat/irw-chat-api-dev.html
   ```
2. **Serve the API at `/api/chat`.** The site (e.g. GitHub Pages) only serves static files, so you need the agent available at that path. Two common approaches:
   - **Reverse proxy:** Serve the Quarto site and the agent behind the same host; configure the server (e.g. nginx, Cloudflare, Netlify) so that requests to `https://yoursite.org/api/chat` are proxied to the FastAPI app (e.g. running on the same machine or a backend service).
   - **Separate host + production include:** Host the agent elsewhere (e.g. Cloud Run, Railway, Fly.io) and add a *production* include file that sets `window.IRW_CHAT_API_URL` to that URL (e.g. `https://your-agent.example.com/chat`). Then the widget talks to the agent on a different origin; ensure CORS allows your site (e.g. via `CORS_ORIGINS`).

Without one of these, the widget will POST to `/api/chat` and get 404 (e.g. on plain GitHub Pages, which does not run the agent).

## Architecture

- **LLM provider:** The agent supports **OpenAI** or **Gemini**; the provider is selected via `IRW_LLM_PROVIDER`. The same tools and system prompt are used for both.
- **RAG:** Dataset "cards" (one text blob per dataset: description, variables, stats, tags) are optionally embedded with OpenAI; the user's message is embedded and top-k cards are retrieved so the agent recommends from real catalog data.
- **Tools:** The LLM can call `search_datasets(project_description)`, `get_dataset_details(tables)`, `generate_r_code(table_names|filter_args)`, `get_docs(topic)`.
- **Agent loop:** Messages + tool results are passed back to the LLM until it returns a final answer (no more tool calls).

## Environment


| Variable                      | Description                                                |
| ----------------------------- | ---------------------------------------------------------- |
| `IRW_LLM_PROVIDER`            | `openai` or `gemini` (default: `openai`).                  |
| `OPENAI_API_KEY`              | Required when provider is `openai`.                        |
| `OPENAI_MODEL`                | Optional; default `gpt-4o-mini`.                            |
| `GOOGLE_API_KEY` / `GEMINI_API_KEY` | Required when provider is `gemini`.                 |
| `GEMINI_MODEL`                | Optional; default `gemini-1.5-flash`.                      |
| `CORS_ORIGINS`                | Optional; comma-separated origins for CORS (default `*`).  |


## Files

- `main.py` — FastAPI app, `POST /chat`.
- `agent.py` — Agentic loop and tool-calling.
- `tools.py` — Tool implementations (search, details, R code, docs).
- `rag.py` — Load metadata/cards; embed + retrieve (or keyword fallback).
- `data/` — `irw_metadata.json`, `irw_cards.json` (from R script); sample files used if these are missing.

