import os
import json
import argparse
import openai_helper
import config
import prompts

# Configuration
INPUT_DIR = os.path.join(config.get_run_dir(), "content")
OUTPUT_DIR = os.path.join(config.get_run_dir(), "content_processed")


def _strip_metadata_header(content):
    """Strip the metadata header (title, Source URL, ID) added by step 01.

    The format is always:
        # Title
        **Source URL:** ...
        **ID:** ...

        <actual content>

    We find the first blank line after these headers and return everything after it.
    """
    lines = content.split('\n')
    for i, line in enumerate(lines):
        # Look for first blank line (the separator after metadata)
        if i > 0 and line.strip() == '':
            # Check that we've passed at least the title line
            remaining = '\n'.join(lines[i+1:]).strip()
            if remaining:
                return remaining
    # If no blank line found or no content after it, return original
    return content


def process_files(limit=None):
    # Ensure output directory exists
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
        print(f"Created directory: {OUTPUT_DIR}")

    # Get list of markdown files
    files = [f for f in os.listdir(INPUT_DIR) if f.endswith(".md")]

    # Sort files to ensure deterministic order (useful for debugging)
    files.sort()

    # Apply limit if provided (positive integer only)
    if limit is not None and limit > 0:
        files = files[:limit]
        print(f"Debug Mode: Processing only the first {limit} files.")

    total_files = len(files)
    print(f"Queued {total_files} files to process.")

    for index, filename in enumerate(files):
        input_path = os.path.join(INPUT_DIR, filename)
        output_filename = filename.replace(".md", ".json")
        output_path = os.path.join(OUTPUT_DIR, output_filename)

        # Skip if already exists (resume capability)
        if os.path.exists(output_path):
            print(f"[{index+1}/{total_files}] Skipping {filename} (already processed)")
            continue

        print(f"[{index+1}/{total_files}] Processing {filename}...")

        # Read the Markdown content
        with open(input_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Strip metadata header before sending to LLM
        clean_content = _strip_metadata_header(content)

        # Send to OpenAI
        response_json_str = openai_helper.openai_llm_request(
            system_prompt=prompts.get("process_content.system"),
            user_prompt=clean_content,
            tools=prompts.get_tools("process_content"),
            tool_choice=prompts.get_tool_choice("process_content"),
            max_tokens=16000
        )

        if response_json_str:
            try:
                # The helper returns the arguments as a JSON string
                data = json.loads(response_json_str)

                # Filter empty-string facts
                if 'facts' in data:
                    original_count = len(data['facts'])
                    data['facts'] = [f for f in data['facts'] if f and f.strip()]
                    filtered_count = original_count - len(data['facts'])
                    if filtered_count > 0:
                        print(f"  Filtered {filtered_count} empty facts.")
                    if len(data['facts']) == 0:
                        print(f"  Warning: Zero facts extracted for {filename}")

                # Add metadata about the source file
                data['source_file'] = filename

                # Save the result
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2)

            except json.JSONDecodeError:
                print(f"Error: Failed to parse JSON response for {filename}")
                # Save the raw error output for debugging
                with open(output_path.replace(".json", "_error.txt"), 'w', encoding='utf-8') as f:
                    f.write(response_json_str)
        else:
            print(f"Error: No response received for {filename}")

    print("\nProcessing complete.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract atomic facts from markdown files.")
    parser.add_argument(
        "-l", "--limit",
        type=int,
        help="Limit the number of files to process (useful for debugging)."
    )

    args = parser.parse_args()

    process_files(limit=args.limit)
