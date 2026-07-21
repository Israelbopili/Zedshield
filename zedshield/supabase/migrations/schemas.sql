-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Events table
CREATE TABLE IF NOT EXISTS events (
    event_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    account_id TEXT NOT NULL,
    counterparty_id TEXT NOT NULL,
    amount DECIMAL(12,2) NOT NULL,
    currency TEXT DEFAULT 'ZMW',
    channel TEXT DEFAULT 'mobile_money',
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    risk_score DECIMAL(5,4) DEFAULT 0,
    threshold_breached BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by UUID REFERENCES auth.users(id)
);

-- Cases table
CREATE TABLE IF NOT EXISTS cases (
    case_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_id UUID REFERENCES events(event_id),
    account_id TEXT NOT NULL,
    risk_score DECIMAL(5,4) NOT NULL,
    reason_codes JSONB DEFAULT '[]',
    status TEXT DEFAULT 'flagged',  -- flagged, under_review, escalated, cleared
    assigned_to UUID REFERENCES auth.users(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Demo requests table
CREATE TABLE IF NOT EXISTS demo_requests (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    company TEXT,
    message TEXT,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- User profiles (extends Supabase auth.users)
CREATE TABLE IF NOT EXISTS profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id),
    full_name TEXT,
    role TEXT DEFAULT 'analyst',  -- admin, analyst, viewer
    company TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes
CREATE INDEX idx_events_account_id ON events(account_id);
CREATE INDEX idx_events_timestamp ON events(timestamp DESC);
CREATE INDEX idx_cases_account_id ON cases(account_id);
CREATE INDEX idx_cases_status ON cases(status);
CREATE INDEX idx_cases_created_at ON cases(created_at DESC);

-- Enable Row Level Security
ALTER TABLE events ENABLE ROW LEVEL SECURITY;
ALTER TABLE cases ENABLE ROW LEVEL SECURITY;
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;

-- RLS Policies

-- Events: Users can read events for cases they have access to
CREATE POLICY "Users can read events" ON events
    FOR SELECT USING (
        auth.role() = 'authenticated'
    );

-- Cases: Users can read cases
CREATE POLICY "Users can read cases" ON cases
    FOR SELECT USING (
        auth.role() = 'authenticated'
    );

-- Cases: Users can update cases (actions)
CREATE POLICY "Users can update cases" ON cases
    FOR UPDATE USING (
        auth.role() = 'authenticated'
    );

-- Cases: Insert cases (system does this)
CREATE POLICY "System can insert cases" ON cases
    FOR INSERT WITH CHECK (
        auth.role() = 'authenticated'
    );

-- Profiles: Users can read all profiles
CREATE POLICY "Users can read profiles" ON profiles
    FOR SELECT USING (
        auth.role() = 'authenticated'
    );

-- Profiles: Users can update own profile
CREATE POLICY "Users can update own profile" ON profiles
    FOR UPDATE USING (
        auth.uid() = id
    );

-- Real-time publication
ALTER PUBLICATION supabase_realtime ADD TABLE cases;
ALTER PUBLICATION supabase_realtime ADD TABLE events;