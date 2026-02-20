import json
import pytest
from tests.conftest import import_step


@pytest.fixture
def prompts_module():
    return import_step("prompts")


class TestPromptsYaml:
    """Verify prompts.yaml loads correctly and has all expected structure."""

    def test_loads_without_error(self, prompts_module):
        """prompts.yaml should parse without errors."""
        assert prompts_module._prompts is not None

    def test_top_level_keys(self, prompts_module):
        """All three pipeline stages should exist."""
        for key in ["process_content", "generate_faq", "enrich_faq"]:
            assert key in prompts_module._prompts, f"Missing top-level key: {key}"

    def test_process_content_structure(self, prompts_module):
        """02_process_content prompt should have system, tools, tool_choice."""
        assert isinstance(prompts_module.get("process_content.system"), str)
        tools = prompts_module.get_tools("process_content")
        assert isinstance(tools, list)
        assert tools[0]["function"]["name"] == "extract_atomic_facts"

    def test_generate_faq_structure(self, prompts_module):
        """05_generate_faq prompt should have system, tools, tool_choice."""
        assert isinstance(prompts_module.get("generate_faq.system"), str)
        tools = prompts_module.get_tools("generate_faq")
        assert tools[0]["function"]["name"] == "synthesize_faq"

    def test_enrich_faq_subkeys(self, prompts_module):
        """06_enrich_faq should have all four sub-prompts."""
        for sub in ["discover_categories", "classify", "audit", "evaluate"]:
            assert sub in prompts_module._prompts["enrich_faq"], f"Missing enrich_faq.{sub}"

    def test_tool_schemas_valid(self, prompts_module):
        """Every tool schema should have type, function.name, function.parameters."""
        paths = [
            "process_content",
            "generate_faq",
            "enrich_faq.discover_categories",
            "enrich_faq.classify",
            "enrich_faq.audit",
            "enrich_faq.evaluate",
        ]
        for path in paths:
            tools = prompts_module.get_tools(path)
            assert len(tools) >= 1, f"No tools at {path}"
            tool = tools[0]
            assert tool["type"] == "function", f"Bad tool type at {path}"
            assert "name" in tool["function"], f"Missing function.name at {path}"
            assert "parameters" in tool["function"], f"Missing function.parameters at {path}"

    def test_template_formatting(self, prompts_module):
        """Template placeholders should format correctly."""
        result = prompts_module.get(
            "enrich_faq.classify.system",
            taxonomy='["Cat A", "Cat B"]'
        )
        assert '["Cat A", "Cat B"]' in result

        result = prompts_module.get(
            "enrich_faq.audit.user",
            fact_text="- Fact 1",
            question="Q?",
            answer="A."
        )
        assert "- Fact 1" in result
        assert "Q?" in result

    def test_get_tools_returns_deep_copy(self, prompts_module):
        """get_tools should return a copy, not a reference to the original."""
        tools1 = prompts_module.get_tools("enrich_faq.classify")
        tools1[0]["function"]["parameters"]["properties"]["category"]["enum"] = ["X"]

        tools2 = prompts_module.get_tools("enrich_faq.classify")
        assert tools2[0]["function"]["parameters"]["properties"]["category"]["enum"] != ["X"]
