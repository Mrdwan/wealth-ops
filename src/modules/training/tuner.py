from typing import Any, Dict, Optional, Tuple
import optuna
import pandas as pd
import numpy as np
from dataclasses import dataclass
from src.modules.training.types import TrainingConfig, ModelArtifact
from src.modules.training.trainer import XGBoostTrainer
from src.shared.logger import get_logger

logger = get_logger("src.modules.training.tuner")

class HyperparameterTuner:
    """
    Optimizes XGBoost hyperparameters using Optuna.
    """
    def __init__(self, output_dir: str = "models/tuning"):
        self.output_dir = output_dir

    def optimize(
        self, 
        X: pd.DataFrame, 
        y: pd.Series, 
        n_trials: int = 50,
        validation_split: float = 0.2
    ) -> TrainingConfig:
        """
        Runs the optimization study.
        
        Args:
            X: Feature DataFrame.
            y: Target Series.
            n_trials: Number of trials to run.
            validation_split: Fraction of data to use for validation in each trial.
            
        Returns:
            The best TrainingConfig found.
        """
        logger.info(f"Starting Hyperparameter Optimization with {n_trials} trials.")
        
        # Define Objective Function
        def objective(trial: optuna.Trial) -> float:
            # 1. Suggest Parameters
            params = {
                "max_depth": trial.suggest_int("max_depth", 3, 10),
                "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
                "subsample": trial.suggest_float("subsample", 0.5, 1.0),
                "colsample_bytree": trial.suggest_float("colsample_bytree", 0.5, 1.0),
                "gamma": trial.suggest_float("gamma", 0.0, 5.0),
                "scale_pos_weight": trial.suggest_float("scale_pos_weight", 1.0, 10.0),
                
                # Fixed / Non-tunable for now
                "n_estimators": 500, # Handled by early stopping really, but cap at 500
                "early_stopping_rounds": 20,
                "target_window": 5, # Getting this from where? Assume fixed for study.
                "target_threshold": 0.03
            }
            
            # 2. Config
            config = TrainingConfig(**params)
            
            # 3. Train
            # We need to split here because Trainer normally does its own split, 
            # but we want to capture the evaluation metric (LogLoss/AUC) specifically.
            # actually Trainer.train returns an Artifact which has metrics.
            
            trainer = XGBoostTrainer(config)
            
            # Run training
            # Note: Trainer does an 80/20 split internally by default. 
            # We can rely on that for this MVP.
            try:
                artifact = trainer.train(X, y, ticker="TUNE_TRIAL")
                
                # 4. Return Metric
                # We want to MINIMIZE LogLoss or MAXIMIZE AUC?
                # Let's Minimize LogLoss as it encourages probability calibration.
                return artifact.metrics.get("logloss", float("inf"))
                
            except Exception as e:
                logger.error(f"Trial failed: {e}")
                return float("inf") # Prune failed trials

        # Create Study
        study = optuna.create_study(direction="minimize")
        study.optimize(objective, n_trials=n_trials)
        
        # Check results
        best_params = study.best_params
        logger.info(f"Optimization complete. Best params: {best_params}")
        logger.info(f"Best LogLoss: {study.best_value}")
        
        # Construct best config
        # We need to merge suggested params with defaults for non-tuned ones
        final_config = TrainingConfig(
            max_depth=best_params["max_depth"],
            learning_rate=best_params["learning_rate"],
            subsample=best_params["subsample"],
            colsample_bytree=best_params["colsample_bytree"],
            gamma=best_params["gamma"],
            scale_pos_weight=best_params["scale_pos_weight"],
             # Keep Defaults/Fixed for others
            n_estimators=1000, # Give plenty of room for final model
            early_stopping_rounds=50,
            target_window=5,
            target_threshold=0.03
        )
        
        return final_config
