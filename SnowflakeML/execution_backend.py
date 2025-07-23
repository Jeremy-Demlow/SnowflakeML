"""Execution backend for SnowflakeML with type-based dispatching."""

from fasttransform import Transform
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, Union, Tuple, TYPE_CHECKING
import numpy as np
import logging
import time

# Type checking imports
if TYPE_CHECKING:
    import snowflake.snowpark.dataframe
    import ray.data

# Set up logging
logger = logging.getLogger(__name__)

@dataclass
class ExecutionConfig:
    """Complete execution control with progressive defaults"""
    
    # Core settings with sensible defaults
    compute_pool: Optional[str] = None
    target_instances: int = 1
    trials: int = 50
    
    # Advanced settings
    min_instances: Optional[int] = None
    parallel_trials: int = 1
    hyperopt_algorithm: str = 'tpe'
    early_stopping: bool = True
    
    # Connection settings
    connection_name: Optional[str] = None  # Snow CLI connection name
    
    # Expert settings
    distributed_backend: str = 'auto'
    scaling_strategy: str = 'conservative'
    resource_config: Dict[str, Any] = field(default_factory=dict)
    
    # Logging settings
    verbose: bool = False
    log_frequency: int = 5

# Pre-defined strategies
OPTIMIZATION_STRATEGIES = {
    'fast': ExecutionConfig(trials=20, early_stopping=True),
    'thorough': ExecutionConfig(trials=200, parallel_trials=4),
    'distributed': ExecutionConfig(target_instances=3, trials=100, parallel_trials=4),
    'production': ExecutionConfig(
        target_instances=8, 
        min_instances=4,
        trials=500, 
        parallel_trials=8, 
        scaling_strategy='aggressive'
    )
}

class OptimizeTransform(Transform):
    """Type-dispatched optimization engine"""
    
    def __init__(self, config=None, strategy=None, **kwargs):
        # Auto-detect strategy if none specified
        self.data = None  # Will be set during __call__
        
        if config is None and strategy is None and not kwargs:
            # Will detect optimal strategy during first call with data
            self.auto_detect_strategy = True
        else:
            self.auto_detect_strategy = False
            
            # Handle configuration priorities: explicit config > strategy > kwargs
            if config is None:
                if strategy and strategy in OPTIMIZATION_STRATEGIES:
                    config = OPTIMIZATION_STRATEGIES[strategy]
                else:
                    config = ExecutionConfig()
                    
            # Override with any explicit kwargs
            for k, v in kwargs.items():
                if hasattr(config, k):
                    setattr(config, k, v)
                    
        self.config = config
        self.strategy = strategy
        super().__init__()
        
        # Setup logging based on config
        self.setup_logging()
    
    def setup_logging(self):
        """Configure logging based on execution config"""
        log_level = logging.DEBUG if self.config and self.config.verbose else logging.INFO
        logger.setLevel(log_level)
        
        # Create console handler if none exists
        if not logger.handlers:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(log_level)
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)
            
        logger.debug("Logging configured for OptimizeTransform")
    
    def _detect_optimal_strategy(self, data):
        """Automatically suggest strategy based on data characteristics"""
        if isinstance(data, tuple) and len(data) == 2:
            X, y = data
            if isinstance(X, np.ndarray):
                if X.shape[0] > 10_000_000:  # 10M+ rows
                    return 'distributed'
                elif X.shape[0] > 1_000_000:  # 1M+ rows
                    return 'thorough'
                else:
                    return 'fast'
            elif hasattr(X, 'count'):
                # Snowflake DataFrame or similar
                try:
                    count = X.count()
                    if count > 10_000_000:
                        return 'distributed'
                    elif count > 1_000_000:
                        return 'thorough'
                except:
                    pass
        
        # Ray dataset or other distributed format
        if hasattr(data, 'count') and callable(data.count):
            return 'distributed'
            
        return 'fast'  # Default to fast for unknown data types
    
    def __call__(self, data):
        # Store data for potential auto-detection
        self.data = data
        
        # Handle auto-strategy detection
        if self.auto_detect_strategy:
            strategy = self._detect_optimal_strategy(data)
            self.strategy = strategy
            self.config = OPTIMIZATION_STRATEGIES[strategy]
            logger.info(f"Auto-selected strategy: '{strategy}'")
            self.explain_strategy()
            
        # Get cost estimate
        if self.config.target_instances > 1:
            logger.info(f"Resource estimate: {self.estimate_cost(data)}")
        
        # Check if data is a tuple of numpy arrays
        if isinstance(data, tuple) and len(data) == 2:
            X, y = data
            if isinstance(X, np.ndarray) and isinstance(y, np.ndarray):
                # Special case for numpy arrays
                return self._optimize_local(X, y)
                
        # Continue with normal transform processing for other types
        return super().__call__(data)
        
    def explain_strategy(self):
        """Help users understand what the strategy does"""
        if not self.strategy:
            return
            
        explanations = {
            'fast': "Quick optimization: 20 trials, early stopping, minimal resources",
            'thorough': "Comprehensive: 200 trials, 4 parallel workers, thorough search", 
            'distributed': "Multi-node: 3+ nodes, 100 trials, parallel distributed execution",
            'production': "Enterprise: 8+ nodes, 500 trials, fault tolerance, aggressive scaling"
        }
        
        logger.info(f"Strategy '{self.strategy}': {explanations.get(self.strategy, 'Custom strategy')}")
        
    def estimate_cost(self, data):
        """Help users understand resource implications"""
        # Simple estimation logic
        config = self.config
        
        # Estimate data size
        data_size_gb = 1.0  # Default
        if isinstance(data, tuple) and len(data) == 2:
            X, _ = data
            if hasattr(X, 'shape') and hasattr(X, 'nbytes'):
                data_size_gb = X.nbytes / (1024**3)
            elif hasattr(X, 'count'):
                # Rough estimate for Snowflake DataFrame
                try:
                    count = X.count()
                    col_count = len(X.columns) if hasattr(X, 'columns') else 10
                    data_size_gb = count * col_count * 8 / (1024**3)  # Assume 8 bytes per value
                except:
                    pass
                    
        # Calculation factors
        node_count = config.target_instances
        parallel_factor = max(1, config.parallel_trials)
        trials = config.trials
        
        # Estimates
        node_hours = node_count * (trials / 100) * (data_size_gb / 5)
        duration_hrs = (trials / parallel_factor) * (data_size_gb / 5) / node_count
        duration_mins = max(5, int(duration_hrs * 60))  # Minimum 5 minutes
        
        return {
            'estimated_node_hours': round(node_hours, 2),
            'estimated_cost': f"${round(node_hours * 5, 2)}",  # $5/node-hour estimate
            'estimated_duration': f"{duration_mins} minutes" if duration_mins < 60 else f"{round(duration_hrs, 1)} hours"
        }
    
    def encodes(self, data: Tuple[np.ndarray, np.ndarray]):
        """Local execution with numpy arrays - no longer used, directly handled in __call__"""
        return NotImplemented  # Will be handled in __call__ instead
    
    def encodes(self, data):
        """Type-based dispatch implementation for other types"""
        # Handle Snowflake DataFrame with target column
        if (isinstance(data, tuple) and len(data) == 2 and 
            hasattr(data[0], 'to_pandas') and hasattr(data[0], 'collect')):
            
            df, target_col = data
            if self.config.target_instances <= 1:
                logger.info(f"Starting remote single-node execution on Snowflake: target column {target_col}")
                return self._optimize_remote_single(df, target_col)
            else:
                logger.info(f"Starting remote distributed execution on Snowflake with {self.config.target_instances} nodes: target column {target_col}")
                return self._optimize_remote_distributed(df, target_col)
                
        # Handle Ray dataset
        if hasattr(data, 'count') and hasattr(data, 'map'):
            logger.info(f"Starting distributed execution with Ray dataset")
            return self._optimize_distributed(data)
            
        # Return NotImplemented for unsupported types
        return NotImplemented
    
    def _get_snowflake_session(self):
        """Get Snowflake session using our connection approach"""
        from .connections import SnowflakeConnection
        
        # Use the connection name from config if available
        connection_name = self.config.connection_name
        
        try:
            # Try to create connection from Snow CLI
            logger.info(f"Creating Snowflake connection from Snow CLI{f' ({connection_name})' if connection_name else ''}")
            connection = SnowflakeConnection.from_snow_cli(connection_name)
            logger.info(f"Connected to Snowflake: {connection}")
            return connection.session
        except Exception as e:
            logger.warning(f"Could not create connection from Snow CLI: {e}")
            
            try:
                # Fall back to environment variables
                logger.info("Falling back to environment variables for Snowflake connection")
                connection = SnowflakeConnection.from_env()
                logger.info(f"Connected to Snowflake: {connection}")
                return connection.session
            except Exception as e2:
                logger.warning(f"Could not create connection from environment: {e2}")
                
                # Last resort - try default session builder
                logger.info("Falling back to default session builder")
                from snowflake.snowpark import Session
                session = Session.builder.getOrCreate()
                logger.info(f"Connected to Snowflake: account={session.get_current_account()}, database={session.get_current_database()}, schema={session.get_current_schema()}")
                return session
    
    def _optimize_local(self, X, y):
        """Local execution using existing optimization code"""
        from .hyperopt_core import HyperOptimizer
        from .model_registry import ModelRegistry
        
        start_time = time.time()
        logger.info("Starting local optimization")
        
        # Create optimizer using existing core logic
        model_registry = ModelRegistry()
        model_type = self.config.__dict__.get('model', 'auto')
        task_type = self._detect_task_type(y)
        
        model_definition = model_registry.get_model(model_type, task_type)
        logger.debug(f"Using model type: {model_type}, task type: {task_type}")
        
        # Configure the optimizer with our settings
        optimizer = HyperOptimizer(
            model_cls=model_definition.model_cls,
            param_space=model_definition.param_space,
            max_evals=self.config.trials,
            early_stopping=self.config.early_stopping
        )
        
        # Run optimization with periodic logging
        if self.config.verbose:
            def log_callback(trial, score, params):
                if trial % self.config.log_frequency == 0:
                    logger.info(f"Trial {trial}/{self.config.trials} - Score: {score:.4f}")
            optimizer.set_callback(log_callback)
        
        # Run optimization
        result = optimizer.fit(X, y)
        
        # Log completion time
        execution_time = time.time() - start_time
        logger.info(f"Optimization completed in {execution_time:.2f} seconds")
        logger.info(f"Best score: {result.best_score:.4f}")
        
        # Create result object
        from .optimizer_result import OptimizerResult
        return OptimizerResult(
            best_model=result.best_model,
            best_params=result.best_params,
            best_score=result.best_score,
            optimization_history=result.history,
            task_type=task_type,
            execution_time=execution_time,
            node_count=1,
            trial_count=self.config.trials
        )
    
    def _optimize_remote_single(self, df, target_col):
        """Single-node remote execution"""
        from snowflake.ml.jobs import remote
        
        start_time = time.time()
        logger.info(f"Starting remote single-node optimization for target column: {target_col}")
        
        # Get or create compute pool
        session = self._get_snowflake_session()
        compute_pool = self.config.compute_pool
        if compute_pool:
            logger.info(f"Using compute pool: {compute_pool}")
        else:
            compute_pool = "SNOWFLAKEML_OPTIMIZE_POOL"
            logger.info(f"No compute pool specified, using default: {compute_pool}")
            self._ensure_compute_pool(session, compute_pool)
        
        @remote(
            compute_pool=compute_pool,
            stage_name="optimization_stage"
        )
        def single_node_optimize():
            # Import optimization logic inside remote context
            import time
            import logging
            remote_logger = logging.getLogger("snowflake.ml.optimize")
            remote_logger.setLevel(logging.INFO)
            
            from snowflake.snowpark.context import get_active_session
            from SnowflakeML.hyperopt_core import HyperOptimizer
            from SnowflakeML.model_registry import ModelRegistry
            
            remote_session = get_active_session()
            remote_logger.info(f"Remote session active: {remote_session.get_current_database()}.{remote_session.get_current_schema()}")
            
            start = time.time()
            
            # Extract features and target
            remote_logger.info(f"Extracting features and target from dataframe")
            X = df.drop(target_col)
            y = df.select(target_col).to_pandas()
            
            # Use existing optimization code
            model_registry = ModelRegistry()
            model_type = self.config.__dict__.get('model', 'auto')
            
            # Detect task type
            if hasattr(y, 'nunique'):
                unique_values = y.nunique()
                task_type = 'classification' if unique_values <= 10 else 'regression'
            else:
                task_type = 'regression'  # Default
                
            remote_logger.info(f"Task type detected: {task_type}")
            
            model_definition = model_registry.get_model(model_type, task_type)
            
            remote_logger.info(f"Starting optimization with {self.config.trials} trials")
            optimizer = HyperOptimizer(
                model_cls=model_definition.model_cls,
                param_space=model_definition.param_space,
                max_evals=self.config.trials,
                early_stopping=self.config.early_stopping
            )
            
            # Set up logging callback
            def log_callback(trial, score, params):
                if trial % 10 == 0 or trial == 1:
                    remote_logger.info(f"Trial {trial}/{self.config.trials} - Score: {score:.4f}")
                    
            optimizer.set_callback(log_callback)
            
            # Run optimization
            result = optimizer.fit(X, y)
            
            execution_time = time.time() - start
            remote_logger.info(f"Optimization completed in {execution_time:.2f} seconds")
            remote_logger.info(f"Best score: {result.best_score:.4f}")
            
            # Return results
            return {
                "best_model": result.best_model,
                "best_params": result.best_params,
                "best_score": result.best_score,
                "history": result.history,
                "task_type": task_type,
                "execution_time": execution_time,
                "trial_count": self.config.trials
            }
            
        # Start the job
        logger.info("Submitting remote optimization job")
        job = single_node_optimize()
        job_id = job.id
        logger.info(f"Job submitted with ID: {job_id}")
        
        # Wait for job to complete with status updates
        logger.info("Waiting for job to complete...")
        status = "UNKNOWN"
        while status not in ["DONE", "FAILED", "CANCELLED"]:
            status = job.status
            logger.info(f"Job status: {status}")
            if status == "RUNNING":
                logger.debug("Job is running - fetching logs")
                logs = job.get_logs()
                if logs:
                    for line in logs.split('\n')[-5:]:  # Show last few log lines
                        if '[INFO]' in line and 'snowflake.ml.optimize' in line:
                            logger.info(f"Remote: {line.split('snowflake.ml.optimize - ')[1] if 'snowflake.ml.optimize - ' in line else line}")
            time.sleep(10)
        
        if status == "FAILED":
            logger.error(f"Job failed: {job.status}")
            logger.error("Job logs:")
            logger.error(job.get_logs())
            raise RuntimeError(f"Remote optimization job failed: {job.id}")
        
        # Get results
        logger.info("Job completed - retrieving results")
        result = job.wait_for_completion()
        
        # Calculate execution time
        execution_time = time.time() - start_time
        
        # Create result object
        from .optimizer_result import OptimizerResult
        return OptimizerResult(
            best_model=result["best_model"],
            best_params=result["best_params"],
            best_score=result["best_score"],
            optimization_history=result["history"],
            task_type=result["task_type"],
            execution_time=execution_time,
            node_count=1,
            trial_count=self.config.trials
        )
    
    def _ensure_compute_pool(self, session, pool_name, instance_family="CPU_X64_S", min_nodes=1, max_nodes=5):
        """Create compute pool if it doesn't exist"""
        try:
            logger.info(f"Checking if compute pool {pool_name} exists")
            result = session.sql(f"""
                CREATE COMPUTE POOL IF NOT EXISTS {pool_name}
                    MIN_NODES = {min_nodes}
                    MAX_NODES = {max_nodes}
                    INSTANCE_FAMILY = {instance_family}
            """).collect()
            logger.info(f"Compute pool status: {result[0][0]}")
        except Exception as e:
            logger.warning(f"Error creating compute pool: {e}")
    
    def _optimize_remote_distributed(self, df, target_col):
        """Multi-node distributed execution"""
        from snowflake.ml.jobs import remote
        
        start_time = time.time()
        logger.info(f"Starting distributed optimization with {self.config.target_instances} nodes")
        
        # Get or create compute pool
        session = self._get_snowflake_session()
        compute_pool = self.config.compute_pool
        if compute_pool:
            logger.info(f"Using compute pool: {compute_pool}")
        else:
            compute_pool = "SNOWFLAKEML_OPTIMIZE_POOL"
            logger.info(f"No compute pool specified, using default: {compute_pool}")
            self._ensure_compute_pool(
                session, 
                compute_pool,
                min_nodes=max(2, self.config.target_instances // 2),
                max_nodes=self.config.target_instances * 2
            )
        
        @remote(
            compute_pool=compute_pool,
            target_instances=self.config.target_instances,
            min_instances=self.config.min_instances,
            stage_name="optimization_stage"
        )
        def distributed_optimize():
            # Import Ray and set up distributed execution
            import ray
            ray.init(address="auto", ignore_reinit_error=True)
            
            # Set up logging
            import logging
            remote_logger = logging.getLogger("snowflake.ml.optimize")
            remote_logger.setLevel(logging.INFO)
            
            # Get node information
            nodes_info = ray.nodes()
            remote_logger.info(f"Distributed optimization with {len(nodes_info)} nodes")
            
            # Use Snowflake's Distributed Modeling Classes
            from snowflake.ml.modeling.distributors.xgboost import XGBEstimator, XGBScalingConfig
            from snowflake.ml.data.data_connector import DataConnector
            from snowflake.snowpark.context import get_active_session
            
            # Get active session
            remote_session = get_active_session()
            remote_logger.info(f"Remote session active: {remote_session.get_current_database()}.{remote_session.get_current_schema()}")
            
            # Configure distributed training
            scaling_config = XGBScalingConfig(
                num_workers=len(nodes_info) - 1,  # All nodes except head
                use_gpu=False
            )
            
            # Configure model params
            params = {
                "eta": 0.1,
                "max_depth": 8,
                "min_child_weight": 100,
                "tree_method": "hist",
            }
            
            # Detect task type from target column
            import pandas as pd
            sample = df.limit(100).select(target_col).to_pandas()
            unique_values = len(sample[target_col].unique())
            is_regression = unique_values > 10 or target_col.startswith("reg_")
            task_type = 'regression' if is_regression else 'classification'
            objective = "reg:squarederror" if is_regression else "binary:logistic"
            
            remote_logger.info(f"Task type detected: {task_type}, objective: {objective}")
            
            # Create distributed estimator
            estimator = XGBEstimator(
                n_estimators=self.config.trials,
                objective=objective,
                params=params,
                scaling_config=scaling_config,
            )
            
            # Train using Snowflake's distributed API
            remote_logger.info("Starting distributed training")
            start = time.time()
            dc = DataConnector.from_dataframe(df)
            model = estimator.fit(
                dc, 
                input_cols=[c for c in df.columns if c != target_col], 
                label_col=target_col
            )
            
            execution_time = time.time() - start
            remote_logger.info(f"Training completed in {execution_time:.2f} seconds")
            
            # Get model metrics
            if hasattr(model, 'score'):
                score = model.score(dc, label_col=target_col)
                remote_logger.info(f"Model score: {score:.4f}")
            else:
                score = 0.0
            
            # Return results
            return {
                "model": model,
                "params": params,
                "score": score,
                "task_type": task_type,
                "execution_time": execution_time,
                "node_count": len(nodes_info)
            }
            
        # Start the job
        logger.info("Submitting distributed optimization job")
        job = distributed_optimize()
        job_id = job.id
        logger.info(f"Job submitted with ID: {job_id}")
        
        # Wait for job to complete with status updates
        logger.info("Waiting for job to complete...")
        status = "UNKNOWN"
        while status not in ["DONE", "FAILED", "CANCELLED"]:
            status = job.status
            logger.info(f"Job status: {status}")
            if status == "RUNNING":
                logger.debug("Job is running - fetching logs")
                logs = job.get_logs()
                if logs:
                    for line in logs.split('\n')[-5:]:  # Show last few log lines
                        if '[INFO]' in line and 'snowflake.ml.optimize' in line:
                            logger.info(f"Remote: {line.split('snowflake.ml.optimize - ')[1] if 'snowflake.ml.optimize - ' in line else line}")
            time.sleep(10)
        
        if status == "FAILED":
            logger.error(f"Job failed: {job.status}")
            logger.error("Job logs:")
            logger.error(job.get_logs())
            raise RuntimeError(f"Distributed optimization job failed: {job.id}")
        
        # Get results
        logger.info("Job completed - retrieving results")
        result = job.wait_for_completion()
        
        # Calculate execution time
        execution_time = time.time() - start_time
        
        # Create result object
        from .optimizer_result import OptimizerResult
        return OptimizerResult(
            best_model=result["model"],
            best_params=result["params"],
            best_score=result["score"],
            task_type=result["task_type"],
            execution_time=execution_time,
            node_count=result["node_count"],
            trial_count=self.config.trials
        )
    
    def _optimize_distributed(self, dataset):
        """Ray dataset distributed execution"""
        from snowflake.ml.jobs import remote
        
        start_time = time.time()
        logger.info(f"Starting Ray dataset optimization with {self.config.target_instances} nodes")
        
        # Get or create compute pool
        session = self._get_snowflake_session()
        compute_pool = self.config.compute_pool
        if compute_pool:
            logger.info(f"Using compute pool: {compute_pool}")
        else:
            compute_pool = "SNOWFLAKEML_OPTIMIZE_POOL"
            logger.info(f"No compute pool specified, using default: {compute_pool}")
            self._ensure_compute_pool(
                session, 
                compute_pool,
                min_nodes=max(2, self.config.target_instances // 2),
                max_nodes=self.config.target_instances * 2
            )
        
        @remote(
            compute_pool=compute_pool,
            target_instances=self.config.target_instances,
            min_instances=self.config.min_instances,
            stage_name="optimization_stage"
        )
        def ray_optimize():
            import ray
            ray.init(address="auto", ignore_reinit_error=True)
            
            # Set up logging
            import logging
            remote_logger = logging.getLogger("snowflake.ml.optimize")
            remote_logger.setLevel(logging.INFO)
            
            # Get node information
            nodes_info = ray.nodes()
            remote_logger.info(f"Ray optimization with {len(nodes_info)} nodes")
            remote_logger.info(f"Dataset: {dataset}")
            
            # Execute distributed training directly on the Ray dataset
            # Implementation depends on the structure of the Ray dataset
            
            # Example implementation for tabular data
            from snowflake.ml.modeling.distributors.xgboost import XGBEstimator, XGBScalingConfig
            
            # Configure scaling for the available nodes
            scaling_config = XGBScalingConfig(
                num_workers=len(nodes_info) - 1
            )
            
            # Not fully implemented yet
            return "Ray dataset optimization not fully implemented"
        
        # Start the job
        logger.info("Submitting Ray dataset optimization job")
        job = ray_optimize()
        
        # Wait for job completion
        logger.info("Waiting for job to complete...")
        result = job.wait_for_completion()
        
        # Placeholder implementation - would need to be expanded based on Ray dataset structure
        from .optimizer_result import OptimizerResult
        return OptimizerResult(
            best_model=None,
            best_params={},
            best_score=0.0,
            task_type="unknown",
            execution_time=time.time() - start_time,
            node_count=self.config.target_instances,
            trial_count=0
        )
    
    def _detect_task_type(self, y):
        """Detect if regression or classification task"""
        if hasattr(y, 'nunique'):
            unique_values = y.nunique()
            if unique_values <= 10:  # Arbitrary cutoff for classification
                return 'classification'
        return 'regression' 