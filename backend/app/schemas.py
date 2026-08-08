from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class FormFieldRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: Optional[str] = None
    input_type: Optional[str] = None
    required: bool = False
    autocomplete: Optional[str] = None
    placeholder: Optional[str] = None


class FormRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    page_url: Optional[str] = None
    action: Optional[str] = None
    method: str = "GET"
    enctype: Optional[str] = None
    is_secure: bool = False
    fields: List[FormFieldRead] = []


class FormAnalysisRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    target: str
    status: str
    analysis_type: str
    created_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    error_message: Optional[str] = None
    forms: List[FormRead] = []


class DiscoverRequest(BaseModel):
    target: str


class DiscoverResponse(BaseModel):
    analysis: FormAnalysisRead
    form_count: int
