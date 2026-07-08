# Kill Switch 单一事实源

> 本文档是 Kill Switch 的**唯一事实源**（Single Source of Truth）。其他文档（`EXECUTION_SAFETY.md`、`RISK_RULES.md`、`OPERATIONS.md`、`AUTOMATION_LEVELS.md`）涉及 Kill Switch 时必须链接到本文，不在他处重复定义触发条件与极性约定。

## 1. 定位

Kill Switch 是执行系统的**总熔断开关**。

当 Kill Switch 激活时：

- 禁止一切新开仓 / 加仓 / 自动提交订单；
- 允许查看行情、查看持仓、撤销订单、手动确认平仓类减风险操作；
- 系统从 L4 自动降级到 L3 / 只读模式（见 `AUTOMATION_LEVELS.md §5`）。

Kill Switch 是**最高优先级的安全状态**，优先于任何风控规则、AI 评估、用户意图。一旦激活，所有新订单路径在执行层之前被拦截。

---

## 2. 极性约定

| 字段值 | 含义 | 系统状态 |
|---|---|---|
| `kill_switch = true` | **激活**（熔断态） | 禁止新开仓，允许平仓/减仓/查询 |
| `kill_switch = false` | **恢复交易** | 正常执行流程 |

> **中文"关闭"歧义已通过布尔字段消除**：在中文语境下，"关闭 Kill Switch" 既可理解为"关闭这个功能"也可理解为"关闭熔断态"，存在歧义。本系统一律以布尔字段 `kill_switch` 为准：`true` = 熔断激活，`false` = 恢复交易。文档与 UI 中描述状态时，使用"激活/恢复"而非"打开/关闭"。

UI 显示约定：

- `kill_switch = true` → 红色标记"已熔断"；
- `kill_switch = false` → 绿色标记"交易正常"。

---

## 3. 激活后允许 / 禁止

> 本节为事实源。`EXECUTION_SAFETY.md §2.2 / §2.3` 引用本节，不重复定义。

### 3.1 激活后允许（`kill_switch = true`）

- 查看行情（ticker / kline / orderbook）；
- 查看结构快照；
- 创建交易计划 / 候选计划；
- Dry Run（不真实提交）；
- 查看持仓与订单；
- 撤销已有订单；
- 手动确认**平仓类**减风险操作（如平仓、减仓）；
- 风控检查、AI 评估（只读计算）；
- 修改配置版本（但激活配置需二次确认，且不立即恢复交易）。

### 3.2 激活后禁止（`kill_switch = true`）

- 开新仓；
- 加仓；
- 自动提交订单；
- 进入订单确认页（confirm 流程在 Kill Switch 激活时直接返回 `KILL_SWITCH_ACTIVE`）；
- execution-mode 切换为开启（Kill Switch 激活时 execution_enabled 强制为 false）。

> 撤单与平仓属于"减风险"，允许执行，但撤单本身仍需二次确认（见 `AUTH.md §4.1`）。

---

## 4. 自动触发条件

> 本表合并自 `EXECUTION_SAFETY.md §3`（9 条）、`OPERATIONS.md §3`、`RISK_RULES.md §5 规则 9`、`AUTOMATION_LEVELS.md §5`（L4 降级条件），**统一为唯一事实源**。原各文档中的零散触发条件以本表为准。

| 条件 | 触发动作 | 严重等级 | 自动解除 |
|---|---|---|---|
| WebSocket 断开超过阈值 | 激活 Kill Switch + 启动 REST 轮询 + 禁止新单 | ERROR | 否，重连对账后手动解除 |
| 下单失败连续达到阈值 | 激活 Kill Switch + 禁止执行 | ERROR | 否，人工排查后手动解除 |
| 止损设置失败（TP_SL_FAILED） | 立即激活 Kill Switch + 禁止新单 + 提供补设止损 UI | CRITICAL | 否，补设止损或人工确认后手动解除 |
| 数据库写入失败 | 激活 Kill Switch + 禁止执行 + 内存保留错误上下文 | CRITICAL | 否，恢复连接补写事件后手动解除 |
| 当日亏损达到限制（`daily_loss_limit_r`） | 激活 Kill Switch + 禁止新单 | ERROR | 否，UTC 0 点亏损重置后仍需手动解除 |
| 连续亏损达到限制（`max_consecutive_losses`） | 激活 Kill Switch + 禁止新单 | ERROR | 否，用户手动重置连亏计数后解除 |
| 风控配置异常 / 丢失 | 激活 Kill Switch + 禁止执行 | CRITICAL | 否，配置修复后手动解除 |
| 交易所 API 返回权限错误 | 激活 Kill Switch + 禁止执行 | CRITICAL | 否，Key 修复/轮换后手动解除 |
| 本地时间与服务器时间偏差过大 | 激活 Kill Switch + 禁止执行 | ERROR | 否，NTP 同步后手动解除 |
| 检测到重复订单风险 | 冻结执行 + 激活 Kill Switch | CRITICAL | 否，人工核查后手动解除 |
| 订单状态无法确认（对账不一致） | 激活 Kill Switch + 标记 RECONCILIATION_REQUIRED | ERROR | 否，对账修复后手动解除 |
| 交易所 API 错误率过高 | L4 降级至 L3/只读 + 激活 Kill Switch | ERROR | 否，恢复后手动解除 |
| Kill Switch 已激活（`kill_switch = true`） | RiskEngine 规则 9 持续输出 BLOCK（自洽，维持熔断） | — | 否，需手动解除 |

### 4.1 触发优先级

- 多个条件同时命中时，取**最高严重等级**记录事件；
- 任意一条 CRITICAL 条件命中即立即激活，不等其他检查完成；
- 自动触发的 Kill Switch **不自动恢复**，即使触发条件消失（如 WebSocket 重连成功、时间同步完成），也必须由用户手动解除（见 §5）。

### 4.2 与 L4 降级的关系

Kill Switch 激活本身也是 `AUTOMATION_LEVELS.md §5` 列出的 L4 降级条件之一：激活后系统从 L4 降级到 L3/只读。Kill Switch 解除后，L4 不会自动恢复，需重新满足 `AUTOMATION_LEVELS.md §4` 的 L4 开启条件。

---

## 5. 手动触发与解除

### 5.1 端点

```text
POST /api/system/kill-switch
```

请求体：

```json
{
  "killSwitch": true,
  "reason": "manual_pause",
  "confirmation": {
    "challengeId": "uuid",
    "password": "..."
  }
}
```

> `killSwitch` 字段名与 `user_settings.kill_switch` 一致，极性约定见 §2。

### 5.2 二次确认

手动触发与解除均属于 high-risk 操作（见 `AUTH.md §4.1`），必须二次确认：

1. 客户端先发起不带 `confirmation` 的请求 → 服务端返回 `403 SECOND_CONFIRMATION_REQUIRED` + `challengeId`；
2. 客户端带 `challengeId` + 口令（或 TOTP）重新请求；
3. 服务端校验通过后切换状态。

### 5.3 解除规则

| 触发方式 | 解除规则 |
|---|---|
| 手动激活 | 手动解除 |
| 自动激活 | **必须手动解除**，不自动恢复 |

> 关键约束：**自动触发的 Kill Switch 不允许自动解除**。即使触发条件已消失（如 WebSocket 已重连、时间已同步、亏损已过 UTC 0 点重置），用户也必须显式调用 `POST /api/system/kill-switch` 将 `killSwitch` 设为 `false`，并完成二次确认。这一约束防止系统在用户未察觉的情况下自动恢复交易。

### 5.4 同值幂等

重复请求相同目标态（如当前已 `kill_switch=true`，再次请求 `killSwitch=true`）返回 `200 + 当前态`，不报错，不触发二次确认（见 `API.md §14.3`）。

### 5.5 限流

`POST /api/system/kill-switch` 限流 `1 req / 5s`（见 `API.md §14.4`），防止抖动。

---

## 6. 与其他文档的关系

| 文档 | 关系 | 引用要求 |
|---|---|---|
| `EXECUTION_SAFETY.md §2` | 执行侧语义 | 引用本文件 §2、§3，不在 §2.2/§2.3 重复定义允许/禁止清单 |
| `EXECUTION_SAFETY.md §3` | 自动触发条件 | 已合并到本文件 §4，原文标注"以 `KILL_SWITCH.md §4` 为准" |
| `RISK_RULES.md §5 规则 9` | Kill Switch BLOCK 规则 | 引用本文件 §2 极性约定与 §3 禁止清单 |
| `OPERATIONS.md §3` | 故障处理 | 触发动作以本文件 §4 为准，OPERATIONS 只描述运维处理步骤 |
| `AUTOMATION_LEVELS.md §5` | L4 降级条件 | 降级条件已合并到本文件 §4，并说明 §4.2 双向关系 |
| `API.md §13` | Kill Switch 端点 | 端点定义在 API.md，极性与触发条件引用本文件 |
| `AUTH.md §4.1` | 二次确认 | Kill Switch 切换列为 high-risk |
| `WEBSOCKET_API.md §3` | system.status 广播 | 字段 `killSwitch` 极性引用本文件 §2 |

> 任何文档新增 Kill Switch 相关内容时，必须在本文件更新，他处仅做引用。

---

## 7. 状态持久化

### 7.1 存储字段

Kill Switch 状态持久化在 `user_settings` 表（见 `DATABASE.md §3.18`）：

```sql
CREATE TABLE user_settings (
  id UUID PRIMARY KEY,
  execution_enabled BOOLEAN NOT NULL DEFAULT false,
  kill_switch BOOLEAN NOT NULL DEFAULT true,   -- kill_switch=true 表示熔断态
  ...
);
```

> 默认值 `true`：系统首次启动或异常重启后默认进入熔断态，需用户显式解除后才允许交易。

### 7.2 重启行为

- 系统重启后从 `user_settings` 读取 `kill_switch` 值恢复状态；
- 不因重启自动改变 Kill Switch 状态；
- 若重启前为 `false`（恢复交易），重启后仍为 `false`，但 execution_enabled 重置为 `false`，需用户重新开启 execution-mode（见 `AUTH.md §4.1`）；
- 若重启前为 `true`（熔断态），重启后保持 `true`。

### 7.3 单行约束

`user_settings` 为单行表，通过 `CHECK (id = '00000000-0000-0000-0000-000000000001')` 强制（见 `DATABASE.md`），避免多行导致状态不一致。

---

## 8. 审计

### 8.1 事件记录

每次 Kill Switch 状态变化必须写入 `system_events`（表结构见 `DATABASE.md §3`，事件设计见 `EVENT_LOG_DESIGN.md`）：

| 字段 | 值 |
|---|---|
| `event_type` | `KILL_SWITCH_TOGGLED` |
| `severity` | INFO（手动解除）/ WARNING（手动激活）/ ERROR（自动激活）/ CRITICAL（止损失败等触发） |
| `entity_type` | `system` |
| `entity_id` | `user_settings` 单行 id |
| `actor` | `user` / `system` |
| `payload` | 见下 |

### 8.2 payload 字段

```json
{
  "from": false,
  "to": true,
  "trigger": "manual",
  "reason": "manual_pause",
  "autoCondition": null,
  "sessionId": "session-uuid",
  "ip": "127.0.0.1"
}
```

- `trigger` 取值：`manual` / `auto`；
- `trigger=auto` 时 `autoCondition` 必填，取 §4 表中的条件标识（如 `websocket_disconnected` / `tp_sl_failed` / `daily_loss_limit_reached`）；
- `trigger=manual` 时 `reason` 由用户传入（如 `manual_pause` / `end_of_day` / `market_volatility`）。

### 8.3 审计约束

- Kill Switch 状态变化事件**不可删除**，只能追加（见 `EVENT_LOG_DESIGN.md §5`）；
- 自动触发但未成功写入 `system_events` 的情况（如数据库写入失败）必须在数据库恢复后补写，并标记 `backfilled=true`；
- 审计日志中不得出现口令、Token 等敏感信息。
