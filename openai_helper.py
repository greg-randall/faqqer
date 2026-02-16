import os
import json
from openai import OpenAI

# Initialize client — fail fast if key is missing
api_key = os.environ.get("OPENAI_API_KEY")
if not api_key:
    raise EnvironmentError("OPENAI_API_KEY environment variable is not set.")
client = OpenAI(api_key=api_key)

def openai_llm_request(system_prompt, user_prompt, model="gpt-4o-mini", tools=None, tool_choice=None, max_tokens=4000, temperature=0.7):
    """
    Makes a request to OpenAI Chat Completion API.

    Args:
        system_prompt (str): The system instructions.
        user_prompt (str): The user input.
        model (str): Model name (e.g., "gpt-4o-mini", "gpt-4o").
        tools (list): List of tool definitions (JSON schema).
        tool_choice (dict or str): Tool choice configuration.
        max_tokens (int): Maximum tokens for the response.
        temperature (float): Sampling temperature.

    Returns:
        str: The content of the response, or the arguments JSON string if a tool was called.
        None: If an error occurs.
    """
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=tools,
            tool_choice=tool_choice,
            max_tokens=max_tokens,
            temperature=temperature
        )

        message = response.choices[0].message

        # Handle tool calls — check the response, not just the request params
        if message.tool_calls:
            return message.tool_calls[0].function.arguments

        return message.content

    except Exception as e:
        print(f"OpenAI API Error ({type(e).__name__}): {e}")
        return None


def get_embeddings(texts, model="text-embedding-3-large"):
    """
    Generates embeddings for a list of texts using OpenAI API.
    Handles batching to ensure reliability.

    Args:
        texts (list of str): List of texts to embed.
        model (str): Embedding model to use.

    Returns:
        list of list of floats: A list of embedding vectors corresponding to the input texts.
    """
    if not texts:
        return []

    batch_size = 100
    all_embeddings = []

    for i in range(0, len(texts), batch_size):
        batch = texts[i:i+batch_size]

        # Replace newlines with spaces to avoid whitespace issues
        batch = [text.replace("\n", " ") for text in batch]

        try:
            response = client.embeddings.create(input=batch, model=model)
            batch_embeddings = [item.embedding for item in response.data]
            all_embeddings.extend(batch_embeddings)
        except Exception as e:
            print(f"OpenAI Embedding Error ({type(e).__name__}) on batch {i//batch_size}: {e}")
            return []

    return all_embeddings
