# 📡 Spec: Data Ingestion-Strategy

> **Status:** Draft
> **Owner:** Architect
> **Implements:** Gap Analysis Fix #1 & #3

## 1. The Core Problem
The original plan relied on `Yahoo Finance` (Unstable/Scraping) and lacked "Gap-Fill" logic. If the ingestion Lambda failed for a day, that data was lost forever.

## 2. Multi-Source Strategy
We will implement a **Provider Pattern** with automatic failover.

| Priority | Provider | Type | Cost | Rate Limit | Usage |
|:---:|---|---|---|---|---|
| **1 (Primary)** | **Tiingo** | Official API | Free | 500 req/hour | Primary source for High Quality data. |
| **2 (Fallback)** | **Yahoo (yfinance)** | Scraper | Free | IP Bans | Backup Only. Used if Tiingo is down/throttled. |

### 2.1 The Interface
All providers must implement this Python protocol:
```python
class MarketDataProvider(Protocol):
    def get_daily_candles(self, ticker: str, start_date: date, end_date: date) -> pd.DataFrame:
        """Returns OHLCV DataFrame normalized to standard schema."""
        ...
```

## 3. The "Smart" Gap-Fill Logic
The Ingest Lambda will effectively be stateless but context-aware by checking the Ledger.

### 3.1 The Flow
1. **Read State:** Query `DynamoDB:Config` for `ticker`. Get `last_updated_date`.
2. **Determine Range:**
   - If `last_updated_date` is `NULL`: **BOOTSTRAP MODE** (Fetch Max History).
   - If `last_updated_date` == `Yesterday`: **DAILY DRIP** (Fetch Today).
   - If `last_updated_date` < `Yesterday`: **GAP FILL** (Fetch `last_updated + 1` to `Today`).
3. **Fetch & Write:**
   - Call Primary Provider.
   - If Error -> Call Fallback Provider.
   - Save Parquet to S3: `s3://wealth-ops-data/raw/{ticker}/{date_range}.parquet`
   - Update `DynamoDB:Config` with new `last_updated_date`.

## 4. Workload Separation (Lambda vs. Fargate)

### 4.1 Daily Drip (Lambda)
- **Trigger:** CloudWatch Event (Mon-Fri, 23:00 UTC).
- **Concurrency:** Fan-out. 1 Lambda fetches 1 Asset (or batch of 10).
- **Timeout:** 900s (Plenty for 1 day of data).

### 4.2 Bootstrap / Disaster Recovery (Fargate)
- **Scenario:** Onboarding 500 new tickers OR re-fetching 10 years of history.
- **Why:** Lambda will timeout on 500 requests x 2 seconds = 1000s.
- **Implementation:**
  - A standalone generic script `scripts/ingest_bulk.py`.
  - Run as a **Fargate Task** manually when needed.
  - Can handle rate-limiting (sleeps) gracefully without timeout fears.

## 5. Schema Normalization
Regardless of source (Tiingo/Yahoo), data must be mapped to:
- `date` (Index, YYYY-MM-DD)
- `open` (float)
- `high` (float)
- `low` (float)
- `close` (float)
- `volume` (float)
- `adjusted_close` (float, if available)

## 6. Implementation Plan
1. Create `src/modules/data/providers/tiingo.py`
2. Create `src/modules/data/providers/yahoo.py`
3. Implement `src/modules/data/manager.py` (The Orchestrator).
4. **Test:** Mock Tiingo failures to prove Yahoo fallback works.
