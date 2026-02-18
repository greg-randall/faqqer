import os
import json
import xml.etree.ElementTree as ET
import pytest
from tests.conftest import import_step, fixture_path


@pytest.fixture
def extract_module():
    return import_step("01_import_wordpress")


class TestExtractContent:
    def test_extracts_published_items(self, extract_module, tmp_path):
        """Should extract published pages and posts."""
        xml_path = fixture_path("sample_export.xml")
        output_dir = str(tmp_path / "content")
        extract_module.parse_wordpress_xml(xml_path, output_dir)

        files = os.listdir(output_dir)
        assert len(files) == 2  # page + post, not draft

    def test_skips_draft(self, extract_module, tmp_path):
        """Draft items should not be extracted."""
        xml_path = fixture_path("sample_export.xml")
        output_dir = str(tmp_path / "content")
        extract_module.parse_wordpress_xml(xml_path, output_dir)

        files = os.listdir(output_dir)
        filenames = [f.lower() for f in files]
        assert not any("draft" in fn for fn in filenames)

    def test_filename_from_url(self, extract_module, tmp_path):
        """Filenames should be derived from URL path."""
        xml_path = fixture_path("sample_export.xml")
        output_dir = str(tmp_path / "content")
        extract_module.parse_wordpress_xml(xml_path, output_dir)

        files = os.listdir(output_dir)
        assert "about.md" in files
        assert "blog_post-one.md" in files

    def test_content_has_metadata(self, extract_module, tmp_path):
        """Extracted files should contain title and source URL headers."""
        xml_path = fixture_path("sample_export.xml")
        output_dir = str(tmp_path / "content")
        extract_module.parse_wordpress_xml(xml_path, output_dir)

        about_path = os.path.join(output_dir, "about.md")
        with open(about_path, 'r', encoding='utf-8') as f:
            content = f.read()

        assert "# About Us" in content
        assert "**Source URL:** https://example.com/about/" in content

    def test_empty_content_skipped(self, extract_module, tmp_path):
        """Items with empty content should be skipped."""
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"
  xmlns:wp="http://wordpress.org/export/1.2/"
  xmlns:content="http://purl.org/rss/1.0/modules/content/"
  xmlns:dc="http://purl.org/dc/elements/1.1/">
<channel>
  <item>
    <title>Empty Page</title>
    <link>https://example.com/empty/</link>
    <wp:post_id>88</wp:post_id>
    <wp:post_type>page</wp:post_type>
    <wp:status>publish</wp:status>
    <content:encoded><![CDATA[]]></content:encoded>
  </item>
</channel>
</rss>"""
        xml_path = str(tmp_path / "empty.xml")
        with open(xml_path, 'w') as f:
            f.write(xml_content)

        output_dir = str(tmp_path / "content")
        extract_module.parse_wordpress_xml(xml_path, output_dir)

        files = os.listdir(output_dir) if os.path.exists(output_dir) else []
        assert len(files) == 0

    def test_homepage_url_filename(self, extract_module, tmp_path):
        """Homepage URL (empty path) should produce homepage.md filename."""
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"
  xmlns:wp="http://wordpress.org/export/1.2/"
  xmlns:content="http://purl.org/rss/1.0/modules/content/"
  xmlns:dc="http://purl.org/dc/elements/1.1/">
<channel>
  <item>
    <title>Home</title>
    <link>https://example.com/</link>
    <wp:post_id>1</wp:post_id>
    <wp:post_type>page</wp:post_type>
    <wp:status>publish</wp:status>
    <content:encoded><![CDATA[<p>Welcome home.</p>]]></content:encoded>
  </item>
</channel>
</rss>"""
        xml_path = str(tmp_path / "home.xml")
        with open(xml_path, 'w') as f:
            f.write(xml_content)

        output_dir = str(tmp_path / "content")
        extract_module.parse_wordpress_xml(xml_path, output_dir)

        files = os.listdir(output_dir)
        assert "homepage.md" in files

    def test_no_link_fallback_filename(self, extract_module, tmp_path):
        """Items with no <link> should use post ID + title as filename."""
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"
  xmlns:wp="http://wordpress.org/export/1.2/"
  xmlns:content="http://purl.org/rss/1.0/modules/content/"
  xmlns:dc="http://purl.org/dc/elements/1.1/">
<channel>
  <item>
    <title>No Link Page</title>
    <wp:post_id>77</wp:post_id>
    <wp:post_type>page</wp:post_type>
    <wp:status>publish</wp:status>
    <content:encoded><![CDATA[<p>Page without a link element.</p>]]></content:encoded>
  </item>
</channel>
</rss>"""
        xml_path = str(tmp_path / "nolink.xml")
        with open(xml_path, 'w') as f:
            f.write(xml_content)

        output_dir = str(tmp_path / "content")
        extract_module.parse_wordpress_xml(xml_path, output_dir)

        files = os.listdir(output_dir)
        assert len(files) == 1
        # Should contain the post ID
        assert "77" in files[0]

    def test_missing_title_defaults_to_untitled(self, extract_module, tmp_path):
        """Items with missing <title> element should default to 'Untitled'."""
        import xml.etree.ElementTree as ET

        # Create XML with missing title element
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"
  xmlns:wp="http://wordpress.org/export/1.2/"
  xmlns:content="http://purl.org/rss/1.0/modules/content/"
  xmlns:dc="http://purl.org/dc/elements/1.1/">
<channel>
  <item>
    <link>https://example.com/no-title/</link>
    <wp:post_id>99</wp:post_id>
    <wp:post_type>page</wp:post_type>
    <wp:status>publish</wp:status>
    <content:encoded><![CDATA[<p>Content without a title tag.</p>]]></content:encoded>
  </item>
</channel>
</rss>"""
        xml_path = str(tmp_path / "notitle.xml")
        with open(xml_path, 'w') as f:
            f.write(xml_content)

        output_dir = str(tmp_path / "content")
        extract_module.parse_wordpress_xml(xml_path, output_dir)

        files = os.listdir(output_dir)
        assert len(files) == 1

        with open(os.path.join(output_dir, files[0]), 'r', encoding='utf-8') as f:
            content = f.read()
        assert "# Untitled" in content


class TestRunDirCreation:
    def _make_xml_with_link(self, tmp_path, link_url):
        """Helper: create a minimal XML with a channel-level <link>."""
        xml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"
  xmlns:wp="http://wordpress.org/export/1.2/"
  xmlns:content="http://purl.org/rss/1.0/modules/content/"
  xmlns:dc="http://purl.org/dc/elements/1.1/">
<channel>
  <link>{link_url}</link>
</channel>
</rss>"""
        xml_path = str(tmp_path / "test.xml")
        with open(xml_path, 'w') as f:
            f.write(xml_content)
        return xml_path

    def test_extract_domain(self, extract_module, tmp_path):
        """Should extract domain from channel <link> element."""
        xml_path = self._make_xml_with_link(tmp_path, "https://example.com/blog")
        tree = ET.parse(xml_path)
        assert extract_module.extract_domain(tree) == "example.com"

    def test_extract_domain_no_link(self, extract_module, tmp_path):
        """Should return 'unknown' when no <link> in channel."""
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel></channel></rss>"""
        xml_path = str(tmp_path / "nolink.xml")
        with open(xml_path, 'w') as f:
            f.write(xml_content)
        tree = ET.parse(xml_path)
        assert extract_module.extract_domain(tree) == "unknown"

    def test_create_run_dir(self, extract_module, tmp_path, monkeypatch):
        """Should create runs/<domain>_<timestamp>/ directory."""
        monkeypatch.chdir(tmp_path)
        run_dir = extract_module.create_run_dir("example.com")
        assert os.path.isdir(run_dir)
        assert run_dir.startswith("runs/example.com_")

    def test_write_run_info(self, extract_module, tmp_path):
        """Should write .run_info.json with domain, timestamp, and xml_file."""
        run_dir = str(tmp_path / "test_run")
        os.makedirs(run_dir)
        extract_module.write_run_info(run_dir, "example.com", "test.xml")

        info_path = os.path.join(run_dir, ".run_info.json")
        assert os.path.exists(info_path)

        with open(info_path) as f:
            info = json.load(f)

        assert info["domain"] == "example.com"
        assert "timestamp" in info
        assert "xml_file" in info
