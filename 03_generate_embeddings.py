import os
import json
import openai_helper
import config

# Configuration
INPUT_DIR = os.path.join(config.get_run_dir(), "content_processed")
OUTPUT_DIR = os.path.join(config.get_run_dir(), "content_embedded")

def process_embeddings():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
        print(f"Created directory: {OUTPUT_DIR}")

    # Get list of processed JSON files
    files = [f for f in os.listdir(INPUT_DIR) if f.endswith(".json")]
    total_files = len(files)
    
    print(f"Found {total_files} files to check for embeddings.")

    for index, filename in enumerate(files):
        input_path = os.path.join(INPUT_DIR, filename)
        output_path = os.path.join(OUTPUT_DIR, filename)

        # 1. CACHE CHECK: If file exists in output, skip it.
        if os.path.exists(output_path):
            # Optional: Check if the source file is newer than the cache file
            # content_mtime = os.path.getmtime(input_path)
            # cache_mtime = os.path.getmtime(output_path)
            # if cache_mtime > content_mtime:
            #     print(f"[{index+1}/{total_files}] Skipping {filename} (Cached)")
            #     continue
            
            # Simple existence check
            print(f"[{index+1}/{total_files}] Skipping {filename} (Already embedded)")
            continue

        print(f"[{index+1}/{total_files}] Embedding facts in {filename}...")

        # 2. Load Facts
        with open(input_path, 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                print(f"  Error: Could not parse {filename}")
                continue

        if 'facts' not in data or not data['facts']:
            print(f"  Warning: No facts found in {filename}")
            # Save it anyway to mark as processed
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            continue

        # 3. Get Embeddings for all facts in this file
        # We assume data['facts'] is a list of strings
        facts_text = data['facts']
        
        # Call OpenAI (The helper handles batching)
        embeddings = openai_helper.get_embeddings(facts_text)

        if not embeddings:
            print(f"  Error: API failed for {filename}")
            continue

        if len(embeddings) != len(facts_text):
            print(f"  Error: Mismatch! Sent {len(facts_text)} facts, got {len(embeddings)} vectors.")
            continue

        # 4. Structure the Output
        # We transform the list of strings into a list of objects with embeddings
        enriched_facts = []
        for i, text in enumerate(facts_text):
            enriched_facts.append({
                "text": text,
                "vector": embeddings[i]
            })

        # Update the data object
        data['facts_with_embeddings'] = enriched_facts
        # We keep the original 'facts' list for human readability if desired, 
        # or we could remove it to save space. Let's keep it for now.

        # 5. Save to Cache
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
            
    print("\nEmbedding process complete.")

if __name__ == "__main__":
    process_embeddings()