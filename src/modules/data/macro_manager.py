"""Macro Data Manager — orchestrates FRED data fetching and persistence.

Handles macro economic indicator ingestion with per-series staleness tracking.
"""

from datetime import date, datetime, timedelta, timezone
from typing import Any

import boto3
import pandas as pd
import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.parquet as pq  # type: ignore[import-untyped]
from botocore.exceptions import ClientError

from src.modules.data.protocols import MacroDataProvider
from src.shared.config import Config
from src.shared.logger import get_logger

logger = get_logger(__name__)

# Series configuration: (series_id, staleness_threshold_hours)
MACRO_SERIES: list[tuple[str, int]] = [
    ("VIXCLS", 24),       # VIX — daily
    ("T10Y2Y", 24),       # Yield Curve — daily
    ("FEDFUNDS", 840),    # Fed Funds Rate — monthly (~35 days)
    ("CPIAUCSL", 840),    # CPI — monthly (~35 days)
]


class MacroDataManager:
    """Orchestrates macro data fetching, S3 persistence, and staleness checks.

    Each macro series is stored as a single Parquet file in S3.
    Staleness is tracked per-series in DynamoDB System table.
    """

    def __init__(
        self,
        config: Config,
        provider: MacroDataProvider,
        s3_client: Any | None = None,
        dynamodb_client: Any | None = None,
    ) -> None:
        """Initialize MacroDataManager.

        Args:
            config: Application configuration.
            provider: Macro data provider (e.g., FredProvider).
            s3_client: Optional boto3 S3 client (for testing).
            dynamodb_client: Optional boto3 DynamoDB client (for testing).
        """
        self._config = config
        self._provider = provider
        self._s3 = s3_client or boto3.client("s3", region_name=config.aws_region)
        self._dynamodb = dynamodb_client or boto3.client(
            "dynamodb", region_name=config.aws_region
        )

    def ingest_all(self, lookback_years: int = 10) -> dict[str, int]:
        """Ingest all configured macro series.

        Args:
            lookback_years: Years of history to fetch.

        Returns:
            Dict of {series_id: record_count}. Failed series have count -1.
        """
        results: dict[str, int] = {}
        end_date = date.today()
        start_date = date(end_date.year - lookback_years, end_date.month, end_date.day)

        for series_id, _ in MACRO_SERIES:
            try:
                count = self._ingest_series(series_id, start_date, end_date)
                results[series_id] = count
            except Exception as e:
                logger.error(f"Failed to ingest macro series {series_id}: {e}")
                results[series_id] = -1

        return results

    def _ingest_series(
        self, series_id: str, start_date: date, end_date: date
    ) -> int:
        """Ingest a single macro series.

        Args:
            series_id: FRED series ID.
            start_date: Start date.
            end_date: End date.

        Returns:
            Number of observations ingested.
        """
        df = self._provider.get_observations(series_id, start_date, end_date)

        if df.empty:
            logger.warning(f"No observations for {series_id}")
            return 0

        self._save_to_s3(series_id, df)
        self._update_staleness(series_id)

        count = len(df)
        logger.info(f"Ingested {count} observations for {series_id}")
        return count

    def check_staleness(self, series_id: str) -> bool:
        """Check if a macro series is stale.

        Args:
            series_id: FRED series ID.

        Returns:
            True if the series is stale (exceeds threshold), False otherwise.
        """
        threshold_hours = self._get_threshold(series_id)

        try:
            response = self._dynamodb.get_item(
                TableName=self._config.system_table,
                Key={"key": {"S": f"macro_staleness_{series_id}"}},
            )
            item = response.get("Item")
            if not item or "updated_at" not in item:
                return True

            updated_at = datetime.fromisoformat(item["updated_at"]["S"])
            age = datetime.now(timezone.utc) - updated_at
            return age > timedelta(hours=threshold_hours)

        except ClientError as e:
            logger.error(f"Error checking staleness for {series_id}: {e}")
            return True

    def _get_threshold(self, series_id: str) -> int:
        """Get staleness threshold hours for a series."""
        for sid, hours in MACRO_SERIES:
            if sid == series_id:
                return hours
        return 24

    def _save_to_s3(self, series_id: str, df: pd.DataFrame) -> None:
        """Save macro data to S3 as Parquet.

        Args:
            series_id: FRED series ID.
            df: DataFrame to save.
        """
        table = pa.Table.from_pandas(df)
        buffer = pa.BufferOutputStream()
        pq.write_table(table, buffer)
        parquet_bytes = buffer.getvalue().to_pybytes()

        key = f"ohlcv/macro/{series_id}.parquet"

        try:
            self._s3.put_object(
                Bucket=self._config.s3_bucket,
                Key=key,
                Body=parquet_bytes,
            )
            logger.info(
                f"Saved {len(df)} observations to s3://{self._config.s3_bucket}/{key}"
            )
        except ClientError as e:
            logger.error(f"Failed to save macro data to S3: {e}")
            raise

    def _update_staleness(self, series_id: str) -> None:
        """Update the staleness timestamp for a series in DynamoDB."""
        try:
            self._dynamodb.put_item(
                TableName=self._config.system_table,
                Item={
                    "key": {"S": f"macro_staleness_{series_id}"},
                    "updated_at": {
                        "S": datetime.now(timezone.utc).isoformat(),
                    },
                    "series_id": {"S": series_id},
                },
            )
        except ClientError as e:
            logger.error(f"Failed to update staleness for {series_id}: {e}")
            raise
