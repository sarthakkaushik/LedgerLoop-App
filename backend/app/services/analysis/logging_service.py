from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analysis_query import AnalysisQuery
from app.models.analysis_query_attempt import AnalysisQueryAttempt


def _utc_now_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


async def create_query_log(
    session: AsyncSession,
    *,
    household_id: UUID,
    user_id: UUID,
    provider: str,
    model: str,
    question: str,
    mode: str,
    route: str,
    tool: str,
) -> AnalysisQuery:
    row = AnalysisQuery(
        household_id=household_id,
        user_id=user_id,
        provider=provider,
        model=model,
        question=question,
        mode=mode,
        route=route,
        tool=tool,
        status="running",
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


async def add_attempt_log(
    session: AsyncSession,
    *,
    query_log: AnalysisQuery,
    attempt_number: int,
    generated_sql: str,
    llm_reason: str | None,
    validation_ok: bool,
    validation_reason: str | None,
    execution_ok: bool,
    db_error: str | None,
) -> AnalysisQueryAttempt:
    row = AnalysisQueryAttempt(
        analysis_query_id=query_log.id,
        attempt_number=attempt_number,
        generated_sql=generated_sql,
        llm_reason=llm_reason,
        validation_ok=validation_ok,
        validation_reason=validation_reason,
        execution_ok=execution_ok,
        db_error=db_error,
    )
    session.add(row)
    query_log.attempt_count = max(query_log.attempt_count, attempt_number)
    query_log.updated_at = _utc_now_naive()
    session.add(query_log)
    await session.commit()
    return row


async def finalize_query_log(
    session: AsyncSession,
    *,
    query_log: AnalysisQuery,
    status: str,
    final_answer: str,
    attempt_count: int,
    final_sql: str | None = None,
    failure_reason: str | None = None,
    mode: str | None = None,
    route: str | None = None,
    tool: str | None = None,
) -> AnalysisQuery:
    query_log.status = status
    query_log.final_sql = final_sql
    query_log.final_answer = final_answer
    query_log.failure_reason = failure_reason
    query_log.attempt_count = max(query_log.attempt_count, attempt_count)
    if mode is not None:
        query_log.mode = mode
    if route is not None:
        query_log.route = route
    if tool is not None:
        query_log.tool = tool
    query_log.updated_at = _utc_now_naive()
    session.add(query_log)
    await session.commit()
    await session.refresh(query_log)
    return query_log

