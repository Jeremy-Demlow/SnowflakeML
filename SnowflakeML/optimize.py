"""
User-facing API module for SnowflakeML optimizer.

The module provides three levels of API:
1. Simple API: optimize(X, y)
2. Strategy API: optimize_with_strategy(X, y, strategy='fast')
3. Advanced API: optimize_advanced(X, y, execution_config=config)
"""

from typing import Union, Dict, Any, Optional, Tuple
import numpy as np
import warnings
import logging

# Import our core execution backend
from .execution_backend import OptimizeTransform, ExecutionConfig
from .optimizer_result import OptimizerResult

# Set up logging
logger = logging.getLogger(__name__)

def optimize(X, y=None, **kwargs):
    """
    Optimize ML model hyperparameters with sensible defaults.
    
    This is the simplest API - handles all data types automatically:
    - numpy arrays -> Local execution
    - pandas DataFrames -> Local execution
    - Snowflake DataFrames -> Remote execution
    - Ray datasets -> Distributed execution
    
    Args:
        X: Features or DataFrame containing features and target
        y: Target variable (optional if X contains target)
        **kwargs: Optional parameters passed to execution backend
        
    Returns:
        OptimizerResult: Results with best model, parameters and metrics
    """
    # Log the API call at debug level
    logger.debug(f"optimize called with X type: {type(X).__name__}")
    
    # Dispatch to the execution backend
    transform = OptimizeTransform()
    
    # Handle different input patterns
    if y is not None:
        # Standard X, y pattern
        data = (X, y)
    else:
        # Single dataframe with target column
        data = X
    
    # Run optimization and return result
    result = transform(data)
    return result


def optimize_with_strategy(X, y=None, strategy='fast', **kwargs):
    """
    Optimize with pre-defined strategies for different scenarios.
    
    Available strategies:
    - 'fast': Quick optimization (default)
    - 'thorough': Comprehensive optimization
    - 'distributed': Multi-node distributed optimization
    - 'production': High-reliability production optimization
    
    Args:
        X: Features or DataFrame containing features and target
        y: Target variable (optional if X contains target)
        strategy: Optimization strategy name
        **kwargs: Override strategy parameters
        
    Returns:
        OptimizerResult: Results with best model, parameters and metrics
    """
    # Log the API call
    logger.debug(f"optimize_with_strategy called with strategy: {strategy}")
    
    # Create transform with strategy
    transform = OptimizeTransform(strategy=strategy, **kwargs)
    
    # Handle different input patterns
    if y is not None:
        # Standard X, y pattern
        data = (X, y)
    else:
        # Single dataframe or target column pattern
        data = X
    
    # Run optimization and return result
    result = transform(data)
    return result


def optimize_advanced(X, y=None, execution_config=None, model='auto', **kwargs):
    """
    Advanced optimization API with full control over execution.
    
    This API gives expert users complete control over the optimization
    process, including distributed execution, compute resources,
    algorithm settings and more.
    
    Args:
        X: Features or DataFrame containing features and target
        y: Target variable (optional if X contains target)
        execution_config: Configuration object controlling execution
        model: Model type to optimize ('auto', 'xgboost', etc.)
        **kwargs: Additional parameters
        
    Returns:
        OptimizerResult: Results with best model, parameters and metrics
    """
    # Log the API call
    logger.debug(f"optimize_advanced called with config: {execution_config}")
    
    # Create config if not provided
    if execution_config is None:
        execution_config = ExecutionConfig()
        
    # Set model type if provided
    if model != 'auto':
        kwargs['model'] = model
    
    # Create transform with config
    transform = OptimizeTransform(config=execution_config, **kwargs)
    
    # Handle different input patterns
    if y is not None:
        # Standard X, y pattern
        data = (X, y)
    else:
        # Single dataframe or target column pattern
        data = X
    
    # Run optimization and return result
    result = transform(data)
    return result 