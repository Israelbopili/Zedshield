#!/usr/bin/env python3
"""
ZedShield Data Simulator
Generates synthetic transaction data with fraud patterns.
"""

import argparse
import sqlite3
import random
import uuid
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

# ===== Configuration =====
ACCOUNTS = [f"ZED{random.randint(1000,9999)}" for _ in range(100)]
COUNTERPARTIES = [f"CP{random.randint(100,999)}" for _ in range(200)]
CHANNELS = ['mobile_money', 'bank_transfer', 'airtime', 'bill_payment']

def generate_event(account_id, timestamp, is_fraud=False):
    """Generate a single transaction event."""
    counterparty = random.choice(COUNTERPARTIES)
    
    # Normal amounts: mostly small, some medium
    if is_fraud:
        # Fraud: larger amounts, more variation
        amount = random.uniform(2000, 50000)
    else:
        amount = random.uniform(10, 5000)
    
    return {
        'event_id': str(uuid.uuid4()),
        'account_id': account_id,
        'counterparty_id': counterparty,
        'amount': round(amount, 2),
        'currency': 'ZMW',
        'channel': random.choice(CHANNELS),
        'timestamp': timestamp.isoformat(),
        'is_fraud': 1 if is_fraud else 0,
    }

def generate_fraud_patterns(events, fraud_rate=0.02):
    """Inject fraud patterns into the event stream."""
    fraud_events = []
    
    # Pattern 1: Velocity (many transactions from one account)
    for _ in range(int(len(events) * fraud_rate * 0.3)):
        acc = random.choice(ACCOUNTS)
        base_time = datetime.now() - timedelta(hours=random.randint(1, 24))
        for i in range(random.randint(5, 15)):
            ts = base_time + timedelta(minutes=random.randint(1, 10))
            fraud_events.append(generate_event(acc, ts, is_fraud=True))
    
    # Pattern 2: Structuring (multiple transactions just below reporting threshold)
    threshold = 5000
    for _ in range(int(len(events) * fraud_rate * 0.25)):
        acc = random.choice(ACCOUNTS)
        base_time = datetime.now() - timedelta(hours=random.randint(1, 48))
        for i in range(random.randint(3, 8)):
            ts = base_time + timedelta(minutes=random.randint(5, 30))
            amount = random.uniform(threshold * 0.7, threshold * 0.95)
            fraud_events.append(generate_event(acc, ts, is_fraud=True))
    
    # Pattern 3: Mule account (many counterparties)
    for _ in range(int(len(events) * fraud_rate * 0.2)):
        acc = random.choice(ACCOUNTS)
        base_time = datetime.now() - timedelta(hours=random.randint(1, 12))
        for i in range(random.randint(5, 12)):
            ts = base_time + timedelta(minutes=random.randint(1, 5))
            fraud_events.append(generate_event(acc, ts, is_fraud=True))
    
    # Pattern 4: Dormant reactivation
    for _ in range(int(len(events) * fraud_rate * 0.15)):
        acc = random.choice(ACCOUNTS)
        ts = datetime.now() - timedelta(days=random.randint(7, 30))
        amount = random.uniform(1000, 20000)
        fraud_events.append({
            'event_id': str(uuid.uuid4()),
            'account_id': acc,
            'counterparty_id': random.choice(COUNTERPARTIES),
            'amount': round(amount, 2),
            'currency': 'ZMW',
            'channel': random.choice(CHANNELS),
            'timestamp': ts.isoformat(),
            'is_fraud': 1,
        })
    
    # Mix fraud events with normal events
    all_events = events + fraud_events
    
    # Sort by timestamp
    all_events.sort(key=lambda x: x['timestamp'])
    
    return all_events

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--events', type=int, default=5000, help='Number of events to generate')
    parser.add_argument('--fraud-rate', type=float, default=0.02, help='Fraud rate (0-1)')
    parser.add_argument('--db', default='zedshield_sim.db', help='Output SQLite database')
    args = parser.parse_args()
    
    print(f"Generating {args.events} events with {args.fraud_rate*100:.1f}% fraud rate...")
    
    # Generate normal events
    normal_count = int(args.events * (1 - args.fraud_rate))
    events = []
    
    # Generate events over the last 30 days
    end_time = datetime.now()
    start_time = end_time - timedelta(days=30)
    
    for i in range(normal_count):
        # Most accounts have regular activity, some are less active
        account = random.choice(ACCOUNTS)
        timestamp = start_time + timedelta(seconds=random.uniform(0, (end_time - start_time).total_seconds()))
        events.append(generate_event(account, timestamp, is_fraud=False))
    
    # Add fraud patterns
    events = generate_fraud_patterns(events, args.fraud_rate)
    
    # Create DataFrame
    df = pd.DataFrame(events)
    
    # Save to SQLite
    conn = sqlite3.connect(args.db)
    df.to_sql('events', conn, if_exists='replace', index=False)
    conn.close()
    
    fraud_count = df['is_fraud'].sum()
    print(f"Generated {len(df)} events ({fraud_count} fraudulent, {fraud_count/len(df)*100:.1f}%)")
    print(f"Saved to {args.db}")
    
    # Also save answer key
    answer_key = df[['event_id', 'is_fraud']].to_dict('records')
    import json
    with open('answer_key.json', 'w') as f:
        json.dump(answer_key, f)
    print("Answer key saved to answer_key.json")

if __name__ == '__main__':
    main()