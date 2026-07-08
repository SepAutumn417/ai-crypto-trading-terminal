# 终端鉴权设计

## 1. 目标

本系统是**单用户个人交易终端**，不存在多租户隔离需求。鉴权边界只解决一个问题：

> 确保只有终端所有者本人（或其授权的本地/远程入口）能够读取数据、切换系统状态、提交真实订单。

鉴权设计遵循以下约束：

- 单用户模型，不实现角色/组织/权限组；
- 默认本地部署（`127.0.0.1`），可选远程访问（Nginx 反向代理）；
- 真实下单、Kill Switch、配置激活等高危操作必须有二次确认；
- 所有鉴权事件必须可审计。

---

## 2. 威胁模型

### 2.1 本地访问（默认场景）

| 威胁 | 说明 | 缓解 |
|---|---|---|
| 未授权本地进程调用 API | 同机其他进程直接访问 `localhost:8000` | 默认绑定 `127.0.0.1`，仍需口令鉴权 |
| 终端无人值守 | 物理接触者直接操作已登录浏览器 | Session 短过期 + 高危操作二次确认 |
| 口令泄露 | 口令写在配置文件或笔记中 | argon2id 哈希存储，禁用明文 |

### 2.2 远程访问（Nginx 反向代理场景）

| 威胁 | 说明 | 缓解 |
|---|---|---|
| 中间人窃听 | 公网流量被截获 | 强制 HTTPS（Nginx 终止 TLS），后端仅监听 `127.0.0.1` |
| 公网扫描 | `8000` 端口被探测 | Nginx 仅放行白名单 IP，后端端口不暴露公网 |
| Session 劫持 | Cookie/Token 被窃取 | `Secure` + `HttpOnly` + `SameSite=Strict`，短过期，Token 绑定 IP |
| 暴力破解 | 远程爆破登录口令 | 登录限流 + 失败计数锁定 |

### 2.3 不在范围内

- 多用户隔离；
- OAuth / 第三方登录；
- 细粒度 RBAC（角色权限）；
- 提现权限（交易 Key 本身禁用提现，见 `SECURITY.md §2.2`）。

---

## 3. 认证方式

### 3.1 单用户口令

系统仅支持**一个用户**，其凭证为：

- 用户名：固定（或配置项 `AUTH_USERNAME`，默认 `admin`）；
- 口令：首次启动时由用户设置。

### 3.2 首次启动设置口令

首次启动检测：`user_settings` 表无口令哈希时进入初始化流程：

1. 后端返回 `SECOND_CONFIRMATION_REQUIRED` 之外的初始化标志（响应 `{"setupRequired": true}`）；
2. 前端引导用户输入口令（≥ 10 字符，含字母+数字）并二次输入确认；
3. 后端以 argon2id 哈希写入 `user_settings.password_hash`；
4. 写入 `system_events`（`event_type=AUTH_PASSWORD_SET`）；
5. 初始化期间所有非 setup 端点返回 `401 UNAUTHORIZED`。

> 初始化端点仅 `/api/system/setup` 与 `/api/system/health` 放行，其余一律拒绝。

### 3.3 Session 凭证

登录成功后下发 Session，二选一（由配置项 `AUTH_SESSION_TRANSPORT` 决定，默认 `cookie`）：

| 方式 | 传输 | 适用场景 |
|---|---|---|
| Cookie | `Set-Cookie: apt_session=<jwt>; HttpOnly; Secure; SameSite=Strict` | 浏览器前端（默认） |
| Bearer Token | 响应体返回 `{"token": "<jwt>"}`，客户端 `Authorization: Bearer <jwt>` | CLI / 程序化访问 / WebSocket |

JWT 载荷：

```json
{
  "sub": "admin",
  "sid": "session-uuid",
  "iat": 1731000000,
  "exp": 1731003600,
  "ip": "127.0.0.1"
}
```

> Session 不携带任何交易权限信息，权限由"已登录 + 是否二次确认"两态决定，不存在角色枚举。

---

## 4. 授权矩阵

按 endpoint 分三级：

| 等级 | 说明 | 示例端点 | 鉴权要求 |
|---|---|---|---|
| `public` | 健康检查、初始化 | `GET /api/system/health`、`POST /api/system/setup` | 无 |
| `authenticated` | 普通查询、计划创建、风控/AI 评估 | `GET /api/orders`、`GET /api/positions`、`POST /api/trade-plans`、`POST /api/risk/check`、`POST /api/ai/evaluate-plan` | 有效 Session |
| `high-risk` | 状态切换、真实下单、配置激活 | `POST /api/system/kill-switch`、`POST /api/system/execution-mode`、`POST /api/execution/{id}/confirm`、`POST /api/configs/{id}/activate`、`POST /api/execution/orders/{id}/cancel` | 有效 Session **且**二次确认 |

### 4.1 high-risk 端点清单

| 端点 | 风险 | 二次确认形式 |
|---|---|---|
| `POST /api/system/kill-switch` | 切换总熔断状态 | 重新输入口令 |
| `POST /api/system/execution-mode` | 开启/关闭真实执行 | 重新输入口令 |
| `POST /api/execution/{id}/confirm` | 提交真实订单到交易所 | 输入 `CONFIRM` 文本 + 口令校验 |
| `POST /api/configs/{id}/activate` | 激活新配置版本（影响风控/策略） | 重新输入口令 |
| `POST /api/execution/orders/{id}/cancel` | 撤单（可能影响持仓） | 输入 `CONFIRM` 文本 |

> 同值幂等：重复请求 Kill Switch / execution-mode 的相同目标态返回 `200 + 当前态`，不触发二次确认（见 `API.md §14.3`）。

---

## 5. 高危操作二次确认

### 5.1 流程

```
client → POST /api/execution/{id}/confirm  (无 confirmation)
       ← 403 SECOND_CONFIRMATION_REQUIRED   {challengeId, expiresAt}
client → POST /api/execution/{id}/confirm  {confirmationText:"CONFIRM", password:"..."}
       ← 200 执行结果
```

### 5.2 确认形式

| 操作 | 确认形式 |
|---|---|
| Kill Switch 切换 | 重新输入登录口令 |
| execution-mode 切换 | 重新输入登录口令 |
| confirm 下单 | 输入 `CONFIRM` 文本 + 口令校验 |
| config activate | 重新输入登录口令 |
| API Key 轮换（新增/禁用） | 重新输入登录口令（见 `SECURITY.md §2.4.1`） |
| 主加密密钥（MASTER_KEY）轮换切换 | 重新输入登录口令 + TOTP（若启用，见 `SECURITY.md §2.4.2`） |
| 撤单 | 输入 `CONFIRM` 文本 |

### 5.3 TOTP（可选）

配置项 `AUTH_TOTP_ENABLED` 开启后，高危操作二次确认改为 TOTP 6 位动态码（RFC 6238），首次启用时显示 secret 供用户绑定 Authenticator。TOTP 与口令二选一，不叠加。

### 5.4 确认时效

- `challengeId` 有效期 60 秒，过期需重新发起；
- 单个 `challengeId` 仅可用一次；
- 失败 3 次锁定该 challenge，需重新发起。

---

## 6. Session 管理

### 6.1 过期时间

| 场景 | TTL |
|---|---|
| 默认（浏览器） | 1 小时 |
| "记住此设备" | 7 天 |
| CLI / 程序化 Token | 24 小时（不可滑动续期） |

### 6.2 滑动续期

- 每次请求命中有效 Session 时，`exp` 顺延（默认续期 1 小时）；
- 续期上限：自首次登录起最长 24 小时，超过强制重新登录；
- CLI Token 不滑动续期，到期必须重新登录。

### 6.3 并发 Session 限制

- 同一用户最多 **2 个**并发 Session（浏览器 + CLI）；
- 超出新登录踢掉最早 Session，被踢 Session 后续请求返回 `401 SESSION_EXPIRED`；
- `POST /api/auth/logout` 主动注销当前 Session。

### 6.4 Session 失效条件

- 自然过期；
- 主动注销；
- 被新 Session 挤下线；
- Kill Switch 激活**不**强制下线（用户仍需登录查看/解除）；
- IP 变化超过配置阈值（默认 `AUTH_STRICT_IP_BIND=true` 时，IP 变化即失效）。

---

## 7. IP 白名单与本地兜底

### 7.1 本地兜底

- `127.0.0.1` / `::1` 默认放行，不强制在白名单中配置；
- 后端默认绑定 `127.0.0.1`，不监听 `0.0.0.0`；
- 本地访问仍需口令鉴权（兜底仅指网络层放行，不跳过认证）。

### 7.2 远程访问白名单

开启远程访问（Nginx 反代场景）时必须配置 `AUTH_IP_ALLOWLIST`：

```text
AUTH_IP_ALLOWLIST=203.0.113.10,198.51.100.0/24
```

- 不在白名单的来源返回 `403 FORBIDDEN`（不发起到鉴权层）；
- Nginx 必须设置 `X-Real-IP` / `X-Forwarded-For`，后端读取 `X-Real-IP` 作为客户端 IP；
- 配置 `AUTH_TRUST_PROXY=true` 时才信任转发头，否则直连 IP 优先（防伪造）。

### 7.3 反代部署约定

- Nginx 仅监听 443，证书由 Let's Encrypt 或自签；
- `proxy_pass http://127.0.0.1:8000`；
- Nginx 层 `allow`/`deny` 做第一道 IP 过滤；
- 后端 `AUTH_IP_ALLOWLIST` 做第二道校验。

---

## 8. 密码存储

### 8.1 哈希算法

- **argon2id**（`memory=64MiB, iterations=3, parallelism=2`）；
- 每个口令独立 salt；
- 严禁明文、严禁 MD5 / SHA1 / 未加盐 SHA256；
- 哈希字符串存 `user_settings.password_hash`（格式 `$argon2id$v=19$m=65536,t=3,p=2$<salt>$<hash>`）。

### 8.2 口令策略

- 最小长度 10；
- 必须含字母 + 数字；
- 不强制特殊字符（个人终端，避免难记）；
- 不实现口令历史（单用户，轮换由用户自主）。

### 8.3 修改口令

- `POST /api/auth/change-password`（authenticated 级，需当前口令校验）；
- 修改后所有现存 Session 失效，强制重新登录；
- 写入 `system_events`（`event_type=AUTH_PASSWORD_CHANGED`）。

### 8.4 重置口令

无在线找回。口令丢失时：

1. 停止服务；
2. 执行 CLI 重置命令 `apt reset-password`（需服务器文件系统访问权限）；
3. 重置后进入首次启动流程，强制重新设置口令；
4. 写入 `system_events`（`event_type=AUTH_PASSWORD_RESET_OFFLINE`，`actor=system`）。

---

## 9. 审计

所有鉴权事件写入 `system_events`（表结构见 `DATABASE.md §3`，事件类型见 `EVENT_LOG_DESIGN.md §2`）。

### 9.1 鉴权事件清单

| event_type | severity | actor | 触发时机 |
|---|---|---|---|
| `AUTH_PASSWORD_SET` | INFO | user | 首次启动设置口令 |
| `AUTH_PASSWORD_CHANGED` | INFO | user | 修改口令 |
| `AUTH_PASSWORD_RESET_OFFLINE` | WARNING | system | 离线重置口令 |
| `AUTH_LOGIN_SUCCESS` | INFO | user | 登录成功 |
| `AUTH_LOGIN_FAILED` | WARNING | user | 登录失败 |
| `AUTH_LOGIN_LOCKED` | WARNING | system | 失败计数超限锁定 |
| `AUTH_LOGOUT` | INFO | user | 主动注销 |
| `AUTH_SESSION_EXPIRED` | INFO | system | Session 过期/被踢 |
| `AUTH_SECOND_CONFIRMATION_PASSED` | INFO | user | 高危操作二次确认通过 |
| `AUTH_SECOND_CONFIRMATION_FAILED` | WARNING | user | 高危操作二次确认失败 |
| `AUTH_TOKEN_REFRESHED` | INFO | system | Session 滑动续期 |

### 9.2 payload 字段

```json
{
  "ip": "127.0.0.1",
  "userAgent": "Mozilla/5.0 ...",
  "sessionId": "session-uuid",
  "endpoint": "POST /api/execution/{id}/confirm",
  "reason": "wrong_password"
}
```

> 口令、TOTP secret、Token 永不出现在 `payload`，仅记录"通过/失败"事实。

---

## 10. 实施时间线

| 版本 | 鉴权要求 |
|---|---|
| v0.1 | 单用户口令 + Cookie Session（已落地核心路径） |
| **v0.2 前** | **必须完整落地本设计**（Bitget 适配器接入前） |
| v0.2 | market 频道鉴权豁免校验、登录限流、失败锁定 |
| v0.5 | TOTP 可选支持（AI 评估接入前） |
| v0.7 | 远程访问白名单 + Nginx 反代部署文档（Bitget 只读同步前） |
| v0.8 | high-risk 二次确认全链路打通（小金额 L4 执行前） |
| v1.0 | 全量审计回放、Session 安全加固验收 |

> 强制约束：v0.2 接入 Bitget 行情适配器前，本设计的 §1–§4、§8、§9 必须实现并通过测试；v0.8 真实下单前，§5 高危操作二次确认必须可用。
