# 安全设计

## 1. 安全目标

保护：

- API Key；
- 账户数据；
- 执行权限；
- 交易日志；
- 系统配置。

---

## 2. API Key管理

### 2.1 存储

- 不在前端存储；
- 不在日志中打印；
- 后端加密保存；
- 支持环境变量或密钥管理；
- Secret永不通过API返回前端。

### 2.2 权限

- 只读Key和交易Key分离；
- 交易Key不开提现；
- 交易Key绑定服务器IP；
- 可随时禁用交易Key。

### 2.3 加密方案

> `api_keys` 表结构见 `DATABASE.md §3.17`。

- **算法**：AES-256-GCM（带认证标签，防篡改）；
- **主密钥**：从环境变量 `MASTER_KEY`（32 字节 base64）读取，或从 KMS（如 AWS KMS / 阿里云 KMS）获取；
- **字段加密**：`encrypted_secret`、`passphrase_encrypted` 列存储密文 + nonce + tag；
- **轮换**：`key_version` 字段标记主密钥版本，轮换主密钥后新写入用新 version，旧数据按需后台重加密；
- **查询**：`key_id`（交易所返回的 apiKey）不敏感，明文存储用于查询；
- **日志脱敏**：日志中只出现 `key_id` 前 4 位 + `***`，如 `bg_a1b2***`。

主密钥严禁入库，严禁写入 `payload` JSONB，严禁通过 API 返回。

### 2.4 密钥轮换流程

本系统的"密钥"分两类，轮换流程不同，必须分开管理：

| 类型 | 说明 | 触发场景 |
|---|---|---|
| **交易所 API Key** | 在交易所创建、存入 `api_keys` 表的 apiKey/secret/passphrase | 怀疑泄露、定期（建议 90 天）、权限调整、IP 变更 |
| **主加密密钥（MASTER_KEY）** | 加密 `api_keys.encrypted_secret` 的对称密钥，存于环境变量/KMS | 怀疑泄露、定期（建议 180 天）、人员变动、加密算法升级 |

#### 2.4.1 交易所 API Key 轮换

> 双 Key 共存期是安全设计的关键：旧订单查询、未结算仓位、挂单管理仍需旧 Key；新订单用新 Key。

**前置检查**：

1. 在交易所创建新 API Key，权限与旧 Key 完全一致（只读 + 交易，不开提现，绑定服务器 IP）；
2. 确认新 Key 通过 `EXCHANGE_API_ERROR` 之外的连通性测试（GET 账户余额、GET 持仓）；
3. 确认当前 Kill Switch 未激活（`kill_switch = false`），否则先处理异常再轮换。

**轮换步骤（单事务）**：

```text
BEGIN;
  -- 1. 旧 Key 改为 rotating，记录轮换开始时间
  UPDATE api_keys SET status = 'rotating', rotating_since = now()
    WHERE id = :old_key_id AND status = 'active';

  -- 2. 新 Key 入库为 active（加密写入，见 §2.3）
  INSERT INTO api_keys (id, exchange, key_id, encrypted_secret, passphrase_encrypted,
                        key_version, permissions, ip_whitelist, status, created_at)
    VALUES (:new_id, :exchange, :new_key_id, :new_encrypted, :new_passphrase_encrypted,
            :key_version, :permissions, :ip_whitelist, 'active', now());
COMMIT;
```

**双 Key 共存期（默认 7 天）**：

- 执行层**优先用新 Key**提交订单；
- 查询层（持仓、订单、成交）**优先用旧 Key**，确保历史数据可追溯；
- 监控旧 Key 是否还有未结算订单 / 未平仓位；
- 每日检查 `api_keys` 表 `rotating_since`，超 7 天仍未结算的需人工介入。

**完成轮换**：

1. 旧 Key 所有订单已结算、所有仓位已平（或迁移到新 Key 视角的对账完成）；
2. 旧 Key 在交易所禁用；
3. `UPDATE api_keys SET status = 'disabled', disabled_at = now() WHERE id = :old_key_id`；
4. 记录 `system_events`（type = `API_KEY_ROTATED`，level = `INFO`，含 old_key_id / new_key_id / 完成时间）。

**异常回滚**：

- 若新 Key 在共存期内异常（如被交易所封禁），`UPDATE api_keys SET status = 'disabled' WHERE id = :new_key_id`，旧 Key 回置 `active`；
- 已用新 Key 提交的订单仍需通过新 Key 查询（不可丢），记录 `system_events`（level = `WARNING`）。

#### 2.4.2 主加密密钥（MASTER_KEY）轮换

> 主密钥轮换不影响交易所侧 Key，只影响 `encrypted_secret` 的解密密钥。必须后台重加密所有 `api_keys` 行。

**前置准备**：

1. 生成新主密钥（32 字节随机，base64 编码）；
2. 新主密钥写入 KMS 或环境变量 `MASTER_KEY_V2`，**不删除**旧 `MASTER_KEY`；
3. `api_keys` 表的 `key_version` 字段用于区分每行是用哪版主密钥加密的（当前活跃版本存于 `app_config.master_key_active_version`）。

**重加密流程（后台任务）**：

```text
for each row in api_keys where status in ('active', 'rotating'):
    plaintext = decrypt(row.encrypted_secret, MASTER_KEY_V1)   # 用旧密钥解密
    new_ciphertext = encrypt(plaintext, MASTER_KEY_V2)          # 用新密钥加密
    UPDATE api_keys SET encrypted_secret = :new_ciphertext,
                       passphrase_encrypted = :new_passphrase,
                       key_version = 2
      WHERE id = row.id;
```

**切换与清理**：

1. 所有行重加密完成后，原子切换 `app_config.master_key_active_version = 2`；
2. 执行层读取密钥时按 `row.key_version` 选择对应主密钥解密（双密钥共存窗口）；
3. 观察 7 天无解密失败后，从环境变量/KMS 移除 `MASTER_KEY_V1`；
4. 记录 `system_events`（type = `MASTER_KEY_ROTATED`，level = `INFO`）。

**异常处理**：

- 重加密过程中某行失败 → 跳过该行，记录 `WARNING`，不影响其他行；
- 切换后出现解密失败 → 立即回切 `master_key_active_version = 1`，未重加密的行仍可用旧密钥；
- 主密钥丢失（无备份）→ 所有 `encrypted_secret` 不可恢复，必须在交易所重置 API Key 后重新入库（这是灾难场景，需 DR 流程）。

#### 2.4.3 轮换频率与审计

| 类型 | 建议频率 | 强制触发 |
|---|---|---|
| 交易所 API Key | 90 天 | 怀疑泄露、人员离职、IP 变更 |
| 主加密密钥 | 180 天 | 怀疑泄露、加密算法升级（如 AES-256 → 后量子算法） |

所有轮换操作必须：

- 写入 `system_events`（type 区分 `API_KEY_ROTATED` / `MASTER_KEY_ROTATED`）；
- 在审计日志中记录操作者、时间、新旧 id/version；
- 触发 `AUTH.md §5` 定义的高危操作二次确认（口令 + TOTP，若启用）。

---

## 3. 用户确认安全

真实执行必须：

- 有有效会话；
- 有订单预览；
- 有风控通过；
- 有二次确认；
- 有确认日志。

---

## 4. 网络安全

- 使用HTTPS；
- 服务器防火墙只开放必要端口；
- 数据库不暴露公网；
- Redis不暴露公网；
- 管理后台限制访问。

---

## 5. 数据安全

- 数据库定期备份；
- 备份加密；
- 敏感字段脱敏；
- 日志保留策略；
- 恢复流程测试。

---

## 6. 执行安全

- Kill Switch；
- Dry Run；
- 订单幂等；
- 风控强制检查；
- 止损强制检查；
- 异常降级。

---

## 7. 审计

记录以下操作：

- 登录；
- API Key变更；
- 配置变更；
- 开启执行；
- 用户确认下单；
- Kill Switch状态变化；
- 风控被触发。
