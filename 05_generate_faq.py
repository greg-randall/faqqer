import pandas as pd
import json
import os
import random
import argparse
import openai_helper
import config

# Configuration
INPUT_CSV = os.path.join(config.get_run_dir(), "data", "fact_clusters.csv")
OUTPUT_JSON = os.path.join(config.get_run_dir(), "data", "faq_raw.json")

# ---------------------------------------------------------
# Define the Tool (JSON Schema)
# ---------------------------------------------------------
tools = [
    {
        "type": "function",
        "function": {
            "name": "synthesize_faq",
            "description": "Synthesizes facts into a FAQ entry for prospective and current users.",
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "A single, natural question a user might type into Google. Write it like a real search query—can be casual ('program application fee') or a full sentence ('How much does it cost to apply?'). Never use 'What is the policy on...' or 'Can you explain...'."
                    },
                    "synthesized_answer": {
                        "type": "string",
                        "description": "A thorough answer using information from the provided facts. Lead with a direct 1-2 sentence summary, then expand with supporting details. Use bullet points or numbered lists when presenting multiple items (requirements, steps, options, deadlines). Organize logically—group related details together. Light framing and connective phrases are fine, but every factual claim must come from the provided facts. Include URLs from facts when present."
                    },
                },
                "required": ["question", "synthesized_answer"]
            }
        }
    }
]

tool_choice = {"type": "function", "function": {"name": "synthesize_faq"}}

def generate_faq(test_limit=None):
    if not os.path.exists(INPUT_CSV):
        print(f"Error: Could not find {INPUT_CSV}")
        return

    df = pd.read_csv(INPUT_CSV, encoding='utf-8')

    # Check for the hierarchical label column
    group_col = 'cluster_label' if 'cluster_label' in df.columns else 'cluster_id'

    # Get all unique clusters
    all_clusters = df[group_col].unique()

    # Pre-filter to remove noise
    valid_clusters = [c for c in all_clusters if "noise" not in str(c) and str(c) != "-1"]

    print(f"Found {len(valid_clusters)} valid topics (excluding noise).")

    # Apply Test Limit
    if test_limit:
        if test_limit > len(valid_clusters):
            test_limit = len(valid_clusters)
        print(f"\n--- TEST MODE: Randomly selecting {test_limit} clusters ---")
        selected_clusters = random.sample(valid_clusters, test_limit)
    else:
        selected_clusters = valid_clusters

    # Resume: load existing output if present
    output_filename = OUTPUT_JSON
    if test_limit:
        output_filename = os.path.join(config.get_run_dir(), "data", "faq_TEST.json")

    knowledge_base = []
    existing_ids = set()
    if os.path.exists(output_filename) and not test_limit:
        try:
            with open(output_filename, 'r', encoding='utf-8') as f:
                knowledge_base = json.load(f)
            existing_ids = {entry['id'] for entry in knowledge_base}
            if existing_ids:
                print(f"Resuming: {len(existing_ids)} entries already processed.")
        except (json.JSONDecodeError, KeyError):
            knowledge_base = []

    print(f"Synthesizing {len(selected_clusters)} FAQ entries...")

    total_clusters = len(selected_clusters)
    for i, label in enumerate(selected_clusters):
        # Skip already-processed clusters (resume)
        if str(label) in existing_ids:
            print(f"[{i+1}/{total_clusters}] Skipping Topic {label} (already processed)")
            continue

        cluster_data = df[df[group_col] == label]

        # 1. Build the Linked Data (Fact + Source)
        linked_facts = cluster_data[['fact', 'source']].to_dict('records')

        # 2. Extract just the text for the LLM Prompt
        prompt_facts_text = [item['fact'] for item in linked_facts]

        # Safety Truncation for Prompt (save tokens)
        if len(prompt_facts_text) > 40:
            print(f"  Warning: Truncating {len(prompt_facts_text)} facts to 40 for topic {label}")
            prompt_facts_text = prompt_facts_text[:40]

        print(f"[{i+1}/{total_clusters}] Processing Topic {label}...")

        user_prompt = "FACTS:\n" + "\n".join([f"- {f}" for f in prompt_facts_text])

        response = openai_helper.openai_llm_request(
            system_prompt="""You are a web editor for the organization's website. Your job is to create FAQ entries that help prospective and current users find comprehensive answers quickly.

FAITHFULNESS: Every factual claim in your answer must come from the provided facts. You may use connective phrases and light framing to make the answer read naturally, but do not introduce new factual claims from your general knowledge. If the facts say "The fee is $50" you write "The fee is $50." You do not add "typically paid by credit card" unless that's in the facts.

Writing style:
- Lead with a clear, direct answer to the question in 1-2 sentences
- Then expand with relevant details, specifics, and context from the facts
- Use bullet points or numbered lists when presenting multiple items (requirements, steps, options, dates)
- Preserve specific dates, credit hours, fees, and deadlines exactly as stated
- Synthesize redundant facts—don't repeat the same point twice
- If facts contain URLs, include them naturally in the answer
- Aim for a complete answer that saves the reader from needing to search further""",
            user_prompt=user_prompt,
            tools=tools,
            tool_choice=tool_choice,
            max_tokens=4000
        )

        if response:
            try:
                data = json.loads(response)

                entry = {
                    "id": str(label),
                    "questions": data['question'],
                    "answer": data['synthesized_answer'],
                    "source_facts": linked_facts,
                    "verified": False
                }
                knowledge_base.append(entry)
            except json.JSONDecodeError:
                print(f"Error parsing JSON.")
        else:
            print(f"No response.")

    # Save output
    os.makedirs(os.path.dirname(output_filename), exist_ok=True)

    with open(output_filename, 'w', encoding='utf-8') as f:
        json.dump(knowledge_base, f, indent=2)

    print(f"\nSuccess! Knowledge Base built: {output_filename}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate FAQ from fact clusters.")
    parser.add_argument("--test", type=int, help="Run on a random subset of N clusters for testing.")
    args = parser.parse_args()

    generate_faq(test_limit=args.test)
