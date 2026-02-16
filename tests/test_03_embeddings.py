import os
import json
import pytest
from unittest.mock import patch, MagicMock
from tests.conftest import import_step


@pytest.fixture
def embed_module():
    return import_step("03_generate_embeddings")


class TestGenerateEmbeddings:
    def test_vector_output(self, embed_module, tmp_path):
        """Output should contain facts_with_embeddings with text+vector."""
        input_dir = str(tmp_path / "content_processed")
        output_dir = str(tmp_path / "content_embedded")
        os.makedirs(input_dir)

        input_data = {
            "page_topic": "Test",
            "facts": ["Fact A", "Fact B"],
            "source_file": "test.md"
        }
        with open(os.path.join(input_dir, "test.json"), 'w') as f:
            json.dump(input_data, f)

        fake_vectors = [[0.1, 0.2, 0.3, 0.4, 0.5], [0.5, 0.4, 0.3, 0.2, 0.1]]

        with patch.object(embed_module, 'INPUT_DIR', input_dir), \
             patch.object(embed_module, 'OUTPUT_DIR', output_dir), \
             patch.object(embed_module.openai_helper, 'get_embeddings', return_value=fake_vectors):
            embed_module.process_embeddings()

        output_path = os.path.join(output_dir, "test.json")
        assert os.path.exists(output_path)

        with open(output_path) as f:
            data = json.load(f)

        assert "facts_with_embeddings" in data
        assert len(data["facts_with_embeddings"]) == 2
        assert data["facts_with_embeddings"][0]["text"] == "Fact A"
        assert len(data["facts_with_embeddings"][0]["vector"]) == 5

    def test_count_match(self, embed_module, tmp_path):
        """Number of embeddings must match number of facts."""
        input_dir = str(tmp_path / "content_processed")
        output_dir = str(tmp_path / "content_embedded")
        os.makedirs(input_dir)

        input_data = {"page_topic": "T", "facts": ["F1", "F2", "F3"], "source_file": "t.md"}
        with open(os.path.join(input_dir, "t.json"), 'w') as f:
            json.dump(input_data, f)

        # Return wrong number of vectors
        fake_vectors = [[0.1] * 5, [0.2] * 5]

        with patch.object(embed_module, 'INPUT_DIR', input_dir), \
             patch.object(embed_module, 'OUTPUT_DIR', output_dir), \
             patch.object(embed_module.openai_helper, 'get_embeddings', return_value=fake_vectors):
            embed_module.process_embeddings()

        output_path = os.path.join(output_dir, "t.json")
        # Should NOT write output when count doesn't match
        assert not os.path.exists(output_path)

    def test_skip_if_exists(self, embed_module, tmp_path):
        """Should skip files already in output dir."""
        input_dir = str(tmp_path / "content_processed")
        output_dir = str(tmp_path / "content_embedded")
        os.makedirs(input_dir)
        os.makedirs(output_dir)

        with open(os.path.join(input_dir, "test.json"), 'w') as f:
            json.dump({"facts": ["F"]}, f)
        with open(os.path.join(output_dir, "test.json"), 'w') as f:
            json.dump({"cached": True}, f)

        with patch.object(embed_module, 'INPUT_DIR', input_dir), \
             patch.object(embed_module, 'OUTPUT_DIR', output_dir), \
             patch.object(embed_module.openai_helper, 'get_embeddings') as mock_embed:
            embed_module.process_embeddings()

        mock_embed.assert_not_called()

    def test_empty_embeddings_skips_file(self, embed_module, tmp_path):
        """When get_embeddings returns [], file should be skipped (no output)."""
        input_dir = str(tmp_path / "content_processed")
        output_dir = str(tmp_path / "content_embedded")
        os.makedirs(input_dir)

        input_data = {"page_topic": "T", "facts": ["F1"], "source_file": "t.md"}
        with open(os.path.join(input_dir, "t.json"), 'w') as f:
            json.dump(input_data, f)

        with patch.object(embed_module, 'INPUT_DIR', input_dir), \
             patch.object(embed_module, 'OUTPUT_DIR', output_dir), \
             patch.object(embed_module.openai_helper, 'get_embeddings', return_value=[]):
            embed_module.process_embeddings()

        output_path = os.path.join(output_dir, "t.json")
        assert not os.path.exists(output_path)

    def test_indent_in_output(self, embed_module, tmp_path):
        """Output JSON should be indented (regression test for missing indent=2)."""
        input_dir = str(tmp_path / "content_processed")
        output_dir = str(tmp_path / "content_embedded")
        os.makedirs(input_dir)

        input_data = {"page_topic": "T", "facts": ["F1"], "source_file": "t.md"}
        with open(os.path.join(input_dir, "t.json"), 'w') as f:
            json.dump(input_data, f)

        fake_vectors = [[0.1, 0.2, 0.3, 0.4, 0.5]]

        with patch.object(embed_module, 'INPUT_DIR', input_dir), \
             patch.object(embed_module, 'OUTPUT_DIR', output_dir), \
             patch.object(embed_module.openai_helper, 'get_embeddings', return_value=fake_vectors):
            embed_module.process_embeddings()

        output_path = os.path.join(output_dir, "t.json")
        with open(output_path) as f:
            raw = f.read()

        # Indented JSON has newlines and spaces
        assert "\n" in raw
        assert "  " in raw
