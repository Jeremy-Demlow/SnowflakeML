from typing import Dict, Any, Callable, Optional, Union, List
import numpy as np
import pandas as pd
from sklearn import metrics
from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.multioutput import MultiOutputClassifier
import logging

# Snowflake ML imports
from snowflake.ml.data.data_connector import DataConnector
from snowflake.ml.modeling import tune
from snowflake.ml.modeling.tune import get_tuner_context, TunerConfig
from snowflake.ml.modeling.preprocessing import LabelEncoder
from entities import search_algorithm

# Connection management
from connections import SnowflakeConnection, ConnectionConfig, ConfigurationError, ConnectionError

# Optional dependencies - fail gracefully
try:
    from xgboost import XGBClassifier, XGBRegressor
    HAS_XGB = True
except ImportError:
    HAS_XGB = False

try:
    from lightgbm import LGBMClassifier, LGBMRegressor
    HAS_LGBM = True
except ImportError:
    HAS_LGBM = False

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def detect_task_type(y):
    """Automatically detect the task type from target variable"""
    if isinstance(y, pd.DataFrame):
        y_values = y.values.flatten() if y.shape[1] == 1 else y.values
    else:
        y_values = y
        
    if len(y_values.shape) == 1:
        n_unique = len(np.unique(y_values))
        if np.issubdtype(y_values.dtype, np.number) and n_unique > 10:
            return 'regression'
        elif n_unique == 2:
            return 'binary_classification'
        else:
            return 'multiclass_classification'
    else:
        # Multi-dimensional target
        return 'multilabel_classification'


class SnowflakeHyperOptimizer:
    """Snowflake ML compatible hyperparameter optimizer"""
    
    def __init__(self, task='auto', model_type='auto', metric=None, 
                 max_evals=50, search_alg_type='bayesian', random_state=42,
                 connection=None, connection_config=None):
        self.task = task
        self.model_type = model_type
        self.metric = metric
        self.max_evals = max_evals
        self.search_alg_type = search_alg_type
        self.random_state = random_state
        
        # Connection handling - flexible approach
        if connection is not None:
            self.connection = connection
        elif connection_config is not None:
            self.connection = SnowflakeConnection.from_config(connection_config)
        else:
            # Try to create connection from environment or Snow CLI
            try:
                self.connection = SnowflakeConnection.from_env_or_snow_cli()
                logger.info("Created connection from environment/Snow CLI config")
            except Exception as e:
                logger.warning(f"Could not auto-create connection: {e}")
                raise ConnectionError(
                    "No connection provided. Please provide either:\n"
                    "1. connection parameter (SnowflakeConnection object)\n" 
                    "2. connection_config parameter (ConnectionConfig object)\n"
                    "3. Set environment variables or Snow CLI config"
                )
        
        self.session = self.connection.session
        
        # State
        self.tuner_results = None
        self.fitted = False
        self.best_model = None
        
        # Will be set during fit
        self.dataset_map = None
        self.search_space = None
        self.tuner_config = None
        
    def _setup_task_and_search_space(self, y):
        """Setup task type and create search space"""
        if self.task == 'auto':
            self.task = detect_task_type(y)
            logger.info(f"Auto-detected task: {self.task}")
        
        # Create search space based on model type and task
        if self.model_type == 'auto':
            if HAS_XGB:
                self.model_type = 'xgb'
            elif HAS_LGBM:
                self.model_type = 'lgbm'
            else:
                self.model_type = 'rf'
        
        self.search_space = self._get_search_space()
        logger.info(f"Using model type: {self.model_type}")
        
    def _get_search_space(self):
        """Get search space for Snowflake ML tune"""
        if self.model_type == 'xgb' and HAS_XGB:
            return {
                'max_depth': tune.randint(3, 9),  # 3 to 8 inclusive
                'min_child_weight': tune.choice([1, 3, 5]),
                'subsample': tune.uniform(0.7, 1.0),
                'colsample_bytree': tune.uniform(0.7, 1.0),
                'n_estimators': tune.randint(50, 400),  # Will be converted to 50-399
                'learning_rate': tune.loguniform(0.01, 0.3),
                'reg_alpha': tune.loguniform(1e-8, 1.0),
                'reg_lambda': tune.loguniform(1.0, 10.0),
            }
        elif self.model_type == 'lgbm' and HAS_LGBM:
            return {
                'num_leaves': tune.choice([31, 63, 127, 255]),
                'max_depth': tune.choice([3, 5, 7, 10, -1]),
                'min_child_samples': tune.choice([20, 50, 100]),
                'subsample': tune.uniform(0.7, 1.0),
                'colsample_bytree': tune.uniform(0.7, 1.0),
                'n_estimators': tune.randint(50, 400),
                'learning_rate': tune.loguniform(0.01, 0.3),
                'reg_alpha': tune.loguniform(1e-8, 1.0),
                'reg_lambda': tune.loguniform(1.0, 10.0),
            }
        else:  # Random Forest
            return {
                'n_estimators': tune.randint(50, 250),
                'max_depth': tune.choice([5, 10, 15, 20, None]),
                'min_samples_split': tune.uniform(0.01, 0.1),
                'min_samples_leaf': tune.choice([1, 2, 4]),
                'max_features': tune.choice(['sqrt', 'log2', None]),
                'bootstrap': tune.choice([True, False]),
            }
    
    def _get_search_algorithm(self):
        """Get search algorithm for Snowflake ML"""
        if self.search_alg_type == 'bayesian':
            return search_algorithm.BayesOpt(
                utility_kwargs={"kind": "ucb", "kappa": 2.5, "xi": 0.0}
            )
        elif self.search_alg_type == 'random':
            return search_algorithm.RandomSearch(random_state=self.random_state)
        elif self.search_alg_type == 'grid':
            # For grid search, we need to modify search space to use lists
            return search_algorithm.GridSearch()
        else:
            return search_algorithm.RandomSearch(random_state=self.random_state)
    
    def _get_default_metric(self):
        """Get default metric based on task"""
        if self.metric is not None:
            return self.metric
            
        if self.task == 'regression':
            return 'mse'
        elif self.task == 'binary_classification':
            return 'auc'
        elif self.task == 'multiclass_classification':
            return 'accuracy'
        else:  # multilabel
            return 'f1_macro'
    
    def _create_training_function(self):
        """Create training function for Snowflake ML tune"""
        task = self.task
        model_type = self.model_type
        metric = self._get_default_metric()
        
        def train_func():
            tuner_context = get_tuner_context()
            config = tuner_context.get_hyper_params()
            dm = tuner_context.get_dataset_map()
            
            # Convert data to pandas for model training
            X_train = dm["x_train"].to_pandas()
            y_train = dm["y_train"].to_pandas()
            X_val = dm["x_val"].to_pandas()
            y_val = dm["y_val"].to_pandas()
            
            # Flatten y if it's a single column DataFrame
            if isinstance(y_train, pd.DataFrame) and y_train.shape[1] == 1:
                y_train = y_train.values.flatten()
            if isinstance(y_val, pd.DataFrame) and y_val.shape[1] == 1:
                y_val = y_val.values.flatten()
            
            # Convert parameters
            params = dict(config)
            if 'n_estimators' in params:
                params['n_estimators'] = int(params['n_estimators'])
            
            # Add task-specific parameters and create model
            if model_type == 'xgb' and HAS_XGB:
                params.update({
                    'random_state': 42,
                    'n_jobs': -1,
                    'verbosity': 0,
                })
                
                if task == 'regression':
                    params['objective'] = 'reg:squarederror'
                    model = XGBRegressor(**params)
                elif task == 'binary_classification':
                    params['objective'] = 'binary:logistic'
                    model = XGBClassifier(**params)
                elif task == 'multiclass_classification':
                    params['objective'] = 'multi:softprob'
                    model = XGBClassifier(**params)
                else:  # multilabel
                    params['objective'] = 'binary:logistic'
                    model = MultiOutputClassifier(XGBClassifier(**params))
                    
            elif model_type == 'lgbm' and HAS_LGBM:
                params.update({
                    'random_state': 42,
                    'n_jobs': -1,
                    'verbosity': -1,
                })
                
                if task == 'regression':
                    params['objective'] = 'regression'
                    model = LGBMRegressor(**params)
                elif task == 'binary_classification':
                    params['objective'] = 'binary'
                    model = LGBMClassifier(**params)
                elif task == 'multiclass_classification':
                    params['objective'] = 'multiclass'
                    model = LGBMClassifier(**params)
                else:  # multilabel
                    params['objective'] = 'binary'
                    model = MultiOutputClassifier(LGBMClassifier(**params))
                    
            else:  # Random Forest
                params.update({
                    'random_state': 42,
                    'n_jobs': -1,
                })
                
                if task == 'regression':
                    if 'criterion' not in params:
                        params['criterion'] = 'squared_error'
                    model = RandomForestRegressor(**params)
                else:
                    if 'criterion' not in params:
                        params['criterion'] = 'gini'
                    if task == 'multilabel_classification':
                        model = MultiOutputClassifier(RandomForestClassifier(**params))
                    else:
                        model = RandomForestClassifier(**params)
            
            # Train model
            model.fit(X_train, y_train)
            
            # Get predictions and compute metric
            if task == 'regression':
                y_pred = model.predict(X_val)
                if metric == 'mse':
                    score = metrics.mean_squared_error(y_val, y_pred)
                    # For MSE, lower is better, but tune maximizes, so negate
                    score = -score
                elif metric == 'mae':
                    score = -metrics.mean_absolute_error(y_val, y_pred)
                else:  # r2
                    score = metrics.r2_score(y_val, y_pred)
            else:
                if (task == 'binary_classification' and 
                    hasattr(model, 'predict_proba') and 
                    metric == 'auc'):
                    y_pred = model.predict_proba(X_val)[:, 1]
                    score = metrics.roc_auc_score(y_val, y_pred)
                elif (task == 'multiclass_classification' and 
                      hasattr(model, 'predict_proba') and 
                      metric == 'auc'):
                    y_pred = model.predict_proba(X_val)
                    score = metrics.roc_auc_score(y_val, y_pred, multi_class='ovr')
                else:
                    y_pred = model.predict(X_val)
                    if metric == 'accuracy':
                        score = metrics.accuracy_score(y_val, y_pred)
                    elif metric == 'f1':
                        score = metrics.f1_score(y_val, y_pred, average='binary' if task == 'binary_classification' else 'macro')
                    elif metric == 'f1_macro':
                        score = metrics.f1_score(y_val, y_pred, average='macro')
                    elif metric == 'f1_weighted':
                        score = metrics.f1_score(y_val, y_pred, average='weighted')
                    else:
                        score = metrics.accuracy_score(y_val, y_pred)
            
            # Report results
            tuner_context.report(metrics={metric: score}, model=model)
        
        return train_func
    
    def create_dataset_map(self, X_train, y_train, X_val=None, y_val=None):
        """Create dataset map for Snowflake ML"""
        # Convert to DataFrames if needed
        if not isinstance(X_train, pd.DataFrame):
            X_train = pd.DataFrame(X_train)
        if not isinstance(y_train, pd.DataFrame):
            y_train = pd.DataFrame(y_train)
            
        # Create validation set if not provided
        if X_val is None or y_val is None:
            X_train, X_val, y_train, y_val = train_test_split(
                X_train, y_train, test_size=0.2, random_state=self.random_state
            )
        
        if not isinstance(X_val, pd.DataFrame):
            X_val = pd.DataFrame(X_val)
        if not isinstance(y_val, pd.DataFrame):
            y_val = pd.DataFrame(y_val)
        
        # Create Snowflake DataFrames and DataConnectors using the connection's session
        dataset_map = {
            "x_train": DataConnector.from_dataframe(
                self.session.create_dataframe(X_train)
            ),
            "y_train": DataConnector.from_dataframe(
                self.session.create_dataframe(y_train)
            ),
            "x_val": DataConnector.from_dataframe(
                self.session.create_dataframe(X_val)
            ),
            "y_val": DataConnector.from_dataframe(
                self.session.create_dataframe(y_val)
            ),
        }
        
        return dataset_map
    
    def fit(self, X_train, y_train, X_val=None, y_val=None):
        """Fit the optimizer using Snowflake ML tune"""
        # Setup task and search space
        self._setup_task_and_search_space(y_train)
        
        # Create dataset map
        self.dataset_map = self.create_dataset_map(X_train, y_train, X_val, y_val)
        
        # Create training function
        train_func = self._create_training_function()
        
        # Setup tuner configuration
        search_alg = self._get_search_algorithm()
        metric = self._get_default_metric()
        mode = "max" if metric not in ['mse', 'mae', 'hamming'] else "min"
        
        self.tuner_config = TunerConfig(
            metric=metric,
            mode=mode,
            search_alg=search_alg,
            num_trials=self.max_evals,
            max_concurrent_trials=1,  # Can be increased for parallel execution
        )
        
        # Create and run tuner
        tuner = tune.Tuner(
            train_func=train_func,
            search_space=self.search_space,
            tuner_config=self.tuner_config,
        )
        
        logger.info(f"Starting hyperparameter optimization with {self.max_evals} trials")
        self.tuner_results = tuner.run(dataset_map=self.dataset_map)
        
        self.fitted = True
        self.best_model = self.tuner_results.best_model
        
        logger.info("Optimization completed!")
        logger.info(f"Best result: {self.tuner_results.best_result}")
        
        return self
    
    def get_model(self):
        """Get the best model"""
        if not self.fitted:
            raise ValueError("Must call fit() first")
        return self.best_model
    
    def get_best_params(self):
        """Get the best parameters"""
        if not self.fitted:
            raise ValueError("Must call fit() first")
        return dict(self.tuner_results.best_result)
    
    def get_results(self):
        """Get all results"""
        if not self.fitted:
            raise ValueError("Must call fit() first")
        return self.tuner_results.results
    
    def score(self, X_test, y_test):
        """Score the best model on test data"""
        if not self.fitted:
            raise ValueError("Must call fit() first")
            
        model = self.get_model()
        
        # Convert to pandas if needed
        if not isinstance(X_test, pd.DataFrame):
            X_test = pd.DataFrame(X_test)
        if not isinstance(y_test, pd.DataFrame):
            y_test = pd.DataFrame(y_test)
            
        # Flatten y if single column
        if y_test.shape[1] == 1:
            y_test = y_test.values.flatten()
        
        # Get predictions based on task and metric
        metric = self._get_default_metric()
        if (self.task == 'binary_classification' and 
            hasattr(model, 'predict_proba') and 
            metric == 'auc'):
            y_pred = model.predict_proba(X_test)[:, 1]
            return metrics.roc_auc_score(y_test, y_pred)
        elif (self.task == 'multiclass_classification' and 
              hasattr(model, 'predict_proba') and 
              metric == 'auc'):
            y_pred = model.predict_proba(X_test)
            return metrics.roc_auc_score(y_test, y_pred, multi_class='ovr')
        else:
            y_pred = model.predict(X_test)
            if self.task == 'regression':
                if metric == 'mse':
                    return metrics.mean_squared_error(y_test, y_pred)
                elif metric == 'mae':
                    return metrics.mean_absolute_error(y_test, y_pred)
                else:
                    return metrics.r2_score(y_test, y_pred)
            else:
                if metric == 'accuracy':
                    return metrics.accuracy_score(y_test, y_pred)
                elif metric.startswith('f1'):
                    avg = 'binary' if self.task == 'binary_classification' else 'macro'
                    return metrics.f1_score(y_test, y_pred, average=avg)
                else:
                    return metrics.accuracy_score(y_test, y_pred)


# Example usage with remote execution
def create_remote_optimizer(compute_pool="HOL_COMPUTE_POOL_HIGHMEM", 
                          stage_name="payload_stage",
                          external_access_integrations=["ALLOW_ALL_ACCESS_INTEGRATION"],
                          connection_name=None):
    """Create a remote version of the hyperparameter optimizer"""
    
    from snowflake.ml import remote
    
    @remote(
        compute_pool=compute_pool,
        stage_name=stage_name,
        external_access_integrations=external_access_integrations
    )
    def remote_hyperopt(X_train, y_train, X_val=None, y_val=None, 
                       task='auto', model_type='auto', metric=None, 
                       max_evals=50, search_alg_type='bayesian',
                       connection_name=None):
        """Remote hyperparameter optimization function"""
        # Create connection in remote environment
        try:
            if connection_name:
                connection = SnowflakeConnection.from_snow_cli(connection_name)
            else:
                connection = SnowflakeConnection.from_env_or_snow_cli()
        except Exception as e:
            logger.error(f"Failed to create connection in remote environment: {e}")
            raise
        
        optimizer = SnowflakeHyperOptimizer(
            task=task,
            model_type=model_type,
            metric=metric,
            max_evals=max_evals,
            search_alg_type=search_alg_type,
            connection=connection
        )
        
        optimizer.fit(X_train, y_train, X_val, y_val)
        
        return {
            'best_params': optimizer.get_best_params(),
            'best_score': optimizer.tuner_results.best_result[optimizer._get_default_metric()].values[0],
            'results': optimizer.get_results()
        }
    
    return remote_hyperopt


if __name__ == "__main__":
    # Example usage
    from sklearn.datasets import make_classification, make_regression
    from sklearn.model_selection import train_test_split
    
    print("=== SNOWFLAKE ML HYPERPARAMETER OPTIMIZER TEST ===")
    
    # Test binary classification
    X, y = make_classification(n_samples=1000, n_features=20, n_classes=2, random_state=42)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)


    connection = SnowflakeConnection.from_snow_cli('ml_pipeline')
    print("✓ Connected using Snow CLI configuration")
    if connection.test_connection():
        print(f"✓ Connection successful to {connection.current_database}.{connection.current_schema}")
    
    # try:
    #     # Try to create connection using the flexible approach
    #     print("Creating Snowflake connection...")
        
    #     # Option 1: From environment variables
    #     try:
    #         connection = SnowflakeConnection.from_env()
    #         print("✓ Connected using environment variables")
    #     except ConfigurationError:
    #         # Option 2: From Snow CLI config
    #         try:
    #             connection = SnowflakeConnection.from_snow_cli()
    #             print("✓ Connected using Snow CLI configuration")
    #         except ConfigurationError:
    #             # Option 3: Manual configuration (for testing)
    #             print("⚠ No auto-connection available, please configure manually")
    #             raise Exception("Please set up connection via environment variables or Snow CLI")
        
    #     # Test connection
    #     if connection.test_connection():
    #         print(f"✓ Connection successful to {connection.current_database}.{connection.current_schema}")
        
    #     optimizer = SnowflakeHyperOptimizer(
    #         task='auto',
    #         model_type='auto',
    #         max_evals=5,  # Small number for testing
    #         search_alg_type='random',  # Use random search for reliability
    #         connection=connection
    #     )
        
    #     optimizer.fit(X_train, y_train)
        
    #     best_model = optimizer.get_model()
    #     test_score = optimizer.score(X_test, y_test)
        
    #     print(f"✓ Best model: {type(best_model).__name__}")
    #     print(f"✓ Test score: {test_score:.3f}")
    #     print(f"✓ Best params: {optimizer.get_best_params()}")
        
    #     # Clean up
    #     connection.close()
        
    # except Exception as e:
    #     print(f"✗ Error: {e}")
    #     print("Note: This requires a properly configured Snowflake connection")
    #     print("Set up connection via:")
    #     print("1. Environment variables (SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, etc.)")
    #     print("2. Snow CLI configuration (~/.snowflake/config.toml)")
    #     print("3. Pass ConnectionConfig or SnowflakeConnection directly")