import os
from supabase import create_client, Client
from typing import Optional, Dict, Any, List
from datetime import datetime
import json
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")  # Service role key for backend

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_db():
    """Dependency for FastAPI - returns the supabase client."""
    return supabase

# ===== Event Operations =====
def create_event(event_data: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new event record."""
    result = supabase.table('events').insert(event_data).execute()
    return result.data[0] if result.data else None

# ===== Case Operations =====
def list_cases(status: Optional[str] = None, limit: int = 200) -> List[Dict]:
    """List cases with optional status filter."""
    query = supabase.table('cases').select('*')
    if status:
        query = query.eq('status', status)
    result = query.order('created_at', desc=True).limit(limit).execute()
    return result.data or []

def get_case(case_id: str) -> Optional[Dict]:
    """Get a single case by ID."""
    result = supabase.table('cases').select('*').eq('case_id', case_id).execute()
    return result.data[0] if result.data else None

def get_case_with_event(case_id: str) -> Optional[Dict]:
    """Get a case with its associated event."""
    result = supabase.table('cases').select('*, events(*)').eq('case_id', case_id).execute()
    return result.data[0] if result.data else None

def update_case_status(case_id: str, status: str, user_id: Optional[str] = None) -> Dict:
    """Update a case's status."""
    data = {
        'status': status,
        'updated_at': datetime.utcnow().isoformat()
    }
    if user_id:
        data['assigned_to'] = user_id
    
    result = supabase.table('cases').update(data).eq('case_id', case_id).execute()
    return result.data[0] if result.data else None

def create_case(case_data: Dict[str, Any]) -> Dict:
    """Create a new case."""
    result = supabase.table('cases').insert(case_data).execute()
    return result.data[0] if result.data else None

# ===== Demo Requests =====
def create_demo_request(data: Dict[str, Any]) -> Dict:
    """Create a demo request."""
    result = supabase.table('demo_requests').insert(data).execute()
    return result.data[0] if result.data else None

# ===== Real-time =====
def subscribe_to_cases(callback):
    """Subscribe to real-time case updates."""
    return supabase.table('cases').on('*', callback).subscribe()