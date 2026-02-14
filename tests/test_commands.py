"""Tests for Telegram command handlers."""

from decimal import Decimal
from unittest.mock import MagicMock

from src.modules.notifications.commands import (
    handle_help,
    handle_portfolio,
    handle_risk,
    handle_status,
)
from src.shared.config import Config


def _make_config() -> Config:
    """Create test configuration."""
    return Config(
        aws_region="us-east-1",
        s3_bucket="test-bucket",
        config_table="test-config",
        ledger_table="test-ledger",
        portfolio_table="test-portfolio",
        system_table="test-system",
        tiingo_api_key="",
        fred_api_key="",
        telegram_bot_token="test-token",
        telegram_chat_id="123456",
        environment="test",
    )


class TestHandleStatus:
    """Tests for /status command."""

    def test_status_includes_market_info(self) -> None:
        """Test status response includes market status."""
        mock_dynamodb = MagicMock()
        mock_dynamodb.get_item.return_value = {
            "Item": {"key": {"S": "market_status"}, "value": {"S": "BULL"}}
        }
        mock_dynamodb.query.return_value = {"Count": 2}

        result = handle_status(_make_config(), dynamodb_client=mock_dynamodb)

        assert "BULL" in result
        assert "🟢" in result
        assert "Open Positions: 2" in result

    def test_status_with_bear_market(self) -> None:
        """Test status with bear market shows red indicator."""
        mock_dynamodb = MagicMock()
        mock_dynamodb.get_item.return_value = {
            "Item": {"key": {"S": "market_status"}, "value": {"S": "BEAR"}}
        }
        mock_dynamodb.query.return_value = {"Count": 0}

        result = handle_status(_make_config(), dynamodb_client=mock_dynamodb)

        assert "BEAR" in result
        assert "🔴" in result

    def test_status_handles_missing_data(self) -> None:
        """Test status with no data shows defaults."""
        mock_dynamodb = MagicMock()
        mock_dynamodb.get_item.return_value = {}
        mock_dynamodb.query.return_value = {"Count": 0}

        result = handle_status(_make_config(), dynamodb_client=mock_dynamodb)

        assert "UNKNOWN" in result
        assert "€0.00" in result


class TestHandlePortfolio:
    """Tests for /portfolio command."""

    def test_portfolio_with_positions(self) -> None:
        """Test portfolio with open positions."""
        mock_dynamodb = MagicMock()
        # Cash balance
        mock_dynamodb.get_item.return_value = {
            "Item": {
                "asset_type": {"S": "CASH"},
                "ticker": {"S": "EUR"},
                "quantity": {"N": "2500"},
            }
        }
        # Open positions
        mock_dynamodb.query.return_value = {
            "Items": [
                {
                    "ticker": {"S": "AAPL"},
                    "quantity": {"N": "10"},
                    "entry_price": {"N": "150.50"},
                },
            ]
        }

        result = handle_portfolio(_make_config(), dynamodb_client=mock_dynamodb)

        assert "€2,500.00" in result
        assert "AAPL" in result
        assert "150.50" in result

    def test_portfolio_no_positions(self) -> None:
        """Test portfolio with no open positions shows cash message."""
        mock_dynamodb = MagicMock()
        mock_dynamodb.get_item.return_value = {}
        mock_dynamodb.query.return_value = {"Items": []}

        result = handle_portfolio(_make_config(), dynamodb_client=mock_dynamodb)

        assert "Cash is a position" in result


class TestHandleRisk:
    """Tests for /risk command."""

    def test_risk_normal_state(self) -> None:
        """Test risk with normal conditions."""
        mock_dynamodb = MagicMock()
        mock_dynamodb.get_item.return_value = {
            "Item": {
                "key": {"S": "risk_state"},
                "drawdown_pct": {"N": "2.5"},
                "portfolio_heat_pct": {"N": "4.0"},
                "risk_status": {"S": "NORMAL"},
            }
        }

        result = handle_risk(_make_config(), dynamodb_client=mock_dynamodb)

        assert "2.5%" in result
        assert "4.0%" in result
        assert "NORMAL" in result
        assert "✅" in result

    def test_risk_halted_state(self) -> None:
        """Test risk with halted state shows stop sign."""
        mock_dynamodb = MagicMock()
        mock_dynamodb.get_item.return_value = {
            "Item": {
                "key": {"S": "risk_state"},
                "drawdown_pct": {"N": "16.0"},
                "portfolio_heat_pct": {"N": "0.0"},
                "risk_status": {"S": "HALTED"},
            }
        }

        result = handle_risk(_make_config(), dynamodb_client=mock_dynamodb)

        assert "HALTED" in result
        assert "🛑" in result

    def test_risk_missing_data_shows_defaults(self) -> None:
        """Test risk with no data shows safe defaults."""
        mock_dynamodb = MagicMock()
        mock_dynamodb.get_item.return_value = {}

        result = handle_risk(_make_config(), dynamodb_client=mock_dynamodb)

        assert "0.0%" in result
        assert "NORMAL" in result


class TestHandleHelp:
    """Tests for /help command."""

    def test_help_lists_all_commands(self) -> None:
        """Test help lists all available commands."""
        result = handle_help()

        assert "/status" in result
        assert "/portfolio" in result
        assert "/risk" in result
        assert "/help" in result

    def test_help_includes_descriptions(self) -> None:
        """Test help has command descriptions."""
        result = handle_help()

        assert "Portfolio summary" in result
        assert "Risk parameters" in result
