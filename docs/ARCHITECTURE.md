# 🏛️ Wealth-Ops v3.0 Architecture

## 1. Core Philosophy
A cloud-native, **notification-first** trading advisory system for a **Solo Trader (Irish Tax Resident, Dublin-based)**.
- **Strategy:** "The Swing Sniper" (Daily Candles, 3–10 day hold) + Momentum Composite as baseline.
- **Tax Logic:** IG Spread Betting for Commodities (**Tax-Free**). IBKR for Stocks (**33% CGT**). Minimize ETFs (41% Exit Tax).
- **Quality:** 100% Test Coverage required for all financial logic.
- **Hybrid AI Model:** "Hard Guards, Soft Skills." We enforce Risk Rules (Hard), AI learns Entry Patterns (Soft).
- **Default State:** 100% CASH. Capital deploys only when ALL gatekeepers are green.
- **Non-Negotiable:** Risk management is the GATE, not the afterthought. Every signal passes through risk checks before reaching the trader.

### What Changed from v2.0
| Area | v2.0 | v3.0 | Why |
|------|------|------|-----|
| Broker | Unspecified | **IG (Gold, tax-free) + IBKR (Stocks, 33% CGT)** | Tax optimization = biggest "edge" for Irish traders |
| Gold Instrument | GLD ETF (41% tax) | **XAU/USD Spread Bet on IG** (0% tax) | Saves ~€750/year on €15K portfolio |
| Risk Management | Static (Exposure Cap only) | **Dynamic drawdown throttling** (8% reduce, 15% halt) | Prevents catastrophic loss spirals |
| Signal Baseline | XGBoost only | **Momentum Composite (academic) + XGBoost (ML)** | Dual-signal validation: rules + ML |
| Backtesting | 1,000-day replay | **Walk-forward + Monte Carlo + shuffled-price test** | Statistical rigor from López de Prado |
| Telegram | One-way pulse | **Full two-way command interface** | Portfolio management from phone |
| Data Sources | Tiingo + Yahoo fallback | **Tiingo (stocks + forex) + FRED (macro)** | Direct gold pricing via Tiingo Forex, not ETF proxy |
| Notification | Daily briefing only | **Signal cards + position alerts + daily/weekly reports** | Actionable trade information |

---

## 2. The Cloud Stack (AWS)

### 2.1 Production Infrastructure
- **Compute (Signals):** AWS Lambda (ARM/Graviton2, 3GB RAM, Container Image). Triggered by EventBridge Scheduler.
- **Compute (Training):** AWS Fargate (ECS). Spins up for XGBoost model training + bulk data bootstrap.
- **Compute (Backtests):** EC2 Spot (c6g.medium, ~$0.017/hr). On-demand, launched via script.
- **State Store:** AWS DynamoDB (Portfolio, Ledger, Config, Signal Log).
- **Data Lake:** AWS S3 (Parquet OHLCV, Model Artifacts, Backtest Results).
- **Orchestration:** EventBridge Scheduler (cron triggers). Step Functions for complex multi-step workflows.
- **Notifications:** Lambda Function URL for Telegram webhook (no API Gateway needed).
- **Monitoring:** CloudWatch (7 alarms within free tier), SNS for failure alerts.
- **Container Registry:** ECR (~500MB container image for Lambda).

### 2.2 Cost Model
| Component | Monthly Cost | Notes |
|-----------|-------------|-------|
| Lambda (6 invocations/day, 3GB ARM) | $0.00 | Well within 400K GB-s free tier |
| EventBridge Scheduler | $0.00 | ~180/month vs 14M free |
| DynamoDB | $0.00 | <1GB vs 25GB free tier |
| S3 (10GB Parquet + requests) | $0.24 | Only non-free component |
| ECR (container image) | $0.05 | ~500MB image |
| CloudWatch (7 alarms) | $0.00 | Within 10-alarm free tier |
| EC2 Spot (backtesting, ~10hr/month) | $0.17 | On-demand only |
| Fargate (training, ~2hr/month) | ~$0.10 | Monthly retraining |
| **Total** | **~$0.56/month** | **$300 lasts 44+ years** |

### 2.3 Execution Schedules
| Schedule | Function | Purpose |
|----------|----------|---------|
| Daily 23:00 UTC | `data_ingest` | Fetch EOD data, validate, store in S3 |
| Daily 23:15 UTC | `signal_scan` | Generate signals, run through guards, notify |
| Daily 09:00 UTC | `daily_briefing` | Portfolio summary, risk health, open position updates |
| Weekly Sunday 18:00 UTC | `weekly_review` | Performance metrics, regime reassessment |
| Monthly 1st 02:00 UTC | `model_retrain` | Retrain XGBoost models (Fargate) |

> **Note:** No intraday monitoring needed. Stop-loss, take-profit, and trailing stops are placed as orders on the broker (IG/IBKR). The broker executes them in real-time.

### 2.4 Local Development (Docker Compose)
Carried forward from v2.0:
| Service | Container | Purpose |
|---------|-----------|---------|
| `dev` | `wealth-ops-dev` | Python 3.13 + Poetry dev environment |
| `localstack` | `wealth-ops-localstack` | Emulates S3, DynamoDB locally |
| `test` | `wealth-ops-test` | Lightweight pytest runner (pre-commit) |

---

## 3. Data Sources & Ingestion

### 3.1 Data Provider Strategy

> **Two sources only.** Tiingo for all market/price data (EOD). FRED for macro indicators.

| Data Type | Primary | Backup | Rationale |
|-----------|---------|--------|-----------|
| US Stocks (EOD) | **Tiingo** (Official API) | Yahoo Finance | Tiingo: 30+ years, 3-exchange cross-validation, proprietary error-checking |
| Gold/Silver (Forex) | **Tiingo Forex** | Yahoo Finance | Direct XAU/USD, XAG/USD pricing from tier-1 banks for IG spread betting (not GLD ETF proxy) |
| Macro (VIX, Yield Curve) | **FRED** (Free API) | — | Decades of history, authoritative source |
| Market Data (SPY, DXY) | **Tiingo** | Yahoo Finance | Needed for regime filters and relative strength |
| Earnings Calendar | **Tiingo Fundamentals** | SEC EDGAR | Event Guard requires next_earnings_date for equities |
| Economic Calendar | **FRED + Finnhub** (Free) | — | FOMC dates, NFP for commodity/forex blackouts |

### 3.2 Tiingo Free Tier Budget
| Resource | Limit | Our Usage | Headroom |
|----------|-------|-----------|----------|
| Requests/hour | 50 | ~17 (daily update) | 66% spare |
| Requests/day | 1,000 | ~17 | 98% spare |
| Unique symbols/month | 500 | ~17 | 97% spare |
| Historical depth | 30+ years | 10 years minimum | ✅ |

**Bootstrap strategy:** Initial 10-year data download uses ~17 symbols × 1 request each = 17 requests. Tiingo returns full history in a single request per symbol. No rate limit concern for bootstrap.

### 3.3 Data Validation Rules (Enforced on Every Ingest)
```
- high >= low
- high >= open AND high >= close
- low <= open AND low <= close
- volume >= 0 (stocks/ETFs only; forex has no centralized volume)
- No null values in OHLCV
- Timestamps are monotonically increasing
- No duplicate timestamps
- Price within 5% of previous close (flag anomalies, don't auto-reject)
- Cross-reference: if Tiingo XAU/USD forex price and Tiingo GLD ETF price diverge > 2%, alert via Telegram
```

### 3.4 S3 Data Structure
```
s3://wealth-ops-data/
├── ohlcv/
│   ├── stocks/           # Tiingo source
│   │   ├── AAPL/daily/2026-02.parquet
│   │   ├── NVDA/daily/...
│   │   └── SPY/daily/...   # Regime index
│   ├── forex/             # Tiingo Forex source
│   │   ├── XAUUSD/daily/...
│   │   └── XAGUSD/daily/...
│   ├── macro/             # FRED source
│   │   ├── VIX.parquet
│   │   ├── T10Y2Y.parquet
│   │   ├── FEDFUNDS.parquet
│   │   └── CPIAUCSL.parquet
│   └── indices/           # Tiingo source
│       └── DXY/daily/...   # Dollar index (UUP proxy or DX-Y.NYB)
├── models/
│   ├── xgboost/           # Per-asset models
│   │   ├── AAPL_v3_20260201.joblib
│   │   └── XAUUSD_v3_20260201.joblib
│   ├── regime/            # LightGBM regime classifier
│   │   └── regime_classifier_v1.joblib
│   └── scalers/
├── backtests/
│   ├── walkforward_2026-02-12/
│   └── montecarlo_2026-02-12/
└── earnings/
    └── calendar_2026-02.json
```

---

## 4. Broker Strategy (NEW in v3.0)

### 4.1 Dual-Broker Setup

#### Gold & Commodities: IG Ireland (Spread Betting)
- **Why:** Profits are **TAX-FREE** in Ireland (spread betting = gambling, exempt from CGT and income tax).
- **Instruments:** XAU/USD, XAG/USD, Oil, Indices.
- **Minimum trade:** 0.01 lots (micro).
- **Gold spread:** ~0.3 points.
- **API:** IG REST Trading API (Python SDK available).
- **Overnight funding:** Yes — factor into swing trade cost calculation.
- **⚠️ Tax caveat:** If Revenue determines spread betting is primary income, profits could be reclassified. Unlikely with Workhuman employment income.

#### US Stocks: IBKR Ireland (IBIE)
- **Why:** Lowest commissions, best API, direct market access.
- **Instruments:** US individual stocks (future: ETFs).
- **Commission:** $0.005/share (min $1.00).
- **Account type:** IBKR Pro (required for API access).
- **CGT:** 33% on gains, €1,270 annual exemption.
- **API:** IBKR Web API (REST + WebSocket).

#### Tax Impact (Real Numbers)
| Scenario | IBKR (33% CGT) | IG Spread Bet (0%) | Annual Savings |
|----------|----------------|---------------------|----------------|
| €1,000 gold profit | €330 tax | €0 tax | **€330** |
| €2,000 gold profit | €660 tax | €0 tax | **€660** |
| €5,000 gold profit | €1,650 tax | €0 tax | **€1,650** |

### 4.2 Broker Abstraction Layer
```python
class BrokerInterface(ABC):
    """All broker integrations implement this interface."""
    def get_positions(self) -> List[Position]: ...
    def get_account_balance(self) -> AccountBalance: ...
    def get_open_orders(self) -> List[Order]: ...
    # Future: auto-execution
    # def place_order(self, order: Order) -> OrderResult: ...

class IGBroker(BrokerInterface):       # Gold, Commodities, Forex
class IBKRBroker(BrokerInterface):     # US Stocks
class PaperBroker(BrokerInterface):    # Testing (Phase 1–2)
```

### 4.3 Broker Field in Asset Profile
Added to DynamoDB:Config profile:
```
broker: "IG" | "IBKR" | "PAPER"
tax_rate: 0.0 | 0.33 | 0.41
```

---

## 5. Asset Profiles (Extended from v2.0)

Each asset in `DynamoDB:Config` carries a profile that configures the entire pipeline.

| Field | Description | Options |
|-------|-------------|---------|
| `asset_class` | Instrument category | `EQUITY`, `COMMODITY`, `FOREX` |
| `regime_index` | Ticker for Macro Gate | `SPY`, `DXY`, or custom |
| `regime_direction` | Buy condition relative to regime | `BULL`, `BEAR`, `ANY` |
| `vix_guard` | Panic Guard applies | `true`, `false` |
| `event_guard` | Earnings Guard applies | `true`, `false` |
| `macro_event_guard` | FOMC/NFP blackout applies | `true`, `false` | ← **NEW v3** |
| `volume_features` | OBV + Volume Ratio computed | `true`, `false` |
| `benchmark_index` | Relative Strength benchmark | `SPY`, `DXY`, or `null` |
| `concentration_group` | Concentration Limit grouping | Sector, commodity type, etc. |
| `broker` | Execution broker | `IG`, `IBKR`, `PAPER` | ← **NEW v3** |
| `tax_rate` | Applicable tax rate | `0.0`, `0.33`, `0.41` | ← **NEW v3** |
| `data_source` | Primary data provider | `TIINGO`, `FRED` | ← **NEW v3** |

### Pre-Built Profiles (Updated for v3)

| Profile | `regime_index` | `regime_dir` | `vix` | `event` | `macro_event` | `volume` | `benchmark` | `broker` | `tax` | Example |
|---------|---------------|-------------|-------|---------|---------------|---------|------------|----------|------|---------|
| **EQUITY** | SPY | BULL | true | true | false | true | SPY | IBKR | 0.33 | AAPL, NVDA |
| **COMMODITY_HAVEN** | DXY | BEAR | false | false | **true** | false | DXY | **IG** | **0.0** | XAU/USD, XAG/USD |
| **COMMODITY_CYCLICAL** | SPY | BULL | true | false | **true** | true (ETF) | DXY | IG | 0.0 | Oil via IG |
| **FOREX** *(Phase 7)* | — | ANY | false | false | **true** | false | DXY | IG | 0.0 | EUR/USD |

**Key v3 changes:**
- **COMMODITY_HAVEN now uses IG broker** (tax-free) and trades XAU/USD directly instead of GLD ETF.
- **`macro_event_guard`** added: blocks new entries around FOMC, NFP, CPI releases. Applies to COMMODITY and FOREX profiles.
- **`volume_features = false`** for COMMODITY_HAVEN when trading forex-style (XAU/USD has no centralized volume). Was `true` when using GLD ETF.
- **`data_source`** field routes the data pipeline to the correct provider. All market data sourced from Tiingo (stocks + forex + indices).

---

## 6. The Feature Vector (Per Asset, Per Day)

Carried forward from v2.0 with no changes. The feature set is profile-dependent.

### Base Features (All Asset Classes — 11 Features)

| # | Feature | Formula | Rationale |
|---|---------|---------|-----------|
| 1 | RSI (14) | Standard Wilder RSI | Overbought/oversold momentum |
| 2 | EMA_8 | Exponential Moving Average, 8-period | Short-term trend |
| 3 | EMA_20 | Exponential Moving Average, 20-period | Medium-term trend |
| 4 | EMA_50 | Exponential Moving Average, 50-period | Long-term trend |
| 5 | MACD Histogram | `EMA_12 - EMA_26 - Signal_9` | Momentum direction |
| 6 | ADX (14) | Average Directional Index | Trend strength |
| 7 | ATR (14) | Average True Range | Volatility (used for stops) |
| 8 | Upper Wick Ratio | `(High - Max(Open,Close)) / (High - Low)` | Shooting Star detection |
| 9 | Lower Wick Ratio | `(Min(Open,Close) - Low) / (High - Low)` | Hammer detection |
| 10 | EMA Fan (Boolean) | `EMA_8 > EMA_20 > EMA_50` | Aligned trend |
| 11 | Distance from 20d Low | `(Close - Min(Low, 20d)) / Close` | Donchian proximity |

### Class-Specific Features

| # | Feature | Applies To | Rationale |
|---|---------|-----------|-----------|
| 12 | OBV | EQUITY (`volume_features=true`) | Volume confirmation |
| 13 | Volume Ratio | EQUITY (`volume_features=true`) | Relative volume spike |
| 14 | Relative Strength | ALL (benchmark varies) | Outperformance detection |

**Feature Count:** EQUITY = 14, COMMODITY_HAVEN (XAU/USD) = 12, FOREX = 12.

**Edge Cases:**
- `(High - Low) == 0` → both wick ratios = `0.0`.
- `rs_ratio` normalized to rolling 20-day z-score.
- COMMODITY_HAVEN (XAU/USD via Tiingo Forex) has no centralized volume → OBV and Volume Ratio excluded.

---

## 7. Momentum Composite Score (NEW in v3.0)

**Purpose:** Academic-backed baseline signal that runs alongside XGBoost. Provides a second, independent opinion. If both agree, confidence is higher.

### Composite Calculation (6 Components)

| Component | Weight | Source | Academic Basis |
|-----------|--------|--------|----------------|
| Momentum (6/12-month) | 40% | Price returns, 1-month skip | Jegadeesh & Titman 1993, Moskowitz 2012 |
| Trend Confirmation | 20% | 50/200 DMA relationship | — |
| RSI Filter | 15% | RSI(14) distance from extremes | Moderate evidence as confirmation |
| Volume Confirmation | 10% | 20d/50d volume ratio | Institutional flow detection |
| ATR Volatility | 10% | Normalized ATR percentile | Prefer moderate volatility |
| Support/Resistance | 5% | Price clustering at local extremes | Osler 2003 (J. Finance) |

**All components are z-score normalized** before weighting to make them comparable.

```
composite = (0.40 × momentum_z + 0.20 × trend_z + 0.15 × rsi_z +
             0.10 × volume_z + 0.10 × volatility_z + 0.05 × sr_z)

Signal thresholds:
  STRONG_BUY  = composite > 2.0σ
  BUY         = composite > 1.5σ
  NEUTRAL     = between -1.5σ and 1.5σ
  SELL        = composite < -1.5σ
  STRONG_SELL = composite < -2.0σ
```

**Note:** Volume component is skipped for assets with `volume_features = false`. Weights redistribute proportionally.

### How Momentum Composite + XGBoost Work Together

| Momentum | XGBoost (>75%) | Action |
|----------|----------------|--------|
| BUY (>1.5σ) | PASS | **STRONG SIGNAL** — High confidence. Both agree. |
| BUY (>1.5σ) | FAIL | **MOMENTUM ONLY** — Lower confidence. Note in signal card. |
| NEUTRAL | PASS | **ML ONLY** — XGBoost sees a pattern momentum doesn't. Proceed with caution. |
| NEUTRAL | FAIL | **NO TRADE** — Neither system sees an opportunity. |
| SELL | PASS | **CONFLICT** — Do not trade. Conflicting signals = uncertainty. |
| SELL | FAIL | **AVOID** — Both bearish. Stay cash or consider exit. |

**Phase-in strategy:** Deploy Momentum Composite first (Phase 2A). Deploy XGBoost second (Phase 2B). Compare their performance independently for 3+ months before combining them.

---

## 8. The "Swing Sniper" Trading Strategy (Multi-Asset)

### A. The Setup
- **Candles:** Strictly **1-Day (Daily)** OHLCV.
- **Why:** Filter HFT noise, capture institutional flows.
- **Applies to:** All asset classes.

### B. The Hard Guards (Pass/Fail Gates)
Non-negotiable. If **any applicable** guard is RED, we stay in CASH.

| # | Guard | Scope | Rule | Condition | Fail Action |
|---|-------|-------|------|-----------|-------------|
| 1 | **Macro Gate** | Market | Regime_Index vs SMA(200) | `regime_dir != ANY` | Halt buying for this class |
| 2 | **Panic Guard** | Market | `VIX_Close < 30` | `vix_guard = true` | Halt buying for flagged assets |
| 3 | **Exposure Cap** | Portfolio | `count(open_positions) < max_positions` (per Section 9.1 capital tier) | Always | Halt all buying |
| 4 | **Trend Gate** | Per Asset | `ADX_14 > 20` | Always | Skip asset |
| 5 | **Event Guard** | Per Asset | `Days_to_Earnings >= 7` | `event_guard = true` | Skip asset |
| 6 | **Macro Event Guard** | Per Asset | `Days_to_FOMC/NFP >= 2` | `macro_event_guard = true` | Skip asset | ← **NEW v3** |
| 7 | **Pullback Zone** | Per Asset | `(Close - EMA_8) / EMA_8 <= 0.05` | Always | Skip asset |
| 8 | **Drawdown Gate** | Portfolio | See Section 9 | Always | Reduce size or halt | ← **NEW v3** |

### C. The Soft Gate (ML Scoring)
Only evaluated if all applicable Hard Guards pass.
- **Rule:** `XGBoost_Calibrated_Probability > 0.75` (75%).
- **Calibration:** Platt Scaling. Validated per profile class.

### D. The Portfolio Guard (Risk Management)
1. **Concentration Limit:** Max 1 position per group. Highest probability wins ties.
2. **Position Cap:** `min(ATR_Size, Portfolio × 0.15 / Entry_Price)`.
3. **News Veto (LLM):** Deferred to Phase 6. Not part of the active guard chain until spec is written and validated.

### E. The "Trap Order" Execution
Carried forward from v2.0:
- **Entry:** BUY STOP LIMIT at `High + (0.02 × ATR_14)`, limit at `Stop + (0.05 × ATR_14)`.
- **Gap-Through:** Order doesn't fill. By design.
- **Position Sizing:** `min((Portfolio × 0.02) / (ATR_14 × 2), Portfolio × 0.15 / Entry_Price)`.
- **Take Profit:** ADX-scaled: `clamp(2 + ADX/30, 2.5, 4.5) × ATR_14`. Sell 50%.
- **Trailing:** Chandelier Stop at `Highest_High - (2 × ATR_14)`.
- **Stop Loss:** Market order at `Entry - (2 × ATR_14)`.
- **Time Stop:** Close after 10 trading days.
- **TTL:** EQUITY (IBKR) = 1 US market session (09:30–16:00 ET). COMMODITY/IG spread bet = expires at next 23:00 UTC data ingest (effectively ~24h since IG gold trades ~23h/day). FOREX = 24 clock hours.

---

## 9. Dynamic Risk Management (NEW in v3.0)

v2.0 had a static Exposure Cap (4 positions × 2% = 8% max heat). v3.0 adds **dynamic throttling** based on actual portfolio performance.

### 9.1 Risk Parameters (Scale with Capital)

| Capital Range | Risk/Trade | Max Positions | Portfolio Heat | Cash Reserve |
|---------------|-----------|--------------|---------------|-------------|
| < €5,000 | 1.0% (€30-50) | 3 | 6% | 40% minimum |
| €5,000–€15,000 | 1.5% (€75-225) | 4 | 8% | 30% minimum |
| ≥ €15,000 | 2.0% (€300+) | 5 | 10% | 25% minimum |

### 9.2 Drawdown Throttling

| Drawdown Level | Action | Reversible? |
|---------------|--------|-------------|
| 0–8% | Normal operations | — |
| 8–12% | **Cut position sizes by 50%.** Risk/trade halved. Alert via Telegram. | Yes, when DD recovers to <6% |
| 12–15% | **Max 1 new position.** Close weakest existing position. Daily alerts. | Yes, when DD recovers to <8% |
| >15% | **HALT ALL TRADING.** No new entries. Review entire system. | Manual resume only after review |

### 9.3 Correlation Controls (NEW in v3.0)
- Rolling 60-day correlation matrix of **daily price returns** across all open + candidate asset tickers (not position P&L — positions are too short-lived for meaningful correlation).
- **Correlation limit: 0.70.** No new position if its underlying asset's returns are correlated >0.70 with any existing position's underlying asset over the trailing 60 days.
- Cross-asset correlation tracked: if Gold and Stocks become unusually correlated (>0.60), flag regime anomaly.

### 9.4 Portfolio State Tracking (DynamoDB)
```json
{
  "account_id": "primary",
  "total_cash": 3000.00,
  "total_equity": 3000.00,
  "peak_equity": 3000.00,
  "drawdown_pct": 0.0,
  "risk_status": "NORMAL",
  "portfolio_heat_pct": 0.0,
  "last_updated": "2026-02-12T23:15:00Z"
}
```

---

## 10. Regime Classifier (NEW in v3.0)

**Purpose:** Classify market regime to adjust Hard Guard parameters and position sizing. Does NOT generate signals.

### 10.1 Regime Types

| Regime | Characteristics | System Adjustment |
|--------|----------------|-------------------|
| BULL_TREND | VIX < 20, positive 6m momentum, normal yield curve | Full position sizes, longs only |
| BEAR_TREND | VIX > 25, negative 6m momentum, inverted yield curve | Half sizes, tighten stops |
| HIGH_VOLATILITY | VIX > 30, ATR spike | Quarter sizes or halt |
| LOW_VOLATILITY | VIX < 15, compressed ranges | Normal sizes |
| TRANSITION | Mixed signals | Half sizes, tighten stops |

### 10.2 Model: LightGBM Binary Classifier
- **Features (15):** Momentum (4 periods), RSI, MACD histogram, Bollinger %B, vol ratio, volume ratio, VIX level, VIX change, yield curve, fed funds rate, DXY momentum.
- **Target:** Next 20-day return direction.
- **Training:** Expanding window, retrain monthly.
- **Expected accuracy:** 52–56% (sufficient with risk management).
- **Runs on Lambda** (3GB RAM). LightGBM trains in seconds on daily data.

### 10.3 Phase-In
- **Phase 4 (Months 4–5):** Train and validate against historical data.
- **Deploy only if backtest shows measurable improvement** over no regime filter.
- The existing v2.0 Macro Gate (SPY > 200 SMA) remains as fallback even if regime classifier is active.

---

## 11. Backtesting & Validation (Enhanced in v3.0)

### 11.1 Walk-Forward Optimization (NEW)
```
Training window: 3 years (expanding)
Test window: 6 months
Roll forward: 6 months
Minimum periods: 10+ (5+ years of data)
```

### 11.2 Execution-Realistic Simulation (From v2.0)
- Full Trap Order logic: entry only if next day's High breaks signal candle high.
- Gap-throughs = missed signal.
- Stop loss executes at market open on gap-down (slippage simulation).
- Dual-constraint sizing.
- **IG Overnight Funding (spread bet positions):** Deduct ~0.008% per night for gold/commodity positions held on IG. Over a 10-day hold this is ~0.08% drag. Source from IG's published funding rates at backtest time. Without this, gold backtest P&L is systematically optimistic.

### 11.3 Statistical Validation (NEW)

| Test | Method | Pass Criteria |
|------|--------|--------------|
| Walk-Forward Efficiency | IS vs OOS performance ratio | > 50% |
| Monte Carlo Bootstrap | 10,000 resamples of trade returns | 5th percentile still positive |
| Shuffled-Price Test | Permute daily returns, re-run | Strategy fails on shuffled data (p < 0.01) |
| t-statistic | `mean_return × √N / std_return` | > 2.0 |

### 11.4 Performance Thresholds

| Metric | Minimum | Overfitting Red Flag |
|--------|---------|---------------------|
| Sharpe Ratio | > 0.5 | > 3.0 |
| Profit Factor | > 1.2 | > 2.5 |
| Max Drawdown | < 20% | < 5% |
| Win Rate | > 35% | > 75% |
| Total Trades | > 100 | — |

### 11.5 Paper Trading Validation
- **Duration:** Minimum 3 months, minimum 20 trades.
- **Track:** Signal accuracy vs backtest, slippage, miss rate, emotional overrides.
- **Pass:** Live results within 1σ of backtest. No systematic slippage > 0.3%.

---

## 12. Telegram Bot (Enhanced in v3.0)

### 12.1 Signal Card Format
```
🟢 WEALTH-OPS SIGNAL — LONG XAU/USD

📊 Confidence: XGBoost 82% | Momentum 1.9σ
🎯 Trap Order: Stop at $2,352 | Limit at $2,354
🛑 Stop Loss: $2,310 (-1.8%)
✅ TP: $2,410 (+2.5%) — Close 50%
📐 Trail: Chandelier at HH - (2 × ATR)

💰 Size: 0.02 lots (€30 risk = 1.0%)
⚖️ R:R: 1:2.5
🏷️ Broker: IG (spread bet — TAX FREE)

📈 Guards Passed:
• DXY < 200 SMA (weak dollar) ✅
• ADX: 28 (trending) ✅
• No FOMC within 2 days ✅
• Portfolio heat: 2% / 6% max ✅

📈 Reasoning:
• 6M momentum: +12.3% (z: 1.9)
• Price above 200 DMA (day 43)
• RSI: 58 (not overbought)
• EMA fan aligned (8 > 20 > 50)

⏰ Trap Order valid: 1 session
/executed  /skip  /details
```

### 12.2 Daily Briefing (Enhanced)
```
📊 Wealth-Ops Daily — Feb 15, 2026

💰 Portfolio: €3,180.00 (+6.0%)
   Cash: €2,280 (71.7%)
   Positions: €900 (28.3%)

📈 Open Positions:
   XAU/USD LONG (IG)  +€60 (+6.7%) 🟢
   NVDA LONG (IBKR)   -€12 (-1.4%) 🔴

🌡️ Risk Health:
   Portfolio Heat: 2.0% / 6% ✅
   Drawdown: 0.0% ✅
   Cash Reserve: 71.7% / 40% ✅
   Correlation: LOW ✅

🔮 Regime: BULL_TREND
   SPY > 200 SMA ✅ | VIX: 16 ✅ | DXY < 200 SMA ✅

📋 Signals: None today. Cash is a position.
/status  /portfolio  /history
```

### 12.3 Commands

| Command | Action |
|---------|--------|
| `/status` | Portfolio summary |
| `/portfolio` | Detailed position breakdown with P&L |
| `/history` | Last 10 trades with outcomes |
| `/executed <id>` | Confirm trade execution |
| `/executed <id> <price>` | Confirm with actual entry price |
| `/skip <id>` | Skip a signal |
| `/close <id>` | Mark position as manually closed |
| `/close <id> <price>` | Close with exit price for P&L |
| `/pause` | Pause signal generation |
| `/resume` | Resume signal generation |
| `/risk` | Current risk parameters and drawdown |
| `/performance` | Monthly/quarterly metrics |
| `/help` | List all commands |

### 12.4 Alert Types (EOD-Derived)
- **TP Hit:** Close 50% notification (detected from EOD data next day).
- **Regime Change:** Market shifted regimes.
- **Drawdown Alert:** Threshold crossed — size reduction active.
- **Data Staleness:** Market data > 24h old.

> **Note:** Stop-loss and trailing stop execution is handled by the broker in real-time. Our system does not monitor intraday prices.

---

## 13. Success Criteria & Kill Conditions

### Success (over 6 months of paper trading)

| Metric | Target |
|--------|--------|
| Positive expectancy | avg_win × win_rate > avg_loss × loss_rate |
| Sharpe ratio | > 0.5 |
| Maximum drawdown | < 15% |
| Win rate | 40–55% |
| Profit factor | > 1.2 |

### Kill Conditions

| Condition | Action |
|-----------|--------|
| Drawdown > 15% (paper) | Halt. Review every parameter. |
| 3 consecutive negative months | Halt. Backtest on newer data. |
| Live diverges >2σ from paper | Halt. Investigate execution gap. |
| Sharpe < 0.3 over 6 months | Strategy may lack edge. Reassess. |
| Override >3 signals per month | System trust broken. Fix or stop. |

---

## 14. Risk Matrix by Asset Class

Carried forward from v2.0 with **IG spread betting update** for commodities:

| Risk | EQUITY (IBKR) | COMMODITY (IG Spread Bet) | FOREX (IG, future) |
|------|---------------|--------------------------|-------------------|
| **Tax** | 33% CGT | **0% (TAX FREE)** | 0% (tax free) |
| **Overnight Gap** | HIGH. Mitigated: Event Guard, Cap, News Veto. | MODERATE. No earnings. Position Cap. | LOW. 24h market. |
| **Correlation** | HIGH (SPY correlated). Macro Gate. | LOW (haven) / MODERATE (cyclical). | LOW. Rate-driven. |
| **Data Quality** | HIGH. Tiingo 3-exchange validation. | HIGH. Tiingo Forex (tier-1 banks). | MODERATE. |
| **Execution** | Trap Order via IBKR API (future). | Trap Order via IG API (future). | IG API. |

---

## 15. What This System Does NOT Do

1. **Does not auto-execute.** Every trade requires human confirmation via Telegram.
2. **Does not scalp or day-trade.** Minimum hold: 1 day. Daily candles only.
3. **Does not use LLMs for trade decisions.** ML is XGBoost scoring + regime classification. LLM is News Veto only.
4. **Does not chase losses.** Drawdown triggers reduce size, never increase.
5. **Does not trade during major events** without blackout rules.
6. **Does not promise returns.** Probabilistic edge, not a guarantee.
7. **Does not use leverage** beyond spread betting's inherent margin.

---

*Wealth-Ops v3.0 Architecture — February 2026*
*No code is written that isn't traced to this spec. No shortcut taken that isn't documented.*