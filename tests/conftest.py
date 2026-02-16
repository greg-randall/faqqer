import os
import sys
import importlib
import json
import pytest

# Add project root to path so numbered modules can be imported
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


@pytest.fixture(autouse=True)
def mock_openai_env(monkeypatch):
    """Set a fake OPENAI_API_KEY so module imports don't crash."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-fake-key-for-testing")


def import_step(module_name):
    """Import a numbered pipeline module by name (e.g. '01_extract_content')."""
    return importlib.import_module(module_name)


def fixture_path(filename):
    """Return absolute path to a test fixture file."""
    return os.path.join(FIXTURES_DIR, filename)


def load_json_fixture(filename):
    """Load and return parsed JSON from a fixture file."""
    with open(fixture_path(filename), 'r', encoding='utf-8') as f:
        return json.load(f)
