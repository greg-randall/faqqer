# FAQ Generation Through Content Atomization 

This project takes a WordPress XML export and transforms it into a clean database of "Atomic Facts" to build a structured, high-quality, and categorized FAQ system.

## Quick Start

1.  **Install:** `pip install openai pandas scikit-learn numpy pytest`
2.  **Configure:** Set `export OPENAI_API_KEY="sk-..."`
3.  **Run:** `python run_pipeline.py <your_wordpress_export.xml>`
4.  **Review:** Follow the on-screen instructions to review FAQs in your browser.

## Pipeline Overview

The project follows a streamlined 8-step pipeline from raw XML to a categorized, approved FAQ.

### 1. The Scripts

* `01_extract_content.py`: Parses WordPress XML, removes HTML, and saves clean Markdown files with source metadata.
* `02_process_content.py`: Uses **GPT-4o-mini** to extract "Atomic Facts" (context-aware, independent statements) into JSON.
* `03_generate_embeddings.py`: Generates vector embeddings for every fact using **OpenAI** (`text-embedding-3-large`).
* `04_cluster_facts.py`: Employs HDBSCAN and Recursive K-Means to group facts into granular topics.
* `05_generate_faq.py`: Synthesizes a Question and Answer pair for each cluster using an LLM.
* `06_enrich_faq.py`: **Consolidated enrichment step** that performs dynamic categorization, extracts live source URLs, and runs an LLM audit/utility scoring.
* `07_faq_reviewer.php`: A PHP web interface for human-in-the-loop review, editing, and approval of FAQ entries.
* `08_generate_wp_html.py`: Converts approved entries into WordPress-ready Gutenberg HTML blocks (details/summary).

### 2. Helper Modules

* `openai_helper.py`: Centralized module for all OpenAI API interactions (Chat and Embeddings) with improved error handling and batching.

---

## Data Formats

### Phase 1: Clean Markdown (`/content/`)
Each file represents a website page with metadata headers (`Source URL`, `ID`).

### Phase 2: Atomic Facts JSON (`/content_processed/`)
LLM-extracted facts with resolved context (e.g., pronouns replaced with entities).

### Phase 3: Embedded Facts JSON (`/content_embedded/`)
Same as Phase 2, but including high-dimensional vector arrays for clustering.

### Phase 4: Cluster Report (`data/fact_clusters.csv`)
A mapping of every fact to a hierarchical cluster label (e.g., `0_5_1`).

### Phase 5: FAQ JSON (`data/faq_raw.json`)
Initial Q&A pairs generated from clusters, including linked source facts.

### Phase 6: Enriched FAQ (`data/faq_categorized.json`)
The production-ready JSON. Contains categories, live URLs, audit status (hallucination check), and utility scores (1-10).

### Phase 7: Reviewed FAQ
Updated version of the enriched JSON after manual intervention via the PHP reviewer tool.

### Phase 8: WordPress HTML (`data/faq_final.html`)
Final output containing only `approved` items, sorted by category and utility score.

---

## Usage & Development

**Execution:**

```bash
# 1. Extract content from WP Export
python 01_extract_content.py wordpress-export.xml

# 2. Extract facts
python 02_process_content.py

# 3. Generate Embeddings
python 03_generate_embeddings.py

# 4. Analyze & Cluster
python 04_cluster_facts.py

# 5. Generate FAQ
python 05_generate_faq.py

# 6. Enrich (Categorize, URLs, Audit/Score)
python 06_enrich_faq.py

# 7. Review (Human)
php -S localhost:8000
# Open: http://localhost:8000/07_faq_reviewer.php

# 8. Generate HTML
python 08_generate_wp_html.py
```

**Testing:**
The project includes a comprehensive test suite covering all pipeline steps and data schemas.
```bash
pytest
```
