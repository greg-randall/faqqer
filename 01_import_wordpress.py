import sys
import os
import json
import re
import argparse
from lxml import etree as ET
from urllib.parse import urlparse
from datetime import datetime
from markdownify import markdownify as md

# We assume markdownify is installed.

# ---------------------------------------------------------------------------
# Domain helpers
# ---------------------------------------------------------------------------

def extract_domain(tree):
    """Extract domain from the WordPress XML's <channel><link> element."""
    root = tree.getroot()
    channel = root.find('channel')
    link_el = channel.find('link') if channel is not None else None
    if link_el is not None and link_el.text:
        parsed = urlparse(link_el.text)
        return parsed.netloc or 'unknown'
    return 'unknown'


def extract_domain_from_text(file_path):
    """Fallback: regex on the channel header (first 4 KB) to get the domain."""
    with open(file_path, 'r', encoding='utf-8') as f:
        head = f.read(4096)
    chunk = head.split('<item>')[0]
    m = re.search(r'<link>(https?://[^<]+)</link>', chunk)
    if m:
        return urlparse(m.group(1)).netloc or 'unknown'
    return 'unknown'


# ---------------------------------------------------------------------------
# Run-dir helpers
# ---------------------------------------------------------------------------

def create_run_dir(domain):
    timestamp = datetime.now().strftime('%Y-%m-%d_%H%M%S')
    run_dir = os.path.join('runs', f"{domain}_{timestamp}")
    os.makedirs(run_dir, exist_ok=True)
    return run_dir


def write_run_info(run_dir, domain, xml_file):
    info = {
        'domain': domain,
        'timestamp': datetime.now().isoformat(),
        'xml_file': os.path.abspath(xml_file),
    }
    with open(os.path.join(run_dir, '.run_info.json'), 'w', encoding='utf-8') as f:
        json.dump(info, f, indent=2)


# ---------------------------------------------------------------------------
# XML path (primary)
# ---------------------------------------------------------------------------

def _inner_html(el):
    """Serialize the inner content of an lxml element back to an HTML string."""
    parts = [el.text or '']
    for child in el:
        parts.append(ET.tostring(child, encoding='unicode', method='html'))
    return ''.join(parts)


def _parse_items_xml(file_path):
    """
    Parse items via lxml with recover=True.
    Returns (items, raw_item_count) where raw_item_count is the number of
    <item> tags found in the raw text (used to detect truncation).
    """
    namespaces = {
        'wp':      'http://wordpress.org/export/1.2/',
        'content': 'http://purl.org/rss/1.0/modules/content/',
        'dc':      'http://purl.org/dc/elements/1.1/',
    }

    with open(file_path, 'rb') as f:
        raw = f.read()

    raw_item_count = raw.count(b'<item>')

    parser = ET.XMLParser(recover=True, encoding='utf-8')
    tree = ET.fromstring(raw, parser)
    # fromstring returns root element; wrap in ElementTree for extract_domain
    tree = ET.ElementTree(tree)
    root = tree.getroot()
    channel = root.find('channel')

    items = []
    for item in channel.findall('item'):
        post_type_obj = item.find('wp:post_type', namespaces)
        post_type = post_type_obj.text if post_type_obj is not None else 'unknown'
        status_obj = item.find('wp:status', namespaces)
        status = status_obj.text if status_obj is not None else 'unknown'

        if post_type not in ('page', 'post') or status != 'publish':
            continue

        title_obj = item.find('title')
        title = (title_obj.text or 'Untitled') if title_obj is not None else 'Untitled'

        post_id_obj = item.find('wp:post_id', namespaces)
        post_id = post_id_obj.text if post_id_obj is not None else '0'

        link_obj = item.find('link')
        permalink = link_obj.text if link_obj is not None else ''

        content_obj = item.find('content:encoded', namespaces)
        raw_html = _inner_html(content_obj) if content_obj is not None else ''

        if not raw_html.strip():
            continue

        items.append({
            'title': title,
            'permalink': permalink,
            'post_id': post_id,
            'raw_html': raw_html,
        })

    return items, tree, raw_item_count


# ---------------------------------------------------------------------------
# Text-based fallback
# ---------------------------------------------------------------------------

def _extract_tag(chunk, tag):
    """
    Extract text between <tag>…</tag>, stripping CDATA if present.
    Plain string search so colons in tag names (e.g. content:encoded) work fine.
    """
    start_marker = f'<{tag}>'
    end_marker   = f'</{tag}>'
    start = chunk.find(start_marker)
    if start == -1:
        return ''
    start += len(start_marker)
    end = chunk.find(end_marker, start)
    if end == -1:
        return ''
    content = chunk[start:end].strip()
    if content.startswith('<![CDATA[') and content.endswith(']]>'):
        content = content[9:-3].strip()
    return content


def _parse_items_text(file_path):
    """
    Fallback text-based parser — splits on <item> boundaries, pulls fields
    with plain string search.  Immune to broken HTML in content.
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        text = f.read()

    items = []
    for chunk in text.split('<item>')[1:]:
        end = chunk.find('</item>')
        if end != -1:
            chunk = chunk[:end]

        post_type = _extract_tag(chunk, 'wp:post_type')
        status    = _extract_tag(chunk, 'wp:status')

        if post_type not in ('page', 'post') or status != 'publish':
            continue

        title     = _extract_tag(chunk, 'title') or 'Untitled'
        post_id   = _extract_tag(chunk, 'wp:post_id') or '0'
        permalink = _extract_tag(chunk, 'link')   # <link> precedes <content:encoded>
        raw_html  = _extract_tag(chunk, 'content:encoded')

        if not raw_html.strip():
            continue

        items.append({
            'title':     title,
            'permalink': permalink,
            'post_id':   post_id,
            'raw_html':  raw_html,
        })

    return items


# ---------------------------------------------------------------------------
# Main parse entry point
# ---------------------------------------------------------------------------

def parse_wordpress_xml(file_path, output_dir):
    """
    Parse a WordPress XML export to Markdown files.

    Tries lxml first (preserves structure best).  Falls back to text-based
    splitting if:
      - lxml throws an exception, OR
      - lxml recovers fewer than 80% of the <item> tags found in the raw text
        (indicates the parser bailed early due to malformed HTML content).
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"Created output directory: {output_dir}")

    print(f"Parsing {file_path}...")

    items = None
    tree  = None

    try:
        items, tree, raw_item_count = _parse_items_xml(file_path)
        ratio = len(items) / raw_item_count if raw_item_count else 1
        if ratio < 0.8:
            print(f"  lxml recovered {len(items)} items vs {raw_item_count} in file "
                  f"({ratio:.0%}) — falling back to text-based parser.")
            items = None
    except Exception as e:
        print(f"  lxml parse failed ({e}) — falling back to text-based parser.")

    if items is None:
        items = _parse_items_text(file_path)

    print(f"Found {len(items)} published page/post items.")

    count = 0
    for item in items:
        title     = item['title']
        post_id   = item['post_id']
        permalink = item['permalink']
        raw_html  = item['raw_html']

        markdown_text = md(raw_html, heading_style="ATX")

        if permalink:
            path = urlparse(permalink).path
            clean_path = path.strip('/').replace('/', '_')
            filename = "homepage.md" if not clean_path else f"{clean_path}.md"
        else:
            safe_title = "".join(c for c in title if c.isalpha() or c.isdigit()).lower()
            filename = f"{post_id}_{safe_title}.md"

        with open(os.path.join(output_dir, filename), 'w', encoding='utf-8') as f:
            f.write(f"# {title}\n")
            f.write(f"**Source URL:** {permalink}\n")
            f.write(f"**ID:** {post_id}\n\n")
            f.write(markdown_text)

        count += 1

    print(f"Success! Extracted {count} items to '{output_dir}/'.")
    return tree


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract WordPress XML content to Markdown.")
    parser.add_argument("xml_file", help="Path to the WordPress XML export file.")
    parser.add_argument("--run-dir", dest="run_dir", default=None,
                        help="Resume into an existing run directory instead of creating a new one.")
    args = parser.parse_args()

    input_file = args.xml_file

    if args.run_dir:
        run_dir = args.run_dir
        output_folder = os.path.join(run_dir, "content")
    else:
        try:
            xml_parser = ET.XMLParser(recover=True, encoding='utf-8')
            tree = ET.parse(input_file, xml_parser)
            domain = extract_domain(tree)
        except Exception:
            domain = extract_domain_from_text(input_file)

        run_dir = create_run_dir(domain)
        write_run_info(run_dir, domain, input_file)
        output_folder = os.path.join(run_dir, "content")
        os.environ['FAQQER_RUN_DIR'] = run_dir

    parse_wordpress_xml(input_file, output_folder)
    print(f"FAQQER_RUN_DIR={run_dir}")
