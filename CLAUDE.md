# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Faqqer is an 8-step pipeline that transforms WordPress XML exports into structured, AI-reviewed FAQ systems. It atomizes content into facts, clusters them semantically, synthesizes Q&A pairs, and provides human review before generating WordPress-ready HTML.

## Tech Stack

- **Python 3.10+**: Pipeline scripts (steps 1-6, 8)
- **PHP**: Human review web UI (step 7)
- **OpenAI APIs**: GPT-4o-mini (text processing), text-embedding-3-large (embeddings)
- **ML**: HDBSCAN + recursive K-Means clustering, scikit-learn, pandas, numpy

## Running the Pipeline

```bash
# Prerequisites
pip install openai pandas scikit-learn markdownify numpy
export OPENAI_API_KEY="sk-..."

# One-shot (steps 1-6)
python run_pipeline.py /path/to/wordpress_export.xml

# Individual steps
python 01_extract_content.py wordpress.xml
python 02_process_content.py
python 03_generate_embeddings.py
python 04_cluster_facts.py
python 05_generate_faq.py
python 06_enrich_faq.py

# Human review (step 7)
php -S localhost:8000
# Open http://localhost:8000/07_faq_reviewer.php

# Final export (step 8, after approving entries in review UI)
python 08_generate_wp_html.py
```

Each step checks for existing output and skips already-processed items, enabling pause/resume.

## Architecture

**Linear file-based pipeline**: each numbered script reads from the previous step's output directory, transforms data, and writes to the next.

```
WordPress XML
  → content/*.md                    (01: extract)
  → content_processed/*.json        (02: atomic facts via GPT-4o-mini)
  → content_embedded/*.json         (03: add embedding vectors)
  → data/fact_clusters.csv          (04: deduplicate + cluster)
  → data/faq_raw.json               (05: synthesize Q&A per cluster)
  → data/faq_categorized.json       (06: categorize + URLs + audit/score)
  → PHP review UI                   (07: human approve/reject/edit)
  → data/faq_final.html             (08: WordPress block HTML)
```

**Helper module**:
- `openai_helper.py` — Chat completion + embedding API wrapper

## Key Thresholds (hard-coded)

- Semantic deduplication: cosine similarity > 0.95
- HDBSCAN min_cluster_size: 5
- Max cluster size before recursive split: 15
- Embedding batch size: 100

## Conventions

- Scripts named `NN_descriptive_name.py` indicating execution order
- All intermediate data persisted to disk (no in-memory state between steps)
- Failed items logged to `*_error.txt` files, processing continues
- Output directories (`content/`, `content_processed/`, `content_embedded/`, `data/`) are gitignored

## Testing

```bash
pip install pytest
pytest -v
```

All tests use mocked API calls — no OpenAI key needed.
