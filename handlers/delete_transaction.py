import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from database import get_transaction, delete_transaction, get_stats
from utils import safe_edit_message, format_date, format_date_short

logger = logging.getLogger(__name__)
router = Router()


@router.callback_query(F.data == "delete_list")
async def show_delete_list(callback: CallbackQuery):
    """Показываем список транзакций для удаления"""
    user_id = callback.from_user.id
    
    try:
        stats = await get_stats(user_id, period_days=30)
        
        if not stats['transactions']:
            await callback.answer(" Нет транзакций для удаления", show_alert=True)
            return
        
        keyboard_buttons = []
        for trans in stats['transactions'][:15]:
            emoji = "💰" if trans['type'] == "income" else "💸"
            date_str = format_date_short(trans['date'])
            btn_text = f"{emoji} {trans['amount']:,.0f}₽ - {trans['category']} ({date_str})"
            keyboard_buttons.append([InlineKeyboardButton(text=btn_text, callback_data=f"delete_trans_{trans['id']}")])
        
        keyboard_buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="show_stats")])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        
        await safe_edit_message(
            callback,
            f"🗑️ **Выберите транзакцию для удаления**\n\n"
            f"Всего транзакций: {len(stats['transactions'])}",
            keyboard,
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Ошибка показа списка удаления: {e}")
        await callback.answer(f"❌ Ошибка: {str(e)[:50]}", show_alert=True)


@router.callback_query(F.data.startswith("delete_trans_"))
async def delete_transaction_from_list(callback: CallbackQuery):
    """Удаление транзакции из списка с подтверждением"""
    try:
        trans_id = int(callback.data.split("delete_trans_")[1])
        user_id = callback.from_user.id
        
        trans = await get_transaction(trans_id, user_id)
        if not trans:
            await callback.answer("❌ Транзакция не найдена", show_alert=True)
            return
        
        type_emoji = "💰" if trans['transaction_type'] == "income" else "💸"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"confirm_delete_{trans_id}")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="delete_list")]
        ])
        
        await safe_edit_message(
            callback,
            f"️ **Подтвердите удаление**\n\n"
            f"{type_emoji} {float(trans['amount']):,.2f}₽ - {trans['category']}\n"
            f"📅 {format_date(trans['transaction_date'])}\n\n"
            f"Это действие нельзя отменить!",
            keyboard,
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Ошибка подтверждения удаления: {e}")
        await callback.answer(f"❌ Ошибка: {str(e)[:50]}", show_alert=True)


@router.callback_query(F.data.startswith("confirm_delete_"))
async def confirm_delete_transaction(callback: CallbackQuery):
    """Подтверждение удаления транзакции"""
    try:
        trans_id = int(callback.data.split("confirm_delete_")[1])
        user_id = callback.from_user.id
        
        await delete_transaction(trans_id, user_id)
        
        stats = await get_stats(user_id, period_days=30)
        
        if not stats['transactions']:
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад к статистике", callback_data="show_stats")],
                [InlineKeyboardButton(text="➕ Добавить", callback_data="add_new")]
            ])
            await safe_edit_message(
                callback,
                "✅ Транзакция удалена!\n\n"
                "Больше нет транзакций для удаления.",
                keyboard
            )
            return
        
        keyboard_buttons = []
        for trans in stats['transactions'][:15]:
            emoji = "💰" if trans['type'] == "income" else "💸"
            date_str = format_date_short(trans['date'])
            btn_text = f"{emoji} {trans['amount']:,.0f}₽ - {trans['category']} ({date_str})"
            keyboard_buttons.append([InlineKeyboardButton(text=btn_text, callback_data=f"delete_trans_{trans['id']}")])
        
        keyboard_buttons.append([InlineKeyboardButton(text=" Назад", callback_data="show_stats")])
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        
        await safe_edit_message(
            callback,
            f"✅ Транзакция удалена!\n\n"
            f"🗑️ **Выберите следующую транзакцию для удаления**\n\n"
            f"Всего транзакций: {len(stats['transactions'])}",
            keyboard,
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Ошибка удаления транзакции: {e}")
        await callback.answer(f"❌ Ошибка: {str(e)[:50]}", show_alert=True)