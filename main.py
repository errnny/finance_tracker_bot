import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from config import BOT_TOKEN, DB_CONFIG
from database import init_db
from handlers import common, add_transaction, statistics, edit_transaction, delete_transaction

# Логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Подключение роутеров
dp.include_router(common.router)
dp.include_router(add_transaction.router)
dp.include_router(statistics.router)
dp.include_router(edit_transaction.router)
dp.include_router(delete_transaction.router)


async def main():
    logger.info("Запуск бота...")
    
    # Инициализация БД
    await init_db()
    
    # Запуск polling
    await dp.start_polling(bot)


if __name__ == "__main__":
    import asyncio
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен")