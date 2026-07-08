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

### 6.1 激活的并发控制（必读）

> 配置激活是稀缺资源：同一 `config_type` 在任意时刻只能有一个 `is_active = true` 的版本。并发激活若用"先 UPDATE 旧版本 is_active=false，再 UPDATE 新版本 is_active=true"两条独立语句实现，会出现两个版本同时为 true 的竞态窗口。

**强制约束**：

1. **数据库层**：`config_versions` 表对 `(config_type) WHERE is_active = true` 建立部分唯一索引（Postgres `CREATE UNIQUE INDEX ... WHERE is_active = true`），任何重复激活在 DB 层直接拒绝。
2. **应用层**：激活必须在**单事务**内完成，使用 `SELECT ... FOR UPDATE` 锁定该 `config_type` 下当前激活行，再原子地切换：

   ```text
   BEGIN;
     -- 锁定该类型当前激活行，防止并发激活
     SELECT id FROM config_versions
       WHERE config_type = :type AND is_active = true
       FOR UPDATE;

     -- 置旧版本为非激活
     UPDATE config_versions SET is_active = false, deactivated_at = now()
       WHERE config_type = :type AND is_active = true;

     -- 激活新版本（若并发竞争，部分唯一索引会在此拒绝）
     UPDATE config_versions SET is_active = true, activated_at = now()
       WHERE id = :new_id;
   COMMIT;
   ```

3. **冲突处理**：若 `COMMIT` 因部分唯一索引冲突失败（`unique constraint violation`），应用层应：
   - 回滚事务；
   - 重新读取当前激活版本；
   - 若当前激活版本已是新目标版本，视为他人已成功激活，返回成功（幂等）；
   - 否则按业务策略返回 `CONFIG_ACTIVATE_CONFLICT` 错误码（HTTP 409，见 `ERROR_CODES.md §3.3`）。

4. **禁止模式**：
   - 禁止用两条独立 UPDATE 语句分步激活；
   - 禁止先在应用内存中判断 `is_active` 再写入（check-then-act 竞态）；
   - 禁止跨事务/跨连接分步完成激活。

> 该约束对应 `DATABASE.md §3.12 config_versions` 的部分唯一索引声明，以及 `project_memory.md` 中"并发激活竞态"教训。

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
