# Keycloak 集成说明（一次性通过版）

## 目标

用最少步骤完成本地联调：拿到 Keycloak token，并成功调用 `http://127.0.0.1:2024/info` 返回 `200`。

## 前置约定（关键）

- Keycloak 端口固定用 `18080`（避免与本机 8080 冲突）
- `KEYCLOAK_AUDIENCE` 本地联调用 `account`（避免 `aud` 不匹配）
- 用户必须有：`email`、`first name`、`last name`，且 `Temporary password` 关闭

## 一次性流程

### 1) 启动 Keycloak

```bash
docker rm -f agent-keycloak 2>/dev/null || true
docker run -d \
  --name agent-keycloak \
  -p 18080:8080 \
  -e KEYCLOAK_ADMIN=admin \
  -e KEYCLOAK_ADMIN_PASSWORD=admin123 \
  quay.io/keycloak/keycloak:26.0 \
  start-dev
```

后台地址：`http://127.0.0.1:18080`

### 2) Keycloak 后台配置

1. 登录 `admin/admin123`
2. 创建 Realm：`agent-platform`
3. 创建 Client：`agent-proxy`
4. Client 设置：
   - `Client authentication = Off`
   - `Direct access grants = On`
5. 创建用户 `demo_user`
6. 用户字段必须补齐：
   - `Email = demo_user@example.com`
   - `First name = Demo`
   - `Last name = User`
   - `Enabled = On`
   - `Email verified = On`
7. 用户密码：`Demo@123456`，且 `Temporary = Off`

> 如果你看到 `Account is not fully set up`，99% 是第 6/7 步没配完整。

### 3) 配置项目 `.env`

```env
KEYCLOAK_AUTH_ENABLED=true
KEYCLOAK_AUTH_REQUIRED=true
KEYCLOAK_ISSUER=http://127.0.0.1:18080/realms/agent-platform
KEYCLOAK_AUDIENCE=account
KEYCLOAK_JWKS_URL=
KEYCLOAK_JWKS_CACHE_TTL_SECONDS=300
```

### 4) 启动代理服务

```bash
uv run uvicorn main:app --host 0.0.0.0 --port 2024 --reload
```

### 5) 验证未登录拦截

```bash
curl -i http://127.0.0.1:2024/info
```

预期：`401`，并带 `WWW-Authenticate: Bearer`

### 6) 获取 token（推荐先看原始响应，再提取）

```bash
RESP=$(curl -sS \
  -X POST "http://127.0.0.1:18080/realms/agent-platform/protocol/openid-connect/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=password" \
  -d "client_id=agent-proxy" \
  -d "username=demo_user" \
  -d "password=Demo@123456")

echo "$RESP"

TOKEN=$(echo "$RESP" | python3 -c 'import sys,json; obj=json.load(sys.stdin); print(obj.get("access_token",""))')

echo "TOKEN_LENGTH=${#TOKEN}"
```

> 注意变量名是 `TOKEN`，不是 `TTOKEN`。

### 7) 带 token 调用

```bash
curl -i -H "Authorization: Bearer $TOKEN" http://127.0.0.1:2024/info
```

预期：`200`，响应头包含 `x-user-subject`

## 重要：两条“必须重做”

1. 你修改了 Keycloak 的 Audience Mapper 后，**必须重新获取一枚新 token**（旧 token 不会自动更新 `aud`）。
2. 你修改了 `.env`（如 `KEYCLOAK_AUDIENCE`）后，**必须重启 FastAPI 服务**（热更新不保证重载环境变量）。

## 典型错误对照

- `invalid_client`
  - client 没设成 public，或 `client_id` 错，或 realm 用错
- `invalid_grant: Account is not fully set up`
  - 用户资料不完整（email/first/last）或密码仍是 temporary
- `401 invalid_token`（调用代理时）
  - `KEYCLOAK_ISSUER` 或 `KEYCLOAK_AUDIENCE` 不匹配（本地先用 `account`）

## 把 token 的受众配置为 `agent-proxy`（生产推荐）

当你准备把 `.env` 切回 `KEYCLOAK_AUDIENCE=agent-proxy` 时，先在 Keycloak 配置 audience mapper。

### UI 操作步骤

1. 进入 Realm：`agent-platform`
2. `Client scopes` -> `Create client scope`
   - Name: `agent-proxy-audience`
   - Type: `Default`
   - Protocol: `openid-connect`
3. 进入该 scope -> `Mappers` -> `Add mapper` -> 选择 `Audience`
   - Name: `aud-agent-proxy`
   - Included Client Audience: `agent-proxy`
   - Add to access token: `ON`
   - Add to ID token: `OFF`（可选）
4. 进入 `Clients` -> `agent-proxy` -> `Client scopes`
   - 把 `agent-proxy-audience` 加到 `Assigned default client scopes`
5. 重新获取新 token（旧 token 不会自动更新 `aud`）

### 验证 `aud` 是否包含 `agent-proxy`

```bash
curl -sS \
  -X POST "http://127.0.0.1:18080/realms/agent-platform/protocol/openid-connect/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=password" \
  -d "client_id=agent-proxy" \
  -d "username=demo_user" \
  -d "password=Demo@123456" | \
python3 -c 'import sys,json,base64; obj=json.load(sys.stdin); tok=obj.get("access_token",""); p=tok.split(".")[1]; p += "=" * (-len(p)%4); payload=json.loads(base64.urlsafe_b64decode(p)); print("aud=", payload.get("aud"))'
```

预期输出包含：`agent-proxy`。

## 端口冲突排查

如果打开浏览器出现 VSCode Web，而不是 Keycloak：

```bash
lsof -i :8080 -n -P
docker ps --format "table {{.Names}}\t{{.Ports}}"
```

保持 Keycloak 在 `18080` 即可规避。
