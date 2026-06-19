import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from database import get_stats
from keyboards import stats_period_keyboard
from utils import safe_edit_message, format_date_short

logger = logging.getLogger(__name__)
router = Router()


def stats_keyboard_with_all(days: int = 30):
    """Клавиатура статистики с кнопкой 'За всё время' и 'Главное меню'"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Обновить", callback_data=f"stats_{days}")],
        [InlineKeyboardButton(text="📅 За 7 дней", callback_data="stats_7"),
         InlineKeyboardButton(text="📅 За 30 дней", callback_data="stats_30"),
         InlineKeyboardButton(text="📅 За 90 дней", callback_data="stats_90")],
        [InlineKeyboardButton(text="📅 За всё время", callback_data="stats_all")],
        [InlineKeyboardButton(text="✏️ Редактировать", callback_data="edit_list"),
         InlineKeyboardButton(text="🗑️ Удалить", callback_data="delete_list")],
        [InlineKeyboardButton(text="➕ Добавить транзакцию", callback_data="add_new")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
    ])


def build_stats_text(stats: dict) -> str:
    """Формируем текст статистики"""
    period_label = stats.get('period_label', '')
    
    text = (
        f"📊 **Статистика {period_label}**\n\n"
        f"💰 Доходы: {stats['total_income']:,.2f} ₽\n"
        f"💸 Расходы: {stats['total_expense']:,.2f} ₽\n"
        f"💵 Баланс: {stats['balance']:,.2f} ₽\n"
        f"📝 Всего транзакций: {len(stats['transactions'])}\n\n"
    )
    
    if stats['expenses_by_category']:
        text += "**Расходы по категориям:**\n"
        for category, amount in stats['expenses_by_category'][:10]:
            percentage = (amount / stats['total_expense'] * 100) if stats['total_expense'] > 0 else 0
            text += f"  • {category}: {amount:,.2f} ₽ ({percentage:.1f}%)\n"
        text += "\n"
    
    if stats['income_by_category']:
        text += "**Доходы по категориям:**\n"
        for category, amount in stats['income_by_category'][:10]:
            text += f"  • {category}: {amount:,.2f} ₽\n"
        text += "\n"
    
    return text


@router.callback_query(F.data == "show_stats")
async def show_statistics(callback: CallbackQuery):
    """Показываем статистику за 30 дней"""
    user_id = callback.from_user.id
    
    try:
        stats = await get_stats(user_id, period_days=30)
        text = build_stats_text(stats)
        await safe_edit_message(callback, text, stats_keyboard_with_all(30), parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Ошибка получения статистики: {e}")
        await callback.answer(f"❌ Ошибка: {str(e)[:50]}", show_alert=True)


@router.callback_query(F.data.in_(["stats_7", "stats_30", "stats_90"]))
async def show_stats_period(callback: CallbackQuery):
    """Показываем статистику за выбранный период"""
    period_map = {"stats_7": 7, "stats_30": 30, "stats_90": 90}
    days = period_map[callback.data]
    
    try:
        stats = await get_stats(callback.from_user.id, period_days=days)
        text = build_stats_text(stats)
        await safe_edit_message(callback, text, stats_keyboard_with_all(days), parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Ошибка получения статистики: {e}")
        await callback.answer(f"❌ Ошибка: {str(e)[:50]}", show_alert=True)


@router.callback_query(F.data == "stats_all")
async def show_stats_all_time(callback: CallbackQuery):
    """Показываем статистику за всё время"""
    user_id = callback.from_user.id
    
    try:
        stats = await get_stats(user_id, period_days=None)
        text = build_stats_text(stats)
        await safe_edit_message(callback, text, stats_keyboard_with_all("all"), parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Ошибка получения статистики за всё время: {e}")
        await callback.answer(f"❌ Ошибка: {str(e)[:50]}", show_alert=True)