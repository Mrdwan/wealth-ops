
from datetime import date
from src.modules.backtest.types import Trade, BacktestResult

def test_trade_zero_cost_basis():
    # Entry price 100.0, Size 0 -> Cost basis 0.0 -> pnl_pct logic check (should check > 0)
    # If Entry > 0, we enter the calculation block.
    t = Trade("A", date(2023,1,1), 100.0, size=0)
    t.close(date(2023,1,2), 110.0, "TP")
    
    # PnL = (110 - 100) * 0 = 0.
    assert t.pnl == 0.0
    # Cost basis = 0. pnl_pct should remain 0.0
    assert t.pnl_pct == 0.0

def test_stats_open_trades_only():
    # BacktestResult with only OPEN trades
    t = Trade("A", date(2023,1,1), 100.0, size=10, status="OPEN")
    
    res = BacktestResult("A", [t])
    res.calculate_stats(1000.0)
    
    # total_trades count CLOSED trades?
    # Logic: closed_trades = [t for t in self.trades if t.status == "CLOSED"]
    # self.total_trades = len(closed_trades)
    
    assert res.total_trades == 0
    # And logic skips the stats calculation block
    assert res.win_rate == 0.0
