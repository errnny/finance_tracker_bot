import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery
from database import get_stats
from keyboards import stats_keyboard, stats_period_keyboard
from utils import safe_edit_message, format_date_short

logger = logging.getLogger(__name__)
router = Router()


@router.callback_query(F.data == "show_stats")
async def show_statistics(callback: CallbackQuery):
    """Показываем статистику за 30 дней"""
    user_id = callback.from_user.id
    
    try:
        stats = await get_stats(user_id, period_days=30)
        
        text = (
            f"📊 **Статистика за 30 дней**\n\n"
            f"💰 Доходы: {stats['total_income']:,.2f} ₽\n"
            f"💸 Расходы: {stats['total_expense']:,.2f} ₽\n"
            f"💵 Баланс: {stats['balance']:,.2f} ₽\n\n"
        )
        
        if stats['expenses_by_category']:
            text += "**Расходы по категориям:**\n"
            for category, amount in stats['expenses_by_category'][:5]:
                percentage = (amount / stats['total_expense'] * 100) if stats['total_expense'] > 0 else 0
                text += f"  • {category}: {amount:,.2f} ₽ ({percentage:.1f}%)\n"
            text += "\n"
        
        if stats['income_by_category']:
            text += "**Доходы по категориям:**\n"
            for category, amount in stats['income_by_category'][:5]:
                text += f"  • {category}: {amount:,.2f} ₽\n"
            text += "\n"
        
        await safe_edit_message(callback, text, stats_keyboard(), parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Ошибка получения статистики: {e}")
        await callback.answer(f"❌ Ошибка: {str(e)[:50]}", show_alert=True)


@router.callback_query(F.data.in_(["stats_7", "stats_90", "stats_30"]))
async def show_stats_period(callback: CallbackQuery):
    """Показываем статистику за выбранный период"""
    period_map = {"stats_7": 7, "stats_90": 90, "stats_30": 30}
    days = period_map[callback.data]
    
    stats = await get_stats(callback.from_user.id, period_days=days)
    
    text = (
        f"📊 **Статистика за {days} дней**\n\n"
        f"💰 Доходы: {stats['total_income']:,.2f} ₽\n"
        f" Расходы: {stats['total_expense']:,.2f} ₽\n"
        f" Баланс: {stats['balance']:,.2f} ₽\n\n"
    )
    
    if stats['expenses_by_category']:
        text += "**Расходы по категориям:**\n"
        for category, amount in stats['expenses_by_category'][:5]:
            percentage = (amount / stats['total_expense'] * 100) if stats['total_expense'] > 0 else 0
            text += f"  • {category}: {amount:,.2f} ₽ ({percentage:.1f}%)\n"
        text += "\n"
    
    await safe_edit_message(callback, text, stats_period_keyboard(), parse_mode="Markdown")