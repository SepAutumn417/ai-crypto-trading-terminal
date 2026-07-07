# 配置版本管理设计

## 1. 为什么需要配置版本

交易系统中的规则会不断调整，例如：

- 风险比例；
- 杠杆上限；
- 最小盈亏比；
- 止损距离阈值；
- 机会评级规则；
- 执行权限。

如果不记录配置版本，历史交易复盘时无法知道当时使用的是哪一版规则。

---

## 2. 配置类型

| 类型 | 说明 |
|---|---|
| risk_config | 风控规则配置 |
| strategy_config | 结构与计划生成规则 |
| execution_config | 执行规则配置 |
| ai_config | AI提示词与输出规范 |
| user_trading_config | 用户交易参数配置 |
| symbol_config | 标的精度和交易限制 |

---

## 3. 配置版本号

建议格式：

```text
risk-v1.0.0
strategy-v1.0.0
execution-v0.7.0
ai-v1.0.0
user-config-v1.0.0
```

---

## 4. 配置存储

表：`config_versions`

字段：

- id；
- config_type；
- version；
- payload；
- payload_hash；
- is_active；
- created_at；
- activated_at；
- deactivated_at；
- note。

---

## 5. 交易计划记录配置版本

每个计划必须记录：

- risk_config_version；
- strategy_config_version；
- execution_config_version；
- user_trading_config_version；
- ai_config_version。

---

## 6. 配置变更流程

1. 创建新配置草稿；
2. 系统校验；
3. 生成版本号；
4. 激活配置；
5. 记录事件日志；
6. 新计划使用新配置；
7. 历史计划保留旧配置版本。

---

## 7. 配置回滚

配置错误时允许回滚：

- 选择历史版本；
- 激活历史版本；
- 写入回滚事件；
- 新计划使用回滚版本。

---

## 8. 对比分析

复盘模块应支持按配置版本统计：

- 胜率；
- 平均R；
- 最大回撤；
- 风控拦截次数；
- 破规次数；
- A/B/C机会表现。
