from collections import defaultdict, deque
from datetime import timedelta
from typing import Tuple, Set
from datetime import datetime

# In-memory per-account history
_history = defaultdict(lambda: deque(maxlen=500))
_seen_counterparties = defaultdict(set)
_last_txn_time = {}

WINDOW = timedelta(hours=1)

def compute_live_features(account_id: str, counterparty_id: str, amount: float, timestamp: datetime):
    """Compute real-time features for a transaction."""
    
    history = _history[account_id]
    
    # Clean old entries (1-hour window)
    while history and (timestamp - history[0][0]) > WINDOW:
        history.popleft()
    
    # Extract recent data
    recent_amounts = [a for (_, a, _) in history]
    recent_counterparties = {cp for (_, _, cp) in history}
    
    # Feature calculations
    txn_count_1h = len(history)
    avg_amount_1h = sum(recent_amounts) / len(recent_amounts) if recent_amounts else 0.0
    
    amount_std_1h = 0.0
    if len(recent_amounts) > 1:
        variance = sum((a - avg_amount_1h) ** 2 for a in recent_amounts) / len(recent_amounts)
        amount_std_1h = variance ** 0.5
    
    unique_counterparties_1h = len(recent_counterparties)
    
    # New counterparty ratio
    seen = _seen_counterparties[account_id]
    new_ones = [cp for cp in recent_counterparties if cp not in seen]
    new_counterparty_ratio_1h = len(new_ones) / unique_counterparties_1h if unique_counterparties_1h else 0.0
    
    # Time since last transaction
    last_time = _last_txn_time.get(account_id)
    hours_since_last_txn = ((timestamp - last_time).total_seconds() / 3600.0) if last_time else 999.0
    
    # Amount vs account average
    running_avg = avg_amount_1h if avg_amount_1h > 0 else amount
    amount_vs_account_avg = amount / running_avg if running_avg > 0 else 1.0
    
    features = {
        "txn_count_1h": float(txn_count_1h),
        "unique_counterparties_1h": float(unique_counterparties_1h),
        "new_counterparty_ratio_1h": float(new_counterparty_ratio_1h),
        "avg_amount_1h": float(avg_amount_1h),
        "amount_std_1h": float(amount_std_1h),
        "hours_since_last_txn": float(hours_since_last_txn),
        "amount": float(amount),
        "amount_vs_account_avg": float(amount_vs_account_avg),
    }
    
    # Update state AFTER computing
    history.append((timestamp, amount, counterparty_id))
    _seen_counterparties[account_id].add(counterparty_id)
    _last_txn_time[account_id] = timestamp
    
    return features