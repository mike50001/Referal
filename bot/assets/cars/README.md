# Фото машин

Каждая папка соответствует машине из списка `CARS` в `bot/content.py`
(имя папки = `id` машины).

Положи фото машины в её папку — бот покажет их альбомом в карточке.

## Правила

- Форматы: `.jpg`, `.jpeg`, `.png`, `.webp`
- Максимум **10** фото на машину (лимит Telegram на альбом)
- Порядок показа — по имени файла, поэтому называй `1.jpg`, `2.jpg`, `3.jpg`…

## Папки

| id | Машина |
|---|---|
| `ford_everest` | Ford Everest Bi-Turbo 2023 |
| `byd_seal` | BYD Seal Performance 2024 |
| `toyota_yaris` | Toyota Yaris 2023 |
| `nissan_almera` | Nissan Almera Turbo 2022 |
| `mazda2` | Mazda 2 2022 |

## Как добавить фото прямо на GitHub

1. Открой нужную папку в репозитории на github.com
2. **Add file → Upload files**
3. Перетащи фото, назови по порядку (`1.jpg`, `2.jpg`…)
4. **Commit changes** — Railway пересоберётся, фото появятся в боте
