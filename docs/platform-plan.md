# Platform Plan

## Goal

Build a multi-tenant AI platform on top of LangGraph runtime without rewriting LangGraph runtime APIs.

## Architecture

- Runtime Plane: LangGraph API server handles threads, runs, stream, checkpoints.
- Control Plane: This FastAPI service handles auth, tenancy, project metadata, policy, and governance.
- Data Plane: PostgreSQL stores tenants, projects, agents, memberships, policy bindings, audit logs.

## Principles

- Keep LangGraph API compatibility at proxy boundary.
- Add platform capabilities outside runtime protocol.
- Prefer mature OSS components over custom infrastructure.

## Recommended OSS Components

- Identity and SSO: Keycloak (OIDC, SAML, enterprise-grade).
- Authorization: OpenFGA (relationship-based access control).
- API edge: Kong or Traefik (rate limits, edge auth, routing).
- Observability: OpenTelemetry + Prometheus + Grafana; optional Langfuse for LLM-centric tracing.

## Phase Plan

### Phase 1 - Proxy Foundation (current)

- Transparent passthrough for all paths and methods.
- SSE passthrough for streaming endpoints.
- Request tracing baseline: request id, structured logs, upstream error mapping.
- Stability baseline: configurable timeout, connection reuse, health endpoints.

### Phase 2 - Identity and Tenant Model

- Integrate IdP (Keycloak).
- Add tenant-aware auth middleware.
- Add core tables: users, tenants, memberships.

### Phase 3 - Project and Agent Management

- Add tables: projects, agents, runtime_bindings.
- Map platform agent id to LangGraph assistant_id/graph_id.
- Add CRUD APIs for project and agent management.

### Phase 4 - Authorization and Governance

- Integrate OpenFGA policy checks before proxy forwarding.
- Add per-tenant limits and quotas.
- Add audit logs for all runtime invocations.

### Phase 5 - Delivery and Operations

- Add environment promotion flow (dev/staging/prod).
- Add deployment and rollback metadata.
- Add cost attribution dashboards by tenant/project/agent.

## PostgreSQL Core Schema (initial)

- tenants(id, name, slug, status, created_at)
- users(id, external_subject, email, created_at)
- memberships(id, tenant_id, user_id, role, created_at)
- projects(id, tenant_id, name, key, created_at)
- agents(id, tenant_id, project_id, name, created_at)
- runtime_bindings(id, agent_id, langgraph_assistant_id, langgraph_graph_id, env, created_at)
- audit_logs(id, tenant_id, project_id, actor_id, action, resource_type, resource_id, metadata_json, created_at)

## Immediate Next Milestone

Complete Phase 1 hardening in the proxy service, then start Phase 2 database migrations and auth integration.
