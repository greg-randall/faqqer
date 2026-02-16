import os
import json
import pytest
from unittest.mock import patch, MagicMock
from tests.conftest import import_step, fixture_path, load_json_fixture


@pytest.fixture
def enrich_module():
    return import_step("06_enrich_faq")


class TestPhaseCategories:
    def test_category_assignment(self, enrich_module):
        """Each entry should get a category assigned."""
        data = load_json_fixture("sample_faq_raw.json")

        taxonomy_response = json.dumps({
            "category_list": ["About & Contact", "Programs"],
            "reasoning": "Natural groupings"
        })
        classify_response = json.dumps({"category": "About & Contact"})

        with patch.object(enrich_module.openai_helper, 'openai_llm_request',
                         side_effect=[taxonomy_response, classify_response, classify_response]):
            enrich_module.phase_categorize(data)

        for entry in data:
            assert "category" in entry

    def test_taxonomy_parse_error(self, enrich_module):
        """Should handle bad JSON from taxonomy discovery gracefully."""
        data = load_json_fixture("sample_faq_raw.json")

        with patch.object(enrich_module.openai_helper, 'openai_llm_request', return_value="not json"):
            enrich_module.phase_categorize(data)

        # Should not crash — entries won't have categories but no exception
        assert True


class TestPhaseUrlEnrichment:
    def test_url_extraction(self, enrich_module, tmp_path):
        """Should extract URLs from markdown files into source_facts."""
        content_dir = str(tmp_path / "content")
        os.makedirs(content_dir)

        # Create a markdown file matching a source
        with open(os.path.join(content_dir, "about.md"), 'w') as f:
            f.write("# About\n**Source URL:** https://example.com/about/\n**ID:** 1\n\nContent")

        data = [
            {
                "id": "1",
                "source_facts": [
                    {"fact": "Some fact", "source": "about.md"}
                ]
            }
        ]

        with patch.object(enrich_module, 'CONTENT_DIR', content_dir):
            enrich_module.phase_url_enrichment(data)

        assert data[0]["source_facts"][0]["live_url"] == "https://example.com/about/"

    def test_semicolon_split_sources(self, enrich_module, tmp_path):
        """Should split semicolon-merged sources and look up each individually."""
        content_dir = str(tmp_path / "content")
        os.makedirs(content_dir)

        with open(os.path.join(content_dir, "a.md"), 'w') as f:
            f.write("# A\n**Source URL:** https://example.com/a/\n")
        with open(os.path.join(content_dir, "b.md"), 'w') as f:
            f.write("# B\n**Source URL:** https://example.com/b/\n")

        data = [
            {
                "id": "1",
                "source_facts": [
                    {"fact": "Merged fact", "source": "a.md; b.md"}
                ]
            }
        ]

        with patch.object(enrich_module, 'CONTENT_DIR', content_dir):
            enrich_module.phase_url_enrichment(data)

        # Should find a URL (from the first source)
        assert data[0]["source_facts"][0]["live_url"] == "https://example.com/a/"

    def test_missing_file_returns_none(self, enrich_module, tmp_path):
        """Missing source files should result in live_url=None."""
        content_dir = str(tmp_path / "content")
        os.makedirs(content_dir)

        data = [
            {
                "id": "1",
                "source_facts": [
                    {"fact": "Fact", "source": "nonexistent.md"}
                ]
            }
        ]

        with patch.object(enrich_module, 'CONTENT_DIR', content_dir):
            enrich_module.phase_url_enrichment(data)

        assert data[0]["source_facts"][0]["live_url"] is None


class TestPhaseAuditScore:
    def test_audit_fields_added(self, enrich_module):
        """Should add audit_status and audit_reason fields."""
        data = load_json_fixture("sample_faq_raw.json")

        audit_response = json.dumps({"status": "PASS", "reason": "All good"})
        eval_response = json.dumps({
            "universality_score": 7,
            "criticality_score": 5,
            "search_demand_score": 6,
            "reasoning": "Standard info"
        })

        with patch.object(enrich_module.openai_helper, 'openai_llm_request',
                         side_effect=[audit_response, eval_response, audit_response, eval_response]):
            enrich_module.phase_audit_and_score(data)

        for entry in data:
            assert "audit_status" in entry
            assert entry["audit_status"] in ("PASS", "FAIL")

    def test_score_ranges(self, enrich_module):
        """Utility scores should be between 1 and 10."""
        data = load_json_fixture("sample_faq_raw.json")

        audit_response = json.dumps({"status": "PASS", "reason": "OK"})
        eval_response = json.dumps({
            "universality_score": 8,
            "criticality_score": 6,
            "search_demand_score": 7,
            "reasoning": "High value"
        })

        with patch.object(enrich_module.openai_helper, 'openai_llm_request',
                         side_effect=[audit_response, eval_response, audit_response, eval_response]):
            enrich_module.phase_audit_and_score(data)

        for entry in data:
            assert 1 <= entry["utility_score"] <= 10

    def test_atomic_write(self, enrich_module, tmp_path):
        """Main should write output atomically via tempfile+replace."""
        input_file = str(tmp_path / "faq_raw.json")
        output_file = str(tmp_path / "data" / "faq_categorized.json")

        # Write a minimal input
        data = [{"id": "1", "questions": "Q?", "answer": "A.", "source_facts": [], "verified": False}]
        with open(input_file, 'w') as f:
            json.dump(data, f)

        taxonomy_resp = json.dumps({"category_list": ["General"], "reasoning": "only one"})
        classify_resp = json.dumps({"category": "General"})
        audit_resp = json.dumps({"status": "PASS", "reason": "OK"})
        eval_resp = json.dumps({
            "universality_score": 5, "criticality_score": 5,
            "search_demand_score": 5, "reasoning": "Average"
        })

        with patch.object(enrich_module, 'INPUT_FILE', input_file), \
             patch.object(enrich_module, 'OUTPUT_FILE', output_file), \
             patch.object(enrich_module, 'CONTENT_DIR', str(tmp_path / "content")), \
             patch.object(enrich_module.openai_helper, 'openai_llm_request',
                         side_effect=[taxonomy_resp, classify_resp, audit_resp, eval_resp]), \
             patch('sys.argv', ['06_enrich_faq.py']):
            os.makedirs(tmp_path / "content", exist_ok=True)
            enrich_module.main()

        assert os.path.exists(output_file)
        with open(output_file) as f:
            result = json.load(f)
        assert len(result) == 1
        assert result[0]["category"] == "General"
