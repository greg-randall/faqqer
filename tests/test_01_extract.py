import os
import pytest
from tests.conftest import import_step, fixture_path


@pytest.fixture
def extract_module():
    return import_step("01_extract_content")


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
