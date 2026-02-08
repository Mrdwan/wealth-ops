"""Tests for JSON logger module."""

import json
import logging
from unittest.mock import MagicMock

from src.shared.logger import JSONFormatter, get_logger


class TestJSONFormatter:
    """Tests for JSONFormatter."""

    def test_format_basic_message(self) -> None:
        """Test basic log record formatting as JSON."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=None,
            exc_info=None,
        )

        result = json.loads(formatter.format(record))

        assert result["level"] == "INFO"
        assert result["message"] == "Test message"
        assert result["logger"] == "test"
        assert "timestamp" in result

    def test_format_record_with_extra_attribute(self) -> None:
        """Test log record with extra attribute merges into JSON output."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test with extra",
            args=None,
            exc_info=None,
        )
        record.extra = {"ticker": "AAPL", "mode": "bootstrap"}  # type: ignore[attr-defined]

        result = json.loads(formatter.format(record))

        assert result["ticker"] == "AAPL"
        assert result["mode"] == "bootstrap"
        assert result["message"] == "Test with extra"


class TestGetLogger:
    """Tests for get_logger factory."""

    def test_get_logger_skips_handler_when_already_exists(self) -> None:
        """Test get_logger does not add duplicate handlers."""
        logger_name = "test.duplicate_handler_check"
        logger = logging.getLogger(logger_name)
        logger.handlers.clear()

        # First call adds a handler
        result1 = get_logger(logger_name)
        handler_count = len(result1.handlers)

        # Second call should not add another handler
        result2 = get_logger(logger_name)

        assert len(result2.handlers) == handler_count
