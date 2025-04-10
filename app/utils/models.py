# app/utils/models.py
from pydantic import BaseModel
from typing import List, Dict, Any

class WebhookData(BaseModel):
    sid: str
    search_name: str
    search_query: str
    description: str
    severity: str
    kill_chain: str
    mitre_tactics: List[str]
    mitre_techniques: List[str]
    row_number: int
    row_data: Dict[str, Any]
