"""Telegram Command Handlers.

Pure functions that generate response text for each /command.
Each handler reads from DynamoDB and returns a formatted string.
"""

from datetime import date
from decimal import Decimal
from typing import Any

import boto3
from botocore.exceptions import ClientError

from src.modules.regime.filter import MarketStatus
from src.shared.config import Config
from src.shared.logger import get_logger

logger = get_logger(__name__)


def handle_status(config: Config, dynamodb_client: Any | None = None) -> str:
    """Generate /status response: portfolio summary.

    Args:
        config: Application configuration.
        dynamodb_client: Optional DynamoDB client (for testing).

    Returns:
        Formatted status message.
    """
    dynamodb = dynamodb_client or boto3.client(
        "dynamodb", region_name=config.aws_region
    )

    market_status = _get_market_status(dynamodb, config.system_table)
    cash = _get_cash_balance(dynamodb, config.portfolio_table)
    positions = _count_positions(dynamodb, config.portfolio_table)

    status_icon = {"BULL": "🟢", "BEAR": "🔴", "UNKNOWN": "⚪"}.get(
        market_status.value, "⚪"
    )

    return (
        f"📊 Wealth-Ops Status\n"
        f"📅 {date.today().isoformat()}\n\n"
        f"🌡️ Market: {status_icon} {market_status.value}\n"
        f"💰 Cash: €{cash:,.2f}\n"
        f"📈 Open Positions: {positions}\n"
    )


def handle_portfolio(config: Config, dynamodb_client: Any | None = None) -> str:
    """Generate /portfolio response: detailed position breakdown.

    Args:
        config: Application configuration.
        dynamodb_client: Optional DynamoDB client (for testing).

    Returns:
        Formatted portfolio message.
    """
    dynamodb = dynamodb_client or boto3.client(
        "dynamodb", region_name=config.aws_region
    )

    cash = _get_cash_balance(dynamodb, config.portfolio_table)
    positions = _get_positions(dynamodb, config.portfolio_table)

    lines = [f"💼 Portfolio Breakdown\n\n💰 Cash: €{cash:,.2f}\n"]

    if positions:
        lines.append("📈 Positions:")
        for pos in positions:
            ticker = pos.get("ticker", {}).get("S", "???")
            qty = pos.get("quantity", {}).get("N", "0")
            entry = pos.get("entry_price", {}).get("N", "0")
            lines.append(f"  • {ticker}: {qty} @ €{float(entry):,.2f}")
    else:
        lines.append("📈 No open positions. Cash is a position.")

    return "\n".join(lines)


def handle_risk(config: Config, dynamodb_client: Any | None = None) -> str:
    """Generate /risk response: risk parameters and drawdown.

    Args:
        config: Application configuration.
        dynamodb_client: Optional DynamoDB client (for testing).

    Returns:
        Formatted risk message.
    """
    dynamodb = dynamodb_client or boto3.client(
        "dynamodb", region_name=config.aws_region
    )

    risk_data = _get_risk_state(dynamodb, config.system_table)

    drawdown = risk_data.get("drawdown_pct", 0.0)
    heat = risk_data.get("portfolio_heat_pct", 0.0)
    status = risk_data.get("risk_status", "NORMAL")

    status_icon = {"NORMAL": "✅", "REDUCED": "⚠️", "MINIMAL": "🔶", "HALTED": "🛑"}.get(
        status, "✅"
    )

    return (
        f"⚖️ Risk Health\n\n"
        f"📉 Drawdown: {drawdown:.1f}%\n"
        f"🔥 Portfolio Heat: {heat:.1f}%\n"
        f"🚦 Risk Status: {status_icon} {status}\n"
    )


def handle_help() -> str:
    """Generate /help response: list available commands.

    Returns:
        Formatted help message.
    """
    return (
        "📋 Available Commands\n\n"
        "/status — Portfolio summary\n"
        "/portfolio — Detailed positions\n"
        "/risk — Risk parameters\n"
        "/help — This message\n"
    )


# --- Internal helpers ---


def _get_market_status(dynamodb: Any, system_table: str) -> MarketStatus:
    """Get market status from System table."""
    try:
        response = dynamodb.get_item(
            TableName=system_table,
            Key={"key": {"S": "market_status"}},
        )
        item = response.get("Item")
        if item and "value" in item:
            return MarketStatus(item["value"]["S"])
    except (ClientError, ValueError) as e:
        logger.error(f"Failed to get market status: {e}")
    return MarketStatus.UNKNOWN


def _get_cash_balance(dynamodb: Any, portfolio_table: str) -> Decimal:
    """Get cash balance from Portfolio table."""
    try:
        response = dynamodb.get_item(
            TableName=portfolio_table,
            Key={
                "asset_type": {"S": "CASH"},
                "ticker": {"S": "EUR"},
            },
        )
        item = response.get("Item")
        if item and "quantity" in item:
            return Decimal(item["quantity"]["N"])
    except ClientError as e:
        logger.error(f"Failed to get cash balance: {e}")
    return Decimal("0")


def _count_positions(dynamodb: Any, portfolio_table: str) -> int:
    """Count open positions from Portfolio table."""
    try:
        response = dynamodb.query(
            TableName=portfolio_table,
            KeyConditionExpression="asset_type = :t",
            ExpressionAttributeValues={":t": {"S": "STOCK"}},
            Select="COUNT",
        )
        return response.get("Count", 0)
    except ClientError as e:
        logger.error(f"Failed to count positions: {e}")
    return 0


def _get_positions(dynamodb: Any, portfolio_table: str) -> list[dict[str, Any]]:
    """Get all open positions from Portfolio table."""
    try:
        response = dynamodb.query(
            TableName=portfolio_table,
            KeyConditionExpression="asset_type = :t",
            ExpressionAttributeValues={":t": {"S": "STOCK"}},
        )
        return response.get("Items", [])
    except ClientError as e:
        logger.error(f"Failed to get positions: {e}")
    return []


def _get_risk_state(dynamodb: Any, system_table: str) -> dict[str, Any]:
    """Get risk state from System table."""
    try:
        response = dynamodb.get_item(
            TableName=system_table,
            Key={"key": {"S": "risk_state"}},
        )
        item = response.get("Item")
        if item:
            return {
                "drawdown_pct": float(item.get("drawdown_pct", {}).get("N", "0")),
                "portfolio_heat_pct": float(
                    item.get("portfolio_heat_pct", {}).get("N", "0")
                ),
                "risk_status": item.get("risk_status", {}).get("S", "NORMAL"),
            }
    except ClientError as e:
        logger.error(f"Failed to get risk state: {e}")
    return {"drawdown_pct": 0.0, "portfolio_heat_pct": 0.0, "risk_status": "NORMAL"}
