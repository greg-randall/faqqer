import sys
import os
import json
import argparse
import xml.etree.ElementTree as ET
from urllib.parse import urlparse
from datetime import datetime
from markdownify import markdownify as md

# We assume markdownify is installed.

def extract_domain(tree):
    """Extract domain from the WordPress XML's <channel><link> element."""
    root = tree.getroot()
    channel = root.find('channel')
    link_el = channel.find('link') if channel is not None else None
    if link_el is not None and link_el.text:
        parsed = urlparse(link_el.text)
        return parsed.netloc or 'unknown'
    return 'unknown'


def create_run_dir(domain):
    """Create a timestamped run directory under runs/."""
    timestamp = datetime.now().strftime('%Y-%m-%d_%H%M%S')
    run_name = f"{domain}_{timestamp}"
    run_dir = os.path.join('runs', run_name)
    os.makedirs(run_dir, exist_ok=True)
    return run_dir


def write_run_info(run_dir, domain, xml_file):
    """Write .run_info.json with metadata about this run."""
    info = {
        'domain': domain,
        'timestamp': datetime.now().isoformat(),
        'xml_file': os.path.abspath(xml_file),
    }
    info_path = os.path.join(run_dir, '.run_info.json')
    with open(info_path, 'w', encoding='utf-8') as f:
        json.dump(info, f, indent=2)


def parse_wordpress_xml(file_path, output_dir):
    """
    Reads a WordPress XML export and saves pages as Markdown files.
    Uses the URL structure to create unique filenames.
    Returns the parsed ElementTree for reuse.
    """

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"Created output directory: {output_dir}")

    print(f"Parsing {file_path}...")

    namespaces = {
        'wp': 'http://wordpress.org/export/1.2/',
        'content': 'http://purl.org/rss/1.0/modules/content/',
        'dc': 'http://purl.org/dc/elements/1.1/'
    }

    tree = ET.parse(file_path)
    root = tree.getroot()
    channel = root.find('channel')

    count = 0

    for item in channel.findall('item'):

        post_type_obj = item.find('wp:post_type', namespaces)
        post_type = post_type_obj.text if post_type_obj is not None else 'unknown'

        status_obj = item.find('wp:status', namespaces)
        status = status_obj.text if status_obj is not None else 'unknown'

        if post_type not in ['page', 'post']:
            continue
        if status != 'publish':
            continue

        title_obj = item.find('title')
        title = title_obj.text if title_obj is not None and title_obj.text else "Untitled"

        # Grab the Post ID as a fallback unique identifier
        post_id_obj = item.find('wp:post_id', namespaces)
        post_id = post_id_obj.text if post_id_obj is not None else '0'

        # Grab the permalink
        link_obj = item.find('link')
        permalink = link_obj.text if link_obj is not None else ''

        content_obj = item.find('content:encoded', namespaces)
        raw_html = content_obj.text if content_obj is not None else ''

        if not raw_html:
            continue

        markdown_text = md(raw_html, heading_style="ATX")

        # GENERATE FILENAME FROM URL
        if permalink:
            # Parse the URL to get the path (e.g., /admissions/apply/)
            parsed = urlparse(permalink)
            path = parsed.path

            # Remove leading/trailing slashes and replace remaining slashes with underscores
            clean_path = path.strip('/').replace('/', '_')

            # Handle the homepage (empty path)
            if not clean_path:
                filename = "homepage.md"
            else:
                filename = f"{clean_path}.md"
        else:
            # Fallback if no link found: Use ID + Title
            safe_title = "".join([c for c in title if c.isalpha() or c.isdigit()]).lower()
            filename = f"{post_id}_{safe_title}.md"

        full_path = os.path.join(output_dir, filename)

        with open(full_path, 'w', encoding='utf-8') as f:
            # Add metadata to the top of the file for reference
            f.write(f"# {title}\n")
            f.write(f"**Source URL:** {permalink}\n")
            f.write(f"**ID:** {post_id}\n\n")
            f.write(markdown_text)

        count += 1

    print(f"Success! Extracted {count} items to '{output_dir}/'.")
    return tree

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract WordPress XML content to Markdown.")
    parser.add_argument("xml_file", help="Path to the WordPress XML export file.")
    parser.add_argument("--run-dir", dest="run_dir", default=None,
                        help="Resume into an existing run directory instead of creating a new one.")
    args = parser.parse_args()

    input_file = args.xml_file

    if args.run_dir:
        # Resume into existing run dir
        run_dir = args.run_dir
        output_folder = os.path.join(run_dir, "content")
    else:
        # Parse XML to extract domain, then create run dir
        tree = ET.parse(input_file)
        domain = extract_domain(tree)
        run_dir = create_run_dir(domain)
        write_run_info(run_dir, domain, input_file)
        output_folder = os.path.join(run_dir, "content")
        # Set env var so downstream code in this process can use it
        os.environ['FAQQER_RUN_DIR'] = run_dir

    parse_wordpress_xml(input_file, output_folder)
    print(f"FAQQER_RUN_DIR={run_dir}")
