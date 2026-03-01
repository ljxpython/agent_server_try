# 服务器迁移手册（PostgreSQL + Keycloak + OpenFGA）

## 目标

把本地已跑通的平台能力迁移到服务器，并尽量做到：

- 迁移后业务数据可直接用（租户/项目/智能体/审计不丢）
- 认证与授权可直接用（Keycloak + OpenFGA）
- 除必要环境差异（域名、端口、证书）外，不需要重复手工配置

---

## 迁移策略（推荐顺序）

1. 先迁 PostgreSQL（业务主数据）。
2. 再迁 Keycloak（Realm/Client/User）。
3. 再迁 OpenFGA（模型 + tuple）。
4. 最后切换代理服务 `.env` 并做冒烟验证。

> 关键原则：**ID 稳定优先**。如果 tenant/project/agent/user subject 不变，迁移会最省心。

---

## 一次性准备（现在就做，未来最省事）

### 1) 固化关键命名

- Keycloak Realm：`agent-platform`
- Keycloak Client：`agent-proxy`
- OpenFGA 模型文件：`config/openfga-models/v1.json`

不要随意改这些标识，后续迁移和回放会更稳定。

### 2) 保留一份“生产环境模板”

建议新增并长期维护：

- `.env.server.template`（仅模板，不放密钥）
- 迁移时只替换：域名、端口、密码、证书路径

### 3) 明确哪些是“必须手工”的

- 域名与 TLS 证书
- 服务器防火墙/安全组
- DNS 切换

其余（数据库恢复、模型写入、应用迁移）可脚本化。

---

## 第 0 步：迁移前冻结窗口

在切换窗口内，暂停写操作（至少暂停平台管理写操作），避免导出期间数据继续变化。

---

## 第 1 步：导出本地数据

## 1.1 导出 PostgreSQL（强制）

使用 `docs/postgres-operations.md` 的逻辑备份流程：

```bash
docker exec agent-platform-pg \
  pg_dump -U agent -d agent_platform -F c -f /backups/agent_platform_migrate.dump
```

导出后把 dump 文件拷贝到服务器。

## 1.2 导出 Keycloak（推荐强制）

你有两种方式：

- 方式 A（推荐）：Keycloak 后台导出 Realm（包含 client/roles/users）
- 方式 B：在容器内用 `kc.sh export` 导出到文件

目标产物：`realm-agent-platform.json`

> 注意：如果只迁移配置不迁移用户，你之后仍需手动创建用户。

## 1.3 记录 OpenFGA 当前状态（最少记录）

记录当前 `.env`：

- `OPENFGA_URL`
- `OPENFGA_STORE_ID`
- `OPENFGA_MODEL_ID`
- `OPENFGA_MODEL_FILE`

以及当前模型文件版本（默认 `config/openfga-models/v1.json`）。

---

## 第 2 步：部署服务器基础组件

## 2.1 PostgreSQL

- 启动服务器 PostgreSQL（推荐独立实例/托管服务）
- 创建目标库
- 恢复 dump：

```bash
pg_restore -U <user> -d <db_name> /path/to/agent_platform_migrate.dump
```

然后执行：

```bash
uv run alembic upgrade head
```

保证目标库 schema 与当前代码一致。

## 2.2 Keycloak

- 服务器启动 Keycloak（生产建议接 PostgreSQL，不用内置 H2）
- 导入 `realm-agent-platform.json`
- 检查：
  - Realm = `agent-platform`
  - Client = `agent-proxy`
  - audience 配置仍满足当前服务端配置

## 2.3 OpenFGA

- 生产建议 OpenFGA 使用 PostgreSQL datastore（避免内存/临时存储）
- 确保 OpenFGA 服务可达

---

## 第 3 步：迁移 OpenFGA 数据（模型 + tuple）

OpenFGA 有两种迁移路径：

### 路径 A（最佳）：连 OpenFGA 的底层持久化库一起迁移

- 优点：store/model/tuple 全保留，几乎零额外动作。
- 结果：可继续使用原 `OPENFGA_STORE_ID` / `OPENFGA_MODEL_ID`。

### 路径 B（常见）：只在新 OpenFGA 上重建模型

1. 在服务器写入模型并拿到新的 store/model id：

```bash
PYTHONPATH=. OPENFGA_URL=http://<server-openfga-host>:<port> \
OPENFGA_MODEL_FILE=config/openfga-models/v1.json \
uv run python scripts/setup_openfga.py
```

2. 把输出写入服务器 `.env`：

- `OPENFGA_STORE_ID=<new-store-id>`
- `OPENFGA_MODEL_ID=<new-model-id>`

3. 回填 tuple（必须）

当前代码会在“新增/删除”时同步 tuple，但**历史数据不会自动回填**。
因此路径 B 需要执行一次全量回填（脚本化或一次性批处理）。

回填关系最小集合：

- `user:<subject> --(owner/admin/member)--> tenant:<tenant_id>`
- `tenant:<tenant_id> --(tenant)--> project:<project_id>`
- `project:<project_id> --(project)--> agent:<agent_id>`

---

## 第 4 步：切换应用配置（服务器 `.env`）

重点确认：

```env
DATABASE_URL=postgresql+psycopg://<user>:<pwd>@<host>:5432/<db>

KEYCLOAK_AUTH_ENABLED=true
KEYCLOAK_AUTH_REQUIRED=true
KEYCLOAK_ISSUER=https://<your-keycloak-host>/realms/agent-platform
KEYCLOAK_AUDIENCE=agent-proxy
KEYCLOAK_JWKS_URL=

OPENFGA_ENABLED=true
OPENFGA_AUTHZ_ENABLED=true
OPENFGA_URL=http://<your-openfga-host>:8080
OPENFGA_STORE_ID=<id>
OPENFGA_MODEL_ID=<id>
OPENFGA_MODEL_FILE=config/openfga-models/v1.json
```

修改后重启服务。

---

## 第 5 步：迁移后验收（必须全通过）

1. 健康检查：`/_proxy/health` 返回 `200`
2. Keycloak：拿 token 后请求 `/info` 返回 `200`
3. 平台数据：能读到既有 tenant/project/agent
4. OpenFGA：
   - member 读请求通过
   - member 写请求被 `403`
5. 冒烟脚本：运行 `scripts/smoke_e2e.py`

---

## 最小停机切换方案（推荐）

1. 旧环境只读（冻结写）
2. 导出 PG + Keycloak
3. 服务器导入并启动
4. 完成 OpenFGA 模型/tuple 就绪
5. 执行冒烟
6. 切 DNS/网关到新环境

---

## 回滚预案（必须提前准备）

- 保留切换前 PostgreSQL dump
- 保留 Keycloak realm 导出文件
- 保留旧环境运行至少 24h（不立刻销毁）
- 新环境失败时，DNS/网关回指旧环境

---

## 你未来“几乎不用重新配置”的关键条件

只要满足以下 4 条，迁移就接近一次完成：

1. Keycloak realm/client 命名保持不变
2. PostgreSQL 主数据完整恢复
3. OpenFGA tuple 也完成迁移（或已全量回填）
4. `.env.server.template` 只改主机与密钥，不改业务标识

否则就会出现“服务起来了但权限不对/用户失效/数据不一致”的情况。
