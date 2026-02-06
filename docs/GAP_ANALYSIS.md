# 📉 Project Readiness Review: Gap Analysis

**Verdict: 🔴 NOT READY FOR CODING**

The current plan contains **Critical Architectural Flaws** that will cause failure in Production if not addressed. You must define these specs before writing code.

| Severity | Area | Issue | Impact |
|:---:|:---:|---|---|
| 🚨 **CRITICAL** | **Data Source** | Reliance on `Yahoo Finance` (Unofficial/Scraping) | **High Fragility.** Data feed will break randomly. No retry/fallback defined. |
| 🚨 **CRITICAL** | **Compute** | `FinBERT` (PyTorch) on AWS Lambda | **Lambda Failure.** 10GB Docker limit tight; Cold starts > 15s; High memory cost. |
| 🟡 **MEDIUM** | **Ingestion** | "Bootstrap" (50 years) via Lambda | **Timeout.** Lambda 15min limit is too short for massive backfill (500+ assets). |
| 🟡 **MEDIUM** | **Resiliency** | No "Gap-Fill" Logic | **Data Loss.** If ingestion fails for 3 days, there is no mechansim to "catch up" automatically. |

---

## 1. The Yahoo Finance Trap
**Current Plan:** Use Yahoo Finance for "Daily Drip".
**The Flaw:** `yfinance` relies on scraping unofficial endpoints. Yahoo frequently changes their DOM/API signature to block scrapers.
**The Fix:**
1.  **Primary:** Tiingo End-of-Day API (Official, Free Tier is generous).
2.  **Fallback:** Yahoo Finance (Only if Tiingo fails).
3.  **Design Change:** Use a standardized `Monitor` interface that attempts Primary -> Fallback automatically.

## 2. ML on Lambda (FinBERT)
**Current Plan:** "Gate 5: Calls LLM... FinBERT (Local)".
**The Flaw:** Running a Transformer model (even a small one like FinBERT) inside a Lambda function is an architectural anti-pattern for this scale.
-   **Size:** PyTorch + Transformers + Model Dependencies > 2-3GB uncompressed.
-   **Performance:** CPU inference on Lambda is slow and expensive per ms.
-   **Concurrency:** Validating 50 tickers = 50 concurrent heavy Lambdas? Costly.
**The Fix:**
-   **Option A (Recommended):** Move FinBERT inference to the **Fargate Training Task**. Run sentiment analysis *during* the training/inference window when the container is already hot.
-   **Option B:** Use a cheap API (e.g., HuggingFace Inference API) for the "Soft Guard" to keep Lambda lightweight.

## 3. The "Bootstrap" Timeout
**Current Plan:** "Lambda... fetches data."
**The Flaw:** Initializing 500 tickers x 20 years of data is a heavy IO/Compute operation.
-   Tiingo Rate Limits: You will hit API throttling before fetching all data.
-   Lambda Timeout: 15 minutes max.
**The Fix:**
-   **Split Logic:**
    -   **Daily Drip:** Lambda is fine (fast).
    -   **Bootstrap:** Run as a **Fargate Task** or a **Step Function Map State** (Fan-out pattern) to handle long-running backfills.

## 4. Missing "Gap-Fill" Logic
**Current Plan:** "Daily Drip".
**The Flaw:** If the system crashes on Tuesday and is fixed on Thursday, Wednesday's data is missing forever in the current design.
**The Fix:**
-   **Smart Ingest:** The Ingest function must reading `DynamoDB:LastUpdated` timestamp.
-   **Logic:** `Range = (LastUpdated + 1 Day) to (Today)`. This automatically heals gaps.

## Recommendation
Do NOT start coding `src/modules`.
**Action:** Author the following Specs first:
1.  `specs/data-ingestion-strategy.md` (Addressing Rate Limits + Gaps).
2.  `specs/ml-compute-strategy.md` (Deciding where FinBERT lives).
