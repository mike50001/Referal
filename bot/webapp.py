"""Веб-сервер Telegram Mini App: мгновенный калькулятор обмена.

Отдаёт HTML-страницу калькулятора и JSON с текущими курсами обменника.
Работает в том же процессе, что и бот (порт берётся из переменной PORT,
которую задаёт Railway).
"""
from __future__ import annotations

import logging
import os

from aiohttp import web

from bot import rates

logger = logging.getLogger("exchange-bot.webapp")

PAGE = """<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no">
<title>Misha Cash — калькулятор</title>
<script src="https://telegram.org/js/telegram-web-app.js"></script>
<style>
  :root {
    --bg: var(--tg-theme-bg-color, #0f1115);
    --card: var(--tg-theme-secondary-bg-color, #1b1e26);
    --text: var(--tg-theme-text-color, #ffffff);
    --hint: var(--tg-theme-hint-color, #8a8f98);
    --accent: var(--tg-theme-button-color, #2ea6ff);
    --accent-text: var(--tg-theme-button-text-color, #ffffff);
  }
  * { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }
  body {
    margin: 0; padding: 16px;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: var(--bg); color: var(--text);
  }
  h1 { font-size: 20px; margin: 4px 0 16px; text-align: center; }
  .brand { color: var(--accent); }
  .card { background: var(--card); border-radius: 16px; padding: 16px; margin-bottom: 14px; }
  label { display: block; font-size: 13px; color: var(--hint); margin-bottom: 8px; }
  .row { display: flex; gap: 10px; align-items: center; }
  input, select {
    width: 100%; padding: 14px; border-radius: 12px; border: none;
    background: var(--bg); color: var(--text); font-size: 18px; outline: none;
  }
  select { appearance: none; -webkit-appearance: none; }
  input:focus, select:focus { box-shadow: 0 0 0 2px var(--accent); }
  .swap {
    display: block; margin: 6px auto; width: 44px; height: 44px; border-radius: 50%;
    border: none; background: var(--accent); color: var(--accent-text);
    font-size: 20px; cursor: pointer;
  }
  .result { text-align: center; padding: 6px 0; }
  .result .big { font-size: 30px; font-weight: 700; }
  .result .rate { font-size: 13px; color: var(--hint); margin-top: 6px; }
  .muted { color: var(--hint); font-size: 13px; text-align: center; margin-top: 4px; }
</style>
</head>
<body>
  <h1>💱 <span class="brand">Misha Cash</span> — калькулятор</h1>

  <div class="card">
    <label>Отдаёте</label>
    <div class="row">
      <input id="amount" type="text" inputmode="decimal" value="1000" placeholder="Сумма">
      <select id="give"></select>
    </div>
  </div>

  <button class="swap" id="swap" title="Поменять">⇅</button>

  <div class="card">
    <label>Получаете</label>
    <div class="row">
      <select id="get" style="flex:0 0 auto; width:130px;"></select>
    </div>
    <div class="result">
      <div class="big" id="out">—</div>
      <div class="rate" id="rateline"></div>
    </div>
  </div>

  <div class="muted" id="hint">Загрузка курсов…</div>

<script>
  const LABELS = { RUB: "🇷🇺 Рубль", KZT: "🇰🇿 Тенге", THB: "🇹🇭 Бат" };
  const CODES = ["RUB", "KZT", "THB"];
  let PAIRS = {};

  const tg = window.Telegram ? window.Telegram.WebApp : null;
  if (tg) { tg.ready(); tg.expand(); }

  const $ = (id) => document.getElementById(id);
  const giveSel = $("give"), getSel = $("get");

  for (const c of CODES) {
    for (const sel of [giveSel, getSel]) {
      const o = document.createElement("option");
      o.value = c; o.textContent = LABELS[c];
      sel.appendChild(o);
    }
  }
  giveSel.value = "RUB";
  getSel.value = "KZT";

  function fmt(v) {
    if (!isFinite(v)) return "—";
    let dec = Math.abs(v) >= 1 ? 2 : 4;
    let s = v.toLocaleString("ru-RU", { minimumFractionDigits: 0, maximumFractionDigits: dec });
    return s;
  }

  function calc() {
    const give = giveSel.value, get = getSel.value;
    const amount = parseFloat(($("amount").value || "").replace(/\\s/g, "").replace(",", "."));
    if (give === get) {
      $("out").textContent = (isFinite(amount) ? fmt(amount) : "—") + " " + get;
      $("rateline").textContent = "Одинаковые валюты";
      return;
    }
    const rate = PAIRS[give + "_" + get];
    if (rate === undefined) {
      $("out").textContent = "—";
      $("rateline").textContent = "Курс для этой пары не задан";
      return;
    }
    if (!isFinite(amount) || amount <= 0) {
      $("out").textContent = "—";
      $("rateline").textContent = "";
      return;
    }
    $("out").textContent = fmt(amount * rate) + " " + get;
    $("rateline").textContent = "Курс: 1 " + give + " = " + fmt(rate) + " " + get;
  }

  $("swap").addEventListener("click", () => {
    const g = giveSel.value; giveSel.value = getSel.value; getSel.value = g;
    calc();
  });
  ["input", "change"].forEach(ev => {
    $("amount").addEventListener(ev, calc);
    giveSel.addEventListener(ev, calc);
    getSel.addEventListener(ev, calc);
  });

  fetch("/api/rates")
    .then(r => r.json())
    .then(data => {
      PAIRS = data.pairs || {};
      $("hint").textContent = "Курс ориентировочный. Для заявки вернитесь в бот.";
      calc();
    })
    .catch(() => { $("hint").textContent = "Не удалось загрузить курсы. Попробуйте позже."; });
</script>
</body>
</html>
"""


async def handle_index(request: web.Request) -> web.Response:
    return web.Response(text=PAGE, content_type="text/html")


async def handle_rates(request: web.Request) -> web.Response:
    return web.json_response({"pairs": rates.all_pair_rates()})


async def handle_health(request: web.Request) -> web.Response:
    return web.Response(text="ok")


def create_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/", handle_index)
    app.router.add_get("/app", handle_index)
    app.router.add_get("/api/rates", handle_rates)
    app.router.add_get("/health", handle_health)
    return app


async def start_webapp() -> web.AppRunner:
    """Запускает веб-сервер и возвращает runner (для последующей остановки)."""
    runner = web.AppRunner(create_app())
    await runner.setup()
    port = int(os.getenv("PORT", "8080"))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info("Mini App веб-сервер запущен на порту %s", port)
    return runner
