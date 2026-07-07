# 部署方案

## 1. 推荐部署模式

v1.0 推荐单机 Docker Compose 部署。

服务：

```text
nginx
web
api
postgres
redis
worker
scheduler
```

---

## 2. 环境

推荐：

- Ubuntu 22.04 / 24.04；
- Docker；
- Docker Compose；
- 2 vCPU；
- 4GB RAM 起步；
- 80GB SSD 起步。

---

## 3. 网络

- Nginx反向代理；
- HTTPS证书；
- API只通过内网访问数据库和Redis；
- 数据库不开放公网。

---

## 4. 环境变量

示例：

```env
DATABASE_URL=postgres://...
REDIS_URL=redis://...
BITGET_API_KEY=...
BITGET_API_SECRET=...
BITGET_API_PASSPHRASE=...
OPENAI_API_KEY=...
EXECUTION_ENABLED=false
KILL_SWITCH=true
```

---

## 5. 部署阶段

### 阶段1：本地开发

- 本地Docker；
- 假数据；
- 不接真实交易Key。

### 阶段2：服务器测试

- 只读Key；
- 行情同步；
- Dry Run。

### 阶段3：小额L4

- 开启交易Key；
- 限制标的；
- 限制金额；
- 开启全部审计。

---

## 6. 备份

每日备份：

- PostgreSQL dump；
- 配置版本；
- 交易日志；
- 事件日志。

备份要求：

- 加密；
- 至少保留7天；
- 定期恢复测试。

---

## 7. 监控

需要监控：

- API状态；
- 数据库状态；
- Redis状态；
- Worker状态；
- WebSocket连接；
- 交易所API错误率；
- 下单失败次数；
- Kill Switch状态。
