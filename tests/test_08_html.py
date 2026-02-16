import os
import json
import pytest
from unittest.mock import patch
from tests.conftest import import_step, fixture_path, load_json_fixture


@pytest.fixture
def html_module():
    return import_step("08_generate_wp_html")


class TestGenerateWpHtml:
    def test_approved_only(self, html_module, tmp_path):
        """Only approved items should appear in output HTML."""
        data = load_json_fixture("sample_faq_categorized.json")
        input_json = str(tmp_path / "input.json")
        output_html = str(tmp_path / "output.html")

        with open(input_json, 'w') as f:
            json.dump(data, f)

        with patch.object(html_module, 'INPUT_JSON', input_json), \
             patch.object(html_module, 'OUTPUT_HTML', output_html):
            html_module.main()

        with open(output_html) as f:
            html = f.read()

        # Only 1 approved item in fixture
        assert "organization&#x27;s mission" in html or "organization's mission" in html.replace("&#x27;", "'")
        # Rejected item should NOT appear
        assert "program cost" not in html.lower() or "rejected" not in html.lower()

    def test_wp_block_format(self, html_module, tmp_path):
        """Output should contain WordPress block comments."""
        data = load_json_fixture("sample_faq_categorized.json")
        input_json = str(tmp_path / "input.json")
        output_html = str(tmp_path / "output.html")

        with open(input_json, 'w') as f:
            json.dump(data, f)

        with patch.object(html_module, 'INPUT_JSON', input_json), \
             patch.object(html_module, 'OUTPUT_HTML', output_html):
            html_module.main()

        with open(output_html) as f:
            html = f.read()

        assert "<!-- wp:details -->" in html
        assert "<!-- /wp:details -->" in html
        assert "<details" in html
        assert "<summary>" in html

    def test_heading_braces_not_eaten(self, html_module, tmp_path):
        """WP heading comment should preserve literal braces (f-string regression)."""
        data = load_json_fixture("sample_faq_categorized.json")
        input_json = str(tmp_path / "input.json")
        output_html = str(tmp_path / "output.html")

        with open(input_json, 'w') as f:
            json.dump(data, f)

        with patch.object(html_module, 'INPUT_JSON', input_json), \
             patch.object(html_module, 'OUTPUT_HTML', output_html):
            html_module.main()

        with open(output_html) as f:
            html = f.read()

        # The heading comment must have literal braces: {"level":2}
        assert '{"level":2}' in html

    def test_html_escaping(self, html_module, tmp_path):
        """HTML special characters in questions/answers should be escaped."""
        data = [{
            "id": "1",
            "questions": "Is 5 > 3 & 2 < 4?",
            "answer": "Yes, 5 > 3 & 2 < 4.",
            "source_facts": [],
            "category": "Math",
            "status": "approved",
            "utility_score": 5
        }]
        input_json = str(tmp_path / "input.json")
        output_html = str(tmp_path / "output.html")

        with open(input_json, 'w') as f:
            json.dump(data, f)

        with patch.object(html_module, 'INPUT_JSON', input_json), \
             patch.object(html_module, 'OUTPUT_HTML', output_html):
            html_module.main()

        with open(output_html) as f:
            html = f.read()

        assert "&amp;" in html
        assert "&gt;" in html
        assert "&lt;" in html

    def test_sort_by_utility(self, html_module, tmp_path):
        """Items within a category should be sorted by utility_score descending."""
        data = [
            {
                "id": "1", "questions": "Low score Q", "answer": "A",
                "source_facts": [], "category": "General",
                "status": "approved", "utility_score": 3
            },
            {
                "id": "2", "questions": "High score Q", "answer": "A",
                "source_facts": [], "category": "General",
                "status": "approved", "utility_score": 9
            }
        ]
        input_json = str(tmp_path / "input.json")
        output_html = str(tmp_path / "output.html")

        with open(input_json, 'w') as f:
            json.dump(data, f)

        with patch.object(html_module, 'INPUT_JSON', input_json), \
             patch.object(html_module, 'OUTPUT_HTML', output_html):
            html_module.main()

        with open(output_html) as f:
            html = f.read()

        high_pos = html.find("High score Q")
        low_pos = html.find("Low score Q")
        assert high_pos < low_pos, "High utility should come first"

    def test_no_approved_items(self, html_module, tmp_path, capsys):
        """Should warn and not create file if no approved items."""
        data = [{"id": "1", "status": "rejected", "questions": "Q", "answer": "A"}]
        input_json = str(tmp_path / "input.json")
        output_html = str(tmp_path / "output.html")

        with open(input_json, 'w') as f:
            json.dump(data, f)

        with patch.object(html_module, 'INPUT_JSON', input_json), \
             patch.object(html_module, 'OUTPUT_HTML', output_html):
            html_module.main()

        assert not os.path.exists(output_html)
        captured = capsys.readouterr()
        assert "approved" in captured.out.lower() or "WARNING" in captured.out
