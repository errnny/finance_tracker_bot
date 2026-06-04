import os
import sys
import logging
from datetime import datetime
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
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
    waiting_for_type = State()  # доход/расход
    waiting_for_amount = State()
    waiting_for_category = State()
    waiting_for_date = State()

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
        # Общая статистика
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
        
        # Статистика по категориям расходов
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
        
        # Статистика по категориям доходов
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
        
        return {
            'total_income': float(total_income),
            'total_expense': float(total_expense),
            'balance': float(total_income) - float(total_expense),
            'expenses_by_category': [(r['category'], float(r['total'])) for r in expenses_by_category],
            'income_by_category': [(r['category'], float(r['total'])) for r in income_by_category]
        }
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
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Добавить транзакцию", callback_data="add_new")],
            [InlineKeyboardButton(text="📅 За 7 дней", callback_data="stats_7"),
             InlineKeyboardButton(text="📅 За 90 дней", callback_data="stats_90")]
        ])
        
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
    except Exception as e:
        await callback.message.answer(f"❌ Ошибка получения статистики: {e}")

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
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Назад", callback_data="show_stats")],
        [InlineKeyboardButton(text="➕ Добавить", callback_data="add_new")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")

@dp.callback_query(F.data == "add_new")
async def add_new_transaction(callback: CallbackQuery, state: FSMContext):
    """Возврат к добавлению транзакции"""
    await state.clear()
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Доход", callback_data="type_income")],
        [InlineKeyboardButton(text="💸 Расход", callback_data="type_expense")]
    ])
    await callback.message.edit_text("Выберите тип транзакции:", reply_markup=keyboard)

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
    
    await callback.message.edit_text(
        f"{emoji} Выбрано: {'Доход' if trans_type == 'income' else 'Расход'}\n\n"
        f"Введите сумму (например: 1500 или 1500.50):"
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
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=cat, callback_data=f"cat_{cat}")]
            for cat in categories
        ])
        
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
    
    await callback.message.edit_text(
        f"📁 Категория: {category}\n\n"
        f"Введите дату {type_name} (ДД.ММ.ГГГГ) или напишите 'сегодня':"
    )
    await state.set_state(TransactionState.waiting_for_date)

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
        
        await message.answer(
            f"✅ {type_name} сохранён!\n\n"
            f"{type_emoji} {amount}₽\n"
            f"📁 {category}\n"
            f"📅 {transaction_date.strftime('%d.%m.%Y')}\n\n"
            f"Добавить ещё? Нажмите /start"
        )
    except Exception as e:
        await message.answer(f"❌ Ошибка сохранения: {e}")
    
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