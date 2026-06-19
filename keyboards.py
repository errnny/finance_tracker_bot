from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import INCOME_CATEGORIES, EXPENSE_CATEGORIES


def main_menu_keyboard():
    """Главное меню"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Доход", callback_data="type_income")],
        [InlineKeyboardButton(text="💸 Расход", callback_data="type_expense")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="show_stats")]
    ])


def type_selection_keyboard():
    """Выбор типа транзакции"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Доход", callback_data="type_income")],
        [InlineKeyboardButton(text="💸 Расход", callback_data="type_expense")]
    ])


def categories_keyboard(trans_type: str):
    """Клавиатура категорий"""
    categories = INCOME_CATEGORIES if trans_type == "income" else EXPENSE_CATEGORIES
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=cat, callback_data=f"cat_{cat}")]
        for cat in categories
    ])


def categories_with_cancel_keyboard(trans_type: str):
    """Клавиатура категорий с кнопкой отмены"""
    categories = INCOME_CATEGORIES if trans_type == "income" else EXPENSE_CATEGORIES
    keyboard = [
        [InlineKeyboardButton(text=cat, callback_data=f"cat_{cat}")]
        for cat in categories
    ]
    keyboard.append([InlineKeyboardButton(text=" Отмена", callback_data="cancel_transaction")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def stats_keyboard(days: int = 30):
    """Клавиатура статистики"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="show_stats")],
        [InlineKeyboardButton(text="📅 За 7 дней", callback_data="stats_7"),
         InlineKeyboardButton(text="📅 За 90 дней", callback_data="stats_90")],
        [InlineKeyboardButton(text="✏️ Редактировать", callback_data="edit_list"),
         InlineKeyboardButton(text="️🗑️ Удалить", callback_data="delete_list")],
        [InlineKeyboardButton(text="➕ Добавить транзакцию", callback_data="add_new")]
    ])


def stats_period_keyboard():
    """Клавиатура для периодов статистики"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Назад к 30 дням", callback_data="show_stats")],
        [InlineKeyboardButton(text="✏️ Редактировать", callback_data="edit_list"),
         InlineKeyboardButton(text="🗑️ Удалить", callback_data="delete_list")],
        [InlineKeyboardButton(text="➕ Добавить", callback_data="add_new")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
    ])


def edit_menu_keyboard():
    """Меню редактирования транзакции"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Изменить сумму", callback_data="edit_amount")],
        [InlineKeyboardButton(text="📁 Изменить категорию", callback_data="edit_category")],
        [InlineKeyboardButton(text="📅 Изменить дату", callback_data="edit_date")],
        [InlineKeyboardButton(text="🔙 Назад к списку", callback_data="edit_list")]
    ])


def delete_confirm_keyboard(trans_id: int):
    """Подтверждение удаления"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"confirm_delete_{trans_id}")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="delete_list")]
    ])


def after_save_keyboard():
    """Клавиатура после сохранения транзакции"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить ещё", callback_data="add_new")],
        [InlineKeyboardButton(text="📊 Посмотреть статистику", callback_data="show_stats")]
    ])


def after_edit_keyboard():
    """Клавиатура после редактирования"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu_from_edit")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="show_stats")]
    ])


def cancel_keyboard():
    """Клавиатура с кнопкой отмены"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_transaction")]
    ])


def edit_cancel_keyboard():
    """Клавиатура отмены редактирования"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_edit")]
    ])

def edit_categories_keyboard(trans_type: str):
    """Клавиатура категорий для редактирования"""
    categories = INCOME_CATEGORIES if trans_type == "income" else EXPENSE_CATEGORIES
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=cat, callback_data=f"edit_cat_{cat}")]
        for cat in categories
    ])