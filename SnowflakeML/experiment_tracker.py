"""
Experiment Tracking - Snowflake Integration
Completely separate from core optimization logic
"""

import time
import json
import random
import numpy as np
from typing import Dict, Any, Optional
from datetime import datetime
from dataclasses import asdict

from pydantic import BaseModel, Field


def generate_unique_name(prefix: str = "run") -> str:
    """Generate a unique name with timestamp and random suffix"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    microseconds = datetime.now().microsecond
    random_suffix = random.randint(100, 999)
    return f"{prefix}_{timestamp}_{microseconds}_{random_suffix}"


class ExperimentConfig(BaseModel):
    """Experiment tracking configuration"""
    experiment_name: Optional[str] = Field(default=None, description="Experiment name")
    run_name: Optional[str] = Field(default=None, description="Run name (auto-generated if None)")
    auto_log: bool = Field(default=True, description="Automatically log key metrics")
    log_frequency: int = Field(default=10, ge=1, description="Log every N trials")
    log_failed_trials: bool = Field(default=True, description="Log failed trials")
    
    class Config:
        extra = "forbid"


class ExperimentTracker:
    """
    Handles experiment tracking with Snowflake
    
    Responsibilities:
    - Managing experiments and runs
    - Logging metrics, parameters, and metadata
    - Integrating with HyperOptimizer via callbacks
    
    Design: Can work with ANY optimizer via callbacks
    """
    
    def __init__(self, session=None, config: ExperimentConfig = None):
        self.session = session
        self.config = config or ExperimentConfig()
        
        # Snowflake tracking objects
        self.exp = None
        self.current_run = None
        
        # Initialize if session provided
        if session:
            try:
                from snowflake.ml.experiment.experiment_tracking import ExperimentTracking
                self.exp = ExperimentTracking(session=session)
                if self.config.experiment_name:
                    self.exp.set_experiment(self.config.experiment_name)
            except ImportError:
                raise ImportError(
                    "Snowflake experiment tracking requires: pip install snowflake-ml-python>=1.9.1"
                )
    
    def start_experiment(self, experiment_name: str):
        """Start or set experiment"""
        if not self.exp:
            raise ValueError("No Snowflake session provided - tracking disabled")
        
        self.exp.set_experiment(experiment_name)
        self.config.experiment_name = experiment_name
    
    def start_run(self, run_name: Optional[str] = None) -> str:
        """Start a new run with unique name generation"""
        if not self.exp:
            return "no_tracking"
        
        if not run_name:
            run_name = generate_unique_name("hpo_run")
        
        # Try to start run, handle existing run names gracefully
        try:
            self.current_run = self.exp.start_run(run_name)
            return run_name
        except Exception as e:
            if "already exists" in str(e):
                # Generate a new unique name and retry
                new_run_name = generate_unique_name("hpo_run")
                print(f"⚠️  Run '{run_name}' already exists, using '{new_run_name}' instead")
                self.current_run = self.exp.start_run(new_run_name)
                return new_run_name
            else:
                raise e
    
    def end_run(self):
        """End current run"""
        if self.exp and self.current_run:
            self.exp.end_run()
            self.current_run = None
    
    def log_setup(self, setup_data: Dict[str, Any]):
        """Log experiment setup parameters with validation"""
        if not self.exp or not self.current_run:
            return
        
        try:
            # Clean setup data for logging with strict validation
            clean_setup = {}
            for key, value in setup_data.items():
                # Ensure key is a valid string
                if not isinstance(key, str):
                    key = str(key)
                
                # Clean the value
                if isinstance(value, (str, int, float, bool)):
                    clean_setup[key] = value
                elif value is None:
                    clean_setup[key] = 'None'
                else:
                    clean_setup[key] = str(value)
            
            # Validate JSON serializability before logging
            json.dumps(clean_setup)
            self.exp.log_params(clean_setup)
            
        except Exception as e:
            print(f"⚠️ Failed to log setup params: {e}")
            # Try logging just the essential params
            try:
                essential_params = {
                    'model_type': str(setup_data.get('model_type', 'unknown')),
                    'data_shape': str(setup_data.get('data_shape', 'unknown'))
                }
                self.exp.log_params(essential_params)
                print("✅ Logged essential setup params only")
            except Exception as e2:
                print(f"⚠️ Failed to log even essential params: {e2}")
                # Continue gracefully
    
    def log_trial(self, trial_data: Dict[str, Any]):
        """Log individual trial data with robust validation"""
        if not self.exp or not self.current_run:
            return
        
        trial_num = trial_data.get('trial_number', 0)
        
        # Skip logging based on frequency
        if trial_num % self.config.log_frequency != 0:
            return
        
        try:
            # Log trial metrics with validation
            metrics = {}
            if trial_data.get('status') == 'success':
                score = trial_data.get('score', 0)
                score_std = trial_data.get('score_std', 0)
                
                # Validate numeric values
                if np.isfinite(score):
                    metrics['trial_score'] = float(score)
                if np.isfinite(score_std):
                    metrics['trial_score_std'] = float(score_std)
                metrics['trial_number'] = int(trial_num)
                
            elif trial_data.get('status') == 'failed' and self.config.log_failed_trials:
                metrics.update({
                    'trial_failed': 1.0,
                    'trial_number': int(trial_num),
                    'trial_error': str(trial_data.get('error', ''))[:100]
                })
            
            if metrics:
                # Validate JSON serializability
                json.dumps(metrics)
                self.exp.log_metrics(metrics, step=trial_num)
            
            # Log parameters for this trial (less frequently)
            if 'params' in trial_data and trial_num % (self.config.log_frequency * 2) == 0:
                all_params = self._extract_key_params(trial_data['params'])
                if all_params:
                    param_dict = {f"trial_{trial_num}_{k}": str(v) for k, v in all_params.items()}
                    # Validate JSON serializability
                    json.dumps(param_dict)
                    self.exp.log_params(param_dict)
                    
        except Exception as e:
            print(f"⚠️ Failed to log trial {trial_num}: {e}")
            # Continue gracefully
    
    def log_completion(self, result):
        """Log optimization completion summary with validation"""
        if not self.exp or not self.current_run:
            return
        
        try:
            # Handle both OptimizationResult objects and dicts
            if hasattr(result, '__dict__'):
                result_dict = asdict(result) if hasattr(result, '__dataclass_fields__') else result.__dict__
            else:
                result_dict = result
            
            # Log summary metrics with strict validation
            summary_metrics = {}
            
            # Validate and add each metric
            best_score = result_dict.get('best_score', 0)
            if np.isfinite(best_score):
                summary_metrics['best_score'] = float(best_score)
            
            opt_time = result_dict.get('optimization_time', 0)
            if np.isfinite(opt_time):
                summary_metrics['optimization_time_seconds'] = float(opt_time)
            
            trials_completed = result_dict.get('trials_completed', 0)
            if isinstance(trials_completed, (int, float)) and np.isfinite(trials_completed):
                summary_metrics['trials_completed'] = int(trials_completed)
            
            trials_failed = result_dict.get('trials_failed', 0)
            if isinstance(trials_failed, (int, float)) and np.isfinite(trials_failed):
                summary_metrics['trials_failed'] = int(trials_failed)
            
            # Add success rate if we have trial counts
            if 'trials_completed' in summary_metrics and 'trials_failed' in summary_metrics:
                total_trials = summary_metrics['trials_completed'] + summary_metrics['trials_failed']
                if total_trials > 0:
                    summary_metrics['success_rate'] = float(summary_metrics['trials_completed'] / total_trials)
            
            # Validate JSON serializability
            if summary_metrics:
                json.dumps(summary_metrics)
                self.exp.log_metrics(summary_metrics)
            
            # Log best parameters
            if 'best_params' in result_dict and result_dict['best_params']:
                best_params_clean = {}
                for k, v in result_dict['best_params'].items():
                    key = f'best_{k}'
                    best_params_clean[key] = str(v)
                
                # Validate JSON serializability
                json.dumps(best_params_clean)
                self.exp.log_params(best_params_clean)
                
        except Exception as e:
            print(f"⚠️ Failed to log completion summary: {e}")
            # Try logging just the score
            try:
                if hasattr(result, 'best_score') or 'best_score' in result:
                    best_score = getattr(result, 'best_score', result.get('best_score', 0))
                    if np.isfinite(best_score):
                        self.exp.log_metrics({'best_score': float(best_score)})
                        print("✅ Logged best score only")
            except Exception as e2:
                print(f"⚠️ Failed to log even basic completion data: {e2}")
                # Continue gracefully
    
    def log_test_score(self, test_score: float, test_data_shape: tuple):
        """Log final test score - simplified to avoid metadata issues"""
        if not self.exp or not self.current_run:
            return
        
        try:
            # Ensure test_score is a valid float and not NaN/infinite
            if not isinstance(test_score, (int, float)) or not np.isfinite(test_score):
                print(f"⚠️ Invalid test score: {test_score}, skipping log")
                return
            
            # Create simple metrics dict - avoid complex shape data that might cause issues
            metrics_dict = {
                'test_score': float(test_score),
                # Convert shape to simple format that Snowflake likes better
                'test_samples': int(test_data_shape[0]) if len(test_data_shape) > 0 else 0,
                'test_features': int(test_data_shape[1]) if len(test_data_shape) > 1 else 0
            }
            
            # Validate JSON serializability
            json.dumps(metrics_dict)
            self.exp.log_metrics(metrics_dict)
            
        except Exception as e:
            # If that still fails, just log the score
            try:
                simple_metrics = {'test_score': float(test_score)}
                json.dumps(simple_metrics)
                self.exp.log_metrics(simple_metrics)
                print("✅ Logged test score without shape data")
            except Exception as e2:
                print(f"⚠️ Failed to log test score completely: {e2}")
                # Continue gracefully
    
    def _extract_key_params(self, params: Dict) -> Dict:
        """Extract and clean all parameters for logging"""
        
        # Log ALL parameters - why limit? User might want to see everything!
        cleaned_params = {}
        for param_name, param_value in params.items():
            # Convert complex types to strings for Snowflake compatibility
            if isinstance(param_value, (list, tuple, dict)):
                cleaned_params[param_name] = str(param_value)
            elif param_value is None:
                cleaned_params[param_name] = 'None'
            elif isinstance(param_value, (str, int, float, bool)):
                cleaned_params[param_name] = param_value
            else:
                # Handle any other types (e.g., numpy types, custom objects)
                cleaned_params[param_name] = str(param_value)
        
        return cleaned_params
    
    # Context manager support
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_run()


def create_tracking_callbacks(tracker: ExperimentTracker):
    """Create callbacks for HyperOptimizer integration"""
    
    def on_trial_complete(trial_data: Dict[str, Any]):
        """Callback for when a trial completes"""
        tracker.log_trial(trial_data)
    
    def on_optimization_complete(result):
        """Callback for when optimization completes"""
        tracker.log_completion(result)
    
    return on_trial_complete, on_optimization_complete


if __name__ == "__main__":
    # Example 1: Basic usage with tracking
    print("Example 1: Basic tracking setup")
    
    # Without Snowflake session (tracking disabled)
    tracker = ExperimentTracker()
    print(f"Tracking enabled: {tracker.exp is not None}")
    
    # Example 2: With Snowflake session (real example)
    try:
        from connections import SnowflakeConnection
        import numpy as np
        
        connection = SnowflakeConnection.from_snow_cli('experiment_tracking')
        session = connection.session
        print(f"Connected to Snowflake: {session}")
        
        # Generate unique experiment name
        unique_run = generate_unique_name("test_run")
        
        # Create tracker with unique experiment config
        config = ExperimentConfig(
            experiment_name='My_Experiment',
            log_frequency=5,  # Log every 5 trials
            auto_log=True
        )
        
        tracker = ExperimentTracker(session=session, config=config)
        
        # Use with context manager
        with tracker:
            # Start run with unique name
            run_name = tracker.start_run(unique_run)
            print(f"Started run: {run_name}")
            
            # Log setup
            tracker.log_setup({
                'model_type': 'RandomForest',
                'data_shape': '(1000, 10)',
                'cv_folds': 5
            })
            
            # Simulate trials
            for i in range(10):
                trial_data = {
                    'trial_number': i + 1,
                    'score': 0.85 + np.random.normal(0, 0.05),
                    'score_std': 0.02,
                    'params': {'n_estimators': 100, 'max_depth': 10},
                    'status': 'success'
                }
                tracker.log_trial(trial_data)
            
            # Log completion
            result = {
                'best_score': 0.92,
                'best_params': {'n_estimators': 200, 'max_depth': 15},
                'optimization_time': 45.2,
                'trials_completed': 9,
                'trials_failed': 1
            }
            tracker.log_completion(result)
            
            # Log test score
            tracker.log_test_score(0.89, (200, 10))
        
        print("✅ Experiment tracking completed successfully!")
        
    except ImportError:
        print("❌ connections module not available - using simulated example")
        print("""
    # Real usage with Snowflake session:
    from snowflake.snowpark import Session
    
    # Initialize session
    connection_params = {...}
    session = Session.builder.configs(connection_params).create()
    
    # Create tracker with experiment config
    config = ExperimentConfig(
        experiment_name="my_unique_experiment",
        log_frequency=5,
        auto_log=True
    )
    
    tracker = ExperimentTracker(session=session, config=config)
    
    # Use with context manager
    with tracker:
        run_name = tracker.start_run("unique_run_name")
        
        # All metrics, parameters, and metadata automatically logged!
        """)
    
    except Exception as e:
        print(f"❌ Error with Snowflake tracking: {e}")
        print("💡 Make sure you have CREATE EXPERIMENT privileges on your schema")
    
    print("\nExperiment tracking module ready!")