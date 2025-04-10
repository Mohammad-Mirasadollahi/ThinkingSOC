# app/api/webhook.py

import logging
from datetime import datetime
from typing import Union, List, Dict, Any
from fastapi import APIRouter, Body, HTTPException, Request

from app.utils.models import WebhookData
from app.processing import queue_manager

router = APIRouter()

@router.post("/webhook", status_code=202) # Use 202 Accepted for async processing
async def receive_webhook(
    request: Request, # Inject request for logging headers/IP if needed
    data: Union[WebhookData, List[WebhookData]] = Body(...)
):
    """Receives webhook data, validates, assigns queue info, and adds to queue."""
    logging.info(f"Webhook received from {request.client.host}") # Log client IP

    try:
        items_to_queue: List[Dict[str, Any]] = []
        if not isinstance(data, list):
            data = [data] # Ensure it's always a list

        # Use the current disk queue size to determine starting queue number
        # This is an approximation, might not be perfectly sequential if items are added concurrently
        # but good enough for logging/tracking.
        base_queue_number = len(queue_manager._disk_queue_mirror)

        for index, item_model in enumerate(data):
            # FastAPI validates against WebhookData here
            item_dict = item_model.dict()

            # Add queue metadata
            item_dict["queue_number"] = base_queue_number + index + 1
            item_dict["received_at"] = datetime.now().isoformat()

            items_to_queue.append(item_dict)
            logging.debug(f"Validated webhook item: SID {item_dict['sid']}, Row {item_dict['row_number']}")

        # Add all validated items to the queue
        for item_dict in items_to_queue:
             await queue_manager.add_item(item_dict) # This handles queue + disk mirror

        return {"message": f"{len(items_to_queue)} item(s) accepted and queued for processing."}

    except Exception as e:
        # Catch validation errors from Pydantic or other issues
        logging.error(f"Error processing webhook request: {e}", exc_info=True)
        raise HTTPException(
            status_code=400, # Bad request if validation fails
            detail=f"Invalid request payload or internal error: {e}"
        )
