import os
from pathlib import Path
from dotenv import load_dotenv

# Загрузка .env
BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / '.env'
load_dotenv(dotenv_path=ENV_PATH, override=True)

# Токен бота
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не найден в .env файле!")

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
