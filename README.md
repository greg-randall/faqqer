# Faqqer: WordPress to structured FAQ pipeline

Faqqer converts WordPress exports into structured FAQs for both human readers and Answer Engine Optimization (AEO). The pipeline atomizes website pages into standalone facts to improve the accuracy of LLM-driven search and automated support systems. By generating verified Q&A pairs, it helps organizations provide direct answers to specific queries instead of requiring users to search through long-form landing pages.

---

## How it Works

Faqqer breaks long-form pages into standalone facts, then recombines them into answers.

### Extract: pages become atomic facts

The pipeline pulls each page apart into self-contained statements. Context that the original page took for granted (like what "the orientation" refers to) gets injected into every fact.

> **Page A — Academic Calendar**
> "The Fall 2025 orientation for new employees is scheduled for August 11-15. This is a mandatory event for all full-time staff."

&rarr; *"The Fall 2025 orientation for new employees is August 11-15."*
&rarr; *"The Fall 2025 new employee orientation is mandatory for all full-time staff."*

> **Page B — Employee Onboarding**
> "New hires must attend a five-day orientation. For the 2025 academic year, this session begins on August 11 and concludes on August 15."

&rarr; *"New hires at the organization must attend a five-day orientation session."*
&rarr; *"The 2025 new hire orientation begins on August 11 and concludes on August 15."*

### Cluster: facts from different pages converge

Embeddings reveal that four facts from two unrelated pages describe the same topic. Duplicates are merged; the rest form a cluster.

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

1.  **Install:** `pip install openai pandas scikit-learn numpy pytest markdownify pyyaml`
2.  **Configure:** Set `export OPENAI_API_KEY="sk-..."`
3.  **Run:** `python run_pipeline.py <your_wordpress_export.xml>`
4.  **Review:** Open the PHP tool to approve and edit the generated FAQs.

## Pipeline steps

The project uses an 8-step process to go from raw XML to a categorized FAQ.

### 1. The Scripts

* `01_extract_content.py`: Parses WordPress XML into Markdown files with source metadata.
* `02_process_content.py`: Uses GPT-4o-mini to extract standalone facts from the Markdown.
* `03_generate_embeddings.py`: Generates vectors for each fact using `text-embedding-3-small`.
* `04_cluster_facts.py`: Uses HDBSCAN and Recursive K-Means to group facts into topics and deduplicate similar information.
* `05_generate_faq.py`: Drafts a question and answer for each cluster.
* `06_enrich_faq.py`: Categorizes entries, maps them to original URLs, and uses GPT-4o to audit for hallucinations.
* `07_faq_reviewer.php`: PHP interface for human review and editing.
* `08_generate_wp_html.py`: Converts approved entries into WordPress Gutenberg blocks.

### 2. Helper Modules

* `openai_helper.py`: Manages OpenAI API calls, including error handling and batching.

---

## Data Formats

### Phase 1: Clean Markdown (`/content/`)
Markdown files with `Source URL` and `ID` headers.

```markdown
# Academic Calendar
**Source URL:** https://example.edu/academics/calendar/
**ID:** 1245

## Fall 2025 Semester
* Orientation begins August 11...
```

### Phase 2: Atomic Facts JSON (`/content_processed/`)
Facts extracted by the LLM with context injected (e.g., pronouns replaced with names).

```json
{
  "page_topic": "Academic Calendar",
  "facts": [
    "The Fall 2025 Orientation for New Employees is from Monday, August 11 through Friday, August 15.",
    "The Fall 2025 registration bills are available on the portal on August 15."
  ],
  "source_file": "academics_calendar.md"
}
```

### Phase 3: Embedded Facts JSON (`/content_embedded/`)
The same data as Phase 2, but with vector arrays.

### Phase 4: Cluster Report (`data/fact_clusters.csv`)
A CSV mapping facts to hierarchical labels (e.g., `0_5_1`).

| cluster_label | source | fact |
| --- | --- | --- |
| 0_5_1 | hr_calendar.md | The Fall 2025 Orientation... |
| 0_5_1 | employees_events.md | Orientation is mandatory for new hires... |
| 0_12_0 | admissions_fees.md | The application fee is $50... |

### Phase 5: FAQ JSON (`data/faq_raw.json`)
Initial Q&A pairs with linked source facts.

### Phase 6: Enriched FAQ (`data/faq_categorized.json`)
Adds categories, live URLs, audit results, and utility scores.

### Phase 7: Reviewed FAQ
Updates the enriched JSON after manual edits in the PHP tool.

### Phase 8: WordPress HTML (`data/faq_final.html`)
HTML output for `approved` items, sorted by category and score.

---

## Humanizer: Reviewer Guidelines

The following guide is used during the human review phase (Step 7) to ensure the AI-generated text is accurate and reads naturally.

### Identify and remove AI patterns

1. **Undue Emphasis on Significance:** Remove phrases like "testament to," "pivotal moment," or "evolving landscape."
2. **Superficial -ing Endings:** Avoid tacking on phrases like "highlighting the importance of..." or "ensuring that..."
3. **Vague Attributions:** Replace "Industry reports suggest" or "Experts argue" with specific sources and dates.
4. **Promotional Language:** Remove subjective adjectives like "groundbreaking," "stunning," or "nestled in the heart of."
5. **Copula Avoidance:** Use "is" or "are" instead of "serves as," "stands as," or "functions as."
6. **Rule of Three:** Avoid forcing ideas into groups of three (e.g., "fast, reliable, and secure").
7. **Filler Phrases:** Replace "In order to" with "To" and "Due to the fact that" with "Because."

### Writing for humans

* **Rhythm:** Vary your sentence lengths.
* **Specificity:** Use numbers and dates instead of vague adjectives like "significant."
* **Point of View:** Ensure the writing sounds like it was written by someone who understands the subject.
* **Read it Aloud:** if a sentence is hard to say, it will be hard to read.

---

## Usage & Development

**Execution:**

```bash
# Run the full pipeline
python run_pipeline.py wordpress-export.xml

# Or run individual steps
python 01_extract_content.py wordpress-export.xml
python 02_process_content.py
python 03_generate_embeddings.py
python 04_cluster_facts.py
python 05_generate_faq.py
python 06_enrich_faq.py

# Review
php -S localhost:8000
# Open: http://localhost:8000/07_faq_reviewer.php

# Generate HTML
python 08_generate_wp_html.py
```

**Testing:**
Run the test suite with:
```bash
pytest
```
