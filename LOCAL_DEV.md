# Running the site on localhost

This is a **Quarto** website (not Next.js). It uses R for some pages and builds to static HTML. Here’s how to run it locally.

## What you need

1. **Quarto** — the site builder (like the “build + dev server” for this project)  
   - Install: https://quarto.org/docs/get-started/  
   - On Windows: download the installer, or `winget install Quarto.Quarto`

2. **R** — used to run R code in the `.qmd` files when the site is built  
   - Install: https://cran.r-project.org/  
   - The project uses **renv** for R packages (similar to `node_modules`)

3. **Rtools** (Windows only) — needed to build R packages that use C++ (e.g. Rcpp)  
   - Install: https://cran.r-project.org/bin/windows/Rtools/  
   - Use the version that matches your R (e.g. “Rtools 4.x for R 4.x”).  
   - During setup, check **“Add rtools to the system PATH”**.  
   - Restart the terminal after installing, then run `renv::restore()` again.

## Steps (from the project root)

### 1. Install Rtools (Windows only, first time)

If `renv::restore()` fails with **'make' not found** or similar:

1. Install **Rtools**: https://cran.r-project.org/bin/windows/Rtools/  
   - Pick the version for your R (e.g. Rtools 4.4 for R 4.4).  
   - In the installer, check **“Add rtools to the system PATH”**.  
2. **Close and reopen** your terminal (or restart the IDE).  
3. Run step 2 again.

### 2. Restore R dependencies (first time only)

Open a terminal in the project folder (`site/`) and run:

```powershell
Rscript -e "renv::restore()"
```

This installs the R packages listed in `renv.lock` (e.g. `dplyr`, `redivis`).  
If that fails, open R or RStudio in this project and run `renv::restore()` there.

### 3. Start the preview server

In the same folder, run:

```powershell
quarto preview
```

- Quarto will render the site and start a local server.
- It should open a browser, or you can go to: **http://localhost:4200**
- Port is set in `_quarto.yml` under `preview.port` (4200).

### 4. (Optional) Redivis / home page data

The **Home** page runs R code that fetches metadata from **Redivis**. If you don’t have Redivis set up:

- You may see an error when that page is built, or
- You might need to log in to Redivis (R will prompt) or set a `REDIVIS_API_TOKEN` env var.

Other pages (Getting Started, Data Standard, etc.) should still build and work.

---

## Comparison to Next.js

| Next.js              | This project (Quarto)        |
|----------------------|-----------------------------|
| `npm run dev`        | `quarto preview`            |
| `npm run build`      | `quarto render`             |
| `package.json`      | `renv.lock` + R packages    |
| React components     | `.qmd` files (markdown + R + JS) |
| Port 3000 (default)  | Port 4200 (in `_quarto.yml`) |

---

## (Optional) Chat widget with AI agent

To test the **IRW Data Assistant** chat (bottom-right button):

1. **Export metadata** (optional; uses sample data if you skip):  
   `Rscript scripts/export_metadata_for_agent.R`

2. **Run the Python backend** (from project root):  
   `pip install -r agent/requirements.txt`  
   Then:  
   `$env:OPENAI_API_KEY = "your-key"; uvicorn agent.main:app --reload --port 8000`

3. **Point the widget at the backend:**  
   In `_quarto.yml`, under `format.html`, add:  
   `include-before-body: resources/chat/irw-chat-api-dev.html`  
   so the widget calls `http://localhost:8000/chat`.

4. Run `quarto preview` again and use the chat on the site.
