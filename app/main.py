# app/main.py

import logging
import os
import asyncio
import uvicorn
from fastapi import FastAPI, Request
from dotenv import load_dotenv

# Load .env before importing modules that depend on it
load_dotenv()

from app.api import webhook
from app.processing import queue_manager, worker

# --- Configuration ---
PORT = int(os.getenv("PORT", 8001))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper() # Allow setting log level via env

# --- Logging Setup ---
# Ensure log level is valid
numeric_level = getattr(logging, LOG_LEVEL, None)
if not isinstance(numeric_level, int):
    numeric_level = logging.INFO # Default to INFO if invalid level set

logging.basicConfig(
    level=numeric_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
# Lower uvicorn logs if our level is DEBUG, otherwise let them be default (INFO)
uvicorn_log_level = "debug" if numeric_level <= logging.DEBUG else "info"

# --- FastAPI App Setup ---
app = FastAPI(title="Webhook Processor Service")

# --- Middleware ---
@app.middleware("http")
async def log_requests(request: Request, call_next):
    # Log basic request info
    logging.debug(f"Request: {request.method} {request.url} from {request.client.host}")
    try:
        # Optionally log headers or body (be careful with sensitive data)
        # body = await request.body()
        # logging.debug(f"Request Body: {body.decode()}")
        # await request._insert_body(body) # Need to re-insert body if read
        pass
    except Exception as e:
         logging.warning(f"Could not log request body: {e}")

    response = await call_next(request)
    # Log basic response info
    logging.debug(f"Response: {response.status_code}")
    return response

# --- API Routers ---
app.include_router(webhook.router, prefix="/api/v1") # Add a version prefix

# --- Background Tasks ---
worker_task = None

@app.on_event("startup")
async def startup_event():
    """Initialize queue and start background worker."""
    global worker_task
    logging.info("Application startup...")
    queue_manager.initialize_queue() # Load disk queue into memory queue
    worker_task = asyncio.create_task(worker.run_worker())
    logging.info("Background worker started.")

@app.on_event("shutdown")
async def shutdown_event():
    """Gracefully shutdown the background worker."""
    logging.info("Application shutdown...")
    if worker_task:
        logging.info("Attempting to cancel worker task...")
        worker_task.cancel()
        try:
            await asyncio.wait_for(worker_task, timeout=10.0) # Wait max 10s
        except asyncio.CancelledError:
            logging.info("Worker task successfully cancelled.")
        except asyncio.TimeoutError:
            logging.warning("Worker task did not finish cancelling within timeout.")
        except Exception as e:
             logging.error(f"Error during worker task shutdown: {e}", exc_info=True)
    # Save queue state one last time? Might not be necessary if saved on add/remove
    # queue_manager.save_disk_queue()
    logging.info("Shutdown complete.")

# --- Root endpoint for health check ---
@app.get("/", tags=["Health Check"])
async def read_root():
    return {"status": "OK", "message": "Webhook Processor is running"}

# --- Main execution ---
if __name__ == "__main__":
    print(f"Starting server on http://0.0.0.0:{PORT}")
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=PORT,
        reload=True, # Reload True is good for development
        log_level=uvicorn_log_level # Control uvicorn's verbosity
    )
