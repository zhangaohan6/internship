# internship — 实习成果

Each project lives in its own folder.

## UNSW Agent 最新升级与真实评测

[项目代码与架构说明](hip-fracture-agent/) · [真实模型评测报告](hip-fracture-agent/reports/2026-11-15-deepseek/) · [全部 300 次脱敏评分记录](hip-fracture-agent/reports/2026-11-15-deepseek/trials.json)

基于 UNSW Datathon 合成数据的 Python 研究型 Agent，现支持 5 个工具、多步证据引用、
多轮筛选、异常恢复与原文检索。2026-11-15 使用 DeepSeek 完成 **150 条自建预留任务 × 2 轮**：
**281/300 次通过（93.7%）**，**135/150 条两轮均通过（90%）**。本轮为实习后独立升级，
采用严格任务契约评分，保留全部失败记录；不代表临床有效性或“零幻觉”。

## Projects

- **[aggreguard/](aggreguard/)** — **AggreGuard**: a trace-level, *aggregation-aware*
  safety-guardrail middleware for LLM agents + a reproducible attack/defense evaluation
  harness. Catches multi-step privacy inference attacks that per-message I/O filters
  (Lakera, LLM Guard) structurally miss. See
  [aggreguard/README.md](aggreguard/README.md) and
  [aggreguard/RESUME.md](aggreguard/RESUME.md).

- **[hip-fracture-agent/](hip-fracture-agent/)** — a Python **research Agent** over synthetic
  UNSW Datathon data: structured statistics, two local prediction tools, source-PDF retrieval,
  checked evidence comparisons, bounded multi-step execution and Streamlit. Includes 61
  offline regression tests and a [real-model evaluation report](hip-fracture-agent/reports/2026-11-15-deepseek/).
  *Code and redacted evaluation metadata only; the restricted dataset and model artifacts are not redistributed.*

- **[ecom-product-selector/](ecom-product-selector/)** — a data-driven **cross-border
  e-commerce** sourcing tool: FBA landed-profit waterfall (margin / ROI / breakeven-ACoS), a
  0–100 product-selection **Opportunity Score**, and a **PPC keyword** analyzer (ACoS / ROAS /
  max-profitable CPC / recommended bid). Zero-dependency core, two CLIs, a Streamlit dashboard,
  and 8 unit tests. Synthetic demo data — clone & run.

- **[ecom-restock-planner/](ecom-restock-planner/)** — a **demand-forecasting + inventory**
  tool for FBA restocking: four interpretable forecasters (moving-avg / exponential smoothing /
  Holt trend / weekly seasonal-naive) with a **backtest that auto-selects the best per SKU**,
  then safety stock, reorder point, days-of-cover, **stockout risk**, and an MOQ-rounded reorder
  quantity. Zero-dependency core, CLI, Streamlit dashboard, 8 unit tests. Synthetic data.

- **[ecom-ads-optimizer/](ecom-ads-optimizer/)** — a multi-platform **ad / ROAS optimizer**
  (Google / Meta / TikTok): per-campaign ROAS / ACoS / CPA / CTR / CVR, **wasted-spend**
  detection below breakeven ROAS, and a **budget-reallocation** projection. CLI + Streamlit +
  6 tests. Validated on a real-structured 1,800-row, $11M-spend ad dataset.
