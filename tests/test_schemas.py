import json
import csv
import pytest
from tests.conftest import fixture_path, load_json_fixture


class TestFixtureSchemas:
    def test_processed_json_schema(self):
        """sample_processed.json should have page_topic, facts[], source_file."""
        data = load_json_fixture("sample_processed.json")
        assert "page_topic" in data
        assert isinstance(data["facts"], list)
        assert len(data["facts"]) > 0
        assert "source_file" in data

    def test_embedded_json_schema(self):
        """sample_embedded.json should have facts_with_embeddings[{text, vector}]."""
        data = load_json_fixture("sample_embedded.json")
        assert "facts_with_embeddings" in data
        for item in data["facts_with_embeddings"]:
            assert "text" in item
            assert "vector" in item
            assert isinstance(item["vector"], list)
            assert len(item["vector"]) == 5

    def test_faq_raw_schema(self):
        """sample_faq_raw.json entries should have id, questions, answer, source_facts, verified."""
        data = load_json_fixture("sample_faq_raw.json")
        assert isinstance(data, list)
        for entry in data:
            assert "id" in entry
            assert "questions" in entry
            assert "answer" in entry
            assert "source_facts" in entry
            assert "verified" in entry

    def test_faq_categorized_schema(self):
        """sample_faq_categorized.json should have full schema with category, audit, scores."""
        data = load_json_fixture("sample_faq_categorized.json")
        assert isinstance(data, list)
        for entry in data:
            assert "category" in entry
            assert "status" in entry
            assert "audit_status" in entry
            assert "utility_score" in entry
            assert isinstance(entry["utility_score"], (int, float))
