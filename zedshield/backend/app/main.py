import os
import json
import uuid
from datetime import datetime
from fastapi import FastAPI, Depends, HTTPException, Security, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional, List
from dotenv import load_dotenv
import httpx

from .db import (
    supabase, create_event, list_cases, get_case, 
    get_case_with_event, update_case_status, create_case,
    create_demo_request
)
from .features import compute_live_features
from .scoring import score_event

load_dotenv()

RISK_THRESHOLD = float(os.getenv("RISK_THRESHOLD", "0.5"))
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

app = FastAPI(title="ZedShield API")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer()

# ===== Auth Helper =====
async def verify_token(credentials: HTTPAuthorizationCredentials = Security(security)):
    """Verify Supabase JWT token."""
    token = credentials.credentials
    
    try:
        headers = {
            "Authorization": f"Bearer {token}",
            "apikey": SUPABASE_KEY,
        }
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{SUPABASE_URL}/auth/v1/user",
                headers=headers
            )
            if response.status_code != 200:
                raise HTTPException(status_code=401, detail="Invalid token")
            user = response.json()
            return user
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Authentication failed: {str(e)}")

async def get_current_user(token_data = Depends(verify_token)):
    """Get current user from token."""
    return token_data

# ===== WebSocket =====
class ConnectionManager:
    def __init__(self):
        self.active: list[WebSocket] = []
    
    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)
    
    def disconnect(self, ws: WebSocket):
        if ws in self.active:
            self.active.remove(ws)
    
    async def broadcast(self, message: dict):
        dead = []
        for ws in self.active:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

manager = ConnectionManager()

# ===== Models =====
class IncomingEvent(BaseModel):
    event_id: Optional[str] = None
    account_id: str
    counterparty_id: str
    amount: float
    currency: str = "ZMW"
    channel: str = "mobile_money"
    timestamp: Optional[datetime] = None

class CaseAction(BaseModel):
    action: str  # escalate, review, clear

class DemoRequest(BaseModel):
    name: str
    email: str
    company: Optional[str] = None
    message: Optional[str] = None

# ===== Endpoints =====

@app.websocket("/ws/dashboard")
async def dashboard_ws(websocket: WebSocket):
    """WebSocket for real-time case updates."""
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.post("/events/ingest")
async def ingest_event(evt: IncomingEvent):
    """Ingest a transaction event for scoring - NO AUTH REQUIRED for demo."""
    event_id = evt.event_id or str(uuid.uuid4())
    timestamp = evt.timestamp or datetime.utcnow()
    
    # Compute features
    features = compute_live_features(
        evt.account_id,
        evt.counterparty_id,
        evt.amount,
        timestamp
    )
    
    # Score
    result = score_event(features, threshold=RISK_THRESHOLD)
    
    # Save event
    event_data = {
        "event_id": event_id,
        "account_id": evt.account_id,
        "counterparty_id": evt.counterparty_id,
        "amount": evt.amount,
        "currency": evt.currency,
        "channel": evt.channel,
        "timestamp": timestamp.isoformat(),
        "risk_score": result["risk_score"],
        "threshold_breached": result["threshold_breached"],
    }
    create_event(event_data)
    
    case_payload = None
    if result["threshold_breached"]:
        case_data = {
            "event_id": event_id,
            "account_id": evt.account_id,
            "risk_score": result["risk_score"],
            "reason_codes": json.dumps(result["reason_codes"]),
            "status": "flagged",
        }
        case = create_case(case_data)
        case_payload = {
            "case_id": case["case_id"],
            "account_id": case["account_id"],
            "risk_score": case["risk_score"],
            "reason_codes": result["reason_codes"],
            "status": case["status"],
            "created_at": case["created_at"],
        }
    
    if case_payload:
        await manager.broadcast({"type": "new_case", "case": case_payload})
    
    return {
        "event_id": event_id,
        "risk_score": result["risk_score"],
        "threshold_breached": result["threshold_breached"],
        "reason_codes": result["reason_codes"],
    }

@app.get("/cases")
async def list_cases_endpoint(
    status: Optional[str] = None,
    limit: int = 200,
    user = Depends(get_current_user)
):
    """List cases, optionally filtered by status."""
    cases = list_cases(status, limit)
    
    result = []
    for c in cases:
        event = supabase.table('events').select('*').eq('event_id', c['event_id']).execute()
        event_data = event.data[0] if event.data else None
        
        result.append({
            "case_id": c["case_id"],
            "account_id": c["account_id"],
            "risk_score": c["risk_score"],
            "reason_codes": json.loads(c["reason_codes"]) if c["reason_codes"] else [],
            "status": c["status"],
            "created_at": c["created_at"],
            "event": {
                "counterparty_id": event_data.get("counterparty_id") if event_data else None,
                "amount": event_data.get("amount") if event_data else None,
                "channel": event_data.get("channel") if event_data else None,
                "timestamp": event_data.get("timestamp") if event_data else None,
            } if event_data else None,
        })
    return result

@app.get("/cases/{case_id}")
async def get_case_endpoint(
    case_id: str,
    user = Depends(get_current_user)
):
    """Get a single case by ID."""
    case = get_case_with_event(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    
    return {
        "case_id": case["case_id"],
        "account_id": case["account_id"],
        "risk_score": case["risk_score"],
        "reason_codes": json.loads(case["reason_codes"]) if case["reason_codes"] else [],
        "status": case["status"],
        "created_at": case["created_at"],
        "event": {
            "counterparty_id": case.get("events", {}).get("counterparty_id"),
            "amount": case.get("events", {}).get("amount"),
            "currency": case.get("events", {}).get("currency"),
            "channel": case.get("events", {}).get("channel"),
            "timestamp": case.get("events", {}).get("timestamp"),
        } if case.get("events") else None,
    }

@app.post("/cases/{case_id}/action")
async def act_on_case(
    case_id: str,
    action: CaseAction,
    user = Depends(get_current_user)
):
    """Take action on a case (escalate, clear, review)."""
    status_map = {
        "escalate": "escalated",
        "clear": "cleared",
        "review": "under_review"
    }
    new_status = status_map.get(action.action)
    if not new_status:
        raise HTTPException(status_code=400, detail="Invalid action")
    
    case = update_case_status(case_id, new_status, user.get("id"))
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    
    await manager.broadcast({
        "type": "case_updated",
        "case_id": case_id,
        "status": new_status
    })
    
    return {"case_id": case_id, "status": new_status}

@app.post("/demo-request")
async def demo_request(request: DemoRequest):
    """Handle demo request from landing page."""
    data = request.dict()
    result = create_demo_request(data)
    return {"status": "ok", "message": "Demo request received"}

@app.get("/health")
async def health():
    return {"status": "ok", "supabase": "connected"}

@app.get("/me")
async def get_me(user = Depends(get_current_user)):
    """Get current user info."""
    return {"user": user}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)