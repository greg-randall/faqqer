import os
import json
import time
import openai
from openai import OpenAI
import config

# Initialize client — fail fast if key is missing
api_key = os.environ.get("OPENAI_API_KEY")
if not api_key:
    raise EnvironmentError("OPENAI_API_KEY environment variable is not set.")
client = OpenAI(api_key=api_key)


def _retry_api_call(fn):
    """Retry an API call with exponential backoff on transient errors."""
    for attempt in range(config.MAX_RETRIES):
        try:
            return fn()
        except (openai.RateLimitError, openai.APITimeoutError, openai.APIConnectionError) as e:
            if attempt == config.MAX_RETRIES - 1:
                raise
            delay = config.RETRY_DELAY * (2 ** attempt)
            print(f"  Retry {attempt+1}/{config.MAX_RETRIES} after {type(e).__name__}, waiting {delay}s...")
            time.sleep(delay)

def openai_llm_request(system_prompt, user_prompt, model=None, tools=None, tool_choice=None, max_tokens=4000, temperature=None):
    """
    Makes a request to OpenAI Chat Completion API.

    Args:
        system_prompt (str): The system instructions.
        user_prompt (str): The user input.
        model (str): Model name. Defaults to config.HELPER_MODEL.
        tools (list): List of tool definitions (JSON schema).
        tool_choice (dict or str): Tool choice configuration.
        max_tokens (int): Maximum tokens for the response.
        temperature (float): Sampling temperature. Defaults to config.TEMPERATURE.

    Returns:
        str: The content of the response, or the arguments JSON string if a tool was called.
        None: If an error occurs.
    """
    if model is None:
        model = config.HELPER_MODEL
    if temperature is None:
        temperature = config.TEMPERATURE

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    try:
        def _call():
            return client.chat.completions.create(
                model=model,
                messages=messages,
                tools=tools,
                tool_choice=tool_choice,
                max_tokens=max_tokens,
                temperature=temperature,
                timeout=config.TIMEOUT
            )

        response = _retry_api_call(_call)

        message = response.choices[0].message

        # Handle tool calls — check the response, not just the request params
        if message.tool_calls:
            return message.tool_calls[0].function.arguments

        return message.content

    except Exception as e:
        print(f"OpenAI API Error ({type(e).__name__}): {e}")
        return None


def get_embeddings(texts, model=None):
    """
    Generates embeddings for a list of texts using OpenAI API.
    Handles batching to ensure reliability.

    Args:
        texts (list of str): List of texts to embed.
        model (str): Embedding model to use. Defaults to config.EMBEDDING_MODEL.

    Returns:
        list of list of floats: A list of embedding vectors corresponding to the input texts.
    """
    if model is None:
        model = config.EMBEDDING_MODEL

    if not texts:
        return []

    batch_size = config.EMBEDDING_BATCH_SIZE
    all_embeddings = []

    for i in range(0, len(texts), batch_size):
        batch = texts[i:i+batch_size]

        # Replace newlines with spaces to avoid whitespace issues
        batch = [text.replace("\n", " ") for text in batch]

        try:
            def _call(b=batch):
                return client.embeddings.create(input=b, model=model, timeout=config.TIMEOUT)

            response = _retry_api_call(_call)
            batch_embeddings = [item.embedding for item in response.data]
            all_embeddings.extend(batch_embeddings)
        except Exception as e:
            print(f"OpenAI Embedding Error ({type(e).__name__}) on batch {i//batch_size}: {e}")
            return []

    return all_embeddings
