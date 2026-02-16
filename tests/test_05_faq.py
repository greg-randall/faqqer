import os
import json
import pytest
from unittest.mock import patch
from tests.conftest import import_step, fixture_path


@pytest.fixture
def faq_module():
    return import_step("05_generate_faq")


class TestGenerateFaq:
    def test_faq_json_schema(self, faq_module, tmp_path):
        """Output should have id, questions, answer, source_facts, verified."""
        input_csv = fixture_path("sample_clusters.csv")
        output_json = str(tmp_path / "faq_raw.json")

        mock_response = json.dumps({
            "question": "What is the mission?",
            "synthesized_answer": "The mission is to help people learn."
        })

        with patch.object(faq_module, 'INPUT_CSV', input_csv), \
             patch.object(faq_module, 'OUTPUT_JSON', output_json), \
             patch.object(faq_module.openai_helper, 'openai_llm_request', return_value=mock_response):
            faq_module.generate_faq()

        assert os.path.exists(output_json)
        with open(output_json) as f:
            data = json.load(f)

        assert len(data) > 0
        entry = data[0]
        assert "id" in entry
        assert "questions" in entry
        assert "answer" in entry
        assert "source_facts" in entry
        assert "verified" in entry
        assert entry["verified"] is False

    def test_noise_filtered(self, faq_module, tmp_path):
        """Noise clusters should be excluded from FAQ generation."""
        input_csv = fixture_path("sample_clusters.csv")
        output_json = str(tmp_path / "faq_raw.json")

        mock_response = json.dumps({
            "question": "Q?",
            "synthesized_answer": "A."
        })

        with patch.object(faq_module, 'INPUT_CSV', input_csv), \
             patch.object(faq_module, 'OUTPUT_JSON', output_json), \
             patch.object(faq_module.openai_helper, 'openai_llm_request', return_value=mock_response):
            faq_module.generate_faq()

        with open(output_json) as f:
            data = json.load(f)

        ids = [entry["id"] for entry in data]
        assert not any("noise" in str(id_) for id_ in ids)

    def test_api_returns_none_cluster_skipped(self, faq_module, tmp_path):
        """When API returns None for a cluster, others should still be written."""
        input_csv = fixture_path("sample_clusters.csv")
        output_json = str(tmp_path / "faq_raw.json")

        mock_response = json.dumps({
            "question": "Q?",
            "synthesized_answer": "A."
        })

        # First call returns None (failure), second succeeds
        with patch.object(faq_module, 'INPUT_CSV', input_csv), \
             patch.object(faq_module, 'OUTPUT_JSON', output_json), \
             patch.object(faq_module.openai_helper, 'openai_llm_request',
                         side_effect=[None, mock_response]):
            faq_module.generate_faq()

        with open(output_json) as f:
            data = json.load(f)

        # One cluster failed, one succeeded — should have 1 entry
        assert len(data) == 1

    def test_truncation_warning(self, faq_module, tmp_path, capsys):
        """Should warn when truncating facts beyond 40."""
        import pandas as pd

        # Create a CSV with >40 facts in one cluster
        rows = []
        for i in range(45):
            rows.append({"cluster_label": "big_cluster", "source": "test.md", "fact": f"Fact {i}"})
        df = pd.DataFrame(rows)

        input_csv = str(tmp_path / "clusters.csv")
        df.to_csv(input_csv, index=False)
        output_json = str(tmp_path / "faq_raw.json")

        mock_response = json.dumps({"question": "Q?", "synthesized_answer": "A."})

        with patch.object(faq_module, 'INPUT_CSV', input_csv), \
             patch.object(faq_module, 'OUTPUT_JSON', output_json), \
             patch.object(faq_module.openai_helper, 'openai_llm_request', return_value=mock_response):
            faq_module.generate_faq()

        captured = capsys.readouterr()
        assert "Truncating" in captured.out or "truncating" in captured.out.lower()
