# 🏛️ Wealth-Ops v3.0

**A Cloud-Native Swing Trading Advisory System optimized for Irish Tax Residents.**

> **Status:** Phase 2B (XGBoost Alpha Specialist — Earnings Calendar ✅)
> **License:** Private / MIT
> **Current Focus:** Building the XGBoost ML pipeline with dual-signal architecture.

---

## 📖 The Mission
Wealth-Ops is a **Capital Preservation & Swing Trading Engine** designed for the solo Irish trader:

1.  **The Tax Edge:** Dual-broker strategy — IG spread betting (tax-free) for gold/commodities, IBKR (33% CGT) for US stocks.
2.  **The Discipline:** Hard Guards enforce risk rules before any signal reaches the trader. "Cash is a Position."
3.  **The Signal:** Momentum Composite (academic baseline) + XGBoost (ML) — dual-signal validation.

---

## 🧠 The Architecture

The system operates as a **notification-first advisory pipeline** on AWS:

1.  **📊 Data Engine:** Tiingo (stocks + forex) + FRED (macro) → S3 Parquet data lake.
2.  **📈 Signal Engine:** Momentum Composite (6-component z-score) + XGBoost per-asset models.
3.  **🛡️ Hard Guards:** 8 non-negotiable gates (Macro, VIX, Exposure, Trend, Earnings, FOMC, Pullback, Drawdown).
4.  **💬 Telegram Bot:** Two-way command interface with signal cards, daily briefings, and trade execution.

---

## 🛠️ Tech Stack

**Infrastructure:**
* **Cloud:** AWS (Lambda, Fargate, EventBridge, Step Functions).
* **IaC:** AWS CDK (Python).
* **Database:** DynamoDB (Config, Ledger, Portfolio, System tables).
* **Storage:** S3 (Parquet data lake + model artifacts).

**Application:**
* **Language:** Python 3.13+.
* **ML Engine:** XGBoost (per-asset) + LightGBM (regime classifier, Phase 4).
* **Quality:** `pytest` (100% branch coverage), `mypy` (strict typing), `ruff` (linting).

---

## 📂 Project Structure

```text
wealth-ops/
├── .devcontainer/          # 🐳 Dev Container (Docker-based dev environment)
├── .agent/                 # 🤖 AI Context Kernel (rules, workflows)
│   ├── rules/              # Constitution, Code Standards
│   └── workflows/          # Repeatable procedures
├── docs/                   # 📜 Architecture, Roadmap, Changelog
├── infra/                  # ☁️ CDK Infrastructure as Code
├── prompts/                # 🏗️ Architect & Builder prompts
├── scripts/                # 🔧 Seed scripts, utilities
├── src/                    # 🧠 Application Logic
│   ├── lambdas/            # Lambda handlers (data ingest, pulse, webhook)
│   ├── modules/
│   │   ├── data/           # Data engine (providers, managers)
│   │   ├── features/       # Technical indicator engine (11+ indicators)
│   │   ├── notifications/  # Telegram bot + command handlers
│   │   ├── regime/         # Regime filter (circuit breaker)
│   │   └── signals/        # Momentum composite, signal cards, guards
│   └── shared/             # Config, logger, asset profiles
├── tests/                  # 🛡️ 394 tests, 100% branch coverage
└── README.md
```

