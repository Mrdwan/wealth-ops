"""Federal Reserve / BLS Economic Calendar Provider.

Provides dates for FOMC meetings, NFP releases, and CPI releases
using hardcoded schedules (Fed/BLS publish these annually) and
algorithmic computation (NFP = first Friday of each month).
"""

from datetime import date

from src.modules.data.protocols import ProviderError
from src.shared.logger import get_logger

logger = get_logger(__name__)

# FOMC meeting conclusion dates (announcement day).
# Source: https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm
_FOMC_DATES: dict[int, list[date]] = {
    2025: [
        date(2025, 1, 29),
        date(2025, 3, 19),
        date(2025, 5, 7),
        date(2025, 6, 18),
        date(2025, 7, 30),
        date(2025, 9, 17),
        date(2025, 10, 29),
        date(2025, 12, 17),
    ],
    2026: [
        date(2026, 1, 28),
        date(2026, 3, 18),
        date(2026, 4, 29),
        date(2026, 6, 17),
        date(2026, 7, 29),
        date(2026, 9, 16),
        date(2026, 10, 28),
        date(2026, 12, 16),
    ],
    2027: [
        date(2027, 1, 27),
        date(2027, 3, 17),
        date(2027, 5, 5),
        date(2027, 6, 16),
        date(2027, 7, 28),
        date(2027, 9, 22),
        date(2027, 10, 27),
        date(2027, 12, 15),
    ],
}

# CPI release dates (8:30 AM ET publication day).
# Source: https://www.bls.gov/schedule/news_release/cpi.htm
_CPI_DATES: dict[int, list[date]] = {
    2025: [
        date(2025, 1, 15),
        date(2025, 2, 12),
        date(2025, 3, 12),
        date(2025, 4, 10),
        date(2025, 5, 13),
        date(2025, 6, 11),
        date(2025, 7, 11),
        date(2025, 8, 12),
        date(2025, 9, 10),
        date(2025, 10, 14),
        date(2025, 11, 12),
        date(2025, 12, 10),
    ],
    2026: [
        date(2026, 1, 14),
        date(2026, 2, 11),
        date(2026, 3, 11),
        date(2026, 4, 14),
        date(2026, 5, 12),
        date(2026, 6, 10),
        date(2026, 7, 14),
        date(2026, 8, 12),
        date(2026, 9, 15),
        date(2026, 10, 13),
        date(2026, 11, 12),
        date(2026, 12, 10),
    ],
    2027: [
        date(2027, 1, 13),
        date(2027, 2, 10),
        date(2027, 3, 10),
        date(2027, 4, 13),
        date(2027, 5, 12),
        date(2027, 6, 10),
        date(2027, 7, 14),
        date(2027, 8, 11),
        date(2027, 9, 14),
        date(2027, 10, 13),
        date(2027, 11, 10),
        date(2027, 12, 10),
    ],
}

# Supported event types.
_VALID_EVENT_TYPES: frozenset[str] = frozenset({"FOMC", "NFP", "CPI"})


class FedCalendarProvider:
    """Economic calendar provider using hardcoded Fed/BLS schedules.

    FOMC and CPI dates are hardcoded from official published schedules.
    NFP (Non-Farm Payrolls) dates are computed algorithmically as the
    first Friday of each month.
    """

    @property
    def name(self) -> str:
        """Provider name."""
        return "FedCalendar"

    def get_event_dates(self, event_type: str, year: int) -> list[date]:
        """Fetch scheduled dates for a macro event type in a given year.

        Args:
            event_type: Event identifier ('FOMC', 'NFP', or 'CPI').
            year: Calendar year to fetch dates for.

        Returns:
            Sorted list of event dates for the given year.

        Raises:
            ProviderError: If event_type is unknown or year is unsupported.
        """
        if event_type not in _VALID_EVENT_TYPES:
            raise ProviderError(
                self.name,
                event_type,
                f"Unknown event type: {event_type}. "
                f"Supported: {sorted(_VALID_EVENT_TYPES)}",
            )

        if event_type == "NFP":
            return self._compute_nfp_dates(year)

        if event_type == "FOMC":
            return self._get_static_dates(_FOMC_DATES, "FOMC", year)

        # CPI
        return self._get_static_dates(_CPI_DATES, "CPI", year)

    def _get_static_dates(
        self,
        schedule: dict[int, list[date]],
        event_type: str,
        year: int,
    ) -> list[date]:
        """Look up hardcoded dates for a year.

        Args:
            schedule: Dict mapping years to date lists.
            event_type: Event name for error messages.
            year: Calendar year.

        Returns:
            Sorted list of dates.

        Raises:
            ProviderError: If the year is not in the schedule.
        """
        if year not in schedule:
            available = sorted(schedule.keys())
            raise ProviderError(
                self.name,
                event_type,
                f"Year {year} not in schedule. "
                f"Available: {available}",
            )
        return sorted(schedule[year])

    def _compute_nfp_dates(self, year: int) -> list[date]:
        """Compute NFP release dates (first Friday of each month).

        Args:
            year: Calendar year.

        Returns:
            Sorted list of 12 NFP dates for the year.
        """
        dates: list[date] = []
        for month in range(1, 13):
            first_day = date(year, month, 1)
            # weekday(): Monday=0 ... Friday=4
            days_ahead = (4 - first_day.weekday()) % 7
            first_friday = date(year, month, 1 + days_ahead)
            dates.append(first_friday)
        return dates
