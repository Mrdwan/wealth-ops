"""Economic Calendar Manager — orchestrates macro event date tracking.

Handles economic calendar ingestion (FOMC, NFP, CPI), S3 persistence,
staleness tracking, and next-event-date querying for the Macro Event Guard.
"""

import json
from datetime import date, datetime, timedelta, timezone
from typing import Any

import boto3
from botocore.exceptions import ClientError

from src.modules.data.protocols import EconomicCalendarProvider
from src.shared.config import Config
from src.shared.logger import get_logger

logger = get_logger(__name__)

# Staleness threshold for economic calendar data (hours).
ECONOMIC_STALENESS_HOURS: int = 24

# Event types tracked by this manager.
_EVENT_TYPES: list[str] = ["FOMC", "NFP", "CPI"]


class EconomicCalendarManager:
    """Orchestrates economic calendar fetching, S3 persistence, and staleness.

    Fetches FOMC, NFP, and CPI dates from the provider, stores them
    as JSON in S3, and provides query methods for the Macro Event Guard.
    """

    def __init__(
        self,
        config: Config,
        provider: EconomicCalendarProvider,
        s3_client: Any | None = None,
        dynamodb_client: Any | None = None,
    ) -> None:
        """Initialize EconomicCalendarManager.

        Args:
            config: Application configuration.
            provider: Economic calendar data provider.
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

    def ingest(self, year: int) -> dict[str, int]:
        """Ingest economic calendar for a given year.

        Fetches FOMC, NFP, and CPI dates and stores them in S3.

        Args:
            year: Calendar year to ingest.

        Returns:
            Dict of {event_type: count}. Failed types have count -1.
        """
        results: dict[str, int] = {}
        all_dates: dict[str, list[str]] = {}

        for event_type in _EVENT_TYPES:
            try:
                dates = self._provider.get_event_dates(event_type, year)
                results[event_type] = len(dates)
                all_dates[event_type.lower()] = [d.isoformat() for d in dates]
            except Exception as e:
                logger.error(
                    f"Failed to fetch {event_type} dates for {year}: {e}"
                )
                results[event_type] = -1
                all_dates[event_type.lower()] = []

        self._save_to_s3(year, all_dates)
        self._update_staleness()

        total = sum(c for c in results.values() if c > 0)
        logger.info(f"Ingested {total} economic calendar dates for {year}")
        return results

    # ── Query ────────────────────────────────────────────────────

    def get_next_macro_event_date(self) -> date | None:
        """Get the nearest upcoming FOMC, NFP, or CPI date.

        Loads the current and next year's calendars from S3
        and returns the closest future event date.

        Returns:
            Next macro event date, or None if no calendar data.
        """
        today = date.today()
        current_year = today.year
        all_dates: list[date] = []

        for year in [current_year, current_year + 1]:
            loaded = self._load_from_s3(year)
            all_dates.extend(loaded)

        if not all_dates:
            return None

        future_dates = [d for d in all_dates if d >= today]
        if not future_dates:
            return None

        return min(future_dates)

    def days_until_macro_event(self) -> int | None:
        """Get the number of days until the next macro event.

        Args: None.

        Returns:
            Days until next FOMC/NFP/CPI event, or None if no data.
        """
        next_date = self.get_next_macro_event_date()
        if next_date is None:
            return None
        return (next_date - date.today()).days

    # ── Staleness ────────────────────────────────────────────────

    def check_staleness(self) -> bool:
        """Check if economic calendar data is stale.

        Returns:
            True if stale (>24h since last refresh), False otherwise.
        """
        try:
            response = self._dynamodb.get_item(
                TableName=self._config.system_table,
                Key={"key": {"S": "economic_calendar_staleness"}},
            )
            item = response.get("Item")
            if not item or "updated_at" not in item:
                return True

            updated_at = datetime.fromisoformat(item["updated_at"]["S"])
            age = datetime.now(timezone.utc) - updated_at
            return age > timedelta(hours=ECONOMIC_STALENESS_HOURS)

        except ClientError as e:
            logger.error(f"Error checking economic calendar staleness: {e}")
            return True

    # ── Internal helpers ─────────────────────────────────────────

    def _save_to_s3(
        self, year: int, all_dates: dict[str, list[str]]
    ) -> None:
        """Save economic calendar dates to S3 as JSON.

        Args:
            year: Calendar year.
            all_dates: Dict of {event_type: [iso_date_strings]}.
        """
        key = f"economic_calendar/calendar_{year}.json"
        payload = json.dumps({"year": year, **all_dates})

        try:
            self._s3.put_object(
                Bucket=self._config.s3_bucket,
                Key=key,
                Body=payload.encode("utf-8"),
                ContentType="application/json",
            )
            logger.info(
                f"Saved economic calendar to "
                f"s3://{self._config.s3_bucket}/{key}"
            )
        except ClientError as e:
            logger.error(f"Failed to save economic calendar to S3: {e}")
            raise

    def _load_from_s3(self, year: int) -> list[date]:
        """Load economic calendar dates from S3.

        Args:
            year: Calendar year.

        Returns:
            Merged list of all event dates for the year. Empty if not found.
        """
        key = f"economic_calendar/calendar_{year}.json"

        try:
            response = self._s3.get_object(
                Bucket=self._config.s3_bucket,
                Key=key,
            )
            body = response["Body"].read().decode("utf-8")
            data = json.loads(body)

            dates: list[date] = []
            for event_type in _EVENT_TYPES:
                raw = data.get(event_type.lower(), [])
                for d_str in raw:
                    dates.append(date.fromisoformat(d_str))

            return sorted(dates)

        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code == "NoSuchKey":
                logger.info(f"No economic calendar found for {year}")
                return []
            logger.error(f"Failed to load economic calendar from S3: {e}")
            raise

    def _update_staleness(self) -> None:
        """Update the staleness timestamp in DynamoDB."""
        try:
            self._dynamodb.put_item(
                TableName=self._config.system_table,
                Item={
                    "key": {"S": "economic_calendar_staleness"},
                    "updated_at": {
                        "S": datetime.now(timezone.utc).isoformat(),
                    },
                },
            )
        except ClientError as e:
            logger.error(
                f"Failed to update economic calendar staleness: {e}"
            )
            raise
