#!/usr/bin/env python3
"""
ZedShield Model Trainer
Trains an XGBoost model on simulated transaction data.
"""

import argparse
import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from collections import defaultdict, deque
import joblib
from sklearn.model_selection import train_test_split
from sklearn.metrics import precision_recall_fscore_support, roc_auc_score
import xgboost as xgb

def compute_features_for_df(df):
    """Compute features for each transaction using the same logic as the live API."""
    features_list = []
    
    # Group by account
    for account_id in df['account_id'].unique():
        account_df = df[df['account_id'] == account_id].sort_values('timestamp')
        
        # State for this account
        history = deque(maxlen=500)
        seen_counterparties = set()
        last_txn_time = None
        
        for _, row in account_df.iterrows():
            timestamp = pd.to_datetime(row['timestamp'])
            amount = row['amount']
            counterparty_id = row['counterparty_id']
            
            # Clean old entries (1-hour window)
            while history and (timestamp - history[0][0]) > timedelta(hours=1):
                history.popleft()
            
            # Extract recent data
            recent_amounts = [a for (_, a, _) in history]
            recent_counterparties = {cp for (_, _, cp) in history}
            
            # Features
            txn_count_1h = len(history)
            avg_amount_1h = sum(recent_amounts) / len(recent_amounts) if recent_amounts else 0.0
            
            amount_std_1h = 0.0
            if len(recent_amounts) > 1:
                variance = sum((a - avg_amount_1h) ** 2 for a in recent_amounts) / len(recent_amounts)
                amount_std_1h = variance ** 0.5
            
            unique_counterparties_1h = len(recent_counterparties)
            
            new_ones = [cp for cp in recent_counterparties if cp not in seen_counterparties]
            new_counterparty_ratio_1h = len(new_ones) / unique_counterparties_1h if unique_counterparties_1h else 0.0
            
            hours_since_last_txn = ((timestamp - last_txn_time).total_seconds() / 3600.0) if last_txn_time else 999.0
            
            running_avg = avg_amount_1h if avg_amount_1h > 0 else amount
            amount_vs_account_avg = amount / running_avg if running_avg > 0 else 1.0
            
            features = {
                'account_id': account_id,
                'event_id': row['event_id'],
                'txn_count_1h': float(txn_count_1h),
                'unique_counterparties_1h': float(unique_counterparties_1h),
                'new_counterparty_ratio_1h': float(new_counterparty_ratio_1h),
                'avg_amount_1h': float(avg_amount_1h),
                'amount_std_1h': float(amount_std_1h),
                'hours_since_last_txn': float(hours_since_last_txn),
                'amount': float(amount),
                'amount_vs_account_avg': float(amount_vs_account_avg),
                'is_fraud': row['is_fraud'],
            }
            
            features_list.append(features)
            
            # Update state
            history.append((timestamp, amount, counterparty_id))
            seen_counterparties.add(counterparty_id)
            last_txn_time = timestamp
    
    return pd.DataFrame(features_list)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--db', default='zedshield_sim.db', help='SQLite database with events')
    parser.add_argument('--model', default='zedshield_model.joblib', help='Output model file')
    parser.add_argument('--test-size', type=float, default=0.2, help='Test set size')
    args = parser.parse_args()
    
    print(f"Loading data from {args.db}...")
    conn = sqlite3.connect(args.db)
    df = pd.read_sql_query("SELECT * FROM events ORDER BY timestamp", conn)
    conn.close()
    
    print(f"Loaded {len(df)} events")
    
    # Compute features
    print("Computing features...")
    features_df = compute_features_for_df(df)
    print(f"Computed features for {len(features_df)} transactions")
    
    # Features and target
    feature_cols = [
        'txn_count_1h', 'unique_counterparties_1h', 'new_counterparty_ratio_1h',
        'avg_amount_1h', 'amount_std_1h', 'hours_since_last_txn', 'amount',
        'amount_vs_account_avg'
    ]
    
    X = features_df[feature_cols]
    y = features_df['is_fraud']
    
    # Handle class imbalance
    fraud_count = y.sum()
    scale_pos_weight = (len(y) - fraud_count) / fraud_count if fraud_count > 0 else 1.0
    
    # Split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=args.test_size, random_state=42, stratify=y
    )
    
    print(f"Training: {len(X_train)} samples, Test: {len(X_test)} samples")
    print(f"Fraud rate: {fraud_count/len(y)*100:.2f}%")
    
    # Train XGBoost
    print("Training XGBoost model...")
    model = xgb.XGBClassifier(
        n_estimators=100,
        max_depth=6,
        learning_rate=0.1,
        scale_pos_weight=scale_pos_weight,
        random_state=42,
        use_label_encoder=False,
        eval_metric='logloss'
    )
    model.fit(X_train, y_train)
    
    # Evaluate
    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]
    
    precision, recall, f1, _ = precision_recall_fscore_support(y_test, y_pred, average='binary')
    auc = roc_auc_score(y_test, y_proba)
    
    print(f"\nResults:")
    print(f"  Precision: {precision:.4f}")
    print(f"  Recall: {recall:.4f}")
    print(f"  F1: {f1:.4f}")
    print(f"  AUC: {auc:.4f}")
    
    # Feature importance
    importance = pd.DataFrame({
        'feature': feature_cols,
        'importance': model.feature_importances_
    }).sort_values('importance', ascending=False)
    print("\nFeature importance:")
    for _, row in importance.iterrows():
        print(f"  {row['feature']}: {row['importance']:.4f}")
    
    # Save model
    bundle = {
        'model': model,
        'features': feature_cols,
        'feature_importance': importance.to_dict('records'),
        'metrics': {
            'precision': precision,
            'recall': recall,
            'f1': f1,
            'auc': auc,
        }
    }
    joblib.dump(bundle, args.model)
    print(f"\nModel saved to {args.model}")
    
    # Also save a simple rules-based fallback for comparison
    print("\nTip: If the model fails to load, the API will fall back to rule-based scoring.")

if __name__ == '__main__':
    main()