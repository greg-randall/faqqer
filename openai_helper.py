import os
import json
from openai import OpenAI

# Initialize client using environment variable OPENAI_API_KEY
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

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

        # Handle tool calls
        if tools and tool_choice:
             # If a tool was chosen/forced, return its arguments
             if message.tool_calls:
                 return message.tool_calls[0].function.arguments
             else:
                 # If no tool was called despite tools being present (unlikely if tool_choice forces it), 
                 # return content. Or return None if strict tool usage is expected?
                 # Based on azure_helper usage, it expects a JSON string compatible with json.loads.
                 # If content is empty/null, we might return None.
                 if not message.content:
                     return None
                 return message.content
        
        return message.content

    except Exception as e:
        print(f"OpenAI API Error: {e}")
        return None
