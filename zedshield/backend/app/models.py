from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID, uuid4

class EventCreate(BaseModel):
    account_id: str
    counterparty_id: str
    amount: float
    currency: str = "ZMW"
    channel: str = "mobile_money"
    timestamp: Optional[datetime] = None
    event_id: Optional[str] = None

class EventResponse(BaseModel):
    event_id: str
    account_id: str
    counterparty_id: str
    amount: float
    currency: str
    channel: str
    timestamp: datetime
    risk_score: float
    threshold_breached: bool
    created_at: datetime

class CaseCreate(BaseModel):
    event_id: str
    account_id: str
    risk_score: float
    reason_codes: List[str] = []
    status: str = "flagged"
    assigned_to: Optional[str] = None

class CaseResponse(BaseModel):
    case_id: str
    event_id: str
    account_id: str
    risk_score: float
    reason_codes: List[str]
    status: str
    assigned_to: Optional[str]
    created_at: datetime
    updated_at: datetime
    event: Optional[EventResponse] = None

class CaseAction(BaseModel):
    action: str  # escalate, review, clear

class DemoRequest(BaseModel):
    name: str
    email: str
    company: Optional[str] = None
    message: Optional[str] = None

class ScoringResult(BaseModel):
    risk_score: float
    threshold_breached: bool
    reason_codes: List[str]