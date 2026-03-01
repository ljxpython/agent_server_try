# 代码架构设计（当前实现）

> 本文已按当前代码更新。之前“建议目录/目标形态”与现在实现不完全一致，以下内容以仓库现状为准。

## 一眼定位：完全透传 LangGraph API 在哪里

核心透传代码现在在：`app/api/proxy/runtime_passthrough.py`

- 透传入口路由：`main.py`（`@app.api_route("/{full_path:path}", ...)`）
- 透传处理函数：`app/api/proxy/runtime_passthrough.py`（`passthrough_request`）
- 上游 URL 拼接：`app/api/proxy/runtime_passthrough.py`（`_upstream_url`）
- 请求头清洗：`app/api/proxy/runtime_passthrough.py`（`_strip_request_headers`）
- 响应头清洗：`app/api/proxy/runtime_passthrough.py`（`_strip_response_headers`）
- 上游重试/超时/网关错误映射：`app/api/proxy/runtime_passthrough.py`（`while attempt <= retries`）
- 流式转发（SSE/流响应）：`app/api/proxy/runtime_passthrough.py`（`StreamingResponse`）

如果你要找“完全透传”的最短路径，先看 `main.py` 的 catch-all 路由，再跳到 `app/api/proxy/runtime_passthrough.py`。

## 当前架构（已落地）

当前是“单入口透传 + 控制平面分模块”的形态：

### 1) 运行时透传面（Runtime Proxy）

- 主入口：`main.py`（路由） + `app/api/proxy/runtime_passthrough.py`（实现）
- 行为：
  - 全路径透传到 `LANGGRAPH_UPSTREAM_URL`
  - 保留/清洗头部，附加 `x-request-id`
  - 可选附加 `LANGGRAPH_UPSTREAM_API_KEY`
  - 失败映射为 `502/504` JSON 错误
  - 流式响应使用 `StreamingResponse`

### 2) 中间件链路（横切治理）

- 请求上下文与审计：`main.py:429`（`request_context_middleware`）
- 租户上下文：`app/middleware/tenant_context.py`
- 鉴权上下文（Keycloak）：`app/middleware/auth_context.py`
- 运行时策略检查（role / agent mapping / OpenFGA）：`main.py:114`、`main.py:141`、`main.py:249`

### 3) 控制平面 API（Platform API）

- 路由文件：`app/api/platform.py`
- 挂载点：`main.py:415`（`app.include_router(platform_router)`）
- 能力：tenant / membership / project / agent / runtime binding / audit 查询与导出

### 4) 鉴权与授权

- Keycloak JWT 验签：`app/auth/keycloak.py`
- OpenFGA 访问检查与 tuple 写入：`app/auth/openfga.py`

### 5) 数据层

- 模型：`app/db/models.py`
- 访问：`app/db/access.py`
- 会话与事务：`app/db/session.py`
- 迁移：`migrations/`

### 6) 日志系统（新增）

- 后端日志初始化：`app/logging_setup.py`
- 日志文件：`logs/backend.log`

## 当前目录（关键部分）

```text
agent_server/
  app/
    api/
      platform.py
    auth/
      keycloak.py
      openfga.py
    middleware/
      auth_context.py
      tenant_context.py
    api/proxy/
      runtime_passthrough.py
    db/
      models.py
      access.py
      session.py
    logging_setup.py
  migrations/
  main.py
  docs/
```

## 运行时请求链路（实际）

1. 请求进入 `/{full_path:path}`（`main.py`）
2. 中间件写入 `request_id` 并记录入口日志（`main.py:429`）
3. 租户上下文解析（`tenant_context.py`）
4. Keycloak token 验签并注入 user context（`auth_context.py`）
5. 运行时策略检查（role / agent / OpenFGA）
6. 转发到 LangGraph 上游（`app/api/proxy/runtime_passthrough.py`）
7. 流式或普通响应回传（`app/api/proxy/runtime_passthrough.py`）

## 为什么你会“找不到透传代码”

此前文档写的是目标分层。现在已完成第一步：透传实现已抽到 `app/api/proxy/runtime_passthrough.py`，但 `app/services/` 还未实现。

结论：

- **现在能跑的透传代码在 `app/api/proxy/runtime_passthrough.py`，入口路由仍在 `main.py`。**
- `app/services/` 仍是后续阶段再实现。

## 后续重构建议（可选）

若要提升可维护性，可按不改行为的方式逐步抽离：

1. 继续在 `app/api/proxy/` 内按职责拆分 `runtime_passthrough.py`（可拆 `header_policy/retry_policy/stream_forwarder`）
2. 下一阶段再实现 `app/services/`，把控制平面业务规则从 `app/api/platform.py` 逐步下沉
3. 每次拆分保持 `@app.api_route` 和返回语义不变，避免透传行为回归
