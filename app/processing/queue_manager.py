# app/processing/queue_manager.py

import asyncio
import json
import os
import logging
from typing import List, Dict, Any

# Queue for active processing
processing_queue = asyncio.Queue()

# On-disk persistence
PENDING_QUEUE_FILE = "pending_queue.json"
# This list mirrors the items intended for the queue on disk
# It's loaded at startup and saved whenever the queue state changes logically
_disk_queue_mirror: List[Dict[str, Any]] = []

def load_disk_queue() -> List[dict]:
    """Loads the pending items list from the JSON file."""
    if os.path.exists(PENDING_QUEUE_FILE):
        try:
            with open(PENDING_QUEUE_FILE, "r", encoding="utf-8") as f:
                content = f.read()
                if content: # Check if file is not empty
                    loaded_data = json.loads(content)
                    if isinstance(loaded_data, list):
                        logging.info(f"Loaded {len(loaded_data)} items from {PENDING_QUEUE_FILE}")
                        return loaded_data
                    else:
                        logging.warning(f"Content in {PENDING_QUEUE_FILE} is not a list. Ignoring.")
                        return []
                else:
                    logging.info(f"{PENDING_QUEUE_FILE} is empty.")
                    return []
        except json.JSONDecodeError as e:
            logging.error(f"Error decoding JSON from {PENDING_QUEUE_FILE}: {e}. Starting with empty queue.")
            # Optional: Backup corrupted file?
            return []
        except Exception as e:
            logging.error(f"Error loading disk queue from {PENDING_QUEUE_FILE}: {e}")
            return []
    else:
        logging.info(f"{PENDING_QUEUE_FILE} not found. Starting with empty queue.")
        return []

def save_disk_queue():
    """Saves the current state of the disk queue mirror to the JSON file."""
    try:
        with open(PENDING_QUEUE_FILE, "w", encoding="utf-8") as f:
            json.dump(_disk_queue_mirror, f, indent=2)
        logging.debug(f"Saved {len(_disk_queue_mirror)} items to {PENDING_QUEUE_FILE}")
    except Exception as e:
        logging.error(f"Error saving disk queue to {PENDING_QUEUE_FILE}: {e}")

async def add_item(item: Dict[str, Any]):
    """Adds an item to the processing queue and the disk mirror, then saves."""
    if not isinstance(item, dict):
         logging.warning(f"Attempted to add non-dict item to queue: {type(item)}")
         return

    # Add to in-memory queue for processing
    await processing_queue.put(item)

    # Add to disk mirror and save
    # Ensure no duplicates in the mirror based on a unique key if necessary
    # Simple append for now:
    _disk_queue_mirror.append(item)
    save_disk_queue()
    logging.info(f"Item SID: {item.get('sid')}/Row: {item.get('row_number')} added to queue (Queue size: {processing_queue.qsize()}, Disk mirror size: {len(_disk_queue_mirror)})")

def remove_item_from_mirror(item_to_remove: Dict[str, Any]):
    """Removes a successfully processed item from the disk mirror list and saves."""
    global _disk_queue_mirror
    # Identify item uniquely (e.g., by SID and row_number)
    sid = item_to_remove.get("sid")
    row = item_to_remove.get("row_number")
    initial_len = len(_disk_queue_mirror)

    _disk_queue_mirror = [
        item for item in _disk_queue_mirror
        if not (item.get("sid") == sid and item.get("row_number") == row)
    ]

    if len(_disk_queue_mirror) < initial_len:
        save_disk_queue()
        logging.info(f"Item SID: {sid}/Row: {row} removed from disk mirror.")
    else:
         logging.warning(f"Could not find item SID: {sid}/Row: {row} in disk mirror for removal.")


def initialize_queue():
    """Loads the disk queue and populates the in-memory queue at startup."""
    global _disk_queue_mirror
    _disk_queue_mirror = load_disk_queue()
    count = 0
    for item in _disk_queue_mirror:
        # No await needed here, just putting into asyncio Queue constructor context
        processing_queue.put_nowait(item)
        count += 1
    logging.info(f"Initialized in-memory queue with {count} items from disk.")
