import os
from pathlib import Path

# Загрузка .env для локальной разработки
from dotenv import load_dotenv
BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / '.env'
if ENV_PATH.exists():
    load_dotenv(dotenv_path=ENV_PATH, override=True)


def clean_value(value):
    """
    Жёстко очищает значение от кавычек.
    Работает даже если Railway добавляет кавычки.
    """
    if value is None:
        return None
    
    value = str(value).strip()
    
    # Убираем ВСЕ кавычки по краям (даже если их несколько)
    while len(value) >= 2 and (
        (value[0] == '"' and value[-1] == '"') or
        (value[0] == "'" and value[-1] == "'")
    ):
        value = value[1:-1]
    
    return value


# Получаем токен и чистим его
BOT_TOKEN = clean_value(os.getenv("BOT_TOKEN"))

# Отладка
print(f"\n{'='*60}")
print(f"🔍 ДИАГНОСТИКА")
print(f"{'='*60}")
print(f"Сырое значение: {repr(os.getenv('BOT_TOKEN'))}")
print(f"После очистки: {repr(BOT_TOKEN)}")
print(f"Длина: {len(BOT_TOKEN) if BOT_TOKEN else 0}")
print(f"{'='*60}\n")

if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN не найден!")

print("✅ Токен загружен успешно!")

# Настройки БД с очисткой
DB_CONFIG = {
    "user": clean_value(os.getenv("DB_USER", "postgres")),
    "password": clean_value(os.getenv("DB_PASSWORD", "")),
    "host": clean_value(os.getenv("DB_HOST", "localhost")),
    "port": int(clean_value(os.getenv("DB_PORT", "5432"))),
    "database": clean_value(os.getenv("DB_NAME", "finance_tracker")),
}

INCOME_CATEGORIES = ["Зарплата", "Премия", "Подработка", "Инвестиции", "Подарок", "Другое"]
EXPENSE_CATEGORIES = ["Еда", "Транспорт", "Жильё", "Развлечения", "Одежда", "Здоровье", "Связь", "Другое"]
