from __future__ import annotations

import argparse
import asyncio
import uuid

from sqlalchemy import select

from app.auth.openfga import OpenFgaClient, OpenFgaSettings, fga_tenant, fga_user
from app.config import load_settings
from app.db.access import (
    create_or_update_membership,
    delete_membership,
    get_membership,
    parse_uuid,
    resolve_tenant,
)
from app.db.models import User
from app.db.session import build_engine, build_session_factory, session_scope


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Rollback tenant membership role and optionally sync OpenFGA")
    parser.add_argument("--tenant-ref", required=True, help="Tenant UUID or slug")
    parser.add_argument(
        "--user-ref",
        required=True,
        help="User UUID or external_subject",
    )
    parser.add_argument(
        "--target-role",
        choices=["owner", "admin", "member", "none"],
        required=True,
        help="Target role, use 'none' to remove membership",
    )
    parser.add_argument("--sync-openfga", action="store_true")
    return parser.parse_args()


def _resolve_user(session, user_ref: str) -> User | None:
    parsed = parse_uuid(user_ref)
    if parsed:
        return session.get(User, parsed)

    stmt = select(User).where(User.external_subject == user_ref)
    return session.scalar(stmt)


async def _sync_openfga_membership(
    tenant_id: uuid.UUID,
    subject: str,
    target_role: str,
) -> None:
    settings = load_settings()
    if not settings.openfga_enabled:
        print("OPENFGA disabled, skip sync")
        return

    client = OpenFgaClient(
        OpenFgaSettings(
            enabled=True,
            authz_enabled=settings.openfga_authz_enabled,
            auto_bootstrap=False,
            base_url=settings.openfga_url,
            store_id=settings.openfga_store_id,
            model_id=settings.openfga_model_id,
            model_file=settings.openfga_model_file,
        )
    )

    try:
        await client.ensure_ready()
        user = fga_user(subject)
        tenant = fga_tenant(str(tenant_id))

        await client.delete_tuples(
            [
                {"user": user, "relation": "owner", "object": tenant},
                {"user": user, "relation": "admin", "object": tenant},
                {"user": user, "relation": "member", "object": tenant},
            ]
        )

        if target_role != "none":
            await client.write_tuple(user=user, relation=target_role, obj=tenant)
    finally:
        await client.aclose()


async def run() -> None:
    args = parse_args()
    settings = load_settings()
    if not settings.platform_db_enabled:
        raise RuntimeError("PLATFORM_DB_ENABLED must be true")

    engine = build_engine(settings)
    session_factory = build_session_factory(engine)

    resolved_subject: str | None = None
    resolved_tenant_id: uuid.UUID | None = None

    with session_scope(session_factory) as session:
        tenant = resolve_tenant(session, args.tenant_ref)
        if tenant is None:
            raise RuntimeError(f"Tenant not found: {args.tenant_ref}")

        user = _resolve_user(session, args.user_ref)
        if user is None:
            raise RuntimeError(f"User not found: {args.user_ref}")

        resolved_subject = user.external_subject
        resolved_tenant_id = tenant.id

        if args.target_role == "none":
            row = get_membership(session, tenant_id=tenant.id, user_id=user.id)
            if row is None:
                print("Membership already absent")
            else:
                delete_membership(session, row)
                print(f"Removed membership tenant={tenant.id} user={user.id}")
        else:
            membership = create_or_update_membership(
                session,
                tenant_id=tenant.id,
                user_id=user.id,
                role=args.target_role,
            )
            print(
                f"Rolled back membership tenant={tenant.id} user={user.id} role={membership.role}"
            )

    if args.sync_openfga:
        assert resolved_subject is not None and resolved_tenant_id is not None
        await _sync_openfga_membership(
            tenant_id=resolved_tenant_id,
            subject=resolved_subject,
            target_role=args.target_role,
        )
        print("OpenFGA sync complete")


if __name__ == "__main__":
    asyncio.run(run())
