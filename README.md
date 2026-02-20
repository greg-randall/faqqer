# Faqqer: WordPress to structured FAQ pipeline

Faqqer converts WordPress exports into structured FAQs for both human readers and Answer Engine Optimization (AEO). The pipeline atomizes website pages into standalone facts to improve the accuracy of LLM-driven search and automated support systems. By generating verified Q&A pairs, it helps organizations provide direct answers to specific queries instead of requiring users to search through long-form landing pages.

---

## How it Works

Faqqer breaks long-form pages into standalone facts, then recombines them into answers.

### Extract: pages become atomic facts

The pipeline pulls each page apart into self-contained statements. Context that the original page took for granted (like what "the orientation" refers to) gets injected into every fact.

> **Page A — Academic Calendar**
> "The Fall 2025 orientation for new employees is scheduled for August 11-15. This is a mandatory event for all full-time staff."

* *"The Fall 2025 orientation for new employees is August 11-15."*
* *"The Fall 2025 new employee orientation is mandatory for all full-time staff."*

> **Page B — Employee Onboarding**
> "New hires must attend a five-day orientation. For the 2025 academic year, this session begins on August 11 and concludes on August 15."

* *"New hires at the organization must attend a five-day orientation session."*
* *"The 2025 new hire orientation begins on August 11 and concludes on August 15."*

### Cluster: group by topic, merge duplicates

Facts with similar content are grouped together, even when they come from different pages. Near-duplicates are merged so the same information isn't repeated.

| Cluster: **New Employee Orientation** | Source |
| --- | --- |
| The Fall 2025 orientation for new employees is August 11-15. | Page A |
| The orientation is mandatory for all full-time staff. | Page A |
| New hires must attend a five-day orientation session. | Page B |

### Synthesize: one question, one verified answer

An LLM writes a concise answer grounded only in the cluster's facts — no outside knowledge allowed. A second model audits it for hallucinations.

> **Q:** What are the dates for the Fall 2025 new employee orientation?
>
> **A:** The orientation for new employees runs from August 11 through August 15, 2025. Attendance is mandatory for all full-time staff.

---

## Quick Start

1.  **Install:** `pip install openai pandas scikit-learn numpy pytest markdownify pyyaml lxml`
2.  **Configure:** Set `export OPENAI_API_KEY="sk-..."`
3.  **Run:** `python run_pipeline.py <wordpress_export.xml | markdown_folder>`
4.  **Review:** Open the PHP tool to approve and edit the generated FAQs.

## Pipeline steps

Faqqer uses a run-based architecture. Each execution creates a timestamped folder in `runs/` (e.g., `runs/example.com_2026-02-19_120000/`) containing all intermediate data.

### 1. The Scripts

* `01_import_wordpress.py`: Parses WordPress XML into Markdown files.
* `01_import_markdown.py`: Imports a directory of existing Markdown files.
* `02_process_content.py`: Uses GPT-4o-mini to extract standalone facts from Markdown.
* `03_generate_embeddings.py`: Generates vectors for each fact using `text-embedding-3-large`.
* `04_cluster_facts.py`: Groups facts into topics using HDBSCAN and Recursive K-Means.
* `05_generate_faq.py`: Drafts a question and answer for each cluster.
* `06_enrich_faq.py`: Categorizes entries and audits for hallucinations.
* `07_faq_reviewer.php`: PHP interface for human review and editing.
* `08_generate_wp_html.py`: Converts approved entries into WordPress Gutenberg blocks.

### 2. Helper Modules

* `openai_helper.py`: Manages OpenAI API calls, including error handling and batching.
* `config.py`: Handles run-directory path resolution via `FAQQER_RUN_DIR`.

---

## Data Formats

Each run stores data in a dedicated folder. Below are the relative paths within a run directory:

### Phase 1: Clean Markdown (`/content/`)
Markdown files with source metadata.

```markdown
# Academic Calendar
**Source URL:** https://example.edu/academics/calendar/
**ID:** 1245

## Fall 2025 Semester
* Orientation begins August 11...
```

### Phase 2: Atomic Facts JSON (`/content_processed/`)
Facts extracted by the LLM with context injected.

### Phase 3: Embedded Facts JSON (`/content_embedded/`)
The same data as Phase 2, but with vector arrays.

### Phase 4: Cluster Report (`/data/fact_clusters.csv`)
A CSV mapping facts to hierarchical labels (e.g., `0_5_1`).

### Phase 5-6: FAQ JSON (`/data/faq_raw.json` & `faq_categorized.json`)
Initial and enriched Q&A pairs with linked source facts and audit scores.

### Phase 7-8: Final Output
The review tool updates `faq_categorized.json`, and the generator produces `/data/faq_final.html`.

---

## Usage & Development

**Automated Pipeline:**

```bash
# Provide either an XML export or a folder of markdown files
python run_pipeline.py wordpress-export.xml
```

**Manual Execution:**

To run or resume a specific step, set the `FAQQER_RUN_DIR` environment variable:

```bash
export FAQQER_RUN_DIR="runs/your_run_folder"

python 02_process_content.py
python 03_generate_embeddings.py
# ... etc
```

**Review:**
```bash
FAQQER_RUN_DIR="runs/your_run_folder" php -S localhost:8000
# Open: http://localhost:8000/07_faq_reviewer.php?run_dir=runs/your_run_folder
```

**Generate HTML:**
```bash
FAQQER_RUN_DIR="runs/your_run_folder" python 08_generate_wp_html.py
```

**Testing:**
Run the test suite with:
```bash
pytest
```
