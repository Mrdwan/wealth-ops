"""FRED (Federal Reserve Economic Data) Provider.

Provides macro economic data: VIX, Yield Curve, Fed Funds Rate, CPI.
FRED data is single-value time series, not OHLCV.
"""

from datetime import date

import httpx
import pandas as pd

from src.modules.data.protocols import ProviderError
from src.shared.logger import get_logger

logger = get_logger(__name__)


class FredProvider:
    """FRED economic data provider.

    Fetches observations from the FRED API for macro indicators.
    Handles FRED's convention of using '.' for missing values.
    """

    def __init__(self, api_key: str) -> None:
        """Initialize FredProvider.

        Args:
            api_key: FRED API key (free at https://fred.stlouisfed.org/docs/api/).
        """
        self._api_key = api_key
        self._base_url = "https://api.stlouisfed.org/fred/series/observations"

    @property
    def name(self) -> str:
        """Provider name."""
        return "FRED"

    def get_observations(
        self,
        series_id: str,
        start_date: date,
        end_date: date,
    ) -> pd.DataFrame:
        """Fetch time series observations from FRED.

        Args:
            series_id: FRED series ID (e.g., 'VIXCLS', 'T10Y2Y').
            start_date: Start date (inclusive).
            end_date: End date (inclusive).

        Returns:
            DataFrame with date index and 'value' column.
            Missing values (FRED uses '.') are dropped.

        Raises:
            ProviderError: If the FRED API fails.
        """
        logger.info(
            "Fetching observations from FRED",
            extra={
                "series_id": series_id,
                "start": str(start_date),
                "end": str(end_date),
            },
        )

        params = {
            "series_id": series_id,
            "api_key": self._api_key,
            "file_type": "json",
            "observation_start": start_date.isoformat(),
            "observation_end": end_date.isoformat(),
        }

        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.get(self._base_url, params=params)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as e:
            raise ProviderError(
                self.name,
                series_id,
                f"HTTP {e.response.status_code}: {e.response.text}",
            ) from e
        except httpx.RequestError as e:
            raise ProviderError(self.name, series_id, str(e)) from e

        observations = data.get("observations", [])
        if not observations:
            raise ProviderError(self.name, series_id, "No observations returned")

        return self._normalize(observations)

    def _normalize(self, observations: list[dict[str, str]]) -> pd.DataFrame:
        """Normalize FRED observations to a clean DataFrame.

        FRED returns observations as:
            [{"date": "2024-01-02", "value": "16.50"}, ...]
        Missing values are represented as '.'.

        Args:
            observations: Raw FRED API observations.

        Returns:
            DataFrame with date index and float 'value' column.
            Rows with missing values are dropped.
        """
        records = []
        for obs in observations:
            if obs.get("value") == ".":
                continue
            try:
                records.append(
                    {
                        "date": date.fromisoformat(obs["date"]),
                        "value": float(obs["value"]),
                    }
                )
            except (ValueError, KeyError):
                continue

        if not records:
            return pd.DataFrame(columns=["value"])

        df = pd.DataFrame(records)
        df = df.set_index("date")
        return df.sort_index()
