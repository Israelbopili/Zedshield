#!/usr/bin/env python3
"""
Demo Replay Script
Replays simulated events through the live API in timestamp order.
"""

import argparse
import sqlite3
import time
import requests
import pandas as pd
from datetime import datetime

def replay(db_path, api_url, speed):
    """Replay events through the API."""
    conn = sqlite3.connect(db_path)
    df = pd.read_sql_query("SELECT * FROM events ORDER BY timestamp", conn)
    conn.close()
    
    print(f"Replaying {len(df)} events against {api_url} at {speed}x speed...")
    print("Press Ctrl+C to stop.\n")
    
    flagged_count = 0
    prev_time = None
    
    for idx, row in df.iterrows():
        payload = {
            "event_id": row["event_id"],
            "account_id": row["account_id"],
            "counterparty_id": row["counterparty_id"],
            "amount": float(row["amount"]),
            "currency": row["currency"],
            "channel": row["channel"],
            "timestamp": row["timestamp"],
        }
        
        try:
            resp = requests.post(f"{api_url}/events/ingest", json=payload, timeout=2)
            result = resp.json()
            
            if result.get("threshold_breached"):
                flagged_count += 1
                print(f"🚨 [{flagged_count}] FLAGGED account={row['account_id']} "
                      f"risk={result['risk_score']:.3f} reasons={result.get('reason_codes', [])}")
            else:
                # Progress indicator
                if idx % 100 == 0:
                    print(f"📊 Processed {idx+1}/{len(df)} events... {flagged_count} flagged so far")
                    
        except Exception as e:
            print(f"⚠️ Error on event {idx}: {e}")
        
        # Throttle to simulate real time
        cur_time = pd.to_datetime(row["timestamp"])
        if prev_time is not None:
            gap = (cur_time - prev_time).total_seconds() / speed
            if gap > 0:
                time.sleep(min(gap, 1.0))  # Cap to keep things moving
        prev_time = cur_time
    
    print(f"\n✅ Done! {flagged_count} events flagged out of {len(df)} processed.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="zedshield_sim.db")
    parser.add_argument("--api", default="http://localhost:8000")
    parser.add_argument("--speed", type=float, default=50, help="Time compression factor")
    args = parser.parse_args()
    
    replay(args.db, args.api, args.speed)