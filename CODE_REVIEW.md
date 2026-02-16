# Faqqer Code Review

Hardass review of all 13 files. Line numbers reference the source directly.

---

## 1. `openai_helper.py`

**The Good:** Simple, thin wrapper. Does its job.

**Issues:**

- **Line 6 — Module-level side effect.** `client = OpenAI(...)` runs at import time. If `OPENAI_API_KEY` is unset, `os.environ.get()` returns `None`, the client is created with `api_key=None`, and you don't find out until the first API call explodes with a cryptic error. Should fail fast with a clear message or defer initialization.

- **Line 43 — Flawed tool-call detection logic.** The condition `if tools and tool_choice:` means if you pass `tools` but *not* `tool_choice` (letting the model decide), tool calls are silently ignored and you get `message.content` back instead. The check should be `if message.tool_calls:` regardless of what was passed in.

- **Line 46 — Only reads the first tool call.** `message.tool_calls[0]` silently drops any additional tool calls. Fine for now since you always force a single tool, but it's a latent bug if anyone ever uses `tool_choice="auto"`.

- **Lines 58-60 — Pokemon exception handling.** `except Exception as e: print(...); return None` swallows everything. Transient network errors, auth failures, rate limits, malformed requests — all become the same `None`. Callers have zero ability to distinguish "retry-able" from "your code is broken." At minimum, log the exception type.

- **Line 59 — Print, not logging.** Every script uses `print()` for error reporting. There's no `logging` module anywhere in the project. Fine for a personal tool, but makes it impossible to filter errors from progress output if you ever pipe stdout.

---

## 2. `openai_helper_embedding.py`

**Issues:**

- **Line 5 — Same module-level client problem** as `openai_helper.py`. Two separate `OpenAI()` clients are instantiated across these two files — doubled initialization, doubled risk of `None` API key.

- **Line 36 — Newline replacement is lossy.** `text.replace("\n", " ")` is applied universally. For most use cases this is fine, but if a fact intentionally contains structured content (bullet lists, code), this silently corrupts the input before embedding. At least document the assumption.

- **Lines 47-49 — Returns empty list on failure.** If the API fails on batch 3 of 5, you've already accumulated embeddings for batches 1-2 into `all_embeddings`, then you throw them away and return `[]`. The caller (step 03) treats `[]` as "API failed" and skips the file — correct behavior, but the partial work is wasted. Worse: no indication of *which* batch failed.

- **No retry logic.** Embedding calls are the most likely to hit rate limits (you're sending 100 texts at a time). A single transient 429 kills the entire file. The `openai` Python SDK does have built-in retry, but you're catching the exception before it can propagate.

---

## 3. `01_extract_content.py`

**Issues:**

- **Line 27 — No XML size guard.** `ET.parse(file_path)` loads the entire XML DOM into memory. WordPress exports can be hundreds of MB. This will work fine for most sites, but a large multisite export could OOM. `iterparse` would be safer.

- **Line 46 — Unguarded `.text` access.** `item.find('title').text` will throw `AttributeError` if `<title>` is missing from an `<item>`. Lines 36/39/52/56/58 all do the safe `obj is not None` check, but the title line doesn't. One malformed item kills the whole run.

- **Line 73 — Filename collision potential.** `path.strip('/').replace('/', '_')` means `/foo/bar/` and `/foo/bar` produce the same filename. Also, URL-encoded characters (e.g., `%20`) end up in filenames verbatim, which could cause issues on some filesystems.

- **Line 82 — Aggressive filename sanitization.** `"".join([c for c in title if c.isalpha() or c.isdigit()])` strips spaces, hyphens, and underscores. A title like "COVID-19 FAQ" becomes `covid19faq`. Not catastrophic, but makes debugging harder.

- **Line 100 — Stale usage string.** Says `extract_content_v2.py` but the file is `01_extract_content.py`.

---

## 4. `02_process_content.py`

**Issues:**

- **Line 101 — Comment says "Azure OpenAI".** `# Send to Azure OpenAI with INCREASED max_tokens` — this is the regular OpenAI API. Leftover from a migration. Appears in multiple files.

- **Line 78 — Truthy check on `limit`.** `if limit:` is falsy for `limit=0`, which means `--limit 0` would process all files instead of zero. Pedantic, but the correct check is `if limit is not None:`.

- **Line 108 — Hardcoded max_tokens with misleading comment.** `max_tokens=4000 # <--- Updated to prevent truncation` — the comment suggests this was bumped from a lower value, but there's no validation that 4000 is sufficient. If a page has 200+ facts, the tool-call response could exceed this. The OpenAI API will silently truncate, producing invalid JSON that hits the `JSONDecodeError` on line 123.

- **Line 126 — Error files written alongside outputs.** `output_path.replace(".json", "_error.txt")` puts error files in the output directory. Since step 03 globs for `*.json`, this is fine — but there's no cleanup, and no summary of which files errored. You'd have to manually `ls *_error.txt` to find failures.

- **No resume awareness for errors.** If a file errored previously (creating `_error.txt` but no `.json`), the skip check on line 91 (`os.path.exists(output_path)`) won't trigger, so it'll retry. That's actually good behavior — but it's accidental, not intentional.

---

## 5. `03_generate_embeddings.py`

**Issues:**

- **Line 85 — Inconsistent JSON formatting.** `json.dump(data, f)` (no indent) while every other script uses `indent=2`. The comment even acknowledges this: `# No indent to save space? Or indent=2 for debug.` — make a decision.

- **Line 59 — Silent failure mode.** If `get_embeddings()` returns `[]` (which it does on *any* error — see helper review), the file is silently skipped with no output written. This means on the next run, it'll retry (good), but there's no log of *why* it failed. Combined with the helper's blanket exception catch, debugging embedding failures requires adding print statements.

- **Lines 71-76 — Redundant data structure.** The output keeps both `data['facts']` (list of strings) and `data['facts_with_embeddings']` (list of `{text, vector}` objects). The `text` in each embedded fact is identical to the corresponding entry in `facts`. This roughly doubles the non-vector portion of each file. Not a huge deal, but it's sloppy.

---

## 6. `04_cluster_facts_hdbscan.py`

**Issues:**

- **Line 61 — O(n^2) memory for deduplication.** `cosine_similarity(matrix)` computes the full n x n similarity matrix. With 10,000 facts and 3072-dimensional embeddings, that's a ~800MB matrix. At 50,000 facts it's ~20GB. This will blow up on a large site. Consider chunked comparison or approximate nearest neighbors (e.g., `faiss`).

- **Line 80 — String-based source merging.** `sources[i] += f"; {sources[j]}"` concatenates source filenames with semicolons. This modifies a list extracted from the DataFrame, which works because of how Python references work — but it's fragile. Also, `if sources[j] not in sources[i]` is a substring check, not a set membership check. If source "a.md" exists and you check for "a.md; b.md", the substring check fails correctly, but if you have "a.md" and check for "a", it incorrectly matches.

- **Line 103 — Queue is a list used as a FIFO.** `cluster_queue.pop(0)` is O(n) on a list. Use `collections.deque` for O(1) popleft. Not a problem at current scale, but it's the kind of thing that makes senior engineers wince.

- **Line 119 — HDBSCAN on raw high-dimensional vectors.** 3072-dimensional embeddings fed directly to HDBSCAN with `metric='euclidean'` — HDBSCAN (and most density-based algorithms) suffer from the curse of dimensionality. The `euclidean` metric becomes increasingly meaningless above ~50 dimensions. You should reduce dimensionality first (UMAP or PCA to ~50 dims) or use `metric='cosine'`. The fact that it works at all is because your clusters are strong enough to survive the bad metric, but you're leaving quality on the table.

- **Line 148 — Duplicate queue entries check is wrong.** `if new_id not in cluster_queue` prevents adding a label that's already in the queue — but labels are generated fresh from HDBSCAN sub-labels, so duplicates in the queue shouldn't be possible. The check is harmless but suggests confusion about the algorithm's invariants.

---

## 7. `05_generate_faq.py`

**Issues:**

- **Lines 86-87 — Silent truncation.** If a cluster has more than 40 facts, it silently drops everything after index 40. No warning printed. The LLM generates an answer from a subset of the facts, and you'd never know facts were omitted. At minimum, log when truncation occurs.

- **Line 119 — `questions` stored as a string, not a list.** The field is called `questions` (plural) but stores `data['question']` — a single string. Steps 6, 8, 9, and 10 all have to handle `isinstance(q, list)` checks because of confusion about whether this is a string or list. Pick one format and stick with it.

- **Line 63 — `random.sample` without seed.** In test mode, `random.sample(valid_clusters, test_limit)` gives different clusters every run. Fine for exploratory testing, but makes debugging specific clusters impossible. Add a `--seed` option or at least log which clusters were selected.

- **Line 123 — `verified: False` hardcoded.** Every entry starts with `verified: False`. This field is later shadowed by the `status` field introduced in the PHP reviewer. Both fields exist in the JSON, doing roughly the same thing. The PHP file (line 35) syncs them: `$item['verified'] = ($input['entry']['status'] === 'approved')`. This is a legacy mess waiting to cause a bug.

---

## 8. `06_categories.py`

**Issues:**

- **Line 25 — All questions sent in a single prompt.** `questions_text = "\n".join(clean_questions)` concatenates every question into one string. With 500+ FAQ entries, this could be 20k+ tokens in a single user message. The comment on line 14 acknowledges this ("if you have >500 items, we might random sample") but doesn't actually implement sampling. Token limit exceeded = API error = no categories = pipeline halts.

- **Lines 91-128 — One API call per FAQ entry.** Category assignment makes a separate LLM call for *each* FAQ entry. With 300 entries, that's 300 API calls that could be batched. You could easily classify 10-20 entries per call by sending them as a numbered list and getting back a mapping.

- **Line 126 — Bare `except:`.** `except:` catches everything including `KeyboardInterrupt` and `SystemExit`. Always catch specific exceptions. This one silently returns "Uncategorized" on *any* error, including bugs in your own code.

- **Line 1 — Missing `import os`.** `os.makedirs` is called on line 165, but `os` is never imported. This will crash at runtime when trying to save. (Edit: it works because `openai_helper` imports `os` and Python's module system... no, that's not how it works. This is an actual bug — `os` is used but not imported.)

---

## 9. `07_add_urls_to_sources.py`

**Issues:**

- **Lines 6-9 — Input and output are the same file.** `INPUT_JSON = OUTPUT_JSON = "data/faq_categorized.json"`. If the script crashes mid-write (line 73-74, `file_put_contents` equivalent), you lose your input. Steps 06, 07, and 08 all do this — they all read and overwrite the same file. One crash corrupts the pipeline state and requires re-running from step 05 or restoring from backup. At minimum, write to a temp file and atomically rename.

- **Line 53 — Source files can contain semicolons.** Step 04's deduplication merges sources with semicolons (e.g., `"page1.md; page2.md"`). This script tries to look up that combined string as a single filename, which obviously doesn't exist. The URL cache lookup fails, and you get `live_url: null` for all deduplicated facts. You need to split on `"; "` and look up each source file individually.

- **Line 21 — Magic number.** `for _ in range(20)` scans the first 20 lines. The metadata is always on line 2 (`**Source URL:**`). Reading 20 lines is harmless but suggests the author wasn't sure where the URL would be.

---

## 10. `08_faq_llm_review.py`

**Issues:**

- **Lines 155, 226 — More bare `except:` blocks.** Same issue as step 06. JSON parse errors, `KeyError`, type errors — all silently swallowed. If the LLM returns `{"status": "Pass"}` (lowercase) instead of `"PASS"`, you'd never know why audit results look wrong.

- **Lines 7-8 — Same input/output file.** Same risk as step 07.

- **Line 93 — Resume logic has a subtle gap.** Items are processed if they're missing `audit_status` OR `utility_score`. But if the audit succeeds and the eval fails (API error), the entry gets `audit_status` set but no `utility_score`. On re-run, the `or` condition still picks it up — good. But if the *save* on line 236 happens (it always does, even if some items errored), the partial results are written. If the script is then killed during the *next* run's save, you could have a mix of complete and partial entries. Not likely, but the lack of transactional writes is a theme.

- **Lines 140-147 & 203-209 — Two LLM calls per entry, sequentially.** Audit and eval are independent — they could be parallelized with `asyncio` or at least batched. With 300 entries, that's 600 sequential API calls. This is the slowest step in the pipeline by far, and it's unnecessarily so.

---

## 11. `09_faq_reviewer.php`

**Issues:**

- **Line 21 — No input validation on entry ID.** `$id = $input['entry']['id']` is used directly from user input to match against data. While this is a local-only tool and the ID is compared with `===`, there's no type checking. If someone sends `id: null`, the `foreach` loop compares `null === $item['id']` for every entry, wasting cycles and potentially matching an entry with a null ID.

- **Line 43 — Non-atomic file write.** `file_put_contents($jsonFile, ...)` overwrites the file directly. If the PHP process dies mid-write (browser closed, server killed), the JSON file is corrupted. Use `file_put_contents` with a temp file + `rename()`, or at minimum `LOCK_EX`.

- **Line 176-177 — PHP values injected into JavaScript.** `const JSON_FILE = '<?php echo $jsonFile; ?>';` and `const SELF_URL = '<?php echo basename($_SERVER['PHP_SELF']); ?>';` — these are unescaped PHP-to-JS injections. `$jsonFile` is a hardcoded string so it's safe *now*, but `$_SERVER['PHP_SELF']` can be manipulated in some server configurations (not PHP's built-in server, but if someone deploys this behind Apache). Low risk for a local tool, but sloppy.

- **Line 216 — XSS via category names.** `const options = sortedCats.map(c => '<option value="${c}">${c}</option>')` injects category names directly into HTML without escaping. If a category name contains `<script>` or quotes (unlikely from LLM output, but possible from manual entry via the "Add New Category" button), you get XSS. Since this is a local-only tool, the practical risk is near zero, but it's still bad practice.

- **Lines 256-267 — More unescaped HTML injection.** The sidebar renders `item.category` and question text directly into HTML template literals. Same XSS vector as above.

- **No CSRF protection.** The POST endpoint accepts any request. Again, local-only mitigates this, but if someone runs this on a network-accessible interface, any page can submit entries.

---

## 12. `10_generate_wp_html.py`

**Issues:**

- **Line 57 — Broken WordPress block comment.** `wp_html.append(f'<!-- wp:heading {"level":2} -->')` — this is an f-string, so `{"level":2}` is interpreted as a Python expression with a format spec. Python evaluates `{"level"}` as a set containing the string `"level"`, then applies `:2}` as a format spec. The result is `<!-- wp:heading level -->` instead of the required `<!-- wp:heading {"level":2} -->`. **This silently produces invalid WordPress block markup.** It doesn't crash — it just generates broken output that WordPress won't parse correctly. The `BLOCK_TEMPLATE` on line 10 correctly uses doubled braces (`{{` and `}}`), but line 57 doesn't. This line should either use doubled braces or drop the `f` prefix since `cat_esc` isn't used in it.

- **Line 84 — Trailing spacer after last category.** The spacer is appended unconditionally inside the loop, meaning the output ends with an unnecessary 40px spacer. Minor, but shows the code wasn't tested carefully.

- **Line 78 — `html.escape` on answer text.** This escapes `&`, `<`, `>`, `"` in the answer. But if answers contain intentional HTML (like `<a href="...">` links from source URLs — which step 05's prompt explicitly asks for), the escaping breaks them. You'd end up with literal `&lt;a href=...&gt;` in the WordPress output. Either strip HTML from answers earlier, or don't escape here and trust the content.

---

## 13. `run_pipeline.py`

**Issues:**

- **Line 13 — No stdout/stderr capture.** `subprocess.run(cmd)` inherits the parent's stdout/stderr. This means all output is interleaved in one stream with no way to attribute errors to specific steps after the fact. For a pipeline runner, capturing output per step (at least stderr) would help debugging.

- **Line 15-17 — Exit code is the only error signal.** If a step prints errors to stdout but exits with code 0, the pipeline continues. Steps like 02 and 03 handle errors with `print()` and `continue` — they don't `sys.exit(1)` on partial failures. So the pipeline "succeeds" even if 30% of files failed processing.

- **No timing information.** For a pipeline that makes hundreds of API calls, there's no output showing how long each step took. Adding `time.time()` before/after each step would cost 4 lines and save significant debugging time.

- **Line 6 — `args=[]` mutable default argument.** Classic Python gotcha. The default list is shared across all calls. In practice this is harmless here since `args` is never mutated, but it's the kind of thing that signals "this person doesn't know Python's footguns." Use `args=None` and `args = args or []`.

---

## Holistic Review: Systemic Issues

### 1. The Pipeline Has No Crash Recovery

Steps 06, 07, and 08 all read from and write to the same file (`data/faq_categorized.json`). If any of these steps crashes during the write, the file is corrupted and you lose everything from step 05 onward. There are no backups, no temp-file-then-rename, no journaling. For a pipeline that makes hundreds of API calls (each costing money), this is the single biggest operational risk.

**Fix:** Write to `output.tmp.json`, then `os.replace("output.tmp.json", "output.json")` atomically. Or at minimum, have each step write to a differently-named file.

### 2. Error Handling Is "Log and Pray"

Every error path follows the same pattern: `print("Error: ...")` and either `return None`, `return []`, or `continue`. No exceptions propagate. No error counts are tracked. No summary is printed at the end. The pipeline runner checks exit codes, but individual steps never exit with non-zero codes on partial failures.

Result: you can run the entire pipeline, see "Processing complete" at the end of every step, and have no idea that 40% of your content silently failed. You'd only discover this when the final FAQ has 60% fewer entries than expected and you don't know why.

**Fix:** Track error counts per step. Print a summary at the end ("Processed 150/200, 50 errors"). Exit with non-zero if error rate exceeds a threshold.

### 3. The `questions` Field Is a Type Mess

Step 05 stores `questions` as a string. But at some point (possibly from an earlier version), some entries have it as a list. Steps 06, 08, 09, and 10 all have defensive `isinstance(q, list)` checks. This is four places where a data format inconsistency is papered over instead of fixed. One canonical format should be enforced at the source (step 05) and all downstream code should trust it.

### 4. No Idempotency for Steps 06-08

Steps 06, 07, and 08 modify `faq_categorized.json` in place. Running step 07 twice is fine (it overwrites URLs). But running step 06 twice re-discovers categories and reassigns them — potentially giving different results if the LLM's mood shifts. There's no "already categorized, skip" logic like steps 02 and 03 have. If you re-run the pipeline, steps 06-08 redo all their work and burn API credits.

### 5. Two OpenAI Clients for No Reason

`openai_helper.py` and `openai_helper_embedding.py` each instantiate their own `OpenAI()` client. These should share a single client instance, or at least be in the same module. Two files, two clients, two places to configure, two places where `OPENAI_API_KEY` can be missing.

### 6. The Deduplication-to-URL Pipeline Is Broken

Step 04 merges sources via string concatenation: `"page1.md; page2.md"`. Step 07 tries to look up this combined string as a single filename. It fails, and all deduplicated facts get `live_url: null`. This means any fact that appeared on multiple pages (the most important, most canonical facts) loses its source URL. This is a real, data-corrupting bug in the pipeline.

### 7. Category Assignment Is Unnecessarily Slow

Step 06 makes N+1 API calls (1 for discovery + 1 per FAQ entry). The 1:1 classification is fine — it's clean, debuggable, and the token cost difference from batching is negligible. The problem is that all 301 calls are **sequential**. At ~0.5-1s per round-trip, that's 2.5-5 minutes of wall clock time spent mostly waiting on network.

**Fix:** Use `asyncio` + `aiohttp` (or the OpenAI SDK's async client) with a configurable concurrency limit (default 8). This applies equally to steps 06 and 08. Eight concurrent connections would cut a 5-minute step to ~40 seconds with zero change to the logic or output.

### 8. HDBSCAN on 3072-Dimensional Embeddings

Using Euclidean distance on 3072-dimensional vectors for density-based clustering is mathematically questionable. The curse of dimensionality makes distance metrics unreliable in high dimensions. The standard approach is to reduce to 50-100 dimensions with UMAP first, then cluster. You're getting results because OpenAI embeddings are well-structured, but you're probably getting *worse* results than you would with dimensionality reduction.

### 9. No Data Validation Between Steps

No step validates that its input matches expected schema. If step 02 produces a JSON file missing the `facts` key, step 03 handles it (line 47). But if step 03 produces a file missing `facts_with_embeddings`, step 04 silently skips those facts with no warning. Each step assumes the previous step's output is well-formed, with inconsistent defensive checks. A single schema validation function at the top of each step would catch pipeline corruption early.

### 10. `06_categories.py` Has a Missing Import

`os` is used on line 165 (`os.makedirs`) but never imported. This script will crash when trying to save output. It was likely tested in an environment where `os` leaked in from an interactive session or was patched after the last commit.

---

## Strategic Review: Does Any of This Make Sense?

The bug list above is "you have a typo." This section is "should you have written the essay at all?"

### 1. The "Atomic Facts" Intermediate Representation Is the Best Decision in the Codebase

Decomposing pages into standalone facts before clustering is genuinely smart. Most FAQ generators go straight from "page" to "Q&A pair," which means one page = one FAQ entry, and cross-page topics never get synthesized. The fact-level decomposition lets you merge information from 5 different pages into one coherent answer. This is the core insight that makes the pipeline worth having. Don't lose this.

### 2. But You're Building a Data Pipeline Without a Data Pipeline Tool

You've hand-rolled a 10-step ETL pipeline using numbered scripts, flat files, and `subprocess.run`. This is fine for a prototype, but you've already hit the problems that pipeline frameworks exist to solve:

- **No dependency graph.** Steps must run in order. If step 04's output changes, you have to manually know to re-run 05-08.
- **No caching/invalidation.** Steps 02-03 have manual "skip if output exists" checks. Steps 06-08 don't. There's no way to say "re-run from step 04 onward."
- **No parallelism.** Steps 02, 03, 06, and 08 process items independently — they could trivially parallelize across files/entries.
- **No provenance.** If the final HTML looks wrong, you can't trace which step produced the bad data without manually inspecting intermediate files.

A pipeline framework (Prefect, Luigi, Make, etc.) would solve these problems in theory. In practice, this pipeline runs once per site and has 8 linear steps. Adding a framework means learning it, wiring it up, and maintaining the integration — all for a run-once workflow. The real fixes are simpler: atomic file writes, distinct output files per step (so steps 06-08 stop mutating the same JSON), and error counting. Those are bugs, not architecture problems. `run_pipeline.py` is fine as an orchestrator.

### 3. Steps 06-08 Should Be One Script, Not Three

Steps 06 (categorize), 07 (add URLs), and 08 (audit + score) all read the same JSON, mutate it, and write it back. They're separated into three scripts for conceptual clarity, but operationally they're three passes over the same data structure. This causes:

- The "same file as input and output" corruption risk
- Three separate script invocations (each with Python startup overhead)
- No ability to batch operations (e.g., categorize + audit in one LLM call)

These should be one script with three internal phases, or at minimum, each should write to a distinct output file so the pipeline has actual checkpoints.

### 4. The LLM-as-Categorizer (Step 06) Is the Wrong Tool

You use HDBSCAN + K-Means for clustering facts (step 04) — a legitimate ML approach. Then for categorization (step 06), you throw all that away and ask GPT to read every question, invent categories, then classify each question individually. This is:

- **Slow:** 301 sequential API round-trips, mostly waiting on network. The 1:1 classification approach is correct (clean, debuggable), but running them sequentially is not.
- **Non-deterministic:** Run it twice, get different categories
- **Fragile:** One API hiccup and you have "Uncategorized" entries

The 1:1 LLM classification is defensible — but run them concurrently (8 at a time via `asyncio`) to fix the latency problem.

Alternatively, you already have embeddings. You could skip the LLM entirely for classification:

1. **Average the fact embeddings per FAQ entry** to get a FAQ-level embedding
2. **Cluster those** with the same HDBSCAN approach you already wrote
3. **Use one LLM call** to *name* each cluster (instead of one call per entry)

This would be deterministic (same embeddings = same clusters) and reuse infrastructure you already built. The LLM is great at naming clusters; it's wasteful at *creating* them when you have embeddings.

### 5. The Embedding Model Is Overkill (and Expensive)

`text-embedding-3-large` produces 3072-dimensional vectors. For clustering short factual sentences, `text-embedding-3-small` (1536 dims) or even `text-embedding-3-large` with the `dimensions` parameter set to 256-512 would work just as well and:

- Cost less per token
- Produce smaller intermediate files (the `content_embedded/` directory is probably enormous)
- Make the cosine similarity matrix in step 04 4x smaller (and 4x faster to compute)
- Reduce the curse-of-dimensionality problem for HDBSCAN

OpenAI's `text-embedding-3-large` supports a `dimensions` parameter that truncates via Matryoshka representation learning — you get the first N dimensions and they're still good. Test with 256 or 512 dimensions before committing to 3072.

### 6. The PHP Review Tool Is Missing Power-User Features

The PHP reviewer is a single-file app with zero dependencies that you can drop on any webserver — that's a genuine strength. Non-technical colleagues can review entries without installing Python or touching a terminal. Don't rewrite this in Streamlit.

What it's missing:

- **No batch operations.** No way to approve all entries matching criteria (e.g., "approve all with utility_score > 7 and audit_status = PASS"). Every entry requires manual clicks. A small Python CLI script alongside the PHP tool would solve this: `python 09_batch.py --approve "utility_score > 7 AND audit_status == PASS"`.
- **No undo.** Approve something by accident? Edit the JSON by hand. Even a simple "last 10 actions" log with a revert button would help.
- **No multi-user safety.** Two people reviewing simultaneously will overwrite each other's saves (last write wins). Acceptable for small teams, but worth knowing about.

### 7. The WordPress Output Format Is Fragile

Step 10 generates WordPress Gutenberg block HTML. This format is:
- Not standardized (Gutenberg block comments are WordPress-internal markup)
- Breaks if WordPress updates its block format
- Requires manual copy-paste into the WordPress editor

Better approaches:
- **WordPress REST API:** POST directly to `/wp-json/wp/v2/pages` with structured content. No copy-paste, no block markup to get wrong.
- **Export as structured JSON/YAML:** Let a WordPress plugin (like ACF or Custom Fields) consume structured data and render it with a template. This separates content from presentation.
- **Generate shortcodes instead of blocks:** `[faq_accordion category="Tuition"]` is more resilient than raw block HTML.

If you must generate block HTML, at least use a template engine (Jinja2) instead of f-strings. The bug on line 57 of step 10 exists precisely because f-strings and JSON braces don't mix.

### 8. You're Missing a "Diff" Capability

The pipeline is designed as a one-shot transformation: XML in, HTML out. But FAQ content changes over time. If the source site updates a page, you'd re-run the entire pipeline, losing all human review decisions. There's no way to:

- Detect which facts are new vs. already processed
- Preserve approved entries while adding new ones
- Flag entries whose source facts changed (potentially invalidating the answer)

Adding a content hash (MD5 of the markdown) to each file in step 01 would enable incremental processing. Steps 02-03 already skip existing files, but steps 04-08 always reprocess everything.

### 9. The Deduplication Strategy Deserves More Thought

Cosine similarity > 0.95 is aggressive — it only catches near-identical sentences. Two facts that say the same thing in different words (e.g., "Tuition is $30,000/year" and "Annual tuition costs $30,000") will have similarity ~0.85-0.90 and survive dedup. Meanwhile, the clustering step is supposed to group related facts, but "related" and "duplicate" exist on a spectrum.

Consider:
- **Lowering the threshold to 0.90** and keeping the "best" version (longest, most specific) of each duplicate cluster
- **Using the LLM for dedup** on borderline cases (0.85-0.95 similarity) — cheaper than you'd think if batched
- **Deduplicating at the FAQ level** (step 05 output) rather than the fact level — two similar facts might end up in different clusters and produce near-identical FAQ entries

### 10. The Whole Pipeline Could Be 3 Scripts Instead of 13

If you squint at the pipeline, there are really three logical phases:

1. **Extract & Embed** (steps 01-03): Get content, atomize it, vectorize it
2. **Cluster & Synthesize** (steps 04-07): Group facts, generate Q&A, categorize, enrich
3. **Review & Export** (steps 08-10): Quality check, human review, output

Each phase has a clear input/output contract. The 10-script breakdown made sense during development (test one step at a time), but for operation, it's unnecessary granularity. Collapsing to 3 scripts with clear intermediate files (`facts_embedded.json`, `faq_draft.json`, `faq_final.html`) would eliminate the file-corruption risks, simplify the runner, and make the pipeline easier to reason about.

This doesn't mean deleting code — it means reorganizing into modules. The current scripts become functions called by three phase scripts.
