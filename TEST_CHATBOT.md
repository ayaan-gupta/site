# Using the IRW Chatbot

The chatbot is the **floating button** (bottom-right) that opens the "IRW Data Assistant" panel. To test it locally you need **two things running**: the site and the agent backend.

## 1. Start the agent backend

From the **site root** (`c:\Users\aayug\irw-ai\site`), in a terminal:

```powershell
# Install Python deps once (includes python-dotenv for agent/.env)
pip install -r agent/requirements.txt

# Option A: Put OPENAI_API_KEY=sk-... in agent/.env, then:
uvicorn agent.main:app --reload --host 0.0.0.0 --port 8000

# Option B: Set key in the terminal
$env:OPENAI_API_KEY = "sk-your-key-here"
uvicorn agent.main:app --reload --host 0.0.0.0 --port 8000
```

Leave this running. You should see: `Uvicorn running on http://0.0.0.0:8000`.

**Verify:** Open **http://localhost:8000/health** in your browser — you should see `{"status":"ok"}`. If that fails, the backend isn’t running or isn’t on port 8000.

## 2. Start the site (with widget pointing at the backend)

In **another terminal**, from the site root:

```powershell
quarto preview
```

Then open **http://localhost:4200** in your browser.

The widget is configured (via `irw-chat-api-dev.html`) to call **http://localhost:8000/chat**, so the frontend (port 4200) and backend (port 8000) will talk to each other.

## 3. Test the chatbot

1. On any page, click the **chat button** (bottom-right).
2. In the input, try prompts like:
   - **"I need child math assessment data with many participants"**
   - **"How do I fetch datasets with response time in R?"**
   - **"What’s the data standard for IRW?"**
   - **"Point me to the getting started guide"**
3. The agent will use tools (search datasets, get details, generate R code, get docs) and reply. You should see a short “Searching datasets…” message, then the answer.

## If you get "Failed to fetch"

1. **Check the backend is running**  
   Open **http://localhost:8000/health** in a new tab. If it doesn’t load:
   - Start the backend from the **site root**: `uvicorn agent.main:app --reload --host 0.0.0.0 --port 8000`
   - Make sure nothing else is using port 8000.

2. **Check the URL the widget uses**  
   The red error bar under the chat will show the URL it tried (e.g. `http://localhost:8000/chat`). It must match where your backend is running.

3. **Use the same host as the site**  
   If you open the site as **http://127.0.0.1:4200**, the widget still calls **http://localhost:8000**; that’s usually fine. If you’re on another machine or port, set `window.IRW_CHAT_API_URL` in `resources/chat/irw-chat-api-dev.html` to your backend URL and rebuild.

4. **.env for the API key**  
   The backend loads `agent/.env`. Add `OPENAI_API_KEY=sk-...` there so you don’t need to set it in the terminal.

- **"Assistant is not configured (missing OPENAI_API_KEY)":** Add `OPENAI_API_KEY` to `agent/.env` or set it in the terminal before starting uvicorn, then restart the backend.
- **CORS errors in the browser console:** The backend allows all origins by default; if you need to restrict, set `CORS_ORIGINS` in `agent/.env`.

## Turning off the dev API URL for production

In `_quarto.yml`, remove or comment out the line:

```yaml
include-before-body: resources/chat/irw-chat-api-dev.html
```

Then the widget will use `/api/chat` (same origin), and you’d need to proxy or host the API at that path in production.
