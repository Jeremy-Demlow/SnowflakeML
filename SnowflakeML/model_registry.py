"""
Model Registry - Extensible Model Definitions
Clean separation of model configurations from core logic
"""

import numpy as np
from typing import Dict, Tuple, Any, Callable, Optional
from dataclasses import dataclass
from abc import ABC, abstractmethod

from hyperopt import hp


@dataclass
class ModelDefinition:
    """Clean model definition with metadata"""
    model_cls: type
    param_space: Dict[str, Any]
    name: str
    task_types: list  # ['classification', 'regression', 'both']
    requires: list  # Required packages
    description: str


class ModelProvider(ABC):
    """Abstract base for model providers"""
    
    @abstractmethod
    def get_model_definition(self) -> ModelDefinition:
        """Return model definition"""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if model dependencies are available"""
        pass


class ModelRegistry:
    """
    Extensible model registry using plugin pattern
    
    Benefits:
    - Easy to add new models
    - Clear separation of concerns
    - Dependency checking
    - Auto task-type detection
    """
    
    _providers: Dict[str, ModelProvider] = {}
    
    @classmethod
    def register(cls, name: str):
        """Decorator to register model providers"""
        def decorator(provider_cls):
            if not issubclass(provider_cls, ModelProvider):
                raise ValueError(f"Provider must inherit from ModelProvider")
            cls._providers[name] = provider_cls()
            return provider_cls
        return decorator
    
    @classmethod
    def get_model(cls, name: str) -> ModelDefinition:
        """Get model definition by name"""
        if name not in cls._providers:
            available = list(cls._providers.keys())
            raise ValueError(f"Model '{name}' not found. Available: {available}")
        
        provider = cls._providers[name]
        
        if not provider.is_available():
            definition = provider.get_model_definition()
            raise ImportError(
                f"Model '{name}' requires: pip install {' '.join(definition.requires)}"
            )
        
        return provider.get_model_definition()
    
    @classmethod
    def list_models(cls, task_type: Optional[str] = None) -> Dict[str, str]:
        """List available models with descriptions"""
        models = {}
        for name, provider in cls._providers.items():
            try:
                definition = provider.get_model_definition()
                if task_type is None or task_type in definition.task_types or 'both' in definition.task_types:
                    status = "✓" if provider.is_available() else "✗"
                    models[name] = f"{status} {definition.description}"
            except Exception:
                models[name] = "✗ Error loading model"
        return models
    
    @classmethod
    def auto_select(cls, task_type: str) -> str:
        """Auto-select best available model for task type"""
        # Priority order for different tasks
        priorities = {
            'binary_classification': ['xgb_clf', 'lgb_clf', 'rf_clf'],
            'multiclass_classification': ['xgb_clf', 'lgb_clf', 'rf_clf'],
            'regression': ['xgb_reg', 'lgb_reg', 'rf_reg']
        }
        
        candidates = priorities.get(task_type, ['rf_clf', 'rf_reg'])
        
        for model_name in candidates:
            if model_name in cls._providers:
                provider = cls._providers[model_name]
                if provider.is_available():
                    definition = provider.get_model_definition()
                    if task_type.endswith('classification') and 'classification' in definition.task_types:
                        return model_name
                    elif task_type == 'regression' and 'regression' in definition.task_types:
                        return model_name
        
        # Fallback to RandomForest (always available)
        return 'rf_clf' if 'classification' in task_type else 'rf_reg'


@ModelRegistry.register('rf_clf')
class RandomForestClassifierProvider(ModelProvider):
    def get_model_definition(self) -> ModelDefinition:
        from sklearn.ensemble import RandomForestClassifier
        
        return ModelDefinition(
            model_cls=RandomForestClassifier,
            param_space={
                'n_estimators': hp.choice('n_estimators', [50, 100, 200, 300]),
                'max_depth': hp.choice('max_depth', [5, 10, 15, 20, None]),
                'min_samples_split': hp.uniform('min_samples_split', 0.01, 0.1),
                'min_samples_leaf': hp.choice('min_samples_leaf', [1, 2, 4]),
                'max_features': hp.choice('max_features', ['sqrt', 'log2', None]),
                'bootstrap': hp.choice('bootstrap', [True, False])
            },
            name='Random Forest Classifier',
            task_types=['classification'],
            requires=['scikit-learn'],
            description='Random Forest for classification - reliable baseline'
        )
    
    def is_available(self) -> bool:
        try:
            from sklearn.ensemble import RandomForestClassifier
            return True
        except ImportError:
            return False


@ModelRegistry.register('rf_reg')
class RandomForestRegressorProvider(ModelProvider):
    def get_model_definition(self) -> ModelDefinition:
        from sklearn.ensemble import RandomForestRegressor
        
        return ModelDefinition(
            model_cls=RandomForestRegressor,
            param_space={
                'n_estimators': hp.choice('n_estimators', [50, 100, 200, 300]),
                'max_depth': hp.choice('max_depth', [5, 10, 15, 20, None]),
                'min_samples_split': hp.uniform('min_samples_split', 0.01, 0.1),
                'min_samples_leaf': hp.choice('min_samples_leaf', [1, 2, 4]),
                'max_features': hp.choice('max_features', ['sqrt', 'log2', None]),
                'bootstrap': hp.choice('bootstrap', [True, False])
            },
            name='Random Forest Regressor',
            task_types=['regression'],
            requires=['scikit-learn'],
            description='Random Forest for regression - reliable baseline'
        )
    
    def is_available(self) -> bool:
        try:
            from sklearn.ensemble import RandomForestRegressor
            return True
        except ImportError:
            return False


@ModelRegistry.register('xgb_clf')
class XGBoostClassifierProvider(ModelProvider):
    def get_model_definition(self) -> ModelDefinition:
        from xgboost import XGBClassifier
        
        return ModelDefinition(
            model_cls=XGBClassifier,
            param_space={
                'max_depth': hp.choice('max_depth', [3, 5, 7, 9]),
                'learning_rate': hp.loguniform('learning_rate', np.log(0.01), np.log(0.3)),
                'n_estimators': hp.choice('n_estimators', [100, 200, 300, 500]),
                'subsample': hp.uniform('subsample', 0.6, 1.0),
                'colsample_bytree': hp.uniform('colsample_bytree', 0.6, 1.0),
                'reg_alpha': hp.loguniform('reg_alpha', np.log(1e-8), np.log(10)),
                'reg_lambda': hp.loguniform('reg_lambda', np.log(1e-8), np.log(10)),
                'objective': 'binary:logistic',
                'eval_metric': 'logloss',
                'verbosity': 0
            },
            name='XGBoost Classifier',
            task_types=['classification'],
            requires=['xgboost'],
            description='XGBoost for classification - high performance gradient boosting'
        )
    
    def is_available(self) -> bool:
        try:
            from xgboost import XGBClassifier
            return True
        except ImportError:
            return False


@ModelRegistry.register('xgb_reg')
class XGBoostRegressorProvider(ModelProvider):
    def get_model_definition(self) -> ModelDefinition:
        from xgboost import XGBRegressor
        
        return ModelDefinition(
            model_cls=XGBRegressor,
            param_space={
                'max_depth': hp.choice('max_depth', [3, 5, 7, 9]),
                'learning_rate': hp.loguniform('learning_rate', np.log(0.01), np.log(0.3)),
                'n_estimators': hp.choice('n_estimators', [100, 200, 300, 500]),
                'subsample': hp.uniform('subsample', 0.6, 1.0),
                'colsample_bytree': hp.uniform('colsample_bytree', 0.6, 1.0),
                'reg_alpha': hp.loguniform('reg_alpha', np.log(1e-8), np.log(10)),
                'reg_lambda': hp.loguniform('reg_lambda', np.log(1e-8), np.log(10)),
                'objective': 'reg:squarederror',
                'verbosity': 0
            },
            name='XGBoost Regressor',
            task_types=['regression'],
            requires=['xgboost'],
            description='XGBoost for regression - high performance gradient boosting'
        )
    
    def is_available(self) -> bool:
        try:
            from xgboost import XGBRegressor
            return True
        except ImportError:
            return False


@ModelRegistry.register('lgb_clf')
class LightGBMClassifierProvider(ModelProvider):
    def get_model_definition(self) -> ModelDefinition:
        from lightgbm import LGBMClassifier
        
        return ModelDefinition(
            model_cls=LGBMClassifier,
            param_space={
                'num_leaves': hp.choice('num_leaves', [31, 50, 100, 150]),
                'learning_rate': hp.loguniform('learning_rate', np.log(0.01), np.log(0.3)),
                'feature_fraction': hp.uniform('feature_fraction', 0.6, 1.0),
                'bagging_fraction': hp.uniform('bagging_fraction', 0.6, 1.0),
                'bagging_freq': hp.choice('bagging_freq', [1, 5, 10]),
                'min_child_samples': hp.choice('min_child_samples', [5, 10, 20, 50]),
                'reg_alpha': hp.loguniform('reg_alpha', np.log(1e-8), np.log(10)),
                'reg_lambda': hp.loguniform('reg_lambda', np.log(1e-8), np.log(10)),
                'n_estimators': hp.choice('n_estimators', [100, 200, 300, 500]),
                'objective': 'binary',
                'verbosity': -1,
                'force_col_wise': True
            },
            name='LightGBM Classifier',
            task_types=['classification'],
            requires=['lightgbm'],
            description='LightGBM for classification - fast gradient boosting'
        )
    
    def is_available(self) -> bool:
        try:
            from lightgbm import LGBMClassifier
            return True
        except ImportError:
            return False


@ModelRegistry.register('lgb_reg')
class LightGBMRegressorProvider(ModelProvider):
    def get_model_definition(self) -> ModelDefinition:
        from lightgbm import LGBMRegressor
        
        return ModelDefinition(
            model_cls=LGBMRegressor,
            param_space={
                'num_leaves': hp.choice('num_leaves', [31, 50, 100, 150]),
                'learning_rate': hp.loguniform('learning_rate', np.log(0.01), np.log(0.3)),
                'feature_fraction': hp.uniform('feature_fraction', 0.6, 1.0),
                'bagging_fraction': hp.uniform('bagging_fraction', 0.6, 1.0),
                'bagging_freq': hp.choice('bagging_freq', [1, 5, 10]),
                'min_child_samples': hp.choice('min_child_samples', [5, 10, 20, 50]),
                'reg_alpha': hp.loguniform('reg_alpha', np.log(1e-8), np.log(10)),
                'reg_lambda': hp.loguniform('reg_lambda', np.log(1e-8), np.log(10)),
                'n_estimators': hp.choice('n_estimators', [100, 200, 300, 500]),
                'objective': 'regression',
                'verbosity': -1,
                'force_col_wise': True
            },
            name='LightGBM Regressor',
            task_types=['regression'],
            requires=['lightgbm'],
            description='LightGBM for regression - fast gradient boosting'
        )
    
    def is_available(self) -> bool:
        try:
            from lightgbm import LGBMRegressor
            return True
        except ImportError:
            return False

def detect_task_type(y: np.ndarray) -> str:
    """Detect task type from target variable"""
    unique_vals = len(np.unique(y))
    
    if np.issubdtype(y.dtype, np.number) and unique_vals > 10:
        return 'regression'
    elif unique_vals == 2:
        return 'binary_classification'
    else:
        return 'multiclass_classification'


def get_model_for_task(task_type: str, model_preference: Optional[str] = None) -> ModelDefinition:
    """Get best model for a given task type"""
    if model_preference:
        # User specified a model
        return ModelRegistry.get_model(model_preference)
    else:
        # Auto-select best available model
        model_name = ModelRegistry.auto_select(task_type)
        return ModelRegistry.get_model(model_name)


if __name__ == "__main__":
    # Example 1: List available models
    print("Available Models:")
    models = ModelRegistry.list_models()
    for name, description in models.items():
        print(f"  {name}: {description}")
    
    print("\nClassification Models:")
    clf_models = ModelRegistry.list_models('classification')
    for name, description in clf_models.items():
        print(f"  {name}: {description}")
    
    # Example 2: Get model definition
    try:
        model_def = ModelRegistry.get_model('rf_clf')
        print(f"\nModel: {model_def.name}")
        print(f"Task types: {model_def.task_types}")
        print(f"Parameters: {list(model_def.param_space.keys())}")
    except Exception as e:
        print(f"Error: {e}")
    
    # Example 3: Auto-selection
    task_type = 'binary_classification'
    auto_model = ModelRegistry.auto_select(task_type)
    print(f"\nAuto-selected for {task_type}: {auto_model}")
    
    # Example 4: Adding custom model (extensibility)
    @ModelRegistry.register('custom_svm')
    class CustomSVMProvider(ModelProvider):
        def get_model_definition(self) -> ModelDefinition:
            from sklearn.svm import SVC
            
            return ModelDefinition(
                model_cls=SVC,
                param_space={
                    'C': hp.loguniform('C', np.log(0.1), np.log(100)),
                    'gamma': hp.choice('gamma', ['scale', 'auto']),
                    'kernel': hp.choice('kernel', ['rbf', 'poly', 'sigmoid'])
                },
                name='Support Vector Machine',
                task_types=['classification'],
                requires=['scikit-learn'],
                description='SVM for classification - good for small datasets'
            )
        
        def is_available(self) -> bool:
            try:
                from sklearn.svm import SVC
                return True
            except ImportError:
                return False
    
    print(f"\nAfter adding custom model:")
    print(f"Available models: {list(ModelRegistry.list_models().keys())}")
    
    print("\nModel registry ready!")