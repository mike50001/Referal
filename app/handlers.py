"""Обработчики сообщений и платежей Telegram."""
import logging
from pathlib import Path

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    CallbackQuery,
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    LabeledPrice,
    Message,
    PreCheckoutQuery,
)

from config import OWNER_ID
from app import catalog, db, llm

logger = logging.getLogger(__name__)
router = Router()


def _catalog_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=f"{p.title} — ⭐ {p.price_stars}",
                callback_data=f"buy:{p.id}",
            )
        ]
        for p in catalog.CATALOG.values()
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await message.answer(
        "Привет! 💕 Рада тебя видеть. Пиши мне о чём угодно, "
        "а глянуть, что у меня есть, можно командой /shop."
    )


@router.message(Command("shop"))
async def cmd_shop(message: Message) -> None:
    await message.answer(
        "Вот что можно забрать себе 👇", reply_markup=_catalog_keyboard()
    )


@router.callback_query(F.data.startswith("buy:"))
async def on_buy(callback: CallbackQuery, bot: Bot) -> None:
    product_id = callback.data.split(":", 1)[1]
    product = catalog.get(product_id)
    if product is None:
        await callback.answer("Товар не найден", show_alert=True)
        return

    # Для Telegram Stars валюта XTR, provider_token не нужен, amount = число звёзд.
    await bot.send_invoice(
        chat_id=callback.from_user.id,
        title=product.title,
        description=product.description,
        payload=product.id,
        currency="XTR",
        prices=[LabeledPrice(label=product.title, amount=product.price_stars)],
    )
    await callback.answer()


@router.pre_checkout_query()
async def on_pre_checkout(query: PreCheckoutQuery) -> None:
    # Обязательно ответить в течение 10 секунд, иначе платёж отменится.
    await query.answer(ok=True)


@router.message(F.successful_payment)
async def on_successful_payment(message: Message, bot: Bot) -> None:
    payment = message.successful_payment
    product = catalog.get(payment.invoice_payload)
    user_id = message.from_user.id

    if product is None:
        logger.error("Оплачен неизвестный товар: %s", payment.invoice_payload)
        await message.answer(
            "Оплата получена, но товар не найден. Напиши владелице — всё решим 🙏"
        )
        return

    await db.record_purchase(
        user_id=user_id,
        product_id=product.id,
        stars=payment.total_amount,
        charge_id=payment.telegram_payment_charge_id,
    )

    await message.answer(f"Спасибо! 💖 Держи «{product.title}»:")
    await _deliver(bot, user_id, product)

    if OWNER_ID:
        await bot.send_message(
            OWNER_ID,
            f"💰 Продажа: {product.title} за ⭐ {payment.total_amount} "
            f"(user_id={user_id})",
        )


async def _deliver(bot: Bot, user_id: int, product: catalog.Product) -> None:
    """Отправить купленный контент. Поддерживает путь к файлу или Telegram file_id."""
    path = Path(product.file)
    try:
        if path.exists():
            if path.suffix.lower() in {".mp4", ".mov"}:
                await bot.send_video(user_id, FSInputFile(path))
            elif path.suffix.lower() in {".jpg", ".jpeg", ".png"}:
                await bot.send_photo(user_id, FSInputFile(path))
            else:
                await bot.send_document(user_id, FSInputFile(path))
        else:
            # Считаем, что product.file — это Telegram file_id
            await bot.send_document(user_id, product.file)
    except Exception:  # noqa: BLE001
        logger.exception("Не удалось доставить товар %s", product.id)
        await bot.send_message(
            user_id,
            "Упс, не получилось отправить файл. Напиши владелице — вышлем вручную 🙏",
        )


@router.message(F.text)
async def on_text(message: Message) -> None:
    """Свободный диалог: ответ генерирует Claude на основе истории."""
    user_id = message.from_user.id
    text = message.text

    history = await db.get_history(user_id)
    await db.add_message(user_id, "user", text)

    try:
        answer = await llm.reply(history, text)
    except Exception:  # noqa: BLE001
        logger.exception("Ошибка запроса к LLM")
        answer = "Ой, связь подвисла 🙈 напиши ещё разок?"

    await db.add_message(user_id, "assistant", answer)
    await message.answer(answer)
