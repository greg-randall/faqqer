import json
import os
import re

# CONFIGURATION
INPUT_JSON = "data/faq_categorized.json"
# We can overwrite the input or create a new "production ready" file. 
# Let's overwrite or create a new 'ready' file to be safe.
OUTPUT_JSON = "data/faq_categorized.json" 
CONTENT_DIR = "content" # Where your .md files live

def extract_url_from_md(filename):
    """
    Reads the first 20 lines of a markdown file to find the 
    **Source URL:** metadata.
    """
    filepath = os.path.join(CONTENT_DIR, filename)
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for _ in range(20): # Only scan header
                line = f.readline()
                if not line: break
                
                # Regex looks for "**Source URL:** <something>"
                match = re.search(r'\*\*Source URL:\*\* (.*)', line)
                if match:
                    return match.group(1).strip()
    except Exception as e:
        print(f"Warning: Could not read {filename}: {e}")
    
    return None

def main():
    if not os.path.exists(INPUT_JSON):
        print(f"Error: Could not find {INPUT_JSON}")
        return

    print(f"Reading {INPUT_JSON}...")
    with open(INPUT_JSON, 'r', encoding='utf-8') as f:
        data = json.load(f)

    print(f"Processing {len(data)} items...")
    
    # Cache to avoid re-opening the same file 50 times
    url_cache = {}
    stats = {"found": 0, "missing": 0}

    for entry in data:
        if 'source_facts' in entry:
            for fact in entry['source_facts']:
                source_file = fact.get('source')
                if not source_file: continue

                # Check cache first
                if source_file in url_cache:
                    live_url = url_cache[source_file]
                else:
                    live_url = extract_url_from_md(source_file)
                    url_cache[source_file] = live_url

                # Bake it into the JSON
                if live_url:
                    fact['live_url'] = live_url
                    stats["found"] += 1
                else:
                    stats["missing"] += 1
                    # Optional: Mark as dead link?
                    fact['live_url'] = None

    # Save
    os.makedirs(os.path.dirname(OUTPUT_JSON), exist_ok=True)
    with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)

    print(f"\nSuccess! Processed {len(data)} items.")
    print(f"URLs Found: {stats['found']}")
    print(f"URLs Missing: {stats['missing']}")
    print(f"Saved to: {OUTPUT_JSON}")

if __name__ == "__main__":
    main()