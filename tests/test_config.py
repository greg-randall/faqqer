import os
import importlib
import pytest
from tests.conftest import import_step


@pytest.fixture
def config_module():
    return import_step("config")


class TestGetRunDir:
    def test_returns_dot_when_no_env(self, config_module, monkeypatch):
        """Without FAQQER_RUN_DIR set, should return '.' for backward compat."""
        monkeypatch.delenv("FAQQER_RUN_DIR", raising=False)
        assert config_module.get_run_dir() == "."

    def test_returns_env_value(self, config_module, monkeypatch):
        """When FAQQER_RUN_DIR is set, should return that value."""
        monkeypatch.setenv("FAQQER_RUN_DIR", "runs/example.com_2026-01-01_120000")
        assert config_module.get_run_dir() == "runs/example.com_2026-01-01_120000"

    def test_empty_env_returns_empty(self, config_module, monkeypatch):
        """An empty FAQQER_RUN_DIR should return empty string (not '.')."""
        monkeypatch.setenv("FAQQER_RUN_DIR", "")
        # Empty string is falsy but still a valid env value
        assert config_module.get_run_dir() == ""


class TestStepPathResolution:
    """Verify that step modules resolve paths under FAQQER_RUN_DIR at import time."""

    def _reimport_with_env(self, module_name, monkeypatch, run_dir):
        """Set FAQQER_RUN_DIR and reimport a module to pick up new paths."""
        monkeypatch.setenv("FAQQER_RUN_DIR", run_dir)
        # Force reimport so module-level constants are recomputed
        mod = importlib.import_module(module_name)
        importlib.reload(mod)
        return mod

    def test_step02_paths(self, monkeypatch):
        mod = self._reimport_with_env("02_process_content", monkeypatch, "runs/test_run")
        assert mod.INPUT_DIR == os.path.join("runs/test_run", "content")
        assert mod.OUTPUT_DIR == os.path.join("runs/test_run", "content_processed")

    def test_step03_paths(self, monkeypatch):
        mod = self._reimport_with_env("03_generate_embeddings", monkeypatch, "runs/test_run")
        assert mod.INPUT_DIR == os.path.join("runs/test_run", "content_processed")
        assert mod.OUTPUT_DIR == os.path.join("runs/test_run", "content_embedded")

    def test_step04_paths(self, monkeypatch):
        mod = self._reimport_with_env("04_cluster_facts", monkeypatch, "runs/test_run")
        assert mod.INPUT_DIR == os.path.join("runs/test_run", "content_embedded")
        assert mod.OUTPUT_FILE == os.path.join("runs/test_run", "data", "fact_clusters.csv")

    def test_step05_paths(self, monkeypatch):
        mod = self._reimport_with_env("05_generate_faq", monkeypatch, "runs/test_run")
        assert mod.INPUT_CSV == os.path.join("runs/test_run", "data", "fact_clusters.csv")
        assert mod.OUTPUT_JSON == os.path.join("runs/test_run", "data", "faq_raw.json")

    def test_step06_paths(self, monkeypatch):
        mod = self._reimport_with_env("06_enrich_faq", monkeypatch, "runs/test_run")
        assert mod.INPUT_FILE == os.path.join("runs/test_run", "data", "faq_raw.json")
        assert mod.OUTPUT_FILE == os.path.join("runs/test_run", "data", "faq_categorized.json")
        assert mod.CONTENT_DIR == os.path.join("runs/test_run", "content")

    def test_step08_paths(self, monkeypatch):
        mod = self._reimport_with_env("08_generate_wp_html", monkeypatch, "runs/test_run")
        assert mod.INPUT_JSON == os.path.join("runs/test_run", "data", "faq_categorized.json")
        assert mod.OUTPUT_HTML == os.path.join("runs/test_run", "data", "faq_final.html")

    def test_default_paths_without_env(self, monkeypatch):
        """Without FAQQER_RUN_DIR, paths should be relative to '.' (backward compat)."""
        monkeypatch.delenv("FAQQER_RUN_DIR", raising=False)
        mod = importlib.import_module("02_process_content")
        importlib.reload(mod)
        assert mod.INPUT_DIR == os.path.join(".", "content")
        assert mod.OUTPUT_DIR == os.path.join(".", "content_processed")
