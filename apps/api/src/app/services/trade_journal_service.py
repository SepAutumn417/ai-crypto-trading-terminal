from uuid import UUID
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.trade_journal import TradeJournal
from app.schemas.trade_journal import TradeJournalCreate, TradeJournalUpdate, TradeJournalSummary


class TradeJournalService:
    @staticmethod
    async def create(db: AsyncSession, data: TradeJournalCreate) -> TradeJournal:
        journal = TradeJournal(**data.model_dump())
        db.add(journal)
        await db.commit()
        await db.refresh(journal)
        return journal

    @staticmethod
    async def get_by_id(db: AsyncSession, journal_id: UUID) -> TradeJournal | None:
        result = await db.execute(select(TradeJournal).where(TradeJournal.id == journal_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def list(
        db: AsyncSession,
        page: int = 1,
        page_size: int = 20,
        symbol: str | None = None,
        status: str | None = None,
    ) -> tuple[list[TradeJournal], int]:
        query = select(TradeJournal)
        count_query = select(func.count()).select_from(TradeJournal)

        if symbol:
            query = query.where(TradeJournal.symbol == symbol)
            count_query = count_query.where(TradeJournal.symbol == symbol)
        if status:
            query = query.where(TradeJournal.status == status)
            count_query = count_query.where(TradeJournal.status == status)

        query = query.order_by(TradeJournal.created_at.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)

        result = await db.execute(query)
        count_result = await db.execute(count_query)
        total = count_result.scalar_one()

        return result.scalars().all(), total

    @staticmethod
    async def update(
        db: AsyncSession,
        journal_id: UUID,
        data: TradeJournalUpdate,
    ) -> TradeJournal | None:
        journal = await TradeJournalService.get_by_id(db, journal_id)
        if not journal:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(journal, key, value)

        await db.commit()
        await db.refresh(journal)
        return journal

    @staticmethod
    async def delete(db: AsyncSession, journal_id: UUID) -> bool:
        journal = await TradeJournalService.get_by_id(db, journal_id)
        if not journal:
            return False
        await db.delete(journal)
        await db.commit()
        return True

    @staticmethod
    async def get_summary(db: AsyncSession, symbol: str | None = None) -> TradeJournalSummary:
        query = select(TradeJournal).where(TradeJournal.status == "CLOSED")
        if symbol:
            query = query.where(TradeJournal.symbol == symbol)

        result = await db.execute(query)
        closed_trades = result.scalars().all()

        total_trades = len(closed_trades)
        winning_trades = sum(1 for t in closed_trades if t.pnl and t.pnl > 0)
        losing_trades = sum(1 for t in closed_trades if t.pnl and t.pnl < 0)

        pnl_values = [t.pnl for t in closed_trades if t.pnl is not None]
        total_pnl = sum(pnl_values) if pnl_values else 0

        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else None
        avg_pnl = (total_pnl / total_trades) if total_trades > 0 else None
        best_trade = max(pnl_values) if pnl_values else None
        worst_trade = min(pnl_values) if pnl_values else None

        from decimal import Decimal
        return TradeJournalSummary(
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            win_rate=Decimal(str(win_rate)) if win_rate is not None else None,
            total_pnl=Decimal(str(total_pnl)),
            avg_pnl=Decimal(str(avg_pnl)) if avg_pnl is not None else None,
            best_trade=Decimal(str(best_trade)) if best_trade is not None else None,
            worst_trade=Decimal(str(worst_trade)) if worst_trade is not None else None,
        )
