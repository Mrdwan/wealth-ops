# 🧠 Why Wealth-Ops v3 is Different

## The Problem with Trading Bots

Most retail trading bots fail. Here's why — and what we do about each one.

### 1. They Fight the Wrong War
Hedge funds have $100M+, co-located servers, Bloomberg terminals, and dark pool access. You have €3K and a Lambda function. **You lose before you start** if you copy their playbook.

**Our Fix:** We don't compete on speed or information. We compete on **patience** (daily candles only, 3–10 day holds), **tax structure** (IG spread betting = 0% tax on gold), and **risk discipline** (machine-enforced guards that never flinch). These are edges institutions can't easily replicate because they don't apply at their scale.

### 2. The "Chop" Killer
Most bots use trend-following indicators (MACD, EMA crossovers). Markets only trend ~30% of the time. The other 70% is sideways "chop" that generates false signals. Death by a thousand cuts.

**Our Fix:** The **ADX > 20 Trend Gate**. If the market isn't trending, we don't trade. We sit in cash and wait. The bot will frequently recommend doing nothing — that's a feature, not a bug.

### 3. Volume Blindness
A 3% price jump on low volume is a head fake. On high volume, it's institutional commitment. Most bots ignore the difference.

**Our Fix:** OBV + Volume Ratio for equities. We only trust moves confirmed by volume. For XAU/USD (no centralized volume), we skip volume features entirely rather than fake them — the model trains on 12 features instead of 14.

### 4. The "Sector Truck" (Correlation Collapse)
Five "great" setups in five semiconductor stocks is actually one giant bet on semiconductors. When the sector drops, everything crashes together.

**Our Fix:** Concentration Limit (max 1 per sector/group) + Correlation Matrix (>0.70 blocks entry). We pick the best signal and ignore the rest. Cross-asset holdings (equities + gold) provide natural hedging.

### 5. The Backtest Trap
Most bots backtest beautifully and fail live. Why? Overfitting, survivorship bias, unrealistic execution assumptions.

**Our Fix:**
- **Walk-forward optimization** (not a single backtest window).
- **Monte Carlo validation** (10,000 bootstraps — 5th percentile must be positive).
- **Shuffled-price test** (strategy must fail on random data or it's curve-fitted).
- **Execution-realistic simulation** (Trap Orders, gap-throughs, slippage at market open).
- **Paper trading gate** (3 months minimum before real money).

---

## The Wealth-Ops v3 Philosophy

### "Hard Guards, Soft Skills"
| Layer | Who Controls It | Examples |
|-------|-----------------|----------|
| **Hard Guards** | Human (You) | Stop Loss, No trading in Bear Markets, Sector Limits, Drawdown Halt |
| **Soft Skills** | AI (XGBoost + Momentum) | Entry timing, Asset selection, Probability scoring |

The AI is free to learn and adapt — **within the safe zone defined by the Hard Guards.** It cannot override the Stop Loss. It cannot trade during a crash. It cannot bypass drawdown throttling. The human sets the cage; the AI hunts inside it.

### "Cash is a Position"
The default state is **100% Cash**. Capital deploys ONLY when ALL guards are green.
- No setup? Stay cash.
- Choppy market (ADX < 20)? Stay cash.
- Bear market (SPY < 200 SMA)? Stay cash.
- Portfolio heat near maximum? Stay cash.
- Drawdown above 8%? Reduce size. Above 15%? Full halt.

The system will frequently do nothing. This is correct behavior.

### "Daily Candles Only"
1-Day timeframes exclusively.
- **Why not intraday?** That's HFT territory with co-located servers. We can't compete.
- **Why daily?** Filters noise, captures institutional "elephant" flows. We trade with the whales, not against them.

### "Two Signals, One Decision" (NEW in v3)
We run two independent signal systems:
1. **Momentum Composite** — Academically proven (30+ years of published research). The safety net.
2. **XGBoost Classifier** — Machine-learned patterns per asset. The alpha seeker.

When both agree → high confidence. When they conflict → no trade. The dual-signal approach catches failures in either system.

### "Tax is the Biggest Edge" (NEW in v3)
For an Irish retail trader, tax optimization is worth more than signal improvement:
- IG spread betting on gold = **0% tax** (spread betting = gambling, exempt).
- IBKR stocks = 33% CGT (unavoidable, but €1,270 annual exemption helps).
- Avoid EU-domiciled ETFs = 41% exit tax + deemed disposal. Never worth it.

A 15% return on €15K gold position: €2,250 on IBKR after tax = €1,507. On IG = **€2,250**. That's €743 saved — more alpha than most strategy improvements.

### "Dynamic Risk, Not Static" (NEW in v3)
v2 had a static Exposure Cap. v3 adds drawdown-based throttling:
- Losing? Automatically reduce sizes. Never increase.
- Drawdown >15%? Full halt. No new trades until human review.
- Winning? Sizes scale with equity (not with recency bias).

Risk management is not an afterthought. It is the **first gate every signal must pass through**, not the last.

---

## What Changed from v2

| Principle | v2 | v3 |
|-----------|----|----|
| Default state | 100% Cash | 100% Cash (**unchanged — this was right**) |
| Signal source | XGBoost only | **Momentum + XGBoost dual signal** |
| Risk model | Static caps | **Dynamic drawdown throttling** |
| Tax strategy | Noted as concern | **Solved: IG spread bet (0%) + IBKR (33%)** |
| Data integrity | Tiingo + Yahoo | **Tiingo (stocks + forex) + FRED (macro)** |
| Backtesting | 1,000-day replay | **Walk-forward + Monte Carlo + shuffled-price** |
| Telegram | One-way pulse | **Full command interface** |
| Gold instrument | GLD ETF (41% tax!) | **XAU/USD direct forex (0% tax)** |

---

*Wealth-Ops v3.0 — February 2026*
*No code written that isn't traced to spec. No shortcut taken that isn't documented.*
