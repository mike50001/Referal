"""Состояния FSM для сбора заявки на обмен валюты."""
from aiogram.fsm.state import State, StatesGroup


class ExchangeForm(StatesGroup):
    give_currency = State()   # что клиент отдаёт
    get_currency = State()    # что клиент хочет получить
    amount_side = State()     # что фиксируем: сумму к отдаче или к получению
    amount = State()          # сумма
    contact = State()         # контакт для связи
    confirm = State()         # подтверждение заявки
