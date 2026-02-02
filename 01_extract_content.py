import sys
import os
import xml.etree.ElementTree as ET
from urllib.parse import urlparse
from markdownify import markdownify as md

# We assume markdownify is installed.

def parse_wordpress_xml(file_path, output_dir):
    """
    Reads a WordPress XML export and saves pages as Markdown files.
    Uses the URL structure to create unique filenames.
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

        title = item.find('title').text
        if not title:
            title = "Untitled"
            
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

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python extract_content_v2.py <path_to_xml_file>")
        sys.exit(1)

    input_file = sys.argv[1]
    output_folder = "content"

    parse_wordpress_xml(input_file, output_folder)