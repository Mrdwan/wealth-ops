# 🧠 Spec: ML Compute Strategy

> **Status:** Draft
> **Owner:** Architect
> **Implements:** Gap Analysis Fix #2

## 1. The Core Problem
The original plan attempted to run **FinBERT** (PyTorch Transformer) inside a **AWS Lambda** for the "News Veto" gate.
- **Issue:** Lambda has a 10GB container limit, slow CPU for inference, and high cold-start latency (>15s) for heavy ML libraries.
- **Risk:** Timeouts and memory failures during trade execution.

## 2. The Solution: "Cloud Native" Separation
We will split the ML workload into **Training (Heavy)** and **Inference (Light/API)**.

### 2.1 Architecture Changes

| Component | Task | Original Plan | **New Plan** |
|---|---|---|---|
| **The Specialist** | Train XGBoost Models | Fargate | **Fargate** (Unchanged). |
| **The Judge** | Trade Execution Logic | Lambda | **Lambda** (Unchanged). |
| **Sentiment** | "News Veto" | FinBERT on Lambda | **LLM API (DeepSeek/Gemini)**. |

## 3. The "News Veto" Implementation
Instead of loading a 500MB PyTorch model into memory to classify news headlines, we will use a **Cost-Effective LLM API**.

### 3.1 Why API?
- **Speed:** < 2s latency.
- **Cost:** DeepSeek-V3 / Gemini Flash are cheaper than running high-memory Lambdas.
- **Quality:** LLMs understand context better than FinBERT (which is just sentiment positive/negative).

### 3.2 The Flow (Gate 5)
1. **Trigger:** `The Judge` Lambda identifies a potential BUY signal.
2. **Fetch News:** Call Tiingo News API / NewsAPI for the ticker (last 24h).
3. **Analyze:**
   - Send headlines to **DeepSeek-V3** (via OpenRouter or Direct) or **Gemini 1.5 Flash**.
   - **Prompt:** "Analyze these headlines for `{ticker}`. Return strictly JSON: `{'sentiment': 'BULLISH'|'BEARISH'|'NEUTRAL', 'veto': true|false}`. Veto if there is catastrophic news (bankruptcy, lawsuits, earnings miss)."
4. **Decision:** If `veto == true`, the trade is aborted.

## 4. What about FinBERT?
We will **Deprecate** FinBERT for the live execution path.
*Optional:* It can be used in the **Offline Training Pipeline** (Fargate) to generate historical sentiment features for the XGBoost model, as the Fargate container is already heavy and long-running.

## 5. Revised Cost Estimate
- **Lambda:** 128MB (Standard) instead of 10GB (ML). **~10x Cheaper.**
- **API Costs:**
  - 10 Trades/day * 5 News items * Input Tokens.
  - ~ $0.05 / month.
  - Much cheaper than keeping Provisioned Concurrency for a heavy ML Lambda.

## 6. Implementation Plan
1. Update `src/modules/llm/client.py` to support `analyze_sentiment(headlines)`.
2. Remove `torch` and `transformers` from the main `requirements.txt` (Keep `xgboost` for the Fargate image).
3. Ensure AWS Secrets Manager stores the `LLM_API_KEY`.
