import json
import os
import argparse
import openai_helper

# CONFIGURATION
INPUT_JSON = "data/faq_categorized.json"
OUTPUT_JSON = "data/faq_categorized.json"

# ---------------------------------------------------------
# Tool 1: Audit (Hallucination Check)
# ---------------------------------------------------------
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

# ---------------------------------------------------------
# Tool 2: Evaluate (Utility Score)
# ---------------------------------------------------------
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


def process_faq(limit=None):
    if not os.path.exists(INPUT_JSON):
        print(f"Error: {INPUT_JSON} not found.")
        return

    with open(INPUT_JSON, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Process items that miss either audit OR eval
    items_to_process = [
        item for item in data 
        if 'audit_status' not in item or 'utility_score' not in item
    ]
    
    if limit:
        items_to_process = items_to_process[:limit]

    total = len(items_to_process)
    print(f"Processing {total} items for Audit & Evaluation...")

    for i, entry in enumerate(items_to_process):
        entry_id = entry.get('id')
        print(f"[{i+1}/{total}] ID {entry_id}...", end=" ")

        # Prepare Data
        question = entry.get('questions', '')
        if isinstance(question, list): question = question[0]
        answer = entry.get('answer', '')
        
        facts = []
        if 'source_facts' in entry:
            for f in entry['source_facts']:
                facts.append(f.get('fact', ''))
        fact_text = "\n".join([f"- {f}" for f in facts])

        # -----------------------------------------------------
        # STEP 1: AUDIT (Hallucination Check)
        # -----------------------------------------------------
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
                tools=audit_tools,
                tool_choice=audit_tool_choice,
                max_tokens=300,
                temperature=0.0
            )

            if response_audit:
                try:
                    res = json.loads(response_audit)
                    entry['audit_status'] = res['status']
                    entry['audit_reason'] = res['reason']
                    print(f"Audit: {res['status']}", end=" | ")
                except:
                    print("Audit: ERR", end=" | ")
            else:
                print("Audit: API_ERR", end=" | ")
        else:
            print("Audit: SKIP", end=" | ")

        # -----------------------------------------------------
        # STEP 2: EVALUATE (Utility Scoring)
        # -----------------------------------------------------
        if 'utility_score' not in entry:
            eval_system_prompt = """You are a Senior Content Strategist evaluating the utility of FAQ entries.
Score the provided Question/Answer pair on three dimensions using a strict 1-10 scale based on the following detailed rubrics.

--- RUBRIC 1: UNIVERSALITY (REACH) ---
What portion of the total user base / audience is this relevant to?
- 1-2 (Extremely Niche): <1% of the audience. (e.g., specific error code for a legacy product, doctoral candidates in a sub-field).
- 3-4 (Specific Segment): Relevant to a distinct sub-group. (e.g., enterprise clients only, biology majors, users of feature X).
- 5-6 (Broad Segment): Relevant to a large category of users. (e.g., new customers, first-year students, mobile app users).
- 7-8 (Majority): Most users will encounter this. (e.g., payment methods, parking information, basic troubleshooting).
- 9-10 (Universal): Affects nearly everyone. (e.g., "How to create an account", "Refund policy", "Contact us").

--- RUBRIC 2: CRITICALITY (IMPACT) ---
What is the consequence if the user does NOT know this?
- 1-2 (Trivia): No real consequence. "Nice to know" background info.
- 3-4 (Minor): Helpful context, but not essential for success.
- 5-6 (Operational): Necessary for completing specific tasks or avoiding minor friction.
- 7-8 (High Impact): Critical for success. Not knowing this leads to failed transactions, missed deadlines, or significant frustration.
- 9-10 (Severe): Safety risks, legal liability, financial loss, or total inability to use the service/product.
* Note: If the answer provides a direct link to the solution, score based on the value of that destination.*

--- RUBRIC 3: SEARCH DEMAND (SEARCHABILITY) ---
How likely is a user to actively search for this?
- 1-2 (Serendipitous): Users rarely know this exists or wouldn't think to ask. Discovered by browsing.
- 3-4 (Low): Occasional searches. Specific edge cases or deep details.
- 5-6 (Moderate): Standard reference questions. Information looked up during typical usage.
- 7-8 (High): Frequent queries. The "bread and butter" questions that drive traffic.
- 9-10 (Burning): Top 1% of queries. The most common pain points or immediate needs (e.g. "Forgot Password", "Pricing").

Scoring Instructions:
- Be objective and clinical.
- Evaluate based on the content's intrinsic value to the general audience of such a knowledge base."""

            eval_user_prompt = f"""QUESTION: {question}
ANSWER: {answer}

Evaluate the utility."""

            response_eval = openai_helper.openai_llm_request(
                system_prompt=eval_system_prompt,
                user_prompt=eval_user_prompt,
                tools=eval_tools,
                tool_choice=eval_tool_choice,
                max_tokens=300,
                temperature=0.3 # Slight creativity allowed for judgement
            )

            if response_eval:
                try:
                    res = json.loads(response_eval)
                    # Store raw scores
                    entry['score_universality'] = res['universality_score']
                    entry['score_criticality'] = res['criticality_score']
                    entry['score_demand'] = res['search_demand_score']
                    entry['score_reason'] = res['reasoning']
                    
                    # Calculate simple average
                    avg_score = (res['universality_score'] + res['criticality_score'] + res['search_demand_score']) / 3
                    entry['utility_score'] = round(avg_score, 1)
                    
                    print(f"Utility: {entry['utility_score']}/10")
                except:
                    print("Eval: ERR")
            else:
                print("Eval: API_ERR")
        else:
            print("Eval: SKIP")


    # Save results
    os.makedirs(os.path.dirname(OUTPUT_JSON), exist_ok=True)
    with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)

    print(f"\nProcessing complete. Updated {OUTPUT_JSON}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Audit and Evaluate FAQ entries.")
    parser.add_argument("-l", "--limit", type=int, help="Limit number of items to process.")
    args = parser.parse_args()

    process_faq(limit=args.limit)