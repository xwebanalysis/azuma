from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class FormFieldRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: Optional[str] = None
    input_type: Optional[str] = None
    value: Optional[str] = None
    required: bool = False
    autocomplete: Optional[str] = None
    placeholder: Optional[str] = None
    is_csrf: bool = False


class FormRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    page_url: Optional[str] = None
    action: Optional[str] = None
    method: str = "GET"
    enctype: Optional[str] = None
    is_secure: bool = False
    redirect_chain: Optional[str] = None
    fields: List[FormFieldRead] = []


class OAuthFlowRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    endpoint: Optional[str] = None
    flow_type: Optional[str] = None
    client_id: Optional[str] = None
    redirect_uri: Optional[str] = None
    scope: Optional[str] = None
    uses_state: bool = False
    weakness: Optional[str] = None


class SessionCookieRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: Optional[str] = None
    value_preview: Optional[str] = None
    domain: Optional[str] = None
    path: Optional[str] = None
    http_only: bool = False
    secure: bool = False
    same_site: Optional[str] = None
    max_age: Optional[str] = None


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
    oauth_flows: List[OAuthFlowRead] = []
    session_cookies: List[SessionCookieRead] = []


class DiscoverRequest(BaseModel):
    target: str


class DiscoverResponse(BaseModel):
    analysis: FormAnalysisRead
    form_count: int
    oauth_flow_count: int
    session_cookie_count: int
