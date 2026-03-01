# PostgreSQL 容器运行手册

## 目标

提供可直接执行的 PostgreSQL Docker 方案，支持：启动、停止、备份、恢复、迁移。

## 一次性创建并启动容器

```bash
docker run -d \
  --name agent-platform-pg \
  -e POSTGRES_USER=agent \
  -e POSTGRES_PASSWORD=agent_pwd \
  -e POSTGRES_DB=agent_platform \
  -p 5432:5432 \
  -v agent_platform_pgdata:/var/lib/postgresql/data \
  -v $(pwd)/backups:/backups \
  postgres:16
```

或使用你当前目录无关的备份路径（推荐）：

```bash
docker run -d \
  --name agent-platform-pg \
  -e POSTGRES_USER=agent \
  -e POSTGRES_PASSWORD=agent_pwd \
  -e POSTGRES_DB=agent_platform \
  -p 5432:5432 \
  -v agent_platform_pgdata:/var/lib/postgresql/data \
  -v "$HOME/pg_data/backups":/backups \
  postgres:16
```

说明：
- `agent_platform_pgdata` 是持久化卷，容器重建数据不丢。
- `$(pwd)/backups` 挂载到容器 `/backups`，用于导出备份文件。

## 启动与停止

```bash
# 启动
docker start agent-platform-pg

# 停止
docker stop agent-platform-pg

# 重启
docker restart agent-platform-pg

# 查看日志
docker logs -f agent-platform-pg
```

## 连接测试

```bash
docker exec -it agent-platform-pg psql -U agent -d agent_platform -c "SELECT version();"
```

## 备份（逻辑备份）

```bash
docker exec agent-platform-pg \
  pg_dump -U agent -d agent_platform -F c -f /backups/agent_platform_$(date +%F_%H%M%S).dump
```

说明：
- `-F c` 为自定义格式，适合 `pg_restore`。
- 备份文件会出现在宿主机 `./backups` 目录。

## 恢复（从 dump 恢复）

```bash
# 先清空并重建 public schema（谨慎执行）
docker exec agent-platform-pg psql -U agent -d agent_platform -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"

# 执行恢复
docker exec agent-platform-pg \
  pg_restore -U agent -d agent_platform /backups/<your_dump_file>.dump
```

## 迁移方案（Alembic）

推荐在应用侧执行迁移，不直接手工改表。

```bash
# 安装（若后续引入）
uv add alembic sqlalchemy psycopg[binary]

# 初始化迁移目录（只执行一次）
uv run alembic init migrations

# 设置连接串（示例）
export DATABASE_URL="postgresql+psycopg://agent:agent_pwd@127.0.0.1:5432/agent_platform"

# 生成迁移文件
uv run alembic revision -m "create core platform tables"

# 执行迁移
uv run alembic upgrade head

# 回滚一步
uv run alembic downgrade -1
```

## 建议的最小运维策略

- 每天至少一次逻辑备份，保留最近 7 天。
- 每次迁移前先执行一次手动备份。
- 所有 schema 变更必须走迁移脚本，禁止手工直改生产库。

## RBAC 回滚脚本（Step 2）

当租户成员角色配置错误时，可用脚本直接回滚：

```bash
PLATFORM_DB_ENABLED=true \
DATABASE_URL="postgresql+psycopg://agent:agent_pwd@127.0.0.1:5432/agent_platform" \
uv run python scripts/rbac_membership_rollback.py \
  --tenant-ref <tenant-slug-or-id> \
  --user-ref <user-id-or-external-subject> \
  --target-role member \
  --sync-openfga
```

参数说明：

- `--target-role owner|admin|member|none`
- `none` 表示删除 membership
- `--sync-openfga` 会同步回滚 OpenFGA tenant 角色 tuple
