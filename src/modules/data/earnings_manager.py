"""Earnings Calendar Manager — orchestrates earnings date fetching and persistence.

Handles earnings calendar ingestion, S3 persistence, staleness tracking,
and next-earnings-date projection for the Event Guard.
"""

import json
from datetime import date, datetime, timedelta, timezone
from typing import Any

import boto3
from botocore.exceptions import ClientError

from src.modules.data.protocols import EarningsDataProvider
from src.shared.config import Config
from src.shared.logger import get_logger

logger = get_logger(__name__)

# Staleness threshold for earnings calendar data (hours).
EARNINGS_STALENESS_HOURS: int = 24

# Default interval guess when only one historical date exists (days).
_DEFAULT_QUARTERLY_INTERVAL: int = 90


class EarningsCalendarManager:
    """Orchestrates earnings calendar fetching, S3 persistence, and staleness.

    Each equity ticker's historical quarterly statement dates are stored
    as a JSON file in S3.  The ``next_earnings_date`` is projected by
    averaging the intervals between consecutive historical dates.
    """

    def __init__(
        self,
        config: Config,
        provider: EarningsDataProvider,
        s3_client: Any | None = None,
        dynamodb_client: Any | None = None,
    ) -> None:
        """Initialize EarningsCalendarManager.

        Args:
            config: Application configuration.
            provider: Earnings data provider (e.g., TiingoEarningsProvider).
            s3_client: Optional boto3 S3 client (for testing).
            dynamodb_client: Optional boto3 DynamoDB client (for testing).
        """
        self._config = config
        self._provider = provider
        self._s3 = s3_client or boto3.client("s3", region_name=config.aws_region)
        self._dynamodb = dynamodb_client or boto3.client(
            "dynamodb", region_name=config.aws_region
        )

    # ── Ingestion ────────────────────────────────────────────────

    def ingest(self, ticker: str, lookback_years: int = 2) -> int:
        """Ingest earnings calendar for a single equity ticker.

        Args:
            ticker: Stock symbol (e.g., 'AAPL').
            lookback_years: Years of history to fetch.

        Returns:
            Number of quarterly statement dates stored.
        """
        end_date = date.today()
        start_date = date(end_date.year - lookback_years, end_date.month, end_date.day)

        dates = self._provider.get_statement_dates(ticker, start_date, end_date)

        if not dates:
            logger.warning(f"No quarterly earnings dates for {ticker}")
            return 0

        self._save_to_s3(ticker, dates)
        self._update_staleness(ticker)

        logger.info(f"Ingested {len(dates)} earnings dates for {ticker}")
        return len(dates)

    def ingest_all(
        self,
        tickers: list[str],
        lookback_years: int = 2,
    ) -> dict[str, int]:
        """Ingest earnings calendars for multiple tickers.

        Args:
            tickers: List of equity ticker symbols.
            lookback_years: Years of history to fetch.

        Returns:
            Dict of {ticker: count}. Failed tickers have count -1.
        """
        results: dict[str, int] = {}
        for ticker in tickers:
            try:
                count = self.ingest(ticker, lookback_years)
                results[ticker] = count
            except Exception as e:
                logger.error(f"Failed to ingest earnings for {ticker}: {e}")
                results[ticker] = -1
        return results

    # ── Query ────────────────────────────────────────────────────

    def get_next_earnings_date(self, ticker: str) -> date | None:
        """Project the next earnings date for a ticker.

        Loads the historical quarterly statement dates from S3 and
        projects forward by the average inter-report interval.

        Args:
            ticker: Stock symbol.

        Returns:
            Projected next earnings date, or None if no calendar data.
        """
        dates = self._load_from_s3(ticker)
        if not dates:
            return None

        last_date = dates[-1]
        today = date.today()

        # If last known date is in the future, treat it as 'upcoming'
        if last_date > today:
            return last_date

        avg_interval = self._average_interval(dates)
        projected = last_date + timedelta(days=avg_interval)

        # If the projection is already past, step forward by avg interval
        while projected < today:
            projected += timedelta(days=avg_interval)

        return projected

    def days_until_earnings(self, ticker: str) -> int | None:
        """Get the number of days until the next projected earnings date.

        Args:
            ticker: Stock symbol.

        Returns:
            Days until next earnings, or None if no data available.
        """
        next_date = self.get_next_earnings_date(ticker)
        if next_date is None:
            return None
        return (next_date - date.today()).days

    # ── Staleness ────────────────────────────────────────────────

    def check_staleness(self, ticker: str) -> bool:
        """Check if earnings calendar data for a ticker is stale.

        Args:
            ticker: Stock symbol.

        Returns:
            True if stale (>24h since last refresh), False otherwise.
        """
        try:
            response = self._dynamodb.get_item(
                TableName=self._config.system_table,
                Key={"key": {"S": f"earnings_staleness_{ticker}"}},
            )
            item = response.get("Item")
            if not item or "updated_at" not in item:
                return True

            updated_at = datetime.fromisoformat(item["updated_at"]["S"])
            age = datetime.now(timezone.utc) - updated_at
            return age > timedelta(hours=EARNINGS_STALENESS_HOURS)

        except ClientError as e:
            logger.error(
                f"Error checking earnings staleness for {ticker}: {e}"
            )
            return True

    # ── Internal helpers ─────────────────────────────────────────

    def _average_interval(self, dates: list[date]) -> int:
        """Compute the average interval between consecutive dates.

        Args:
            dates: Sorted list of statement dates.

        Returns:
            Average interval in days. Falls back to 90 if only one date.
        """
        if len(dates) < 2:
            return _DEFAULT_QUARTERLY_INTERVAL

        intervals = [
            (dates[i + 1] - dates[i]).days for i in range(len(dates) - 1)
        ]
        return max(1, sum(intervals) // len(intervals))

    def _save_to_s3(self, ticker: str, dates: list[date]) -> None:
        """Save earnings dates to S3 as JSON.

        Args:
            ticker: Stock symbol.
            dates: Sorted list of earnings dates.
        """
        key = f"earnings/calendar_{ticker}.json"
        payload = json.dumps(
            {"ticker": ticker, "dates": [d.isoformat() for d in dates]},
        )

        try:
            self._s3.put_object(
                Bucket=self._config.s3_bucket,
                Key=key,
                Body=payload.encode("utf-8"),
                ContentType="application/json",
            )
            logger.info(
                f"Saved {len(dates)} earnings dates to "
                f"s3://{self._config.s3_bucket}/{key}"
            )
        except ClientError as e:
            logger.error(f"Failed to save earnings data to S3: {e}")
            raise

    def _load_from_s3(self, ticker: str) -> list[date]:
        """Load earnings dates from S3.

        Args:
            ticker: Stock symbol.

        Returns:
            Sorted list of earnings dates. Empty list if not found.
        """
        key = f"earnings/calendar_{ticker}.json"

        try:
            response = self._s3.get_object(
                Bucket=self._config.s3_bucket,
                Key=key,
            )
            body = response["Body"].read().decode("utf-8")
            data = json.loads(body)
            return [date.fromisoformat(d) for d in data.get("dates", [])]
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code == "NoSuchKey":
                logger.info(f"No earnings calendar found for {ticker}")
                return []
            logger.error(f"Failed to load earnings data from S3: {e}")
            raise

    def _update_staleness(self, ticker: str) -> None:
        """Update the staleness timestamp for a ticker in DynamoDB.

        Args:
            ticker: Stock symbol.
        """
        try:
            self._dynamodb.put_item(
                TableName=self._config.system_table,
                Item={
                    "key": {"S": f"earnings_staleness_{ticker}"},
                    "updated_at": {
                        "S": datetime.now(timezone.utc).isoformat(),
                    },
                    "ticker": {"S": ticker},
                },
            )
        except ClientError as e:
            logger.error(
                f"Failed to update earnings staleness for {ticker}: {e}"
            )
            raise
