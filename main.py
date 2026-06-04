import os
import sys
import logging
from datetime import datetime
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.exceptions import TelegramBadRequest
import asyncpg
from dotenv import load_dotenv

# Загружаем .env
load_dotenv()

# Проверяем токен
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    print("❌ ОШИБКА: BOT_TOKEN не найден в .env файле!")
    sys.exit(1)

print("✅ Токен загружен успешно")

# Настройки БД
DB_CONFIG = {
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", ""),
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", 5432)),
    "database": os.getenv("DB_NAME", "finance_tracker"),
}

# Категории
INCOME_CATEGORIES = ["Зарплата", "Премия", "Подработка", "Инвестиции", "Подарок", "Другое"]
EXPENSE_CATEGORIES = ["Еда", "Транспорт", "Жильё", "Развлечения", "Одежда", "Здоровье", "Связь", "Другое"]

# Логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Состояния
class TransactionState(StatesGroup):
    waiting_for_type = State()
    waiting_for_amount = State()
    waiting_for_category = State()
    waiting_for_date = State()

class EditState(StatesGroup):
    waiting_for_new_amount = State()
    waiting_for_new_category = State()
    waiting_for_new_date = State()

# Вспомогательная функция для безопасного редактирования сообщения
async def safe_edit_message(callback: CallbackQuery, text: str, reply_markup: InlineKeyboardMarkup = None, parse_mode: str = "Markdown"):
    """Безопасное редактирование сообщения с обработкой ошибок"""
    try:
        await callback.message.edit_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            # Игнорируем ошибку, если сообщение не изменилось
            logger.debug("Сообщение не изменилось, пропускаем редактирование")
            pass
        else:
            # Другие ошибки пробрасываем дальше
            raise
    except Exception as e:
        logger.error(f"Ошибка при редактировании сообщения: {e}")
        raise

# Работа с БД
async def init_db():
    """Создаем таблицу если не существует"""
    try:
        conn = await asyncpg.connect(**DB_CONFIG)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                transaction_type VARCHAR(10) NOT NULL,
                amount NUMERIC(10, 2) NOT NULL,
                category VARCHAR(50) NOT NULL,
                transaction_date DATE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await conn.close()
        logger.info("✅ База данных инициализирована")
    except Exception as e:
        logger.error(f"❌ Ошибка подключения к БД: {e}")
        raise

async def save_transaction(user_id: int, trans_type: str, amount: float, category: str, date):
    """Сохраняем транзакцию"""
    conn = await asyncpg.connect(**DB_CONFIG)
    try:
        await conn.execute(
            """
            INSERT INTO transactions (user_id, transaction_type, amount, category, transaction_date)
            VALUES ($1, $2, $3, $4, $5)
            """,
            user_id, trans_type, amount, category, date
        )
        logger.info(f"💾 Транзакция сохранена: {trans_type} {amount}₽, {category}, {date}")
    finally:
        await conn.close()

async def get_stats(user_id: int, period_days: int = 30):
    """Получаем статистику за период"""
    conn = await asyncpg.connect(**DB_CONFIG)
    try:
        total_income = await conn.fetchval(
            """
            SELECT COALESCE(SUM(amount), 0) 
            FROM transactions 
            WHERE user_id = $1 
            AND transaction_type = 'income'
            AND transaction_date >= CURRENT_DATE - INTERVAL '%s days'
            """ % period_days,
            user_id
        )
        
        total_expense = await conn.fetchval(
            """
            SELECT COALESCE(SUM(amount), 0) 
            FROM transactions 
            WHERE user_id = $1 
            AND transaction_type = 'expense'
            AND transaction_date >= CURRENT_DATE - INTERVAL '%s days'
            """ % period_days,
            user_id
        )
        
        expenses_by_category = await conn.fetch(
            """
            SELECT category, SUM(amount) as total
            FROM transactions 
            WHERE user_id = $1 
            AND transaction_type = 'expense'
            AND transaction_date >= CURRENT_DATE - INTERVAL '%s days'
            GROUP BY category
            ORDER BY total DESC
            """ % period_days,
            user_id
        )
        
        income_by_category = await conn.fetch(
            """
            SELECT category, SUM(amount) as total
            FROM transactions 
            WHERE user_id = $1 
            AND transaction_type = 'income'
            AND transaction_date >= CURRENT_DATE - INTERVAL '%s days'
            GROUP BY category
            ORDER BY total DESC
            """ % period_days,
            user_id
        )
        
        # Получаем все транзакции за период
        all_transactions = await conn.fetch(
            """
            SELECT id, transaction_type, amount, category, transaction_date, created_at
            FROM transactions 
            WHERE user_id = $1 
            AND transaction_date >= CURRENT_DATE - INTERVAL '%s days'
            ORDER BY transaction_date DESC, created_at DESC
            """ % period_days,
            user_id
        )
        
        return {
            'total_income': float(total_income),
            'total_expense': float(total_expense),
            'balance': float(total_income) - float(total_expense),
            'expenses_by_category': [(r['category'], float(r['total'])) for r in expenses_by_category],
            'income_by_category': [(r['category'], float(r['total'])) for r in income_by_category],
            'transactions': [
                {
                    'id': r['id'],
                    'type': r['transaction_type'],
                    'amount': float(r['amount']),
                    'category': r['category'],
                    'date': r['transaction_date']
                }
                for r in all_transactions
            ]
        }
    finally:
        await conn.close()

async def delete_transaction(transaction_id: int, user_id: int):
    """Удаляем транзакцию"""
    conn = await asyncpg.connect(**DB_CONFIG)
    try:
        await conn.execute(
            "DELETE FROM transactions WHERE id = $1 AND user_id = $2",
            transaction_id, user_id
        )
        logger.info(f"🗑️ Транзакция {transaction_id} удалена")
    finally:
        await conn.close()

async def update_transaction(transaction_id: int, user_id: int, amount: float = None, 
                            category: str = None, date = None):
    """Обновляем транзакцию"""
    conn = await asyncpg.connect(**DB_CONFIG)
    try:
        updates = []
        params = []
        param_values = []
        
        if amount is not None:
            param_values.append(amount)
            params.append(f"amount = ${len(params) + 1}")
        
        if category is not None:
            param_values.append(category)
            params.append(f"category = ${len(params) + 1}")
        
        if date is not None:
            param_values.append(date)
            params.append(f"transaction_date = ${len(params) + 1}")
        
        if params:
            param_values.extend([transaction_id, user_id])
            query = f"UPDATE transactions SET {', '.join(params)} WHERE id = ${len(params) + 1} AND user_id = ${len(params) + 2}"
            await conn.execute(query, *param_values)
            logger.info(f"✏️ Транзакция {transaction_id} обновлена")
    finally:
        await conn.close()

async def get_transaction(transaction_id: int, user_id: int):
    """Получаем транзакцию по ID"""
    conn = await asyncpg.connect(**DB_CONFIG)
    try:
        return await conn.fetchrow(
            "SELECT * FROM transactions WHERE id = $1 AND user_id = $2",
            transaction_id, user_id
        )
    finally:
        await conn.close()

# Хендлеры
@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Доход", callback_data="type_income")],
        [InlineKeyboardButton(text="💸 Расход", callback_data="type_expense")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="show_stats")]
    ])
    
    await message.answer(
        "👋 Привет! Я финансовый трекер.\n\n"
        "Выберите действие:",
        reply_markup=keyboard
    )

@dp.callback_query(F.data == "show_stats")
async def show_statistics(callback: CallbackQuery):
    """Показываем статистику"""
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
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Обновить", callback_data="show_stats")],
            [InlineKeyboardButton(text="📅 За 7 дней", callback_data="stats_7"),
             InlineKeyboardButton(text="📅 За 90 дней", callback_data="stats_90")],
            [InlineKeyboardButton(text="✏️ Редактировать", callback_data="edit_list"),
             InlineKeyboardButton(text="🗑️ Удалить", callback_data="delete_list")],
            [InlineKeyboardButton(text="➕ Добавить транзакцию", callback_data="add_new")]
        ])
        
        await safe_edit_message(callback, text, keyboard, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Ошибка получения статистики: {e}")
        await callback.answer(f"❌ Ошибка: {str(e)[:50]}", show_alert=True)

@dp.callback_query(F.data.in_(["stats_7", "stats_90", "stats_30"]))
async def show_stats_period(callback: CallbackQuery):
    """Показываем статистику за выбранный период"""
    period_map = {"stats_7": 7, "stats_90": 90, "stats_30": 30}
    days = period_map[callback.data]
    
    stats = await get_stats(callback.from_user.id, period_days=days)
    
    text = (
        f"📊 **Статистика за {days} дней**\n\n"
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
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Назад к 30 дням", callback_data="show_stats")],
        [InlineKeyboardButton(text="✏️ Редактировать", callback_data="edit_list"),
         InlineKeyboardButton(text="🗑️ Удалить", callback_data="delete_list")],
        [InlineKeyboardButton(text="➕ Добавить", callback_data="add_new")]
    ])
    
    await safe_edit_message(callback, text, keyboard, parse_mode="Markdown")

@dp.callback_query(F.data == "edit_list")
async def show_edit_list(callback: CallbackQuery):
    """Показываем список транзакций для редактирования"""
    user_id = callback.from_user.id
    
    try:
        stats = await get_stats(user_id, period_days=30)
        
        if not stats['transactions']:
            await callback.answer("❌ Нет транзакций для редактирования", show_alert=True)
            return
        
        # Создаём клавиатуру со списком транзакций
        keyboard_buttons = []
        for trans in stats['transactions'][:15]:  # Показываем последние 15
            emoji = "💰" if trans['type'] == "income" else "💸"
            date_str = trans['date'].strftime('%d.%m') if hasattr(trans['date'], 'strftime') else str(trans['date'])
            btn_text = f"{emoji} {trans['amount']:,.0f}₽ - {trans['category']} ({date_str})"
            keyboard_buttons.append([InlineKeyboardButton(text=btn_text, callback_data=f"edit_trans_{trans['id']}")])
        
        keyboard_buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="show_stats")])
        
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

@dp.callback_query(F.data == "delete_list")
async def show_delete_list(callback: CallbackQuery):
    """Показываем список транзакций для удаления"""
    user_id = callback.from_user.id
    
    try:
        stats = await get_stats(user_id, period_days=30)
        
        if not stats['transactions']:
            await callback.answer("❌ Нет транзакций для удаления", show_alert=True)
            return
        
        # Создаём клавиатуру со списком транзакций
        keyboard_buttons = []
        for trans in stats['transactions'][:15]:  # Показываем последние 15
            emoji = "💰" if trans['type'] == "income" else "💸"
            date_str = trans['date'].strftime('%d.%m') if hasattr(trans['date'], 'strftime') else str(trans['date'])
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

@dp.callback_query(F.data.startswith("edit_trans_"))
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
        date_str = trans['transaction_date'].strftime('%d.%m.%Y') if hasattr(trans['transaction_date'], 'strftime') else str(trans['transaction_date'])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💰 Изменить сумму", callback_data="edit_amount")],
            [InlineKeyboardButton(text="📁 Изменить категорию", callback_data="edit_category")],
            [InlineKeyboardButton(text="📅 Изменить дату", callback_data="edit_date")],
            [InlineKeyboardButton(text="🔙 Назад к списку", callback_data="edit_list")]
        ])
        
        await safe_edit_message(
            callback,
            f"✏️ **Редактирование транзакции #{trans_id}**\n\n"
            f"{type_emoji} {float(trans['amount']):,.2f}₽\n"
            f"📁 {trans['category']}\n"
            f"📅 {date_str}\n\n"
            f"Что хотите изменить?",
            keyboard,
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Ошибка редактирования транзакции: {e}")
        await callback.answer(f"❌ Ошибка: {str(e)[:50]}", show_alert=True)

@dp.callback_query(F.data.startswith("delete_trans_"))
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
        
        # Показываем подтверждение
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"confirm_delete_{trans_id}")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="delete_list")]
        ])
        
        await safe_edit_message(
            callback,
            f"⚠️ **Подтвердите удаление**\n\n"
            f"{type_emoji} {float(trans['amount']):,.2f}₽ - {trans['category']}\n"
            f"📅 {trans['transaction_date'].strftime('%d.%m.%Y') if hasattr(trans['transaction_date'], 'strftime') else str(trans['transaction_date'])}\n\n"
            f"Это действие нельзя отменить!",
            keyboard,
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Ошибка подтверждения удаления: {e}")
        await callback.answer(f"❌ Ошибка: {str(e)[:50]}", show_alert=True)

@dp.callback_query(F.data.startswith("confirm_delete_"))
async def confirm_delete_transaction(callback: CallbackQuery):
    """Подтверждение удаления транзакции"""
    try:
        trans_id = int(callback.data.split("confirm_delete_")[1])
        user_id = callback.from_user.id
        
        await delete_transaction(trans_id, user_id)
        
        # Возвращаемся к списку на удаление
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
        
        # Показываем обновлённый список
        keyboard_buttons = []
        for trans in stats['transactions'][:15]:
            emoji = "💰" if trans['type'] == "income" else "💸"
            date_str = trans['date'].strftime('%d.%m') if hasattr(trans['date'], 'strftime') else str(trans['date'])
            btn_text = f"{emoji} {trans['amount']:,.0f}₽ - {trans['category']} ({date_str})"
            keyboard_buttons.append([InlineKeyboardButton(text=btn_text, callback_data=f"delete_trans_{trans['id']}")])
        
        keyboard_buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="show_stats")])
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

@dp.callback_query(F.data == "add_new")
async def add_new_transaction(callback: CallbackQuery, state: FSMContext):
    """Возврат к добавлению транзакции"""
    await state.clear()
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Доход", callback_data="type_income")],
        [InlineKeyboardButton(text="💸 Расход", callback_data="type_expense")]
    ])
    await safe_edit_message(callback, "Выберите тип транзакции:", keyboard)

@dp.callback_query(F.data.in_(["type_income", "type_expense"]))
async def process_type(callback: CallbackQuery, state: FSMContext):
    """Выбор типа транзакции"""
    trans_type = "income" if callback.data == "type_income" else "expense"
    await state.update_data(transaction_type=trans_type)
    
    categories = INCOME_CATEGORIES if trans_type == "income" else EXPENSE_CATEGORIES
    emoji = "💰" if trans_type == "income" else "💸"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=cat, callback_data=f"cat_{cat}")]
        for cat in categories
    ])
    
    # Добавляем кнопку отмены
    cancel_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_transaction")]
    ])
    
    await safe_edit_message(
        callback,
        f"{emoji} Выбрано: {'Доход' if trans_type == 'income' else 'Расход'}\n\n"
        f"Введите сумму (например: 1500 или 1500.50):",
        cancel_keyboard
    )
    await state.set_state(TransactionState.waiting_for_amount)

@dp.message(TransactionState.waiting_for_amount)
async def process_amount(message: Message, state: FSMContext):
    """Ввод суммы"""
    try:
        amount = float(message.text.replace(',', '.'))
        if amount <= 0:
            raise ValueError
        
        await state.update_data(amount=amount)
        data = await state.get_data()
        trans_type = data.get("transaction_type", "expense")
        
        categories = INCOME_CATEGORIES if trans_type == "income" else EXPENSE_CATEGORIES
        emoji = "💰" if trans_type == "income" else "💸"
        
        # Создаём клавиатуру с категориями и кнопкой отмены в конце
        keyboard_buttons = [
            [InlineKeyboardButton(text=cat, callback_data=f"cat_{cat}")]
            for cat in categories
        ]
        # Добавляем кнопку отмены в конец
        keyboard_buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_transaction")])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        
        await message.answer(
            f"{emoji} Сумма: {amount}₽\n\n"
            f"Выберите категорию:",
            reply_markup=keyboard
        )
        await state.set_state(TransactionState.waiting_for_category)
    except ValueError:
        await message.answer("❌ Введите корректное число больше 0")

@dp.callback_query(F.data.startswith("cat_"), TransactionState.waiting_for_category)
async def process_category(callback: CallbackQuery, state: FSMContext):
    """Выбор категории"""
    category = callback.data.split("cat_", 1)[1]
    await state.update_data(category=category)
    
    data = await state.get_data()
    trans_type = data.get("transaction_type", "expense")
    type_name = "дохода" if trans_type == "income" else "расхода"
    
    # Добавляем кнопку отмены
    cancel_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_transaction")]
    ])
    
    await safe_edit_message(
        callback,
        f"📁 Категория: {category}\n\n"
        f"Введите дату {type_name} (ДД.ММ.ГГГГ) или напишите 'сегодня':",
        cancel_keyboard
    )
    await state.set_state(TransactionState.waiting_for_date)

    # Обработчик кнопки отмены
@dp.callback_query(F.data == "cancel_transaction")
async def cancel_transaction(callback: CallbackQuery, state: FSMContext):
    """Отмена добавления транзакции"""
    await state.clear()
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Доход", callback_data="type_income")],
        [InlineKeyboardButton(text="💸 Расход", callback_data="type_expense")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="show_stats")]
    ])
    
    await safe_edit_message(
        callback,
        "❌ Добавление транзакции отменено\n\n"
        "Выберите действие:",
        keyboard
    )

# Также добавим команду /cancel для отмены
@dp.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    """Отмена текущей операции командой"""
    await state.clear()
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Доход", callback_data="type_income")],
        [InlineKeyboardButton(text="💸 Расход", callback_data="type_expense")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="show_stats")]
    ])
    
    await message.answer(
        "❌ Операция отменена\n\n"
        "Выберите действие:",
        reply_markup=keyboard
    )

@dp.message(TransactionState.waiting_for_date)
async def process_date(message: Message, state: FSMContext):
    """Ввод даты и сохранение"""
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
    user_id = message.from_user.id
    trans_type = data["transaction_type"]
    amount = data["amount"]
    category = data["category"]
    
    try:
        await save_transaction(user_id, trans_type, amount, category, transaction_date)
        
        type_emoji = "💰" if trans_type == "income" else "💸"
        type_name = "Доход" if trans_type == "income" else "Расход"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Добавить ещё", callback_data="add_new")],
            [InlineKeyboardButton(text="📊 Посмотреть статистику", callback_data="show_stats")]
        ])
        
        await message.answer(
            f"✅ {type_name} сохранён!\n\n"
            f"{type_emoji} {amount}₽\n"
            f"📁 {category}\n"
            f"📅 {transaction_date.strftime('%d.%m.%Y')}\n",
            reply_markup=keyboard
        )
    except Exception as e:
        logger.error(f"Ошибка сохранения транзакции: {e}")
        await message.answer(f"❌ Ошибка сохранения: {e}")
    
    await state.clear()

@dp.callback_query(F.data == "cancel_edit")
async def cancel_edit(callback: CallbackQuery, state: FSMContext):
    """Отмена редактирования"""
    await state.clear()
    await safe_edit_message(callback, "❌ Редактирование отменено", None)

@dp.callback_query(F.data == "edit_amount")
async def edit_amount_start(callback: CallbackQuery, state: FSMContext):
    """Начало редактирования суммы"""
    cancel_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_edit")]
    ])
    
    await callback.message.answer(
        "💰 Введите новую сумму:",
        reply_markup=cancel_keyboard
    )
    await state.set_state(EditState.waiting_for_new_amount)

@dp.message(EditState.waiting_for_new_amount)
async def process_new_amount(message: Message, state: FSMContext):
    """Обработка новой суммы"""
    try:
        amount = float(message.text.replace(',', '.'))
        if amount <= 0:
            raise ValueError
        
        data = await state.get_data()
        trans_id = data["edit_id"]
        user_id = message.from_user.id
        
        await update_transaction(trans_id, user_id, amount=amount)
        
        # Создаём клавиатуру с кнопками
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu_from_edit")],
            [InlineKeyboardButton(text="📊 Статистика", callback_data="show_stats")]
        ])
        
        await message.answer(
            f"✅ Сумма изменена на {amount:,.2f}₽",
            reply_markup=keyboard
        )
        await state.clear()
    except ValueError:
        await message.answer("❌ Введите корректное число больше 0")
    except Exception as e:
        logger.error(f"Ошибка изменения суммы: {e}")
        await message.answer(f"❌ Ошибка: {e}")

@dp.callback_query(F.data == "edit_category")
async def edit_category_start(callback: CallbackQuery, state: FSMContext):
    """Начало редактирования категории"""
    data = await state.get_data()
    trans_type = data.get("original_type", "expense")
    categories = INCOME_CATEGORIES if trans_type == "income" else EXPENSE_CATEGORIES
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=cat, callback_data=f"edit_cat_{cat}")]
        for cat in categories
    ])
    
    await callback.message.answer("📁 Выберите новую категорию:", reply_markup=keyboard)

@dp.callback_query(F.data.startswith("edit_cat_"))
async def process_new_category(callback: CallbackQuery, state: FSMContext):
    """Обработка новой категории"""
    category = callback.data.split("edit_cat_", 1)[1]
    
    data = await state.get_data()
    trans_id = data["edit_id"]
    user_id = callback.from_user.id
    
    await update_transaction(trans_id, user_id, category=category)
    
    # Создаём клавиатуру с кнопками
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu_from_edit")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="show_stats")]
    ])
    
    await callback.message.answer(
        f"✅ Категория изменена на {category}",
        reply_markup=keyboard
    )
    await state.clear()

@dp.callback_query(F.data == "main_menu_from_edit")
async def main_menu_from_edit(callback: CallbackQuery):
    """Возврат в главное меню из редактирования"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Доход", callback_data="type_income")],
        [InlineKeyboardButton(text="💸 Расход", callback_data="type_expense")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="show_stats")]
    ])
    
    await callback.message.answer(
        "👋 Привет! Я финансовый трекер.\n\n"
        "Выберите действие:",
        reply_markup=keyboard
    )

@dp.callback_query(F.data == "edit_date")
async def edit_date_start(callback: CallbackQuery, state: FSMContext):
    """Начало редактирования даты"""
    cancel_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_edit")]
    ])
    
    await callback.message.answer(
        "📅 Введите новую дату (ДД.ММ.ГГГГ) или 'сегодня':",
        reply_markup=cancel_keyboard
    )
    await state.set_state(EditState.waiting_for_new_date)

@dp.message(EditState.waiting_for_new_date)
async def process_new_date(message: Message, state: FSMContext):
    """Обработка новой даты"""
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
    
    # Создаём клавиатуру с кнопками
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu_from_edit")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="show_stats")]
    ])
    
    await message.answer(
        f"✅ Дата изменена на {transaction_date.strftime('%d.%m.%Y')}",
        reply_markup=keyboard
    )
    await state.clear()

# Запуск
async def main():
    logger.info("🚀 Запуск бота...")
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Бот остановлен")