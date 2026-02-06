# 🏛️ Wealth-Ops v2.0 Architecture

## 1. Core Philosophy
A cloud-native, automated hedge fund for a **Single User (Irish Tax Resident)**.
- **Strategy:** "The Swing Sniper" (Daily Candles, 3-10 day hold).
- **Tax Logic:** Minimize ETFs (41% Tax). Prioritize Individual Stocks (33% CGT).
- **Quality:** 100% Test Coverage required for all financial logic.
- **Hybrid AI Model:** "Hard Guards, Soft Skills." We enforce Risk Rules (Hard), AI learns Entry Patterns (Soft).

## 2. The Cloud Stack (AWS)
- **Ingest & Scout:** AWS Lambda (Python). Fetches data/news daily.
- **The Specialist (Training):** AWS Fargate (ECS). Spins up, trains XGBoost models for each asset, saves to S3, shuts down.
- **The Judge & Execution:** AWS Lambda. Reads S3 models, predicts, calls LLM, executes trade.
- **State Store:** AWS DynamoDB (Ledger, Holdings, Config).
- **Data Lake:** AWS S3 (Parquet History, Model Artifacts).
- **Orchestration:** AWS Step Functions (Visual Workflow).

## 3. The "One-Asset, One-Model" Policy
We train a unique XGBoost Classifier for each active asset in `DynamoDB:Config`.
- **Input:** 1-Day Candles (OHLCV) + Technicals (RSI, EMA, MACD, ADX, **OBV/Volume-Ratio**).
- **Target:** "Swing Probability" (Price > Current + 3% in 5 days).

## 4. The "Swing Sniper" Trading Strategy
This system is optimized for an **Irish Tax Resident** managing personal capital. The default state is **100% CASH** unless a high-probability setup is confirmed.

### A. The Setup (Daily Intervals)
- **Candles:** We strictly use **1-Day (Daily)** OHLCV data.
- **Why:** To filter out HFT (High-Frequency Trading) noise and capture institutional flows.

### B. The "Gatekeeper" Trio (Entry Logic)
We require **Three Green Lights** to enter a trade. If any light is RED, we stay in CASH.

1.  **Macro Gate (The Regime):**
    -   **Rule:** S&P 500 Price > 200-day SMA.
    -   **Why:** Never buy stocks in a Bear Market.
2.  **Trend Gate (The Volatility):**
    -   **Rule:** ADX (14-day) > 20.
    -   **Why:** Never trade in a choppy, sideways market ("The Chop").
3.  **Asset Gate (The Alpha Specialist):**
    -   **Rule:** XGBoost Probability > 75%.
    -   **Why:** Only swing at the fat pitches.

### C. The Portfolio Guard (Risk Management)
Before execution, we apply **Correlation Controls**:
1.  **Sector Limit:** Max **1 Position** per Sector (e.g., Tech, Finance, Energy).
    -   *If multiple signals:* Pick the one with the highest Probability Score.
2.  **News Veto:** The LLM scans for negative sentiment/uncertainty.

### D. The Execution (Trade Management)
-   **Minimum Trade Size:** $2,000 (To keep fees < 0.2%).
-   **Holding Period:** 3 to 10 Days (Swing Trade).
-   **Exit Strategy:**
    -   **Take Profit:** Sell 50% at +5%, Sell remainder at Trend Reversal.
    -   **Stop Loss:** Hard exit at -5% from Entry Price.
    -   **Time Stop:** Close position if no movement after 10 days.