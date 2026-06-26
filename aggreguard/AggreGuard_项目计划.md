# AggreGuard:Agent 安全护栏与评测层 — 详细项目计划

> 工作代号 **AggreGuard**(可改名)。核心定位:一层能挂在任意 LLM agent 上的 **trace 级 + 聚合感知** 安全中间件,外加一套可复现的 **攻击/防御评测流水线**。把"我做 agent 安全研究"落成"我能交付可靠性基建"。

---

## 0. 一句话定位

市面护栏(Lakera / LLM Guard / NeMo / Llama Guard)基本都是 **I/O 文本过滤**——只看进出文本里有没有注入特征。AggreGuard 看的是 **agent 的执行轨迹**(调用了哪些工具、数据从哪流到哪),并且独家处理 **聚合/推理攻击**:一串"单看都人畜无害"的查询合起来越过敏感阈值时报警。后者正是 aggregation-based inference 研究的工程变现。

---

## 1. 背景与机会

### 1.1 现状工具盘点(避免重造轮子)

| 工具 | 类型 | 形态 | 局限 |
|------|------|------|------|
| Lakera Guard | 托管 API | 输入/输出文本扫描,sub-50ms | 闭源、按量收费、看不懂工具调用轨迹 |
| LLM Guard (Protect AI) | 开源 | 自托管 scanner 链 | 文本层、无轨迹/无聚合视角 |
| NeMo Guardrails (NVIDIA) | 开源 | Colang 写对话流策略 | 偏多轮对话流控、非 agent 工具链 |
| Llama Guard / ShieldGemma | 开源安全模型 | 单条文本分类 | 单点判断,无会话级累积 |
| LlamaFirewall (Meta) | 开源 | agent 护栏系统 | 通用,无聚合/再识别建模 |
| Prompt-Guard-86M / deberta-prompt-injection-v2 | 开源检测器 | 注入二分类 | 只做注入检测这一环 |

**共同缺口**:它们都是"单次、文本、I/O 边界"的判断。没有一个跟踪 **会话级累计信息披露**,也没有把 agent 的 **工具调用序列**当作一等公民来审计。

### 1.2 学术参照(站在巨人肩上)

- **AgentDojo**(arXiv 2406.13352,NeurIPS 2024):事实标准评测基准,97 真实任务 + 629 安全用例。本项目的主评测台。
- **Design patterns for securing LLM agents**(arXiv 2506.08837):信任边界 / 数据来源标记的设计原则。
- **Defeating prompt injections by design / CaMeL**(arXiv 2503.18813):从架构上隔离不可信数据。
- **Task Shield**(arXiv 2412.16682):用"任务对齐"判断每个动作是否偏离用户意图。
- **AgentArmor**(arXiv 2508.01249):对运行时轨迹做程序分析来防注入(与本项目 trace 思路同源,可对标)。
- **Gray Swan IPI Arena**:开源 eval kit `github.com/GraySwanAI/ipi_arena_os`,引入"隐蔽性(concealment)作为攻击成功条件"这一独特维度。

### 1.3 你的独家护城河

聚合监控(组件 4)直接来自数据库 **inference / aggregation 攻击**与经典 **query auditing / k-匿名 / 差分隐私预算** 文献。市面护栏几乎无人处理"千刀慢割";而你恰好在这条线上有研究底子,做出来既是工程亮点,也是 workshop/short paper 的 novelty。

---

## 2. 项目目标

- **工程目标**:可组合的中间件 + 干净 API + 可观测 + 失败处理 = 面试官认的"能写真正软件"。
- **研究目标**:对"trace 级聚合感知防御"给出可复现实验,产出一份 workshop/short paper 草稿。
- **简历目标**:把"agent 安全研究"转成"AI safety / reliability engineer"岗位的硬证据,每个量化指标都是一条 bullet。

---

## 3. 系统架构总览

```
                         ┌─────────────────────────────┐
   用户指令 ──────────────▶│        Target Agent          │
                         │  (LangGraph / Claude SDK …)  │
   工具返回/网页/RAG ──────▶│                              │
                         └──────────────┬──────────────┘
                                        │  每一步:动作 + 数据流
                                        ▼
            ┌───────────────────────────────────────────────┐
            │            AggreGuard 护栏中间件 (产物 B)        │
            │  1 来源标记 & 信任边界                           │
            │  2 注入检测 (复用现成检测器)                     │
            │  3 任务对齐监控                                  │
            │  4 ★聚合/推理监控 (独家)                         │
            │  5 高危动作 gating + HITL                        │
            │  6 决策日志 (可观测性)                           │
            └───────────────────────────────────────────────┘
                                        │
                                        ▼
            ┌───────────────────────────────────────────────┐
            │              评测层 (产物 A)                     │
            │  攻击套件 → 跑 → ASR / utility / concealment /   │
            │  延迟开销 / 误杀率 → 对照报告表                   │
            └───────────────────────────────────────────────┘
```

两条挂载方式任选其一先做:LangGraph 里加一个监控 node;或 Claude Agent SDK 的 hook;进阶可做成 MCP proxy 拦截工具调用。

---

## 4. 产物 B:护栏中间件(详细设计)

### 组件 1 — 数据来源标记 & 信任边界
给流经 agent 的每段数据打 provenance 标签:`USER`(可信)/ `TOOL`(半可信)/ `WEB/RAG`(不可信)。规则:不可信来源的内容**不得**直接触发高权限工具(发邮件、转账、外发数据)。落地为一个 taint-tracking 包装层。参考 design patterns 论文 + CaMeL。

### 组件 2 — 注入检测(直接复用,别从零训)
把 `ProtectAI/deberta-v3-base-prompt-injection-v2` 或 `Meta Prompt-Guard-86M` 作为 baseline 检测器,挂在不可信数据入口。可选接 Lakera API 做对照。**这一环不是你的创新点,目标是省力 + 提供 baseline 数字。**

### 组件 3 — 任务对齐监控(Task Shield 思路)
维护"原始用户意图"的结构化表示;每次工具调用前,用一个轻量判断(规则 + 小模型)检查该动作是否服务于原意图,偏离则 flag。例:用户让"总结邮件",agent 却要"把邮件转发到外部地址" → 拦。

### 组件 4 — ★聚合/推理监控(你的独家核心)

**目标**:抓住"每一步单看都合规,但累积起来构成敏感信息泄露 / 再识别"的攻击,同时**不误杀**正常多步任务。

**状态**:按 `(session × data-subject)` 维护一个披露账本
```
disclosed[entity] = { (attribute, value, sensitivity_weight, sink_type, timestamp), ... }
```
只记录**流向不可信 sink**(外发、写入 WEB 标记目标、返回给可能被注入控制的输出)的披露;agent 内部推理读取不计入,避免误杀。

**两类触发器**:
1. **累计敏感度预算**:每个属性有敏感权重 `w(a)`;同一 entity 的累计分 `S(entity)=Σ w(a)·decay(Δt)`。`S` 越过阈值 `τ` → 升级。带时间衰减,防止历史污染。
2. **准标识符再识别**:跟踪每个 entity 已披露的 quasi-identifier 集合;当其组合使匿名集规模跌破 `k`(k-匿名思想)→ 触发,因为"邮编+生日+性别"这种组合即可唯一定位。

**降误杀机制**(这是成败关键):
- 预算严格 scope 到 `(session, entity)`,正常"处理某一个人的多步任务"不会无限累积。
- 只对 **linkable**(同一实体)且 **流向不可信 sink** 的披露计分。
- 支持任务模式 allowlist(已批准的合法批量操作走白名单)。
- 优先 **HITL 二次确认**,而非硬 block,把误杀转成"问一句"。

**算法骨架(伪代码)**:
```python
def on_disclosure(entity, attr, value, sink_type, session_state):
    if sink_type != "untrusted":           # 只管外流
        return ALLOW
    rec = (attr, value, weight(attr), now())
    book = session_state.disclosed[entity]
    book.add(rec)

    S = sum(r.w * decay(now() - r.t) for r in book)         # 累计敏感度
    qids = {r.attr for r in book if is_quasi_identifier(r.attr)}
    anon = estimate_anonymity_set(entity, qids)              # 估计匿名集大小

    if S >= TAU or anon < K:
        return ESCALATE_HITL(reason=...)                    # 优先问,不直接杀
    return ALLOW
```

**可调参数**:`w(a)` 权重表、`τ`、`k`、衰减半衰期、`is_quasi_identifier` 字段集。这些就是论文里的 ablation 维度。

### 组件 5 — 高危动作 gating + HITL
对 `send_email / transfer / external_post / delete` 等定义为高危;命中即要求显式确认。可配置策略(纯日志 / 软提示 / 硬拦)。

### 组件 6 — 决策日志(可观测性)
每次"拦/放/升级"都落一条结构化轨迹(动作、命中组件、理由、置信度),用 **Langfuse**(开源、自托管)做 trace 可视化。这一条就是面试时的"我有 observability"证据。

---

## 5. 产物 A:评测层(详细设计)

### 5.1 攻击套件
- **AgentDojo** 注入任务(主)。
- **Gray Swan ipi_arena_os** 场景(含 concealment 维度)。
- **你自己的 aggregation-inference 攻击**:构造"多步、单步合规、累积泄露"的攻击任务,塞进同一套接口。← 这是你区别于所有人的实验。

### 5.2 指标定义
| 指标 | 含义 | 目标方向 |
|------|------|----------|
| **ASR** | 攻击成功率 | 越低越好 |
| **Utility (clean)** | 无攻击下任务完成率 | 越高越好 |
| **Utility under attack** | 被攻击时仍完成正常任务的比例 | 越高越好 |
| **Concealment rate** | 攻击成功且对用户隐蔽的比例 | 越低越好 |
| **FPR (误杀率)** | 把正常请求/动作拦掉的比例 | 越低越好 |
| **Latency overhead** | 护栏带来的 p50/p95 延迟增量 | 越小越好 |
| **Cost overhead** | 额外 token / API 成本 | 越小越好 |

### 5.3 报告产物
一键跑出 `report.md` + `report.html`:每个 `(agent × 防御配置 × 攻击套件)` 一行,带上面所有指标。对标对象:**无防御 baseline**、**LLM Guard**、**Lakera**、**AggreGuard(各组件 ablation)**。

---

## 6. 技术栈

- **语言**:Python 3.11+
- **评测基准**:`agentdojo`(pip)/ `inspect_evals` 的 agentdojo 实现;`ipi_arena_os`(GitHub)
- **agent 框架接入**:LangGraph 监控 node(首选,trace 最清晰)/ Claude Agent SDK hook / 进阶 MCP proxy
- **注入检测 baseline**:`ProtectAI/deberta-v3-base-prompt-injection-v2`、`Meta Prompt-Guard-86M`、可选 Lakera API
- **红队/对抗测试**:Garak、PyRIT、Promptfoo
- **可观测性**:Langfuse(自托管)
- **目标 agent 的模型**:本地用你 Mac mini M4 上的 Ollama 跑开源模型做快速迭代;正式跑分用 Claude / GPT API
- **报告**:pandas + 简单 HTML 模板

---

## 7. 里程碑与时间线

> 你同时有论文 + 课程 + 比赛,按"先出最小可量化版本"推进,别一上来全做。

### Phase 0(第 0 周)— 地基
- 装好 AgentDojo,复现官方 baseline 数字(workspace 套件),跑通无防御 ASR/utility。
- 建仓库骨架 + Langfuse 本地起来。
- **出口**:能一键跑出 baseline 报告表。

### Phase 1(第 1–2 周)— MVP
- 实现组件 1(来源标记/信任边界)+ 组件 3(任务对齐)。
- 接组件 2 的现成注入检测器当 baseline。
- 评测层出第一张对照表:无防御 vs 简单防御。
- **出口**:workspace 套件上 ASR 有可见下降 + 一张对照表。

### Phase 2(第 3–4 周)— 差异化核心
- 实现组件 4(聚合监控),先做"累计敏感度预算"分支,再加"准标识符再识别"。
- 把你自己的 aggregation-inference 攻击任务接进评测套件。
- 做误杀率测试(正常多步任务集)。
- **出口**:在聚合攻击子集上,AggreGuard 对比所有现成工具显著更好,且 FPR 可控。

### Phase 3(第 5–6 周)— 对标 + 写作 + 开源
- 加组件 5/6;跑全套 ablation(各组件单开/组合)。
- 与 LLM Guard / Lakera 完整对照。
- 写 README + benchmark 表;开源(MIT/Apache)。
- 起草 workshop/short paper(聚合监控为 novelty 主线)。
- **出口**:可公开的 repo + 一版论文草稿 + 简历 bullet。

### Stretch
- 扩到 computer-use / browser agent 场景;接入更多 task suite;把聚合监控形式化(信息论/DP 预算严谨化)投正会。

---

## 8. 交付物

1. **GitHub 仓库**(开源):中间件 + 评测层 + 一键复现脚本 + benchmark 表。
2. **技术报告 / workshop paper 草稿**:主打 trace 级聚合感知防御。
3. **简历 bullet 草稿**(英文,数字按实测填):
   - *Built AggreGuard, a trace-level guardrail middleware for LLM agents that tracks tool-call provenance and cumulative information disclosure; reduced indirect-prompt-injection ASR on AgentDojo from XX% to YY% while retaining ZZ% benign utility.*
   - *Designed an aggregation-aware monitor (k-anonymity + sensitivity-budget) that detects multi-step inference attacks missed by I/O filters (Lakera, LLM Guard), at <NN ms p50 overhead and <MM% false-positive rate.*
   - *Built a reproducible attack/defense evaluation harness over AgentDojo + Gray Swan IPI kit; open-sourced with a benchmark comparing 4 defenses across 6 security/utility metrics.*

---

## 9. 风险与开放问题

- **误杀是头号风险**:聚合监控天然容易把"合法多步任务"误判。→ 用 HITL 而非硬 block、严格 scope、allowlist、衰减来压。把 FPR 当一等指标公开。
- **阈值/权重标定**:`τ / k / w(a)` 需要在验证集上调,且别 overfit 到 AgentDojo 的特定攻击。→ 留 held-out 攻击集 + 报告跨套件泛化。
- **延迟开销**:逐步监控会加延迟。→ 轻量组件用规则/小模型,重判断只在高危分支触发。
- **泛化性**:单一 task suite 上的结论可能不迁移。→ Phase 3 至少跨两个套件验证。
- **与现成工具的公平对比**:确保 baseline 工具配置到位,不要"打稻草人"。

---

## 10. 参考资料

**基准 / 套件**
- AgentDojo — arXiv 2406.13352
- Gray Swan IPI Arena eval kit — github.com/GraySwanAI/ipi_arena_os

**防御 / 设计**
- Design patterns for securing LLM agents — arXiv 2506.08837
- Defeating prompt injections by design (CaMeL) — arXiv 2503.18813
- Task Shield — arXiv 2412.16682
- AgentArmor — arXiv 2508.01249
- LlamaFirewall — arXiv 2505.03574
- AgentGuardian — arXiv 2601.10440
- Polymorphic Prompt — arXiv 2506.05739
- SecAlign(CCS 2025)

**现成护栏 / 检测器**
- LLM Guard(Protect AI)、NeMo Guardrails(NVIDIA)、Lakera Guard、Llama Guard、ShieldGemma
- ProtectAI/deberta-v3-base-prompt-injection-v2、Meta Prompt-Guard-86M

**红队 / 可观测性**
- Garak、PyRIT、Promptfoo;Langfuse

**经典推理控制(组件 4 的理论根)**
- k-anonymity、quasi-identifier、query auditing、differential privacy budget

**标准**
- OWASP Top 10 for Agentic Applications(2025-12)

---

## 附录:建议仓库结构

```
aggreguard/
├── README.md
├── pyproject.toml
├── aggreguard/
│   ├── middleware/
│   │   ├── provenance.py        # 组件 1
│   │   ├── injection_detect.py  # 组件 2 (封装现成检测器)
│   │   ├── task_alignment.py    # 组件 3
│   │   ├── aggregation.py       # 组件 4 ★
│   │   ├── action_gate.py       # 组件 5
│   │   └── logging.py           # 组件 6 (Langfuse)
│   ├── integrations/
│   │   ├── langgraph_node.py
│   │   ├── claude_sdk_hook.py
│   │   └── mcp_proxy.py         # 进阶
│   └── config.py
├── eval/
│   ├── runner.py                # 产物 A 主流程
│   ├── attacks/
│   │   ├── agentdojo_suite.py
│   │   ├── ipi_arena_suite.py
│   │   └── aggregation_suite.py # 你的独家攻击 ★
│   ├── metrics.py
│   └── report.py
├── benchmarks/
│   └── results/                 # 对照表 + 图
└── tests/
```
