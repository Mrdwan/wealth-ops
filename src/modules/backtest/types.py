from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Literal, Optional

import pandas as pd


@dataclass
class Trade:
    """Represents a single executed trade."""
    ticker: str
    entry_date: date
    entry_price: float
    exit_date: Optional[date] = None
    exit_price: Optional[float] = None
    size: float = 0.0
    direction: Literal["LONG", "SHORT"] = "LONG"
    status: Literal["OPEN", "CLOSED"] = "OPEN"
    pnl: float = 0.0
    pnl_pct: float = 0.0
    exit_reason: str = ""
    commission: float = 0.0
    funding_fees: float = 0.0

    def close(self, exit_date: date, exit_price: float, reason: str) -> None:
        """Close the trade and calculate P&L."""
        self.exit_date = exit_date
        self.exit_price = exit_price
        self.exit_reason = reason
        self.status = "CLOSED"
        
        if self.entry_price > 0:
            raw_pnl = (self.exit_price - self.entry_price) * self.size
            if self.direction == "SHORT":
                raw_pnl = (self.entry_price - self.exit_price) * self.size
            
            self.pnl = raw_pnl - self.commission - self.funding_fees
            # Simple return on capital allocated
            cost_basis = self.entry_price * self.size
            if cost_basis > 0:
                self.pnl_pct = self.pnl / cost_basis


@dataclass
class BacktestResult:
    """Aggregated results of a backtest run."""
    ticker: str
    trades: list[Trade] = field(default_factory=list)
    equity_curve: pd.DataFrame = field(default_factory=pd.DataFrame)
    final_equity: float = 0.0
    total_trades: int = 0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    max_drawdown_pct: float = 0.0
    sharpe_ratio: float = 0.0
    annualized_return: float = 0.0

    def calculate_stats(self, initial_capital: float) -> None:
        """Calculate aggregate statistics from trades."""
        if not self.trades:
            self.final_equity = initial_capital
            return

        closed_trades = [t for t in self.trades if t.status == "CLOSED"]
        self.total_trades = len(closed_trades)
        
        if self.total_trades > 0:
            wins = [t for t in closed_trades if t.pnl > 0]
            losses = [t for t in closed_trades if t.pnl <= 0]
            self.win_rate = len(wins) / self.total_trades
            
            gross_profit = sum(t.pnl for t in wins)
            gross_loss = abs(sum(t.pnl for t in losses))
            
            if gross_loss > 0:
                self.profit_factor = gross_profit / gross_loss
            else:
                self.profit_factor = float('inf') if gross_profit > 0 else 0.0
