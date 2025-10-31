from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class AutoCountIn(BaseModel):
    timestamp: datetime
    source: str
    camera_name: Optional[str] = None
    count_type: str
    count_value: int
    meta_json: Optional[str] = None

class AutoCountOut(AutoCountIn):
    id: int

class CountsQuery(BaseModel):
    type: str
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
