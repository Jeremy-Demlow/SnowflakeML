"""
HyperOptimizer Interface
Maximum simplicity for beginners, full flexibility for experts

Key design principles:
- optimize(X, y) just works with best defaults
- Progressively expose complexity as needed
- Clean separation of concerns
- Extensible via plugins
"""

import numpy as np
from typing import Optional, Union, Callable, Dict, Any

# Import our clean modules
from hyperopt_core import (
    HyperOptimizer, OptimizationConfig, ScoringConfig, 
    OptimizationResult, OptimizationError
)
from experiment_tracker import ExperimentTracker, ExperimentConfig, create_tracking_callbacks, generate_unique_name
from model_registry import ModelRegistry, detect_task_type, get_model_for_task


class OptimizerResult:
    """
    User-friendly result wrapper with convenient methods
    
    Hides complexity while providing power when needed
    """
    
    def __init__(self, optimizer: HyperOptimizer, tracker: Optional[ExperimentTracker] = None):
        self.optimizer = optimizer
        self.tracker = tracker
        self.result = optimizer.result
    
    @property
    def best_params(self) -> Dict[str, Any]:
        """Best hyperparameters found"""
        return self.result.best_params
    
    @property
    def best_score(self) -> float:
        """Best cross-validation score"""
        return self.result.best_score
    
    @property
    def model_name(self) -> str:
        """Name of the optimized model"""
        return self.result.model_name
    
    def get_model(self):
        """Get the best model trained on all data"""
        return self.optimizer.get_model()
    
    def score(self, X_test: np.ndarray, y_test: np.ndarray) -> float:
        """Score on test data using the same metric as optimization"""
        test_score = self.optimizer.score(X_test, y_test)
        
        # Log test score if tracking enabled
        if self.tracker:
            self.tracker.log_test_score(test_score, X_test.shape)
            self.tracker.end_run()
        
        return test_score
    
    def summary(self) -> str:
        """Pretty summary of optimization results"""
        lines = [
            f"🎯 Optimization Complete!",
            f"",
            f"📊 Model: {self.result.model_name}",
            f"🏆 Best Score: {self.result.best_score:.4f} ({self.result.scoring_metric})",
            f"⏱️  Time: {self.result.optimization_time:.1f}s",
            f"🔄 Trials: {self.result.trials_completed} completed, {self.result.trials_failed} failed",
            f"📈 Task: {self.result.task_type}",
            f"",
            f"🎛️  Best Parameters:",
        ]
        
        for param, value in self.result.best_params.items():
            lines.append(f"   {param}: {value}")
        
        return "\n".join(lines)
    
    def __repr__(self) -> str:
        return f"OptimizerResult(score={self.best_score:.4f}, model={self.model_name})"


def optimize(X: np.ndarray, 
             y: np.ndarray,
             model: str = 'auto',
             metric: str = 'auto',
             trials: int = 50,
             cv: int = 5,
             scorer_func: Optional[Callable] = None,
             greater_is_better: Optional[bool] = None,
             experiment: Optional[str] = None,
             run_name: Optional[str] = None,
             session = None,
             random_state: int = 42,
             verbose: bool = True) -> OptimizerResult:
    """
    Optimize hyperparameters with sensible defaults
    
    Args:
        X: Training features
        y: Training targets
        model: Model type ('auto', 'xgb', 'lgb', 'rf', 'xgb_clf', 'rf_reg', etc.)
        metric: Scoring metric ('auto', 'accuracy', 'roc_auc', 'f1', 'precision', 'r2', etc.)
        trials: Number of optimization trials (default: 50)
        cv: Cross-validation folds (default: 5)
        scorer_func: Custom scoring function(y_true, y_pred) -> float
        greater_is_better: Whether higher scores are better (required with scorer_func)
        experiment: Experiment name for tracking (requires session)
        run_name: Run name for tracking (auto-generated if None)
        session: Snowflake session for experiment tracking
        random_state: Random seed for reproducibility
        verbose: Print progress and results
    
    Returns:
        OptimizerResult with convenient methods
    
    Examples:
        # Simplest usage - just give it data
        result = optimize(X, y)
        best_model = result.get_model()
        test_score = result.score(X_test, y_test)
        
        # Specify model and metric
        result = optimize(X, y, model='xgb', metric='roc_auc', trials=100)
        
        # Custom business metric
        def profit_score(y_true, y_pred):
            tp = ((y_true == 1) & (y_pred == 1)).sum()
            fp = ((y_true == 0) & (y_pred == 1)).sum()
            return tp * 100 - fp * 50
        
        result = optimize(X, y, scorer_func=profit_score, greater_is_better=True)
        
        # With experiment tracking
        result = optimize(X, y, experiment="churn_model", session=snowflake_session)
        
        # Quick model comparison
        for model_type in ['rf', 'xgb', 'lgb']:
            result = optimize(X, y, model=model_type, trials=20)
            print(f"{model_type}: {result.best_score:.4f}")
    """
    
    # 1. Auto-detect task type
    task_type = detect_task_type(y)
    
    # 2. Resolve model
    if model == 'auto':
        model_name = ModelRegistry.auto_select(task_type)
    else:
        # Handle shortcuts like 'xgb' -> 'xgb_clf'/'xgb_reg'
        model_shortcuts = {
            'rf': 'rf_clf' if 'classification' in task_type else 'rf_reg',
            'xgb': 'xgb_clf' if 'classification' in task_type else 'xgb_reg',
            'lgb': 'lgb_clf' if 'classification' in task_type else 'lgb_reg',
        }
        model_name = model_shortcuts.get(model, model)
    
    try:
        model_definition = ModelRegistry.get_model(model_name)
    except Exception as e:
        if verbose:
            print(f"❌ {e}")
            print(f"💡 Available models: {list(ModelRegistry.list_models().keys())}")
        raise
    
    if verbose:
        print(f"🤖 Using model: {model_definition.name}")
        print(f"📋 Task type: {task_type}")
    
    # 3. Create configurations
    opt_config = OptimizationConfig(
        max_evals=trials,
        cv=cv,
        random_state=random_state,
        verbose=verbose
    )
    
    scoring_config = ScoringConfig(
        metric=metric,
        custom_scorer=scorer_func,
        greater_is_better=greater_is_better
    )
    
    # 4. Setup experiment tracking (optional)
    tracker = None
    if session or experiment:
        exp_config = ExperimentConfig(
            experiment_name=experiment,
            run_name=run_name,
            auto_log=True
        )
        
        tracker = ExperimentTracker(session=session, config=exp_config)
        
        if experiment:
            tracker.start_experiment(experiment)
    
    # 5. Create optimizer
    optimizer = HyperOptimizer(
        model_cls=model_definition.model_cls,
        param_space=model_definition.param_space,
        optimization_config=opt_config,
        scoring_config=scoring_config
    )
    
    # 6. Setup tracking callbacks
    if tracker:
        # Generate unique run name if not provided
        if not run_name:
            run_name = generate_unique_name(f"optimize_{model_name}")
        
        actual_run_name = tracker.start_run(run_name)
        
        # Log setup information
        setup_data = {
            'model_class': model_definition.name,
            'model_type': model_name,
            'task_type': task_type,
            'scoring_metric': scoring_config.metric,
            'greater_is_better': scoring_config.greater_is_better,
            'max_evals': trials,
            'cv_folds': cv,
            'data_shape': str(X.shape),
            'target_classes': len(np.unique(y)) if task_type != 'regression' else 'continuous',
            'custom_scorer': scorer_func is not None,
            'hyperparameter_space_size': len(model_definition.param_space)
        }
        tracker.log_setup(setup_data)
        
        # Add callbacks
        trial_callback, completion_callback = create_tracking_callbacks(tracker)
        optimizer.add_callback('trial_complete', trial_callback)
        optimizer.add_callback('optimization_complete', completion_callback)
        
        if verbose and tracker.exp:
            print(f"📊 Experiment tracking: {experiment or 'default'} / {actual_run_name}")
    
    # 7. Run optimization
    if verbose:
        print(f"🚀 Starting optimization with {trials} trials...")
    
    try:
        result = optimizer.fit(X, y)
        
        if verbose:
            print(f"✅ Optimization complete!")
            print(f"🏆 Best score: {result.best_score:.4f}")
        
        return OptimizerResult(optimizer, tracker)
        
    except Exception as e:
        if tracker:
            tracker.end_run()
        raise OptimizationError(f"Optimization failed: {e}")


def list_models(task_type: Optional[str] = None) -> None:
    """List available models with their status"""
    print("📚 Available Models:")
    print("=" * 50)
    
    models = ModelRegistry.list_models(task_type)
    for name, description in models.items():
        print(f"  {name}: {description}")
    
    print("\n💡 Usage: optimize(X, y, model='model_name')")


def quick_compare(X: np.ndarray, 
                  y: np.ndarray, 
                  models: list = None, 
                  trials: int = 20,
                  metric: str = 'auto') -> Dict[str, float]:
    """
    Quickly compare multiple models
    
    Args:
        X: Training features
        y: Training targets
        models: List of models to compare (None = auto-select top 3)
        trials: Number of trials per model
        metric: Scoring metric
    
    Returns:
        Dictionary of model_name -> best_score
    """
    if models is None:
        task_type = detect_task_type(y)
        if 'classification' in task_type:
            models = ['rf_clf', 'xgb_clf']
        else:
            models = ['rf_reg', 'xgb_reg']
    
    results = {}
    print(f"🏁 Comparing {len(models)} models with {trials} trials each...")
    
    for model in models:
        try:
            print(f"\n🔄 Testing {model}...")
            result = optimize(X, y, model=model, trials=trials, metric=metric, verbose=False)
            results[model] = result.best_score
            print(f"✅ {model}: {result.best_score:.4f}")
        except Exception as e:
            print(f"❌ {model}: Failed ({e})")
            results[model] = None
    
    # Sort by score
    valid_results = {k: v for k, v in results.items() if v is not None}
    if valid_results:
        best_model = max(valid_results.keys(), key=lambda k: valid_results[k])
        print(f"\n🏆 Winner: {best_model} ({valid_results[best_model]:.4f})")
    
    return results

if __name__ == "__main__":
    from sklearn.datasets import make_classification, make_regression
    from sklearn.model_selection import train_test_split
    
    print("HyperOptimizer Examples")
    print("=" * 50)
    
    # Example 1: Simplest possible usage
    print("\n1. Simplest Usage - Just Give It Data:")
    X, y = make_classification(n_samples=1000, n_features=10, n_classes=2, random_state=42)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    result = optimize(X_train, y_train, trials=15)  # Minimal arguments
    best_model = result.get_model()
    test_score = result.score(X_test, y_test)
    print(result.summary())
    
    # Example 2: Specify model and metric
    print("\n2. Specify Model and Metric:")
    result = optimize(X_train, y_train, model='xgb', metric='roc_auc', trials=20)
    print(f"XGBoost ROC-AUC: {result.best_score:.4f}")
    
    # Example 3: Custom business metric
    print("\n3. Custom Business Metric:")
    def profit_score(y_true, y_pred):
        tp = ((y_true == 1) & (y_pred == 1)).sum()
        fp = ((y_true == 0) & (y_pred == 1)).sum()
        return tp * 100 - fp * 50  # $100 per TP, -$50 per FP
    
    result = optimize(X_train, y_train, 
                     scorer_func=profit_score, 
                     greater_is_better=True,
                     trials=15)
    print(f"Profit optimization: ${result.best_score:.0f}")
    
    # Example 4: Regression
    print("\n4. Regression Example:")
    X_reg, y_reg = make_regression(n_samples=1000, n_features=10, noise=0.1, random_state=42)
    X_train_reg, X_test_reg, y_train_reg, y_test_reg = train_test_split(X_reg, y_reg, test_size=0.2)
    
    result = optimize(X_train_reg, y_train_reg, model='auto', trials=15)
    test_score = result.score(X_test_reg, y_test_reg)
    print(f"Regression R²: {result.best_score:.4f}")
    
    # Example 5: Quick model comparison
    print("\n5. Quick Model Comparison:")
    comparison = quick_compare(X_train, y_train, trials=15)
    
    # Example 6: List available models
    print("\n6. Available Models:")
    list_models('classification')
    
    # Example 7: With experiment tracking (if available)
    print("\n7. With Experiment Tracking:")
    try:
        from connections import SnowflakeConnection
        connection = SnowflakeConnection.from_snow_cli('experiment_tracking')
        session = connection.session
        
        result = optimize(X_train, y_train,
                         model='xgb',
                         experiment="demo_experiment",
                         session=session,
                         trials=10)
        test_score = result.score(X_test, y_test)
        print(f"✅ Experiment tracking completed: {result.best_score:.4f}")
        
    except ImportError:
        print("❌ connections module not available - skipping experiment tracking demo")
        print("💡 Would work with: optimize(X, y, experiment='name', session=snowflake_session)")
    except Exception as e:
        print(f"❌ Experiment tracking error: {e}")