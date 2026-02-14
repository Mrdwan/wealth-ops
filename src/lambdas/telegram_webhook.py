"""Telegram Webhook Lambda Handler.

Receives incoming messages from Telegram Bot API via Lambda Function URL.
Routes commands to appropriate handlers and sends replies.
"""

import json
from typing import Any

from src.modules.notifications.commands import (
    handle_help,
    handle_portfolio,
    handle_risk,
    handle_status,
)
from src.modules.notifications.telegram import TelegramNotifier
from src.shared.config import load_config
from src.shared.logger import get_logger

logger = get_logger(__name__)


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Lambda Function URL handler for Telegram webhook.

    Telegram sends POST with JSON body containing the Update object.
    We parse the command, dispatch to the handler, and reply.

    Args:
        event: Lambda Function URL event with Telegram Update in body.
        context: Lambda context.

    Returns:
        HTTP response dict.
    """
    try:
        body = json.loads(event.get("body", "{}"))
    except json.JSONDecodeError:
        logger.warning("Invalid JSON in webhook body")
        return {"statusCode": 400, "body": "Invalid JSON"}

    message = body.get("message", {})
    text = message.get("text", "").strip()
    chat_id = str(message.get("chat", {}).get("id", ""))

    if not chat_id or not text:
        return {"statusCode": 200, "body": "OK"}

    config = load_config()

    # Security: only respond to configured chat
    if chat_id != config.telegram_chat_id:
        logger.warning(f"Rejected message from unauthorized chat: {chat_id}")
        return {"statusCode": 403, "body": "Unauthorized"}

    # Parse command (first word, lowercased)
    command = text.split()[0].lower()

    # Dispatch
    commands = {
        "/status": lambda: handle_status(config),
        "/portfolio": lambda: handle_portfolio(config),
        "/risk": lambda: handle_risk(config),
        "/help": handle_help,
    }

    handler_fn = commands.get(command)
    if handler_fn is None:
        reply_text = (
            f"Unknown command: {command}\n"
            "Type /help for available commands."
        )
    else:
        reply_text = handler_fn()

    # Send reply
    notifier = TelegramNotifier(config)
    notifier.send_reply(chat_id, reply_text)

    return {"statusCode": 200, "body": "OK"}
