# 常见错误与排查手册

## 目标

记录本项目已遇到的高频报错、根因和修复动作，避免重复踩坑。

## 错误清单

### 1) Keycloak `invalid_client`

- 现象：`{"error":"invalid_client","error_description":"Invalid client or Invalid client credentials"}`
- 根因：`client_id` 不匹配，或 Client 被配置为需要 `client_secret`。
- 修复：
  - `Client authentication = Off`
  - `Direct access grants = On`
  - 确认在正确 realm（`agent-platform`）下。
- 验证：重新请求 token，返回包含 `access_token`。

### 2) Keycloak `invalid_grant` / `Account is not fully set up`

- 现象：`{"error":"invalid_grant","error_description":"Account is not fully set up"}`
- 根因：用户资料不完整或密码仍是 temporary。
- 修复：
  - 用户 `Enabled = On`
  - `Email verified = On`
  - 补齐 `email/first name/last name`
  - 密码 `Temporary = Off`
- 验证：token 请求返回 `access_token`。

### 3) `401 invalid_token`（已拿到 token）

- 现象：调用 `/info` 返回 `401 invalid_token`。
- 根因：`KEYCLOAK_AUDIENCE` 与 token 的 `aud` 不匹配。
- 修复：
  - 本地联调可先用 `KEYCLOAK_AUDIENCE=account`
  - 或在 Keycloak 配置 audience mapper，让 token 包含 `agent-proxy`
- 验证：解码 token，`aud` 包含配置值。

### 4) 浏览器打开 `8080` 进入 VSCode Web

- 现象：访问 `http://127.0.0.1:8080` 不是 Keycloak 后台。
- 根因：本机其他服务占用 8080（常见是 node/code-server）。
- 修复：Keycloak 改用 `18080:8080`。
- 验证：`http://127.0.0.1:18080` 可正常打开 Keycloak。

### 5) CORS 预检 `OPTIONS` 返回 401

- 现象：`OPTIONS /info`、`OPTIONS /threads/*` 401。
- 根因：认证/租户中间件拦截了浏览器预检请求。
- 修复：在 auth/tenant 中间件和透传策略里统一放行 `OPTIONS`。
- 验证：`OPTIONS /info` 和 `OPTIONS /threads/search` 返回 200。

### 6) 浏览器报 CORS，但后端实际是 401

- 现象：前端看到 `No 'Access-Control-Allow-Origin' header` + `401`。
- 根因：中间件早退的 `401/403` 响应未带 CORS 头。
- 修复：统一错误响应附带 `Access-Control-Allow-Origin` + `Vary: Origin`。
- 验证：401 响应头包含 `Access-Control-Allow-Origin`。

### 7) Agent Chat UI 默认不带 Bearer token

- 现象：`/info`、`/threads/search` 401。
- 根因：UI 默认传 `X-Api-Key`，后端只认 `Authorization: Bearer`。
- 修复：后端兼容 `X-Api-Key` 作为 token 来源（已实现）。
- 验证：`X-Api-Key=<access_token>` 调 `/info` 返回 200。

### 8) Next.js hydration mismatch（`imt-state` / `data-imt-p`）

- 现象：`A tree hydrated but some attributes ...`，DOM 有 `imt-*` 属性。
- 根因：浏览器扩展注入（常见翻译/输入法扩展），非后端问题。
- 修复：无痕窗口重试或禁用相关扩展。
- 验证：禁用扩展后 hydration 警告消失。

### 9) Alembic 迁移报 `relation already exists`

- 现象：`DuplicateTable: relation "tenants" already exists`。
- 根因：历史已存在同名表（例如之前 `create_all` 建过）。
- 修复：首版迁移使用兼容式 DDL（`CREATE TABLE IF NOT EXISTS` + `ALTER TABLE ... IF NOT EXISTS`）。
- 验证：`alembic upgrade head` 成功。

### 10) OpenFGA model 写入失败（union child）

- 现象：`invalid_authorization_model`，提示 union child 数量问题。
- 根因：单子项关系错误使用了 `union`。
- 修复：单关系改为 `tupleToUserset` 直接定义。
- 验证：`scripts/setup_openfga.py` 输出 store/model id。

### 11) OpenFGA 删除 tuple 报 400

- 现象：`cannot delete a tuple which does not exist`。
- 根因：删除时目标 tuple 本来就不存在。
- 修复：删除接口对该错误容忍（幂等化）。
- 验证：重复删除不再导致 500。

### 12) `auth_invalid_token` + `Invalid payload padding`

- 现象：后端日志出现 `token_source=x-api-key error=Invalid payload padding`，`/info` 返回 401。
- 根因：前端把非 JWT 值（如旧 LangSmith key）放在 `X-Api-Key`，后端在 Keycloak 模式下按 JWT 验签失败。
- 修复：
  - 前端在自动 Keycloak token 模式下，不再把非 JWT 值当 `X-Api-Key` 发送。
  - 若是 JWT，则优先走 `Authorization: Bearer <token>`。
  - `ThreadProvider` 在自动模式下忽略非 JWT 的本地缓存 key。
- 验证：
  - `/info` 不再出现 `Invalid payload padding`。
  - `/threads/search` 与运行时请求保持 200（或明确的权限状态码）。

## 快速排查顺序（推荐）

1. 先看后端状态码是否为 401/403（鉴权问题优先）。
2. 再看响应头是否有 `Access-Control-Allow-Origin`（排 CORS 伪报错）。
3. 再看 token 本身：是否存在、是否过期、`aud/iss` 是否匹配。
4. 最后看 OpenFGA：store/model 是否配置正确、tuple 是否已同步。
