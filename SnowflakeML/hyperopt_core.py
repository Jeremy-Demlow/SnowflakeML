"""
HyperOptimizer Core - Clean, Simple, Extensible
Inspired by FastAI's philosophy: simple for beginners, powerful for experts
"""

import numpy as np
import time
from typing import Dict, Any, Optional, Callable, Union, List
from abc import ABC, abstractmethod
from dataclasses import dataclass

from pydantic import BaseModel, Field, field_validator
from sklearn.model_selection import cross_val_score
from sklearn.metrics import make_scorer
from hyperopt import fmin, tpe, hp, Trials, STATUS_OK, space_eval


# ==============================================================================
# CONFIGURATION MODELS (Pydantic for validation)
# ==============================================================================

class OptimizationConfig(BaseModel):
    """Core optimization configuration with sensible defaults"""
    max_evals: int = Field(default=50, ge=1, le=1000, description="Number of optimization trials")
    cv: int = Field(default=5, ge=2, le=10, description="Cross-validation folds")
    random_state: int = Field(default=42, description="Random seed for reproducibility")
    n_jobs: int = Field(default=-1, description="Number of parallel jobs for CV")
    verbose: bool = Field(default=True, description="Print optimization progress")
    
    class Config:
        extra = "forbid"  # Don't allow extra fields


class ScoringConfig(BaseModel):
    """Scoring configuration - handles all scoring scenarios"""
    metric: str = Field(default='auto', description="Built-in metric name or 'auto'")
    custom_scorer: Optional[Callable] = Field(default=None, description="Custom scoring function")
    greater_is_better: Optional[bool] = Field(default=None, description="Score direction")
    
    class Config:
        arbitrary_types_allowed = True  # Allow Callable
        extra = "forbid"
    
    @field_validator('greater_is_better')
    @classmethod
    def validate_direction_with_custom(cls, v, info):
        if info.data.get('custom_scorer') is not None and v is None:
            raise ValueError("Must specify greater_is_better=True/False when using custom_scorer")
        return v


class ExperimentConfig(BaseModel):
    """Experiment tracking configuration"""
    experiment_name: Optional[str] = Field(default=None, description="Experiment name")
    run_name: Optional[str] = Field(default=None, description="Run name (auto-generated if None)")
    auto_log: bool = Field(default=True, description="Automatically log key metrics")
    log_frequency: int = Field(default=10, ge=1, description="Log every N trials")
    
    class Config:
        extra = "forbid"


# ==============================================================================
# CORE RESULTS AND EXCEPTIONS
# ==============================================================================

@dataclass
class OptimizationResult:
    """Clean result container"""
    best_params: Dict[str, Any]
    best_score: float
    optimization_time: float
    trials_completed: int
    trials_failed: int
    task_type: str
    model_name: str
    scoring_metric: str


class OptimizationError(Exception):
    """Clear, helpful error messages for users"""
    pass


class ModelNotFoundError(OptimizationError):
    """When a requested model isn't available"""
    pass


# ==============================================================================
# SCORING SYSTEM (Separate Concern)
# ==============================================================================

class ScoringSystem:
    """Handles all scoring logic - built-in and custom metrics"""
    
    # Common metrics and their directions
    METRIC_DIRECTIONS = {
        'accuracy': True, 'roc_auc': True, 'f1': True, 'f1_macro': True, 'f1_micro': True,
        'f1_weighted': True, 'precision': True, 'precision_macro': True, 'recall': True,
        'recall_macro': True, 'r2': True,
        'neg_mean_squared_error': True, 'neg_mean_absolute_error': True, 
        'neg_root_mean_squared_error': True, 'neg_log_loss': True
    }
    
    def __init__(self, config: ScoringConfig):
        self.config = config
        self.task_type = None
        self.final_scorer = None
        self.greater_is_better = None
    
    def setup_scoring(self, y: np.ndarray) -> str:
        """Setup scoring function and detect task type"""
        # Detect task type
        unique_vals = len(np.unique(y))
        
        if np.issubdtype(y.dtype, np.number) and unique_vals > 10:
            self.task_type = 'regression'
        elif unique_vals == 2:
            self.task_type = 'binary_classification'
        else:
            self.task_type = 'multiclass_classification'
        
        # Handle custom scorer
        if self.config.custom_scorer is not None:
            self.final_scorer = make_scorer(
                self.config.custom_scorer, 
                greater_is_better=self.config.greater_is_better
            )
            self.greater_is_better = self.config.greater_is_better
            return self.task_type
        
        # Handle auto metric selection
        if self.config.metric == 'auto':
            if self.task_type == 'regression':
                self.config.metric = 'neg_mean_squared_error'
            elif self.task_type == 'binary_classification':
                self.config.metric = 'roc_auc'
            else:
                self.config.metric = 'accuracy'
        
        # Set direction
        if self.config.greater_is_better is None:
            self.greater_is_better = self.METRIC_DIRECTIONS.get(self.config.metric, True)
        else:
            self.greater_is_better = self.config.greater_is_better
        
        self.final_scorer = self.config.metric
        return self.task_type
    
    def score_cv(self, model, X: np.ndarray, y: np.ndarray, cv: int) -> tuple[float, float]:
        """Perform cross-validation scoring"""
        scores = cross_val_score(
            model, X, y, 
            cv=cv, 
            scoring=self.final_scorer, 
            n_jobs=-1
        )
        return scores.mean(), scores.std()
    
    def score_test(self, model, X_test: np.ndarray, y_test: np.ndarray) -> float:
        """Score on test data using the same metric as optimization"""
        if self.config.custom_scorer is not None:
            # Custom scorer
            predictions = model.predict(X_test)
            return self.config.custom_scorer(y_test, predictions)
        
        # Built-in scorer
        if isinstance(self.final_scorer, str):
            try:
                from sklearn.metrics import get_scorer
                scorer = get_scorer(self.final_scorer)
                return scorer(model, X_test, y_test)
            except Exception:
                # Fallback to model.score
                return model.score(X_test, y_test)
        
        # Sklearn scorer object
        return self.final_scorer(model, X_test, y_test)


# ==============================================================================
# CORE OPTIMIZER (No External Dependencies)
# ==============================================================================

class HyperOptimizer:
    """
    Core hyperparameter optimizer - clean and focused
    
    Responsibilities:
    - Hyperparameter optimization with hyperopt
    - Cross-validation scoring
    - Result management
    
    NOT responsible for:
    - Experiment tracking (separate concern)
    - Model definitions (separate concern)
    """
    
    def __init__(self, 
                 model_cls, 
                 param_space: Dict, 
                 optimization_config: OptimizationConfig,
                 scoring_config: ScoringConfig):
        
        self.model_cls = model_cls
        self.param_space = param_space
        self.opt_config = optimization_config
        self.scoring_system = ScoringSystem(scoring_config)
        
        # State
        self.trials = Trials()
        self.result = None
        self.X, self.y = None, None
        self.trial_count = 0
        
        # Callbacks for extensibility
        self.on_trial_complete: List[Callable] = []
        self.on_optimization_complete: List[Callable] = []
    
    def add_callback(self, event: str, callback: Callable):
        """Add callbacks for extensibility (e.g., experiment tracking)"""
        if event == 'trial_complete':
            self.on_trial_complete.append(callback)
        elif event == 'optimization_complete':
            self.on_optimization_complete.append(callback)
        else:
            raise ValueError(f"Unknown event: {event}")
    
    def objective(self, params: Dict) -> Dict:
        """Objective function for hyperopt"""
        self.trial_count += 1
        
        try:
            # Create model
            model = self.model_cls(
                random_state=self.opt_config.random_state, 
                **params
            )
            
            # Evaluate
            score, score_std = self.scoring_system.score_cv(
                model, self.X, self.y, self.opt_config.cv
            )
            
            # Convert to loss (hyperopt minimizes)
            loss = -score if self.scoring_system.greater_is_better else score
            
            # Fire callbacks
            trial_data = {
                'trial_number': self.trial_count,
                'score': score,
                'score_std': score_std,
                'params': params,
                'loss': loss,
                'status': 'success'
            }
            
            for callback in self.on_trial_complete:
                callback(trial_data)
            
            # Progress indication
            if self.opt_config.verbose and self.trial_count % 10 == 0:
                print(f"  Trial {self.trial_count}: score={score:.4f}")
            
            return {'loss': loss, 'status': STATUS_OK}
            
        except Exception as e:
            # Fire failure callbacks
            trial_data = {
                'trial_number': self.trial_count,
                'error': str(e),
                'params': params,
                'status': 'failed'
            }
            
            for callback in self.on_trial_complete:
                callback(trial_data)
            
            return {'loss': float('inf'), 'status': STATUS_OK}
    
    def fit(self, X: np.ndarray, y: np.ndarray) -> OptimizationResult:
        """Run hyperparameter optimization"""
        self.X, self.y = X, y
        self.trial_count = 0
        
        # Setup scoring
        task_type = self.scoring_system.setup_scoring(y)
        
        if self.opt_config.verbose:
            print(f"Starting optimization: {task_type}")
            print(f"Metric: {self.scoring_system.config.metric}")
            print(f"Trials: {self.opt_config.max_evals}")
        
        start_time = time.time()
        
        # Run optimization
        best = fmin(
            fn=self.objective,
            space=self.param_space,
            algo=tpe.suggest,
            max_evals=self.opt_config.max_evals,
            trials=self.trials,
            verbose=False
        )
        
        optimization_time = time.time() - start_time
        
        # Create result
        best_params = space_eval(self.param_space, best)
        completed_trials = [t for t in self.trials.trials if t['result']['status'] == STATUS_OK]
        best_loss = min([t['result']['loss'] for t in completed_trials]) if completed_trials else float('inf')
        best_score = -best_loss if self.scoring_system.greater_is_better else best_loss
        
        self.result = OptimizationResult(
            best_params=best_params,
            best_score=best_score,
            optimization_time=optimization_time,
            trials_completed=len(completed_trials),
            trials_failed=len(self.trials.trials) - len(completed_trials),
            task_type=task_type,
            model_name=self.model_cls.__name__,
            scoring_metric=str(self.scoring_system.config.metric)
        )
        
        # Fire completion callbacks
        for callback in self.on_optimization_complete:
            callback(self.result)
        
        if self.opt_config.verbose:
            print(f"Optimization completed in {optimization_time:.1f}s")
            print(f"Best score: {best_score:.4f}")
            print(f"Best params: {best_params}")
        
        return self.result
    
    def get_model(self):
        """Get best model fitted on all training data"""
        if self.result is None:
            raise OptimizationError("Must call fit() first")
        
        model = self.model_cls(
            random_state=self.opt_config.random_state, 
            **self.result.best_params
        )
        model.fit(self.X, self.y)
        return model
    
    def score(self, X_test: np.ndarray, y_test: np.ndarray) -> float:
        """Score on test data"""
        model = self.get_model()
        return self.scoring_system.score_test(model, X_test, y_test)


# ==============================================================================
# SIMPLE USAGE EXAMPLE
# ==============================================================================

if __name__ == "__main__":
    from sklearn.datasets import make_classification
    from sklearn.ensemble import RandomForestClassifier
    from hyperopt import hp
    
    # Generate data
    X, y = make_classification(n_samples=1000, n_features=10, random_state=42)
    
    # Define model and space
    model_cls = RandomForestClassifier
    space = {
        'n_estimators': hp.choice('n_estimators', [50, 100, 200]),
        'max_depth': hp.choice('max_depth', [5, 10, None]),
        'min_samples_split': hp.uniform('min_samples_split', 0.01, 0.1)
    }
    
    # Create configs
    opt_config = OptimizationConfig(max_evals=20)
    scoring_config = ScoringConfig(metric='roc_auc')
    
    # Run optimization
    optimizer = HyperOptimizer(model_cls, space, opt_config, scoring_config)
    result = optimizer.fit(X, y)