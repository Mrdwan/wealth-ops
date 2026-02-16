#!/usr/bin/env python3
"""
Manual tuning script for SPY using Optuna.
Simulates a hyperparameter optimization run.
"""
import sys
import os
import pandas as pd
import numpy as np
from unittest.mock import MagicMock

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.modules.training.tuner import HyperparameterTuner
from src.modules.training.types import TrainingConfig

def create_mock_data():
    """Generates 2 years of random OHLCV data + features."""
    dates = pd.date_range(start="2022-01-01", end="2023-12-31", freq="D")
    n = len(dates)
    
    # Random walk for price
    price = 100 + np.cumsum(np.random.randn(n))
    
    df = pd.DataFrame({
        "open": price + np.random.randn(n),
        "high": price + 2 + np.random.randn(n),
        "low": price - 2 + np.random.randn(n),
        "close": price + np.random.randn(n),
        "volume": np.random.randint(1000, 10000, n).astype(float)
    }, index=dates)
    
    # Fake Features
    for i in range(10):
        df[f"feature_{i}"] = np.random.randn(n)
        
    return df

def main():
    print("Initializing Hyperparameter Tuner for SPY...")
    
    # 1. Get Data (Mocked)
    print("Fetching data (Mocked)...")
    df = create_mock_data()
    
    # 2. Prep Targets (Simple lookahead for tuning demo)
    # Target: Close + 2% in 5 days
    future_max = df["high"].shift(-1).rolling(5).max()
    target_price = df["close"] * 1.02
    y = (future_max >= target_price).astype(int)
    
    # Drop NaNs
    valid_idx = df.index[:-5]
    X = df.loc[valid_idx, [c for c in df.columns if "feature" in c]]
    y = y.loc[valid_idx]
    
    print(f"Data Shape: X={X.shape}, y={y.shape}")
    
    # 3. Optimize
    tuner = HyperparameterTuner(output_dir="models/tuning")
    
    # Run small number of trials for demo
    best_config = tuner.optimize(X, y, n_trials=5)
    
    print("\nSUCCESS: Tuning Complete.")
    print(f"Best Configuration Found:")
    print(f"  Max Depth: {best_config.max_depth}")
    print(f"  Learning Rate: {best_config.learning_rate:.4f}")
    print(f"  Subsample: {best_config.subsample:.4f}")
    print(f"  Colsample ByTree: {best_config.colsample_bytree:.4f}")
    print(f"  Gamma: {best_config.gamma:.4f}")
    print(f"  Scale Pos Weight: {best_config.scale_pos_weight:.4f}")

if __name__ == "__main__":
    main()
