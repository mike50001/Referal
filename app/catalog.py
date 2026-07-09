"""Каталог контента на продажу.

Цены указаны в Telegram Stars (XTR). Поле `file` — путь к файлу, который
бот отправит после успешной оплаты. Можно заменить на file_id уже
загруженного в Telegram файла, чтобы не хранить файлы в репозитории.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Product:
    id: str
    title: str
    description: str
    price_stars: int  # цена в Telegram Stars (XTR)
    file: str  # путь к файлу или Telegram file_id


CATALOG: dict[str, Product] = {
    "photo_pack_1": Product(
        id="photo_pack_1",
        title="Фотосет №1",
        description="10 эксклюзивных фото",
        price_stars=100,
        file="content/photo_pack_1.zip",
    ),
    "photo_pack_2": Product(
        id="photo_pack_2",
        title="Фотосет №2",
        description="20 фото + бонус",
        price_stars=200,
        file="content/photo_pack_2.zip",
    ),
    "video_1": Product(
        id="video_1",
        title="Видео",
        description="Персональное видео",
        price_stars=350,
        file="content/video_1.mp4",
    ),
}


def get(product_id: str) -> Product | None:
    return CATALOG.get(product_id)
