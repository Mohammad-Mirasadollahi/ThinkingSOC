# app/utils/file_handler.py

import os
import json
import re
import logging

# Get a logger instance for this module
# Using __name__ ensures the logger name matches the module path (app.utils.file_handler)
logger = logging.getLogger(__name__)

# Function to get base data directory (centralized)
def get_data_dir():
    """Returns the absolute path to the Data directory."""
    # os.getcwd() might be ambiguous depending on where the script is run from.
    # It's safer to get the directory of *this* file and go up.
    # current_dir = os.path.dirname(os.path.abspath(__file__))
    # project_root = os.path.dirname(os.path.dirname(current_dir)) # Go up two levels (from utils -> app -> project_root)
    # For simplicity if running from project root is assumed:
    project_root = os.getcwd()
    return os.path.join(project_root, "Data")

def _ensure_dir_exists(path: str):
    """Ensures a directory exists, creating it if necessary. Logs errors."""
    try:
        os.makedirs(path, exist_ok=True)
    except OSError as e:
        logger.error(f"Failed to create directory {path}: {e}")
        # Depending on severity, you might want to raise the exception
        # raise

def save_webhook_data(data: dict) -> str:
    """
    Saves the raw webhook data as a JSON file in the Data directory.
    File name: raw_row_<row_number>.json
    Returns the file path or an empty string on failure.
    """
    sid = data.get("sid")
    row_number = data.get("row_number")
    if not sid or row_number is None:
        logger.error("Cannot save raw webhook data: SID or row_number missing.")
        return ""

    try:
        sid_folder_path = os.path.join(get_data_dir(), str(sid)) # Ensure sid is string
        _ensure_dir_exists(sid_folder_path)

        file_name = f"raw_row_{row_number}.json"
        file_path = os.path.join(sid_folder_path, file_name)

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        logger.debug(f"Raw webhook data saved to {file_path}")
        return file_path
    except Exception as e:
        logger.error(f"Error saving raw webhook data for SID {sid}, Row {row_number}: {e}", exc_info=True)
        return ""

def save_metadata(sid: str, metadata: dict):
    """
    Saves search metadata for a given SID as metadata.json in the Data/<sid>/ directory.
    """
    if not sid:
        logger.error("Cannot save metadata: SID missing.")
        return
    if not isinstance(metadata, dict):
         logger.error(f"Cannot save metadata: metadata is not a dictionary (type: {type(metadata)}) for SID {sid}.")
         return

    try:
        sid_folder_path = os.path.join(get_data_dir(), str(sid))
        _ensure_dir_exists(sid_folder_path)

        metadata_path = os.path.join(sid_folder_path, "metadata.json")

        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=4)
        logger.debug(f"Metadata saved to {metadata_path}")
    except Exception as e:
        logger.error(f"Error saving metadata for SID {sid} to {metadata_path}: {e}", exc_info=True)


def clean_and_save_analysis(sid: str, row_number: int, analysis_result: str) -> str:
    """
    Cleans the analysis result (removes <think> blocks), extracts valid JSON
    from Markdown code blocks (```json ... ```), and saves it.
    Falls back to saving the cleaned text if JSON extraction/parsing fails.
    Saves analysis to Data/<sid>/analysis_row_<row_number>.json
    Saves <think> blocks to Data/<sid>/think_row_<row_number>.txt
    Returns the path to the saved analysis file or an empty string on failure.
    """
    if not sid or row_number is None:
        logger.error("Cannot save analysis: SID or row_number missing.")
        return ""
    if not isinstance(analysis_result, str):
         logger.error(f"Cannot save analysis: analysis_result is not a string (type: {type(analysis_result)}) for SID {sid}, Row {row_number}.")
         return ""

    analysis_json = None # Initialize

    try:
        sid_folder_path = os.path.join(get_data_dir(), str(sid))
        _ensure_dir_exists(sid_folder_path)

        # 1. Handle <think> blocks
        think_pattern = re.compile(r"<think>(.*?)</think>", re.DOTALL)
        think_matches = think_pattern.findall(analysis_result)
        cleaned_result = think_pattern.sub("", analysis_result).strip()

        if think_matches:
            think_path = os.path.join(sid_folder_path, f"think_row_{row_number}.txt")
            try:
                with open(think_path, "w", encoding="utf-8") as f:
                    # Save each think block separated by a clear marker
                    f.write("\n\n---\n\n".join(m.strip() for m in think_matches))
                logger.debug(f"Think content saved to {think_path}")
            except Exception as e:
                logger.error(f"Error saving think text to {think_path}: {e}", exc_info=True)
                # Continue processing even if saving think fails

        # 2. Attempt to extract and parse JSON from ```json block
        json_pattern = re.compile(r"```json\s*(.*?)\s*```", re.DOTALL)
        json_match = json_pattern.search(cleaned_result)

        if json_match:
            extracted_json_text = json_match.group(1).strip()
            if not extracted_json_text:
                 logger.warning(f"Found empty ```json block for SID {sid}, Row {row_number}.")
                 # Fall through to try parsing the whole cleaned_result or save as text
            else:
                try:
                    analysis_json = json.loads(extracted_json_text)
                    logger.info(f"Successfully parsed JSON from Markdown block for SID {sid}, Row {row_number}.")
                except json.JSONDecodeError as e:
                    # Log the error and the problematic text
                    logger.error(f"JSONDecodeError parsing ```json block for SID {sid}, Row {row_number}. Error: {e}. Problematic Text (first 500 chars): {extracted_json_text[:500]}")
                    # Fallback: Store the problematic text itself for manual inspection
                    analysis_json = {
                        "error": f"Invalid JSON format extracted from triple backticks: {e}",
                        "extracted_text": extracted_json_text
                    }
        else:
             logger.warning(f"Could not find ```json block in Ollama response for SID {sid}, Row {row_number}. Attempting to parse whole response or saving as text.")
             # Fall through: analysis_json is still None

        # 3. Fallback: If no valid JSON extracted, try parsing the whole cleaned result or save as text
        if analysis_json is None:
            try:
                # Attempt to parse the entire cleaned string directly
                analysis_json = json.loads(cleaned_result)
                logger.info(f"Successfully parsed the entire cleaned response as JSON for SID {sid}, Row {row_number}.")
            except json.JSONDecodeError:
                # Final fallback: store the cleaned_result as plain text within a JSON structure
                logger.warning(f"Could not parse entire cleaned response as JSON for SID {sid}, Row {row_number}. Saving as analysis_text.")
                analysis_json = {"analysis_text": cleaned_result}

        # 4. Save the final JSON (either parsed or fallback structure)
        analysis_file_name = f"analysis_row_{row_number}.json"
        analysis_path = os.path.join(sid_folder_path, analysis_file_name)

        with open(analysis_path, "w", encoding="utf-8") as f:
            json.dump(analysis_json, f, ensure_ascii=False, indent=4)
        logger.debug(f"Analysis JSON structure saved to {analysis_path}")
        return analysis_path

    except Exception as e:
        # Catch any unexpected errors during the process
        logger.error(f"Unexpected error in clean_and_save_analysis for SID {sid}, Row {row_number}: {e}", exc_info=True)
        return "" # Indicate failure
