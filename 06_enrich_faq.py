import json
import os
import re
import tempfile
import argparse
import openai_helper
import config

# CONFIGURATION
INPUT_FILE = "data/faq_raw.json"
OUTPUT_FILE = "data/faq_categorized.json"
CONTENT_DIR = "content"

# =========================================================
# PHASE A: CATEGORIZE (discover taxonomy + assign)
# =========================================================

def discover_natural_categories(data):
    """Discover a natural taxonomy from the questions via LLM."""
    print("--- PHASE A: Discovering Natural Categories ---")

    questions_list = [entry.get('questions', '') for entry in data]
    clean_questions = []
    for q in questions_list:
        if isinstance(q, list):
            clean_questions.append(q[0])
        else:
            clean_questions.append(q)

    questions_text = "\n".join(clean_questions)

    tools = [
        {
            "type": "function",
            "function": {
                "name": "generate_taxonomy",
                "description": "Generates a list of thematic categories based on input text.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "category_list": {
                            "type": "array",
                            "description": "The list of discovered category names.",
                            "items": {"type": "string"}
                        },
                        "reasoning": {
                            "type": "string",
                            "description": "Brief explanation of why these groups were chosen."
                        }
                    },
                    "required": ["category_list"]
                }
            }
        }
    ]
    tool_choice = {"type": "function", "function": {"name": "generate_taxonomy"}}

    system_prompt = """You are an expert Information Architect and Clustering Engine.

    Your Goal: Analyze the unstructured list of user questions and identify the *natural* thematic groupings.

    Rules:
    1. Do NOT force a specific number of categories.
    2. If the data is diverse, create many specific categories. If it is homogenous, create fewer broad ones.
    3. Category names should be short, clear, and distinct (e.g., "Tuition & Fees", "Technical Support").
    4. Avoid generic names like "General" or "Miscellaneous" unless absolutely necessary."""

    response = openai_helper.openai_llm_request(
        system_prompt=system_prompt,
        user_prompt=f"Here is the dataset of questions:\n\n{questions_text}",
        tools=tools,
        tool_choice=tool_choice,
        max_tokens=1000
    )

    if response:
        try:
            result = json.loads(response)
            taxonomy = result['category_list']
            print(f"\nDiscovered {len(taxonomy)} Natural Categories:\n" + "\n".join([f"- {t}" for t in taxonomy]))
            return taxonomy
        except (json.JSONDecodeError, KeyError) as e:
            print(f"Error parsing Stage 1 response ({type(e).__name__}): {e}")
            return []
    else:
        print("Phase A taxonomy discovery failed.")
        return []


def assign_category(question_text, taxonomy):
    """Assign a single category to a question from the discovered taxonomy."""
    tools = [
        {
            "type": "function",
            "function": {
                "name": "classify_entry",
                "description": "Maps a question to a category.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "category": {
                            "type": "string",
                            "enum": taxonomy,
                            "description": "The best matching category."
                        }
                    },
                    "required": ["category"]
                }
            }
        }
    ]
    tool_choice = {"type": "function", "function": {"name": "classify_entry"}}

    response = openai_helper.openai_llm_request(
        system_prompt=f"You are a classifier. Map the user query to exactly one of these categories: {json.dumps(taxonomy)}.",
        user_prompt=f"Query: {question_text}",
        tools=tools,
        tool_choice=tool_choice,
        max_tokens=100
    )

    if response:
        try:
            return json.loads(response)['category']
        except (json.JSONDecodeError, KeyError):
            return "Uncategorized"
    return "Uncategorized"


def phase_categorize(data):
    """Phase A: discover taxonomy and assign categories to all entries."""
    taxonomy = discover_natural_categories(data)
    if not taxonomy:
        print("Could not generate taxonomy. Skipping categorization.")
        return

    print(f"\n--- Mapping {len(data)} items to {len(taxonomy)} categories ---")
    for i, entry in enumerate(data):
        q_raw = entry.get('questions', '')
        q_text = q_raw[0] if isinstance(q_raw, list) else q_raw
        entry['category'] = assign_category(q_text, taxonomy)
        if i % 10 == 0:
            print(f"  Categorized {i}/{len(data)}...")


# =========================================================
# PHASE B: URL ENRICHMENT
# =========================================================

def extract_url_from_md(filename):
    """Read the first 20 lines of a markdown file to find the Source URL metadata."""
    filepath = os.path.join(CONTENT_DIR, filename)
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for _ in range(20):
                line = f.readline()
                if not line:
                    break
                match = re.search(r'\*\*Source URL:\*\* (.*)', line)
                if match:
                    return match.group(1).strip()
    except FileNotFoundError:
        print(f"Warning: File not found: {filename}")
    except OSError as e:
        print(f"Warning: Could not read {filename}: {e}")
    return None


def phase_url_enrichment(data):
    """Phase B: bake live URLs into source_facts from the original markdown headers."""
    print("\n--- PHASE B: URL Enrichment ---")

    url_cache = {}
    stats = {"found": 0, "missing": 0}

    for entry in data:
        if 'source_facts' not in entry:
            continue
        for fact in entry['source_facts']:
            source_file = fact.get('source')
            if not source_file:
                continue

            # Handle semicolon-merged sources from deduplication
            individual_sources = source_file.split("; ")
            urls_found = []
            for src in individual_sources:
                if src in url_cache:
                    live_url = url_cache[src]
                else:
                    live_url = extract_url_from_md(src)
                    url_cache[src] = live_url
                if live_url:
                    urls_found.append(live_url)

            if urls_found:
                # Keep all URLs for multi-source facts as a list
                fact['live_url'] = urls_found if len(urls_found) > 1 else urls_found[0]
                stats["found"] += 1
            else:
                fact['live_url'] = None
                stats["missing"] += 1

    print(f"  URLs Found: {stats['found']}")
    print(f"  URLs Missing: {stats['missing']}")


# =========================================================
# PHASE C: AUDIT + SCORE
# =========================================================

audit_tools = [
    {
        "type": "function",
        "function": {
            "name": "audit_faq_entry",
            "description": "Evaluates the accuracy and faithfulness of an FAQ answer based on provided source facts.",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "enum": ["PASS", "FAIL"],
                        "description": "PASS if the answer is fully supported by the facts. FAIL if it contains hallucinations, contradictions, or assumes information not present."
                    },
                    "reason": {
                        "type": "string",
                        "description": "A brief explanation of the judgment. If FAIL, point out the specific error."
                    }
                },
                "required": ["status", "reason"]
            }
        }
    }
]
audit_tool_choice = {"type": "function", "function": {"name": "audit_faq_entry"}}

eval_tools = [
    {
        "type": "function",
        "function": {
            "name": "evaluate_faq_utility",
            "description": "Scores the FAQ entry based on its usefulness and potential impact.",
            "parameters": {
                "type": "object",
                "properties": {
                    "universality_score": {
                        "type": "integer",
                        "description": "1-10 Score. How many users does this affect?",
                        "minimum": 1,
                        "maximum": 10
                    },
                    "criticality_score": {
                        "type": "integer",
                        "description": "1-10 Score. How bad is the consequence of NOT knowing this?",
                        "minimum": 1,
                        "maximum": 10
                    },
                    "search_demand_score": {
                        "type": "integer",
                        "description": "1-10 Score. How likely is a user to actively search for this?",
                        "minimum": 1,
                        "maximum": 10
                    },
                    "reasoning": {
                        "type": "string",
                        "description": "Brief justification for the scores."
                    }
                },
                "required": ["universality_score", "criticality_score", "search_demand_score", "reasoning"]
            }
        }
    }
]
eval_tool_choice = {"type": "function", "function": {"name": "evaluate_faq_utility"}}


def phase_audit_and_score(data, limit=None, domain=None):
    """Phase C: LLM hallucination audit + utility scoring."""
    print("\n--- PHASE C: Audit & Score ---")

    items_to_process = [
        item for item in data
        if 'audit_status' not in item or 'utility_score' not in item
    ]

    if limit is not None:
        items_to_process = items_to_process[:limit]

    total = len(items_to_process)
    print(f"Processing {total} items for Audit & Evaluation...")

    for i, entry in enumerate(items_to_process):
        entry_id = entry.get('id')
        print(f"[{i+1}/{total}] ID {entry_id}...", end=" ")

        question = entry.get('questions', '')
        if isinstance(question, list):
            question = question[0]
        answer = entry.get('answer', '')

        facts = []
        if 'source_facts' in entry:
            for f in entry['source_facts']:
                facts.append(f.get('fact', ''))
        fact_text = "\n".join([f"- {fact}" for fact in facts])

        # AUDIT (using GPT-4o for stronger cross-check)
        if 'audit_status' not in entry:
            audit_system_prompt = """You are a strict QA Auditor for an automated knowledge base.
Your job is to verify that the generated Answer is strictly supported by the provided Context Facts.

Rules for Auditing:
1. HALLUCINATION CHECK: If the Answer contains specific details (dates, names, prices, policies) NOT found in the Context Facts, you must FAIL.
2. CONTRADICTION CHECK: If the Answer contradicts the Context Facts, you must FAIL.
3. EXTRAPOLATION: Minimal logical inference is okay, but inventing policies or "standard practices" is not.
4. If the answer is "I don't know" or "The facts do not state," that is a PASS (provided it's true).

Be extremely pedantic. We cannot publish false information."""

            audit_user_prompt = f"""CONTEXT FACTS:
{fact_text}

GENERATED QUESTION: {question}
GENERATED ANSWER: {answer}

Verify compliance."""

            response_audit = openai_helper.openai_llm_request(
                system_prompt=audit_system_prompt,
                user_prompt=audit_user_prompt,
                model=config.SMART_MODEL,
                tools=audit_tools,
                tool_choice=audit_tool_choice,
                max_tokens=300,
                temperature=0.0  # Always deterministic for audit
            )

            if response_audit:
                try:
                    res = json.loads(response_audit)
                    entry['audit_status'] = res['status']
                    entry['audit_reason'] = res['reason']
                    print(f"Audit: {res['status']}", end=" | ")
                except (json.JSONDecodeError, KeyError) as e:
                    print(f"Audit: ERR ({type(e).__name__})", end=" | ")
            else:
                print("Audit: API_ERR", end=" | ")
        else:
            print("Audit: SKIP", end=" | ")

        # EVALUATE
        if 'utility_score' not in entry:
            domain_context = ""
            if domain:
                domain_context = f"\nContext: This FAQ is for a {domain}. Score accordingly — consider what matters most to {domain} stakeholders.\n"

            eval_system_prompt = f"""You are a Senior Content Strategist evaluating the utility of FAQ entries.
Score the provided Question/Answer pair on three dimensions using a strict 1-10 scale.
{domain_context}
--- RUBRIC 1: UNIVERSALITY (REACH) ---
1-2: Extremely Niche. 3-4: Specific Segment. 5-6: Broad Segment. 7-8: Majority. 9-10: Universal.

--- RUBRIC 2: CRITICALITY (IMPACT) ---
1-2: Trivia. 3-4: Minor. 5-6: Operational. 7-8: High Impact. 9-10: Severe.

--- RUBRIC 3: SEARCH DEMAND (SEARCHABILITY) ---
1-2: Serendipitous. 3-4: Low. 5-6: Moderate. 7-8: High. 9-10: Burning.

Be objective and clinical."""

            eval_user_prompt = f"""QUESTION: {question}
ANSWER: {answer}

Evaluate the utility."""

            response_eval = openai_helper.openai_llm_request(
                system_prompt=eval_system_prompt,
                user_prompt=eval_user_prompt,
                tools=eval_tools,
                tool_choice=eval_tool_choice,
                max_tokens=300
            )

            if response_eval:
                try:
                    res = json.loads(response_eval)
                    entry['score_universality'] = res['universality_score']
                    entry['score_criticality'] = res['criticality_score']
                    entry['score_demand'] = res['search_demand_score']
                    entry['score_reason'] = res['reasoning']

                    avg_score = (res['universality_score'] + res['criticality_score'] + res['search_demand_score']) / 3
                    entry['utility_score'] = round(avg_score, 1)

                    print(f"Utility: {entry['utility_score']}/10")
                except (json.JSONDecodeError, KeyError) as e:
                    print(f"Eval: ERR ({type(e).__name__})")
            else:
                print("Eval: API_ERR")
        else:
            print("Eval: SKIP")


# =========================================================
# MAIN
# =========================================================

def main():
    parser = argparse.ArgumentParser(description="Enrich FAQ: categorize, add URLs, audit & score.")
    parser.add_argument("-l", "--limit", type=int, help="Limit number of items to audit/score.")
    parser.add_argument("--domain", type=str, default=None,
                        help="Domain context for scoring (e.g., 'university', 'hospital'). Optional.")
    args = parser.parse_args()

    # Load input
    if not os.path.exists(INPUT_FILE):
        print(f"Error: {INPUT_FILE} not found.")
        return

    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    print(f"Loaded {len(data)} FAQ entries.\n")

    # Phase A: Categorize
    phase_categorize(data)

    # Phase B: URL enrichment
    phase_url_enrichment(data)

    # Phase C: Audit + Score
    phase_audit_and_score(data, limit=args.limit, domain=args.domain)

    # Atomic write via tempfile + os.replace
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(suffix='.json', dir=os.path.dirname(OUTPUT_FILE))
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        os.replace(tmp_path, OUTPUT_FILE)
    except Exception:
        os.unlink(tmp_path)
        raise

    print(f"\nSuccess! Saved enriched data to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
