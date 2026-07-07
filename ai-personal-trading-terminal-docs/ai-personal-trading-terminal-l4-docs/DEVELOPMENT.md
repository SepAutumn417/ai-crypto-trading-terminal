# 开发路线图

## 1. 开发原则

1. 先闭环，后美化；
2. 先Dry Run，后真实执行；
3. 先只读同步，后交易权限；
4. 风控先于AI；
5. 订单状态机先于真实下单；
6. 每个版本冻结需求，通过验收后再进入下一阶段。

---

## 2. 技术栈建议

### 推荐组合

| 层 | 技术 |
|---|---|
| 前端 | Next.js / React |
| UI | Tailwind CSS |
| 图表 | TradingView Lightweight Charts |
| 后端 | FastAPI 或 NestJS |
| 数据库 | PostgreSQL |
| 缓存/队列 | Redis |
| 定时任务 | Celery/BullMQ/APScheduler |
| 部署 | Docker Compose |
| AI | 外部LLM API |
| 交易所 | Bitget API |

### 推荐优先级

如果开发者更熟 Python 和AI数据处理：

```text
Next.js + FastAPI + PostgreSQL + Redis
```

如果开发者更熟 TypeScript 全栈：

```text
Next.js + NestJS + PostgreSQL + Redis
```

---

## 3. 版本路线

## v0.1 交易计划与仓位计算

目标：完成最小交易计划检查闭环。

功能：

- 创建手动交易计划；
- 输入入场、止损、止盈；
- 自动计算风险金额；
- 自动计算名义仓位；
- 自动计算保证金；
- 自动计算盈亏比；
- 风控检查；
- 保存计划。

不做：

- 行情接入；
- AI；
- 下单。

---

## v0.2 行情接入与图表

目标：接入行情并展示K线。

功能：

- Bitget REST K线；
- K线入库；
- K线图展示；
- 切换标的；
- 切换周期。

---

## v0.3 市场结构识别

目标：自动识别基础市场结构。

功能：

- Swing High/Low；
- 趋势/震荡判断；
- BOS/CHOCH；
- 支撑压力区；
- 禁交易区域。

---

## v0.4 自动候选计划生成

目标：生成候选计划。

功能：

- Opportunity Radar；
- 候选计划状态机；
- 机会评级；
- 自动入场区/止损/目标；
- 初步风控。

---

## v0.5 AI评估与解释

目标：增加AI解释层。

功能：

- AI结构解释；
- AI计划质量分析；
- AI风险解释；
- AI等待条件；
- 结构化输出。

---

## v0.6 订单预览与Dry Run

目标：准备L4执行基础。

功能：

- Order Intent；
- Order Preview；
- Dry Run；
- 请求体生成；
- clientOid；
- 执行日志。

不做真实下单。

---

## v0.7 只读实盘同步

目标：接入真实账户只读数据。

功能：

- 读取账户权益；
- 读取持仓；
- 读取订单；
- 读取成交；
- 持仓监控；
- 自动日志草稿。

---

## v0.8 小额L4确认执行

目标：开启小额真实执行。

功能：

- 启用交易Key；
- 用户确认后提交限价单；
- 设置止损止盈；
- 订单状态同步；
- Kill Switch；
- 错误处理。

限制：

- 小额；
- 逐仓；
- 限价单；
- 必须止损；
- 必须确认。

---

## v1.0 L4个人交易终端

目标：完整L4闭环。

功能：

- Dashboard；
- Opportunity Radar；
- Chart Workspace；
- Trade Plan Center；
- Risk Center；
- Order Preview；
- Execution Monitor；
- Journal；
- Review；
- Settings。

---

## 4. 后续版本

## v1.1 提醒中心

- 关键位提醒；
- 计划触发提醒；
- 风控提醒；
- 持仓偏离提醒。

## v1.2 Replay训练

- 历史行情回放；
- 模拟计划；
- 训练复盘。

## v1.3 增强市场数据

- 资金费率；
- OI；
- 清算数据；
- 多空比。

## v2.0 多交易所扩展

- Binance/OKX等；
- 统一适配器；
- 多账户只读。

---

## 5. 开发冻结点

每个版本上线后冻结：

- v0.1冻结计划/仓位计算；
- v0.2冻结K线基础；
- v0.3冻结结构算法第一版；
- v0.4冻结候选计划状态机；
- v0.6冻结订单状态机；
- v0.8冻结真实执行安全规则。

新想法进入Backlog，不允许打断当前版本。
