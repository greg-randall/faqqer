import pandas as pd
import json
import os
import random
import argparse
import openai_helper

# Configuration
INPUT_CSV = "data/fact_clusters.csv" 
OUTPUT_JSON = "data/faq_raw.json"

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
                    "synthesized_answer": {
                        "type": "string",
                        "description": "A concise answer using ONLY information from the provided facts. Do not add details, context, or caveats from outside knowledge—even if accurate. If a fact says 'X is required,' write that. Do not add 'typically' or 'usually' or explain why. Lead with the key information. 2-4 sentences max. Include URLs from facts when present."
                    },
                    "question": {
                        "type": "string",
                        "description": "A single, natural question a user might type into Google. Write it like a real search query—can be casual ('program application fee') or a full sentence ('How much does it cost to apply?'). Never use 'What is the policy on...' or 'Can you explain...'."
                    },
                },
                "required": ["synthesized_answer", "question"]
            }
        }
    }
]

tool_choice = {"type": "function", "function": {"name": "synthesize_faq"}}

def generate_faq(test_limit=None):
    if not os.path.exists(INPUT_CSV):
        print(f"Error: Could not find {INPUT_CSV}")
        return

    df = pd.read_csv(INPUT_CSV)
    
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

    knowledge_base = []

    print(f"Synthesizing {len(selected_clusters)} FAQ entries...")

    total_clusters = len(selected_clusters)
    for i, label in enumerate(selected_clusters):
        cluster_data = df[df[group_col] == label]
        
        # 1. Build the Linked Data (Fact + Source)
        # We create a list of dictionaries: [{'fact': '...', 'source': 'file.md'}, ...]
        # This keeps the provenance tight.
        linked_facts = cluster_data[['fact', 'source']].to_dict('records')
        
        # 2. Extract just the text for the LLM Prompt
        # We assume the LLM doesn't need the filenames to write the answer, just the facts.
        prompt_facts_text = [item['fact'] for item in linked_facts]
        
        # Safety Truncation for Prompt (save tokens)
        if len(prompt_facts_text) > 40:
            prompt_facts_text = prompt_facts_text[:40] 

        print(f"[{i+1}/{total_clusters}] Processing Topic {label}...")
        
        user_prompt = "FACTS:\n" + "\n".join([f"- {f}" for f in prompt_facts_text])
        
        #
        response = openai_helper.openai_llm_request(
            system_prompt="""You are a web editor for the organization's website. Your job is to create FAQ entries that help prospective and current users find answers quickly.

CRITICAL: Your answers must contain ONLY information present in the provided facts. Do not add context, caveats, recommendations, or details from your general knowledge—even if you're confident they're true. If the facts say "The fee is $50" you write "The fee is $50." You do not add "typically paid by credit card" or "which is non-refundable" unless that's explicitly stated in the facts.

If the facts are insufficient to write a useful answer, assign a low quality_score. Do not fill gaps with assumed information.

Writing style:
- Helpful and direct, not legalistic or bureaucratic
- Lead with the answer, not background context
- Preserve specific dates, credit hours, fees, and deadlines exactly as stated
- If facts contain URLs, include them naturally in the answer
- Synthesize redundant facts—don't repeat the same point twice""",
            user_prompt=user_prompt,
            tools=tools,
            tool_choice=tool_choice,
            max_tokens=2000 
        )

        if response:
            try:
                data = json.loads(response)
                
                entry = {
                    "id": str(label),
                    "questions": data['question'],
                    "answer": data['synthesized_answer'],
                    # The linked list goes here:
                    "source_facts": linked_facts,
                    "verified": False 
                }
                knowledge_base.append(entry)
                #print(f"Success! ('{str(label)}')")
            except json.JSONDecodeError:
                print(f"Error parsing JSON.")
        else:
            print(f"No response.")

    # Save output
    output_filename = OUTPUT_JSON
    if test_limit:
        output_filename = "data/faq_TEST.json"
        
    os.makedirs(os.path.dirname(output_filename), exist_ok=True)
        
    with open(output_filename, 'w', encoding='utf-8') as f:
        json.dump(knowledge_base, f, indent=2)
    
    print(f"\nSuccess! Knowledge Base built: {output_filename}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate FAQ from fact clusters.")
    parser.add_argument("--test", type=int, help="Run on a random subset of N clusters for testing.")
    args = parser.parse_args()
    
    generate_faq(test_limit=args.test)