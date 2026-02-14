"""Tests for Telegram webhook Lambda handler."""

import json
from unittest.mock import MagicMock, patch

from src.lambdas.telegram_webhook import handler


def _make_event(chat_id: str, text: str) -> dict:
    """Create a mock Lambda Function URL event with Telegram Update."""
    return {
        "body": json.dumps(
            {
                "message": {
                    "text": text,
                    "chat": {"id": int(chat_id) if chat_id.isdigit() else 0},
                }
            }
        )
    }


@patch("src.lambdas.telegram_webhook.TelegramNotifier")
@patch("src.lambdas.telegram_webhook.load_config")
class TestWebhookHandler:
    """Tests for the webhook handler."""

    def test_status_command_dispatches(
        self, mock_config: MagicMock, mock_notifier_cls: MagicMock
    ) -> None:
        """Test /status command is dispatched correctly."""
        config = MagicMock()
        config.telegram_chat_id = "123456"
        mock_config.return_value = config

        event = _make_event("123456", "/status")

        with patch("src.lambdas.telegram_webhook.handle_status") as mock_status:
            mock_status.return_value = "status reply"
            response = handler(event, {})

        assert response["statusCode"] == 200
        mock_notifier_cls.return_value.send_reply.assert_called_once_with(
            "123456", "status reply"
        )

    def test_help_command_dispatches(
        self, mock_config: MagicMock, mock_notifier_cls: MagicMock
    ) -> None:
        """Test /help command returns help text."""
        config = MagicMock()
        config.telegram_chat_id = "123456"
        mock_config.return_value = config

        event = _make_event("123456", "/help")
        response = handler(event, {})

        assert response["statusCode"] == 200
        reply_text = mock_notifier_cls.return_value.send_reply.call_args[0][1]
        assert "/status" in reply_text
        assert "/portfolio" in reply_text

    def test_portfolio_command_dispatches(
        self, mock_config: MagicMock, mock_notifier_cls: MagicMock
    ) -> None:
        """Test /portfolio command is dispatched."""
        config = MagicMock()
        config.telegram_chat_id = "123456"
        mock_config.return_value = config

        event = _make_event("123456", "/portfolio")

        with patch(
            "src.lambdas.telegram_webhook.handle_portfolio"
        ) as mock_portfolio:
            mock_portfolio.return_value = "portfolio reply"
            response = handler(event, {})

        assert response["statusCode"] == 200
        mock_notifier_cls.return_value.send_reply.assert_called_once_with(
            "123456", "portfolio reply"
        )

    def test_risk_command_dispatches(
        self, mock_config: MagicMock, mock_notifier_cls: MagicMock
    ) -> None:
        """Test /risk command is dispatched."""
        config = MagicMock()
        config.telegram_chat_id = "123456"
        mock_config.return_value = config

        event = _make_event("123456", "/risk")

        with patch("src.lambdas.telegram_webhook.handle_risk") as mock_risk:
            mock_risk.return_value = "risk reply"
            response = handler(event, {})

        assert response["statusCode"] == 200

    def test_unknown_command_sends_error(
        self, mock_config: MagicMock, mock_notifier_cls: MagicMock
    ) -> None:
        """Test unknown command gets an error reply."""
        config = MagicMock()
        config.telegram_chat_id = "123456"
        mock_config.return_value = config

        event = _make_event("123456", "/foobar")
        response = handler(event, {})

        assert response["statusCode"] == 200
        reply_text = mock_notifier_cls.return_value.send_reply.call_args[0][1]
        assert "Unknown command" in reply_text
        assert "/help" in reply_text

    def test_unauthorized_chat_rejected(
        self, mock_config: MagicMock, mock_notifier_cls: MagicMock
    ) -> None:
        """Test messages from wrong chat are rejected."""
        config = MagicMock()
        config.telegram_chat_id = "123456"
        mock_config.return_value = config

        event = _make_event("999999", "/status")
        response = handler(event, {})

        assert response["statusCode"] == 403
        mock_notifier_cls.return_value.send_reply.assert_not_called()

    def test_empty_body_returns_ok(
        self, mock_config: MagicMock, mock_notifier_cls: MagicMock
    ) -> None:
        """Test empty body returns 200 OK without dispatching."""
        event = {"body": "{}"}
        response = handler(event, {})

        assert response["statusCode"] == 200
        mock_notifier_cls.return_value.send_reply.assert_not_called()

    def test_invalid_json_returns_400(
        self, mock_config: MagicMock, mock_notifier_cls: MagicMock
    ) -> None:
        """Test malformed JSON returns 400."""
        event = {"body": "not json"}
        response = handler(event, {})

        assert response["statusCode"] == 400

    def test_missing_body_returns_ok(
        self, mock_config: MagicMock, mock_notifier_cls: MagicMock
    ) -> None:
        """Test missing body key returns 200 OK."""
        event = {}
        response = handler(event, {})

        assert response["statusCode"] == 200

    def test_command_case_insensitive(
        self, mock_config: MagicMock, mock_notifier_cls: MagicMock
    ) -> None:
        """Test commands are case-insensitive."""
        config = MagicMock()
        config.telegram_chat_id = "123456"
        mock_config.return_value = config

        event = _make_event("123456", "/STATUS")

        with patch("src.lambdas.telegram_webhook.handle_status") as mock_status:
            mock_status.return_value = "status reply"
            response = handler(event, {})

        assert response["statusCode"] == 200
