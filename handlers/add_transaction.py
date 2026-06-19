import logging
from datetime import datetime
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from states import TransactionState
from keyboards import categories_with_cancel_keyboard, after_save_keyboard
from database import save_transaction
from utils import safe_edit_message

logger = logging.getLogger(__name__)
router = Router()


@router.callback_query(F.data.in_(["type_income", "type_expense"]))
async def process_type(callback: CallbackQuery, state: FSMContext):
    """Выбор типа транзакции"""
    trans_type = "income" if callback.data == "type_income" else "expense"
    await state.update_data(transaction_type=trans_type)
    
    emoji = "💰" if trans_type == "income" else "💸"
    
    await safe_edit_message(
        callback,
        f"{emoji} Выбрано: {'Доход' if trans_type == 'income' else 'Расход'}\n\n"
        f"Введите сумму (например: 1500 или 1500.50):",
        None
    )
    await state.set_state(TransactionState.waiting_for_amount)


@router.message(TransactionState.waiting_for_amount)
async def process_amount(message: Message, state: FSMContext):
    """Ввод суммы"""
    try:
        amount = float(message.text.replace(',', '.'))
        if amount <= 0:
            raise ValueError
        
        await state.update_data(amount=amount)
        data = await state.get_data()
        trans_type = data.get("transaction_type", "expense")
        
        keyboard = categories_with_cancel_keyboard(trans_type)
        
        emoji = "💰" if trans_type == "income" else "💸"
        
        await message.answer(
            f"{emoji} Сумма: {amount}₽\n\n"
            f"Выберите категорию:",
            reply_markup=keyboard
        )
        await state.set_state(TransactionState.waiting_for_category)
    except ValueError:
        await message.answer("❌ Введите корректное число больше 0")


@router.callback_query(F.data.startswith("cat_"), TransactionState.waiting_for_category)
async def process_category(callback: CallbackQuery, state: FSMContext):
    """Выбор категории"""
    category = callback.data.split("cat_", 1)[1]
    await state.update_data(category=category)
    
    data = await state.get_data()
    trans_type = data.get("transaction_type", "expense")
    type_name = "дохода" if trans_type == "income" else "расхода"
    
    from keyboards import cancel_keyboard
    await safe_edit_message(
        callback,
        f" Категория: {category}\n\n"
        f"Введите дату {type_name} (ДД.ММ.ГГГГ) или напишите 'сегодня':",
        cancel_keyboard()
    )
    await state.set_state(TransactionState.waiting_for_date)


@router.message(TransactionState.waiting_for_date)
async def process_date(message: Message, state: FSMContext):
    """Ввод даты и сохранение"""
    user_input = message.text.strip().lower()
    
    if user_input == "сегодня":
        transaction_date = datetime.now().date()
    else:
        try:
            transaction_date = datetime.strptime(user_input, "%d.%m.%Y").date()
        except ValueError:
            await message.answer(" Неверный формат. Используйте ДД.ММ.ГГГГ или 'сегодня'")
            return
    
    data = await state.get_data()
    user_id = message.from_user.id
    trans_type = data["transaction_type"]
    amount = data["amount"]
    category = data["category"]
    
    try:
        await save_transaction(user_id, trans_type, amount, category, transaction_date)
        
        type_emoji = "💰" if trans_type == "income" else "💸"
        type_name = "Доход" if trans_type == "income" else "Расход"
        
        await message.answer(
            f"✅ {type_name} сохранён!\n\n"
            f"{type_emoji} {amount}₽\n"
            f" {category}\n"
            f" {transaction_date.strftime('%d.%m.%Y')}\n",
            reply_markup=after_save_keyboard()
        )
    except Exception as e:
        logger.error(f"Ошибка сохранения транзакции: {e}")
        await message.answer(f"❌ Ошибка сохранения: {e}")
    
    await state.clear()