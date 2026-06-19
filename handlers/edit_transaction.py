import logging
from datetime import datetime
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from states import TransactionState, EditState
from database import get_transaction, update_transaction, get_stats
from keyboards import (
    edit_menu_keyboard, categories_keyboard, after_edit_keyboard, edit_cancel_keyboard
)
from utils import safe_edit_message, format_date, format_date_short

logger = logging.getLogger(__name__)
router = Router()


@router.callback_query(F.data == "edit_list")
async def show_edit_list(callback: CallbackQuery):
    """Показываем список транзакций для редактирования"""
    user_id = callback.from_user.id
    
    try:
        stats = await get_stats(user_id, period_days=30)
        
        if not stats['transactions']:
            await callback.answer("❌ Нет транзакций для редактирования", show_alert=True)
            return
        
        keyboard_buttons = []
        for trans in stats['transactions'][:15]:
            emoji = "💰" if trans['type'] == "income" else "💸"
            date_str = format_date_short(trans['date'])
            btn_text = f"{emoji} {trans['amount']:,.0f}₽ - {trans['category']} ({date_str})"
            keyboard_buttons.append([InlineKeyboardButton(text=btn_text, callback_data=f"edit_trans_{trans['id']}")])
        
        keyboard_buttons.append([InlineKeyboardButton(text=" Назад", callback_data="show_stats")])
        
        from aiogram.types import InlineKeyboardMarkup
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        
        await safe_edit_message(
            callback,
            f"✏️ **Выберите транзакцию для редактирования**\n\n"
            f"Всего транзакций: {len(stats['transactions'])}",
            keyboard,
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Ошибка показа списка редактирования: {e}")
        await callback.answer(f"❌ Ошибка: {str(e)[:50]}", show_alert=True)


@router.callback_query(F.data.startswith("edit_trans_"))
async def edit_transaction_from_list(callback: CallbackQuery, state: FSMContext):
    """Редактирование транзакции из списка"""
    try:
        trans_id = int(callback.data.split("edit_trans_")[1])
        user_id = callback.from_user.id
        
        trans = await get_transaction(trans_id, user_id)
        if not trans:
            await callback.answer("❌ Транзакция не найдена", show_alert=True)
            return
        
        await state.update_data(edit_id=trans_id, original_type=trans['transaction_type'])
        
        type_emoji = "💰" if trans['transaction_type'] == "income" else "💸"
        date_str = format_date(trans['transaction_date'])
        
        await safe_edit_message(
            callback,
            f"✏️ **Редактирование транзакции #{trans_id}**\n\n"
            f"{type_emoji} {float(trans['amount']):,.2f}₽\n"
            f"📁 {trans['category']}\n"
            f"📅 {date_str}\n\n"
            f"Что хотите изменить?",
            edit_menu_keyboard(),
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Ошибка редактирования транзакции: {e}")
        await callback.answer(f" Ошибка: {str(e)[:50]}", show_alert=True)


@router.callback_query(F.data == "edit_amount")
async def edit_amount_start(callback: CallbackQuery, state: FSMContext):
    """Начало редактирования суммы"""
    await callback.message.answer(
        "💰 Введите новую сумму:",
        reply_markup=edit_cancel_keyboard()
    )
    await state.set_state(EditState.waiting_for_new_amount)


@router.message(EditState.waiting_for_new_amount)
async def process_new_amount(message: Message, state: FSMContext):
    """Обработка новой суммы"""
    if message.text.startswith("/"):
        return
    
    try:
        amount = float(message.text.replace(',', '.'))
        if amount <= 0:
            raise ValueError
        
        data = await state.get_data()
        trans_id = data["edit_id"]
        user_id = message.from_user.id
        
        await update_transaction(trans_id, user_id, amount=amount)
        
        await message.answer(
            f"✅ Сумма изменена на {amount:,.2f}₽",
            reply_markup=after_edit_keyboard()
        )
        await state.clear()
    except ValueError:
        await message.answer("❌ Введите корректное число больше 0")
    except Exception as e:
        logger.error(f"Ошибка изменения суммы: {e}")
        await message.answer(f"❌ Ошибка: {e}")


@router.callback_query(F.data == "edit_category")
async def edit_category_start(callback: CallbackQuery, state: FSMContext):
    """Начало редактирования категории"""
    data = await state.get_data()
    trans_type = data.get("original_type", "expense")
    
    await callback.message.answer(
        "📁 Выберите новую категорию:",
        reply_markup=categories_keyboard(trans_type)
    )


@router.callback_query(F.data.startswith("edit_cat_"))
async def process_new_category(callback: CallbackQuery, state: FSMContext):
    """Обработка новой категории"""
    category = callback.data.split("edit_cat_", 1)[1]
    
    data = await state.get_data()
    trans_id = data["edit_id"]
    user_id = callback.from_user.id
    
    await update_transaction(trans_id, user_id, category=category)
    
    await callback.message.answer(
        f"✅ Категория изменена на {category}",
        reply_markup=after_edit_keyboard()
    )
    await state.clear()


@router.callback_query(F.data == "edit_date")
async def edit_date_start(callback: CallbackQuery, state: FSMContext):
    """Начало редактирования даты"""
    await callback.message.answer(
        "📅 Введите новую дату (ДД.ММ.ГГГГ) или 'сегодня':",
        reply_markup=edit_cancel_keyboard()
    )
    await state.set_state(EditState.waiting_for_new_date)


@router.message(EditState.waiting_for_new_date)
async def process_new_date(message: Message, state: FSMContext):
    """Обработка новой даты"""
    if message.text.startswith("/"):
        return
    
    user_input = message.text.strip().lower()
    
    if user_input == "сегодня":
        transaction_date = datetime.now().date()
    else:
        try:
            transaction_date = datetime.strptime(user_input, "%d.%m.%Y").date()
        except ValueError:
            await message.answer("❌ Неверный формат. Используйте ДД.ММ.ГГГГ или 'сегодня'")
            return
    
    data = await state.get_data()
    trans_id = data["edit_id"]
    user_id = message.from_user.id
    
    await update_transaction(trans_id, user_id, date=transaction_date)
    
    await message.answer(
        f"✅ Дата изменена на {format_date(transaction_date)}",
        reply_markup=after_edit_keyboard()
    )
    await state.clear()