import os
from openai import OpenAI

# Initialize client using environment variable OPENAI_API_KEY
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

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
    try:
        # Check for empty list
        if not texts:
            return []

        # Batching
        # OpenAI supports up to 2048 inputs in an array, 
        # but large total token counts can hit rate limits.
        # Batch size of 100 is generally safe for typical text chunks.
        batch_size = 100
        all_embeddings = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i+batch_size]
            
            # Simple sanitization: replace newlines with spaces. 
            # This is common practice for embeddings to avoid whitespace issues.
            batch = [text.replace("\n", " ") for text in batch] 
            
            response = client.embeddings.create(input=batch, model=model)
            
            # Ensure the embeddings are in the same order as input
            # OpenAI guarantees order in the list.
            batch_embeddings = [item.embedding for item in response.data]
            all_embeddings.extend(batch_embeddings)

        return all_embeddings

    except Exception as e:
        print(f"OpenAI Embedding Error: {e}")
        return []
