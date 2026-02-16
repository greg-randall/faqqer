import os
import json
import pytest
from unittest.mock import patch
from tests.conftest import import_step


@pytest.fixture
def process_module():
    return import_step("02_process_content")


class TestProcessContent:
    def test_output_json_schema(self, process_module, tmp_path):
        """Output JSON should have page_topic, facts, and source_file."""
        input_dir = str(tmp_path / "content")
        output_dir = str(tmp_path / "content_processed")
        os.makedirs(input_dir)
        os.makedirs(output_dir)

        # Write a sample markdown file
        with open(os.path.join(input_dir, "test.md"), 'w') as f:
            f.write("# Test Page\n**Source URL:** https://example.com\n\nSome content.")

        mock_response = json.dumps({
            "page_topic": "Test Page",
            "facts": ["Fact one.", "Fact two."]
        })

        with patch.object(process_module, 'INPUT_DIR', input_dir), \
             patch.object(process_module, 'OUTPUT_DIR', output_dir), \
             patch.object(process_module.openai_helper, 'openai_llm_request', return_value=mock_response):
            process_module.process_files()

        output_path = os.path.join(output_dir, "test.json")
        assert os.path.exists(output_path)

        with open(output_path) as f:
            data = json.load(f)

        assert "page_topic" in data
        assert "facts" in data
        assert isinstance(data["facts"], list)
        assert data["source_file"] == "test.md"

    def test_skip_if_exists(self, process_module, tmp_path):
        """Should skip files that already have output."""
        input_dir = str(tmp_path / "content")
        output_dir = str(tmp_path / "content_processed")
        os.makedirs(input_dir)
        os.makedirs(output_dir)

        with open(os.path.join(input_dir, "test.md"), 'w') as f:
            f.write("# Test\nContent")
        with open(os.path.join(output_dir, "test.json"), 'w') as f:
            json.dump({"page_topic": "Existing"}, f)

        with patch.object(process_module, 'INPUT_DIR', input_dir), \
             patch.object(process_module, 'OUTPUT_DIR', output_dir), \
             patch.object(process_module.openai_helper, 'openai_llm_request') as mock_llm:
            process_module.process_files()

        mock_llm.assert_not_called()

    def test_limit_zero_processes_all(self, process_module, tmp_path):
        """limit=0 should NOT truncate the file list (regression for `if limit:` bug)."""
        input_dir = str(tmp_path / "content")
        output_dir = str(tmp_path / "content_processed")
        os.makedirs(input_dir)
        os.makedirs(output_dir)

        for i in range(3):
            with open(os.path.join(input_dir, f"test{i}.md"), 'w') as f:
                f.write(f"# Page {i}\nContent {i}")

        mock_response = json.dumps({"page_topic": "T", "facts": ["F"]})

        with patch.object(process_module, 'INPUT_DIR', input_dir), \
             patch.object(process_module, 'OUTPUT_DIR', output_dir), \
             patch.object(process_module.openai_helper, 'openai_llm_request', return_value=mock_response):
            process_module.process_files(limit=0)

        # With the fix, limit=0 means no limit → process all 3
        outputs = [f for f in os.listdir(output_dir) if f.endswith('.json')]
        assert len(outputs) == 3
