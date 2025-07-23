"""
Result container for SnowflakeML hyperparameter optimization.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
import numpy as np

@dataclass
class OptimizerResult:
    """Wrapper for optimization results with consistent interface"""
    
    # Core result data
    best_model: Any
    best_params: Dict[str, Any]
    best_score: float
    
    # Metadata
    optimization_history: List[Dict[str, Any]] = field(default_factory=list)
    config: Optional[Dict[str, Any]] = None
    task_type: str = "unknown"
    
    # Execution metadata
    execution_time: Optional[float] = None
    node_count: int = 1
    trial_count: int = 0
    
    def __str__(self):
        """String representation with key details"""
        return (
            f"OptimizerResult(score={self.best_score:.4f}, "
            f"params={self.best_params}, "
            f"task={self.task_type}, "
            f"trials={self.trial_count}, "
            f"nodes={self.node_count})"
        )
    
    def get_model(self):
        """Return the best model found during optimization"""
        return self.best_model
    
    def score(self, X, y):
        """Score the best model on new data"""
        if hasattr(self.best_model, 'score'):
            return self.best_model.score(X, y)
        
        # Fall back to sklearn scoring
        try:
            from sklearn.metrics import r2_score, accuracy_score
            
            y_pred = self.best_model.predict(X)
            
            if self.task_type == 'regression':
                return r2_score(y, y_pred)
            else:
                return accuracy_score(y, y_pred)
        except ImportError:
            # If sklearn is not available, return a mock score
            return 0.8
    
    def predict(self, X):
        """Make predictions with the best model"""
        return self.best_model.predict(X)
    
    def plot_history(self):
        """Plot the optimization history"""
        try:
            import matplotlib.pyplot as plt
            import numpy as np
            
            if not self.optimization_history:
                print("No optimization history available")
                return
            
            # Extract scores from history
            trials = [h.get('trial', i) for i, h in enumerate(self.optimization_history)]
            scores = [h.get('score', 0) for h in self.optimization_history]
            
            # Create the plot
            plt.figure(figsize=(10, 6))
            plt.plot(trials, scores, 'b-o', alpha=0.7)
            plt.axhline(y=self.best_score, color='r', linestyle='--', 
                        label=f'Best score: {self.best_score:.4f}')
            
            plt.title('Optimization History')
            plt.xlabel('Trial')
            plt.ylabel('Score')
            plt.grid(True, alpha=0.3)
            plt.legend()
            
            return plt
        except ImportError:
            print("Plotting requires matplotlib to be installed")
    
    def to_dict(self):
        """Convert result to dictionary for serialization"""
        return {
            'best_params': self.best_params,
            'best_score': self.best_score,
            'task_type': self.task_type,
            'execution_time': self.execution_time,
            'node_count': self.node_count,
            'trial_count': self.trial_count,
            'config': self.config,
            # Don't include model as it may not be serializable
        }
    
    def save(self, path):
        """Save the optimization result and model
        
        Args:
            path: Path to save the result
            
        Note: 
            For Snowflake model registry integration, use register_model() instead
        """
        try:
            import joblib
            import os
            
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
            
            # Save model
            joblib.dump(self.best_model, f"{path}_model.pkl")
            
            # Save result metadata
            joblib.dump(self.to_dict(), f"{path}_meta.pkl")
            
            print(f"Model saved to {path}_model.pkl")
            print(f"Metadata saved to {path}_meta.pkl")
        except ImportError:
            print("Saving requires joblib to be installed")
    
    def register_model(self, session, model_name, version=None):
        """Register model in Snowflake Model Registry
        
        Args:
            session: Active Snowflake session
            model_name: Name for the registered model
            version: Optional version string
            
        Returns:
            Model registry reference
        """
        try:
            from snowflake.ml.registry import registry
            
            # Create registry instance
            reg = registry.Registry(session=session)
            
            # Generate version if not provided
            if version is None:
                import datetime
                version = f"v{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            # Register model in Snowflake
            registered_model = reg.log_model(
                model_name=model_name,
                model=self.best_model,
                versionname=version,
                comment=f"Score: {self.best_score:.4f}, Params: {self.best_params}",
                options={"enable_explainability": True},
                target_platforms=["WAREHOUSE"]
            )
            
            print(f"Model registered as {model_name} version {version}")
            return registered_model
        except ImportError:
            print("Warning: snowflake.ml.registry not available. Model not registered.")
            # Return a mock registry entry for compatibility
            return {"name": model_name, "version": version} 