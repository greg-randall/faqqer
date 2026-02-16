import json
import html
import os

# CONFIGURATION
INPUT_JSON = "data/faq_categorized.json"
OUTPUT_HTML = "data/faq_final.html"

PARAGRAPH_TEMPLATE = """<!-- wp:paragraph {{"placeholder":"Type / to add a hidden block"}} -->
<p>{text}</p>
<!-- /wp:paragraph -->"""


def _build_faq_block(question, answer):
    """Build a wp:details block with one wp:paragraph per paragraph in the answer."""
    escaped_question = html.escape(question)

    # Split on newlines, escape each paragraph, drop empties
    paragraphs = [html.escape(p.strip()) for p in answer.split('\n') if p.strip()]
    if not paragraphs:
        paragraphs = [html.escape(answer)]

    inner = "\n".join(PARAGRAPH_TEMPLATE.format(text=p) for p in paragraphs)

    return f"""<!-- wp:details -->
<details class="wp-block-details"><summary>{escaped_question}</summary>
{inner}
</details>
<!-- /wp:details -->
"""

SPACER_BLOCK = """<!-- wp:spacer {{"height":"40px"}} -->
<div style="height:40px" aria-hidden="true" class="wp-block-spacer"></div>
<!-- /wp:spacer -->
"""

def main():
    # 1. Load Data
    if not os.path.exists(INPUT_JSON):
        print(f"Error: Could not find {INPUT_JSON}")
        return

    with open(INPUT_JSON, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # 2. Filter & Group Approved Items
    grouped_data = {}
    approved_count = 0

    for item in data:
        if item.get('status') == 'approved':
            category = item.get('category', 'General')
            if category not in grouped_data:
                grouped_data[category] = []
            grouped_data[category].append(item)
            approved_count += 1

    if approved_count == 0:
        print("WARNING: No 'approved' items found! Please use the reviewer tool first.")
        return

    print(f"Generating WordPress block HTML for {approved_count} approved items...")

    # 3. Build HTML
    wp_html = []

    sorted_categories = sorted(grouped_data.keys())
    last_category = sorted_categories[-1] if sorted_categories else None

    for category in sorted_categories:
        # Category Heading
        cat_esc = html.escape(category)
        wp_html.append('<!-- wp:heading {"level":2} -->')
        wp_html.append(f'<h2 class="wp-block-heading">{cat_esc}</h2>')
        wp_html.append('<!-- /wp:heading -->')
        wp_html.append('')  # empty line for readability

        # Sort items within this category by utility_score (descending)
        # Default to 0 if utility_score is missing
        items = sorted(
            grouped_data[category],
            key=lambda x: x.get('utility_score', 0),
            reverse=True
        )

        # FAQ Items
        for item in items:
            q_raw = item.get('questions', '')
            question = q_raw[0] if isinstance(q_raw, list) else q_raw
            answer = item.get('answer', '')

            wp_html.append(_build_faq_block(question, answer))

        # Spacer between categories (skip after the last one)
        if category != last_category:
            wp_html.append(SPACER_BLOCK)
            wp_html.append('')

    # Join everything with newlines
    final_html = '\n'.join(wp_html).strip()

    # 4. Save
    os.makedirs(os.path.dirname(OUTPUT_HTML), exist_ok=True)
    with open(OUTPUT_HTML, 'w', encoding='utf-8') as f:
        f.write(final_html)

    print(f"Success! WordPress-ready HTML generated at: {OUTPUT_HTML}")
    print("Copy the entire contents and paste into the WordPress Code Editor (Gutenberg).")

if __name__ == "__main__":
    main()
