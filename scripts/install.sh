#!/usr/bin/env bash
#
# Подготовка сервера и установка панели 3x-ui для VPN (VLESS + Reality).
# Запускать на свежем Ubuntu 22.04 / 24.04 под root:
#
#   bash <(curl -Ls https://raw.githubusercontent.com/mike50001/referal/claude/custom-vpn-8o0v15/scripts/install.sh)
#
# После установки настрой inbound Reality по docs/03-reality.md.

set -euo pipefail

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
info()  { echo -e "${GREEN}[+]${NC} $*"; }
warn()  { echo -e "${YELLOW}[!]${NC} $*"; }
error() { echo -e "${RED}[x]${NC} $*" >&2; }

# --- проверки ---------------------------------------------------------------
if [[ "${EUID}" -ne 0 ]]; then
    error "Запусти скрипт под root (или через sudo)."
    exit 1
fi

if ! grep -qiE 'ubuntu' /etc/os-release 2>/dev/null; then
    warn "Скрипт рассчитан на Ubuntu. Продолжаю, но возможны нюансы."
fi

# --- обновление системы -----------------------------------------------------
info "Обновляю систему..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get upgrade -y
apt-get install -y curl socat ca-certificates ufw

# --- BBR (ускорение сети) ---------------------------------------------------
info "Включаю BBR..."
if ! grep -q "tcp_congestion_control=bbr" /etc/sysctl.conf; then
    echo "net.core.default_qdisc=fq" >> /etc/sysctl.conf
    echo "net.ipv4.tcp_congestion_control=bbr" >> /etc/sysctl.conf
fi
sysctl -p >/dev/null 2>&1 || true
if sysctl net.ipv4.tcp_congestion_control 2>/dev/null | grep -q bbr; then
    info "BBR активен."
else
    warn "BBR не активировался (не критично)."
fi

# --- фаервол ----------------------------------------------------------------
info "Настраиваю фаервол (SSH + 443)..."
ufw allow 22/tcp   >/dev/null 2>&1 || true
ufw allow 443/tcp  >/dev/null 2>&1 || true
# Панель и подписка используют свои порты — открой их вручную после установки:
#   ufw allow <порт_панели>
#   ufw allow <порт_подписки>
ufw --force enable  >/dev/null 2>&1 || true
warn "Не забудь открыть порт панели: ufw allow <порт_панели>"

# --- установка 3x-ui --------------------------------------------------------
info "Ставлю панель 3x-ui..."
bash <(curl -Ls https://raw.githubusercontent.com/mhsanaei/3x-ui/master/install.sh)

echo
info "Готово!"
echo    "Дальше:"
echo    "  1. Войди в панель по адресу из вывода выше (Access URL)."
echo    "  2. Смени логин/пароль/путь панели, если ещё не сделал."
echo    "  3. Открой порт панели в фаерволе: ufw allow <порт>."
echo    "  4. Настрой Reality: см. docs/03-reality.md"
echo    "  5. Добавь пользователей: см. docs/04-users.md"
