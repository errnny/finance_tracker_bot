import logging
from aiogram.types import CallbackQuery, InlineKeyboardMarkup
from aiogram.exceptions import TelegramBadRequest

logger = logging.getLogger(__name__)


async def safe_edit_message(callback: CallbackQuery, text: str, 
                           reply_markup: InlineKeyboardMarkup = None, 
                           parse_mode: str = "Markdown"):
    """Безопасное редактирование сообщения с обработкой ошибок"""
    try:
        await callback.message.edit_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            logger.debug("Сообщение не изменилось, пропускаем редактирование")
        else:
            raise
    except Exception as e:
        logger.error(f"Ошибка при редактировании сообщения: {e}")
        raise


def format_date(date_obj):
    """Форматирование даты"""
    if hasattr(date_obj, 'strftime'):
        return date_obj.strftime('%d.%m.%Y')
    return str(date_obj)


def format_date_short(date_obj):
    """Краткое форматирование даты"""
    if hasattr(date_obj, 'strftime'):
        return date_obj.strftime('%d.%m')
    return str(date_obj)