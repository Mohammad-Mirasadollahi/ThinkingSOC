# app/processing/worker.py
import asyncio
import logging
import json # For formatting data passed to Ollama

from app.processing import queue_manager
from app.external import ollama_client
from app.utils import file_handler

# Get a logger instance for this module
logger = logging.getLogger(__name__)

# --- CHANGE HERE: Remove 'async' ---
def process_single_item(data: dict) -> bool: # Return bool for success/failure
    """Processes a single webhook data item synchronously. Intended for asyncio.to_thread."""
    sid = data.get("sid")
    row_number = data.get("row_number")
    queue_num = data.get('queue_number', 'N/A') # Get queue number for logging

    if not sid or row_number is None:
        logger.error(f"Worker (sync): Invalid data received, missing SID or row_number: {data}")
        return False # Indicate failure

    logger.info(f"Worker (sync): Starting processing for Queue# {queue_num} - SID: {sid}, Row: {row_number}")

    # 1. Save raw data (optional, but good for debugging)
    # file_handler.save_webhook_data(data) # Keep commented unless needed

    # 2. Save Metadata
    try:
        file_handler.save_metadata(sid, {
            "search_name": data.get("search_name"),
            "search_query": data.get("search_query"),
            "description": data.get("description"),
            "severity": data.get("severity"),
            "kill_chain": data.get("kill_chain"),
            "mitre_tactics": data.get("mitre_tactics", []),
            "mitre_techniques": data.get("mitre_techniques", [])
        })
        logger.debug(f"Worker (sync): Metadata saved for SID {sid}.")
    except Exception as e:
        logger.error(f"Worker (sync): Failed to save metadata for SID {sid}: {e}", exc_info=True)
        return False # Indicate failure

    # 3. Prepare data and call Ollama
    data_for_ollama = data.get("row_data", {}) # Use row_data if available
    data_for_ollama.update({
         k: v for k, v in data.items()
         if k not in ['row_data', 'queue_number', 'received_at']
    })
    logger.debug(f"Worker (sync): Prepared data for Ollama for SID {sid}, Row {row_number}.")

    analysis_result_text = "" # Initialize
    try:
        logger.info(f"Worker (sync): Calling Ollama client for SID {sid}, Row {row_number}...")
        # This call is blocking and runs within the thread managed by asyncio.to_thread
        analysis_result_text = ollama_client.generate_analysis(data_for_ollama)
        logger.info(f"Worker (sync): Received result from Ollama client for SID {sid}, Row {row_number}.")
        logger.debug(f"Worker (sync): Ollama result type: {type(analysis_result_text)}, Length: {len(analysis_result_text) if isinstance(analysis_result_text, str) else 'N/A'}")

        # Check if Ollama returned an error string
        if isinstance(analysis_result_text, str) and analysis_result_text.startswith("Error:"):
             logger.error(f"Worker (sync): Ollama analysis failed for SID {sid}, Row {row_number}. Reason from client: {analysis_result_text}")
             return False # Indicate failure

    except Exception as e:
        # This catches errors if generate_analysis itself raises an unhandled exception
        logger.error(f"Worker (sync): Unexpected error calling Ollama client function for SID {sid}, Row {row_number}: {e}", exc_info=True)
        return False # Indicate failure

    # 4. Clean and Save Analysis Result
    try:
        logger.debug(f"Worker (sync): Attempting to clean and save analysis for SID {sid}, Row {row_number}.")
        saved_path = file_handler.clean_and_save_analysis(sid, row_number, analysis_result_text)
        if saved_path:
            logger.info(f"Worker (sync): Successfully processed and saved analysis for SID {sid}, Row {row_number} to {saved_path}")
            return True # Indicate success
        else:
            # clean_and_save_analysis should log its own errors, but we add one here too
            logger.error(f"Worker (sync): Failed to save analysis (clean_and_save_analysis returned empty path) for SID {sid}, Row {row_number}.")
            return False # Indicate failure
    except Exception as e:
         logger.error(f"Worker (sync): Error during clean/save analysis step for SID {sid}, Row {row_number}: {e}", exc_info=True)
         return False # Indicate failure


async def run_worker():
    """Continuously fetches items from the queue and processes them."""
    logger.info("Worker started, waiting for items...")
    while True:
        try:
            item_data = await queue_manager.processing_queue.get()
            sid = item_data.get('sid', 'N/A')
            row = item_data.get('row_number', 'N/A')
            logger.info(f"Worker: Dequeued item SID {sid}, Row {row}. Starting processing in thread.")

            processing_successful = False # Default to False
            try:
                # Run the NOW SYNCHRONOUS process_single_item in a separate thread
                # It should return True on success, False on failure
                processing_successful = await asyncio.to_thread(process_single_item, item_data)
                logger.info(f"Worker: Processing thread finished for SID {sid}, Row {row}. Success: {processing_successful}")

            except Exception as e:
                # Catch errors if asyncio.to_thread itself fails or the function raises an unexpected Exception
                logger.error(f"Worker: Unhandled exception during to_thread execution for item SID {sid}, Row {row}: {e}", exc_info=True)
                processing_successful = False # Ensure it's marked as failed

            finally:
                queue_manager.processing_queue.task_done()
                logger.debug(f"Worker: Task marked done for item SID {sid}, Row {row}.")

                # Now check the actual result before removing from mirror
                if processing_successful:
                    logger.info(f"Worker: Processing deemed successful for SID {sid}, Row {row}. Removing from disk mirror.")
                    queue_manager.remove_item_from_mirror(item_data)
                else:
                     logger.warning(f"Worker: Processing failed or deemed unsuccessful for item SID {sid}/Row {row}. Item potentially remains in disk queue.")


        except asyncio.CancelledError:
            logger.info("Worker cancellation requested.")
            break
        except Exception as e:
            # Catch errors related to getting from queue etc.
            logger.error(f"Worker loop error: {e}", exc_info=True)
            await asyncio.sleep(5) # Avoid tight loop on unexpected errors

    logger.info("Worker stopped.")
