"""Состояния FSM для сбора заявки на обмен валюты."""
from aiogram.fsm.state import State, StatesGroup


class ExchangeForm(StatesGroup):
    give_currency = State()   # что клиент отдаёт
    get_currency = State()    # что клиент хочет получить
    amount_side = State()     # что фиксируем: сумму к отдаче или к получению
    amount = State()          # сумма
    contact = State()         # контакт для связи
    confirm = State()         # подтверждение заявки


class SetRates(StatesGroup):
    """Пошаговый ввод курсов админом (команда /setrate)."""
    kzt_give_kzt = State()   # тенге за 1 рубль (клиент отдаёт тенге)
    kzt_give_rub = State()   # тенге за 1 рубль (клиент отдаёт рубли)
    thb_give_thb = State()   # рублей за 1 бат (клиент отдаёт баты)
    thb_give_rub = State()   # рублей за 1 бат (клиент отдаёт рубли)
