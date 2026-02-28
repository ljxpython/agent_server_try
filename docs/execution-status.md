# 执行状态

## 当前焦点

第三阶段：项目与智能体管理（进行中）

## 总体进度

- 阶段1（透传基础）：100%
- 阶段2（身份与租户）：100%
- 阶段3（项目/智能体/审计/OpenFGA）：95%
- 阶段4（高级治理与自动化测试）：20%

## 状态看板

- [x] FastAPI 全路径透明透传
- [x] SSE 流式透传
- [x] `.env` 上游配置
- [x] 请求 ID 透传与结构化日志
- [x] 上游超时/传输错误分类（504/502）
- [x] 基础契约冒烟验证（`/_proxy/health`、`/info`）

## 暂缓项

- [x] Keycloak 对接（JWT 验签）
- [x] OpenFGA 集成

## 第二阶段已完成项（本轮）

1. 新增数据库模型骨架：`tenants/users/memberships`。
2. 新增数据库会话与建表入口（可通过开关控制启用）。
3. 新增租户上下文中间件骨架（`x-tenant-id` / `x-user-id`）。
4. 完成中间件开关验证：`REQUIRE_TENANT_CONTEXT=true` 时无租户头返回 `400`。
5. 新增 Keycloak JWT 验签中间件骨架（JWKS、issuer/audience、401/502 映射）。
6. 完成 Keycloak 本地联调并跑通 `agent-proxy` audience。
7. 新增 `sub -> users.external_subject` 自动入库。
8. 新增 Alembic 迁移框架与首版迁移（`20260228_0001`）。
9. 新增租户成员校验：有 `x-tenant-id` 且无 membership 时返回 `403`。
10. 新增平台管理 API：创建租户、查询租户、管理成员（owner/admin）。
11. 新增项目与智能体管理 API：projects/agents/runtime_bindings。
12. 新增角色权限矩阵：`owner/admin` 写、`member` 只读。
13. 新增 Alembic 迁移 `20260228_0002`：runtime_bindings 表与索引。
14. 新增审计日志模型与迁移 `20260228_0003`：`audit_logs`。
15. 新增统一请求审计：平台 API 与透传请求均写入 `audit_logs`。
16. 新增审计查询 API：`GET /_platform/tenants/{tenant_ref}/audit-logs`（owner/admin）。
17. 列表接口统一分页/排序：`limit/offset/sort_by/sort_order` + `x-total-count`。
18. 新增透传细粒度策略开关：`RUNTIME_ROLE_ENFORCEMENT_ENABLED`。
19. 新增 OpenFGA 集成骨架：模型文件、初始化脚本、tuple 同步、透传 check 接入。
20. 新增 OpenFGA tuple 回收：删除成员/项目/智能体时同步删除关系。
21. 新增透传 `x-agent-id` 资源映射校验与 agent 级 OpenFGA check。
22. 新增端到端自动化冒烟脚本：`scripts/smoke_e2e.py`。
23. 新增 GitHub Actions CI：`.github/workflows/smoke-e2e.yml`。

## 下一步

1. 增加审计查询 API 的聚合统计（按路径/状态码/用户）。
2. 增加平台 API 的审计导出能力。
3. 增加 OpenFGA 模型版本管理与迁移流程。
4. 增加 CI 状态徽章与失败诊断指引。
