import pytest
from unittest.mock import MagicMock, patch
import pandas as pd
import numpy as np

from src.modules.training.tuner import HyperparameterTuner
from src.modules.training.types import TrainingConfig, ModelArtifact

def test_tuner_optimization_flow():
    # Mock data
    X = pd.DataFrame({"feat1": np.random.randn(100), "feat2": np.random.randn(100)})
    y = pd.Series(np.random.randint(0, 2, 100))
    
    # Mock XGBoostTrainer
    with patch("src.modules.training.tuner.XGBoostTrainer") as MockTrainer:
        trainer_instance = MockTrainer.return_value
        
        # Configure trainer to return a valid artifact with metrics
        # We need it to return different logloss values to simulate optimization?
        # Optuna minimizes logloss.
        # Let's just return a constant for simplicity, we verify it runs.
        trainer_instance.train.return_value = ModelArtifact(
            ticker="TUNE_TRIAL",
            model_path="",
            metrics={"logloss": 0.5},
            calibration_curve={},
            feature_names=["feat1", "feat2"],
            config=TrainingConfig()
        )
        
        tuner = HyperparameterTuner(output_dir="tmp/tuning")
        
        # Run optimize
        best_config = tuner.optimize(X, y, n_trials=2)
        
        # Assertions
        assert isinstance(best_config, TrainingConfig)
        # Check that trainer was called once per trial
        assert trainer_instance.train.call_count == 2
        
        # Check that we got reasonable params back (e.g. within bounds or default if fixed)
        assert 3 <= best_config.max_depth <= 10
        assert 0.01 <= best_config.learning_rate <= 0.3
        
def test_tuner_handles_training_failure():
    # Mock data
    X = pd.DataFrame({"feat1": np.random.randn(100)})
    y = pd.Series(np.random.randint(0, 2, 100))
    
    with patch("src.modules.training.tuner.XGBoostTrainer") as MockTrainer:
        trainer_instance = MockTrainer.return_value
        # Simulate failure
        trainer_instance.train.side_effect = Exception("Boom")
        
        tuner = HyperparameterTuner()
        
        # Should handle exception and continue (or fail trial gracefully)
        # Optuna usually continues if catch is configured or if we catch inside objective.
        # Our updated tuner catches Exception inside objective and returns inf.
        
        best_config = tuner.optimize(X, y, n_trials=1)
        
        # Since all trials failed, best_params might be empty or default?
        # Optuna create_study might have best_params if at least one trial completed?
        # If ALL failed -> raises ValueError: No trials are completed yet.
        # We should catch that in optimize?
        # Wait, if n_trials=1 and it fails, Optuna raises error when accessing best_params.
        # Let's see if our code handles it.
        # line 74: best_params = study.best_params -> will crash.
        
        # The tuner catches exceptions in the objective and returns inf.
        # If all trials fail, Optuna might settle on one trial as "best" (with inf value) 
        # or raise ValueError if no trials completed. 
        # However, our objective returns 'inf', which is a completed trial state in Optuna.
        # So study.best_params will exist (the parameters that led to inf).
        
        # We assert that it does NOT raise, and returns a config.
        best_config = tuner.optimize(X, y, n_trials=1)
        assert isinstance(best_config, TrainingConfig)
        
        # We can also verify that it logged an error if we mocked logger, but 
        # simply asserting no crash is enough for now given our design choice.
