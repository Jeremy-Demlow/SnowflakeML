#!/usr/bin/env python3
"""
Example showing how to use SnowflakeML's optimization API 
with Snowflake connections from Snow CLI
"""

import numpy as np
import pandas as pd
from sklearn.datasets import load_diabetes
from sklearn.model_selection import train_test_split
import logging
import argparse

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Check if required packages are installed
try:
    import hyperopt
    import pydantic
    from hyperopt import hp
except ImportError:
    logger.error("Required packages not found. Please install with:")
    logger.error("pip install hyperopt pydantic")
    raise

# Import our optimization API - direct imports from modules
from SnowflakeML.optimize import optimize, optimize_with_strategy, optimize_advanced
from SnowflakeML.execution_backend import ExecutionConfig
from SnowflakeML.connections import SnowflakeConnection


def local_example():
    """Example using local numpy data"""
    logger.info("Running local optimization example")
    
    # Load a sample dataset
    data = load_diabetes()
    X, y = data.data, data.target
    
    # Split data
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    logger.info(f"Training data shape: {X_train.shape}")
    
    # Call our optimization API - simplest form
    # This will auto-detect task type (regression) and use good defaults
    result = optimize(X_train, y_train)
    
    # Debug output
    logger.info(f"Result type: {type(result)}")
    logger.info(f"Result: {result}")
    
    # Evaluate on test set
    score = result.score(X_test, y_test)
    logger.info(f"Test score: {score:.4f}")
    
    # Check model parameters
    logger.info(f"Best parameters: {result.best_params}")
    logger.info(f"Task type: {result.task_type}")
    
    # Get predictions
    y_pred = result.predict(X_test)
    logger.info(f"First few predictions: {y_pred[:5]}")
    
    return result


def strategy_example():
    """Example using strategy-based API with Snow CLI connection"""
    logger.info("Running strategy-based optimization example")
    
    # Get Snow CLI connection
    try:
        connection = SnowflakeConnection.from_snow_cli()
        logger.info(f"Using connection: {connection}")
    except Exception as e:
        logger.error(f"Error creating Snow CLI connection: {e}")
        logger.info("Using fake Snowflake DataFrame for example")
        
        # Create mock DataFrame that looks like a Snowflake DataFrame
        class MockSnowflakeDF:
            def __init__(self, data):
                self.data = data
                self.columns = ["COL1", "COL2", "TARGET"]
            
            def collect(self):
                return self.data
                
            def to_pandas(self):
                return pd.DataFrame(self.data, columns=self.columns)
                
            def drop(self, col):
                return self
                
            def select(self, col):
                return self
        
        snowflake_df = MockSnowflakeDF(np.random.rand(100, 3))
        target_col = "TARGET"
    else:
        # In real code, we'd create a Snowflake DataFrame here
        # For example:
        # session = connection.session
        # snowflake_df = session.sql("SELECT * FROM my_table")
        
        # For the example, we'll use a mock DataFrame
        class MockSnowflakeDF:
            def __init__(self, data):
                self.data = data
                self.columns = ["COL1", "COL2", "TARGET"]
            
            def collect(self):
                return self.data
                
            def to_pandas(self):
                return pd.DataFrame(self.data, columns=self.columns)
                
            def drop(self, col):
                return self
                
            def select(self, col):
                return self
        
        snowflake_df = MockSnowflakeDF(np.random.rand(100, 3))
        target_col = "TARGET"
    
    # Call strategy-based API with 'fast' strategy
    result = optimize_with_strategy(
        snowflake_df, 
        target_col, 
        strategy='fast'
    )
    
    # Check results
    logger.info(f"Best score: {result.best_score:.4f}")
    logger.info(f"Best params: {result.best_params}")
    
    return result


def advanced_example():
    """Example using advanced API with custom configuration"""
    logger.info("Running advanced optimization example")
    
    # Load data
    data = load_diabetes()
    X, y = data.data, data.target
    
    # Create custom configuration
    config = ExecutionConfig(
        trials=100,  # Number of trials
        target_instances=2,  # For distributed execution
        early_stopping=True,
        verbose=True
    )
    
    # Call advanced API with custom configuration
    result = optimize_advanced(
        X, 
        y,
        execution_config=config,
        model='xgb_reg'  # Specify model type
    )
    
    # Check results
    logger.info(f"Best score: {result.best_score:.4f}")
    logger.info(f"Task type: {result.task_type}")
    logger.info(f"Execution time: {result.execution_time:.2f} seconds")
    
    return result


def snowflake_example():
    """Example using Snowflake connection and data"""
    logger.info("Running Snowflake optimization example")
    
    # Try to get Snow CLI connection
    try:
        connection = SnowflakeConnection.from_snow_cli()
        logger.info(f"Using connection: {connection}")
        
        # Get session
        session = connection.session
        
        # Example query - in real code this would be your data
        snowflake_df = session.sql("""
            SELECT * FROM SNOWFLAKE_SAMPLE_DATA.TPCH_SF1.CUSTOMER LIMIT 1000
        """)
        
        # Call optimization API with Snowflake data
        # Note: This would need a proper target column in real use
        result = optimize(
            snowflake_df,
            "C_ACCTBAL"  # Target column
        )
        
        # Check results
        logger.info(f"Best score: {result.best_score:.4f}")
        logger.info(f"Model parameters: {result.best_params}")
        
        return result
        
    except Exception as e:
        logger.error(f"Error in Snowflake example: {e}")
        logger.info("Skipping Snowflake example due to connection error")
        return None


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SnowflakeML Optimization Examples")
    parser.add_argument("--mode", choices=["local", "strategy", "advanced", "snowflake", "all"], 
                        default="local", help="Example mode to run")
    args = parser.parse_args()
    
    if args.mode == "local" or args.mode == "all":
        local_example()
        
    if args.mode == "strategy" or args.mode == "all":
        strategy_example()
        
    if args.mode == "advanced" or args.mode == "all":
        advanced_example()
        
    if args.mode == "snowflake" or args.mode == "all":
        snowflake_example() 