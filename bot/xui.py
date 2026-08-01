"""Клиент к API панели 3x-ui (MHSanaei, v2.x). Синхронный (httpx.Client).

Умеет: логин, получить inbound, добавить/продлить клиента, собрать ссылку vless://.
Эндпоинты — под /panel/api/inbounds/. Если у тебя другая версия панели и что-то
не так — правки в основном тут.
"""
import json
import time
import uuid as uuidlib
from urllib.parse import quote

import httpx

import config


class XUIError(Exception):
    pass


class XUI:
    def __init__(self):
        self.base = config.XUI_BASE_URL
        self._client = httpx.Client(timeout=20, verify=False, follow_redirects=True)
        self._logged_in = False

    def login(self):
        r = self._client.post(
            f"{self.base}/login",
            data={"username": config.XUI_USERNAME, "password": config.XUI_PASSWORD},
        )
        ok = r.status_code == 200 and r.json().get("success")
        if not ok:
            raise XUIError(f"Не удалось залогиниться в панель: {r.status_code} {r.text[:200]}")
        self._logged_in = True

    def _post(self, path: str, payload: dict):
        if not self._logged_in:
            self.login()
        r = self._client.post(f"{self.base}{path}", json=payload)
        if r.status_code in (401, 403):          # сессия протухла — перелогин
            self.login()
            r = self._client.post(f"{self.base}{path}", json=payload)
        data = r.json()
        if not data.get("success"):
            raise XUIError(f"API {path}: {data.get('msg')}")
        return data

    def get_inbound(self) -> dict:
        if not self._logged_in:
            self.login()
        r = self._client.get(f"{self.base}/panel/api/inbounds/get/{config.XUI_INBOUND_ID}")
        data = r.json()
        if not data.get("success"):
            raise XUIError(f"get inbound: {data.get('msg')}")
        return data["obj"]

    def add_or_extend(self, user_id: int, days: int):
        """Создаёт клиента, если его нет, иначе продлевает срок. Возвращает
        (client_uuid, email, expiry_ms, vless_link)."""
        inbound = self.get_inbound()
        email = f"tg{user_id}"
        now_ms = int(time.time() * 1000)
        add_ms = days * 86400 * 1000

        settings = json.loads(inbound["settings"])
        existing = next((c for c in settings.get("clients", [])
                         if c.get("email") == email), None)

        if existing:
            base = existing.get("expiryTime") or 0
            base = base if base > now_ms else now_ms
            new_expiry = base + add_ms
            existing["expiryTime"] = new_expiry
            existing["enable"] = True
            client_uuid = existing["id"]
            self._post(
                f"/panel/api/inbounds/updateClient/{client_uuid}",
                {"id": inbound["id"], "settings": json.dumps({"clients": [existing]})},
            )
        else:
            client_uuid = str(uuidlib.uuid4())
            new_expiry = now_ms + add_ms
            client = {
                "id": client_uuid,
                "email": email,
                "flow": config.CLIENT_FLOW,
                "totalGB": 0,
                "expiryTime": new_expiry,
                "enable": True,
                "tgId": str(user_id),
                "subId": "",
            }
            self._post(
                "/panel/api/inbounds/addClient",
                {"id": inbound["id"], "settings": json.dumps({"clients": [client]})},
            )

        link = self.build_link(inbound, client_uuid, email)
        return client_uuid, email, new_expiry, link

    def build_link(self, inbound: dict, client_uuid: str, email: str) -> str:
        ss = json.loads(inbound["streamSettings"])
        rs = ss.get("realitySettings", {})
        rset = rs.get("settings", {})
        pbk = rset.get("publicKey", "")
        fp = rset.get("fingerprint", "chrome")
        spx = rset.get("spiderX", "/")
        sni = (rs.get("serverNames") or [""])[0]
        sid = (rs.get("shortIds") or [""])[0]
        port = inbound["port"]
        q = (f"encryption=none&security=reality&sni={sni}&fp={fp}"
             f"&pbk={pbk}&sid={sid}&spx={quote(spx, safe='')}&type=tcp")
        if config.CLIENT_FLOW:
            q += f"&flow={config.CLIENT_FLOW}"
        return f"vless://{client_uuid}@{config.SERVER_IP}:{port}?{q}#{quote(email)}"
