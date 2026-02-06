# Export IRW metadata to JSON for the AI agent (RAG and tools).
# Run from project root: Rscript scripts/export_metadata_for_agent.R
# Requires: redivis, dplyr, tidyr, stringr, purrr, tibble, forcats, jsonlite

suppressPackageStartupMessages({
  library(dplyr)
  library(tidyr)
  library(stringr)
  library(purrr)
  library(tibble)
  library(forcats)
  library(jsonlite)
  library(redivis)
})

# Same data pipeline as _load-data-explore.qmd
irw_meta <- redivis$user("bdomingu")$dataset("irw_meta:bdxt")
metadata_table <- irw_meta$table("metadata:h5gs")$to_tibble()

metadata <- metadata_table |>
  mutate(table = str_to_lower(table)) |>
  mutate(
    variable = str_split(variables, "\\| "),
    prefix = str_extract_all(variables, "(?<= )[A-z_]*?(?=_)") |> map(unique) |> map(sort)
  ) |>
  mutate(
    longitudinal = if_else(longitudinal, "longitudinal", "cross-sectional"),
    longitudinal = as.list(longitudinal)
  ) |>
  filter(n_categories != 0)

biblio <- irw_meta$table("biblio:qahg")$to_tibble()
bib_data <- biblio |>
  mutate(table = str_to_lower(table)) |>
  select(
    table,
    license = `Derived_License`,
    data_url = URL__for_data_,
    description = Description,
    reference = Reference_x,
    doi = DOI__for_paper_
  )

tag_table <- irw_meta$table("tags:7nkh")$to_tibble()
na_vals <- c(
  "no access to the osf page", "non-verbal task",
  "I can't find the description of this dataset", "missing description",
  "need help", "no link or info", "Missing (NA)"
)
comma <- "~"
tags <- tag_table |>
  mutate(table = str_to_lower(table)) |>
  left_join(bib_data |> select(table, license)) |>
  mutate(across(everything(), \(s) if_else(s %in% na_vals, "NA", s))) |>
  mutate(across(everything(), \(s) replace_na(s, "NA"))) |>
  mutate(sample = sample |> str_replace_all(",(?= etc)", comma) |> str_remove_all('\\"')) |>
  mutate(across(-table, \(s) s |> str_split(",") |> map(str_trim) |> map(\(x) str_replace_all(x, comma, ",")))) |>
  left_join(metadata |> select(table, longitudinal)) |>
  relocate(longitudinal, .before = age_range)

ds <- c("item_response_warehouse", "item_response_warehouse_2")
urls <- ds |>
  map(\(d) redivis$user("datapages")$dataset(d)$list_tables() |>
        map(\(t) tibble(table = t$name, url = t$properties$url)) |>
        list_rbind()) |>
  list_rbind() |>
  mutate(table = str_to_lower(table), url = str_remove(url, "\\?.*$"))

datasets <- metadata |>
  inner_join(tags) |>
  inner_join(urls) |>
  inner_join(bib_data |> select(-license)) |>
  arrange(table)

# Ensure output directory exists
out_dir <- file.path("agent", "data")
dir.create(out_dir, showWarnings = FALSE, recursive = TRUE)

# Write full metadata for agent tools (jsonlite handles list columns as arrays)
write(
  toJSON(datasets, dataframe = "rows", auto_unbox = TRUE, pretty = TRUE),
  file.path(out_dir, "irw_metadata.json")
)

# Build "dataset cards" for RAG: one searchable text blob per dataset
# so the agent can semantically match user project descriptions to datasets
tag_cols <- setdiff(names(tags), "table")
card_rows <- datasets |> rowwise() |> group_split() |> map(\(d) {
  d <- as.list(d)
  desc <- if (is.null(d$description) || is.na(d$description) || length(d$description) == 0) "No description" else d$description[[1]]
  vars <- if (is.character(d$variables)) d$variables else paste(as.character(d$variables), collapse = ", ")
  density_val <- tryCatch(as.numeric(d$density[[1]]), error = function(e) 0)
  nums <- sprintf(
    "n_responses=%s n_participants=%s n_items=%s n_categories=%s density=%s",
    d$n_responses, d$n_participants, d$n_items, d$n_categories,
    round(if (is.na(density_val)) 0 else density_val, 4)
  )
  tag_vals <- map_chr(tag_cols, \(tc) {
    v <- d[[tc]]
    if (is.null(v) || length(v) == 0) return("")
    paste(as.character(v), collapse = ", ")
  }) |> paste(collapse = " ")
  table_name <- if (is.list(d$table)) d$table[[1]] else d$table
  list(table = table_name, card = sprintf(
    "Dataset: %s. %s Variables: %s. %s Tags: %s",
    table_name, desc, vars, nums, tag_vals
  ))
})

write(
  toJSON(card_rows, auto_unbox = TRUE, pretty = TRUE),
  file.path(out_dir, "irw_cards.json")
)

message("Exported ", nrow(datasets), " datasets to ", out_dir)
