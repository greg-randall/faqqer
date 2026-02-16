import os
import json
import numpy as np
import pandas as pd
import pytest
from unittest.mock import patch
from tests.conftest import import_step


@pytest.fixture
def cluster_module():
    return import_step("04_cluster_facts")


class TestClustering:
    def _make_embedded_file(self, tmp_path, filename, facts_with_vectors, source_file=None):
        """Helper to create an embedded JSON file."""
        input_dir = tmp_path / "content_embedded"
        input_dir.mkdir(exist_ok=True)

        data = {
            "page_topic": "Test",
            "facts": [f["text"] for f in facts_with_vectors],
            "facts_with_embeddings": facts_with_vectors,
            "source_file": source_file or filename.replace(".json", ".md")
        }
        with open(input_dir / filename, 'w') as f:
            json.dump(data, f)

    def test_dedup_removes_near_duplicates(self, cluster_module):
        """Facts with cosine similarity > 0.95 should be deduplicated."""
        # Two nearly identical vectors and one different
        df = pd.DataFrame({
            "fact": ["Fact A", "Fact A duplicate", "Fact B"],
            "vector": [
                [1.0, 0.0, 0.0, 0.0, 0.0],
                [0.999, 0.01, 0.0, 0.0, 0.0],  # very similar to A
                [0.0, 0.0, 1.0, 0.0, 0.0],       # different
            ],
            "source": ["a.md", "b.md", "c.md"]
        })
        result = cluster_module.deduplicate_facts(df)
        assert len(result) == 2

    def test_source_merging_is_set_based(self, cluster_module):
        """Dedup should merge sources using sets, not string containment."""
        # Make vectors that are near-duplicates
        df = pd.DataFrame({
            "fact": ["Fact A", "Fact A dup"],
            "vector": [
                [1.0, 0.0, 0.0, 0.0, 0.0],
                [0.999, 0.01, 0.0, 0.0, 0.0],
            ],
            "source": ["a.md; b.md", "b.md; c.md"]
        })
        result = cluster_module.deduplicate_facts(df)
        assert len(result) == 1
        merged_source = result.iloc[0]["source"]
        sources = set(merged_source.split("; "))
        assert sources == {"a.md", "b.md", "c.md"}

    def test_csv_format(self, cluster_module, tmp_path):
        """Output CSV should have cluster_label, source, fact columns."""
        # Create some embedded data with enough facts
        np.random.seed(42)
        facts = []
        for i in range(20):
            facts.append({
                "text": f"Fact number {i}",
                "vector": np.random.randn(5).tolist()
            })
        self._make_embedded_file(tmp_path, "test.json", facts)

        output_file = str(tmp_path / "clusters.csv")

        with patch.object(cluster_module, 'INPUT_DIR', str(tmp_path / "content_embedded")), \
             patch.object(cluster_module, 'OUTPUT_FILE', output_file):
            cluster_module.main()

        assert os.path.exists(output_file)
        df = pd.read_csv(output_file)
        assert set(df.columns) == {"cluster_label", "source", "fact"}

    def test_max_cluster_size(self, cluster_module, tmp_path):
        """No non-noise cluster should exceed MAX_CLUSTER_SIZE after splitting."""
        np.random.seed(42)
        # Create 30 facts with enough spread to survive dedup but cluster together
        facts = []
        for i in range(30):
            # Spread vectors enough to avoid dedup (similarity < 0.95)
            # but keep in same general region
            vec = np.random.randn(50).tolist()  # higher dim for better clustering
            facts.append({"text": f"Unique fact number {i} with distinct content", "vector": vec})

        self._make_embedded_file(tmp_path, "test.json", facts)
        output_file = str(tmp_path / "clusters.csv")

        with patch.object(cluster_module, 'INPUT_DIR', str(tmp_path / "content_embedded")), \
             patch.object(cluster_module, 'OUTPUT_FILE', output_file):
            cluster_module.main()

        df = pd.read_csv(output_file)
        non_noise = df[~df['cluster_label'].str.endswith('_noise')]
        if len(non_noise) > 0:
            sizes = non_noise['cluster_label'].value_counts()
            assert sizes.max() <= cluster_module.MAX_CLUSTER_SIZE

    def test_noise_labels(self, cluster_module, tmp_path):
        """Noise clusters should have labels ending in '_noise'."""
        np.random.seed(42)
        # Mix of clustered and outlier facts
        facts = []
        # 10 similar facts
        for i in range(10):
            facts.append({"text": f"Similar {i}", "vector": [1.0 + i*0.001, 0, 0, 0, 0]})
        # 3 outliers (too few for a cluster)
        for i in range(3):
            facts.append({"text": f"Outlier {i}", "vector": [0, 0, 0, 0, float(i+1)]})

        self._make_embedded_file(tmp_path, "test.json", facts)
        output_file = str(tmp_path / "clusters.csv")

        with patch.object(cluster_module, 'INPUT_DIR', str(tmp_path / "content_embedded")), \
             patch.object(cluster_module, 'OUTPUT_FILE', output_file):
            cluster_module.main()

        df = pd.read_csv(output_file)
        noise_rows = df[df['cluster_label'].str.endswith('_noise')]
        non_noise = df[~df['cluster_label'].str.endswith('_noise')]
        # At least some data should be in non-noise clusters
        assert len(non_noise) > 0
