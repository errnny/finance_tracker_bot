from aiogram.fsm.state import State, StatesGroup


class TransactionState(StatesGroup):
    """Состояния для добавления транзакции"""
    waiting_for_type = State()
    waiting_for_amount = State()
    waiting_for_category = State()
    waiting_for_date = State()


class EditState(StatesGroup):
    """Состояния для редактирования транзакции"""
    waiting_for_new_amount = State()
    waiting_for_new_category = State()
    waiting_for_new_date = State()