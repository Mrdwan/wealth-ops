from __future__ import annotations

import collections
import logging
from dataclasses import replace
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from src.modules.backtest.types import BacktestResult, Trade
from src.shared.profiles import AssetProfile

if TYPE_CHECKING:
    from logging import Logger


class ExecutionSimulator:
    """Simulates realistic trade execution with Trap Orders, gaps, and slippage."""

    def __init__(self, profile: AssetProfile, logger: Optional[Logger] = None):
        self.profile = profile
        self.logger = logger or logging.getLogger(__name__)
        self.commission_per_share = 0.005 if profile.asset_class == "EQUITY" else 0.0
        self.min_commission = 1.0 if profile.asset_class == "EQUITY" else 0.0
        # IG Overnight funding (~0.008% per night, simplified)
        self.funding_rate_daily = 0.00008 if profile.asset_class == "COMMODITY" else 0.0

    def calculate_trap_levels(self, row: pd.Series) -> Tuple[float, float]:
        """Calculate Buy Stop and Limit prices for the NEXT day."""
        atr = row["atr_14"]
        high = row["high"]
        
        buy_stop = high + (0.02 * atr)
        # Limit at Stop + (0.05 * ATR)
        limit_price = buy_stop + (0.05 * atr)
        
        return buy_stop, limit_price

    def check_entry(
        self, 
        current_row: pd.Series, 
        buy_stop: float, 
        limit_price: float
    ) -> Optional[float]:
        """Check if a Trap Order is filled on the current day.
        
        Args:
            current_row: Today's OHLCV data.
            buy_stop: The trigger price set yesterday.
            limit_price: The max price we are willing to pay.
            
        Returns:
            Fill price if filled, None otherwise.
        """
        open_price = current_row["open"]
        high_price = current_row["high"]
        
        # 1. Gap Open Check
        if open_price > limit_price:
            return None  # Gap over limit, no fill
            
        # 2. Trigger Check
        if high_price < buy_stop:
            return None  # Price never reached stop
            
        # 3. Fill Logic
        # If open is below stop, but high reached it -> Fill at Stop (Stop Limit logic)
        # If open is above stop (but below limit) -> Fill at Open (Slippage)
        fill_price = max(open_price, buy_stop)
        
        if fill_price > limit_price:
            return None # Should not happen given gap check, but safety
            
        return fill_price


class BacktestEngine:
    """Orchestrates the backtest over a dataframe."""

    def __init__(self, profile: AssetProfile, initial_capital: float = 10_000.0):
        self.profile = profile
        self.initial_capital = initial_capital
        self.simulator = ExecutionSimulator(profile)
        self.logger = logging.getLogger(__name__)

    def run(self, ticker: str, data: pd.DataFrame) -> BacktestResult:
        """Run backtest on a single asset."""
        
        trades: List[Trade] = []
        equity_curve: List[Dict[str, Any]] = []
        
        # State
        current_capital = self.initial_capital
        open_trade: Optional[Trade] = None
        pending_buy_stop: Optional[float] = None
        pending_limit: Optional[float] = None
        
        stop_loss: Optional[float] = None
        take_profit: Optional[float] = None
        days_in_trade = 0
        highest_high_since_entry = 0.0

        # Iterate
        # We need previous row for signal generation relative to "tomorrow" execution
        # data iteration: we use itertuples for speed, but valid columns access is key.
        # columns: open, high, low, close, atr_14, adx_14, composite_signal, etc.
        
        # Ensure signal column exists, default to 0 if not
        if "composite_signal" not in data.columns:
            # If explicit signal column missing, maybe use a dummy or skip
            # For now assume it's there or we can't trade
            pass

        for i in range(len(data)):
            date = data.index[i]
            row = data.iloc[i]
            
            # --- 1. Manage Open Trade ---
            if open_trade:
                days_in_trade += 1
                
                # Update stats
                current_price = row["close"]
                high = row["high"]
                low = row["low"]
                open_px = row["open"]
                atr = row["atr_14"]
                adx = row["adx_14"]
                
                # Update highest high for trailing stop
                if high > highest_high_since_entry:
                    highest_high_since_entry = high
                
                # Calculate Chandelier Stop
                # High - 2 * ATR
                chandelier_stop = highest_high_since_entry - (2.0 * atr)
                
                # Update Stop Loss (Ratchet only - never lower it for longs)
                if stop_loss is not None:
                    stop_loss = max(stop_loss, chandelier_stop)
                else:
                    stop_loss = chandelier_stop # pragma: no cover

                # Check Exits
                exit_price = None
                exit_reason = ""
                
                # A. Stop Loss (Gap handling)
                if low < stop_loss:
                    # If open was below stop, we gapped down -> exit at Open
                    # Else exit at Stop
                    exit_price = min(open_px, stop_loss) if open_px < stop_loss else stop_loss
                    exit_reason = "STOP_LOSS"
                
                # B. Take Profit (Gap handling)
                elif take_profit and high > take_profit:
                    # If open was above TP, gap up -> exit at Open (better price)
                    # Else exit at TP
                    exit_price = max(open_px, take_profit) if open_px > take_profit else take_profit
                    exit_reason = "TAKE_PROFIT"
                
                # C. Time Stop
                elif days_in_trade >= 10:
                    exit_price = row["close"]
                    exit_reason = "TIME_STOP"

                # Apply Fee
                # Overnight funding for Commodities
                daily_funding = 0.0
                if self.simulator.funding_rate_daily > 0:
                     cost_basis = open_trade.entry_price * open_trade.size
                     daily_funding = cost_basis * self.simulator.funding_rate_daily
                     open_trade.funding_fees += daily_funding

                if exit_price:
                    open_trade.close(date.date(), exit_price, exit_reason)
                    
                    # Commission
                    commission = 0.0
                    if self.profile.asset_class == "EQUITY":
                        commission = max(self.simulator.min_commission, 
                                       open_trade.size * self.simulator.commission_per_share)
                    open_trade.commission = commission
                    
                    # Update Capital
                    current_capital += open_trade.pnl
                    trades.append(open_trade)
                    open_trade = None
                    stop_loss = None
                    take_profit = None
                    days_in_trade = 0
            
            # --- 2. Check Pending Orders (Trap Entry) ---
            elif pending_buy_stop and pending_limit:
                fill_price = self.simulator.check_entry(row, pending_buy_stop, pending_limit)
                
                if fill_price:
                    # Execute Buy
                    # Size calculation: 
                    # Risk = 2% of Current Capital (Mock logic, real logic in architecture is more complex)
                    # For Step 2B.3 we implement the Sizing rule: 
                    # min((Portfolio * 0.02) / (2 * ATR), Portfolio * 0.15 / Price)
                    
                    risk_per_share = 2.0 * row["atr_14"]
                    max_risk_amount = current_capital * 0.02
                    
                    # Shares based on risk
                    size_risk = max_risk_amount / risk_per_share if risk_per_share > 0 else 0
                    
                    # Shares based on capital cap (15%)
                    max_capital_alloc = current_capital * 0.15
                    size_cap = max_capital_alloc / fill_price if fill_price > 0 else 0
                    
                    size = min(size_risk, size_cap)
                    
                    # Round down to integer for stocks provided broker supports fractional? 
                    # IBKR supports fractional, but let's stick to int or float. 
                    # For consistency with "lots" in Forex/Commodity, float is safer.
                    if self.profile.asset_class == "EQUITY":
                        size = int(size)
                    
                    if size > 0:
                        commission = 0.0
                        if self.profile.asset_class == "EQUITY":
                            commission = max(self.simulator.min_commission, 
                                           size * self.simulator.commission_per_share)
                            # Deduct commission upfront? No, usually deducted from cash balance.
                        
                        open_trade = Trade(
                            ticker=ticker,
                            entry_date=date.date(),
                            entry_price=fill_price,
                            size=size,
                            commission=commission
                        )
                        
                        # Init Exits
                        atr = row["atr_14"]
                        adx = row["adx_14"]
                        
                        highest_high_since_entry = fill_price # or High of day? "Highest High" usually starts with entry day high
                        if row["high"] > fill_price:
                            highest_high_since_entry = row["high"]
                            
                        # Initial Stop: Entry - 2 ATR
                        stop_loss = fill_price - (2.0 * atr)
                        
                        # Take Profit: clamp(2 + ADX/30, 2.5, 4.5) * ATR
                        # Added to entry price
                        tp_multiple = max(2.5, min(4.5, 2.0 + (adx / 30.0)))
                        take_profit = fill_price + (tp_multiple * atr)
                        
                        days_in_trade = 0
                
                # Pending order expires if not filled (TTL = 1 session)
                pending_buy_stop = None
                pending_limit = None

            # --- 3. Generate New Signals (if no trade open) ---
            # Architecture says: "Gap-Through Policy: no fill if opens above limit. By design."
            # Implicitly this means we place orders for TOMORROW based on TODAY's Close data.
            
            if not open_trade and "composite_signal" in data.columns:
                 # Signal Logic: 
                 # composite_signal column is present.
                 # 1 = Buy, -1 = Sell, 0 = Neutral.
                 # We only trade Longs.
                 signal = row.get("composite_signal", 0)
                 
                 # Also check simple hard guards if variables present
                 # e.g. "adx_14" > 20
                 adx_ok = row["adx_14"] > 20
                 
                 if signal == 1 and adx_ok:
                     pending_buy_stop, pending_limit = self.simulator.calculate_trap_levels(row)
            
            # Record Equity
            # Mark-to-market
            daily_equity = current_capital
            if open_trade:
                # Unrealized P&L
                # ignore commissions here for simplicity or include?
                unrealized = (row["close"] - open_trade.entry_price) * open_trade.size
                daily_equity += unrealized
            
            equity_curve.append({
                "date": date,
                "equity": daily_equity,
                "drawdown": 0.0 # Calculate later?
            })
            
        # Compile Result
        if not equity_curve:
            df_equity = pd.DataFrame(columns=["equity", "drawdown"])
        else:
            df_equity = pd.DataFrame(equity_curve).set_index("date")
            # Calculate DD
            rolling_max = df_equity["equity"].cummax()
            df_equity["drawdown"] = (df_equity["equity"] - rolling_max) / rolling_max
        
        result = BacktestResult(
            ticker=ticker,
            trades=trades,
            equity_curve=df_equity
        )
        result.calculate_stats(self.initial_capital)
        
        return result
