# SnowflakeML: Type-driven ML Optimization

SnowflakeML is an ML library providing a type-driven approach to hyperparameter optimization that automatically adapts based on input data types. It follows the FastAI principles of **making simple things simple and complex things possible**.

## Features

- **Type-based execution routing**: Local vs remote vs distributed
- **Three-level progressive API**: Simple, strategic, and expert
- **Seamless Snowflake integration**: Optimized for Snowflake Snowpark and ML Jobs
- **Extensible model registry**: Easily add new model types

## Three-Level API Design

### Simple API

Use the simplest API for the most common scenarios:

```python
from SnowflakeML.optimize import optimize

# Automatic local execution with numpy arrays
result = optimize(X, y)

# Automatic remote execution with Snowflake DataFrame
result = optimize(snowflake_df, "target_column")
```

### Strategy-based API

Choose from predefined optimization strategies:

```python
from SnowflakeML.optimize import optimize_with_strategy

# Fast optimization
result = optimize_with_strategy(X, y, strategy="fast")

# Thorough optimization
result = optimize_with_strategy(X, y, strategy="thorough")

# Distributed optimization
result = optimize_with_strategy(
    snowflake_df, 
    "target_column", 
    strategy="distributed"
)
```

### Expert API

Full control over all optimization parameters:

```python
from SnowflakeML.optimize import optimize_advanced
from SnowflakeML.execution_backend import ExecutionConfig

# Create custom configuration
config = ExecutionConfig(
    target_instances=3,
    trials=100,
    early_stopping=True,
    compute_pool="ML_POOL"
)

# Run with advanced configuration
result = optimize_advanced(
    snowflake_df,
    "target_column",
    execution_config=config,
    model='xgb_clf'
)
```

## Type-Based Execution

SnowflakeML automatically selects the optimal execution mode based on data type:

- **numpy arrays** → Local execution
- **Snowflake DataFrames** → Remote execution
- **Ray datasets** → Distributed execution

```python
# Local execution
import numpy as np
result = optimize(np.array(X), np.array(y))

# Remote execution on Snowflake
from snowflake.snowpark import Session
session = Session.builder.getOrCreate()
snowflake_df = session.table("MY_TABLE")
result = optimize(snowflake_df, "TARGET_COLUMN")

# Distributed execution with Ray
import ray.data
ray_dataset = ray.data.read_csv("large_dataset.csv")
result = optimize(ray_dataset)
```

## Snowflake Integration

SnowflakeML seamlessly integrates with Snowflake:

```python
# Use Snow CLI connection
from SnowflakeML.connections import SnowflakeConnection
connection = SnowflakeConnection.from_snow_cli("my_conn")

# Run optimization
result = optimize_with_strategy(
    connection.session.table("MY_TABLE"), 
    "TARGET", 
    strategy="distributed"
)

# Register the model in Snowflake Model Registry
model_ref = result.register_model(
    session=connection.session,
    model_name="MY_MODEL"
)
```

## Installation

```bash
pip install SnowflakeML
```

Optional dependencies:
```bash
# Install visualization tools
pip install SnowflakeML[viz]

# Install boosting models
pip install SnowflakeML[boost]
```

## Examples

See the `examples` directory for more detailed usage examples:

- `examples/optimize_with_connection.py`: Shows how to use different API levels with Snowflake connection