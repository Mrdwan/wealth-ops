"""Tests for configuration loader."""

from unittest.mock import patch

from src.shared.config import load_config


class TestLoadConfig:
    """Tests for load_config function."""

    @patch.dict("os.environ", {}, clear=True)
    def test_load_config_defaults_to_dev(self) -> None:
        """Test default configuration uses dev environment."""
        config = load_config()

        assert config.environment == "dev"
        assert config.s3_bucket == "wealth-ops-data-dev"
        assert config.config_table == "wealth-ops-config-dev"
        assert config.ledger_table == "wealth-ops-ledger-dev"
        assert config.portfolio_table == "wealth-ops-portfolio-dev"
        assert config.system_table == "wealth-ops-system-dev"
        assert config.aws_region == "us-east-1"

    @patch.dict("os.environ", {"ENVIRONMENT": "prod"}, clear=True)
    def test_load_config_prod_environment(self) -> None:
        """Test configuration uses prod environment in table defaults."""
        config = load_config()

        assert config.environment == "prod"
        assert config.s3_bucket == "wealth-ops-data-prod"
        assert config.config_table == "wealth-ops-config-prod"
        assert config.ledger_table == "wealth-ops-ledger-prod"
        assert config.portfolio_table == "wealth-ops-portfolio-prod"
        assert config.system_table == "wealth-ops-system-prod"

    @patch.dict(
        "os.environ",
        {"ENVIRONMENT": "staging", "S3_BUCKET": "custom-bucket", "AWS_REGION": "eu-west-1"},
        clear=True,
    )
    def test_load_config_explicit_overrides(self) -> None:
        """Test explicit environment variables override defaults."""
        config = load_config()

        assert config.environment == "staging"
        assert config.s3_bucket == "custom-bucket"
        assert config.aws_region == "eu-west-1"
        # Non-overridden values use staging suffix
        assert config.config_table == "wealth-ops-config-staging"
