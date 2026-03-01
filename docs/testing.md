# 测试与冒烟验证

[![smoke-e2e](https://github.com/ljxpython/agent_server_try/actions/workflows/smoke-e2e.yml/badge.svg)](https://github.com/ljxpython/agent_server_try/actions/workflows/smoke-e2e.yml)

工作流状态页：`https://github.com/ljxpython/agent_server_try/actions/workflows/smoke-e2e.yml`

## 端到端 Smoke

脚本：`scripts/smoke_e2e.py`

覆盖范围：

- CORS 预检与 401 响应头
- Keycloak 鉴权
- 租户/项目/智能体创建
- OpenFGA 授权与 tuple 回收
- 透传 runtime 读写策略
- 审计日志查询

## 运行命令

```bash
PLATFORM_DB_ENABLED=true \
KEYCLOAK_AUTH_ENABLED=true \
KEYCLOAK_AUTH_REQUIRED=true \
KEYCLOAK_ISSUER=http://127.0.0.1:18080/realms/agent-platform \
KEYCLOAK_AUDIENCE=agent-proxy \
OPENFGA_ENABLED=true \
OPENFGA_AUTHZ_ENABLED=true \
OPENFGA_AUTO_BOOTSTRAP=false \
OPENFGA_URL=http://127.0.0.1:18081 \
OPENFGA_STORE_ID=01KJHRWEE4PEZ943TT56NGYTK8 \
OPENFGA_MODEL_ID=01KJHRWEEDAYED9JKPCE66KSS1 \
DATABASE_URL="postgresql+psycopg://agent:agent_pwd@127.0.0.1:5432/agent_platform" \
RUNTIME_ROLE_ENFORCEMENT_ENABLED=true \
uv run python scripts/smoke_e2e.py
```

成功输出：`PASS: smoke_e2e`

## CI 接入

已提供 GitHub Actions 工作流：`.github/workflows/smoke-e2e.yml`

触发条件：

- Push 到 `main/master`
- Pull Request

CI 会自动完成：

1. 启动 PostgreSQL 并执行 Alembic 迁移
2. 启动 Keycloak 并创建 realm/client/test users
3. 启动 OpenFGA 并初始化 store/model
4. 执行 `scripts/smoke_e2e.py`

## CI 失败诊断

详见：`docs/ci-troubleshooting.md`

## 跨环境模板

已提供模板：

- `config/environments/.env.dev.example`
- `config/environments/.env.staging.example`
- `config/environments/.env.prod.example`
