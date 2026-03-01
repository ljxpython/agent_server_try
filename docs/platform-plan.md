# 平台规划

## 目标

在不重写 LangGraph 运行时协议的前提下，构建多租户 AI 平台能力（租户、项目、智能体管理、权限与治理）。

## 分层架构

- 运行时平面（Runtime Plane）：LangGraph 负责 `threads/runs/stream/checkpoints`。
- 控制平面（Control Plane）：当前 FastAPI 代理负责鉴权、租户、项目、策略、审计、配额。
- 数据平面（Data Plane）：PostgreSQL 保存平台核心元数据与审计数据。

## 设计原则

- 代理边界保持 LangGraph API 兼容，不破坏 `agent-chat-ui` 调用方式。
- 平台能力通过控制平面叠加，不侵入运行时协议。
- 优先使用成熟开源组件，避免重复造轮子。

## 推荐开源组件

- 身份与单点登录：Keycloak（OIDC/SAML）
- 细粒度授权：OpenFGA（关系模型授权）
- 网关与限流：Kong 或 Traefik
- 观测与指标：OpenTelemetry + Prometheus + Grafana（可选 Langfuse）

## 分阶段计划

### 第一阶段：透传基础能力（已完成）

- 全路径透明透传。
- SSE 流式透传。
- `.env` 配置化上游地址。
- 请求 ID、结构化日志、错误分类（502/504）。

### 第二阶段：身份与租户模型（进行中）

- 接入 IdP（Keycloak）。
- 增加租户感知中间件。
- 建立核心表：`users/tenants/memberships`。

### 第三阶段：项目与智能体管理（进行中）

- 增加表：`projects/agents/runtime_bindings`。
- 平台智能体 ID 与 `assistant_id/graph_id` 做映射。
- 提供项目与智能体管理 API。

### 第四阶段：权限与治理

- 接入 OpenFGA 鉴权检查。
- 增加配额、限流、审计日志。

### 第五阶段：交付与运营

- 环境发布流（dev/staging/prod）。
- 版本发布与回滚元数据。
- 成本归因看板（租户/项目/智能体）。

### 第六阶段：前端平台化改造（规划完成）

- 基于 `agent-chat-ui` 进行渐进改造，不做重写。
- 拆分平台壳与聊天壳：`租户/项目` 上下文前置到全局。
- 新增平台页面：`agents/runtime-bindings/audit/stats/export/settings`。
- 统一平台 API 封装层（BFF-lite 转发 + 错误/分页规范）。
- 已完成第一条关键链路：运行时请求自动注入 `x-tenant-id` / `x-project-id`。
- 详见：`docs/frontend-platform-plan.md`。

## PostgreSQL 核心表（初版）

- `tenants(id, name, slug, status, created_at)`
- `users(id, external_subject, email, created_at)`
- `memberships(id, tenant_id, user_id, role, created_at)`
- `projects(id, tenant_id, name, created_at)`
- `agents(id, project_id, name, graph_id, runtime_base_url, description, created_at)`
- `runtime_bindings(id, agent_id, environment, langgraph_assistant_id, langgraph_graph_id, runtime_base_url, created_at)`
- `audit_logs(id, tenant_id, project_id, actor_id, action, resource_type, resource_id, metadata_json, created_at)`

## 当前里程碑结论

第二至第四阶段核心后端能力已完成并可用，已进入前端平台化改造阶段。
