# 设计决策记录索引

| ADR | 标题 | 状态 |
|---|---|---|
| ADR-0001 | 选择L4而不是L5 | Accepted |
| ADR-0002 | 风控引擎优先 | Accepted |
| ADR-0003 | 第一阶段先接Bitget | Accepted |
| ADR-0004 | 后端采用 FastAPI | Accepted |
| ADR-0005 | 前端实时状态采用 WebSocket 推送 | Accepted |
| ADR-0006 | 止盈止损采用灵活双策略 | Accepted |

---

## ADR 模板

新增 ADR 遵循 Michael Nygard 模板，包含以下章节：

- **状态**（Proposed / Accepted / Deprecated / Superseded）；
- **背景**（Context：决策面临的问题与约束）；
- **决策**（Decision：做出的选择）；
- **后果**（Consequences：正面/负面影响 + 强制约束）；
- **备选方案**（Alternatives：考虑但拒绝的方案及拒绝原因）；
- **关联**（相关文档与 ADR）。

文件命名：`ADR-XXXX-kebab-case-title.md`，编号 4 位递增。

---

## 未来需要补充的 ADR

以下决策尚未记录，待对应版本实现时补充：

- 是否支持市价单（当前 v0.8 倾向限价单优先，市价单留待评估）；
- 是否拆分数据库和应用服务器（单用户 v1.0 倾向同机部署，待压测验证）；
- AI 供应商选择（OpenAI / Anthropic / 国产模型，待 v0.5 评估）；
- 结构识别算法选型（自研规则 vs 开源库，待 v0.2 评估）。
