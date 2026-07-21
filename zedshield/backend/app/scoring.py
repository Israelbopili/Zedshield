import os
import joblib
import numpy as np

MODEL_PATH = os.getenv("MODEL_PATH", "zedshield_model.joblib")

# Try to load model, fall back to a simple rule-based scorer
try:
    _bundle = joblib.load(MODEL_PATH)
    _model = _bundle["model"]
    _feature_order = _bundle["features"]
    _model_loaded = True
except Exception:
    _model_loaded = False
    _feature_order = [
        "txn_count_1h", "unique_counterparties_1h", "new_counterparty_ratio_1h",
        "avg_amount_1h", "amount_std_1h", "hours_since_last_txn", "amount",
        "amount_vs_account_avg"
    ]

def score_event(features: dict, threshold: float = 0.5):
    """Score a transaction with the trained model or fallback rules."""
    
    if _model_loaded:
        # Use trained XGBoost model
        import pandas as pd
        X = pd.DataFrame([[features[f] for f in _feature_order]], columns=_feature_order)
        risk_score = float(_model.predict_proba(X)[0][1])
    else:
        # Fallback: rule-based scoring
        risk_score = _rule_based_score(features)
    
    # Generate reason codes
    reason_codes = _generate_reason_codes(features, risk_score)
    
    threshold_breached = risk_score >= threshold
    
    return {
        "risk_score": risk_score,
        "threshold_breached": threshold_breached,
        "reason_codes": reason_codes
    }

def _rule_based_score(features: dict) -> float:
    """Simple rule-based scoring when model isn't available."""
    score = 0.0
    
    # High transaction count
    if features["txn_count_1h"] > 10:
        score += 0.3
    elif features["txn_count_1h"] > 5:
        score += 0.15
    
    # Many unique counterparties
    if features["unique_counterparties_1h"] > 8:
        score += 0.25
    elif features["unique_counterparties_1h"] > 4:
        score += 0.1
    
    # High new counterparty ratio
    if features["new_counterparty_ratio_1h"] > 0.7:
        score += 0.25
    elif features["new_counterparty_ratio_1h"] > 0.4:
        score += 0.1
    
    # Long gap since last transaction (dormant reactivation)
    if features["hours_since_last_txn"] > 72:
        score += 0.15
    elif features["hours_since_last_txn"] > 24:
        score += 0.05
    
    # Amount significantly above average
    if features["amount_vs_account_avg"] > 5:
        score += 0.2
    elif features["amount_vs_account_avg"] > 3:
        score += 0.1
    
    # Large absolute amount
    if features["amount"] > 10000:
        score += 0.15
    elif features["amount"] > 5000:
        score += 0.05
    
    return min(score, 1.0)

def _generate_reason_codes(features: dict, risk_score: float) -> list:
    """Generate human-readable reason codes for flagged transactions."""
    reasons = []
    
    if features["txn_count_1h"] > 10:
        reasons.append(f"High transaction velocity: {features['txn_count_1h']:.0f} in 1 hour")
    
    if features["unique_counterparties_1h"] > 8:
        reasons.append(f"Many unique counterparties: {features['unique_counterparties_1h']:.0f}")
    
    if features["new_counterparty_ratio_1h"] > 0.7:
        reasons.append(f"High new counterparty ratio: {features['new_counterparty_ratio_1h']:.0%}")
    
    if features["hours_since_last_txn"] > 72:
        reasons.append(f"Dormant account reactivation: {features['hours_since_last_txn']:.0f} hours since last txn")
    
    if features["amount_vs_account_avg"] > 5:
        reasons.append(f"Amount vs account average: {features['amount_vs_account_avg']:.1f}x")
    
    if features["amount"] > 10000:
        reasons.append(f"Large transaction: K{features['amount']:,.2f}")
    
    # Always include at least one reason if risk is high
    if not reasons and risk_score > 0.3:
        reasons.append("Unusual transaction pattern detected")
    
    return reasons[:3]  # Limit to top 3