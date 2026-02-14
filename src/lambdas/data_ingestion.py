"""Data Ingestion Lambda Handler.

Triggered daily to ingest market data for all configured assets.
Routes each ticker to the correct provider based on its asset profile.
"""

from typing import Any

import boto3
from botocore.exceptions import ClientError

from src.modules.data.manager import DataManager
from src.modules.data.providers.tiingo import TiingoProvider
from src.modules.data.providers.yahoo import YahooProvider
from src.shared.config import load_config
from src.shared.logger import get_logger
from src.shared.profiles import AssetProfile

logger = get_logger(__name__)


def get_enabled_tickers(
    config_table: str, region: str
) -> list[tuple[str, AssetProfile]]:
    """Scan DynamoDB Config table for enabled tickers with profiles.

    Args:
        config_table: Name of the config table.
        region: AWS region.

    Returns:
        List of (ticker, profile) tuples.
    """
    dynamodb = boto3.client("dynamodb", region_name=region)
    results: list[tuple[str, AssetProfile]] = []

    try:
        paginator = dynamodb.get_paginator("scan")
        for page in paginator.paginate(TableName=config_table):
            for item in page.get("Items", []):
                if "enabled" in item and not item["enabled"]["BOOL"]:
                    continue

                if "ticker" in item:
                    ticker = item["ticker"]["S"]
                    profile = AssetProfile.from_dynamodb_item(item)
                    results.append((ticker, profile))

    except ClientError as e:
        logger.error(f"Failed to scan config table: {e}")
        raise

    return results


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Lambda handler for data ingestion.

    Args:
        event: CloudWatch Event or test payload.
        context: Lambda context.

    Returns:
        Execution summary.
    """
    logger.info("Starting Data Ingestion Lambda")

    try:
        config = load_config()

        # Initialize providers
        tiingo = TiingoProvider(config.tiingo_api_key)
        yahoo = YahooProvider()

        # Initialize manager with stock providers as default
        manager = DataManager(
            config=config,
            primary_provider=tiingo,
            fallback_provider=yahoo,
        )

        ticker_profiles = get_enabled_tickers(config.config_table, config.aws_region)

        if not ticker_profiles:
            logger.warning("No enabled tickers found in configuration.")
            return {"statusCode": 200, "body": "No tickers to process.", "processed_count": 0}

        total_records = 0
        failed_tickers: list[str] = []

        for ticker, profile in ticker_profiles:
            try:
                s3_prefix = profile.s3_prefix()
                records = manager.ingest(ticker, s3_prefix=s3_prefix)
                total_records += records
            except Exception as e:
                logger.error(f"Failed to ingest {ticker}: {e}")
                failed_tickers.append(ticker)

        status = "success" if not failed_tickers else "partial_success"

        summary = {
            "status": status,
            "total_ingested_records": total_records,
            "processed_tickers": len(ticker_profiles) - len(failed_tickers),
            "failed_tickers": failed_tickers,
        }

        logger.info(f"Ingestion complete: {summary}")

        return {"statusCode": 200 if not failed_tickers else 207, "body": summary}

    except Exception as e:
        logger.exception("Fatal error in Data Ingestion Lambda")
        return {"statusCode": 500, "body": f"Internal Server Error: {str(e)}"}
