# OpenFGA 集成说明

## 作用

OpenFGA 用于资源级授权，把“谁可以对哪个 tenant/project/agent 做什么操作”从代码里抽离出来。

## 本地启动

```bash
docker rm -f agent-openfga 2>/dev/null || true
docker run -d \
  --name agent-openfga \
  -p 18081:8080 \
  openfga/openfga:latest \
  run
```

## 初始化 store 和 model

```bash
PYTHONPATH=. OPENFGA_URL=http://127.0.0.1:18081 uv run python scripts/setup_openfga.py
```

输出示例：

```text
OPENFGA_STORE_ID=01J...
OPENFGA_MODEL_ID=01J...
```

把这两个值写入 `.env`。

## `.env` 配置

```env
OPENFGA_ENABLED=true
OPENFGA_AUTHZ_ENABLED=true
OPENFGA_AUTO_BOOTSTRAP=false
OPENFGA_URL=http://127.0.0.1:18081
OPENFGA_STORE_ID=<store-id>
OPENFGA_MODEL_ID=<model-id>
```

## 已接入逻辑

- 创建租户/成员变更时，同步 tenant 角色 tuple（`owner/admin/member`）。
- 删除成员时，回收 tenant 角色 tuple。
- 创建项目时，同步 `project -> tenant` 关系。
- 删除项目时，回收 `project -> tenant` 关系及其下 agent 关系。
- 创建智能体时，同步 `agent -> project` 关系。
- 删除智能体时，回收 `agent -> project` 关系。
- 透传请求在带 `x-tenant-id` 时，按方法映射 `can_read/can_write` 做 `check`。
- 透传请求带 `x-agent-id` 时，增加 `agent` 级别 `check` 与 agent-tenant 映射一致性校验。

## 联调验证

1. 使用 owner 用户创建 tenant/project/agent。
2. 使用 member 用户调用读接口应通过。
3. member 写透传请求在策略开启时应被 `403` 拦截。
