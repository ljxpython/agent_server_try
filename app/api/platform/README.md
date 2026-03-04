# Platform API README

## 这块代码在干什么

`app/api/platform` 是控制平面（Control Plane）API 的路由层，统一挂载在 `/_platform/*`。

它的职责是：

- 提供租户、成员、项目、助手、审计等平台管理接口。
- 在路由层做参数约束、分页参数处理、响应模型映射。
- 把业务逻辑下沉到 `app/services/*`，自身尽量保持薄路由。

当前路由聚合入口：`app/api/platform/__init__.py`。


## 目录与职责

- `app/api/platform/__init__.py`: 平台路由聚合（prefix `/_platform`）
- `app/api/platform/tenants.py`: 租户与 membership 路由
- `app/api/platform/projects.py`: 项目路由
- `app/api/platform/assistants.py`: assistant 路由
- `app/api/platform/audit.py`: 审计查询/统计/导出路由
- `app/api/platform/schemas.py`: 平台 API 请求/响应模型
- `app/api/platform/common.py`: 平台路由共用 logger 与 request_id helper


## 后端调用链路

### 全局链路（请求进入后）

1. App 组装：`app/factory.py`
2. 注册 `platform_router`：`app/factory.py`
3. 请求进入 `/_platform/*` 路由：`app/api/platform/*`
4. 路由调用 service：`app/services/platform_service.py`（导出门面）
5. 具体 service 执行业务与权限：`app/services/*_service.py`
6. DB 访问：`app/db/access.py` + 事务：`app/db/session.py`
7. 可选 OpenFGA 同步：`app/services/platform_common.py` + `app/auth/openfga.py`

### 按域链路

- Tenants/Memberships
  - Router: `app/api/platform/tenants.py`
  - Service: `app/services/tenant_service.py`, `app/services/membership_service.py`
  - DB: `create_tenant`, `list_tenants_for_user`, `create_or_update_membership`, `delete_membership`
  - 权限: `current_user_id_from_request`, `require_tenant_admin`（`platform_common.py`）

- Projects
  - Router: `app/api/platform/projects.py`
  - Service: `app/services/project_service.py`
  - DB: `list_projects_for_tenant`, `create_project`, `update_project`, `delete_project`
  - 权限: `require_tenant_membership`（读）, `require_tenant_admin`（写）

- Assistants
  - Router: `app/api/platform/assistants.py`
  - Service: `app/services/agent_service.py`
  - DB: `list_agents_for_project`, `create_agent`, `update_agent`, `delete_agent`
  - 上游联动: `LangGraphAssistantsService`（创建/更新/删除 assistant 时同步 LangGraph）
  - 权限: `require_tenant_membership`（读）, `require_tenant_admin`（写）

- Audit
  - Router: `app/api/platform/audit.py`
  - Service: `app/services/audit_service.py`
  - DB: `list_audit_logs`, `aggregate_audit_logs`
  - 权限: 全部要求 `require_tenant_admin`


## 接口清单与前端使用情况

说明：这里的“已使用/未观测到”仅基于当前仓库 `agent-chat-ui/src` 的代码检索结果。

### Tenants/Memberships

- `GET /_platform/tenants` -> 已使用
  - 调用方: `agent-chat-ui/src/providers/WorkspaceContext.tsx` -> `agent-chat-ui/src/lib/platform-api/tenants.ts`

- `POST /_platform/tenants` -> 前端未观测到
- `GET /_platform/tenants/{tenant_ref}/memberships` -> 已使用
  - 调用方: `agent-chat-ui/src/app/workspace/tenants/[tenantRef]/members/page.tsx`
- `POST /_platform/tenants/{tenant_ref}/memberships` -> 已使用
  - 调用方: `agent-chat-ui/src/app/workspace/tenants/[tenantRef]/members/page.tsx`
- `DELETE /_platform/tenants/{tenant_ref}/memberships/{user_ref}` -> 已使用
  - 调用方: `agent-chat-ui/src/app/workspace/tenants/[tenantRef]/members/page.tsx`

### Projects

- `GET /_platform/tenants/{tenant_ref}/projects` -> 已使用
  - 调用方: `agent-chat-ui/src/providers/WorkspaceContext.tsx`, `agent-chat-ui/src/app/workspace/projects/page.tsx`
  - 封装: `agent-chat-ui/src/lib/platform-api/projects.ts`

- `POST /_platform/projects` -> 已使用
  - 调用方: `agent-chat-ui/src/app/workspace/projects/page.tsx`

- `PATCH /_platform/projects/{project_id}` -> 已使用
  - 调用方: `agent-chat-ui/src/app/workspace/projects/page.tsx`

- `DELETE /_platform/projects/{project_id}` -> 已使用
  - 调用方: `agent-chat-ui/src/app/workspace/projects/page.tsx`

### Assistants

- `GET /_platform/projects/{project_id}/assistants` -> 已使用
  - 调用方: `agent-chat-ui/src/app/workspace/agents/page.tsx`, `agent-chat-ui/src/providers/Stream.tsx`
  - 封装: `agent-chat-ui/src/lib/platform-api/assistants.ts`

- `POST /_platform/assistants` -> 已使用
  - 调用方: `agent-chat-ui/src/app/workspace/agents/page.tsx`

- `PATCH /_platform/assistants/{assistant_id}` -> 已使用
  - 调用方: `agent-chat-ui/src/app/workspace/agents/page.tsx`

- `DELETE /_platform/assistants/{assistant_id}` -> 已使用
  - 调用方: `agent-chat-ui/src/app/workspace/agents/page.tsx`

### Audit

- `GET /_platform/tenants/{tenant_ref}/audit-logs` -> 已使用
  - 调用方: `agent-chat-ui/src/app/workspace/audit/page.tsx`
  - 封装: `agent-chat-ui/src/lib/platform-api/audit.ts`

- `GET /_platform/tenants/{tenant_ref}/audit-logs/stats` -> 已使用
  - 调用方: `agent-chat-ui/src/app/workspace/stats/page.tsx`
  - 封装: `agent-chat-ui/src/lib/platform-api/stats.ts`

- `GET /_platform/tenants/{tenant_ref}/audit-logs/export` -> 已使用
  - 调用方: `agent-chat-ui/src/app/workspace/audit/page.tsx`


## 前端调用逻辑（从页面到后端）

当前前端对 `/_platform` 的调用路径是：

1. 页面或 Provider 发起业务调用
   - 例如 `workspace/projects/page.tsx` 调用 `createProject`。
2. 进入 `agent-chat-ui/src/lib/platform-api/*.ts` 封装函数
   - 负责拼路径、分页参数、请求体。
3. 统一走 `PlatformApiClient`
   - 文件: `agent-chat-ui/src/lib/platform-api/client.ts`
   - 通过 `fetch(${baseUrl}${path})` 发送请求。
   - 自动附带 `Authorization: Bearer <jwt>` 或 `X-Api-Key`。
4. 后端 `app/factory.py` 注册的 `platform_router` 接收
5. 路由转 service，再到 DB/OpenFGA，返回 JSON（或 CSV）。


## 结论（回答你的核心问题）

- `app/api/platform` 中的接口并不是每个都被前端页面使用。
- 当前前端主路径已覆盖：租户读取、项目 CRUD、助手 CRUD、审计查询/统计/导出。
- 当前前端未覆盖：租户创建、membership 管理。
