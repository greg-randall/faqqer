import json
import openai_helper

INPUT_FILE = "data/faq_raw.json"
OUTPUT_FILE = "data/faq_categorized.json"

# ---------------------------------------------------------
# STAGE 1: DYNAMIC DISCOVERY (The "HDBSCAN" replacement)
# ---------------------------------------------------------
def discover_natural_categories(data):
    print("--- STAGE 1: Discovering Natural Categories ---")
    
    # 1. Prepare the Data
    # We grab just the questions. If you have >500 items, we might random sample 
    # 200 of them to get the "gist" without burning tokens.
    questions_list = [entry.get('questions', '') for entry in data]
    
    # Handle case where 'questions' is a list
    clean_questions = []
    for q in questions_list:
        if isinstance(q, list): clean_questions.append(q[0])
        else: clean_questions.append(q)

    # Convert to a simple newline-separated string for the prompt
    questions_text = "\n".join(clean_questions)

    # 2. Define the Tool
    # notice we do NOT specify a number of items in the description
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

    # 3. The "Clustering" Prompt
    # We explicitly tell it to act like a clustering algorithm.
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
        except json.JSONDecodeError:
            print("Error parsing Stage 1 response.")
            return []
    else:
        print("Stage 1 failed.")
        return []

# ---------------------------------------------------------
# STAGE 2: STRICT ASSIGNMENT
# ---------------------------------------------------------
def assign_category(question_text, taxonomy):
    # We dynamically build the tool definition using the taxonomy we just discovered.
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
                            "enum": taxonomy, # STRICT CONSTRAINT
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
        except:
            return "Uncategorized"
    return "Uncategorized"

# ---------------------------------------------------------
# MAIN
# ---------------------------------------------------------
def main():
    try:
        with open(INPUT_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: {INPUT_FILE} not found.")
        return

    # 1. Discover
    taxonomy = discover_natural_categories(data)
    
    if not taxonomy:
        print("Could not generate taxonomy. Exiting.")
        return

    # 2. Assign
    print(f"\n--- STAGE 2: Mapping {len(data)} items to {len(taxonomy)} categories ---")
    
    for i, entry in enumerate(data):
        # Extract question text safely
        q_raw = entry.get('questions', '')
        q_text = q_raw[0] if isinstance(q_raw, list) else q_raw
        
        # Classify
        cat = assign_category(q_text, taxonomy)
        entry['category'] = cat
        
        # Simple progress bar
        if i % 10 == 0:
            print(f"Processed {i}/{len(data)}...")

    # 3. Save
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)

    print(f"\nSuccess! Saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
