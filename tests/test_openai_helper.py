import json
import pytest
from unittest.mock import patch, MagicMock, PropertyMock
import openai
from tests.conftest import import_step


@pytest.fixture
def helper_module():
    return import_step("openai_helper")


class TestOpenaiLlmRequest:
    def test_tool_call_response(self, helper_module):
        """Should return tool call arguments when model uses a tool."""
        mock_args = json.dumps({"key": "value"})
        mock_tool_call = MagicMock()
        mock_tool_call.function.arguments = mock_args

        mock_message = MagicMock()
        mock_message.tool_calls = [mock_tool_call]

        mock_choice = MagicMock()
        mock_choice.message = mock_message

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        with patch.object(helper_module.client.chat.completions, 'create', return_value=mock_response):
            result = helper_module.openai_llm_request("sys", "user")

        assert result == mock_args

    def test_plain_text_response(self, helper_module):
        """Should return content when no tool call is made."""
        mock_message = MagicMock()
        mock_message.tool_calls = None
        mock_message.content = "Hello world"

        mock_choice = MagicMock()
        mock_choice.message = mock_message

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        with patch.object(helper_module.client.chat.completions, 'create', return_value=mock_response):
            result = helper_module.openai_llm_request("sys", "user")

        assert result == "Hello world"

    def test_api_exception_returns_none(self, helper_module):
        """Should return None on API error after retries exhaust."""
        with patch.object(helper_module.client.chat.completions, 'create',
                         side_effect=Exception("Server error")):
            result = helper_module.openai_llm_request("sys", "user")

        assert result is None

    def test_timeout_parameter_passed(self, helper_module):
        """Should pass timeout=120 to the API call."""
        mock_message = MagicMock()
        mock_message.tool_calls = None
        mock_message.content = "ok"

        mock_choice = MagicMock()
        mock_choice.message = mock_message

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        with patch.object(helper_module.client.chat.completions, 'create',
                         return_value=mock_response) as mock_create:
            helper_module.openai_llm_request("sys", "user")

        call_kwargs = mock_create.call_args[1]
        assert call_kwargs['timeout'] == 120

    def test_retry_on_rate_limit(self, helper_module):
        """Should retry on RateLimitError and succeed on second attempt."""
        mock_message = MagicMock()
        mock_message.tool_calls = None
        mock_message.content = "success"

        mock_choice = MagicMock()
        mock_choice.message = mock_message

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        rate_limit_error = openai.RateLimitError(
            message="rate limited",
            response=MagicMock(status_code=429),
            body=None
        )

        with patch.object(helper_module.client.chat.completions, 'create',
                         side_effect=[rate_limit_error, mock_response]), \
             patch('openai_helper.time.sleep'):
            result = helper_module.openai_llm_request("sys", "user")

        assert result == "success"


class TestGetEmbeddings:
    def test_empty_input_returns_empty(self, helper_module):
        """Should return [] for empty input without calling API."""
        result = helper_module.get_embeddings([])
        assert result == []

    def test_batching(self, helper_module):
        """Should batch >100 items into multiple API calls."""
        texts = [f"text {i}" for i in range(150)]

        mock_item = MagicMock()
        mock_item.embedding = [0.1, 0.2]

        mock_response = MagicMock()
        mock_response.data = [mock_item] * 100

        mock_response2 = MagicMock()
        mock_response2.data = [mock_item] * 50

        with patch.object(helper_module.client.embeddings, 'create',
                         side_effect=[mock_response, mock_response2]):
            result = helper_module.get_embeddings(texts)

        assert len(result) == 150

    def test_batch_failure_returns_empty(self, helper_module):
        """Should return [] if any batch fails."""
        with patch.object(helper_module.client.embeddings, 'create',
                         side_effect=Exception("API down")):
            result = helper_module.get_embeddings(["text1"])

        assert result == []
