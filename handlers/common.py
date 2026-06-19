import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from keyboards import main_menu_keyboard, type_selection_keyboard
from utils import safe_edit_message

logger = logging.getLogger(__name__)
router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    """Главное меню"""
    await state.clear()
    await message.answer(
        " Привет! Я финансовый трекер.\n\n"
        "Выберите действие:",
        reply_markup=main_menu_keyboard()
    )


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    """Отмена текущей операции"""
    await state.clear()
    await message.answer(
        "❌ Операция отменена\n\n"
        "Выберите действие:",
        reply_markup=main_menu_keyboard()
    )


@router.callback_query(F.data == "cancel_transaction")
async def cancel_transaction(callback: CallbackQuery, state: FSMContext):
    """Отмена добавления транзакции"""
    await state.clear()
    await safe_edit_message(
        callback,
        "❌ Добавление транзакции отменено\n\n"
        "Выберите действие:",
        main_menu_keyboard()
    )


@router.callback_query(F.data == "cancel_edit")
async def cancel_edit(callback: CallbackQuery, state: FSMContext):
    """Отмена редактирования"""
    await state.clear()
    await safe_edit_message(callback, "❌ Редактирование отменено", None)


@router.callback_query(F.data == "add_new")
async def add_new_transaction(callback: CallbackQuery, state: FSMContext):
    """Возврат к добавлению транзакции"""
    await state.clear()
    await safe_edit_message(callback, "Выберите тип транзакции:", type_selection_keyboard())


@router.callback_query(F.data == "main_menu_from_edit")
async def main_menu_from_edit(callback: CallbackQuery):
    """Возврат в главное меню из редактирования"""
    await callback.message.answer(
        "👋 Привет! Я финансовый трекер.\n\n"
        "Выберите действие:",
        reply_markup=main_menu_keyboard()
    )

@router.callback_query(F.data == "main_menu")
async def go_to_main_menu(callback: CallbackQuery, state: FSMContext):
    """Переход в главное меню"""
    await state.clear()
    await safe_edit_message(
        callback,
        " Привет! Я финансовый трекер.\n\n"
        "Выберите действие:",
        main_menu_keyboard()
    )