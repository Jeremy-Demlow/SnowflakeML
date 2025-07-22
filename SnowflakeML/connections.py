"""
Modern Snowflake connection management.
Clean, simple connection handling with dynamic behavior.
Enhanced to leverage Snow CLI configuration.
"""

from __future__ import annotations
from typing import Optional, Dict, Any, Union
from snowflake.snowpark import Session
from snowflake.snowpark.dataframe import DataFrame
from snowflake.snowpark.exceptions import SnowparkSessionException
import os
import toml
from pathlib import Path
from pydantic import BaseModel, Field
import logging
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
import warnings

# Set up logging
logger = logging.getLogger(__name__)

# Suppress Pydantic warning about schema
warnings.filterwarnings("ignore", message="Field name \"schema\" .* shadows an attribute in parent \"BaseModel\"")

class ConnectionError(Exception):
    """Raised when there's an error connecting to Snowflake"""
    pass

class ConfigurationError(Exception):
    """Raised when there's an error in configuration"""
    pass

def _load_snow_cli_config() -> Dict[str, Any]:
    """Load Snow CLI configuration from ~/.snowflake/config.toml"""
    config_path = Path.home() / ".snowflake" / "config.toml"
    
    if not config_path.exists():
        return {}
    
    try:
        with open(config_path, 'r') as f:
            config = toml.load(f)
        return config
    except Exception as e:
        logger.warning(f"Failed to load Snow CLI config: {e}")
        return {}

def _get_snow_cli_connection(connection_name: Optional[str] = None) -> Dict[str, Any]:
    """Get specific connection from Snow CLI config"""
    config = _load_snow_cli_config()
    
    if not config:
        return {}
    
    connections = config.get('connections', {})
    
    if connection_name:
        # Get specific connection
        return connections.get(connection_name, {})
    
    # Find default connection
    for name, conn_config in connections.items():
        if conn_config.get('default', False):
            return conn_config
    
    # If no default, return first connection
    if connections:
        return next(iter(connections.values()))
    
    return {}

class ConnectionConfig(BaseModel):
    """Configuration for Snowflake connection"""
    user: str
    password: Optional[str] = None
    account: str
    role: str = Field("ACCOUNTADMIN", description="Snowflake role")
    warehouse: str = Field("COMPUTE_WH", description="Default warehouse")
    database: Optional[str] = Field(None, description="Default database")
    schema: Optional[str] = Field(None, description="Default schema")
    private_key_path: Optional[str] = None
    private_key_pem: Optional[str] = None
    authenticator: Optional[str] = None
    create_db_if_missing: bool = Field(True, description="Create database/schema if they don't exist")
    
    @classmethod
    def from_env(cls) -> ConnectionConfig:
        """Create connection config from environment variables"""
        config = {}
        env_vars = {
            'SNOWFLAKE_ACCOUNT': 'account',
            'SNOWFLAKE_USER': 'user',
            'SNOWFLAKE_PASSWORD': 'password',
            'SNOWFLAKE_ROLE': 'role',
            'SNOWFLAKE_WAREHOUSE': 'warehouse',
            'SNOWFLAKE_DATABASE': 'database',
            'SNOWFLAKE_SCHEMA': 'schema',
            'SNOWFLAKE_PRIVATE_KEY_PATH': 'private_key_path',
            'SNOWFLAKE_AUTHENTICATOR': 'authenticator',
            'SNOWFLAKE_CREATE_DB_IF_MISSING': 'create_db_if_missing'
        }

        for env_var, config_key in env_vars.items():
            if value := os.getenv(env_var):
                # Handle boolean conversion for create_db_if_missing
                if config_key == 'create_db_if_missing':
                    config[config_key] = value.lower() in ('true', '1', 'yes', 'on')
                else:
                    config[config_key] = value
                
        # Ensure required fields are present
        if 'account' not in config:
            raise ConfigurationError("Missing required environment variable: SNOWFLAKE_ACCOUNT")
        if 'user' not in config:
            raise ConfigurationError("Missing required environment variable: SNOWFLAKE_USER")
        
        # Check that at least one authentication method is provided
        if not any(k in config for k in ['password', 'private_key_path', 'authenticator']):
            raise ConfigurationError("No authentication method provided via environment variables")
            
        return cls(**config)
    
    @classmethod
    def from_snow_cli(cls, connection_name: Optional[str] = None) -> ConnectionConfig:
        """Create connection config from Snow CLI configuration
        
        Args:
            connection_name: Name of connection in Snow CLI config, or None for default
        """
        # Get Snow CLI connection
        snow_config = _get_snow_cli_connection(connection_name)
        
        if not snow_config:
            if connection_name:
                raise ConfigurationError(f"Snow CLI connection '{connection_name}' not found")
            else:
                raise ConfigurationError("No Snow CLI connections found or default connection not set")
        
        # Map Snow CLI config to our config
        config = {}
        
        # Required fields
        if 'account' in snow_config:
            config['account'] = snow_config['account']
        if 'user' in snow_config:
            config['user'] = snow_config['user']
        if 'password' in snow_config:
            config['password'] = snow_config['password']
        
        # Optional fields with defaults
        config['role'] = snow_config.get('role', 'ACCOUNTADMIN')
        config['warehouse'] = snow_config.get('warehouse', 'COMPUTE_WH')
        config['database'] = snow_config.get('database')
        config['schema'] = snow_config.get('schema')
        
        # Authentication
        if 'authenticator' in snow_config and snow_config['authenticator'] != 'oauth':
            config['authenticator'] = snow_config['authenticator']
        if 'private_key_path' in snow_config:
            config['private_key_path'] = snow_config['private_key_path']
        if 'token' in snow_config:
            # PAT tokens are used as passwords, not with oauth authenticator
            config['password'] = snow_config['token']
        
        # Ensure required fields are present
        if 'account' not in config:
            raise ConfigurationError("Missing required field 'account' in Snow CLI connection")
        if 'user' not in config:
            raise ConfigurationError("Missing required field 'user' in Snow CLI connection")
            
        return cls(**config)
    
    @classmethod
    def from_env_or_snow_cli(cls, connection_name: Optional[str] = None) -> ConnectionConfig:
        """Create connection config from environment variables or Snow CLI config
        
        Tries environment variables first, then falls back to Snow CLI config
        """
        try:
            # Try environment variables first
            return cls.from_env()
        except ConfigurationError:
            # Fall back to Snow CLI config
            return cls.from_snow_cli(connection_name)

class SnowflakeConnection:
    """Manages Snowflake connection with dynamic behavior for data exploration."""
    
    def __init__(self, session: Session, config: Optional[ConnectionConfig] = None):
        """Initialize Snowflake connection"""
        self.session = session
        self._config = config
        self.warehouse = session.get_current_warehouse()
        self.database = session.get_current_database()
        self.schema = session.get_current_schema()
        
        logger.debug(f"Connection initialized: {self.database}.{self.schema}")
        
    @classmethod
    def from_config(cls, config: ConnectionConfig) -> SnowflakeConnection:
        """Create connection from config object. The main way to create connections."""
        try:
            # Prepare connection parameters
            params = {
                "account": config.account,
                "user": config.user,
                "role": config.role,
                "warehouse": config.warehouse,
            }

            if config.database:
                params["database"] = config.database
            if config.schema:
                params["schema"] = config.schema
            
            # Select authentication method
            if config.authenticator:
                params["authenticator"] = config.authenticator
            elif config.private_key_path or config.private_key_pem:
                # Load and format private key
                if config.private_key_pem:
                    key_data = config.private_key_pem.encode()
                elif config.private_key_path:
                    with open(config.private_key_path, "rb") as key_file:
                        key_data = key_file.read()
                        
                p_key = serialization.load_pem_private_key(
                    key_data,
                    password=None,
                    backend=default_backend()
                )
                params["private_key"] = p_key.private_bytes(
                    encoding=serialization.Encoding.DER,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption()
                )
            elif config.password:
                params["password"] = config.password
            else:
                raise ConnectionError(
                    "No authentication method provided. Please provide either "
                    "authenticator, private_key, or password."
                )

            # Create session
            session = Session.builder.configs(params).create()
            
            # Ensure database and schema exist and are set (if enabled)
            if config.database:
                try:
                    if config.create_db_if_missing:
                        logger.debug(f"Ensuring database {config.database} exists")
                        session.sql(f"CREATE DATABASE IF NOT EXISTS {config.database}").collect()
                    
                    session.sql(f"USE DATABASE {config.database}").collect()
                    
                    if config.schema:
                        if config.create_db_if_missing:
                            logger.debug(f"Ensuring schema {config.schema} exists")
                            session.sql(f"CREATE SCHEMA IF NOT EXISTS {config.schema}").collect()
                        
                        session.sql(f"USE SCHEMA {config.schema}").collect()
                        
                except Exception as db_error:
                    if config.create_db_if_missing:
                        logger.warning(f"Database/schema setup warning: {db_error}")
                    else:
                        logger.debug(f"Using existing database/schema: {db_error}")
                        # Try to use them anyway - they might exist
                        try:
                            session.sql(f"USE DATABASE {config.database}").collect()
                            if config.schema:
                                session.sql(f"USE SCHEMA {config.schema}").collect()
                        except Exception as use_error:
                            raise ConnectionError(f"Database/schema not found and create_db_if_missing=False: {use_error}")
                
            return cls(session, config=config)
        except Exception as e:
            raise ConnectionError(f"Failed to create session: {str(e)}")
    
    @classmethod 
    def from_env(cls) -> SnowflakeConnection:
        """Create connection from environment variables."""
        return cls.from_config(ConnectionConfig.from_env())
    
    @classmethod
    def from_snow_cli(cls, connection_name: Optional[str] = None) -> SnowflakeConnection:
        """Create connection from Snow CLI configuration
        
        Args:
            connection_name: Name of connection in Snow CLI config, or None for default
        """
        return cls.from_config(ConnectionConfig.from_snow_cli(connection_name))
    
    @classmethod
    def from_env_or_snow_cli(cls, connection_name: Optional[str] = None) -> SnowflakeConnection:
        """Create connection from environment or Snow CLI config (tries env first)"""
        return cls.from_config(ConnectionConfig.from_env_or_snow_cli(connection_name))
    
    def sql(self, query: str) -> DataFrame:
        """
        Execute SQL query - returns Snowpark DataFrame for exploration.
        This is the main method you'll use - supports .show(), .to_pandas(), etc.
        
        Examples:
            df = conn.sql("SELECT * FROM table")
            df.show()  # Display results
            pandas_df = df.to_pandas()  # Convert to pandas
            df.count()  # Get row count
        """
        try:
            return self.session.sql(query)
        except Exception as e:
            raise ConnectionError(f"Query execution failed: {str(e)}")
    
    def execute_query(self, query: str) -> DataFrame:
        """Alias for sql() - backwards compatibility"""
        return self.sql(query)
    
    def fetch(self, query: str) -> list:
        """Execute query and return collected results as list of Row objects"""
        try:
            return self.session.sql(query).collect()
        except Exception as e:
            raise ConnectionError(f"Query execution failed: {str(e)}")
    
    def execute(self, query: str) -> None:
        """Execute query without returning results (for DDL, DML statements)"""
        try:
            self.session.sql(query).collect()
        except Exception as e:
            raise ConnectionError(f"Query execution failed: {str(e)}")
    
    def test_connection(self) -> bool:
        """Test if connection is working"""
        try:
            result = self.fetch('SELECT CURRENT_DATABASE(), CURRENT_SCHEMA(), CURRENT_WAREHOUSE()')
            if result:
                db, schema, warehouse = result[0]
                logger.info(f"Connection test successful: {db}.{schema} on {warehouse}")
            return True
        except Exception as e:
            logger.error(f"Connection test failed: {str(e)}")
            return False
    
    # Dynamic properties for easy exploration
    @property
    def current_database(self) -> str:
        """Get current database"""
        return self.session.get_current_database()
    
    @property  
    def current_schema(self) -> str:
        """Get current schema"""
        return self.session.get_current_schema()
    
    @property
    def current_warehouse(self) -> str:
        """Get current warehouse"""
        return self.session.get_current_warehouse()
    
    def list_tables(self, pattern: Optional[str] = None, schema: Optional[str] = None) -> DataFrame:
        """
        List tables with optional pattern matching OR schema filtering (not both).
        
        Args:
            pattern: Pattern to match table names (e.g., 'fact_%', '%subset%')
            schema: Schema to search in (defaults to current schema)
            
        Examples:
            conn.list_tables()  # All tables
            conn.list_tables('%subset%')  # Tables containing 'subset'
            conn.list_tables('ORDERS%')   # Tables starting with 'ORDERS'
            conn.list_tables(schema='PUBLIC')  # All tables in PUBLIC schema
        """
        if pattern:
            query = f"SHOW TABLES LIKE '{pattern}'"
        elif schema:
            query = f"SHOW TABLES IN SCHEMA {schema}"
        else:
            query = "SHOW TABLES"
            
        return self.sql(query)
    
    def describe_table(self, table_name: str) -> DataFrame:
        """Describe table structure"""
        return self.sql(f"DESCRIBE TABLE {table_name}")
    
    def quick_sample(self, table_name: str, n: int = 5) -> DataFrame:
        """Quick sample of table for exploration"""
        return self.sql(f"SELECT * FROM {table_name} SAMPLE ({n} ROWS)")
    
    def get_ddl(self, object_name: str, object_type: str = "TABLE") -> str:
        """
        Get DDL (Data Definition Language) for a database object.
        
        Args:
            object_name: Name of the object (table, view, etc.)
            object_type: Type of object (TABLE, VIEW, SEQUENCE, etc.)
            
        Returns:
            DDL statement as string
            
        Examples:
            ddl = conn.get_ddl("my_table")
            ddl = conn.get_ddl("my_view", "VIEW")
        """
        try:
            result = self.fetch(f"SELECT GET_DDL('{object_type}', '{object_name}') as ddl")
            return result[0]["DDL"] if result else ""
        except Exception as e:
            raise ConnectionError(f"Failed to get DDL for {object_type} {object_name}: {str(e)}")
    
    def table_info(self, table_name: str) -> dict:
        """Get quick info about a table"""
        try:
            count_df = self.sql(f"SELECT COUNT(*) as row_count FROM {table_name}")
            desc_df = self.describe_table(table_name)
            
            return {
                "row_count": count_df.collect()[0]["ROW_COUNT"],
                "columns": [row["name"] for row in desc_df.collect()],
                "column_count": desc_df.count()
            }
        except Exception as e:
            raise ConnectionError(f"Failed to get table info for {table_name}: {str(e)}")
            
    def close(self):
        """Close the Snowflake session"""
        try:
            if self.session:
                self.session.close()
                logger.debug("Session closed")
        except Exception as e:
            logger.error(f"Error closing connection: {str(e)}")
            
    def __enter__(self):
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        
    def __repr__(self) -> str:
        return f"SnowflakeConnection(database={self.current_database}, schema={self.current_schema}, warehouse={self.current_warehouse})" 