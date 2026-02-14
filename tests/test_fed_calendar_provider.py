"""Tests for FedCalendarProvider."""

from datetime import date

import pytest

from src.modules.data.protocols import ProviderError
from src.modules.data.providers.fed_calendar_provider import (
    FedCalendarProvider,
)


@pytest.fixture
def provider() -> FedCalendarProvider:
    """Create test provider instance."""
    return FedCalendarProvider()


class TestProviderName:
    """Tests for provider name property."""

    def test_name(self, provider: FedCalendarProvider) -> None:
        """Test provider name is FedCalendar."""
        assert provider.name == "FedCalendar"


class TestFOMCDates:
    """Tests for FOMC meeting date retrieval."""

    def test_fomc_2026_returns_eight_dates(
        self, provider: FedCalendarProvider
    ) -> None:
        """Test that 2026 FOMC schedule has 8 meeting dates."""
        dates = provider.get_event_dates("FOMC", 2026)
        assert len(dates) == 8

    def test_fomc_dates_are_sorted(
        self, provider: FedCalendarProvider
    ) -> None:
        """Test that FOMC dates are in ascending order."""
        dates = provider.get_event_dates("FOMC", 2026)
        assert dates == sorted(dates)

    def test_fomc_first_date_2026(
        self, provider: FedCalendarProvider
    ) -> None:
        """Test the first FOMC date in 2026."""
        dates = provider.get_event_dates("FOMC", 2026)
        assert dates[0] == date(2026, 1, 28)

    def test_fomc_unsupported_year_raises(
        self, provider: FedCalendarProvider
    ) -> None:
        """Test that an unsupported year raises ProviderError."""
        with pytest.raises(ProviderError, match="not in schedule"):
            provider.get_event_dates("FOMC", 2020)

    def test_fomc_2025_returns_eight_dates(
        self, provider: FedCalendarProvider
    ) -> None:
        """Test that 2025 FOMC schedule has 8 meeting dates."""
        dates = provider.get_event_dates("FOMC", 2025)
        assert len(dates) == 8

    def test_fomc_2027_returns_eight_dates(
        self, provider: FedCalendarProvider
    ) -> None:
        """Test that 2027 FOMC schedule has 8 meeting dates."""
        dates = provider.get_event_dates("FOMC", 2027)
        assert len(dates) == 8


class TestNFPDates:
    """Tests for NFP (Non-Farm Payrolls) date computation."""

    def test_nfp_returns_twelve_dates(
        self, provider: FedCalendarProvider
    ) -> None:
        """Test that NFP returns 12 dates (one per month)."""
        dates = provider.get_event_dates("NFP", 2026)
        assert len(dates) == 12

    def test_nfp_all_fridays(
        self, provider: FedCalendarProvider
    ) -> None:
        """Test that all NFP dates are Fridays."""
        dates = provider.get_event_dates("NFP", 2026)
        for d in dates:
            assert d.weekday() == 4, f"{d} is not a Friday"

    def test_nfp_all_first_week(
        self, provider: FedCalendarProvider
    ) -> None:
        """Test that all NFP dates are in the first 7 days of the month."""
        dates = provider.get_event_dates("NFP", 2026)
        for d in dates:
            assert d.day <= 7, f"{d} is not in the first week"

    def test_nfp_works_for_any_year(
        self, provider: FedCalendarProvider
    ) -> None:
        """Test that NFP computation works for arbitrary years."""
        dates = provider.get_event_dates("NFP", 2050)
        assert len(dates) == 12
        for d in dates:
            assert d.weekday() == 4

    def test_nfp_specific_date_jan_2026(
        self, provider: FedCalendarProvider
    ) -> None:
        """Test specific NFP date: Jan 2026 first Friday is Jan 2."""
        dates = provider.get_event_dates("NFP", 2026)
        assert dates[0] == date(2026, 1, 2)

    def test_nfp_dates_are_sorted(
        self, provider: FedCalendarProvider
    ) -> None:
        """Test that NFP dates are in ascending order."""
        dates = provider.get_event_dates("NFP", 2026)
        assert dates == sorted(dates)


class TestCPIDates:
    """Tests for CPI release date retrieval."""

    def test_cpi_2026_returns_twelve_dates(
        self, provider: FedCalendarProvider
    ) -> None:
        """Test that 2026 CPI schedule has 12 release dates."""
        dates = provider.get_event_dates("CPI", 2026)
        assert len(dates) == 12

    def test_cpi_dates_are_sorted(
        self, provider: FedCalendarProvider
    ) -> None:
        """Test that CPI dates are in ascending order."""
        dates = provider.get_event_dates("CPI", 2026)
        assert dates == sorted(dates)

    def test_cpi_first_date_2026(
        self, provider: FedCalendarProvider
    ) -> None:
        """Test the first CPI date in 2026."""
        dates = provider.get_event_dates("CPI", 2026)
        assert dates[0] == date(2026, 1, 14)

    def test_cpi_unsupported_year_raises(
        self, provider: FedCalendarProvider
    ) -> None:
        """Test that an unsupported year raises ProviderError."""
        with pytest.raises(ProviderError, match="not in schedule"):
            provider.get_event_dates("CPI", 2020)


class TestInvalidEventType:
    """Tests for invalid event type handling."""

    def test_unknown_event_type_raises(
        self, provider: FedCalendarProvider
    ) -> None:
        """Test that an unknown event type raises ProviderError."""
        with pytest.raises(ProviderError, match="Unknown event type"):
            provider.get_event_dates("INVALID", 2026)

    def test_empty_event_type_raises(
        self, provider: FedCalendarProvider
    ) -> None:
        """Test that an empty event type raises ProviderError."""
        with pytest.raises(ProviderError, match="Unknown event type"):
            provider.get_event_dates("", 2026)
