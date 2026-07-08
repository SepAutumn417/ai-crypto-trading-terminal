import pytest


@pytest.mark.asyncio
async def test_get_active_configs(client):
    resp = await client.get("/api/configs/active")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["risk"]["version_label"] == "risk-v1"
    assert data["symbol_rules"]["version_label"] == "symbol_rules-v1"


@pytest.mark.asyncio
async def test_list_configs(client):
    resp = await client.get("/api/configs", params={"type": "risk"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) >= 1
    assert all(v["config_type"] == "risk" for v in data)


@pytest.mark.asyncio
async def test_create_and_activate_config(client):
    resp = await client.post("/api/configs", json={
        "config_type": "risk",
        "version_label": "risk-v2",
        "payload": {"max_leverage": "5"},
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    new_id = body["data"]["id"]

    resp = await client.post(f"/api/configs/{new_id}/activate")
    assert resp.status_code == 200
    assert resp.json()["data"]["is_active"] is True

    resp = await client.get("/api/configs/active")
    active = resp.json()["data"]
    assert active["risk"]["version_label"] == "risk-v2"
    assert active["risk"]["id"] == new_id

    resp = await client.get("/api/configs", params={"type": "risk"})
    versions = {v["version_label"]: v for v in resp.json()["data"]}
    assert versions["risk-v1"]["is_active"] is False
    assert versions["risk-v2"]["is_active"] is True


@pytest.mark.asyncio
async def test_duplicate_label_rejected(client):
    resp = await client.post("/api/configs", json={
        "config_type": "risk",
        "version_label": "risk-v1",
        "payload": {},
    })
    body = resp.json()
    assert body["success"] is False
    assert body["error"]["code"] == "DUPLICATE_LABEL"


@pytest.mark.asyncio
async def test_invalid_config_type(client):
    resp = await client.post("/api/configs", json={
        "config_type": "invalid",
        "version_label": "x",
        "payload": {},
    })
    body = resp.json()
    assert body["success"] is False
    assert body["error"]["code"] == "INVALID_CONFIG_TYPE"


@pytest.mark.asyncio
async def test_invalid_config_type_in_list(client):
    resp = await client.get("/api/configs", params={"type": "invalid"})
    body = resp.json()
    assert body["success"] is False
    assert body["error"]["code"] == "INVALID_CONFIG_TYPE"


@pytest.mark.asyncio
async def test_activate_missing_config(client):
    from uuid import uuid4
    resp = await client.post(f"/api/configs/{uuid4()}/activate")
    body = resp.json()
    assert body["success"] is False
    assert body["error"]["code"] == "CONFIG_NOT_FOUND"


@pytest.mark.asyncio
async def test_partial_unique_index_enforced(db_session):
    """DB 层验证：每种 config_type 同时只能有一个 is_active=true。

    直接绕过 API 写 DB，试图让两个同类型都为 is_active=True，
    应被部分唯一索引 idx_config_versions_active 拒绝。
    """
    import uuid as _uuid
    from datetime import datetime, timezone
    from sqlalchemy.exc import IntegrityError

    from app.models import ConfigVersionModel as CVM
    from app.db import Base
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

    # 用独立的 engine + session 避免 conflict with module-level TestSession
    # （module-level session 可能复用连接导致 partial unique 索引无法浮现）
    eng = create_async_engine(
        "postgresql+asyncpg://crypto:crypto@localhost:5432/crypto_terminal_test",
        echo=False, future=True,
    )
    Sess = async_sessionmaker(eng, class_=AsyncSession, expire_on_commit=False)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    try:
        async with Sess() as s:
            a = CVM(
                id=_uuid.uuid4(), config_type="risk", version_label="risk-unique-test-a",
                payload={}, is_active=True,
                created_at=datetime.now(timezone.utc), activated_at=datetime.now(timezone.utc),
            )
            s.add(a)
            await s.commit()

            b = CVM(
                id=_uuid.uuid4(), config_type="risk", version_label="risk-unique-test-b",
                payload={}, is_active=True,
                created_at=datetime.now(timezone.utc), activated_at=datetime.now(timezone.utc),
            )
            s.add(b)
            caught = False
            try:
                await s.commit()
            except IntegrityError as exc:
                assert "idx_config_versions_active" in str(exc) or "unique" in str(exc).lower()
                caught = True
            await s.rollback()
            assert caught, "未触发 partial unique index idx_config_versions_active"
    finally:
        async with eng.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await eng.dispose()


@pytest.mark.asyncio
async def test_concurrent_activation_only_one_wins():
    """并发激活同 config_type 的两个版本，最终只能有一个 is_active=True。

    用两个独立 session + asyncio.gather 模拟并发，
    SELECT FOR UPDATE 串行化 + partial unique index 保证最终一致性。
    """
    import asyncio
    import os
    import uuid as _uuid
    from datetime import datetime, timezone

    from sqlalchemy import select, update
    from sqlalchemy.exc import IntegrityError
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

    from app.models import ConfigVersionModel as CVM
    from app.db import Base

    eng = create_async_engine(
        os.environ.get("TEST_DATABASE_URL",
                       "postgresql+asyncpg://crypto:crypto@localhost:5432/crypto_terminal_test"),
        echo=False, future=True,
    )
    Sess = async_sessionmaker(eng, class_=AsyncSession, expire_on_commit=False)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    try:
        # 预置两个同 type 的 inactive 版本
        async with Sess() as s:
            id_a, id_b = _uuid.uuid4(), _uuid.uuid4()
            s.add_all([
                CVM(id=id_a, config_type="risk", version_label="risk-concurrent-a",
                    payload={}, is_active=False, activated_at=None),
                CVM(id=id_b, config_type="risk", version_label="risk-concurrent-b",
                    payload={}, is_active=False, activated_at=None),
            ])
            await s.commit()

        async def activate(vid) -> bool:
            async with Sess() as s:
                # 锁住目标行
                result = await s.execute(
                    select(CVM).where(CVM.id == vid).with_for_update()
                )
                target = result.scalar_one()
                ct = target.config_type
                # 锁住同 type 全部行
                await s.execute(
                    select(CVM).where(CVM.config_type == ct).with_for_update()
                )
                # 其他版本置 inactive
                await s.execute(
                    update(CVM)
                    .where(CVM.config_type == ct, CVM.id != vid, CVM.is_active == True)  # noqa: E712
                    .values(is_active=False)
                )
                if not target.is_active:
                    target.is_active = True
                    target.activated_at = datetime.now(timezone.utc)
                try:
                    await s.commit()
                    return True
                except IntegrityError:
                    await s.rollback()
                    return False

        results = await asyncio.gather(activate(id_a), activate(id_b))
        # 两个都应成功提交（串行化），但最终只有一个 active
        assert all(results), f"两个激活事务都应成功，结果: {results}"

        async with Sess() as s:
            result = await s.execute(
                select(CVM).where(CVM.config_type == "risk", CVM.is_active == True)  # noqa: E712
            )
            active = result.scalars().all()
            assert len(active) == 1, f"应有且仅有 1 个 active，实际 {len(active)}"
    finally:
        async with eng.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await eng.dispose()
