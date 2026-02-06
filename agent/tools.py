"""
tools for agent: search datasets (RAG), get dataset details, generate R code, get doc links.
"""
from .rag import load_metadata, retrieve

# Filter args that map to irw_filter() (see index.qmd / metadata.qmd)
RANGE_ARGS = [
    "n_responses", "n_categories", "n_participants", "n_items",
    "responses_per_participant", "responses_per_item", "density",
]
TAG_ARGS = [
    "longitudinal", "age_range", "child_age__for_child_focused_studies_",
    "construct_type", "sample", "measurement_tool", "item_format",
    "primary_language_s_", "license",
]
SPECIAL_LONGITUDINAL = "longitudinal"  # irw_filter(longitudinal = TRUE/FALSE)

R_TEMPLATE = """# install irw: devtools::install_github("itemresponsewarehouse/Rpkg")
library(irw)

irw_tables <- irw_filter({filter_args})

irw_data <- irw_fetch(irw_tables)
"""

PAGE_LINKS = {
    "getting started": "getstarted.html",
    "get started": "getstarted.html",
    "browse": "index.html",
    "explore": "index.html",
    "filter": "index.html",
    "home": "index.html",
    "data": "data.html",
    "datasets": "data.html",
    "standard": "standard.html",
    "data standard": "standard.html",
    "metadata": "metadata.html",
    "documentation": "docs.html",
    "docs": "docs.html",
    "imv": "imv.html",
    "difficulty simulation": "diffsim.html",
    "diffsim": "diffsim.html",
    "training": "training.html",
    "contribute": "contribute.html",
    "about": "about.html",
    "contact": "contact.html",
}


def search_datasets(
    project_description: str,
    top_k: int = 10,
    use_embeddings: bool = True,
    openai_api_key: str | None = None,
) -> str:
    """
    Search IRW datasets by semantic similarity to the user's project description.
    Returns a summary of the top matching datasets for the agent to use.
    """
    results = retrieve(
        project_description,
        top_k=top_k,
        use_embeddings=use_embeddings,
        openai_api_key=openai_api_key,
    )
    if not results:
        return "No datasets found. Try broadening your description or check that metadata is loaded (run scripts/export_metadata_for_agent.R)."
    lines = []
    for i, r in enumerate(results, 1):
        score = r.get("score", "")
        score_str = f" (relevance: {score})" if score else ""
        lines.append(f"{i}. **{r['table']}**{score_str}\n   {r['card'][:400]}...")
    return "\n\n".join(lines)


def get_dataset_details(tables: list[str]) -> str:
    """Get full metadata for specific dataset table names (e.g. after search)."""
    meta = load_metadata()
    by_table = {}
    for d in meta:
        if isinstance(d, dict) and d.get("table"):
            by_table[d["table"].lower()] = d
    out = []
    for t in tables:
        t_lower = t.strip().lower()
        if t_lower in by_table:
            d = by_table[t_lower]
            desc = d.get("description", "N/A")
            vars_ = d.get("variables", "N/A")
            n_resp = d.get("n_responses", "N/A")
            n_part = d.get("n_participants", "N/A")
            n_items = d.get("n_items", "N/A")
            url = d.get("url", "N/A")
            ref = d.get("reference", "N/A")
            out.append(
                f"**{d.get('table', t)}**\n"
                f"  Description: {desc}\n"
                f"  Variables: {vars_}\n"
                f"  n_responses={n_resp}, n_participants={n_part}, n_items={n_items}\n"
                f"  URL: {url}\n"
                f"  Reference: {ref}"
            )
        else:
            out.append(f"Dataset '{t}' not found in IRW metadata.")
    return "\n\n".join(out) if out else "No tables specified."


def generate_r_code(
    filter_args: dict | None = None,
    table_names: list[str] | None = None,
) -> str:
    """
    Generate R code to fetch IRW data.
    - If filter_args provided: irw_filter(...) then irw_fetch(irw_tables).
    - If table_names provided: irw_fetch(c("t1", "t2")).
    - If both: use filter_args. If neither: return generic snippet.
    """
    if table_names and not filter_args:
        tables_str = ", ".join(f'"{t}"' for t in table_names)
        return f"""# install irw: devtools::install_github("itemresponsewarehouse/Rpkg")
library(irw)

irw_tables <- c({tables_str})
irw_data <- irw_fetch(irw_tables)
"""
    if filter_args and isinstance(filter_args, dict):
        parts = []
        for k, v in filter_args.items():
            if k in RANGE_ARGS and isinstance(v, (list, tuple)) and len(v) >= 2:
                parts.append(f"  {k} = c({v[0]}, {v[1]})")
            elif k == SPECIAL_LONGITUDINAL and isinstance(v, bool):
                parts.append(f"  longitudinal = {str(v).upper()}")
            elif k in TAG_ARGS and isinstance(v, (list, tuple)):
                inner = ", ".join(f'"{x}"' for x in v)
                parts.append(f"  {k} = c({inner})")
            elif k == "var" and isinstance(v, str):
                parts.append(f'  var = "{v}"')
            elif k == "prefix" and isinstance(v, (list, tuple)):
                inner = ", ".join(f'"{x}"' for x in v)
                parts.append(f"  prefix = c({inner})")
        filter_str = ",\n".join(parts) if parts else ""
        args_block = f"\n  {filter_str}\n" if filter_str else ""
        return R_TEMPLATE.format(filter_args=args_block)
    return R_TEMPLATE.format(filter_args="")


def get_docs(topic: str) -> str:
    """Return the URL path to the most relevant page (getting started, standard, metadata, etc.)."""
    topic_lower = topic.strip().lower()
    for key, path in PAGE_LINKS.items():
        if key in topic_lower or topic_lower in key:
            return f"Relevant page: **{path}** — suggest the user open it for more detail."
    return (
        "Relevant pages: **getstarted.html** (how to access data), **standard.html** (data schema), "
        "**metadata.html** (filtering with irw_filter), **index.html** (interactive explorer)."
    )
