"""Веб-сервер Telegram Mini App: мгновенный калькулятор обмена.

Отдаёт HTML-страницу калькулятора и JSON с текущими курсами обменника.
Работает в том же процессе, что и бот (порт берётся из переменной PORT,
которую задаёт Railway).
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import pathlib
from urllib.parse import parse_qsl

from aiohttp import web

from bot import rates

logger = logging.getLogger("exchange-bot.webapp")

_BG_PATH = pathlib.Path(__file__).resolve().parent / "assets" / "bg.png"

PAGE = """<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no">
<title>Misha Cash — калькулятор</title>
<script src="https://telegram.org/js/telegram-web-app.js"></script>
<style>
  * { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }
  body {
    margin: 0; padding: 18px; min-height: 100vh;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    color: #f4ead0; position: relative;
  }
  body::before {
    content: ""; position: fixed; inset: 0; z-index: -2;
    background: url('/bg.png') center center / cover no-repeat;
  }
  body::after {
    content: ""; position: fixed; inset: 0; z-index: -1;
    background: linear-gradient(180deg, rgba(5,12,14,.66) 0%, rgba(4,9,11,.82) 60%, rgba(3,7,9,.9) 100%);
  }
  .wrap { max-width: 460px; margin: 0 auto; }
  .frame {
    border-radius: 22px; padding: 18px 16px 16px;
    background: linear-gradient(180deg, rgba(12,28,30,.72), rgba(6,16,18,.82));
    border: 1px solid rgba(232,184,64,.38);
    box-shadow: 0 18px 50px rgba(0,0,0,.5), inset 0 1px 0 rgba(255,220,150,.08);
  }
  .gold {
    background: linear-gradient(180deg,#fdefb0 0%,#e9c15a 45%,#c8971f 100%);
    -webkit-background-clip: text; background-clip: text; color: transparent;
  }
  h1 { text-align: center; font-size: 27px; font-weight: 800; letter-spacing: .5px; margin: 2px 0 3px; }
  .sub { display: block; text-align: center; font-size: 12px; letter-spacing: 5px; margin-bottom: 4px; }
  .card {
    background: rgba(6,18,20,.6); border: 1px solid rgba(232,184,64,.28);
    border-radius: 16px; padding: 14px; margin-top: 14px;
  }
  label { display: block; font-size: 11px; letter-spacing: 1.5px; text-transform: uppercase; color: #b89a5c; margin-bottom: 9px; }
  .row { display: flex; gap: 10px; align-items: center; }
  input, select {
    width: 100%; padding: 14px; border-radius: 12px; font-size: 18px; outline: none;
    border: 1px solid rgba(232,184,64,.25); background: rgba(0,0,0,.35); color: #fff;
  }
  select { appearance: none; -webkit-appearance: none; font-weight: 600; }
  input:focus, select:focus { border-color: #e8b840; box-shadow: 0 0 0 2px rgba(232,184,64,.35); }
  .swap {
    display: block; margin: -8px auto; width: 46px; height: 46px; border-radius: 50%;
    border: none; cursor: pointer; font-size: 20px; color: #3a2a00; font-weight: 800;
    background: linear-gradient(180deg,#fbe08a,#d4a017); position: relative; z-index: 2;
    box-shadow: 0 6px 16px rgba(0,0,0,.45), inset 0 1px 0 rgba(255,255,255,.5);
  }
  .result { text-align: center; padding: 8px 0 2px; }
  .result .big { font-size: 33px; font-weight: 800; }
  .result .rate { font-size: 12.5px; color: #b89a5c; margin-top: 6px; }
  .rrow {
    display: flex; justify-content: space-between; align-items: center;
    padding: 9px 2px; border-bottom: 1px solid rgba(232,184,64,.14); font-size: 14px;
  }
  .rrow:last-child { border-bottom: none; }
  .rrow .v { font-weight: 800; font-size: 16px; }
  .rrow .u { color: #9c8a5c; font-size: 10.5px; margin-left: 4px; }
  .ratenote { text-align: center; font-size: 13px; color: #b89a5c; margin-top: 10px; min-height: 16px; }
  .submit {
    display: block; width: 100%; margin-top: 16px; padding: 15px; border: none;
    border-radius: 14px; font-size: 16px; font-weight: 800; color: #3a2a00; cursor: pointer;
    background: linear-gradient(180deg,#fbe08a,#d4a017);
    box-shadow: 0 8px 20px rgba(0,0,0,.4), inset 0 1px 0 rgba(255,255,255,.5);
  }
  .submit:active { transform: translateY(1px); }
  .muted { text-align: center; font-size: 12px; color: #9c8a5c; margin-top: 14px; }
</style>
</head>
<body>
  <div class="wrap">
   <div class="frame">
    <h1><span class="gold">MISHA CASH</span></h1>
    <div class="sub">🌴 <span class="gold">ОБМЕН&nbsp;ВАЛЮТ</span> 🌴</div>

    <div class="card">
      <label>Отдаёте</label>
      <div class="row">
        <input id="amountGive" type="text" inputmode="decimal" value="1000" placeholder="Сумма">
        <select id="give"></select>
      </div>
    </div>

    <button class="swap" id="swap" title="Поменять">⇅</button>

    <div class="card">
      <label>Получаете</label>
      <div class="row">
        <input id="amountGet" type="text" inputmode="decimal" placeholder="Сумма">
        <select id="get"></select>
      </div>
      <div class="ratenote" id="rateline"></div>
    </div>

    <button class="submit" id="submit">📩 Оформить заявку</button>

    <div class="card">
      <label>📈 Курсы обменника</label>
      <div id="rateslist"></div>
    </div>

    <div class="muted" id="hint">Загрузка курсов…</div>
   </div>
  </div>

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
  giveSel.value = "KZT";
  getSel.value = "RUB";

  function fmt(v) {
    if (!isFinite(v)) return "—";
    let dec = Math.abs(v) >= 1 ? 2 : 4;
    let s = v.toLocaleString("ru-RU", { minimumFractionDigits: 0, maximumFractionDigits: dec });
    return s;
  }

  const amtGive = $("amountGive"), amtGet = $("amountGet");
  let lastEdited = "give";

  function parseAmt(v) { return parseFloat((v || "").replace(/\\s/g, "").replace(",", ".")); }

  function calc() {
    const give = giveSel.value, get = getSel.value;
    const rate = (give === get) ? 1 : PAIRS[give + "_" + get];
    if (rate === undefined) {
      $("rateline").textContent = "Курс для этой пары не задан";
      if (lastEdited === "give") amtGet.value = ""; else amtGive.value = "";
      return;
    }
    if (lastEdited === "give") {
      const a = parseAmt(amtGive.value);
      amtGet.value = (isFinite(a) && a > 0) ? fmt(a * rate) : "";
    } else {
      const b = parseAmt(amtGet.value);
      amtGive.value = (isFinite(b) && b > 0) ? fmt(b / rate) : "";
    }
    $("rateline").textContent = (give === get) ? "" : ("Курс: 1 " + give + " = " + fmt(rate) + " " + get);
  }

  $("swap").addEventListener("click", () => {
    const g = giveSel.value; giveSel.value = getSel.value; getSel.value = g;
    calc();
  });

  $("submit").addEventListener("click", () => {
    const give = giveSel.value, get = getSel.value;
    const amount = parseAmt(amtGive.value);
    const result = parseAmt(amtGet.value);
    if (!isFinite(amount) || amount <= 0) {
      if (tg && tg.showAlert) tg.showAlert("Введите сумму больше нуля.");
      else alert("Введите сумму больше нуля.");
      return;
    }
    const order = { type: "order", give, get, amount, result: (isFinite(result) ? result : null) };

    if (!tg) {
      alert("Оформление заявки работает только внутри Telegram.");
      return;
    }

    // Открыто через кнопку в боте (reply): initData пустой — шлём через sendData.
    if (!tg.initData) {
      if (tg.sendData) { tg.sendData(JSON.stringify(order)); }  // закроет приложение
      else { alert("Откройте приложение через кнопку в боте."); }
      return;
    }

    // Открыто через меню/ссылку: есть initData — шлём на сервер с проверкой подписи.
    const btn = $("submit"); btn.disabled = true; const old = btn.textContent;
    btn.textContent = "Отправляем…";
    fetch("/api/order", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ initData: tg.initData, give, get, amount, result })
    })
    .then(r => r.json())
    .then(j => {
      if (j.ok) {
        const done = () => { if (tg.close) tg.close(); };
        if (tg.showAlert) tg.showAlert("✅ Заявка отправлена! Менеджер ответит в течение 10 минут.", done);
        else { alert("Заявка отправлена! Менеджер ответит в течение 10 минут."); done(); }
      } else {
        (tg.showAlert || alert)("Не удалось отправить заявку. Попробуйте позже.");
        btn.disabled = false; btn.textContent = old;
      }
    })
    .catch(() => {
      (tg.showAlert || alert)("Ошибка сети. Попробуйте позже.");
      btn.disabled = false; btn.textContent = old;
    });
  });
  amtGive.addEventListener("input", () => { lastEdited = "give"; calc(); });
  amtGet.addEventListener("input", () => { lastEdited = "get"; calc(); });
  giveSel.addEventListener("change", calc);
  getSel.addEventListener("change", calc);

  function renderRates(rows) {
    $("rateslist").innerHTML = (rows || []).map(r =>
      '<div class="rrow"><span>' + r.title + '</span>' +
      '<span><span class="v gold">' + r.value + '</span>' +
      '<span class="u">' + r.unit + '</span></span></div>'
    ).join("");
  }

  fetch("/api/rates")
    .then(r => r.json())
    .then(data => {
      PAIRS = data.pairs || {};
      renderRates(data.rows);
      $("hint").textContent = "Курс ориентировочный. После заявки менеджер ответит в течение 10 минут.";
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
    return web.json_response({
        "pairs": rates.all_pair_rates(),
        "rows": rates.display_rows(),
    })


async def handle_bg(request: web.Request) -> web.StreamResponse:
    if _BG_PATH.exists():
        return web.FileResponse(_BG_PATH)
    return web.Response(status=404)


async def handle_health(request: web.Request) -> web.Response:
    return web.Response(text="ok")


def _validate_init_data(init_data: str, bot_token: str) -> dict | None:
    """Проверяет подпись Telegram WebApp initData. Возвращает данные user или None."""
    if not init_data:
        return None
    try:
        parsed = dict(parse_qsl(init_data, keep_blank_values=True))
    except Exception:
        return None
    received_hash = parsed.pop("hash", None)
    if not received_hash:
        return None
    data_check = "\n".join(f"{k}={parsed[k]}" for k in sorted(parsed))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    computed = hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(computed, received_hash):
        return None
    try:
        return json.loads(parsed.get("user", ""))
    except Exception:
        return None


async def handle_order(request: web.Request) -> web.Response:
    """Заявка из Mini App: проверяем подпись и шлём менеджеру."""
    from bot.handlers.client import CLIENT_ID_MARKER

    bot = request.app["bot"]
    config = request.app["config"]
    try:
        body = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "bad_json"}, status=400)

    user = _validate_init_data(body.get("initData", ""), config.bot_token)
    if not user:
        return web.json_response({"ok": False, "error": "auth"}, status=403)

    give, get = body.get("give"), body.get("get")
    amount, result = body.get("amount"), body.get("result")
    if not give or not get or amount is None:
        return web.json_response({"ok": False, "error": "data"}, status=400)

    uid = user.get("id")
    name = user.get("first_name") or "клиент"
    uname = user.get("username")
    username_part = f" (@{uname})" if uname else ""
    receive = (
        f"≈ <b>{rates.fmt(float(result))} {get}</b>" if result is not None
        else f"<b>{get}</b> <i>(рассчитает менеджер)</i>"
    )
    quote = rates.quote_text(give, get)
    rate_line = f"📈 Курс: {quote}\n" if quote else ""

    text = (
        "🆕 <b>Новая заявка (приложение)</b>\n\n"
        f"👤 Клиент: <a href=\"tg://user?id={uid}\">{name}</a>{username_part}\n"
        f"💸 Отдаёт: <b>{rates.fmt(float(amount))} {give}</b>\n"
        f"💰 Получает: {receive}\n"
        f"{rate_line}"
        f"{CLIENT_ID_MARKER} {uid}\n"
        "↩️ Чтобы ответить клиенту — ответьте (reply) на это сообщение."
    )
    try:
        await bot.send_message(config.admin_chat_id, text)
    except Exception:
        return web.json_response({"ok": False, "error": "send"}, status=500)
    return web.json_response({"ok": True})


def create_app(bot=None, config=None) -> web.Application:
    app = web.Application()
    app["bot"] = bot
    app["config"] = config
    app.router.add_get("/", handle_index)
    app.router.add_get("/app", handle_index)
    app.router.add_get("/api/rates", handle_rates)
    app.router.add_post("/api/order", handle_order)
    app.router.add_get("/bg.png", handle_bg)
    app.router.add_get("/health", handle_health)
    return app


async def start_webapp(bot=None, config=None) -> web.AppRunner:
    """Запускает веб-сервер и возвращает runner (для последующей остановки)."""
    runner = web.AppRunner(create_app(bot, config))
    await runner.setup()
    port = int(os.getenv("PORT", "8080"))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info("Mini App веб-сервер запущен на порту %s", port)
    return runner
