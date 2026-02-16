from __future__ import annotations

from typing import Iterator

import pandas as pd


class WalkForwardSplitter:
    """Splits time-series data into expanding training windows and fixed test windows.
    
    Implements the Walk-Forward Optimization method:
    1. Train on [Start, Start + Train_Size]
    2. Test on [Start + Train_Size, Start + Train_Size + Test_Size]
    3. Roll forward by Step_Size
    4. Repeat until end of data.
    """

    def __init__(
        self,
        train_years: int = 3,
        test_months: int = 6,
        roll_months: int = 6,
        min_periods: int = 0  # Optional minimum number of splits required
    ):
        """
        Args:
            train_years: Length of the initial training window in years.
            test_months: Length of the out-of-sample test window in months.
            roll_months: How many months to shift forward in each step.
            min_periods: Minimum required data points (rows) to even attempt a split.
        """
        self.train_months = train_years * 12
        self.test_months = test_months
        self.roll_months = roll_months
        self.min_periods = min_periods

    def split(self, df: pd.DataFrame) -> Iterator[tuple[pd.DataFrame, pd.DataFrame]]:
        """
        Yields (train_df, test_df) tuples.
        
        Assumes df index is DatetimeIndex and sorted.
        """
        if df.empty or not isinstance(df.index, pd.DatetimeIndex):
            return

        start_date = df.index.min()
        max_date = df.index.max()
        
        # Calculate approximate month offsets
        # We use pd.DateOffset for accurate calendar months
        
        current_train_end = start_date + pd.DateOffset(months=self.train_months)
        
        while current_train_end < max_date:
            test_end = current_train_end + pd.DateOffset(months=self.test_months)
            
            # Create masks
            # Train: Expanding window from VERY BEGINNING to current_train_end
            # NOTE: Architecture says "3 years (expanding)". This implies start is fixed.
            train_mask = (df.index < current_train_end)
            test_mask = (df.index >= current_train_end) & (df.index < test_end)
            
            train_df = df.loc[train_mask]
            test_df = df.loc[test_mask]
            
            if not test_df.empty and len(train_df) >= self.min_periods:
                yield train_df, test_df
            
            # Step forward
            current_train_end = current_train_end + pd.DateOffset(months=self.roll_months)
            
            # Break if next test start is beyond data
            if current_train_end >= max_date:
                break
