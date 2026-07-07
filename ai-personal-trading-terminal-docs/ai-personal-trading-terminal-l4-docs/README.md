# AI Personal Trading Terminal L4 文档包

## 项目定位

**AI Personal Trading Terminal L4** 是一个面向个人加密货币合约交易者的半自动个人交易终端。

系统目标不是做全自动交易机器人，而是建立一套完整的交易工作流：

```text
行情数据 → 市场结构识别 → 自动计划生成 → 动态仓位计算 → 风控审核 → AI评估解释 → 用户确认 → 交易所执行 → 订单/持仓监控 → 交易日志 → 复盘分析
```

系统当前目标自动化等级为 **L4：用户确认后执行**。

也就是说：

- 系统可以自动识别结构、生成候选交易计划、计算开仓仓位、准备交易所订单参数；
- 系统必须经过风控引擎、AI解释、订单预览和用户确认；
- 系统可以在用户确认后提交订单；
- 系统不允许无确认自动开仓；
- 系统 v1.0 不做 L5 全自动交易。

---

## 文档目录

| 文档 | 说明 |
|---|---|
| `SCOPE.md` | 项目范围、v1做什么、不做什么 |
| `PRD.md` | 产品需求文档 |
| `SYSTEM_DESIGN.md` | 总体系统架构 |
| `MODULES.md` | 模块拆分与职责 |
| `AUTOMATION_LEVELS.md` | L0-L5自动化等级定义 |
| `AUTOMATION_DESIGN.md` | 自动计划生成与实时评估设计 |
| `EXECUTION_DESIGN.md` | L4确认执行系统设计 |
| `ORDER_LIFECYCLE.md` | 订单生命周期与状态机 |
| `EXCHANGE_INTEGRATION.md` | 交易所接入设计，以Bitget为第一交易所 |
| `EXECUTION_SAFETY.md` | 执行安全、Kill Switch、Dry Run、安全限制 |
| `RISK_RULES.md` | 通用风控规则 |
| `AI_GUARDRAILS.md` | AI边界与结构化输出规范 |
| `CONFIG_VERSIONING.md` | 配置版本管理 |
| `EVENT_LOG_DESIGN.md` | 事件日志与审计设计 |
| `DATABASE.md` | 数据库设计初稿 |
| `API.md` | 后端API设计初稿 |
| `FRONTEND_PAGES.md` | 前端页面与交互规划 |
| `DEVELOPMENT.md` | 开发路线图 |
| `MVP_ACCEPTANCE.md` | 各版本验收标准 |
| `TESTING.md` | 测试方案 |
| `SECURITY.md` | 密钥、权限、数据安全 |
| `DEPLOYMENT.md` | 部署方案 |
| `OPERATIONS.md` | 运维、备份、监控、故障处理 |
| `USER_TRADING_CONFIG.template.md` | 个人交易配置模板，和系统设计分离 |
| `DECISION_RECORDS.md` | 重大设计决策记录索引 |
| `adr/ADR-0001-l4-not-l5.md` | ADR：为什么选择L4而不是L5 |
| `adr/ADR-0002-risk-engine-first.md` | ADR：为什么风控引擎优先 |
| `adr/ADR-0003-bitget-first.md` | ADR：为什么第一阶段先接Bitget |

---

## 核心原则

1. **算法负责计算，AI负责解释，风控负责拦截，用户负责确认，执行引擎负责提交。**
2. 风控引擎必须独立，任何订单不能绕过风控。
3. AI不能直接下单，不能覆盖风控结论。
4. 真实下单前必须支持 Dry Run。
5. v1.0 默认只做单用户个人终端，不做多用户平台。
6. v1.0 不做全自动交易。
7. 所有计划、订单、风控结论、AI评估、用户确认都必须记录。

---

## 推荐开发顺序

1. `v0.1`：交易计划 + 动态仓位计算 + 风控检查。
2. `v0.2`：行情接入 + K线展示 + 市场结构识别。
3. `v0.3`：自动候选计划生成。
4. `v0.4`：AI实时评估与机会雷达。
5. `v0.5`：订单预览 + Dry Run。
6. `v0.6`：只读实盘同步。
7. `v0.7`：L4小额确认执行。
8. `v1.0`：完整L4个人交易终端。
