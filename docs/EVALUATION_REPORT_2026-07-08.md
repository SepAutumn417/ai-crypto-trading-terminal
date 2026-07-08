# AI 个人交易终端 — 全面评估报告

> **评审日期**：2026-07-08
> **评审基线**：v0.1 已交付代码 + L4 设计文档包 + v0.1 spec/plan
> **评审范围**：设计文档（27 份 L4 文档 + spec/plan + README）+ 后端代码（apps/api + 7 个 packages + migrations + 配置）+ 前端代码（apps/web 全部）
> **评审维度**：文档完整性 / 架构设计 / 代码正确性 / 安全 / 数据库 / 测试 / v0.2 就绪度
> **项目记忆约束基线**：7 条硬性约束（单位一致性、部分唯一索引、notional/equity 比例、懒初始化、ORM/迁移一致、ValidationError 详情、嵌套事务、激活原子性）

---

## 目录

- [一、总体评价](#一总体评价)
- [二、P0 阻断项](#二p0-阻断项必须立即修复)
- [三、设计文档评估](#三设计文档评估)
- [四、后端代码评估](#四后端代码评估)
- [五、前端代码评估](#五前端代码评估)
- [六、设计 vs 实现一致性交叉核对](#六设计-vs-实现一致性交叉核对)
- [七、优点与亮点](#七优点与亮点)
- [八、v0.2 就绪度矩阵](#八v02-就绪度矩阵)
- [九、建议修复路径](#九建议修复路径)
- [十、关键风险提示](#十关键风险提示)
- [十一、问题汇总总表](#十一问题汇总总表)

---

## 一、总体评价

| 维度 | 评级 | 核心结论 |
|------|------|----------|
| 设计文档 | ⭐⭐⭐⭐ | 方向清晰、风控先行理念正确，但跨文档一致性差、关键 schema 缺失、鉴权设计空白 |
| 后端代码 | ⭐⭐⭐ | 风控/配置版本化工程水准高，但 execution_service 存在 P0 级资金风险，Bitget 适配器无法运行 |
| 前端代码 | ⭐⭐⭐ | 技术栈现代、API 类型定义完整，但零测试、PlanDetail 死循环、错误处理缺失 |
| v0.2 就绪度 | ⚠️ | 行情/K线可启动，但 Bitget 实盘/AI 评估/真实订单前需修复多项 P0/P1 |

**核心结论**：v0.1 验收层面达标，但存在 **3 个 P0 阻断项** 与 **约 30 个 P1 高危项** 必须在 v0.2 实盘前修复。文档与实现之间存在系统性的"规则文档有、实现无"和"版本号/枚举不一致"问题。

---

## 二、P0 阻断项（必须立即修复）

### P0-1 后端：`execute_plan` 允许 SUBMITTED 状态重复下单 [资金损失风险]

- **文件**：[execution_service.py:41-47](file:///f:/crypto/apps/api/src/app/services/execution_service.py)
- **问题**：状态检查允许 `READY_FOR_CONFIRMATION` 与 `SUBMITTED` 两种状态进入下单路径：

  ```python
  if model.status not in (
      PlanStatus.READY_FOR_CONFIRMATION.value,
      PlanStatus.SUBMITTED.value,    # ← 允许已下单状态再次执行
  ):
      raise ValueError(...)
  ```

  `SUBMITTED` 意味着已下单，再次执行会向交易所发新订单并覆盖 `exchange_order_id`。配合 `client_order_id` 含 `uuid4().hex[:8]` 随机后缀（[第 70 行](file:///f:/crypto/apps/api/src/app/services/execution_service.py)），交易所层无法基于 `clientOid` 去重。
- **影响**：真实资金环境下，用户重复点击或前端重试会导致重复开仓。
- **修复**：仅允许 `READY_FOR_CONFIRMATION` 进入；`client_order_id` 改为 `f"plan_{plan_id.hex}"` 去掉随机后缀，让交易所层基于 `clientOid` 幂等去重。

### P0-2 前端：`PlanDetail` useEffect 无限重渲染循环

- **文件**：[PlanDetail.tsx:71-75](file:///f:/crypto/apps/web/components/plans/PlanDetail.tsx)
- **代码**：

  ```typescript
  useEffect(() => {
    if (plan && result && result.plan.id === plan.id) {
      setResult({ ...result, plan });
    }
  }, [plan, result]);
  ```

- **问题**：`result` 在依赖数组中，effect 内 `setResult({...result, plan})` 创建新对象引用 → `result` 变化 → effect 重新触发 → 条件 `result.plan.id === plan.id` 仍为 true（因为刚设置的 `result.plan` 就是 `plan`）→ 再次 `setResult` → **无限循环**，触发 React "Maximum update depth exceeded"。
- **影响**：用户点击计划详情后页面卡死。
- **修复**：

  ```typescript
  useEffect(() => {
    if (plan && result && result.plan.id === plan.id && result.plan.updated_at !== plan.updated_at) {
      setResult(prev => prev ? { ...prev, plan } : prev);
    }
  }, [plan]); // 移除 result
  ```

### P0-3 文档：README v0.2 范围与 DEVELOPMENT.md 严重冲突

- **文件**：[README.md](file:///f:/crypto/README.md) vs [DEVELOPMENT.md](file:///f:/crypto/ai-personal-trading-terminal-docs/ai-personal-trading-terminal-l4-docs/DEVELOPMENT.md)
- **问题**：README 把 v0.2~v0.8 共 6 个版本的工作（行情、Bitget 适配器、AI 评估、真实订单、确认流、交易日志）压缩进 v0.2，与 DEVELOPMENT.md / MVP_ACCEPTANCE.md 的 v0.2（仅行情+K线）完全脱节。
- **版本路线对比**：

  | 版本 | DEVELOPMENT.md 定义 | README 错误归入 v0.2 |
  |------|---------------------|----------------------|
  | v0.2 | 行情接入与图表 | 行情数据接入 ✅ |
  | v0.4 | 自动候选计划 | — |
  | v0.5 | AI 评估 | AI 评估 ❌ |
  | v0.6 | 订单预览+Dry Run | — |
  | v0.7 | 只读实盘同步 | — |
  | v0.8 | 小额 L4 执行 | Bitget 适配器/真实订单/用户确认流 ❌ |
  | v1.0 | 完整 L4 终端 | 交易日志 ❌ |

- **影响**：v0.2 启动评审范围混乱，验收标准无法对齐。
- **修复**：README v0.2 范围改为"行情接入与 K 线图表"（对齐 DEVELOPMENT.md §3 v0.2 与 MVP_ACCEPTANCE.md v0.2），其余项分别归位 v0.5/v0.7/v0.8/v1.0。

---

## 三、设计文档评估

### 3.1 文档完整性

#### 已覆盖且质量较好的领域

- 业务定位、L4 边界、自动化等级（PRD §2-7、SCOPE §2、AUTOMATION_LEVELS §1-6）
- 风控引擎定位、硬禁止/降风险/等待规则、机会等级映射（RISK_RULES §1-10）
- 订单状态机、执行安全、Kill Switch（ORDER_LIFECYCLE、EXECUTION_SAFETY）
- 配置版本管理、事件日志、AI 边界（CONFIG_VERSIONING、EVENT_LOG_DESIGN、AI_GUARDRAILS）
- 版本路线、验收标准、测试/部署/运维（DEVELOPMENT、MVP_ACCEPTANCE、TESTING、DEPLOYMENT、OPERATIONS）

#### [P0] 用户鉴权与授权完全缺失

- **来源**：SECURITY.md 全文仅覆盖交易所 API Key 安全；API.md 全部端点无任何鉴权；PRD §4.2 提及"系统管理员"但无访问控制设计；DECISION_RECORDS.md 未把鉴权列入未来 ADR。
- **问题**：终端自身 REST API（含 `POST /api/system/kill-switch`、`POST /api/execution/{id}/confirm` 等高危端点）没有任何 AuthN/AuthZ 设计。DEPLOYMENT.md §3 又写到"Nginx 反向代理 + HTTPS"，意味着可能远端访问。一个能真实下单的系统无鉴权是阻断级安全漏洞。
- **建议**：新增 `AUTH.md`，至少设计：单用户口令/Token + Session、Cookie 或 JWT；高危操作（Kill Switch、execution-mode、confirm、config activate）强制二次确认；IP 白名单与本地访问兜底。在 v0.2 引入 Bitget 适配器前必须落地。

#### [P1] DATABASE.md 表结构严重不完整

- **来源**：DATABASE.md §2 表总览列出 18 张表，但 §3 只给出了 11 张表的 DDL。
- **缺失 schema 的表**：
  - `order_state_events`（ORDER_LIFECYCLE.md §5 反复引用，DATABASE.md §3 无定义）
  - `positions`（API.md §10 Position APIs 依赖）
  - `trade_journal`（FRONTEND_PAGES.md §9 Journal 页面依赖，字段已在 UI 文档列出却无库表）
  - `review_reports`
  - `config_versions`（v0.1 spec §4.2 被迫自行补 schema）
  - `api_keys`（SECURITY.md §2 反复强调"加密保存"，但无表结构、无加密字段说明）
  - `user_settings`（v0.1 spec §4.2 被迫自行补）
- **建议**：补全所有 18 张表的 DDL，特别是 `api_keys`（含 `key_id`、`encrypted_secret`、`passphrase_encrypted`、`permissions`、`ip_whitelist`、`rotated_at`、`disabled_at`）、`order_state_events`、`positions`、`trade_journal`、`review_reports`、`config_versions`、`user_settings`。

#### [P1] `max_notional_equity_ratio` 硬禁止规则文档有、实现无

- **来源**：RISK_RULES.md §5 规则 14"名义价值 / 账户权益 超过上限（如 20 倍）→ BLOCK"；USER_TRADING_CONFIG.template.md §2 `max_notional_equity_ratio: 20`。
- **问题**：v0.1 spec §3.1 RiskConfig 字段仅 8 个，无 `max_notional_equity_ratio`；v0.1 plan `packages/shared/src/shared/configs.py` 的 `RiskConfig` 同样缺失；`packages/risk-engine/src/risk_engine/rules.py` 仅在 `check_warnings` 中对 `notional_value/equity > 5` 给出 warning，没有 20 倍硬 BLOCK。
- **影响**：文档声明的 14 条硬禁止规则中至少 1 条未实现，且 v0.1 spec §1.3"差异说明"未声明该项被推迟。
- **建议**：在 `RiskConfig` 增加 `max_notional_equity_ratio: Decimal`；在 `check_hard_blocks` 增加判定；同步更新 v0.1 spec §3.1、附录 A seed、USER_TRADING_CONFIG.template.md。

#### [P1] `account_risk_state` 写入路径缺失

- **来源**：v0.1 spec §1.3 声明"当日亏损/连亏/冷却期：v0.1 完整实现读写和检查逻辑"，§4.2 定义了 `account_risk_state` 表。
- **问题**：v0.1 plan Task 6/7 只创建 model 与 seed（初始值 0），没有任何 API 或 service 提供"写"路径；README 与 spec 都说"完整实现读写"，实际是只读。
- **建议**：要么明确声明 v0.1 为只读、写路径在 v0.8 接入真实成交时补；要么提供一个手动调整端点用于演练。

#### [P1] 前端 WebSocket API 设计缺失

- **来源**：MODULES.md §3 "apps/api 职责：提供 REST/WebSocket API"；SYSTEM_DESIGN.md §3.2 同；API.md 全文只有 REST。
- **问题**：v0.2 行情、v0.7 订单/持仓推送、Kill Switch 状态广播都需要 WebSocket，但完全无设计。
- **建议**：v0.2 启动前完成 `WEBSOCKET_API.md`：定义频道（market/ticker、system/status、orders/updates、positions/updates）、消息格式、鉴权、重连、心跳。

#### [P2] 无 API 版本化策略

API.md 全部端点为 `/api/...`，无 `/api/v1/` 前缀；无 deprecation 政策。建议引入 `/api/v1/` 与 Header `X-API-Version`。

#### [P2] 无错误码总表

API.md §1 举例 `RISK_BLOCKED`；v0.1 plan `exceptions.py` 用 `CONFIG_NOT_FOUND / PLAN_NOT_FOUND / PLAN_STATUS_ERROR / DUPLICATE_LABEL`；README 又列 `INVALID_CONFIG_TYPE / INVALID_INPUT`；risk-engine 的 `block_reasons` 又用 `kill_switch_active / no_stop_loss` 等小写 snake_case。错误码风格混用、无集中目录。建议新增 `ERROR_CODES.md`。

#### [P2] 无性能/并发/容量非功能需求

PRD §8 仅含安全/稳定/扩展/可观测，无延迟、吞吐、并发指标。交易系统应对下单端到端延迟、行情订阅并发数、DB 连接池规模有量化目标。

#### [P2] 无 CI/CD、无威胁建模、无 DR/RPO/RTO

DEPLOYMENT.md §6 备份仅一句"每日 dump、加密、保留 7 天、定期恢复测试"，无 RPO/RTO、无异地容灾；SECURITY.md 是清单式无 STRIDE 威胁模型；全仓无 CI 配置文档。

### 3.2 跨文档版本号严重不一致

#### [P1] "小额 L4 执行"版本号在四份文档中不一致

| 文档 | 位置 | 表述 |
|---|---|---|
| DEVELOPMENT.md | §3 | v0.7 = 只读实盘同步；**v0.8 = 小额 L4 确认执行** |
| MVP_ACCEPTANCE.md | v0.7/v0.8 | v0.7 = 只读同步；**v0.8 = 小额 L4 执行** |
| EXECUTION_DESIGN.md | §11 推荐执行模式 | **v0.7 小额 L4**；v1.0 稳定 L4 |
| EXCHANGE_INTEGRATION.md | §5.3 | **v0.7 小额 L4 阶段** |
| l4-docs/README.md | 推荐开发顺序 §7 | **v0.7：L4 小额确认执行** |

5 份文档分裂成两派。DEVELOPMENT/MVP_ACCEPTANCE 一派（v0.8），EXECUTION_DESIGN/EXCHANGE_INTEGRATION/README 一派（v0.7）。
- **建议**：以 DEVELOPMENT.md + MVP_ACCEPTANCE.md 为准（v0.7 只读、v0.8 小额 L4），统一修正 EXECUTION_DESIGN.md §11、EXCHANGE_INTEGRATION.md §5.3、l4-docs/README.md §推荐开发顺序。

#### [P1] SCOPE.md 把 v0.8 能力记到 v1.0 头上

SCOPE.md §2.2"v1.0 支持 L4：…系统撤销未成交订单、系统同步订单状态"，但 DEVELOPMENT.md §3 把"撤单/状态同步"放在 v0.8。建议统一：v0.8 已含撤单与状态同步，v1.0 是"完整闭环 + 全部页面"。

### 3.3 枚举/语义不一致

#### [P1] RiskStatus 枚举三份文档互斥

- MODULES.md §8 risk-engine 输出：`ALLOW | WARN | REDUCE_RISK | BLOCK`（4 值，无 ALLOW_CONFIRM）。
- RISK_RULES.md §4 示例：`"status": "ALLOW_CONFIRM"`（直接用 ALLOW_CONFIRM 作为风控结果）。
- v0.1 spec §3.1 / `shared/enums.py`：`ALLOW | ALLOW_CONFIRM | WARN | REDUCE_RISK | BLOCK`（5 值）。
- **问题**：风控结果到底有没有 `ALLOW_CONFIRM`？MODULES 说没有，RISK_RULES 示例说有，spec 说有但只在 grade A 时输出 `ALLOW`（不是 `ALLOW_CONFIRM`），`ALLOW_CONFIRM` 留给 decision-gate。语义混乱。
- **建议**：明确分层——RiskEngine 只输出 `ALLOW / WARN / REDUCE_RISK / BLOCK`（4 值，去掉 ALLOW_CONFIRM）；DecisionGate 输出 `ALLOW_CONFIRM / WAIT / REDUCE_RISK / BLOCK / EXPIRED`（5 值）。同步修订 MODULES.md §8、RISK_RULES.md §4 示例、v0.1 spec §3.3、shared/enums.py。

#### [P1] RISK_RULES.md §7 把 DecisionGate 状态混入 RiskStatus

RISK_RULES.md §7"等待规则：输出 WAIT 的情况"，但 `WAIT` 是 DecisionGateStatus，不是 RiskStatus。RISK_RULES.md §5 又把 `BLOCK` 当作风控输出，而 `EXPIRED` 也是 DecisionGate 状态。
- **建议**：RISK_RULES.md 应只描述风控层输出（ALLOW/WARN/REDUCE_RISK/BLOCK），把 WAIT/EXPIRED 移到 decision-gate 文档或 AUTOMATION_DESIGN.md。

#### [P1] `stop_distance_percent` 与 `min_stop_distance_percent` 单位命名陷阱

- RISK_RULES.md §3 单位约定表：`riskPercent` 百分数基（1=1%）；`stopDistancePercent` 小数（0.008=0.8%）；`min_stop_distance_percent` 百分数基（0.3=0.3%）。
- 两个字段都带 `_percent` 后缀但单位不同（一个是小数、一个是百分数基），v0.1 plan `rules.py` 必须乘 100 才能比较：`stop_dist_pct = sizing.stop_distance_percent * Decimal("100")`。
- **问题**：这是极易引入 bug 的命名不一致。
- **建议**：统一为百分数基（即 `stop_distance_percent = 0.8` 表示 0.8%），或更名为 `stop_distance_ratio`（小数）。在 RISK_RULES.md §3、shared/configs.py、shared/schemas.py、calculator.py 同步修订并加单元测试防回退。

#### [P2] Kill Switch 布尔极性语义未显式定义

v0.1 spec §9.3"Kill Switch 默认开启：kill_switch 初始为 true"且 `kill_switch=true` 表示阻断；USER_TRADING_CONFIG.template.md `blocked_conditions` 含 `kill_switch_enabled`；RISK_RULES.md §5 规则 9"Kill Switch 关闭 → BLOCK"；EXECUTION_SAFETY.md §2.2/§2.3 反复用"关闭后允许/关闭后禁止"。
- **问题**：中文"关闭"既可理解为"开关置 OFF"也可理解为"熔断/切断"。"`kill_switch=true` 是阻断"的语义未在任何文档明示。
- **建议**：在 SECURITY.md 或 EXECUTION_SAFETY.md §2 顶部加一句："`kill_switch = true` 表示 Kill Switch 已激活（熔断态），禁止新开仓；`kill_switch = false` 表示恢复交易"。

#### [P2] order_intents 的 `risk_config_version` 字段在文档与 schema 间不一致

EXECUTION_DESIGN.md §5 订单意图 JSON 含 `riskConfigVersion: "risk-v1"`；DATABASE.md §3.9 `order_intents` 表无 `risk_config_version` 列。
- **建议**：在 DATABASE.md §3.9 显式增加 `risk_config_version VARCHAR(64)`、`execution_config_version`、`user_trading_config_version`、`ai_config_version`、`strategy_config_version` 列，与 CONFIG_VERSIONING.md §5"每个计划必须记录 5 个配置版本"对齐。

### 3.4 内部矛盾与歧义

#### [P2] v0.1 spec 与 RISK_RULES.md 在 exchange_connected 处理上冲突

RISK_RULES.md §5 规则 10"WebSocket/交易所状态异常 → BLOCK"（硬禁止）；v0.1 spec §3.3"v0.1 中 exchange_connected=false 仅作 warning，不 BLOCK…v0.7 后改为 BLOCK"；v0.1 plan `checker.py` 确实只 warning。
- **建议**：在 RISK_RULES.md §5 规则 10 加注："v0.1 无交易所接入，此项降级为 warning；v0.7 起恢复 BLOCK"。在 v0.1 spec §1.3 差异说明中显式列出此降级。

#### [P2] 候选计划状态机与订单状态机命名重叠且无映射

AUTOMATION_DESIGN.md §4 候选计划状态：`DISCOVERED → WATCHING → READY → RISK_CHECKED → AI_EVALUATED → ALLOW_CONFIRM/WAIT/BLOCK/EXPIRED`；ORDER_LIFECYCLE.md §1 订单意图状态：`DRAFT → RISK_CHECKED → AI_EVALUATED → READY_FOR_CONFIRMATION → CONFIRMED_BY_USER → ...`。两套状态机都有 `RISK_CHECKED / AI_EVALUATED`，但语义不同；从候选计划 promote 到订单意图的状态映射未定义。
- **建议**：新增"候选计划状态 ↔ 订单意图状态映射表"。

#### [P2] API.md §8.3 `clientNonce` 与 EXECUTION_DESIGN.md §8 `clientOid` 概念混用

API.md §8.3 confirm 请求体字段 `clientNonce`；EXECUTION_DESIGN.md §5/§8 全用 `clientOid`；DATABASE.md §3.9 `order_intents` 有 `client_oid` 列。
- **建议**：统一为 `clientOid`（与 Bitget API 字段一致）。

#### [P3] ADR 过于简略，未记录已做决策

ADR-0001/0002/0003 各仅 5-10 行，无"备选方案 / 权衡 / 后果"完整段落；DECISION_RECORDS.md §"未来需要补充的 ADR"中"FastAPI vs NestJS"实际已在 v0.1 plan 定为 FastAPI 但未补 ADR-0004。
- **建议**：补 ADR-0004（选择 FastAPI + Python）、ADR-0005（v1 限价单优先）、ADR-0006（成交后设置 TP/SL 还是预设），并按 Michael Nygard 经典 ADR 模板补充 Context/Decision/Status/Consequences/Alternatives。

### 3.5 架构设计质量

#### 优点

- **风控先行（ADR-0002）**：所有计划/订单必经 RiskEngine + DecisionGate，前端不能直调执行 API，分层清晰。
- **配置版本不可变 + 单一激活（CONFIG_VERSIONING §4-7）**：历史计划保留旧版本，可复盘，是交易系统的正确范式。
- **纯函数核心 + IO 边界分离**：v0.1 plan 把 `position-sizing / risk-engine / decision-gate` 设计为无 IO 纯函数包，可独立单测，工程质量高。
- **L4 而非 L5（ADR-0001）**：保留用户确认，风险可控，理由充分。
- **Dry Run 强制（EXECUTION_SAFETY §5）**：真实下单前必须 Dry Run，正确。

#### [P1] SYSTEM_DESIGN.md 架构图与 MODULES.md 拆分不对应

SYSTEM_DESIGN.md §1 架构图只画了 3 个服务（Market Data / Risk Engine / Execution Engine），但 MODULES.md §1 列了 13 个 packages。Position Sizing、Auto Plan、Decision Gate、AI Evaluation、Config Versioning、Event Log、Journal、Review 等在图中无位置。
- **建议**：重画分层图：表现层（Web）→ API 编排层（apps/api + services）→ 领域纯逻辑层（packages/*）→ 适配层（exchange-adapters）→ 基础设施（PG/Redis）。

#### [P1] DecisionGate 与 AI 的合并逻辑未定义

v0.1 spec §3.4 decision-gate 入参 `ai_evaluation: Optional`（v0.1 恒 None）；AI_GUARDRAILS.md §5"AI 与风控冲突：以风控为准"。但 v0.5 AI 接入后：AI 输出 `recommendedAction: WAIT | ALLOW_CONFIRM | REDUCE_RISK | DO_NOT_TRADE`，DecisionGate 如何合并？AI 能否把 ALLOW 降级为 WAIT？均未定义。
- **建议**：在 AI_GUARDRAILS.md 或新增 `DECISION_FUSION.md` 中明确合并矩阵：风控 BLOCK → 永远 BLOCK（AI 不可覆盖）；风控 ALLOW + AI DO_NOT_TRADE → WAIT；风控 REDUCE_RISK + AI ALLOW_CONFIRM → 仍 REDUCE_RISK。

#### [P2] candidate_plans 与 trade_plans 的 promote 语义不清

API.md §4 `POST /api/auto-plans/{id}/promote` 把候选计划"提升为正式交易计划"，DATABASE.md §3.4 `trade_plans.candidate_plan_id` 有外键。但 promote 时是否复制字段？候选计划后续状态变化是否影响 trade_plan？promote 后 candidate_plans.status 变什么？均未定义。
- **建议**：在 AUTOMATION_DESIGN.md §4 后补"promote 流程"小节。

#### [P2] 配置激活并发控制未定义

CONFIG_VERSIONING.md §6"激活配置"流程未提并发。v0.1 plan `ConfigStore.activate_version` 是内存实现、单线程；DB 实现下若两个请求并发激活同一类型不同版本，仅靠 `UNIQUE INDEX WHERE is_active = true` 会让第二个请求失败，但应用层未处理重试。
- **建议**：在 spec/services/config_service.py 设计中加 `SELECT ... FOR UPDATE` 或重试逻辑。

### 3.6 API 设计

#### 优点

- 统一响应信封 `{success, data, error, requestId}`（API.md §1）清晰。
- 错误结构含 `code/message/details` 便于前端处理。
- 高危执行端点（confirm）要求 `confirmationText: "CONFIRM"` 与 `clientNonce`，符合交易系统二次确认范式。

#### [P1] 无分页/排序/过滤规范

GET `/api/orders`、`/api/journal`、`/api/auto-plans`、`/api/trade-plans`、`/api/configs` 均无 `limit/offset/cursor/sort` 设计。v0.1 spec 仅 `?status=DRAFT` 单字段过滤。v0.2 行情、v0.8 真实订单后数据量会快速增长，缺分页会导致性能与可用性问题。
- **建议**：统一 `?limit=20&cursor=<encoded>&sort=-created_at` 游标分页规范。

#### [P1] 无幂等规范（除订单外）

订单提交有 `clientOid`，但 `POST /api/trade-plans/{id}/check`、`POST /api/configs/{id}/activate`、`POST /api/system/kill-switch` 均无幂等键。activate 与 kill-switch 应是幂等的（同值再调应返回当前态而非报错）。
- **建议**：在 API.md §1 增加"幂等策略"小节：查询类幂等；状态切换类同值幂等返回 200；创建类用 `Idempotency-Key` Header。

#### [P2] 端点命名风格混合

资源用复数 `/api/trade-plans`、`/api/orders`（好）；但 `/api/auto-plans/scan`、`/api/execution/order-preview`、`/api/execution/{id}/dry-run`、`/api/positions/{id}/close-preview` 混用动词路径。
- **建议**：动作类端点统一用 `POST /api/<resource>/<id>:<action>` 风格。

#### [P2] 无限流/配额

无自身 API 限流（防止前端误操作狂点 confirm）。建议在 API.md 加 Rate Limit 段，至少对 `confirm / kill-switch / activate` 限流。

#### [P3] `POST /api/risk/check` 接收客户端传入 `sizing_result`

接收客户端传入 `sizing_result` 再让服务端风控，存在客户端伪造 sizing 风险。v0.1 是个人终端可接受，但应在文档注明"生产中 sizing 必须由服务端重算，不接受客户端传入"。

### 3.7 数据模型

#### 优点

- 选 PostgreSQL + JSONB（结构快照/AI 输出/交易所响应）+ NUMERIC（金额精度）正确。
- `candles` 有 `UNIQUE(exchange, symbol, timeframe, open_time)` 防重复。
- v0.1 spec §4.2 对 `config_versions` 用部分唯一索引 `WHERE is_active = true` 保证单一激活。

#### [P1] 索引覆盖严重不足

DATABASE.md §4 仅 5 个索引。缺失：
- `position_sizing_results(trade_plan_id)`
- `risk_checks(trade_plan_id)`
- `decision_gate_results(trade_plan_id)`
- `exchange_orders(order_intent_id)`、`exchange_orders(exchange, exchange_order_id)`
- `order_state_events(order_intent_id, created_at)`
- `system_events(entity_type, entity_id, created_at)`（按实体查事件）
- `config_versions(config_type, is_active)`
- `candles(exchange, symbol, timeframe, open_time DESC)`

#### [P2] NUMERIC 未指定精度标度

所有金额/价格字段用裸 `NUMERIC`。PostgreSQL `NUMERIC` 无精度上限会带来存储与计算开销。
- **建议**：统一 `NUMERIC(28, 8)` 用于价格/数量，`NUMERIC(20, 8)` 用于金额。

#### [P2] 缺约束与外键级联策略

DATABASE.md §3 大量 `REFERENCES` 未声明 `ON DELETE` 行为；`trade_plans.status` 无 CHECK 约束；`user_settings` / `account_risk_state` 声明"单行表"但无 `CHECK` 或触发器强制。
- **建议**：补 CHECK 约束（status 枚举、leverage > 0、risk_percent > 0）；单行表用 `CHECK (id = '00000000-0000-0000-0000-000000000001')` 强制。

#### [P2] 无数据库迁移/Schema 演进策略

v0.1 plan 用 Alembic，但 DATABASE.md 无迁移说明、无向后兼容策略。
- **建议**：新增 `MIGRATION_POLICY.md`。

#### [P3] RISK_RULES.md §4 示例数值精度有误

equity=1500、riskPercent=1、entry=62400、stop=61900：实际 `stop_distance = 500/62400 = 0.0080128…`，`notional = 15 / 0.0080128 = 1872.0`；但 RISK_RULES.md §4 示例写 `notionalValue: 1875`（用 0.008 整除得 1875）。v0.1 plan test_calculate_long_basic 期望 `notional_value == 1872` 才正确。
- **建议**：RISK_RULES.md §4 示例改为 `notionalValue: 1872` 并注明 `stopDistancePercent: 0.008013`。

### 3.8 风控与安全设计

#### 优点

- 14 条硬禁止 + 7 条降风险 + 6 条等待规则覆盖面广（RISK_RULES §5-7）。
- Kill Switch 自动触发条件表完整（EXECUTION_SAFETY §3，9 条）。
- Dry Run 必须先通过、订单提交前二次检查 7 项（EXECUTION_SAFETY §5/§7）。
- 异常恢复流程（EXECUTION_SAFETY §9）含对账、状态修复、人工标记。
- L4 自动降级条件明确（AUTOMATION_LEVELS §5，10 条）。

#### [P1] Kill Switch 触发条件无单一事实源

EXECUTION_SAFETY.md §3（9 条自动触发）、RISK_RULES.md §5（14 条 BLOCK 含 Kill Switch）、OPERATIONS.md §3（4 类故障）、AUTOMATION_LEVELS.md §5（10 条降级）四处分散且重叠不一致。
- **建议**：新增 `KILL_SWITCH.md` 作为唯一事实源，其他文档链接过去。

#### [P1] 止损设置失败（TP_SL_FAILED）的处置在多文档间略有矛盾

- ORDER_LIFECYCLE.md §4.3：标记严重事件、禁止新单、提示用户人工检查、可提供一键补设止损确认。
- EXECUTION_SAFETY.md §8：记录严重事件、通知用户、禁止新订单、提供人工处理提示。
- OPERATIONS.md §3.3：触发 CRITICAL、开启 Kill Switch、提醒用户人工检查、提供补设止损确认操作。

三处对"是否强制开启 Kill Switch"措辞不同（ORDER_LIFECYCLE 未提 Kill Switch，OPERATIONS 明确开启，EXECUTION_SAFETY 未提）。
- **建议**：统一为"止损设置失败 → 立即触发 Kill Switch + CRITICAL 事件 + 禁止新单 + 提供补设止损 UI"。

#### [P2] 机会等级 B 的"小风险确认"路径未定义

RISK_RULES.md §8：B 级 → "降低风险 / 可观察或小风险确认"；AUTOMATION_DESIGN.md §4 候选计划状态机中 B 级经 REDUCE_RISK 仍可到 ALLOW_CONFIRM？v0.1 plan `gate.py` 中 REDUCE_RISK 直接透传不到 ALLOW_CONFIRM，意味着 B 级无法进入订单预览。
- **问题**：文档说 B 级"可小风险确认"，实现中 B 级永远到不了 ALLOW_CONFIRM，矛盾。
- **建议**：明确 B 级路径——要么 REDUCE_RISK 后用户调整 risk_percent 到 B 的上限（1.5%）后重检可升 ALLOW_CONFIRM；要么 B 级永远只观察。

#### [P2] 当日亏损 R 值的计算来源未定义

RISK_RULES.md §5 规则 6"当日亏损达到限制"，输入字段 `dailyLossR`；USER_TRADING_CONFIG `daily_loss_limit_r: 2`。但"当日亏损 R"如何计算？是当日已平仓交易 R 值之和？包含手续费吗？浮亏算吗？均未定义。
- **建议**：在 RISK_RULES.md §9 后补"当日亏损 R = 当日已平仓交易 (actual_R) 之和 + 当日已实现手续费 / risk_amount"或类似明确定义。

#### [P2] 冷却期触发与解除条件未定义

USER_TRADING_CONFIG `cooldown_minutes_after_loss: 30`；RISK_RULES §5 规则 8"冷却期未结束"。但"何时进入冷却期"？每次亏损都进？还是连亏达上限才进？冷却期结束自动解除还是手动？未定义。
- **建议**：明确"每次平仓亏损（actual_R < 0）即进入冷却期 `cooldown_minutes_after_loss` 分钟；冷却期内 BLOCK 新开仓；冷却期到期自动解除"。

### 3.9 安全设计

#### 优点

- 交易所 API Key 分离只读/交易 Key、不启用提现、绑定 IP、加密存储方向正确。
- 审计事件清单完整（EVENT_LOG_DESIGN §4）。
- 敏感字段脱敏、订单日志不可删除只标记废弃（EVENT_LOG_DESIGN §5）。

#### [P0] 终端自身 API 无鉴权

见 §3.1 [P0]。

#### [P1] `api_keys` 表 schema 缺失

见 §3.1 [P1]。

#### [P1] API Key 加密方案未指定

SECURITY.md §2.1"后端加密保存"、EXECUTION_SAFETY §4"环境变量或密钥管理服务"——但用什么加密？KMS？AES-256-GCM？主密钥存哪？轮换周期？均未定义。
- **建议**：在 SECURITY.md §2 增加"加密方案"小节：明确用 PostgreSQL pgcrypto 还是应用层 AES-256-GCM、主密钥从环境变量/KMS 读取、`encrypted_secret` 列、`key_version` 用于轮换。

#### [P2] 审计日志防篡改未设计

EVENT_LOG_DESIGN §5"订单执行日志不可删除"，但未设计防篡改（hash chain、append-only、WORM 存储）。内部人员或 DBA 可直接 UPDATE。
- **建议**：对 `system_events` 增加 `prev_event_hash` 字段形成链式哈希，或使用 append-only 表 + 触发器禁止 UPDATE/DELETE。

#### [P2] 无密钥轮换流程

EXECUTION_SAFETY §4"支持手动轮换 Key"但无步骤。建议补 `KEY_ROTATION.md`：新 Key 入库 → 旧 Key 标记 `rotating` → 监控 N 天 → 旧 Key `disabled`。

### 3.10 L4 文档与 superpowers spec/plan 的一致性

#### 一致的部分

- v0.1 spec §0 明确声明"不重新定义业务规则，只对 L4 文档包做实施层面的裁剪与具化"。
- v0.1 plan 的 11 个 Task 与 v0.1 spec §1-§7 严格对应。
- v0.1 plan 的 `shared/enums.py`、`RiskConfig`、`PositionSizingResult` 字段与 RISK_RULES.md §3-4、MODULES.md §8 高度对齐。
- v0.1 plan 的验收测试（Task 11）覆盖 MVP_ACCEPTANCE.md v0.1 全部点。

#### [P1] v0.1 spec §3.3 与 RISK_RULES.md §5 规则 10 的 exchange_connected 降级未在 spec §1.3 列出

spec §1.3 只列了 3 项差异（equity 来源、symbol rules、account state），漏了 exchange_connected 降级。

#### [P1] v0.1 spec §3.4 DecisionGate 输入比 MODULES.md §10 少

MODULES.md §10 输入：plan / risk result / AI evaluation / system mode / execution enabled / user settings；v0.1 spec §3.4 输入：risk_result / execution_enabled / kill_switch / ai_evaluation / plan_expired。缺 `plan` 对象本身、`system mode`、`user settings`。v0.1 是简化，但 spec §1.3 未声明该项简化。

#### [P1] v0.1 plan Task 6 model 文件计数与清单不符

Task 6 Step 3 说"8 个 model 文件"，但文件结构总览列出 10 个（含 `base.py` 与 9 个实体 model）。Step 4 `models/__init__.py` 导出 8 个实体类。表述混乱。
- **建议**：明确"9 个实体 model + 1 个 base.py = 10 个文件"。

#### [P2] v0.1 spec §4.2 `account_risk_state` 是 v0.1 新增表，但 DATABASE.md §2 表总览未列

DATABASE.md §2 列了 18 张表，无 `account_risk_state`。spec §4.1 标注"v0.1 新增"，但 L4 文档包 DATABASE.md 应同步补入。

---

## 四、后端代码评估

### 4.1 架构与分层

#### 优点

- **领域包纯函数化**：[risk_engine/checker.py](file:///f:/crypto/packages/risk-engine/src/risk_engine/checker.py)、[rules.py](file:///f:/crypto/packages/risk-engine/src/risk_engine/rules.py)、[position_sizing/calculator.py](file:///f:/crypto/packages/position-sizing/src/position_sizing/calculator.py)、[decision_gate/gate.py](file:///f:/crypto/packages/decision-gate/src/decision_gate/gate.py) 全部纯函数无 IO。
- **uv workspace 划分清晰**：依赖关系 `shared ← position-sizing ← risk-engine ← decision-gate` 与 `shared ← exchange-adapter ← ai-evaluator` 单向无环。
- **API 层薄**：路由只做参数装配与编排，业务逻辑下沉到 service。

#### [P2] `config-versioning` 包是僵尸依赖

- **文件**：[apps/api/pyproject.toml:9](file:///f:/crypto/apps/api/pyproject.toml)、[packages/config-versioning/src/config_versioning/service.py](file:///f:/crypto/packages/config-versioning/src/config_versioning/service.py)
- **问题**：API 声明依赖 `config-versioning`，但 `apps/api/src/app` 下没有任何 import 引用它。`ConfigStore` 是个内存实现，仅供包内单测；API 端的配置激活逻辑在 [api/configs.py](file:///f:/crypto/apps/api/src/app/api/configs.py) 完全重写了一遍。两套实现、两套激活语义，未来易漂移。
- **建议**：要么删除 `config-versioning` 包，要么把激活逻辑下沉到包里、提供 `AsyncConfigStore` 抽象。

#### [P2] `execution_service` 反向依赖 `plan_service._to_schema`

- **文件**：[execution_service.py:10](file:///f:/crypto/apps/api/src/app/services/execution_service.py)
- **问题**：`from app.services.plan_service import _to_schema` — service 之间互相 import 私有函数（带下划线），违反封装。
- **建议**：把 `_to_schema` 提到 `app/services/_mappers.py` 或独立模块。

#### [P3] `shared.errors` 与 `app.exceptions` 异常体系重复

- **文件**：[shared/src/shared/errors.py](file:///f:/crypto/packages/shared/src/shared/errors.py)、[apps/api/src/app/exceptions.py](file:///f:/crypto/apps/api/src/app/exceptions.py)
- **问题**：`shared.errors` 定义了 `ConfigNotFoundError` 等，但全工程无任何代码抛出或捕获它们。API 自己又定义了 `AppException` / `ConfigNotFoundException` 等。
- **建议**：统一到 shared 包。

#### [P3] `shared.api.ApiResponse` 与 `app.response.ApiResponse` 重复

两个 `ApiResponse`/`ApiError` 类。shared 版本只是数据模型，没有 `ok()/err()` 工厂方法；app 版本才有。建议把 `ok()/err()` 上提到 shared。

### 4.2 正确性与 Bug

#### [P0] `execute_plan` 允许 SUBMITTED 状态重复下单

见 §二 P0-1。

#### [P1] `max_notional_equity_ratio` 配置项实际不生效

- **文件**：[config_service.py:40-55](file:///f:/crypto/apps/api/src/app/services/config_service.py)
- **问题**：[`RiskConfig`](file:///f:/crypto/packages/shared/src/shared/configs.py) 有字段 `max_notional_equity_ratio: Decimal = Decimal("20")`（默认 20），seed 也写入了 20（[seed.py:21](file:///f:/crypto/apps/api/src/app/seed.py)），`rules.py:77` 也基于它做硬阻断。但 `get_active_risk_config()` 构造 `RiskConfig` 时**没有从 payload 读取 `max_notional_equity_ratio`**：

  ```python
  return RiskConfig(
      max_risk_percent=..., max_leverage=..., min_risk_reward_ratio=...,
      preferred_risk_reward_ratio=..., min_stop_distance_percent=...,
      daily_loss_limit_r=..., max_consecutive_losses=...,
      cooldown_minutes_after_loss=...,
      # ❌ 缺 max_notional_equity_ratio
  )
  ```

  用户通过 `POST /api/configs` 创建一个 `max_notional_equity_ratio=5` 的新版本并激活后，risk-engine 仍然用默认值 20 判定。项目记忆明确要求"所有 risk checks 必须包含 notional/equity ratio 校验"。
- **建议**：在 `get_active_risk_config` 增加 `max_notional_equity_ratio=_parse_decimal(p["max_notional_equity_ratio"])`；同步增加 `KeyError` 容错（旧版本 payload 可能没有该字段）。

#### [P1] `aiohttp` 未声明为运行时依赖，Bitget 适配器必崩

- **文件**：[apps/api/pyproject.toml:5-11](file:///f:/crypto/apps/api/pyproject.toml)、[exchange-adapter/pyproject.toml:5](file:///f:/crypto/packages/exchange-adapter/pyproject.toml)、[bitget_exchange.py:64-71](file:///f:/crypto/packages/exchange-adapter/src/exchange_adapter/bitget_exchange.py)
- **问题**：`BitgetExchange._get_session()` 内 `import aiohttp`；但 `exchange-adapter` 的 `pyproject.toml` 只把 `aiohttp` 放在 `[dependency-groups] dev = [...]`，`apps/api` 完全没声明 `aiohttp`。一旦 `settings.mock_exchange=False`，第一个请求即 `ImportError`。
- **建议**：把 `aiohttp>=3.9.0` 加入 `exchange-adapter` 的 `dependencies`。

#### [P1] Bitget 凭证从未被读取

- **文件**：[config.py:4-13](file:///f:/crypto/apps/api/src/app/config.py)、[execution_service.py:23-27](file:///f:/crypto/apps/api/src/app/services/execution_service.py)
- **问题**：`Settings` 类**没有** `bitget_api_key` / `bitget_api_secret` / `bitget_passphrase` 字段。`execution_service._get_exchange` 用 `hasattr(settings, 'bitget_api_key')` 判断，永远返回 `False`，于是 `BitgetExchange` 永远用 `None` 凭证构造，调用任何私有接口都会抛 `ValueError("API key and passphrase are required")`。`.env.example` 也缺这些变量。
- **建议**：在 `Settings` 增加 `bitget_api_key: str | None = None` 等三个字段；`.env.example` 同步补充；`_get_exchange` 改为直接 `settings.bitget_api_key`。

#### [P1] `execute_plan` 不调用 `set_leverage` / `set_margin_mode`

- **文件**：[execution_service.py:72-83](file:///f:/crypto/apps/api/src/app/services/execution_service.py)
- **问题**：`place_order` 前没有 `await exchange.set_leverage(model.symbol, int(model.leverage))` 和 `set_margin_mode(model.symbol, model.margin_mode)`。Bitget 默认杠杆是 1x。用户在计划里设置 `leverage=10, margin_mode=isolated` 完全不会生效，实际下单杠杆与计划不一致——破坏 risk-engine 的杠杆校验语义。
- **建议**：在 `place_order` 前调用 `set_leverage` + `set_margin_mode`，并把这两步的失败纳入 `execution_error`。

#### [P1] `execution_service` 的 try/except/finally 在异常路径下仍 commit

- **文件**：[execution_service.py:92-98](file:///f:/crypto/apps/api/src/app/services/execution_service.py)

  ```python
  except Exception as e:
      model.status = PlanStatus.FAILED.value
      model.execution_error = str(e)
      raise
  finally:
      await db.commit()    # ← 即使 raise 也会执行
      await db.refresh(model)
  ```

- **问题**：1) 如果 `place_order` 已经在交易所侧成功、只是网络读响应失败，本地标 FAILED 但订单实际活着，下次 `sync_order_status` 也找不到（`exchange_order_id` 没写入）。2) `db.commit()` 自身可能抛异常会掩盖原始 `Exception`。
- **建议**：把 `commit` 从 `finally` 移到 `try` 末尾和 `except` 内部分别处理；为"place_order 超时但订单可能存活"增加告警事件。

#### [P2] `decision_gate` 的 `ALLOW_CONFIRM` 分支是死代码

- **文件**：[gate.py:30-34](file:///f:/crypto/packages/decision-gate/src/decision_gate/gate.py)
- **问题**：`case RiskStatus.ALLOW | RiskStatus.ALLOW_CONFIRM:` — 但 `risk_engine.checker.check()` 永远不会返回 `RiskStatus.ALLOW_CONFIRM`。枚举里挂着这个值会造成混淆。
- **建议**：要么从 `RiskStatus` 删掉 `ALLOW_CONFIRM`，要么在 `checker.py` 增加 ALLOW_CONFIRM 产生路径。

#### [P2] `decide()` 的 `ai_evaluation` 参数完全未使用

- **文件**：[gate.py:6-12](file:///f:/crypto/packages/decision-gate/src/decision_gate/gate.py)
- **问题**：`ai_evaluation: Optional[dict] = None` 参数被声明但函数体没引用。AI 评估结果目前**完全没有进入决策门**。
- **建议**：v0.2 需要把 `ai_evaluator` 的 `grade/score/conviction` 接入 `decide()`。

#### [P2] `trade_journal_service.get_summary` 把 pnl=0 算作亏损

- **文件**：[trade_journal_service.py:87-88](file:///f:/crypto/apps/api/src/app/services/trade_journal_service.py)

  ```python
  winning_trades = sum(1 for t in closed_trades if t.pnl and t.pnl > 0)
  losing_trades = sum(1 for t in closed_trades if t.pnl and t.pnl <= 0)
  ```

- **问题**：`pnl=0`（保本出场）被算入 `losing_trades`。win_rate 计算基准错乱。
- **建议**：`losing_trades = sum(1 for t in closed_trades if t.pnl is not None and t.pnl < 0)`；增加 `breakeven_trades`。

#### [P2] `get_summary` 用 Python 聚合而非 SQL

- **文件**：[trade_journal_service.py:78-108](file:///f:/crypto/apps/api/src/app/services/trade_journal_service.py)
- **问题**：`select(TradeJournal).where(status=="CLOSED")` 把所有平仓单全量加载到内存再做 `sum/max/min`。1000 笔交易后就会出现可感知延迟。
- **建议**：用 `select(func.count(), func.sum(TradeJournal.pnl), func.max(...), ...)` 一次性 SQL 聚合。

#### [P2] `configs.create_config` 的 TOCTOU 会让重复 label 触发 500

- **文件**：[configs.py:74-97](file:///f:/crypto/apps/api/src/app/api/configs.py)
- **问题**：先 `select` 判重，再 `db.add`+`commit`。两个并发请求可能同时通过判重，第二个 commit 撞 `uq_config_versions_type_label` 唯一约束抛 `IntegrityError`，但代码没有 catch，最终返回 500。
- **建议**：包 try/except IntegrityError，转成 `DUPLICATE_LABEL` 错误响应。

#### [P2] `cancel_plan_order` 对终态订单 raise ValueError 而非 409

- **文件**：[execution_service.py:141-146](file:///f:/crypto/apps/api/src/app/services/execution_service.py)
- **问题**：对 `FILLED/CANCELLED/FAILED` 状态调用 cancel 会 `raise ValueError`，被转成 400。语义上应该是 409 Conflict。
- **建议**：抛 `AppException("ORDER_NOT_CANCELLABLE", ..., 409)`。

#### [P2] `BitgetExchange._parse_order` 缺 `expired` 状态映射

- **文件**：[bitget_exchange.py:277-284](file:///f:/crypto/packages/exchange-adapter/src/exchange_adapter/bitget_exchange.py)
- **问题**：`status_map` 只覆盖 `filled/live/partially_filled/canceled/rejected`，缺 `expired`。Bitget POST_ONLY 限价单超时会进入 expired 状态，会被默认映射为 `OrderStatus.NEW`，导致 `sync_order_status` 把 plan 永远停在 `SUBMITTED`。
- **建议**：`"expired": OrderStatus.EXPIRED`，并在 `_order_status_to_plan_status` 增加 `EXPIRED → PlanStatus.EXPIRED`。

#### [P2] `BitgetExchange._session` 资源泄漏

- **文件**：[bitget_exchange.py:62-71](file:///f:/crypto/packages/exchange-adapter/src/exchange_adapter/bitget_exchange.py)
- **问题**：`_get_exchange()` 每个 HTTP 请求 new 一个 `BitgetExchange`，第一个私有请求 `aiohttp.ClientSession()` 被创建但**从不 close**。长跑会泄漏文件描述符。
- **建议**：把 exchange 做成 app 级单例（`app.state.exchange`），在 `lifespan` 里 close。

#### [P3] `check_warnings` 未防 equity=0 除零

- **文件**：[rules.py:95-98](file:///f:/crypto/packages/risk-engine/src/risk_engine/rules.py)
- **问题**：`ratio = sizing.notional_value / sizing.equity`，外层 `if sizing.notional_value > 0:` 不防 equity=0。
- **建议**：加 `and sizing.equity > 0` 守卫。

#### [P3] `evaluate_trade` 的 `entry_price` 参数未使用

- **文件**：[evaluator.py:344-350](file:///f:/crypto/packages/ai-evaluator/src/ai_evaluator/evaluator.py)
- **建议**：要么删除，要么用于"距离当前价的偏离度"评分。

#### [P3] `plan_service.check_plan` 允许 CHECKED 状态重复 check

- **文件**：[plan_service.py:71](file:///f:/crypto/apps/api/src/app/services/plan_service.py)
- **问题**：CHECKED 状态再次 check 会插入新的 sizing/risk/decision 行，旧的没失效。表会膨胀。
- **建议**：要么禁止 CHECKED 重复 check，要么软删旧记录。

#### [P3] `trade_journal` status 字段无枚举校验

- **文件**：[schemas/trade_journal.py:24,36](file:///f:/crypto/apps/api/src/app/schemas/trade_journal.py)
- **问题**：`status: str = "OPEN"`，接受任意字符串。可以写入 `"FOOBAR"`。
- **建议**：定义 `JournalStatus` 枚举（OPEN/CLOSED/CANCELLED）。

### 4.3 安全

#### [P2] Bitget API 错误信息原样透出到 `execution_error` 字段

- **文件**：[execution_service.py:94,125,153](file:///f:/crypto/apps/api/src/app/services/execution_service.py)、[main.py:49-54](file:///f:/crypto/apps/api/src/app/main.py)
- **问题**：`model.execution_error = str(e)` 会把 `Bitget API error: {msg}` 直接写入 DB 并通过 `TradePlanOut.execution_error` 返回前端。如果错误信息包含内部端点路径或签名调试信息，会泄漏内部架构。
- **建议**：对外 message 走白名单映射，详细错误只写 `system_events.payload`。

#### [P2] Pydantic ValidationError 详情默认全暴露

- **文件**：[main.py:37-46](file:///f:/crypto/apps/api/src/app/main.py)
- **问题**：`{"errors": exc.errors()}` 包含 `input` 字段，会回显用户输入。项目记忆明确要求"API error responses for Pydantic ValidationError must include detailed error information"，所以这是**有意为之**。但 `input` 字段可能包含 token、密码、API key 等敏感字段。
- **建议**：保留 `loc`, `type`, `msg`，对 `input` 做字段名黑名单过滤（password/secret/key/token）。

#### [P3] CORS `allow_methods=["*"]` + `allow_credentials=True`

- **文件**：[main.py:13-19](file:///f:/crypto/apps/api/src/app/main.py)
- **问题**：生产环境应该收窄 methods。`allow_origins` 硬编码 `http://localhost:3000` 不便于部署。
- **建议**：从 `Settings` 读 `cors_origins` 配置。

#### SQL 注入面：全部用 ORM/参数化，无字符串拼接 ✅

全部 `select(...).where(...)` 用绑定参数，无 raw SQL 拼接。

#### `BitgetExchange._sign` 用 HMAC-SHA256+base64 ✅

符合 Bitget v2 规范。但 `query_string` 构造未 URL-encode，含特殊字符的参数会破坏签名。当前用法（symbol/数字）安全。

### 4.4 数据库

#### [P2] ORM 模型与迁移不一致：`TradeJournal` 缺索引声明

- **文件**：[models/trade_journal.py](file:///f:/crypto/apps/api/src/app/models/trade_journal.py)、[migrations/versions/9d7b8a3c2f1e_add_trade_journals_table.py:44-46](file:///f:/crypto/apps/api/migrations/versions/9d7b8a3c2f1e_add_trade_journals_table.py)
- **问题**：迁移建了 `ix_trade_journals_symbol`、`ix_trade_journals_status`、`ix_trade_journals_created_at` 三个索引，但 ORM 模型 `TradeJournal` 没有 `__table_args__` 声明。测试用 `Base.metadata.create_all()` 不会建索引，导致测试和生产行为不一致；未来 `alembic autogenerate` 还会再次生成这些索引造成迁移冲突。
- **建议**：在 ORM 模型加 `__table_args__ = (Index(...), Index(...), Index(...))`。

#### 部分唯一索引声明与迁移一致 ✅

- **文件**：[models/config_version.py:13-23](file:///f:/crypto/apps/api/src/app/models/config_version.py)、[migrations/versions/e465fb3ecf35_init_v0_1_tables.py:135-141](file:///f:/crypto/apps/api/migrations/versions/e465fb3ecf35_init_v0_1_tables.py)
- ORM 与迁移都声明了 `idx_config_versions_active`。守恒测试 [`test_partial_unique_index_enforced`](file:///f:/crypto/apps/api/tests/test_configs_api.py) 验证了双 active 写入会被拒。✅

#### Engine 懒初始化防连接泄漏 ✅

- **文件**：[db.py:11-26](file:///f:/crypto/apps/api/src/app/db.py)
- `_engine` / `_async_session` 全局懒初始化，避免测试环境导入即建连。✅

#### [P3] `risk_checks` / `position_sizing_results` / `decision_gate_results` 缺 `trade_plan_id` 索引

`_get_latest_sizing` 用 `where(trade_plan_id == ...).order_by(id.desc())` 查询，无索引。
- **建议**：加 `Index("ix_position_sizing_results_plan_id", "trade_plan_id")`。

#### [P3] `Numeric` 列未指定精度

所有 `Numeric` 列裸用，PG 会存任意精度。
- **建议**：统一 `Numeric(28, 10)` 或按字段语义区分。

#### [P3] `updated_at` 的 `onupdate=func.now()` 在 ORM 层生效，DB 层无 trigger

如果绕过 ORM 直接 SQL UPDATE，`updated_at` 不会更新。
- **建议**：迁移里加 `onupdate=now()` trigger。

### 4.5 API 与响应一致性

#### [P2] `journals` 和 `ai` 路由用 `HTTPException` 绕过 envelope

- **文件**：[api/journals.py:53,74,85](file:///f:/crypto/apps/api/src/app/api/journals.py)、[api/ai.py:20](file:///f:/crypto/apps/api/src/app/api/ai.py)
- **问题**：`raise HTTPException(status_code=404, detail="Journal not found")` 会产出 `{"detail": "Journal not found"}`，与全工程约定的 `{"success": false, "error": {...}, "request_id": ...}` envelope 不一致。前端 `lib/api.ts` 解析会失败。
- **建议**：改用 `AppException("JOURNAL_NOT_FOUND", "未找到", 404)`。

#### [P2] `configs.create_config` 与 `list_configs` 用 `ApiResponse.err(...)` 返回 200

- **文件**：[configs.py:57,72,84,106,134](file:///f:/crypto/apps/api/src/app/api/configs.py)
- **问题**：业务错误（`INVALID_CONFIG_TYPE`、`DUPLICATE_LABEL`、`CONFIG_NOT_FOUND`、`ACTIVATE_CONFLICT`）全部以 HTTP 200 + `success=false` 返回。违反 REST 语义，监控/告警无法基于 status code 区分。
- **建议**：业务错误用 `AppException` 抛出，让全局 handler 设正确 status code。

#### [P3] `risk.py` 路由手动构造 `PositionSizingSchema`

- **文件**：[risk.py:68-82](file:///f:/crypto/apps/api/src/app/api/risk.py)
- **问题**：手抄 18 个字段构造 schema，新增字段必断。
- **建议**：`PositionSizingSchema.model_validate(body.sizing_result.model_dump())`。

#### [P3] `market.py` 与 `ai.py` 各自实例化 MockExchange

- **文件**：[ai.py:22](file:///f:/crypto/apps/api/src/app/api/ai.py)
- **问题**：`exchange = MockExchange()` 硬编码，不走 settings。
- **建议**：复用 `market._get_exchange()` 或抽到 `app/services/market_service.py`。

### 4.6 测试质量

#### 优点

- 风控硬阻断有完整单测覆盖（[test_rules_block.py](file:///f:/crypto/packages/risk-engine/tests/test_rules_block.py) 13 条规则几乎每条一个用例）。
- 单位换算守恒测试 [`test_min_stop_distance_unit_is_percent_basis`](file:///f:/crypto/packages/risk-engine/tests/test_rules_block.py) ✅
- 部分唯一索引在 DB 层被验证 ✅
- v0.1 验收路径端到端覆盖（[test_acceptance.py](file:///f:/crypto/apps/api/tests/test_acceptance.py)）✅

#### [P1] `execute_plan` / `sync_order_status` / `cancel_plan_order` 零集成测试

- **文件**：[apps/api/tests/](file:///f:/crypto/apps/api/tests/)
- **问题**：整个 execution_service 在测试目录里没有任何集成测试。P0-1（重复下单）、B4（缺 set_leverage）、B5（异常 commit）都不会被现有测试发现。
- **建议**：增加 `test_execution_api.py`：用 MockExchange 走完 create → check → execute → sync → cancel 全流程；增加"SUBMITTED 状态再次 execute 应报错"的回归测试。

#### [P2] `max_notional_equity_ratio` 仅单测覆盖，无 API 集成测试

- **文件**：单测在 [test_rules_block.py:167-178](file:///f:/crypto/packages/risk-engine/tests/test_rules_block.py)
- **问题**：API 层 `POST /api/risk/check` 走 `get_active_risk_config` 加载配置，C2（配置不生效）只在 API 集成测试能暴露，但目前没有。
- **建议**：加测试：创建 `max_notional_equity_ratio=1` 的新 risk 配置激活后，调用 `/api/risk/check` 应返回 BLOCK。

#### [P2] `test_partial_unique_index_enforced` 破坏测试隔离

- **文件**：[test_configs_api.py:91-142](file:///f:/crypto/apps/api/tests/test_configs_api.py)
- **问题**：测试自建独立 engine，在 `eng.begin()` 里 `Base.metadata.drop_all()` + `create_all()`，最后再 drop。如果该测试与其他测试并行跑会清掉别人的表。
- **建议**：用专用数据库或用 `pytest-xdist` 隔离；至少加 `@pytest.mark.isolated` 标记并串行执行。

#### [P2] `conftest.py` 在 fixture 内 `engine.dispose()` 后下一用例仍复用已 dispose 的 engine

- **文件**：[conftest.py:22,45](file:///f:/crypto/apps/api/tests/conftest.py)
- **问题**：模块级 `engine = create_async_engine(...)`，`client` fixture 末尾 `await engine.dispose()`。每个测试都重新建池，浪费且掩盖了"连接池共享"的真实生产语义。
- **建议**：把 `engine`/`TestSession` 改成 session 级 fixture，每个测试用 transaction rollback 隔离。

#### [P3] 领域包 `tests/` 目录无 `conftest.py`、无 `pytest.ini` 配置

根 `pyproject.toml` 配了 `asyncio_mode = "auto"`，但每个包单独 `pytest` 时没有该配置。
- **建议**：每个包 `pyproject.toml` 加 `[tool.pytest.ini_options] asyncio_mode = "auto"`。

### 4.7 依赖与配置管理

#### [P2] `pyproject.toml` 依赖未锁版本

全部 `>=`，没有 lower bound 之外的上限。FastAPI 0.110 → 0.115 之间有 breaking change。
- **建议**：用 `uv lock` 生成 `uv.lock`（已有），部署时 `uv sync --frozen`。

#### [P2] `.env.example` 缺 Bitget 凭证与 CORS 配置

- **文件**：[.env.example](file:///f:/crypto/.env.example)
- **缺**：`BITGET_API_KEY`、`BITGET_API_SECRET`、`BITGET_PASSPHRASE`、`MOCK_EXCHANGE=true`、`CORS_ORIGINS`。

#### [P3] `docker-compose.yml` 只有 postgres，无 API 容器

v0.2 上线前需要补 api 服务（含 Dockerfile + healthcheck）。

#### [P3] `alembic.ini` 硬编码 DB URL，与 `env.py` 重复

`alembic.ini` 写了一份默认 URL，`env.py` 又用 `settings.database_url` 覆盖。前者是死配置。
- **建议**：`alembic.ini` 改为 `sqlalchemy.url = `（空），全部从 env.py 注入。

---

## 五、前端代码评估

### 5.1 架构与结构

#### [P1] 整个应用为客户端组件树，未利用 Server Components

- **文件**：[layout.tsx:1](file:///f:/crypto/apps/web/app/layout.tsx)
- **问题**：`RootLayout` 标注 `'use client'`，导致所有子页面和组件默认为客户端组件。App Router 的核心优势（SSR、流式渲染、SEO、服务端数据获取）完全未被利用。所有页面均标注 `'use client'`。
- **修复**：将 `layout.tsx` 改为 Server Component，仅将 `QueryClientProvider` 包裹的子树抽离为独立的 Client Component。

#### [P2] 首页客户端重定向造成白屏闪烁

- **文件**：[page.tsx:7](file:///f:/crypto/apps/web/app/page.tsx)
- **问题**：使用 `useEffect` + `router.push('/plans')` 做重定向，会先渲染空白页面再跳转。
- **修复**：使用 `next.config.js` 的 `redirects()` 或在 Server Component 中调用 `redirect('/plans')`。

#### [P2] Zustand store 定义但从未使用

- **文件**：[systemStore.ts](file:///f:/crypto/apps/web/store/systemStore.ts) 全文
- **问题**：定义了 `useSystemStore`（executionEnabled、killSwitch），但全局搜索发现没有任何组件 import 或使用它。系统状态实际通过 React Query 的 `['systemStatus']` query key 在 `SystemStatusBadge`、`KillSwitchToggle`、`RiskPage` 间重复获取。store 是死代码。
- **修复**：要么删除 store，要么将系统状态统一收敛到 store 中。

#### [P3] 容器/展示组件分离不彻底

页面组件同时承担数据获取和布局编排，但部分展示组件内部又直接调用 React Query（如 `PlanDetail` 内部有 4 个 mutation + 1 个 query）。展示组件与数据逻辑耦合。

### 5.2 TypeScript 质量

#### [P0] 多处显式 `any` 类型，且已有正确定义却未使用

| 文件 | 行号 | 代码 | 说明 |
|------|------|------|------|
| [api.ts](file:///f:/crypto/apps/web/lib/api.ts) | 6 | `details?: any` | ApiResponse error details 未定义结构 |
| [api.ts](file:///f:/crypto/apps/web/lib/api.ts) | 41 | `payload: Record<string, any>` | ConfigVersion payload 完全无类型 |
| [api.ts](file:///f:/crypto/apps/web/lib/api.ts) | 277 | `payload: any` | createConfig 入参 payload 无类型 |
| [api.ts](file:///f:/crypto/apps/web/lib/api.ts) | 294-295 | `(input: any) => request<any>` | calculatePosition 入参和返回值均无类型 |
| [DecisionCard.tsx](file:///f:/crypto/apps/web/components/plans/DecisionCard.tsx) | 7 | `decision: any` | **已有 `DecisionGateResult` 类型定义却未 import** |
| [RiskCard.tsx](file:///f:/crypto/apps/web/components/plans/RiskCard.tsx) | 7 | `risk: any` | **已有 `RiskCheckResult` 类型定义却未 import** |
| [SizingCard.tsx](file:///f:/crypto/apps/web/components/plans/SizingCard.tsx) | 2 | `sizing: any` | **已有 `PositionSizingResult` 类型定义却未 import** |

- **修复**：`DecisionCard`、`RiskCard`、`SizingCard` 应 import 对应类型；`calculatePosition` 应定义请求和返回类型；`ConfigVersion.payload` 应按 `config_type` 做联合类型区分。

#### [P1] 前后端类型漂移：status/margin_mode/direction 使用宽泛 `string` 而非字面量联合

- **文件**：[api.ts:69](file:///f:/crypto/apps/web/lib/api.ts) (`status: string`)、第 63 行 (`margin_mode: string`)
- **后端对比**：[enums.py](file:///f:/crypto/packages/shared/src/shared/enums.py) 定义了 `PlanStatus`（含 9 个值）、`MarginMode`（`isolated`/`crossed`）、`Direction`（`LONG`/`SHORT`）、`RiskStatus`、`DecisionGateStatus` 等枚举。
- **问题**：前端 `TradePlan.status` 为 `string`，编译器无法捕获拼写错误。
- **修复**：定义与后端枚举对齐的 TypeScript 联合类型。

#### [P1] PlanList 状态样式映射包含无效状态值，缺失有效状态值

- **文件**：[PlanList.tsx:5-14](file:///f:/crypto/apps/web/components/plans/PlanList.tsx)
- **问题**：`statusStyles` 包含 `APPROVED`、`REJECTED`、`CLOSED` 三个**后端 PlanStatus 枚举中不存在的值**；同时缺失 `READY_FOR_CONFIRMATION`、`PARTIALLY_FILLED`、`FAILED`、`EXPIRED` 四个有效状态。
- **修复**：删除无效 key，补全有效 key。

#### [P2] `request<T>` 中 `body.data as T` 为不安全断言

- **文件**：[api.ts:19](file:///f:/crypto/apps/web/lib/api.ts)
- **问题**：当 `body.success === true` 时，`body.data` 仍可能为 `null`。`as T` 断言掩盖了此风险。
- **修复**：添加 `if (body.data === null) throw new Error('Empty response data')`。

### 5.3 代码质量

#### [P0] PlanDetail useEffect 存在无限重渲染循环

见 §二 P0-2。

#### [P1] `getUserSettings` 返回硬编码假数据

- **文件**：[api.ts:266-274](file:///f:/crypto/apps/web/lib/api.ts)

  ```typescript
  getUserSettings: async (): Promise<UserSettings> => {
    const s = await request<SystemStatus>('/api/system/status');
    return {
      execution_enabled: s.execution_enabled,
      kill_switch: s.kill_switch,
      account_equity: null,  // 硬编码 null
      mode: 'training',      // 硬编码
    };
  },
  ```

- **问题**：后端 `UserSettingsOut` 包含真实的 `account_equity`，但后端**没有 GET /api/user-settings 端点**。此函数伪造了 `account_equity: null` 和 `mode: 'training'`，导致 [EquityEditor](file:///f:/crypto/apps/web/components/settings/EquityEditor.tsx) 永远收到 `undefined`，始终显示默认值 `'1500'`。
- **修复**：后端新增 `GET /api/user-settings` 端点返回 `UserSettingsOut`；前端 `getUserSettings` 直接调用该端点。

#### [P1] EquityEditor 保存按钮永久禁用，整个组件为死 UI

- **文件**：[EquityEditor.tsx:16-21](file:///f:/crypto/apps/web/components/settings/EquityEditor.tsx)
- **问题**：保存按钮 `disabled` 属性硬编码为 `true`，`title` 提示"v0.1 暂未实现"。用户可输入但无法保存。
- **修复**：实现后端 `PUT /api/user-settings` 端点后接入；v0.2 前可暂时隐藏此组件。

#### [P2] 重复的格式化函数散布各组件

至少 7 个文件各自定义了 `formatPrice`/`formatPnl`/`formatDate`，逻辑相似但实现细节不同。[utils.ts](file:///f:/crypto/apps/web/lib/utils.ts) 仅有 `cn` 函数。
- **修复**：在 `lib/utils.ts` 中统一并复用。

#### [P2] 变量遮蔽全局 `setInterval`/`clearInterval`

- **文件**：[market/page.tsx:21](file:///f:/crypto/apps/web/app/market/page.tsx)、[ai/page.tsx:20](file:///f:/crypto/apps/web/app/ai/page.tsx)
- **代码**：`const [interval, setInterval] = useState<KlineInterval>('1h');`
- **修复**：重命名为 `klineInterval`/`setKlineInterval`。

#### [P3] `cn` 工具函数过于简陋

- **文件**：[utils.ts](file:///f:/crypto/apps/web/lib/utils.ts) 全文
- **问题**：`cn` 仅做 `filter(Boolean).join(' ')`，无法处理 Tailwind 类冲突（如 `cn('px-2', 'px-4')` 会输出两者）。
- **修复**：引入 `clsx` + `tailwind-merge`。

### 5.4 React/Next.js 最佳实践

#### [P1] PlanForm 表单校验错误不展示给用户

- **文件**：[PlanForm.tsx:23](file:///f:/crypto/apps/web/components/plans/PlanForm.tsx)
- **问题**：`errors` 对象被解构但**全文未使用**。zod schema 定义了校验规则，但校验失败时用户看不到任何提示。
- **修复**：在每个输入框下方渲染 `errors.fieldName?.message`。

#### [P1] QueryClient 无默认配置，无全局错误处理

- **文件**：[layout.tsx:8](file:///f:/crypto/apps/web/app/layout.tsx)
- **问题**：`QueryClient` 未设置任何 `defaultOptions`：无 `retry`、无 `staleTime`（默认 0，每次组件挂载都重新请求）、无全局 `onError` 回调。
- **修复**：

  ```typescript
  const [client] = useState(() => new QueryClient({
    defaultOptions: {
      queries: { staleTime: 30_000, retry: 2, refetchOnWindowFocus: false },
      mutations: { onError: (err) => toast.error(String(err)) },
    },
  }));
  ```

#### [P1] 无加载错误状态展示

- **文件**：所有页面组件
- **问题**：各页面 `useQuery` 只解构 `data` 和 `isLoading`，均未处理 `error`/`isError`。当 API 返回错误时，页面静默失败，用户看到空白或"加载中..."永远不消失。
- **修复**：每个 `useQuery` 解构 `isError`/`error`，渲染错误提示组件。

#### [P2] mutation 错误未处理

- **文件**：[PlanDetail.tsx:27-59](file:///f:/crypto/apps/web/components/plans/PlanDetail.tsx)
- **问题**：`checkMut`、`executeMut`、`syncMut`、`cancelMut` 四个 mutation 均只定义 `onSuccess`，无 `onError`。
- **修复**：添加 `onError`。

#### [P2] AI 评估页 `enabled: false` 配合 `refetch` 的反模式

- **文件**：[ai/page.tsx:31](file:///f:/crypto/apps/web/app/ai/page.tsx)
- **问题**：`useQuery` 设 `enabled: false`，然后用 `refetch()` 手动触发。应使用 `useMutation`。
- **修复**：改用 `useMutation`。

#### [P3] 列表 key 使用数组索引

多处 `key={i}` 或 `key={index}` 使用数组索引作为 key。对于动态列表会导致 React 无法正确复用 DOM。
- **修复**：用业务字段作 key（如 `bid.price`、`signal.name`）。

### 5.5 UX/可访问性

#### [P1] 模态框无可访问性支持

- **文件**：[OrderConfirmModal.tsx](file:///f:/crypto/apps/web/components/plans/OrderConfirmModal.tsx) 全文
- **问题**：无 `role="dialog"`、`aria-modal="true"`、`aria-labelledby`；无焦点陷阱；无 Escape 键关闭；关闭按钮为纯 SVG 无 `aria-label`。
- **修复**：添加 ARIA 属性、监听 `keydown` Escape、使用 `@radix-ui/react-dialog`。

#### [P1] JournalList 使用 div + onClick，不可键盘访问

- **文件**：[JournalList.tsx:46-48](file:///f:/crypto/apps/web/components/journal/JournalList.tsx)
- **代码**：`<div onClick={() => onSelect(journal.id)} className="... cursor-pointer ...">`
- **问题**：无法用 Tab 聚焦，无法用 Enter/Space 激活。
- **修复**：改为 `<button>`。

#### [P2] 交易对选择硬编码，无搜索

`SYMBOLS = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'XRPUSDT']` 硬编码在三个文件中重复定义。Journal 页的下拉只有 3 个交易对。
- **修复**：提取为共享常量；v0.2 考虑从后端获取支持的交易对列表。

#### [P2] 无响应式适配，移动端体验差

- **文件**：[Navbar.tsx](file:///f:/crypto/apps/web/components/layout/Navbar.tsx)
- **问题**：Navbar 有 6 个链接 + 状态徽章，在小屏幕上会溢出。无汉堡菜单。KlineChart 固定 800px 宽度需横向滚动。
- **修复**：添加移动端汉堡菜单；KlineChart 改为响应式宽度。

#### [P3] 无 loading skeleton，仅纯文本"加载中..."

加载状态均为纯文本，用户体验差。仅 [AIScoreCard.tsx](file:///f:/crypto/apps/web/components/ai/AIScoreCard.tsx) 有 skeleton 动画。
- **修复**：统一使用 skeleton 占位组件。

### 5.6 API 集成

#### [P1] `request` 函数无 HTTP 状态检查，无网络错误处理

- **文件**：[api.ts:10-20](file:///f:/crypto/apps/web/lib/api.ts)
- **问题**：
  1. 未检查 `res.ok`。若后端返回 500 + HTML 错误页，`res.json()` 抛出 JSON 解析异常。
  2. 无 `AbortController` 超时控制。
  3. 抛出的错误丢失了 `error.code` 和 `request_id`。
- **修复**：

  ```typescript
  async function request<T>(path: string, init?: RequestInit): Promise<T> {
    const res = await fetch(`${BASE}${path}`, { ...init, headers: {...} });
    if (!res.ok) throw new ApiError(`HTTP ${res.status}`, res.status);
    const body: ApiResponse<T> = await res.json();
    if (!body.success) throw new ApiError(body.error?.message ?? 'API error', body.error?.code, body.request_id);
    if (body.data === null) throw new ApiError('Empty data', 'EMPTY_DATA', body.request_id);
    return body.data;
  }
  ```

#### [P1] Base URL 配置不健全

- **文件**：[api.ts:1](file:///f:/crypto/apps/web/lib/api.ts)、[next.config.js:3-7](file:///f:/crypto/apps/web/next.config.js)
- **问题**：`BASE` 默认为 `''`，依赖 `next.config.js` 的 `rewrites` 代理到 `http://localhost:8000`。生产环境部署时若前端与 API 不同源需设置 `NEXT_PUBLIC_API_BASE_URL`，但无文档说明。
- **修复**：添加 `.env.example` 说明；`next.config.js` 的 destination 用环境变量。

#### [P2] 轮询策略不一致

- 系统状态在 Navbar 和 Risk 页同时 5s 轮询（2 倍流量）
- 订单簿 2s 轮询对真实 Bitget 会产生高频请求
- K线数据无轮询（静态）
- **修复**：系统状态统一到 Zustand store 或 React Query 的 `staleTime` 共享；v0.2 改用 WebSocket。

#### [P2] `calculatePosition` 端点类型完全缺失

- **文件**：[api.ts:294-295](file:///f:/crypto/apps/web/lib/api.ts)
- **问题**：后端已有 `CalculatePositionRequest` schema 和 `PositionSizingOut` 响应类型，但前端完全用 `any`。
- **修复**：前端定义对应类型。

### 5.7 状态管理

#### [P1] React Query query key 不统一，数据缓存碎片化

- `['systemStatus']` 在 [SystemStatusBadge.tsx:8](file:///f:/crypto/apps/web/components/layout/SystemStatusBadge.tsx)、[risk/page.tsx:10](file:///f:/crypto/apps/web/app/risk/page.tsx) 重复使用
- `['activeConfigs']` 在 [risk/page.tsx:15](file:///f:/crypto/apps/web/app/risk/page.tsx)、[settings/page.tsx:16](file:///f:/crypto/apps/web/app/settings/page.tsx) 重复
- 无统一的 query key 工厂函数，key 拼写错误不会报错，invalidate 时容易遗漏。
- **修复**：创建 `lib/queryKeys.ts`。

#### [P2] PlanDetail 本地 state `result` 与 React Query 数据源冲突

- **文件**：[PlanDetail.tsx:14](file:///f:/crypto/apps/web/components/plans/PlanDetail.tsx)
- **问题**：`const [result, setResult] = useState<CheckResult | null>(null)` 将 check 结果存在本地 state。导致：切换计划再切回时 result 丢失；多个组件无法共享 check 结果；需手动用 useEffect 同步（引发 P0-2 的死循环）。
- **修复**：用 `useQuery(['plan-check', planId], ...)` 管理 check 结果。

### 5.8 样式与 UI

#### [P2] Tailwind 配置为空，无设计系统

- **文件**：[tailwind.config.ts:8-10](file:///f:/crypto/apps/web/tailwind.config.ts)
- **问题**：`theme: { extend: {} }` 完全为空。无自定义颜色、间距、字体配置。
- **修复**：定义语义化 token（如 `bg-surface`、`text-primary`、`bg-accent`）。

#### [P2] 无暗色/亮色模式切换，硬编码暗色

- **文件**：[globals.css:5](file:///f:/crypto/apps/web/app/globals.css)
- **问题**：`body { background: var(--bg); }` 硬编码 `#0a0a0a`（暗色）。无 `dark:` 前缀，无 `prefers-color-scheme` 支持。
- **修复**：若需双模式，配置 `darkMode: 'class'` 并用 CSS 变量驱动。

#### [P3] 样式类名冗长重复

`"block w-full bg-gray-900 border border-gray-700 px-2 py-1 rounded"` 在 PlanForm 中重复 7 次。
- **修复**：提取为 Tailwind 组件层或 `cva`。

### 5.9 测试

#### [P0] 前端零测试覆盖

- **文件**：整个 `apps/web/` 目录
- **问题**：未找到任何 `.test.ts`/`.test.tsx`/`.spec.ts`/`.spec.tsx` 文件。`package.json` 无测试脚本、无测试框架依赖。
- **影响**：前端无回归保障。v0.2 新增功能将无法安全迭代。
- **修复**：
  1. 安装 Vitest + @testing-library/react + @testing-library/jest-dom
  2. 为 `lib/api.ts` 的 `request` 函数编写单元测试
  3. 为 `PlanForm` 编写表单校验测试
  4. 为 `PlanDetail` 的 useEffect 逻辑编写测试（防止 P0-2 的死循环回归）
  5. 添加 `package.json` scripts: `"test": "vitest", "test:ci": "vitest run"`

#### [P2] 无 ESLint 配置文件

`package.json` 有 `"lint": "next lint"` 但无 `.eslintrc.json`。首次运行 `next lint` 会交互式生成配置，CI 中会失败。
- **修复**：创建 `.eslintrc.json`：`{ "extends": "next/core-web-vitals", "rules": { "@typescript-eslint/no-explicit-any": "error" } }`。

### 5.10 v0.2 就绪度

#### [P1] K线图需替换为 TradingView Lightweight Charts

- **文件**：[KlineChart.tsx](file:///f:/crypto/apps/web/components/market/KlineChart.tsx) 全文
- **当前**：手写 SVG K线图，固定 800px 宽度，无交互（无缩放/平移/十字线），无实时更新。
- **重构**：安装 `lightweight-charts`，重写组件，添加 ResizeObserver 响应式宽度，添加 WebSocket 增量更新。

#### [P1] 无 WebSocket 基础设施

- **当前**：所有实时数据靠 `refetchInterval` 轮询。
- **重构**：创建 `lib/ws.ts` WebSocket 客户端（自动重连、心跳、订阅管理）；创建 `hooks/useWebSocket.ts` React hook。

#### [P1] 订单确认模态框无倒计时

- **文件**：[OrderConfirmModal.tsx](file:///f:/crypto/apps/web/components/plans/OrderConfirmModal.tsx) 全文
- **重构**：添加倒计时逻辑，倒计时结束自动关闭并标记 EXPIRED。

#### [P1] AI 评分卡片无实时更新

- **文件**：[AIScoreCard.tsx](file:///f:/crypto/apps/web/components/ai/AIScoreCard.tsx) 全文
- **重构**：接入 WebSocket 订阅评分更新。

#### [P2] 交易日志缺少 CRUD UI

- **文件**：[journal/page.tsx](file:///f:/crypto/apps/web/app/journal/page.tsx) 全文
- **当前**：仅有列表查看 + 详情查看（只读）。无新建/编辑/删除/平仓 UI。后端 API 已完整（POST/PUT/DELETE）。
- **重构**：添加 `JournalForm` 组件；`JournalDetail` 添加"平仓"和"编辑"按钮；接入 `useMutation`。

#### [P2] 订单簿无聚合深度展示

- **文件**：[Orderbook.tsx](file:///f:/crypto/apps/web/components/market/Orderbook.tsx) 全文
- **重构**：添加聚合档位选择；显示累计量；接入 WebSocket 实时增量更新。

---

## 六、设计 vs 实现一致性交叉核对

### 6.1 文档声明有、代码实现无

| 文档声明 | 实现状态 | 严重度 |
|----------|----------|--------|
| RISK_RULES §5 规则14：`max_notional_equity_ratio` 硬 BLOCK | rules.py 有判定，但 config_service 不加载该字段 → **永不生效** | P1 |
| v0.1 spec §1.3：`account_risk_state` 完整读写 | 只有 model + seed，无写入 API/service → **只读** | P1 |
| MODULES §10：DecisionGate 输入含 `plan/system mode/user settings` | spec §3.4 简化为 `plan_expired` bool，未声明简化 | P1 |
| API.md §8.3：confirm 用 `clientNonce` | 代码用 `clientOid`，文档与实现字段名不一致 | P2 |
| RISK_RULES §4 示例：`notionalValue: 1875` | 实现与测试期望 `1872`（示例数值算错） | P3 |

### 6.2 代码实现有、文档无

| 实现内容 | 文档状态 |
|----------|----------|
| `trade_journal` 表（v0.1 plan 已建） | DATABASE.md §2 表总览未列 |
| `account_risk_state` 表（v0.1 spec §4.2 定义） | DATABASE.md §2 表总览未列 |
| `config_versions` 部分唯一索引 | DATABASE.md §4 索引清单未列 |
| `TradeJournal` 三个索引（symbol/status/created_at） | ORM 模型未声明（迁移有）→ 测试/生产不一致 |

### 6.3 版本号/枚举不一致汇总

| 主题 | 冲突点 |
|------|--------|
| v0.2 范围 | README（6 项全集）vs DEVELOPMENT/MVP（仅行情+K线） |
| 小额 L4 版本 | DEVELOPMENT/MVP=v0.8 vs EXECUTION_DESIGN/EXCHANGE_INTEGRATION/README=v0.7 |
| RiskStatus 枚举 | MODULES=4 值 vs RISK_RULES 示例 vs spec=5 值 |
| kill_switch 极性 | "关闭"语义在中文里歧义，未显式定义 `true=阻断` |
| 候选计划 vs 订单意图状态机 | 都有 RISK_CHECKED/AI_EVALUATED 但语义不同，无映射表 |

---

## 七、优点与亮点

### 后端

1. **风控硬规则实现完整且单测充分**：13 条硬阻断在 [rules.py](file:///f:/crypto/packages/risk-engine/src/risk_engine/rules.py) 全部落实，[test_rules_block.py](file:///f:/crypto/packages/risk-engine/tests/test_rules_block.py) 逐条覆盖。
2. **单位换算有守恒测试**：`min_stop_distance_percent` 与 `stop_distance_percent` 的百分数基/小数基换算有专门回归测试，是工程上值得肯定的细节。
3. **DB 层强制"单一激活配置"**：部分唯一索引 + ORM 声明 + 迁移 + DB 测试四重保障，杜绝了应用层 race condition。
4. **Engine 懒初始化**：[db.py](file:///f:/crypto/apps/api/src/app/db.py) 避免了测试环境连接泄漏。
5. **Pydantic ValidationError 详情暴露**：[main.py:37-46](file:///f:/crypto/apps/api/src/app/main.py) 符合项目记忆要求。
6. **配置版本化设计成熟**：config_versions 表 + 激活时间戳 + `risk_config_version` 反向记录在 trade_plan/risk_check 上，可追溯每次计划用的配置版本。
7. **领域包零 IO**：risk-engine / position-sizing / decision-gate 完全纯函数，可独立测试。
8. **MockExchange 行情生成合理**：用固定 seed + 随机游走生成 K 线，便于前端开发联调。

### 前端

1. **技术栈现代**：Next.js 14 + TS 5.5 + Tailwind + React Query 5 + Zustand + react-hook-form + zod 是主流栈。
2. **API 类型定义较完整**：[api.ts](file:///f:/crypto/apps/web/lib/api.ts) 为所有主要实体定义了 interface，与后端 Pydantic schema 字段基本对齐。
3. **统一的 API 响应包装**：`ApiResponse<T>` 与后端 `ApiResponse` 完全对齐，`request<T>` 函数统一处理。
4. **React Query 使用得当**：列表/详情用 `useQuery`，变更用 `useMutation` + `invalidateQueries`，条件轮询思路正确。
5. **表单校验有 schema**：[PlanForm.tsx](file:///f:/crypto/apps/web/components/plans/PlanForm.tsx) 用 zod + react-hook-form。
6. **PlanList/PlanDetail 状态驱动 UI**：按计划状态条件渲染按钮，逻辑清晰。
7. **OrderConfirmModal 信息完整**：下单前展示仓位计算、风控检查、决策结果、警告/禁止原因，符合交易终端安全要求。
8. **组件文件组织清晰**：按 domain 分目录，组件命名直观。
9. **`tsconfig.json` 开启 `strict: true`**。
10. **后端测试覆盖良好**：`apps/api/tests/` 有 9 个测试文件覆盖所有 API 端点。

### 文档

1. **风控先行（ADR-0002）理念正确**。
2. **配置版本不可变 + 单一激活**是交易系统正确范式。
3. **L4 而非 L5**（保留用户确认）风险可控。
4. **Dry Run 强制**正确。
5. **v0.1 spec/plan 工程落地度高**，纯函数包 + 单事务编排 + 部分唯一索引专业。

---

## 八、v0.2 就绪度矩阵

| v0.2 模块 | 就绪度 | 阻塞项 |
|-----------|--------|--------|
| 行情接入 + K 线图表 | 🟡 可启动 | 需补 `MARKET_DATA_DESIGN.md`、Bitget K 线接口规约、Chart 集成文档；前端 K线图需替换为 TradingView Lightweight Charts；需 WebSocket 基础设施 |
| Bitget 适配器实盘 | 🔴 不可上 | aiohttp 依赖缺失 + Settings 凭证字段缺失 + set_leverage 缺失 + expired 状态映射 + P0-1 重复下单 |
| AI 评估接入 | 🟡 框架在 | ai_evaluation 未接入 decision_gate；需补 `AI_EVALUATION_DESIGN.md`（prompt/模型/兜底/缓存） |
| 真实订单提交 | 🔴 不可上 | P0-1 + set_leverage + 异常 commit + 缺鉴权 + 缺 `order_state_events` 表 |
| 用户确认流 | 🟡 UI 在 | 需倒计时、确认令牌时效、失败回退 UI；需补 `CONFIRMATION_FLOW.md` |
| 交易日志 | 🟢 基本就绪 | 需修 win_rate 计算（pnl=0 误算亏损）、SQL 聚合、HTTPException→AppException；需 CRUD UI |

---

## 九、建议修复路径

### 第一阶段：立即修复（P0，1-2 天）

1. 修 `execution_service` 重复下单（P0-1）
2. 修 `PlanDetail` useEffect 死循环（P0-2）
3. 修 README v0.2 范围（P0-3）
4. 修 3 个 Card 组件 `any` 类型（极低成本）

### 第二阶段：v0.2 实盘前必修（P1，1-2 周）

5. 修 `max_notional_equity_ratio` 加载（B1）+ 补 API 集成测试
6. 修 Bitget 适配器运行时依赖与凭证（B2/B3）+ set_leverage（B4）+ expired 状态（B8）
7. 修 execution_service 异常 commit 与幂等（B5）+ 补集成测试（B6）
8. 修前端 API 健壮性（F4）+ 错误状态展示（F5）+ 类型对齐（F7）
9. 落地终端 API 鉴权设计（D1，新增 `AUTH.md`）
10. 补全 DATABASE.md 缺失的 7 张表 DDL（D2）
11. 统一版本号与 RiskStatus 枚举（D5/D6）
12. 修 `getUserSettings` 硬编码假数据 + EquityEditor 死 UI（F2/F3）
13. 修 PlanForm 校验错误展示（F6）+ QueryClient 默认配置（F8）

### 第三阶段：v0.2 迭代中（P2，2-4 周）

14. 补 `MARKET_DATA_DESIGN.md` / `WEBSOCKET_API.md` / `BITGET_ADAPTER_SPEC.md`
15. 前端 WebSocket 基础设施 + K 线图替换 + 订单确认倒计时
16. AI 评估接入 decision_gate（B7）+ 补 `AI_EVALUATION_DESIGN.md`
17. 前端测试框架搭建（Vitest + Testing Library）
18. 统一 `stop_distance_percent` 单位命名（D7）
19. TradeJournal ORM 索引声明 + win_rate 修复
20. Kill Switch 单一事实源（`KILL_SWITCH.md`）
21. 前后端类型对齐（status/margin_mode/direction 联合类型）
22. 补 `api_keys` 加密方案设计

---

## 十、关键风险提示

1. **资金安全风险**：当前 execution_service 在真实交易所环境下存在重复下单、杠杆不一致、本地失败但远端成功无补偿三个独立风险路径，**严禁在修复前切换 `mock_exchange=False`**。

2. **配置失效风险**：`max_notional_equity_ratio` 是项目记忆中的硬规则，但实际永不生效——用户创建的任何风险配置中的该字段都会被忽略，risk-engine 永远用默认 20 倍判定。

3. **安全裸奔风险**：终端 API 无任何鉴权，`POST /api/system/kill-switch`、`POST /api/execution/{id}/confirm` 等高危端点可被任意访问。若 DEPLOYMENT.md §3 的 Nginx 反向代理生效，远程可触发。

4. **前端体验风险**：PlanDetail 死循环在用户点击计划详情时必然触发，是当前最影响可用性的 bug。

5. **文档漂移风险**：README v0.2 范围错误已导致本次评估的 v0.2 范围讨论基于错误前提，需立即修正以避免后续迭代范围失控。

6. **测试缺失风险**：execution_service 零集成测试，前端零测试覆盖。任何重构都缺乏回归保障。

---

## 十一、问题汇总总表

### P0 阻断项（3 项）

| # | 类别 | 文件 | 问题摘要 |
|---|------|------|----------|
| 1 | 后端-正确性 | [execution_service.py:41-47](file:///f:/crypto/apps/api/src/app/services/execution_service.py) | SUBMITTED 状态可重复下单，资金损失风险 |
| 2 | 前端-React | [PlanDetail.tsx:71-75](file:///f:/crypto/apps/web/components/plans/PlanDetail.tsx) | useEffect 无限重渲染循环 |
| 3 | 文档-一致性 | [README.md](file:///f:/crypto/README.md) vs [DEVELOPMENT.md](file:///f:/crypto/ai-personal-trading-terminal-docs/ai-personal-trading-terminal-l4-docs/DEVELOPMENT.md) | v0.2 范围与版本路线严重冲突 |

### P1 高危项（30 项）

#### 后端（10 项）

| # | 类别 | 文件 | 问题摘要 |
|---|------|------|----------|
| B1 | 正确性 | [config_service.py:40-55](file:///f:/crypto/apps/api/src/app/services/config_service.py) | `max_notional_equity_ratio` 配置项永不生效 |
| B2 | 依赖 | [pyproject.toml](file:///f:/crypto/apps/api/pyproject.toml) | `aiohttp` 未声明为运行时依赖，Bitget 适配器必崩 |
| B3 | 正确性 | [config.py:4-13](file:///f:/crypto/apps/api/src/app/config.py) | Bitget 凭证字段在 Settings 完全不存在 |
| B4 | 正确性 | [execution_service.py:72-83](file:///f:/crypto/apps/api/src/app/services/execution_service.py) | 下单前不调用 `set_leverage`/`set_margin_mode` |
| B5 | 正确性 | [execution_service.py:92-98](file:///f:/crypto/apps/api/src/app/services/execution_service.py) | 异常路径 `finally: commit` 会掩盖原始异常 |
| B6 | 测试 | [apps/api/tests/](file:///f:/crypto/apps/api/tests/) | execution_service 零集成测试 |
| B7 | 正确性 | [gate.py:6-12](file:///f:/crypto/packages/decision-gate/src/decision_gate/gate.py) | `ai_evaluation` 参数未使用，AI 评估未进入决策门 |
| B8 | 正确性 | [bitget_exchange.py:277-284](file:///f:/crypto/packages/exchange-adapter/src/exchange_adapter/bitget_exchange.py) | `_parse_order` 缺 `expired` 状态映射 |
| B9 | 正确性 | [bitget_exchange.py:62-71](file:///f:/crypto/packages/exchange-adapter/src/exchange_adapter/bitget_exchange.py) | `_session` 资源泄漏 |
| B10 | 正确性 | [configs.py:74-97](file:///f:/crypto/apps/api/src/app/api/configs.py) | create_config TOCTOU 漏 IntegrityError 处理 |

#### 前端（8 项）

| # | 类别 | 文件 | 问题摘要 |
|---|------|------|----------|
| F1 | TypeScript | 3 个 Card 组件 | 显式 `any`，类型已定义未 import |
| F2 | 代码质量 | [api.ts:266-274](file:///f:/crypto/apps/web/lib/api.ts) | `getUserSettings` 返回硬编码假数据 |
| F3 | 代码质量 | [EquityEditor.tsx:16-21](file:///f:/crypto/apps/web/components/settings/EquityEditor.tsx) | 保存按钮永久禁用，死 UI |
| F4 | API | [api.ts:10-20](file:///f:/crypto/apps/web/lib/api.ts) | `request` 无 HTTP 状态检查/超时/错误码保留 |
| F5 | React | 6 个 page.tsx | 所有页面无 error 状态渲染 |
| F6 | React | [PlanForm.tsx:23](file:///f:/crypto/apps/web/components/plans/PlanForm.tsx) | zod 校验错误不展示给用户 |
| F7 | TypeScript | [PlanList.tsx:5-14](file:///f:/crypto/apps/web/components/plans/PlanList.tsx) | 状态样式含无效 key，缺有效 key |
| F8 | React | [layout.tsx:8](file:///f:/crypto/apps/web/app/layout.tsx) | QueryClient 无默认配置 |

#### 文档（12 项）

| # | 类别 | 问题摘要 |
|---|------|----------|
| D1 | 安全 | 终端自身 API 完全无 AuthN/AuthZ |
| D2 | 完整性 | DATABASE.md 缺 7 张表 DDL |
| D3 | 完整性 | 前端 WebSocket API 设计完全缺失 |
| D4 | 风控 | `max_notional_equity_ratio` 硬禁止规则文档有、实现无 |
| D5 | 一致性 | "小额 L4"版本号 v0.7 vs v0.8 不一致 |
| D6 | 一致性 | RiskStatus 枚举三文档互斥 |
| D7 | 一致性 | `stop_distance_percent` 与 `min_stop_distance_percent` 同名异单位 |
| D8 | 完整性 | `account_risk_state` 写入路径缺失但 spec 声明"完整读写" |
| D9 | 风控 | Kill Switch 触发条件无单一事实源 |
| D10 | 风控 | TP_SL_FAILED 是否触发 Kill Switch 三处不一致 |
| D11 | 架构 | DecisionGate 与 AI 合并矩阵未定义 |
| D12 | 安全 | `api_keys` 加密方案未指定 |

### P2 中危项（约 30 项，详见各章节）

包括：config-versioning 僵尸依赖、execution_service 反向依赖私有函数、TradeJournal ORM 索引缺失、journals/ai 路由 HTTPException 绕过 envelope、configs 业务错误一律 200、Bitget 错误信息透出、测试隔离问题、前端 Zustand store 死代码、格式化函数重复、轮询策略不一致、query key 不统一、Tailwind 无设计系统、前端无 ESLint 配置等。

### P3 低危项（约 15 项，详见各章节）

包括：ADR 过简、`cn` 工具简陋、列表 key 用索引、Numeric 精度未指定、`updated_at` 无 trigger、`alembic.ini` 死配置、`uv.toml` 固化镜像源等。

---

**报告完毕**

如需针对任一具体问题给出修订草案（如 `execution_service` 幂等重写、`api_keys` 表 DDL、`AUTH.md` 初稿、`RiskStatus` 枚举统一方案、前端测试框架搭建），请指明优先项。
