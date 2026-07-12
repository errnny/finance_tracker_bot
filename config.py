import os
import re
from pathlib import Path
from dotenv import load_dotenv

# Загрузка .env для локалки
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / '.env', override=True)

def clean_bot_token(raw_value: str | None) -> str:
    """Агрессивная очистка токена от кавычек, пробелов и переносов"""
    if not raw_value:
        raise ValueError("Переменная BOT_TOKEN пуста!")
        
    # 1. Убираем пробелы и скрытые переносы строк
    token = raw_value.strip().replace('\n', '').replace('\r', '')
    
    # 2. Убираем парные кавычки в начале и конце
    if len(token) >= 2 and token[0] == token[-1] and token[0] in "\"'":
        token = token[1:-1]
        
    # 3. На всякий случай вырезаем ВСЕ кавычки (токен Telegram их не содержит)
    token = token.replace('"', '').replace("'", '')
    
    # 4. Финальная проверка формата
    if not re.match(r'^\d+[A-Za-z0-9_-]{30,}$', token):
        print(f"⚠️  Внимание: Токен может быть повреждён. Сырое значение: {repr(raw_value)}")
        
    return token

# === ПРИМЕНЯЕМ ОЧИСТКУ ===
BOT_TOKEN = clean_bot_token(os.getenv("BOT_TOKEN"))

# === ЖЁСТКАЯ ДИАГНОСТИКА ===
print("\n" + "="*50)
print(" ДИАГНОСТИКА ТОКЕНА")
print("="*50)
print(f"📥 Сырое из env: {repr(os.getenv('BOT_TOKEN'))}")
print(f"🧼 После очистки: {repr(BOT_TOKEN)}")
print(f" Длина: {len(BOT_TOKEN)}")
print("="*50 + "\n")

if not BOT_TOKEN:
    raise SystemExit("❌ ОШИБКА: Токен не найден или пуст!")

# Остальные переменные (тоже чистим на всякий случай)
def clean(v):
    return v.strip().replace('"', '').replace("'", '') if v else v

DB_CONFIG = {
    "user": clean(os.getenv("DB_USER", "postgres")),
    "password": clean(os.getenv("DB_PASSWORD", "")),
    "host": clean(os.getenv("DB_HOST", "localhost")),
    "port": int(clean(os.getenv("DB_PORT", "5432"))),
    "database": clean(os.getenv("DB_NAME", "finance_tracker")),
}

INCOME_CATEGORIES = ["Зарплата", "Премия", "Подработка", "Инвестиции", "Подарок", "Другое"]
EXPENSE_CATEGORIES = ["Еда", "Транспорт", "Жильё", "Развлечения", "Одежда", "Здоровье", "Связь", "Другое"]

print("✅ Конфигурация успешно загружена!")
