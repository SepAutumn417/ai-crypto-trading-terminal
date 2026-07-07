# 个人交易配置模板

> 本文档用于保存个人交易参数。它与系统设计文档分离，避免把个人交易细节写进正式系统架构文档。

## 1. 账户模式

| 模式 | 账户规模 | 风险比例 | 说明 |
|---|---:|---:|---|
| Training | `<填写>` | `<填写>` | 训练模式 |
| Transition | `<填写>` | `<填写>` | 实盘过渡模式 |
| Standard | `<填写>` | `<填写>` | 标准实盘模式 |
| Advanced | `<填写>` | `<填写>` | 高权限模式 |

---

## 2. 风险配置

```yaml
risk:
  max_leverage: 10
  min_risk_reward_ratio: 1.5
  preferred_risk_reward_ratio: 2.0
  min_stop_distance_percent: 0.3
  daily_loss_limit_r: 2
  max_consecutive_losses: 2
  cooldown_minutes_after_loss: 30
```

---

## 3. 执行配置

```yaml
execution:
  enabled: false
  mode: dry_run
  margin_mode: isolated
  allowed_order_types:
    - limit
  require_stop_loss: true
  require_user_confirmation: true
  require_second_confirmation: true
```

---

## 4. 标的配置

```yaml
symbols:
  - BTCUSDT
  - ETHUSDT
  - SOLUSDT
```

---

## 5. 机会等级配置

```yaml
opportunity_grade:
  A:
    max_risk_percent: 3
  B:
    max_risk_percent: 1.5
  C:
    max_risk_percent: 0
  BLOCKED:
    max_risk_percent: 0
```

---

## 6. 禁止交易条件

```yaml
blocked_conditions:
  - no_stop_loss
  - leverage_too_high
  - risk_too_high
  - rr_too_low
  - cooldown_active
  - daily_loss_limit_reached
  - kill_switch_enabled
  - exchange_disconnected
```
