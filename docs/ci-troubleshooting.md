# CI 失败诊断（smoke-e2e）

## 工作流

- 名称：`smoke-e2e`
- 文件：`.github/workflows/smoke-e2e.yml`

## 快速定位顺序

1. 看失败步骤（Install / DB migration / Keycloak / OpenFGA / smoke script）
2. 看失败前最后 100 行日志
3. 对照下方常见错误与处理方式

## 常见失败与处理

### 1) PostgreSQL 启动超时 / migration 失败

- 现象：`pg_isready` 长时间失败，或 `alembic upgrade head` 失败
- 处理：
  - 检查 `DATABASE_URL` 与容器端口是否一致
  - 本地复现：`uv run alembic upgrade head`

### 2) Keycloak 未就绪 / token 获取失败

- 现象：无法访问 well-known，或 `invalid_client` / `invalid_grant`
- 处理：
  - 确认 realm/client/user 创建命令执行成功
  - 确认用户密码不是 temporary，资料完整

### 3) OpenFGA 初始化失败

- 现象：`setup_openfga.py` 报 store/model 错误
- 处理：
  - 检查 `OPENFGA_URL` 可达
  - 本地执行：`PYTHONPATH=. OPENFGA_URL=http://127.0.0.1:18081 uv run python scripts/setup_openfga.py`

### 4) smoke_e2e 失败

- 现象：`scripts/smoke_e2e.py` 中断
- 处理：
  - 本地按 CI 同参数运行一次
  - 对照 `docs/testing.md` 和 `docs/error-playbook.md`

## 本地复现 CI（推荐）

```bash
uv sync
uv run alembic upgrade head
uv run python scripts/smoke_e2e.py
```

## 何时重跑 CI

- 临时网络或容器拉取波动导致失败
- 无代码变更的基础设施抖动

如果是确定性失败（同一步稳定失败），先修复再重跑。
