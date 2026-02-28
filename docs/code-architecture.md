# 代码架构设计（当前到目标）

## 当前状态

当前后端核心逻辑集中在 `main.py`，属于单文件透传实现，优点是上线快、链路短；缺点是后续扩展（鉴权、租户、项目）会变得难维护。

## 目标架构

采用“控制平面 + 运行时代理”的分层设计，保证透传能力不退化。

### 1) API 层（HTTP 接入）

- 职责：路由、请求/响应模型、参数校验。
- 位置建议：`app/api/`。

### 2) 中间件层（横切能力）

- 职责：请求 ID、日志、鉴权、租户上下文、限流。
- 位置建议：`app/middleware/`。

### 3) 代理层（LangGraph 透传）

- 职责：上游 URL 拼接、头部清洗、流式转发、错误映射。
- 位置建议：`app/proxy/`。

### 4) 领域服务层（控制平面）

- 职责：租户、项目、智能体、授权策略等业务规则。
- 位置建议：`app/services/`。

### 5) 数据访问层（PostgreSQL）

- 职责：ORM 模型、仓储、事务边界。
- 位置建议：`app/db/`、`migrations/`。

## 推荐目录结构

```text
agent_server/
  app/
    api/
      proxy_routes.py
      health_routes.py
    middleware/
      request_id.py
      access_log.py
      auth_context.py
    proxy/
      upstream_client.py
      header_policy.py
      stream_forwarder.py
      error_mapping.py
    services/
      tenants.py
      projects.py
      agents.py
      authorization.py
    db/
      models.py
      session.py
      repositories/
  migrations/
  main.py
```

## 演进策略（不影响当前可用性）

1. 保持 `main.py` 的对外行为不变（继续全路径透传）。
2. 按层逐步抽离：先抽 `proxy/`，再抽 `middleware/`。
3. 第二阶段再引入 `services/ + db/`，避免一次性重构风险。

## 第二阶段启动条件（冻结前提）

- PostgreSQL 容器运行与备份流程已验证。
- 目录结构评审通过。
- 鉴权方案（Keycloak/OpenFGA）已确认。
