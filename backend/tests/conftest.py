from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel

from app.core.db import get_session
from app.main import app
from app.models import analysis_query as _analysis_query  # noqa: F401
from app.models import analysis_query_attempt as _analysis_query_attempt  # noqa: F401
from app.models import expense as _expense  # noqa: F401
from app.models import family_member as _family_member  # noqa: F401
from app.models import household as _household  # noqa: F401
from app.models import household_category as _household_category  # noqa: F401
from app.models import household_subcategory as _household_subcategory  # noqa: F401
from app.models import llm_setting as _llm_setting  # noqa: F401
from app.models import user as _user  # noqa: F401
from app.models import user_login_event as _user_login_event  # noqa: F401


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    async def override_get_session() -> AsyncIterator[AsyncSession]:
        async with session_maker() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as test_client:
        yield test_client

    app.dependency_overrides.clear()
    await engine.dispose()
