# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added — Phase 1 v3 Data Pipelines (Steps 1.6–1.10)
- **Asset Profile Schema v3** (`src/shared/profiles.py`): `AssetProfile` frozen dataclass with 4 templates (EQUITY, COMMODITY_HAVEN, COMMODITY_CYCLICAL, INDEX), DynamoDB serialization, and S3 prefix routing.
- **Seed script** (`scripts/seed_profiles.py`): Idempotent DynamoDB seeder for 9 tickers (5 equities, 2 indices, 2 commodities).
- **Tiingo Forex Provider** (`src/modules/data/providers/tiingo_forex.py`): `TiingoForexProvider` for XAU/USD and XAG/USD via Tiingo FX endpoint (`resampleFreq=1day`, volume=0, adjusted_close=close).
- **FRED Macro Pipeline**: `MacroDataProvider` protocol, `FredProvider`, and `MacroDataManager` with per-series staleness thresholds (daily series=24h, monthly=35d). Series: VIXCLS, T10Y2Y, FEDFUNDS, CPIAUCSL.
- **DXY via UUP**: UUP ETF added to seed script with INDEX profile — uses existing TiingoProvider, zero new code.
- **Two-Way Telegram Commands**: Lambda Function URL webhook (`src/lambdas/telegram_webhook.py`), command handlers (`/status`, `/portfolio`, `/risk`, `/help`), `send_reply()` method, chat ID security validation.
- **Relative Strength Feature** (`src/modules/features/indicators/relative_strength.py`): Z-scored asset/benchmark price ratio (20-day rolling window). Feature counts: EQUITY=14, COMMODITY_HAVEN=12.

### Changed
- `Config` dataclass: added `fred_api_key` field.
- `DataManager.ingest()`: added `s3_prefix` parameter for profile-based S3 path routing.
- `data_ingestion.py`: `get_enabled_tickers()` now returns `list[tuple[str, AssetProfile]]` for profile-aware routing.
- `FeatureEngine.compute()`: added optional `benchmark_df` parameter for relative strength calculation.

### Tests
- **209 tests passing** (added 73 new tests across 8 test files).
- **97% overall coverage** — uncovered lines limited to:
  - `macro_manager.py`: S3 save error paths (operational edge cases)
  - `commands.py` / `telegram.py`: DynamoDB error handling branches and `send_reply()` method (require integration tests)

## [3.0.0] - 2026-02-12

### Added — Broker & Tax Strategy
- **Dual-broker architecture:** IG Ireland (spread betting, tax-free) for gold/commodities + IBKR Ireland for US stocks (33% CGT).
- Broker abstraction layer (`BrokerInterface` ABC) with `IGBroker`, `IBKRBroker`, `PaperBroker` implementations.
- `broker`, `tax_rate`, and `data_source` fields added to DynamoDB:Config asset profiles.
- Tax impact calculations in P&L reporting.
- Gold instrument changed from GLD ETF (41% exit tax) to XAU/USD spread bet on IG (0% tax).

### Added — Data Sources
- **Tiingo Forex** integration for direct XAU/USD and XAG/USD pricing (from tier-1 banks, not ETF proxy). Enables IG spread betting (tax-free).
- **FRED** integration for macro data: VIX, Yield Curve (T10Y2Y), Fed Funds Rate, CPI.
- **DXY index** data pipeline (UUP proxy or DX-Y.NYB) for COMMODITY_HAVEN regime gate.
- Cross-reference validation: Tiingo XAU/USD forex vs Tiingo GLD ETF, >2% divergence = Telegram alert.

### Added — Signal Generation
- **Momentum Composite Score** as academic baseline signal (Jegadeesh & Titman 1993).
  - 6 components: Momentum (40%), Trend (20%), RSI (15%), Volume (10%), ATR Volatility (10%), S/R (5%).
  - Z-score normalized. Thresholds: STRONG_BUY >2.0σ, BUY >1.5σ.
- Dual-signal framework: Momentum Composite + XGBoost run in parallel.
  - Both scores logged daily for all assets.
  - Agreement matrix determines confidence level.
  - Phase-in: Momentum first (Phase 2A), XGBoost second (Phase 2B).

### Added — Risk Management
- **Dynamic drawdown throttling:** 8% DD → half sizes, 12% → 1 position max, 15% → HALT.
- **Capital-based scaling:** <€5K = 3 positions/1% risk, €5-15K = 4/1.5%, €15K+ = 5/2%.
- **Correlation controls:** 60-day rolling matrix, >0.70 correlation blocks new entries.
- **Cash reserve minimum:** 40% at <€5K, 30% at €5-15K, 25% at €15K+.
- `risk_status` field in DynamoDB portfolio state: NORMAL, CAUTION, HALT.

### Added — Hard Guards
- **Guard 6: Macro Event Guard** — Blocks entries within 2 days of FOMC, NFP, CPI releases. Applied to `macro_event_guard = true` assets (COMMODITY, FOREX).
- **Guard 8: Drawdown Gate** — Enforces dynamic throttling from Section 9 of architecture.
- Economic calendar integration (FRED + Finnhub) for macro event dates.

### Added — Backtesting
- **Walk-forward optimization:** 3-year expanding train, 6-month test, rolling. Min 10 periods.
- **Monte Carlo validation:** 10,000 bootstrap iterations, 5th percentile must be positive.
- **Shuffled-price test:** Strategy must fail on permuted returns (p < 0.01).
- **t-statistic requirement:** > 2.0 for signal significance.
- **Overfitting detection:** Red flags for Sharpe >3.0, PF >2.5, DD <5%, WR >75%.
- Paper trading gate: 3 months, 30 trades, live within 1σ of backtest.

### Added — Telegram
- Full two-way command interface: `/status`, `/portfolio`, `/history`, `/risk`, `/performance`.
- Trade execution commands: `/executed <id> [price]`, `/skip <id>`, `/close <id> [price]`.
- System commands: `/pause`, `/resume`, `/help`.
- Signal cards with dual-score display, Trap Order parameters, guard status, reasoning.
- Position alerts: stop proximity, trailing updates, TP hits, regime changes, drawdown alerts.
- Enhanced daily briefing with risk health dashboard.

### Added — ML Regime Classifier
- **LightGBM binary classifier** for market regime detection (Phase 4).
- 5 regimes: BULL_TREND, BEAR_TREND, HIGH_VOLATILITY, LOW_VOLATILITY, TRANSITION.
- 15 features from existing data pipeline.
- Adjusts position sizing and stop-loss parameters. Does NOT generate signals.
- Deploy only if backtest proves measurable improvement over no regime filter.

### Added — Success Criteria
- Explicit kill conditions: 15% DD halt, 3 negative months, 2σ divergence from paper.
- Paper trading validation criteria codified.
- Sharpe >0.5, Profit Factor >1.2, Win Rate 40-55% targets.

### Changed
- COMMODITY_HAVEN profile: `volume_features` changed from `true` to `false` (XAU/USD forex has no volume).
- COMMODITY_HAVEN profile: `data_source` set to `TIINGO` (Tiingo Forex covers XAU/USD directly).
- Removed hourly `position_monitor` — broker (IG/IBKR) handles stop/TP execution in real-time; system only needs EOD data.
- Execution schedules refined: added weekly review, monthly retrain.
- Phase numbering restructured: Phase 2 split into 2A (Momentum) and 2B (XGBoost).
- Backtesting enhanced from 1,000-day replay to walk-forward + Monte Carlo.
- Roadmap expanded from 5 phases to 7 phases.

### Fixed (Carried from v2.0)
- DevContainer symlink issue for Antigravity Server tool availability.
- Recursive `cdk-synth` bundling issue (`.dockerignore` + `.gitignore` exclusions).
- All `pre-commit` hook errors (mypy stubs, ruff formatting).

---

## [2.0.0] - 2026-02-08

### Fixed
- Fixed devcontainer issue with Antigravity Server symlink to ensure tool availability in the container.
- Resolved recursive `cdk-synth` bundling issue by ignoring `cdk.out` in `.dockerignore` and `.gitignore`.
- Fixed all `pre-commit` hook errors, including missing `mypy` stubs and `ruff` formatting issues.

### Added
- Configured DevContainer with `docker-outside-of-docker` and `node` features for full CDK and Docker support.
- Added **Rule 4: The "Living Documentation" Clause** to the `00-constitution.md`, enforcing documentation updates at the end of every session.

---

*Wealth-Ops v3.0 Changelog — February 2026*
