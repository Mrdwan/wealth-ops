
from src.shared.profiles import (
    AssetProfile, 
    EQUITY_PROFILE, 
    COMMODITY_HAVEN_PROFILE, 
    COMMODITY_CYCLICAL_PROFILE,
    INDEX_PROFILE
)

def test_asset_profile_defaults():
    # Verify standard profiles exist and have correct types
    assert isinstance(EQUITY_PROFILE, AssetProfile)
    assert EQUITY_PROFILE.asset_class == "EQUITY"
    
    assert isinstance(COMMODITY_HAVEN_PROFILE, AssetProfile)
    assert COMMODITY_HAVEN_PROFILE.asset_class == "COMMODITY"
    
    assert isinstance(COMMODITY_CYCLICAL_PROFILE, AssetProfile)
    assert COMMODITY_CYCLICAL_PROFILE.asset_class == "COMMODITY"

    assert isinstance(INDEX_PROFILE, AssetProfile)
    assert INDEX_PROFILE.asset_class == "INDEX"

def test_s3_prefix():
    assert EQUITY_PROFILE.s3_prefix() == "ohlcv/stocks"
    assert COMMODITY_HAVEN_PROFILE.s3_prefix() == "ohlcv/forex" # Mapped to forex in code?
    assert INDEX_PROFILE.s3_prefix() == "ohlcv/indices"
    
    # Test fallback
    custom = AssetProfile(
        asset_class="CRYPTO",
        regime_index="", regime_direction="", vix_guard=False, event_guard=False, 
        macro_event_guard=False, volume_features=False, benchmark_index="", 
        concentration_group="", broker="", tax_rate=0.0, data_source=""
    )
    assert custom.s3_prefix() == "ohlcv/stocks" # Default

def test_dynamodb_serialization():
    # Test round-trip
    item = EQUITY_PROFILE.to_dynamodb_item("AAPL", enabled=True)
    
    assert item["ticker"]["S"] == "AAPL"
    assert item["asset_class"]["S"] == "EQUITY"
    assert item["tax_rate"]["N"] == "0.33"
    
    # Parse back
    parsed = AssetProfile.from_dynamodb_item(item)
    assert parsed == EQUITY_PROFILE

def test_dynamodb_parsing_defaults():
    # Test parsing with missing fields
    item = {} # Empty item
    profile = AssetProfile.from_dynamodb_item(item)
    
    # Should get defaults
    assert profile.asset_class == "EQUITY"
    assert profile.regime_index == "SPY"
    assert profile.vix_guard is True
    assert profile.macro_event_guard is False
