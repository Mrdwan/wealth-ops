"""Seed DynamoDB Config table with asset profiles.

Idempotent — safe to run multiple times. Uses put_item to upsert.

Usage:
    python -m scripts.seed_profiles
    python -m scripts.seed_profiles --region eu-west-1
    python -m scripts.seed_profiles --endpoint-url http://localhost:4566  # LocalStack
"""

from __future__ import annotations

import argparse
import os
import sys

import boto3

from src.shared.profiles import (
    COMMODITY_HAVEN_PROFILE,
    EQUITY_PROFILE,
    INDEX_PROFILE,
    AssetProfile,
)

# Ticker → Profile mapping
SEED_DATA: dict[str, AssetProfile] = {
    # Equities
    "AAPL": EQUITY_PROFILE,
    "NVDA": EQUITY_PROFILE,
    "MSFT": EQUITY_PROFILE,
    "AMZN": EQUITY_PROFILE,
    "GOOGL": EQUITY_PROFILE,
    # Regime / Benchmark indices
    "SPY": INDEX_PROFILE,
    "UUP": INDEX_PROFILE,
    # Commodities (haven) — added in Step 1.6
    "XAUUSD": COMMODITY_HAVEN_PROFILE,
    "XAGUSD": COMMODITY_HAVEN_PROFILE,
}


def seed_profiles(
    table_name: str,
    region: str,
    endpoint_url: str | None = None,
) -> None:
    """Write all profiles to DynamoDB Config table.

    Args:
        table_name: DynamoDB table name.
        region: AWS region.
        endpoint_url: Optional endpoint URL (for LocalStack).
    """
    kwargs = {"region_name": region}
    if endpoint_url:
        kwargs["endpoint_url"] = endpoint_url

    dynamodb = boto3.client("dynamodb", **kwargs)

    for ticker, profile in SEED_DATA.items():
        item = profile.to_dynamodb_item(ticker, enabled=True)
        dynamodb.put_item(TableName=table_name, Item=item)
        print(f"  Seeded {ticker} ({profile.asset_class})")

    print(f"\nDone. {len(SEED_DATA)} profiles seeded to {table_name}.")


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Seed asset profiles to DynamoDB")
    parser.add_argument(
        "--table",
        default=None,
        help="DynamoDB table name (default: wealth-ops-config-{ENVIRONMENT})",
    )
    parser.add_argument("--region", default="us-east-1", help="AWS region")
    parser.add_argument(
        "--endpoint-url",
        default=None,
        help="Custom endpoint URL (e.g., http://localhost:4566 for LocalStack)",
    )
    args = parser.parse_args()

    env = os.getenv("ENVIRONMENT", "dev")
    table_name = args.table or f"wealth-ops-config-{env}"

    print(f"Seeding profiles to {table_name} in {args.region}...")
    if args.endpoint_url:
        print(f"  Using endpoint: {args.endpoint_url}")

    seed_profiles(table_name, args.region, args.endpoint_url)


if __name__ == "__main__":
    sys.exit(main() or 0)
