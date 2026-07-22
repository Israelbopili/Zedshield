import os
from supabase import create_client, Client

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_db():
    return supabase

# ===== Event Operations =====
def create_event(event_data: dict):
    """Create a new event record."""
    result = supabase.table('events').insert(event_data).execute()
    return result.data[0] if result.data else None

# ===== Case Operations =====
def list_cases(status: str = None, limit: int = 200):
    """List cases with optional status filter."""
    query = supabase.table('cases').select('*')
    if status:
        query = query.eq('status', status)
    result = query.order('created_at', desc=True).limit(limit).execute()
    return result.data or []

def get_case(case_id: str):
    """Get a single case by ID."""
    result = supabase.table('cases').select('*').eq('case_id', case_id).execute()
    return result.data[0] if result.data else None

def get_case_with_event(case_id: str):
    """Get a case with its associated event."""
    result = supabase.table('cases').select('*, events(*)').eq('case_id', case_id).execute()
    return result.data[0] if result.data else None

def update_case_status(case_id: str, status: str, user_id: str = None):
    """Update a case's status."""
    data = {
        'status': status,
        'updated_at': datetime.utcnow().isoformat()
    }
    if user_id:
        data['assigned_to'] = user_id
    
    result = supabase.table('cases').update(data).eq('case_id', case_id).execute()
    return result.data[0] if result.data else None

def create_case(case_data: dict):
    """Create a new case."""
    result = supabase.table('cases').insert(case_data).execute()
    return result.data[0] if result.data else None

# ===== Demo Requests =====
def create_demo_request(data: dict):
    """Create a demo request."""
    result = supabase.table('demo_requests').insert(data).execute()
    return result.data[0] if result.data else None
