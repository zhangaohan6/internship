# internship — 实习成果

Each project lives in its own folder.

## Projects

- **[aggreguard/](aggreguard/)** — **AggreGuard**: a trace-level, *aggregation-aware*
  safety-guardrail middleware for LLM agents + a reproducible attack/defense evaluation
  harness. Catches multi-step privacy inference attacks that per-message I/O filters
  (Lakera, LLM Guard) structurally miss. See
  [aggreguard/README.md](aggreguard/README.md) and
  [aggreguard/RESUME.md](aggreguard/RESUME.md).

- **[hip-fracture-agent/](hip-fracture-agent/)** — a clinical decision-support **AI agent**
  over the ANZHFR hip-fracture registry: XGBoost outcome models (walking recovery AUC 0.84,
  rehab access 0.78) + SHAP, RAG over ACSQHC care standards, a native tool-use agent, a
  Streamlit UI, and a Type A/B/C evaluation harness (100% tool-selection, 0.97 composite).
  *Code only — the dataset is under a Data Use Agreement and is not redistributed.*

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
