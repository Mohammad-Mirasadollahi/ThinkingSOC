# app/external/ollama_client.py

import os
import json
import requests
import logging
from dotenv import load_dotenv

# Load environment variables - Consider a central config module later
load_dotenv()

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434") # Default safer
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3") # Example default
OLLAMA_URL = f"{OLLAMA_HOST}/api/generate"

# Generation parameters - read from env
TEMPERATURE = float(os.getenv("TEMPERATURE", 0.2))
TOP_P = float(os.getenv("TOP_P", 0.5))
TOP_K = int(os.getenv("TOP_K", 20))
MAX_TOKENS = int(os.getenv("MAX_TOKENS", 256))
REPETITION_PENALTY = float(os.getenv("REPETITION_PENALTY", 1.2))

PROMPT_PATH = os.path.join(os.getcwd(), "prompt", "prompt.md")

# Get a logger instance for this module
logger = logging.getLogger(__name__)

def read_prompt():
    """Reads the prompt content from the prompt.md file."""
    try:
        with open(PROMPT_PATH, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        logger.error(f"Prompt file not found at {PROMPT_PATH}")
        raise # Re-raise the exception
    except Exception as e:
        logger.error(f"Error reading prompt file {PROMPT_PATH}: {e}")
        raise # Re-raise

def generate_analysis(data_to_analyze: dict) -> str:
    """
    Sends data to the Ollama server for analysis and returns the raw response string.
    """
    try:
        prompt_template = read_prompt()
    except Exception:
        logger.exception("Failed to read prompt template.") # Log exception details
        return "Error: Could not read prompt template." # Return error message

    # Format input for the prompt
    input_data_str = json.dumps(
        {k: v for k, v in data_to_analyze.items() if k not in ['queue_number', 'received_at']},
        indent=2
    )
    full_prompt = f"{prompt_template}\n\n### Input Data:\n{input_data_str}"

    payload = {
        "model": OLLAMA_MODEL,
        "prompt": full_prompt,
        "stream": False,
        "options": { # Ollama API often uses an 'options' sub-dictionary
            "temperature": TEMPERATURE,
            "top_p": TOP_P,
            "top_k": TOP_K,
            "num_predict": MAX_TOKENS, # Parameter name might differ slightly
            "repeat_penalty": REPETITION_PENALTY
        }
    }
    # Log before sending - Use DEBUG level for potentially large payloads
    logger.debug(f"Attempting to send request to Ollama URL: {OLLAMA_URL}")
    # Log key details, avoid logging the full prompt unless necessary for debugging
    logger.debug(f"Ollama Payload Details - Model: {payload['model']}, Options: {payload['options']}")
    logger.debug(f"Ollama Prompt length: {len(payload['prompt'])} characters.")
    # If you absolutely need to see the prompt (be careful with size/sensitivity):
    # logger.debug(f"Full Ollama Prompt: {payload['prompt']}")

    try:
        logger.info(f"Sending request to Ollama model '{OLLAMA_MODEL}'...") # Info level for key action
        response = requests.post(OLLAMA_URL, json=payload, timeout=1200) # Added timeout
        logger.info(f"Received response from Ollama. Status Code: {response.status_code}") # Log status code

        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)

        response_data = response.json()
        analysis_text = response_data.get("response", "")
        # Log received data - DEBUG level
        logger.debug(f"Ollama raw response JSON: {response_data}")
        logger.debug(f"Extracted analysis text length: {len(analysis_text)} characters.")
        # Log first 100 chars for quick inspection
        logger.debug(f"Ollama analysis text (first 100 chars): {analysis_text[:100]}...")
        logger.info(f"Successfully received analysis from Ollama for model '{OLLAMA_MODEL}'.")
        return analysis_text

    except requests.exceptions.Timeout:
        logger.error(f"Ollama request timed out after 120 seconds to {OLLAMA_URL}")
        return f"Error: Ollama request timed out"
    except requests.exceptions.ConnectionError:
        logger.error(f"Ollama connection error. Could not connect to {OLLAMA_URL}. Is Ollama running and accessible?")
        return f"Error: Ollama connection error"
    except requests.exceptions.HTTPError as e:
        logger.error(f"Ollama HTTP error: {e.response.status_code} - {e.response.text}")
        return f"Error: Ollama HTTP error {e.response.status_code} - Check Ollama logs."
    except requests.exceptions.RequestException as e:
        logger.error(f"Ollama request failed with generic RequestException: {e}")
        return f"Error: Ollama request failed - {e}"
    except json.JSONDecodeError as e:
         logger.error(f"Failed to decode Ollama JSON response: {e} - Response text: {response.text}")
         return f"Error: Failed to decode Ollama JSON response - {e}"
    except Exception as e:
        # Catch any other unexpected errors
        logger.exception(f"An unexpected error occurred during Ollama request") # Log full traceback
        return f"Error: An unexpected error occurred - {e}"
