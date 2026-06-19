import logging
import asyncpg
from config import DB_CONFIG

logger = logging.getLogger(__name__)


async def init_db():
    """Создаем таблицу если не существует"""
    conn = await asyncpg.connect(**DB_CONFIG)
    try:
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
        logger.info("База данных инициализирована")
    finally:
        await conn.close()


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
        logger.info(f"Транзакция сохранена: {trans_type} {amount}₽, {category}, {date}")
    finally:
        await conn.close()


async def get_stats(user_id: int, period_days: int = 30):
    """Получаем статистику за период"""
    conn = await asyncpg.connect(**DB_CONFIG)
    try:
        total_income = await conn.fetchval(
            f"""
            SELECT COALESCE(SUM(amount), 0) 
            FROM transactions 
            WHERE user_id = $1 
            AND transaction_type = 'income'
            AND transaction_date >= CURRENT_DATE - INTERVAL '{period_days} days'
            """,
            user_id
        )
        
        total_expense = await conn.fetchval(
            f"""
            SELECT COALESCE(SUM(amount), 0) 
            FROM transactions 
            WHERE user_id = $1 
            AND transaction_type = 'expense'
            AND transaction_date >= CURRENT_DATE - INTERVAL '{period_days} days'
            """,
            user_id
        )
        
        expenses_by_category = await conn.fetch(
            f"""
            SELECT category, SUM(amount) as total
            FROM transactions 
            WHERE user_id = $1 
            AND transaction_type = 'expense'
            AND transaction_date >= CURRENT_DATE - INTERVAL '{period_days} days'
            GROUP BY category
            ORDER BY total DESC
            """,
            user_id
        )
        
        income_by_category = await conn.fetch(
            f"""
            SELECT category, SUM(amount) as total
            FROM transactions 
            WHERE user_id = $1 
            AND transaction_type = 'income'
            AND transaction_date >= CURRENT_DATE - INTERVAL '{period_days} days'
            GROUP BY category
            ORDER BY total DESC
            """,
            user_id
        )
        
        all_transactions = await conn.fetch(
            f"""
            SELECT id, transaction_type, amount, category, transaction_date, created_at
            FROM transactions 
            WHERE user_id = $1 
            AND transaction_date >= CURRENT_DATE - INTERVAL '{period_days} days'
            ORDER BY transaction_date DESC, created_at DESC
            """,
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
        logger.info(f"Транзакция {transaction_id} удалена")
    finally:
        await conn.close()


async def update_transaction(transaction_id: int, user_id: int, 
                            amount: float = None, category: str = None, date = None):
    """Обновляем транзакцию"""
    conn = await asyncpg.connect(**DB_CONFIG)
    try:
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
            logger.info(f"Транзакция {transaction_id} обновлена")
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