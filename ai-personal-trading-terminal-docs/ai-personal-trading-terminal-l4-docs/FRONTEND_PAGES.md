# 前端页面规划

## 1. 总体导航

```text
Dashboard
Opportunity Radar
Chart Workspace
Trade Plans
Order Preview
Execution Monitor
Risk Center
Journal
Review
Settings
```

---

## 2. Dashboard

### 目标

展示系统总状态。

### 组件

- 当前账户权益；
- 今日盈亏；
- 今日风险状态；
- Execution Mode状态；
- Kill Switch状态；
- 当前持仓；
- 候选机会摘要；
- AI市场摘要；
- 系统健康状态。

---

## 3. Opportunity Radar

### 目标

展示系统自动扫描出的候选交易计划。

### 组件

- 标的筛选；
- 周期筛选；
- A/B/C/Blocked分类；
- 候选计划卡片；
- AI解释；
- 等待条件；
- 风控状态。

### 候选计划卡片字段

- symbol；
- direction；
- setup type；
- entry zone；
- stop loss；
- targets；
- RR；
- grade；
- status；
- max risk；
- action button。

按钮：

- 保存观察；
- 提升为计划；
- 查看图表；
- 放弃。

---

## 4. Chart Workspace

### 目标

图表分析主页面。

### 布局

```text
左侧：标的列表
中间：K线图
右侧：结构分析 + AI评估
底部：计划与仓位计算
```

### 图表显示

- K线；
- Swing High/Low；
- 支撑压力区；
- 入场区；
- 止损线；
- 止盈线；
- 禁交易区域；
- 当前候选计划。

---

## 5. Trade Plans

### 目标

管理正式交易计划。

### 功能

- 创建手动计划；
- 从候选计划生成；
- 风控检查；
- AI评估；
- 进入订单预览；
- 取消计划；
- 计划过期。

---

## 6. Order Preview

### 目标

真实执行前的最后确认页。

必须展示：

- 交易对；
- 方向；
- 入场价；
- 止损价；
- 止盈价；
- 数量；
- 杠杆；
- 保证金模式；
- 最大计划亏损；
- 所需保证金；
- 预估手续费；
- 盈亏比；
- 风控结论；
- AI解释；
- 交易所请求摘要；
- 风险警告。

按钮：

- Dry Run；
- 确认提交；
- 取消。

高风险订单要求输入：

```text
CONFIRM
```

---

## 7. Execution Monitor

### 目标

监控订单和持仓。

### 组件

- 未成交订单；
- 成交订单；
- 部分成交；
- 止盈止损状态；
- 当前持仓；
- 持仓距离止损/止盈；
- 订单事件时间线。

---

## 8. Risk Center

### 目标

查看和管理风险状态。

### 组件

- 当前风控配置；
- 今日亏损；
- 连亏次数；
- 冷却期；
- Kill Switch；
- 禁交易原因；
- 最近风控拦截事件。

---

## 9. Journal

### 目标

查看交易日志。

### 字段

- symbol；
- direction；
- setup type；
- opportunity grade；
- planned R；
- actual R；
- PnL；
- fee；
- followed plan；
- emotion tag；
- review status。

---

## 10. Review

### 目标

复盘统计。

### 组件

- R曲线；
- 账户权益曲线；
- 胜率；
- 平均R；
- 最大回撤；
- A/B/C机会表现；
- 风控拦截统计；
- 情绪标签统计；
- AI复盘摘要。

---

## 11. Settings

### 设置项

- 交易所API；
- 执行模式；
- Kill Switch；
- 风控配置；
- AI配置；
- 自选标的；
- 备份设置；
- 通知设置。
