"""Configuration loader for Wealth-Ops.

Loads configuration from environment variables with sensible defaults.
"""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    """Application configuration loaded from environment variables.

    Attributes:
        aws_region: AWS region for all services.
        s3_bucket: S3 bucket name for data storage.
        config_table: DynamoDB table for asset configuration.
        ledger_table: DynamoDB table for trade history.
        portfolio_table: DynamoDB table for current positions.
        system_table: DynamoDB table for system state.
        tiingo_api_key: API key for Tiingo market data.
        fred_api_key: API key for FRED economic data.
        telegram_bot_token: Telegram bot authentication token.
        telegram_chat_id: Target Telegram chat for notifications.
        environment: Current environment (dev/prod).
    """

    aws_region: str
    s3_bucket: str
    config_table: str
    ledger_table: str
    portfolio_table: str
    system_table: str
    tiingo_api_key: str
    fred_api_key: str
    telegram_bot_token: str
    telegram_chat_id: str
    environment: str


def load_config() -> Config:
    """Load configuration from environment variables.

    Returns:
        Config object with all settings.

    Raises:
        ValueError: If required environment variables are missing.
    """
    env = os.getenv("ENVIRONMENT", "dev")

    return Config(
        aws_region=os.getenv("AWS_REGION", "us-east-1"),
        s3_bucket=os.getenv("S3_BUCKET", f"wealth-ops-data-{env}"),
        config_table=os.getenv("CONFIG_TABLE", f"wealth-ops-config-{env}"),
        ledger_table=os.getenv("LEDGER_TABLE", f"wealth-ops-ledger-{env}"),
        portfolio_table=os.getenv("PORTFOLIO_TABLE", f"wealth-ops-portfolio-{env}"),
        system_table=os.getenv("SYSTEM_TABLE", f"wealth-ops-system-{env}"),
        tiingo_api_key=os.getenv("TIINGO_API_KEY", ""),
        fred_api_key=os.getenv("FRED_API_KEY", ""),
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
        telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID", ""),
        environment=env,
    )
