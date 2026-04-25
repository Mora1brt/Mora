import asyncio
import logging
import os
import sqlite3
import json
import time
import re
import random
import sys
import requests
from concurrent.futures import ThreadPoolExecutor
from fake_useragent import FakeUserAgent
from bs4 import BeautifulSoup
from telethon import TelegramClient, errors, functions, types
from telethon.tl.functions.channels import JoinChannelRequest, LeaveChannelRequest, InviteToChannelRequest
from telethon.tl.functions.messages import GetHistoryRequest
from telethon.tl.functions.contacts import ImportContactsRequest, DeleteContactsRequest
from telethon.tl.types import InputPhoneContact
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, LinkPreviewOptions
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler
)
from telegram.error import Conflict, NetworkError, TelegramError
from telegram.warnings import PTBUserWarning

import warnings
warnings.filterwarnings("ignore", message=r".*CallbackQueryHandler", category=PTBUserWarning)

# ========== إعدادات التسجيل ==========
import logging

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.WARNING
)
logger = logging.getLogger(__name__)

# ========== الثوابت الأساسية ==========
DEVELOPER_ID = 8405201865
DEVELOPER_USERNAME = "@ka_1lo"
ADMIN_ID = 8405201865
BOT_TOKEN = "8263138216:AAHOxcueT0rvJALqHHJD3CAMSqJPf4OCagM"

# ========== مسارات الملفات ==========
SESSIONS_DIR = "sessions"
DATABASE_PATH = "data/bot_v3_2.db"
JSON_DATA_PATH = "data/members_data.json"
UPLOAD_DIR = "uploads"
SETTINGS_FILE = "bot_settings.json"
USER_SETTINGS_DIR = "user_settings"
AUTO_SWITCH_FILE = "auto_switch.txt"

# ========== ملفات الأدمن ==========
ADMIN_FILES = {
    "state": "Dyler.txt",
    "channel1": "Dyler0.txt",
    "channel2": "Dyler1.txt",
    "notify": "Dyler2.txt",
    "forward": "Dyler3.txt",
    "users": "users.txt",
    "channels": "chall.txt",
    "groups": "DylerGR.txt",
    "banned_users": "banned.txt",
    "admins_list": "admins.txt",
    "owner": "owner.txt",
    "welcome_message": "welcome_message.txt",
}

# ========== إنشاء ملف المالك ==========
if not os.path.exists(ADMIN_FILES["owner"]):
    with open(ADMIN_FILES["owner"], 'w') as f:
        f.write(str(DEVELOPER_ID))

# ========== الإعدادات الافتراضية ==========
DEFAULT_SETTINGS = {
    "MAX_ACCOUNTS": 500,
    "CONTACTS_PER_ACCOUNT": 120,
    "ADD_DELAY": 12.0,
    "CONTACT_ADD_DELAY": 1.5,
    "SCRAPE_BATCH_SIZE": 50,
    "MAX_MESSAGES_SCRAPE": 20000,
    "PARALLEL_WORKERS": 5,
    "JOIN_DELAY": 2.0,
    "LEAVE_DELAY": 2.0,
    "AUTO_SWITCH_DEFAULT": False
}

# ========== دوال تحميل وحفظ الإعدادات (تعريفها أولاً) ==========
def load_settings():
    """تحميل الإعدادات من ملف JSON"""
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                settings = json.load(f)
                for key, value in DEFAULT_SETTINGS.items():
                    if key not in settings:
                        settings[key] = value
                return settings
        except:
            return DEFAULT_SETTINGS.copy()
    return DEFAULT_SETTINGS.copy()

def save_settings(settings):
    """حفظ الإعدادات في ملف JSON"""
    with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(settings, f, ensure_ascii=False, indent=4)

def update_setting(key, value):
    """تحديث إعداد معين"""
    settings = load_settings()
    settings[key] = value
    save_settings(settings)
    return settings

# ========== تحميل الإعدادات (بعد تعريف الدوال) ==========
BOT_SETTINGS = load_settings()

# ========== تعيين المتغيرات من الإعدادات ==========
MAX_ACCOUNTS = BOT_SETTINGS['MAX_ACCOUNTS']
CONTACTS_PER_ACCOUNT = BOT_SETTINGS['CONTACTS_PER_ACCOUNT']
ADD_DELAY = BOT_SETTINGS['ADD_DELAY']
CONTACT_ADD_DELAY = BOT_SETTINGS['CONTACT_ADD_DELAY']
SCRAPE_BATCH_SIZE = BOT_SETTINGS['SCRAPE_BATCH_SIZE']
MAX_MESSAGES_SCRAPE = BOT_SETTINGS['MAX_MESSAGES_SCRAPE']
PARALLEL_WORKERS = BOT_SETTINGS['PARALLEL_WORKERS']
JOIN_DELAY = BOT_SETTINGS['JOIN_DELAY']
LEAVE_DELAY = BOT_SETTINGS['LEAVE_DELAY']

# ========== باقي الكود (إنشاء المجلدات، التسجيل، etc.) ==========
STOP_PROCESS = False
AUTO_SWITCH_ENABLED = False
STORE_VISIBLE_SOURCE = 34

# إنشاء المجلدات
os.makedirs(SESSIONS_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
os.makedirs(USER_SETTINGS_DIR, exist_ok=True)

# ========== دوال التبديل التلقائي لكل مستخدم ==========
def get_user_auto_switch_file(user_id):
    """الحصول على مسار ملف إعدادات التبديل التلقائي لمستخدم محدد"""
    return os.path.join(USER_SETTINGS_DIR, f"auto_switch_{user_id}.txt")

def is_auto_switch_enabled_for_user(user_id):
    """التحقق من تفعيل خاصية التبديل التلقائي لمستخدم محدد"""
    return os.path.exists(get_user_auto_switch_file(user_id))

def enable_auto_switch_for_user(user_id):
    """تفعيل خاصية التبديل التلقائي لمستخدم محدد"""
    if not is_auto_switch_enabled_for_user(user_id):
        with open(get_user_auto_switch_file(user_id), 'w') as f:
            f.write("enabled")
        return True
    return False

def disable_auto_switch_for_user(user_id):
    """تعطيل خاصية التبديل التلقائي لمستخدم محدد"""
    user_file = get_user_auto_switch_file(user_id)
    if os.path.exists(user_file):
        os.remove(user_file)
        return True
    return False

def is_auto_switch_enabled():
    """التحقق من تفعيل خاصية التبديل التلقائي"""
    return os.path.exists(AUTO_SWITCH_FILE)

def enable_auto_switch():
    """تفعيل خاصية التبديل التلقائي"""
    if not os.path.exists(AUTO_SWITCH_FILE):
        with open(AUTO_SWITCH_FILE, 'w') as f:
            f.write("enabled")
        return True
    return False

def disable_auto_switch():
    """تعطيل خاصية التبديل التلقائي"""
    if os.path.exists(AUTO_SWITCH_FILE):
        os.remove(AUTO_SWITCH_FILE)
        return True
    return False

# ========== إنشاء ملف المالك ==========
if not os.path.exists(ADMIN_FILES["owner"]):
    with open(ADMIN_FILES["owner"], 'w') as f:
        f.write(str(DEVELOPER_ID))

# ========== إنشاء ملفات الأدمن ==========
for file in ADMIN_FILES.values():
    if not os.path.exists(file):
        with open(file, 'w') as f:
            pass

# ========== دوال التعامل مع ملفات الأدمن ==========
def get_admin_file_content(file_path):
    """قراءة محتوى ملف"""
    try:
        with open(file_path, 'r') as f:
            return f.read().strip()
    except:
        return ""

def get_admin_file_lines(file_path):
    """قراءة سطور الملف"""
    try:
        with open(file_path, 'r') as f:
            return [line.strip() for line in f.readlines() if line.strip()]
    except:
        return []

def write_to_admin_file(file_path, content, append=False):
    """الكتابة في ملف"""
    mode = 'a' if append else 'w'
    with open(file_path, mode) as f:
        if append:
            f.write(f"\n{content}")
        else:
            f.write(str(content))

def remove_from_admin_file(file_path, content):
    """حذف سطر من ملف"""
    lines = get_admin_file_lines(file_path)
    if content in lines:
        lines.remove(content)
        with open(file_path, 'w') as f:
            f.write("\n".join(lines))

# ========== دوال التحقق من الصلاحيات ==========
def is_owner(user_id):
    """التحقق من أن المستخدم هو المالك"""
    owner = get_admin_file_content(ADMIN_FILES["owner"])
    return str(user_id) == str(owner)

def is_admin(user_id):
    """التحقق من أن المستخدم أدمن"""
    admins = get_admin_file_lines(ADMIN_FILES["admins_list"])
    return str(user_id) in admins or is_owner(user_id)

def is_banned(user_id):
    """التحقق من أن المستخدم محظور"""
    banned = get_admin_file_lines(ADMIN_FILES["banned_users"])
    return str(user_id) in banned

def add_admin(user_id):
    """إضافة أدمن جديد"""
    admins = get_admin_file_lines(ADMIN_FILES["admins_list"])
    if str(user_id) not in admins and str(user_id) != str(DEVELOPER_ID):
        write_to_admin_file(ADMIN_FILES["admins_list"], user_id, append=True)
        return True
    return False

def remove_admin(user_id):
    """حذف أدمن"""
    if str(user_id) == str(DEVELOPER_ID):
        return False
    remove_from_admin_file(ADMIN_FILES["admins_list"], str(user_id))
    return True

def ban_user(user_id):
    """حظر مستخدم"""
    banned = get_admin_file_lines(ADMIN_FILES["banned_users"])
    if str(user_id) not in banned:
        write_to_admin_file(ADMIN_FILES["banned_users"], user_id, append=True)
        return True
    return False

def unban_user(user_id):
    """فك حظر مستخدم"""
    remove_from_admin_file(ADMIN_FILES["banned_users"], str(user_id))
    return True

def change_owner(new_owner_id):
    """تغيير المالك (للمطور الأساسي فقط)"""
    if str(new_owner_id).isdigit():
        write_to_admin_file(ADMIN_FILES["owner"], new_owner_id)
        old_owner = get_admin_file_content(ADMIN_FILES["owner"])
        if old_owner and str(old_owner) != str(new_owner_id):
            admins = get_admin_file_lines(ADMIN_FILES["admins_list"])
            if str(old_owner) not in admins:
                write_to_admin_file(ADMIN_FILES["admins_list"], old_owner, append=True)
        return True
    return False

def check_subscription(user_id):
    """التحقق من اشتراك المستخدم في القنوات الإجبارية"""
    channel1 = get_admin_file_content(ADMIN_FILES["channel1"])
    channel2 = get_admin_file_content(ADMIN_FILES["channel2"])

    if not channel1 and not channel2:
        return True

    try:
        if channel1:
            resp = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getChatMember", params={
                "chat_id": channel1, "user_id": user_id
            })
            data = resp.json()
            status = data.get("result", {}).get("status", "")
            if status in ["left", "kicked"]:
                return False

        if channel2:
            resp = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getChatMember", params={
                "chat_id": channel2, "user_id": user_id
            })
            data = resp.json()
            status = data.get("result", {}).get("status", "")
            if status in ["left", "kicked"]:
                return False
        return True
    except:
        return False

# ========== كلاس قاعدة البيانات ==========
class Database:
    def __init__(self, db_path):
        self.db_path = db_path
        self.init_db()

    def get_connection(self):
        return sqlite3.connect(self.db_path)

    def init_db(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('CREATE TABLE IF NOT EXISTS accounts (phone TEXT PRIMARY KEY, api_id INTEGER, api_hash TEXT, session_name TEXT, owner_id TEXT)')
            cursor.execute('CREATE TABLE IF NOT EXISTS admins (user_id INTEGER PRIMARY KEY)')
            cursor.execute('CREATE TABLE IF NOT EXISTS members (user_id INTEGER PRIMARY KEY, username TEXT, access_hash TEXT, phone TEXT, type TEXT)')
            conn.commit()

    def add_account(self, phone, api_id, api_hash, session_name, owner_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('INSERT OR REPLACE INTO accounts VALUES (?, ?, ?, ?, ?)', (phone, api_id, api_hash, session_name, owner_id))
            conn.commit()

    def get_accounts(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM accounts')
            return cursor.fetchall()

    def get_user_accounts(self, user_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM accounts WHERE owner_id = ?', (str(user_id),))
            return cursor.fetchall()

    def get_account_count(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM accounts')
            return cursor.fetchone()[0]

    def remove_account(self, phone):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM accounts WHERE phone = ?', (phone,))
            conn.commit()

    def save_members(self, members_list):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany('INSERT OR IGNORE INTO members (user_id, username, access_hash, phone, type) VALUES (?, ?, ?, ?, ?)', members_list)
            conn.commit()

        json_list = []
        for m in members_list:
            json_list.append({
                "user_id": m[0],
                "username": m[1],
                "access_hash": str(m[2]),
                "phone": m[3],
                "type": m[4]
            })
        save_to_json(json_list)

    def clear_members(self, m_type=None):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if m_type:
                cursor.execute('DELETE FROM members WHERE type = ?', (m_type,))
            else:
                cursor.execute('DELETE FROM members')
            conn.commit()

    def get_members_by_type(self, m_type):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM members WHERE type = ?', (m_type,))
            return cursor.fetchall()

# ========== إنشاء قاعدة البيانات ==========
db = Database(DATABASE_PATH)

# ========== دوال مساعدة ==========
def resolve_conflict(token):
    """حذف الويب هوك وإلغاء أي طلبات معلقة"""
    try:
        url = f"https://api.telegram.org/bot{token}/deleteWebhook?drop_pending_updates=True"
        response = requests.get(url)
        if response.status_code == 200:
            logger.info("✅ تم تصفية كافة الجلسات المعلقة بنجاح.")
            return True
    except Exception as e:
        logger.error(f"❌ فشل في تصفية الجلسات: {e}")
    return False

def save_to_json(data, filename=JSON_DATA_PATH):
    """حفظ البيانات في ملف JSON"""
    try:
        existing_data = []
        if os.path.exists(filename):
            with open(filename, 'r', encoding='utf-8') as f:
                try:
                    existing_data = json.load(f)
                except json.JSONDecodeError:
                    existing_data = []

        seen_ids = {item['user_id'] for item in existing_data}
        for item in data:
            if item['user_id'] not in seen_ids:
                existing_data.append(item)
                seen_ids.add(item['user_id'])

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(existing_data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        logger.error(f"خطأ في حفظ JSON: {e}")

def format_channel_link(channel):
    """تحويل معرف القناة إلى رابط صالح لزر Inline Keyboard"""
    if not channel:
        return None
    channel = channel.strip()

    if channel.startswith('@'):
        return f"https://t.me/{channel[1:]}"

    if channel.startswith('https://t.me/') or channel.startswith('http://t.me/'):
        return channel

    if channel.startswith('+'):
        return f"https://t.me/joinchat/{channel[1:]}"
    if 'joinchat' in channel:
        return channel if channel.startswith('http') else f"https://t.me/{channel}"

    return f"https://t.me/{channel.replace('@', '')}"

# ========== دوال السحب المتوازي ==========
async def fetch_messages_batch(client, entity, offset_id, limit):
    """جلب دفعة من الرسائل بشكل غير متزامن"""
    try:
        messages = await client(GetHistoryRequest(
            peer=entity,
            limit=limit,
            offset_date=None,
            offset_id=offset_id,
            max_id=0,
            min_id=0,
            add_offset=0,
            hash=0
        ))
        return messages.messages
    except Exception as e:
        logger.error(f"خطأ في جلب الدفعة: {e}")
        return []

async def scrape_hidden_members_parallel(client, entity, status_msg, max_messages=20000):
    """سحب المخفيين بشكل متوازي وسريع"""
    global STOP_PROCESS
    STOP_PROCESS = False

    users_to_save = []
    seen_ids = set()
    seen_lock = asyncio.Lock()
    
    batch_size = 200
    max_batches = (max_messages // batch_size) + 5
    
    first_batch = await fetch_messages_batch(client, entity, 0, batch_size)
    if not first_batch:
        return []
    
    total_messages = len(first_batch)
    all_messages = first_batch
    
    if total_messages >= batch_size:
        offset_id = first_batch[-1].id
        batch_tasks = []
        
        for batch_num in range(max_batches - 1):
            if STOP_PROCESS:
                break
            batch_tasks.append(fetch_messages_batch(client, entity, offset_id, batch_size))
            offset_id -= batch_size
            
            if len(batch_tasks) >= 5:
                results = await asyncio.gather(*batch_tasks)
                for res in results:
                    if res:
                        all_messages.extend(res)
                        total_messages += len(res)
                batch_tasks = []
                
                if total_messages % 1000 < batch_size:
                    await status_msg.edit_text(
                        f"⏳ جاري السحب المتوازي...\n"
                        f"📨 تم جلب: `{total_messages}` رسالة\n"
                        f"👥 تم استخراج: `{len(users_to_save)}` مستخدم\n"
                        f"⚡ وضع: سريع (متوازي)",
                        parse_mode="Markdown"
                    )
                await asyncio.sleep(0.1)
        
        if batch_tasks:
            results = await asyncio.gather(*batch_tasks)
            for res in results:
                if res:
                    all_messages.extend(res)
    
    await status_msg.edit_text(
        f"⏳ جاري استخراج المستخدمين من `{len(all_messages)}` رسالة...\n"
        f"⚡ استخدام المعالجة المتوازية...",
        parse_mode="Markdown"
    )
    
    chunk_size = 500
    chunks = [all_messages[i:i+chunk_size] for i in range(0, len(all_messages), chunk_size)]
    
    async def process_chunk(chunk):
        local_users = []
        local_ids = set()
        
        for m in chunk:
            if STOP_PROCESS:
                break
            if m.from_id and isinstance(m.from_id, types.PeerUser):
                u_id = m.from_id.user_id
                if u_id not in local_ids:
                    try:
                        user = await client.get_entity(u_id)
                        if not user.bot and user.username:
                            local_users.append((user.id, user.username, user.access_hash, None, 'hidden'))
                            local_ids.add(u_id)
                    except:
                        pass
        return local_users, local_ids
    
    chunk_tasks = [process_chunk(chunk) for chunk in chunks[:20]]
    results = await asyncio.gather(*chunk_tasks)
    
    for users, ids in results:
        async with seen_lock:
            for user in users:
                if user[0] not in seen_ids:
                    seen_ids.add(user[0])
                    users_to_save.append(user)
    
    if STOP_PROCESS:
        STOP_PROCESS = False
    
    return users_to_save

# ========== كلاس إنشاء API تيليجرام ==========
class TelegramAPICreator:
    def __init__(self, user_id):
        self.user_id = user_id
        self.phone_number = None
        self.random_hash = None
        self.stel_token = None
        self.useragent = FakeUserAgent().random
        self.app_title = None
        self.app_shortname = None
        self.app_url = None
        self.app_platform = None
        self.app_desc = None
        self.session = requests.Session()

    def send_password(self) -> bool:
        """إرسال طلب الحصول على كلمة المرور"""
        try:
            response = self.session.post(
                url="https://my.telegram.org/auth/send_password",
                data={"phone": self.phone_number},
                headers={
                    "Origin": "https://my.telegram.org",
                    "Accept-Encoding": "gzip, deflate, br",
                    "Accept-Language": "ar,en;q=0.9",
                    "User-Agent": self.useragent,
                    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                    "Accept": "application/json, text/javascript, */*; q=0.01",
                    "Referer": "https://my.telegram.org/auth",
                    "X-Requested-With": "XMLHttpRequest",
                    "Connection": "keep-alive",
                }
            )
            if response.status_code == 200:
                get_json = json.loads(response.content)
                self.random_hash = get_json.get("random_hash")
                return True
            return False
        except Exception as e:
            logger.error(f"Error sending password: {e}")
            return False

    def auth_login(self, code: str) -> bool:
        """تسجيل الدخول باستخدام رمز التحقق"""
        try:
            response = self.session.post(
                url="https://my.telegram.org/auth/login",
                data={
                    "phone": self.phone_number,
                    "random_hash": self.random_hash,
                    "password": code
                },
                headers={
                    "Origin": "https://my.telegram.org",
                    "Accept-Encoding": "gzip, deflate, br",
                    "Accept-Language": "ar,en;q=0.9",
                    "User-Agent": self.useragent,
                    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                    "Accept": "application/json, text/javascript, */*; q=0.01",
                    "Referer": "https://my.telegram.org/auth",
                    "X-Requested-With": "XMLHttpRequest",
                    "Connection": "keep-alive",
                }
            )
            if response.status_code == 200:
                if 'stel_token' in response.cookies:
                    self.stel_token = response.cookies['stel_token']
                    return True
                try:
                    resp_json = response.json()
                    if resp_json.get('success'):
                        return True
                except:
                    pass
            return False
        except Exception as e:
            logger.error(f"Error auth login: {e}")
            return False

    def get_app_data(self):
        """استرجاع بيانات API الموجودة"""
        try:
            response = self.session.get(
                url="https://my.telegram.org/apps",
                headers={
                    "User-Agent": self.useragent,
                    "Referer": "https://my.telegram.org/org",
                }
            )

            if response.status_code != 200:
                return None

            soup = BeautifulSoup(response.text, 'html.parser')

            try:
                api_id_label = soup.find('label', string='App api_id:')
                if api_id_label:
                    api_id_div = api_id_label.find_next_sibling('div')
                    if api_id_div:
                        api_id_span = api_id_div.select_one('span')
                        api_id = api_id_span.get_text().strip() if api_id_span else api_id_div.get_text().strip()
                    else:
                        api_id = None
                else:
                    api_id = None

                api_hash_label = soup.find('label', string='App api_hash:')
                if api_hash_label:
                    api_hash_div = api_hash_label.find_next_sibling('div')
                    if api_hash_div:
                        api_hash_span = api_hash_div.select_one('span')
                        api_hash = api_hash_span.get_text().strip() if api_hash_span else api_hash_div.get_text().strip()
                    else:
                        api_hash = None
                else:
                    api_hash = None

                if api_id and api_hash and api_id != 'None' and api_hash != 'None':
                    return api_id, api_hash
            except Exception as e:
                logger.error(f"Error parsing: {e}")

            api_id_match = re.search(r'api_id[^0-9]*([0-9]+)', response.text, re.IGNORECASE)
            api_hash_match = re.search(r'api_hash[^a-f0-9]*([a-f0-9]{32})', response.text, re.IGNORECASE)

            if api_id_match and api_hash_match:
                return api_id_match.group(1), api_hash_match.group(1)

            return None

        except Exception as e:
            logger.error(f"Error getting app data: {e}")
            return None

    def create_new_app(self):
        """إنشاء تطبيق جديد"""
        try:
            response = self.session.get(
                url="https://my.telegram.org/apps",
                headers={
                    "User-Agent": self.useragent,
                    "Referer": "https://my.telegram.org/org"
                }
            )

            if response.status_code != 200:
                return False

            content = response.text
            soup = BeautifulSoup(content, 'html.parser')

            hash_value = None
            hash_input = soup.find('input', {'name': 'hash'})
            if hash_input and hash_input.get('value'):
                hash_value = hash_input.get('value')

            if not hash_value:
                hash_match = re.search(r'name="hash"\s+value="([^"]+)"', content)
                if hash_match:
                    hash_value = hash_match.group(1)

            if not hash_value:
                hash_match = re.search(r'hash=([a-f0-9]+)', content)
                if hash_match:
                    hash_value = hash_match.group(1)

            if not hash_value:
                return False

            app_data = {
                "hash": hash_value,
                "app_title": self.app_title,
                "app_shortname": self.app_shortname,
                "app_url": self.app_url,
                "app_platform": self.app_platform,
                "app_desc": self.app_desc
            }

            create_response = self.session.post(
                url="https://my.telegram.org/apps/create",
                data=app_data,
                headers={
                    "User-Agent": self.useragent,
                    "Origin": "https://my.telegram.org",
                    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                    "Accept": "application/json, text/javascript, */*; q=0.01",
                    "Referer": "https://my.telegram.org/apps",
                    "X-Requested-With": "XMLHttpRequest",
                }
            )

            if create_response.status_code == 200:
                try:
                    resp_json = create_response.json()
                    if resp_json.get('error'):
                        return False
                except:
                    pass

                time.sleep(3)
                return self.retrieve_created_app_data()
            return False

        except Exception as e:
            logger.error(f"Error creating app: {e}")
            return False

    def retrieve_created_app_data(self):
        """استرجاع بيانات التطبيق بعد الإنشاء"""
        for attempt in range(10):
            time.sleep(3)

            try:
                response = self.session.get(
                    url="https://my.telegram.org/apps",
                    headers={"User-Agent": self.useragent}
                )

                if response.status_code != 200:
                    continue

                soup = BeautifulSoup(response.text, 'html.parser')

                try:
                    api_id_label = soup.find('label', string='App api_id:')
                    if api_id_label:
                        api_id_div = api_id_label.find_next_sibling('div')
                        if api_id_div:
                            api_id_span = api_id_div.select_one('span')
                            api_id = api_id_span.get_text().strip() if api_id_span else api_id_div.get_text().strip()
                        else:
                            api_id = None
                    else:
                        api_id = None

                    api_hash_label = soup.find('label', string='App api_hash:')
                    if api_hash_label:
                        api_hash_div = api_hash_label.find_next_sibling('div')
                        if api_hash_div:
                            api_hash_span = api_hash_div.select_one('span')
                            api_hash = api_hash_span.get_text().strip() if api_hash_span else api_hash_div.get_text().strip()
                        else:
                            api_hash = None
                    else:
                        api_hash = None

                    if api_id and api_hash and api_id != 'None' and api_hash != 'None':
                        return api_id, api_hash
                except Exception as e:
                    logger.error(f"Error parsing: {e}")

                api_id_match = re.search(r'api_id[^0-9]*([0-9]+)', response.text, re.IGNORECASE)
                api_hash_match = re.search(r'api_hash[^a-f0-9]*([a-f0-9]{32})', response.text, re.IGNORECASE)

                if api_id_match and api_hash_match:
                    return api_id_match.group(1), api_hash_match.group(1)

            except Exception as e:
                logger.error(f"Error retrieving data: {e}")

        return False

# ========== دوال الفحص الدوري ==========
async def periodic_check(application=None):
    """تشغيل فحص الحسابات كل ساعة"""
    while True:
        try:
            await asyncio.sleep(3600)
            removed = await check_all_accounts_subscription()
            if removed > 0:
                logger.info(f"✅ تم الفحص الدوري: تم حذف {removed} حساب غير مشترك")
            else:
                logger.info("✅ تم الفحص الدوري: جميع الحسابات مشتركة")
        except asyncio.CancelledError:
            logger.info("تم إيقاف الفحص الدوري")
            break
        except Exception as e:
            logger.error(f"خطأ في الفحص الدوري: {e}")

# ========== دوال لوحات الأدمن ==========
def get_admin_sections_keyboard():
    """لوحة أقسام الأدمن الرئيسية"""
    keyboard = [
        [
            InlineKeyboardButton("📢 إشتراك إجباري", callback_data="section_subscription"),
            InlineKeyboardButton("📣 إذاعة ونشر", callback_data="section_broadcast")
        ],
        [
            InlineKeyboardButton("📊 إحصائيات", callback_data="section_stats"),
            InlineKeyboardButton("🔔 تنبيهات", callback_data="section_alerts")
        ],
        [
            InlineKeyboardButton("🔄 توجيه رسائل", callback_data="section_forward"),
            InlineKeyboardButton("👥 إدارة مستخدمين", callback_data="section_users_management")
        ],
        [
            InlineKeyboardButton("🎨 تخصيص البوت", callback_data="section_customize"),
            InlineKeyboardButton("⚙️ الإعدادات", callback_data="section_settings")
        ],
        [
            InlineKeyboardButton("📝 رسالة الترحيب", callback_data="section_welcome")
        ],
        [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_subscription_keyboard():
    """قسم الإشتراك الإجباري"""
    keyboard = [
        [InlineKeyboardButton("📢 القناة الأولى", callback_data="sub1_info")],
        [
            InlineKeyboardButton("➕ وضع قناة", callback_data="Dyler0"),
            InlineKeyboardButton("🗑️ حذف قناة", callback_data="delete11")
        ],
        [InlineKeyboardButton("📢 القناة الثانية", callback_data="sub2_info")],
        [
            InlineKeyboardButton("➕ وضع قناة", callback_data="Dyler2"),
            InlineKeyboardButton("🗑️ حذف قناة", callback_data="delete22")
        ],
        [InlineKeyboardButton("👁️ عرض القنوات", callback_data="Dyler4")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="admin_sections")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_broadcast_keyboard():
    """قسم الإذاعة والنشر"""
    users_count = len(get_admin_file_lines(ADMIN_FILES["users"]))
    groups_count = len(get_admin_file_lines(ADMIN_FILES["groups"]))
    channels_count = len(get_admin_file_lines(ADMIN_FILES["channels"]))

    keyboard = [
        [InlineKeyboardButton(f"👤 للمستخدمين ({users_count})", callback_data="broadcast_users")],
        [InlineKeyboardButton(f"👥 للمجموعات ({groups_count})", callback_data="broadcast_groups")],
        [InlineKeyboardButton(f"📢 للقنوات ({channels_count})", callback_data="broadcast_channels")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="admin_sections")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_stats_keyboard():
    """قسم الإحصائيات"""
    users_count = len(get_admin_file_lines(ADMIN_FILES["users"]))
    groups_count = len(get_admin_file_lines(ADMIN_FILES["groups"]))
    channels_count = len(get_admin_file_lines(ADMIN_FILES["channels"]))
    accounts_count = db.get_account_count()

    keyboard = [
        [InlineKeyboardButton(f"📢 القنوات: {channels_count}", callback_data="noop")],
        [InlineKeyboardButton(f"📱 حسابات السحب: {accounts_count}", callback_data="noop")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="admin_sections")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_alerts_keyboard():
    """قسم التنبيهات"""
    notify_enabled = get_admin_file_content(ADMIN_FILES["notify"]) == "Dyler"
    status_text = "✅ مفعل" if notify_enabled else "❌ معطل"

    keyboard = [
        [InlineKeyboardButton(f"📢 التنبيهات: {status_text}", callback_data="noop")],
        [
            InlineKeyboardButton("✅ تفعيل", callback_data="Dyler9"),
            InlineKeyboardButton("❌ تعطيل", callback_data="Dyler10")
        ],
        [InlineKeyboardButton("🔙 رجوع", callback_data="admin_sections")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_forward_keyboard():
    """قسم توجيه الرسائل"""
    forward_enabled = get_admin_file_content(ADMIN_FILES["forward"]) == "Dyler"
    status_text = "✅ مفعل" if forward_enabled else "❌ معطل"

    keyboard = [
        [InlineKeyboardButton(f"🔄 التوجيه: {status_text}", callback_data="noop")],
        [
            InlineKeyboardButton("✅ تفعيل", callback_data="Dyler11"),
            InlineKeyboardButton("❌ تعطيل", callback_data="Dyler12")
        ],
        [InlineKeyboardButton("🔙 رجوع", callback_data="admin_sections")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_users_management_keyboard():
    """لوحة إدارة المستخدمين"""
    keyboard = [
        [InlineKeyboardButton("━━━━━ 👑 الأدمن ━━━━━", callback_data="noop")],
        [
            InlineKeyboardButton("➕ إضافة", callback_data="add_admin"),
            InlineKeyboardButton("➖ حذف", callback_data="remove_admin"),
            InlineKeyboardButton("📋 القائمة", callback_data="list_admins")
        ],
        [InlineKeyboardButton("━━━━━ 🚫 الحظر ━━━━━", callback_data="noop")],
        [
            InlineKeyboardButton("🚫 حظر", callback_data="ban_user"),
            InlineKeyboardButton("✅ فك حظر", callback_data="unban_user"),
            InlineKeyboardButton("🚷 المحظورين", callback_data="list_banned")
        ],
        [InlineKeyboardButton("━━━━━ 👤 المستخدمين ━━━━━", callback_data="noop")],
        [InlineKeyboardButton("👤 المستخدمين", callback_data="list_all_users")],
        [InlineKeyboardButton("🔙 رجوع للوحة الرئيسية", callback_data="admin_sections")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_settings_keyboard():
    """لوحة إعدادات البوت"""
    settings = load_settings()
    
    keyboard = [
        [InlineKeyboardButton("📊 الإعدادات العامة", callback_data="noop")],
        [InlineKeyboardButton("━━━━━━━━━━━━━━━━━━━━━", callback_data="noop")],
        
        [InlineKeyboardButton(f"📱 الحد الأقصى للحسابات: {settings['MAX_ACCOUNTS']}", callback_data="noop")],
        [
            InlineKeyboardButton("🔻 -10", callback_data="set_MAX_ACCOUNTS_down"),
            InlineKeyboardButton("🔺 +10", callback_data="set_MAX_ACCOUNTS_up")
        ],
        
        [InlineKeyboardButton(f"📞 جهات الاتصال لكل حساب: {settings['CONTACTS_PER_ACCOUNT']}", callback_data="noop")],
        [
            InlineKeyboardButton("🔻 -10", callback_data="set_CONTACTS_PER_ACCOUNT_down"),
            InlineKeyboardButton("🔺 +10", callback_data="set_CONTACTS_PER_ACCOUNT_up")
        ],
        
        [InlineKeyboardButton(f"⏱️ تأخير الإضافة (ثانية): {settings['ADD_DELAY']}", callback_data="noop")],
        [
            InlineKeyboardButton("🔻 -1", callback_data="set_ADD_DELAY_down"),
            InlineKeyboardButton("🔺 +1", callback_data="set_ADD_DELAY_up")
        ],
        
        [InlineKeyboardButton(f"⏱️ تأخير إضافة جهات: {settings['CONTACT_ADD_DELAY']}", callback_data="noop")],
        [
            InlineKeyboardButton("🔻 -0.2", callback_data="set_CONTACT_ADD_DELAY_down"),
            InlineKeyboardButton("🔺 +0.2", callback_data="set_CONTACT_ADD_DELAY_up")
        ],
        
        [InlineKeyboardButton(f"📦 حجم دفعة السحب: {settings['SCRAPE_BATCH_SIZE']}", callback_data="noop")],
        [
            InlineKeyboardButton("🔻 -10", callback_data="set_SCRAPE_BATCH_SIZE_down"),
            InlineKeyboardButton("🔺 +10", callback_data="set_SCRAPE_BATCH_SIZE_up")
        ],
        
        [InlineKeyboardButton(f"📨 عدد الرسائل للفحص: {settings['MAX_MESSAGES_SCRAPE']:,}", callback_data="noop")],
        [
            InlineKeyboardButton("🔻 -1000", callback_data="set_MAX_MESSAGES_SCRAPE_down"),
            InlineKeyboardButton("🔺 +1000", callback_data="set_MAX_MESSAGES_SCRAPE_up")
        ],
        
        [InlineKeyboardButton(f"⚡ العمال المتوازيين: {settings['PARALLEL_WORKERS']}", callback_data="noop")],
        [
            InlineKeyboardButton("🔻 -1", callback_data="set_PARALLEL_WORKERS_down"),
            InlineKeyboardButton("🔺 +1", callback_data="set_PARALLEL_WORKERS_up")
        ],
        
        [InlineKeyboardButton("━━━━━━━━━━━━━━━━━━━━━", callback_data="noop")],
        [
            InlineKeyboardButton("🔄 إعادة ضبط الكل", callback_data="reset_all_settings"),
            InlineKeyboardButton("📋 عرض الإعدادات", callback_data="view_all_settings")
        ],
        [InlineKeyboardButton("🔙 رجوع للوحة الأدمن", callback_data="admin_sections")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_customize_keyboard():
    """لوحة تخصيص البوت"""
    keyboard = [
        [InlineKeyboardButton("📝 تعديل رسالة الترحيب", callback_data="edit_welcome")],
        [InlineKeyboardButton("👁️ معاينة رسالة الترحيب", callback_data="preview_welcome")],
        [InlineKeyboardButton("🔄 استعادة الرسالة الافتراضية", callback_data="reset_welcome")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="admin_sections")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_welcome_edit_keyboard():
    """لوحة تعديل رسالة الترحيب"""
    keyboard = [
        [InlineKeyboardButton("✅ حفظ وإرسال", callback_data="save_welcome")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="section_customize")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_add_admin_keyboard():
    """لوحة تأكيد إضافة أدمن"""
    keyboard = [
        [InlineKeyboardButton("🔙 رجوع", callback_data="users_management")]
    ]
    return InlineKeyboardMarkup(keyboard)

# ========== دوال التحويلات ==========
(
    A_PHONE, A_API_ID, A_API_HASH, A_CODE, A_PASSWORD,
    JOIN_COUNT, JOIN_LINK,
    LEAVE_LINK,
    TRANSFER_HIDDEN_SOURCE, TRANSFER_HIDDEN_TARGET,
    TRANSFER_VISIBLE_SOURCE, TRANSFER_VISIBLE_TARGET,
    TRANSFER_FILE_DOC, TRANSFER_FILE_TARGET,
    STORE_HIDDEN_SOURCE,
    ADD_CONTACTS_SOURCE,
    IMPORT_SESSION_FILE,
    UPLOAD_BACKUP,
    UPLOAD_FILE_DOC
) = range(19)


async def get_client(acc):
    """إنشاء عميل تيليجرام للحساب - يدعم 4 أو 5 عناصر"""

    phone = acc[0]
    api_id = acc[1]
    api_hash = acc[2]

    if len(acc) >= 4:
        session_name = acc[3]
    else:
        session_name = phone

    device = random.choice(DEVICES)
    client = TelegramClient(
        f"{SESSIONS_DIR}/{phone}",
        int(api_id),
        api_hash,
        device_model=device["model"],
        system_version=device["sys"],
        app_version="4.8.4",
        lang_code="ar",
        system_lang_code="ar-SA"
    )
    await client.connect()
    return client

async def clear_contacts_for_account(client):
    """حذف جميع جهات الاتصال لحساب معين"""
    try:
        contacts = await client(functions.contacts.GetContactsRequest(hash=0))
        if contacts.users:
            await client(DeleteContactsRequest(id=[user.id for user in contacts.users]))
            return len(contacts.users)
    except Exception as e:
        logger.error(f"خطأ في حذف جهات الاتصال: {e}")
    return 0

def get_main_keyboard(user_id=None):
    keyboard = []

    # ========== القسم الأول: الحسابات (زرارين) ==========
    keyboard.append([
        InlineKeyboardButton("➕ اضافة حساب", callback_data='add_acc'),
        InlineKeyboardButton("🗑️ حذف حساب", callback_data='del_acc')
    ])
    
    # ========== القسم الثاني: استخراج API ==========
    keyboard.append([InlineKeyboardButton("✦ 🔑 استخراج API ID/HASH ✦", callback_data="extract_api")])
    
    # ========== القسم الثالث: النقل ==========
    keyboard.append([
        InlineKeyboardButton("👥 نقل أعضاء ظاهر", callback_data='trans_visible'),
        InlineKeyboardButton("🕶️ نقل أعضاء مخفي", callback_data='trans_hidden')
    ])
    
    # ========== القسم الرابع: التخزين ==========
    keyboard.append([
        InlineKeyboardButton("💾 تخزين اعضاء ظاهر", callback_data='store_visible'),
        InlineKeyboardButton("📀 تخزين اعضاء مخفي", callback_data='store_hidden')
    ])
    
    # ========== باقي الأزرار ==========
    keyboard.append([
        InlineKeyboardButton("➕ اضافة جهات", callback_data='add_contacts'),
        InlineKeyboardButton("🗑️ حذف كل الجهات", callback_data='del_contacts'),
        InlineKeyboardButton("📂 نقل من ملف", callback_data='trans_file')
    ])
    
    keyboard.append([
        InlineKeyboardButton("📥 تحميل نسخة", callback_data='backup'),
        InlineKeyboardButton("📥 استيراد جلسات", callback_data='import_session'),
        InlineKeyboardButton("🛑 ايقاف العمليات النشطه", callback_data='stop_process')
    ])
    
    keyboard.append([
        InlineKeyboardButton("➖ خروج من مجموعة", callback_data='leave_group'),
        InlineKeyboardButton("🔍 فحص ارقامي", callback_data='check_accs'),
        InlineKeyboardButton("➕ دخول مجموعة", callback_data='join_group')
    ])
    
    keyboard.append([
        InlineKeyboardButton("📋 قائمه ارقامي", callback_data='list_accs'),
        InlineKeyboardButton("📤 رفع نسخة", callback_data='upload_backup'),
        InlineKeyboardButton("📤 رفع ملف اعضاء", callback_data='upload_file')
    ])
    
    keyboard.append([
        InlineKeyboardButton("🗑️ حذف ملف اعضاء", callback_data='del_file'),
        InlineKeyboardButton("📥 استخراج ملفات اعضاء", callback_data='extract_files')
    ])
    
    # زر التبديل التلقائي - حالة تفعيل/تعطيل لكل مستخدم
    if user_id and is_auto_switch_enabled_for_user(user_id):
        keyboard.append([InlineKeyboardButton("✅ التبديل التلقائي: مفعل (ل اگونتـک فقط)", callback_data='toggle_auto_switch')])
    else:
        keyboard.append([InlineKeyboardButton("❌ التبديل التلقائي: معطل (ل اگونتـک فقط)", callback_data='toggle_auto_switch')])
    
    if user_id and is_admin(user_id):
        keyboard.append([InlineKeyboardButton("🎛️ لوحة التحكم", callback_data='admin_panel')])
    
    return InlineKeyboardMarkup(keyboard)


def get_stop_keyboard():
    """زر إيقاف العملية"""
    return InlineKeyboardMarkup([[InlineKeyboardButton("🛑 إيقاف العملية", callback_data='stop_process')]])

async def get_next_available_account(current_account_index, accounts, failed_accounts, flood_wait_accounts):
    """الحصول على الحساب التالي المتاح للتبديل التلقائي"""
    if not is_auto_switch_enabled():
        return None, current_account_index + 1
    
    for i in range(current_account_index + 1, len(accounts)):
        acc = accounts[i]
        # تخطي الحسابات الفاشلة أو التي في فلود
        if acc[0] not in failed_accounts and acc[0] not in flood_wait_accounts:
            return acc, i
    return None, len(accounts)

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, LinkPreviewOptions
from telegram.ext import ContextTypes, ConversationHandler

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر البداية"""
    user = update.effective_user
    if not user:
        return

    if is_banned(user.id):
        await update.message.reply_text("🚫 أنت محظور من استخدام هذا البوت!")
        return

    user_id = user.id
    users_list = get_admin_file_lines(ADMIN_FILES["users"])
    if str(user_id) not in users_list:
        write_to_admin_file(ADMIN_FILES["users"], user_id, append=True)

    if not check_subscription(user_id) and user_id != ADMIN_ID:
        channel1 = get_admin_file_content(ADMIN_FILES["channel1"])
        channel2 = get_admin_file_content(ADMIN_FILES["channel2"])

        subscription_keyboard = []

        def format_channel_link(channel):
            if not channel:
                return None
            channel = channel.strip()
            if channel.startswith('@'):
                return f"https://t.me/{channel[1:]}"
            if channel.startswith('https://t.me/') or channel.startswith('http://t.me/'):
                return channel
            return f"https://t.me/{channel.replace('@', '')}"

        link1 = format_channel_link(channel1)
        link2 = format_channel_link(channel2)

        if link1:
            subscription_keyboard.append([InlineKeyboardButton("📢 القناة الأولى", url=link1)])
        if link2:
            subscription_keyboard.append([InlineKeyboardButton("📢 القناة الثانية", url=link2)])

        subscription_keyboard.append([InlineKeyboardButton("✅ تحقق من الإشتراك", callback_data="check_subscription")])

        await update.message.reply_text(
            f"⚠️ عذراً عزيزي {user.first_name} ⚠️\n\n"
            f"يجب عليك الإشتراك في القنوات التالية لإستخدام البوت:\n\n"
            f"📢 بعد الإشتراك، اضغط على زر التحقق.",
            reply_markup=InlineKeyboardMarkup(subscription_keyboard),
            parse_mode="Markdown",
            link_preview_options=LinkPreviewOptions(is_disabled=True)
        )
        return

    welcome_template = get_admin_file_content(ADMIN_FILES["welcome_message"])

    if welcome_template:
        try:
            text = welcome_template.format(
                first_name=user.first_name or "",
                last_name=user.last_name or "",
                username=user.username or "",
                user_id=user.id,
                developer_username=DEVELOPER_USERNAME
            )
        except Exception as e:
            logger.error(f"خطأ في تنسيق رسالة الترحيب: {e}")
            text = f"أهلاً بك {user.first_name} في بوت السحب\n\nالمطور | {DEVELOPER_USERNAME}"
    else:
        text = f"أهلاً بك {user.first_name} في بوت السحب النسخة المحسّنة من سورس كيرو\n\nالمطور | {DEVELOPER_USERNAME}"

    try:
        if update.message:
            await update.message.reply_text(
                text,
                parse_mode="HTML",
                reply_markup=get_main_keyboard(user_id),
                link_preview_options=LinkPreviewOptions(is_disabled=True)
            )
        elif update.callback_query:
            await update.callback_query.edit_message_text(
                text,
                parse_mode="HTML",
                reply_markup=get_main_keyboard(user_id),
                link_preview_options=LinkPreviewOptions(is_disabled=True)
            )
    except Exception as e:
        logger.error(f"خطأ في إرسال رسالة البداية: {e}")
        if update.message:
            await update.message.reply_text(
                "أهلاً بك في البوت!",
                reply_markup=get_main_keyboard(user_id),
                link_preview_options=LinkPreviewOptions(is_disabled=True)
            )

    return ConversationHandler.END

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر /admin لعرض لوحة التحكم"""
    user_id = update.effective_user.id

    if not is_admin(user_id):
        await update.message.reply_text("⚠️ هذا الأمر مخصص للأدمن فقط!")
        return

    keyboard = get_admin_sections_keyboard()
    await update.message.reply_text(
        "🔰 لوحة تحكم الأدمن\n﹎﹎﹎﹎﹎﹎﹎﹎﹎﹎﹎﹎\nمرحباً بك في لوحة التحكم.\nاختر القسم الذي تريد التحكم فيه:",
        reply_markup=keyboard
    )

async def admin_panel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض لوحة تحكم الأدمن"""
    query = update.callback_query
    user_id = query.from_user.id


    if not is_admin(user_id):
        await query.answer("⚠️ هذه اللوحة مخصصة للأدمن فقط!", show_alert=True)
        return

    await query.answer()
    keyboard = get_admin_sections_keyboard()

    await query.edit_message_text(
        "🔰 لوحة تحكم الأدمن\n﹎﹎﹎﹎﹎﹎﹎﹎﹎﹎﹎﹎\nمرحباً بك في لوحة التحكم.\nاختر القسم الذي تريد التحكم فيه:",
        reply_markup=keyboard
    )


async def handle_admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة أزرار لوحة الأدمن"""
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id
    chat_id = query.message.chat_id
    message_id = query.message.message_id

    if not is_admin(user_id):
        await query.answer("⚠️ غير مصرح! هذه اللوحة للأدمن فقط.", show_alert=True)
        return

    await query.answer()

    if data == "section_customize":
        keyboard = get_customize_keyboard()
        await query.edit_message_text(
            "🎨 قسم تخصيص البوت\n﹎﹎﹎﹎﹎﹎﹎﹎﹎﹎﹎﹎\n"
            "من هنا يمكنك تخصيص:\n"
            "• رسالة الترحيب (HTML مدعوم)\n\n"
            "📝 الوسوم المدعومة في HTML:\n"
            "• `<b>نص عريض</b>`\n"
            "• `<i>نص مائل</i>`\n"
            "• `<u>تسطير</u>`\n"
            "• `<code>كود</code>`\n"
            "• `<blockquote>اقتباس</blockquote>`\n"
            "• `<a href='رابط'>نص الرابط</a>`",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
        return

    # ========== قسم الإعدادات الجديد ==========
    if data == "section_settings":
        keyboard = get_settings_keyboard()
        settings = load_settings()
        await query.edit_message_text(
            "⚙️ **قسم إعدادات البوت**\n"
            "﹎﹎﹎﹎﹎﹎﹎﹎﹎﹎﹎﹎\n"
            "من هنا يمكنك التحكم في:\n"
            "• سرعة البوت وأمانه\n"
            "• عدد الحسابات المسموحة\n"
            "• التأخيرات بين العمليات\n"
            "• قوة المعالجة المتوازية\n"
            "﹎﹎﹎﹎﹎﹎﹎﹎﹎﹎﹎﹎\n"
            f"📊 **الإعدادات الحالية:**\n"
            f"• أقصى حسابات: `{settings['MAX_ACCOUNTS']}`\n"
            f"• جهات اتصال/حساب: `{settings['CONTACTS_PER_ACCOUNT']}`\n"
            f"• تأخير الإضافة: `{settings['ADD_DELAY']} ثانية`\n"
            f"• تأخير إضافة جهات: `{settings['CONTACT_ADD_DELAY']} ثانية`\n"
            f"• حجم دفعة السحب: `{settings['SCRAPE_BATCH_SIZE']}`\n"
            f"• عدد الرسائل للفحص: `{settings['MAX_MESSAGES_SCRAPE']:,}`\n"
            f"• عمال متوازيين: `{settings['PARALLEL_WORKERS']}`\n"
            "﹎﹎﹎﹎﹎﹎﹎﹎﹎﹎﹎﹎\n"
            "⚠️ تغيير الإعدادات يتم فوراً ويؤثر على جميع المستخدمين!",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
        return

    # ========== معالج تعديل الإعدادات ==========
    if data.startswith("set_") or data == "reset_all_settings" or data == "view_all_settings":
        await handle_settings_callback(update, context)
        return

    if data == "edit_welcome":
        current_message = get_admin_file_content(ADMIN_FILES["welcome_message"])
        if not current_message:
            current_message = "أهلاً بك {first_name} في بوت السحب\n\nالمطور | {developer_username}"

        await query.edit_message_text(
            "📝 تعديل رسالة الترحيب\n﹎﹎﹎﹎﹎﹎﹎﹎﹎﹎﹎﹎\n"
            "يمكنك استخدام HTML في رسالتك.\n\n"
            "الرسالة الحالية:\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            f"{current_message}\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            "📝 الوسوم المدعومة:\n"
            "• `<b>نص عريض</b>`\n"
            "• `<i>نص مائل</i>`\n"
            "• `<u>تسطير</u>`\n"
            "• `<code>كود</code>`\n"
            "• `<blockquote>اقتباس</blockquote>`\n"
            "• `<a href='رابط'>نص الرابط</a>`\n\n"
            "🔤 المتغيرات المدعومة:\n"
            "• `{first_name}` - اسم المستخدم الأول\n"
            "• `{last_name}` - اسم المستخدم الأخير\n"
            "• `{username}` - معرف المستخدم\n"
            "• `{user_id}` - ايدي المستخدم\n"
            "• `{developer_username}` - يوزر المطور\n\n"
            "✏️ أرسل رسالتك الجديدة (HTML مدعوم):",
            reply_markup=get_welcome_edit_keyboard(),
            parse_mode="Markdown"
        )
        write_to_admin_file(ADMIN_FILES["state"], "waiting_welcome_message")
        return

    if data == "save_welcome":
        await query.edit_message_text(
            "✅ تم حفظ رسالة الترحيب!\n\n"
            "يمكنك معاينتها من زر '👁️ معاينة رسالة الترحيب'",
            reply_markup=get_customize_keyboard(),
            parse_mode="Markdown"
        )
        if os.path.exists(ADMIN_FILES["state"]):
            os.remove(ADMIN_FILES["state"])
        return

    if data == "preview_welcome":
        await query.answer("⏳ جاري إرسال معاينة...")
        user = query.from_user
        welcome_text = get_admin_file_content(ADMIN_FILES["welcome_message"])

        formatted_text = welcome_text.format(
            first_name=user.first_name or "",
            last_name=user.last_name or "",
            username=user.username or "",
            user_id=user.id,
            developer_username=DEVELOPER_USERNAME
        ) if welcome_text else f"أهلاً بك {user.first_name} في بوت السحب\n\nالمطور | {DEVELOPER_USERNAME}"

        try:
            await query.message.reply_text(
                formatted_text,
                parse_mode="HTML"
            )
            await query.message.reply_text(
                "👆 هذه هي معاينة رسالة الترحيب",
                parse_mode="Markdown"
            )
        except Exception as e:
            await query.message.reply_text(f"❌ خطأ في إرسال المعاينة: {e}\nتأكد من صحة HTML.")
        return

    if data == "reset_welcome":
        if os.path.exists(ADMIN_FILES["welcome_message"]):
            os.remove(ADMIN_FILES["welcome_message"])
        await query.edit_message_text(
            "✅ تم استعادة رسالة الترحيب الافتراضية!",
            reply_markup=get_customize_keyboard(),
            parse_mode="Markdown"
        )
        return

    if data == "admin_sections":
        keyboard = get_admin_sections_keyboard()
        await query.edit_message_text(
            "🔰 لوحة تحكم الأدمن - الأقسام\n﹎﹎﹎﹎﹎﹎﹎﹎﹎﹎﹎﹎\nاختر القسم المطلوب:",
            reply_markup=keyboard
        )
        return


    if data == "section_subscription":
        keyboard = get_subscription_keyboard()
        await query.edit_message_text(
            "📢 قسم الإشتراك الإجباري\n﹎﹎﹎﹎﹎﹎﹎﹎﹎﹎﹎﹎\nالتحكم بقنوات الإشتراك الإجباري:",
            reply_markup=keyboard
        )
        return


    if data == "section_broadcast":
        keyboard = get_broadcast_keyboard()
        await query.edit_message_text(
            "📣 قسم الإذاعة والنشر\n﹎﹎﹎﹎﹎﹎﹎﹎﹎﹎﹎﹎\nاختر نوع الإذاعة:",
            reply_markup=keyboard
        )
        return


    if data == "section_stats":
        keyboard = get_stats_keyboard()
        await query.edit_message_text(
            "📊 قسم الإحصائيات\n﹎﹎﹎﹎﹎﹎﹎﹎﹎﹎﹎﹎",
            reply_markup=keyboard
        )
        return

    if data == "refresh_stats":
        keyboard = get_stats_keyboard()
        await query.edit_message_text(
            "📊 قسم الإحصائيات (تم التحديث)\n﹎﹎﹎﹎﹎﹎﹎﹎﹎﹎﹎﹎",
            reply_markup=keyboard
        )
        return


    if data == "section_alerts":
        keyboard = get_alerts_keyboard()
        await query.edit_message_text(
            "🔔 قسم التنبيهات\n﹎﹎﹎﹎﹎﹎﹎﹎﹎﹎﹎﹎\nالتحكم بتنبيهات دخول المستخدمين الجدد:",
            reply_markup=keyboard
        )
        return


    if data == "section_forward":
        keyboard = get_forward_keyboard()
        await query.edit_message_text(
            "🔄 قسم توجيه الرسائل\n﹎﹎﹎﹎﹎﹎﹎﹎﹎﹎﹎﹎\nالتحكم بتوجيه رسائل المستخدمين للأدمن:",
            reply_markup=keyboard
        )
        return



    if data == "section_users_management":
        keyboard = get_users_management_keyboard()
        await query.edit_message_text(
            "👥 قسم إدارة المستخدمين\n﹎﹎﹎﹎﹎﹎﹎﹎﹎﹎﹎﹎\n"
            "• إضافة/حذف الأدمن\n"
            "• حظر/فك حظر المستخدمين\n"
            "• تغيير المالك (للمطور فقط)\n"
            "• عرض القوائم",
            reply_markup=keyboard
        )
        return


    if data == "add_admin":
        context.user_data['admin_action'] = 'add_admin'
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="section_users_management")]]
        await query.edit_message_text(
            "➕ إضافة أدمن جديد\n﹎﹎﹎﹎﹎﹎﹎﹎﹎﹎﹎﹎\n"
            "أرسل معرف المستخدم (ID) لإضافته كأدمن:\n"
            "مثال: `8405201865`",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="MarkDown"
        )
        write_to_admin_file(ADMIN_FILES["state"], "waiting_user_id")
        return


    if data == "remove_admin":
        admins = get_admin_file_lines(ADMIN_FILES["admins_list"])
        if not admins:
            keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="section_users_management")]]
            await query.edit_message_text(
                "📭 لا يوجد أدمن مساعدين حالياً.",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return

        keyboard = []
        for admin in admins:
            keyboard.append([InlineKeyboardButton(f"🗑️ {admin}", callback_data=f"remove_admin_{admin}")])
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="section_users_management")])

        await query.edit_message_text(
            "🗑️ اختر الأدمن المراد حذفه:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    if data.startswith("remove_admin_"):
        admin_id = data.replace("remove_admin_", "")
        if remove_admin(admin_id):
            await query.answer(f"✅ تم حذف الأدمن {admin_id}")
        else:
            await query.answer("❌ لا يمكن حذف المطور الأساسي!", show_alert=True)

        keyboard = get_users_management_keyboard()
        await query.edit_message_text(
            "👥 قسم إدارة المستخدمين\n﹎﹎﹎﹎﹎﹎﹎﹎﹎﹎﹎﹎\nتم التحديث.",
            reply_markup=keyboard
        )
        return


    if data == "ban_user":
        context.user_data['admin_action'] = 'ban_user'
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="section_users_management")]]
        await query.edit_message_text(
            "🚫 حظر مستخدم\n﹎﹎﹎﹎﹎﹎﹎﹎﹎﹎﹎﹎\n"
            "أرسل معرف المستخدم (ID) لحظره:\n"
            "مثال: `8405201865`",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="MarkDown"
        )
        write_to_admin_file(ADMIN_FILES["state"], "waiting_ban_user")
        return


    if data == "unban_user":
        banned = get_admin_file_lines(ADMIN_FILES["banned_users"])
        if not banned:
            keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="section_users_management")]]
            await query.edit_message_text(
                "📭 لا يوجد مستخدمين محظورين حالياً.",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return

        keyboard = []
        for user in banned:
            keyboard.append([InlineKeyboardButton(f"✅ {user}", callback_data=f"unban_{user}")])
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="section_users_management")])

        await query.edit_message_text(
            "✅ اختر المستخدم المراد فك حظره:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    if data.startswith("unban_"):
        user_id_unban = data.replace("unban_", "")
        unban_user(user_id_unban)
        await query.answer(f"✅ تم فك حظر المستخدم {user_id_unban}")

        keyboard = get_users_management_keyboard()
        await query.edit_message_text(
            "👥 قسم إدارة المستخدمين\n﹎﹎﹎﹎﹎﹎﹎﹎﹎﹎﹎﹎\nتم التحديث.",
            reply_markup=keyboard
        )
        return


    if data == "change_owner":
        if not is_owner(user_id):
            await query.answer("⚠️ هذا الأمر للمالك فقط!", show_alert=True)
            return

        context.user_data['admin_action'] = 'change_owner'
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="section_users_management")]]
        await query.edit_message_text(
            "👑 تغيير المالك\n﹎﹎﹎﹎﹎﹎﹎﹎﹎﹎﹎﹎\n"
            "⚠️ تحذير: هذا سينقل صلاحيات المالك للمستخدم الجديد!\n\n"
            "أرسل معرف المستخدم (ID) للمالك الجديد:\n"
            "مثال: `8405201865`",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="MarkDown"
        )
        write_to_admin_file(ADMIN_FILES["state"], "waiting_new_owner")
        return


    if data == "list_admins":
        admins = get_admin_file_lines(ADMIN_FILES["admins_list"])
        owner = get_admin_file_content(ADMIN_FILES["owner"])

        text = "👑 قائمة الأدمن:\n﹎﹎﹎﹎﹎﹎﹎﹎﹎﹎﹎﹎\n"
        text += f"👑 المالك: `{owner}`\n\n"

        if admins:
            text += "👥 الأدمن المساعدين:\n"
            for admin in admins:
                text += f"• `{admin}`\n"
        else:
            text += "📭 لا يوجد أدمن مساعدين."

        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="section_users_management")]]
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="MarkDown"
        )
        return


    if data == "list_banned":
        banned = get_admin_file_lines(ADMIN_FILES["banned_users"])

        text = "🚷 قائمة المستخدمين المحظورين:\n﹎﹎﹎﹎﹎﹎﹎﹎﹎﹎﹎﹎\n"
        if banned:
            for user in banned:
                text += f"• `{user}`\n"
        else:
            text += "📭 لا يوجد مستخدمين محظورين."

        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="section_users_management")]]
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="MarkDown"
        )
        return


    if data == "list_all_users":
        users = get_admin_file_lines(ADMIN_FILES["users"])

        text = f"👤 قائمة المستخدمين:\n﹎﹎﹎﹎﹎﹎﹎﹎﹎﹎﹎﹎\n"
        text += f"📊 إجمالي المستخدمين: {len(users)}\n\n"

        if users:
            for user in users[:20]:
                text += f"• `{user}`\n"
            if len(users) > 20:
                text += f"\n... و {len(users) - 20} مستخدم آخر"

        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="section_users_management")]]
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="MarkDown"
        )
        return


    if data == "sub1_info":
        ch1 = get_admin_file_content(ADMIN_FILES["channel1"]) or "لا يوجد"
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="section_subscription")]]
        await query.edit_message_text(
            f"📢 القناة الأولى:\n{ch1}\n\nقم برفع البوت أدمن في القناة لتفعيل الإشتراك الإجباري.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    if data == "sub2_info":
        ch2 = get_admin_file_content(ADMIN_FILES["channel2"]) or "لا يوجد"
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="section_subscription")]]
        await query.edit_message_text(
            f"📢 القناة الثانية:\n{ch2}\n\nقم برفع البوت أدمن في القناة لتفعيل الإشتراك الإجباري.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return


    if data == "broadcast_users":
        users_count = len(get_admin_file_lines(ADMIN_FILES["users"]))
        await query.edit_message_text(
            f"👤 إذاعة للمستخدمين\n﹎﹎﹎﹎﹎﹎﹎﹎﹎﹎﹎﹎\nعدد المستخدمين: {users_count}\n\nاختر نوع الإذاعة:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📨 توجيه", callback_data="Dyler5")],
                [InlineKeyboardButton("📝 نصي", callback_data="Dyler6")],
                [InlineKeyboardButton("🔙 رجوع", callback_data="section_broadcast")]
            ])
        )
        return

    if data == "broadcast_groups":
        groups_count = len(get_admin_file_lines(ADMIN_FILES["groups"]))
        await query.edit_message_text(
            f"👥 إذاعة للمجموعات\n﹎﹎﹎﹎﹎﹎﹎﹎﹎﹎﹎﹎\nعدد المجموعات: {groups_count}\n\nاختر نوع الإذاعة:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📨 توجيه", callback_data="DylerGro")],
                [InlineKeyboardButton("📝 نصي", callback_data="DylerGr")],
                [InlineKeyboardButton("🔙 رجوع", callback_data="section_broadcast")]
            ])
        )
        return

    if data == "broadcast_channels":
        channels_count = len(get_admin_file_lines(ADMIN_FILES["channels"]))
        await query.edit_message_text(
            f"📢 إذاعة للقنوات\n﹎﹎﹎﹎﹎﹎﹎﹎﹎﹎﹎﹎\nعدد القنوات: {channels_count}\n\nاختر نوع الإذاعة:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📨 توجيه", callback_data="Dylerch")],
                [InlineKeyboardButton("📝 نصي", callback_data="Dylerchtx")],
                [InlineKeyboardButton("🔙 رجوع", callback_data="section_broadcast")]
            ])
        )
        return

    if data == "noop":
        await query.answer()
        return



    state = get_admin_file_content(ADMIN_FILES["state"])
    users_list = get_admin_file_lines(ADMIN_FILES["users"])
    groups_list = get_admin_file_lines(ADMIN_FILES["groups"])
    channels_list = get_admin_file_lines(ADMIN_FILES["channels"])


    context.user_data['admin_state'] = state
    context.user_data['admin_chat_id'] = chat_id
    context.user_data['admin_message_id'] = message_id


    if data == "Dyler":
        keyboard = get_admin_sections_keyboard()
        await query.edit_message_text(
            "🔰 لوحة تحكم الأدمن - الأقسام\n﹎﹎﹎﹎﹎﹎﹎﹎﹎﹎﹎﹎\nاختر القسم المطلوب:",
            reply_markup=keyboard
        )
        if os.path.exists(ADMIN_FILES["state"]):
            os.remove(ADMIN_FILES["state"])
        return


    elif data == "Dyler0":
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="section_subscription")]]
        await query.edit_message_text(
            "- حسناً، الآن قم بإرسال معرف قناتك ليتم وضعه في خدمة الإشتراك الإجباري للقناة الأولى\n#مثال:\n▪️@channel",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        write_to_admin_file(ADMIN_FILES["state"], "Dyler0")


    elif data == "Dyler2":
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="section_subscription")]]
        await query.edit_message_text(
            "- حسناً، الآن قم بإرسال معرف قناتك ليتم وضعه في خدمة الإشتراك الإجباري للقناة الثانية\n#مثال:\n▪️@channel",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        write_to_admin_file(ADMIN_FILES["state"], "Dyler1")


    elif data == "Dyler4":
        ch1 = get_admin_file_content(ADMIN_FILES["channel1"]) or "لا يوجد"
        ch2 = get_admin_file_content(ADMIN_FILES["channel2"]) or "لا يوجد"
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="section_subscription")]]
        await query.edit_message_text(
            f"- هذه قائمة القنوات الإشتراك الإجباري 🔰\n- القناة الأولى: {ch1} 📢\n- القناة الثانية: {ch2} 📣\n﹎﹎﹎﹎﹎﹎﹎﹎﹎﹎﹎﹎",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        if os.path.exists(ADMIN_FILES["state"]):
            os.remove(ADMIN_FILES["state"])


    elif data == "Dyler5":
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="section_broadcast")]]
        await query.edit_message_text(
            f"~ أرسل رسالتك وسيتم توجيهها لـ [ {len(users_list)} ] مشترك 🐙",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        write_to_admin_file(ADMIN_FILES["state"], "Dyler2")
        context.user_data['broadcast_type'] = 'forward_users'


    elif data == "Dyler6":
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="section_broadcast")]]
        await query.edit_message_text(
            f"~ أرسل رسالتك وسيتم إرسالها لـ [ {len(users_list)} ] مشترك 🐠",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        write_to_admin_file(ADMIN_FILES["state"], "Dyler3")
        context.user_data['broadcast_type'] = 'text_users'


    elif data == "DylerGro":
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="section_broadcast")]]
        await query.edit_message_text(
            f"~ أرسل رسالتك وسيتم توجيهها لـ [ {len(groups_list)} ] كروب 🐙",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        write_to_admin_file(ADMIN_FILES["state"], "DylerGro")
        context.user_data['broadcast_type'] = 'forward_groups'


    elif data == "DylerGr":
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="section_broadcast")]]
        await query.edit_message_text(
            f"~ أرسل رسالتك وسيتم إرسالها لـ [ {len(groups_list)} ] كروب 🐠",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        write_to_admin_file(ADMIN_FILES["state"], "DylerGr")
        context.user_data['broadcast_type'] = 'text_groups'


    elif data == "Dylerch":
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="section_broadcast")]]
        await query.edit_message_text(
            f"~ أرسل رسالتك وسيتم توجيهها لـ [ {len(channels_list)} ] قناة 🐙",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        write_to_admin_file(ADMIN_FILES["state"], "Dylerch")
        context.user_data['broadcast_type'] = 'forward_channels'


    elif data == "Dylerchtx":
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="section_broadcast")]]
        await query.edit_message_text(
            f"~ أرسل رسالتك وسيتم إرسالها لـ [ {len(channels_list)} ] قناة 🐠",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        write_to_admin_file(ADMIN_FILES["state"], "Dyleroch")
        context.user_data['broadcast_type'] = 'text_channels'


    elif data == "Dyler7":
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="admin_sections")]]
        await query.edit_message_text(
            f"- عدد مشتركين البوت [ {len(users_list)} ] مشترك 🦑",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data == "Dyler77":
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="admin_sections")]]
        await query.edit_message_text(
            f"- عدد قنوات البوت [ {len(channels_list)} ] قناة 🦑",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data == "Dyler777":
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="admin_sections")]]
        await query.edit_message_text(
            f"- عدد كروبات البوت [ {len(groups_list)} ] كروب 🦑",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )


    elif data == "Dyler9":
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="section_alerts")]]
        await query.edit_message_text(
            "- تم تفعيل دخول المشتركين 🐎",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        write_to_admin_file(ADMIN_FILES["notify"], "Dyler")


    elif data == "Dyler10":
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="section_alerts")]]
        await query.edit_message_text(
            "- تم تعطيل دخول المشتركين 🦍",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        if os.path.exists(ADMIN_FILES["notify"]):
            os.remove(ADMIN_FILES["notify"])


    elif data == "Dyler11":
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="section_forward")]]
        await query.edit_message_text(
            "- تم تفعيل توجيه الرسائل 🦇",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        write_to_admin_file(ADMIN_FILES["forward"], "Dyler")


    elif data == "Dyler12":
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="section_forward")]]
        await query.edit_message_text(
            "- تم تعطيل توجيه الرسائل 🐌",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        if os.path.exists(ADMIN_FILES["forward"]):
            os.remove(ADMIN_FILES["forward"])


    elif data == "delete11":
        keyboard = [
            [InlineKeyboardButton("• لا ❎", callback_data="section_subscription"),
             InlineKeyboardButton("• نعم 💬", callback_data="Dyler1")]
        ]
        await query.edit_message_text(
            "- حسناً هل أنت متأكد من أنك تريد حذف القناة من الإشتراك الإجباري 🚫",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )


    elif data == "Dyler1":
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="section_subscription")]]
        await query.edit_message_text(
            "- لقد تم حذف القناة الأولى من الإشتراك الإجباري بنجاح 📮",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        if os.path.exists(ADMIN_FILES["channel1"]):
            os.remove(ADMIN_FILES["channel1"])
        if os.path.exists(ADMIN_FILES["state"]):
            os.remove(ADMIN_FILES["state"])


    elif data == "delete22":
        keyboard = [
            [InlineKeyboardButton("• لا ❎", callback_data="section_subscription"),
             InlineKeyboardButton("• نعم 💬", callback_data="Dyler3")]
        ]
        await query.edit_message_text(
            "- حسناً هل أنت متأكد من أنك تريد حذف القناة من الإشتراك الإجباري 🚫",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )


    elif data == "Dyler3":
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="section_subscription")]]
        await query.edit_message_text(
            "- لقد تم حذف القناة الثانية من الإشتراك الإجباري بنجاح 📮",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        if os.path.exists(ADMIN_FILES["channel2"]):
            os.remove(ADMIN_FILES["channel2"])
        if os.path.exists(ADMIN_FILES["state"]):
            os.remove(ADMIN_FILES["state"])


    elif data in ["sub1", "sub2", "broadcast", "alert", "forward"]:
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="admin_sections")]]
        await query.edit_message_text(
            f"- اختر الأمر المناسب من القائمة أعلاه 🐬",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    else:

        await query.answer("⚠️ حدث خطأ، حاول مرة أخرى", show_alert=True)


async def handle_admin_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة رسائل الأدمن للإذاعات وإعداد القنوات وإدارة المستخدمين"""
    message = update.message
    chat_id = message.chat_id
    user_id = message.from_user.id
    text = message.text
    message_id = message.message_id


    if not is_admin(user_id):
        return

    state = get_admin_file_content(ADMIN_FILES["state"])
    users_list = get_admin_file_lines(ADMIN_FILES["users"])
    groups_list = get_admin_file_lines(ADMIN_FILES["groups"])
    channels_list = get_admin_file_lines(ADMIN_FILES["channels"])



    if state == "waiting_welcome_message" and text:

        try:
            test_text = text.format(
                first_name="Test",
                last_name="User",
                username="test",
                user_id=123456,
                developer_username=DEVELOPER_USERNAME
            )

            await message.reply_text(
                "⏳ جاري التحقق من صحة HTML...",
                parse_mode="Markdown"
            )
            await message.reply_text(
                test_text,
                parse_mode="HTML"
            )

            write_to_admin_file(ADMIN_FILES["welcome_message"], text)
            await message.reply_text(
                "✅ تم حفظ رسالة الترحيب الجديدة!\n\n"
                "📝 تم التحقق من صحة HTML بنجاح.\n"
                "👁️ استخدم زر 'معاينة' لرؤيتها بشكل كامل مع صورتك.",
                parse_mode="Markdown",
                reply_markup=get_customize_keyboard()
            )
        except Exception as e:
            await message.reply_text(
                f"❌ خطأ في صيغة HTML!\n\n"
                f"الخطأ: `{str(e)[:200]}`\n\n"
                f"يرجى التأكد من صحة الوسوم وإعادة المحاولة.\n"
                f"مثال: `<b>نص عريض</b>`\n"
                f"أو أرسل /start للإلغاء.",
                parse_mode="Markdown"
            )
            return

        if os.path.exists(ADMIN_FILES["state"]):
            os.remove(ADMIN_FILES["state"])
        return


    if state == "waiting_user_id" and text:


        if str(user_id) != str(DEVELOPER_ID) and not is_owner(user_id):
            await message.reply_text("⚠️ فقط المطور أو المالك يمكنه إضافة أدمن!")
            if os.path.exists(ADMIN_FILES["state"]):
                os.remove(ADMIN_FILES["state"])
            return

        if text.isdigit() or (text.startswith('-') and text[1:].isdigit()):
            user_id_input = text
            if add_admin(user_id_input):
                await message.reply_text(f"✅ تم إضافة المستخدم `{user_id_input}` كأدمن بنجاح!", parse_mode="MarkDown")
            else:
                await message.reply_text(f"⚠️ المستخدم `{user_id_input}` موجود بالفعل أو هو المطور الأساسي!", parse_mode="MarkDown")
        else:
            await message.reply_text("❌ يرجى إرسال ID صحيح (أرقام فقط).")

        if os.path.exists(ADMIN_FILES["state"]):
            os.remove(ADMIN_FILES["state"])
        return


    if state == "waiting_ban_user" and text:
        if text.isdigit() or (text.startswith('-') and text[1:].isdigit()):
            user_id_input = text


            if str(user_id_input) == str(DEVELOPER_ID):
                await message.reply_text("⚠️ لا يمكن حظر المطور الأساسي!")

            elif is_owner(user_id_input):
                await message.reply_text("⚠️ لا يمكن حظر المالك!")

            elif is_admin(user_id_input):
                await message.reply_text("⚠️ لا يمكن حظر أدمن!")
            elif ban_user(user_id_input):
                await message.reply_text(f"✅ تم حظر المستخدم `{user_id_input}` بنجاح!", parse_mode="MarkDown")
            else:
                await message.reply_text(f"⚠️ المستخدم `{user_id_input}` محظور بالفعل!", parse_mode="MarkDown")
        else:
            await message.reply_text("❌ يرجى إرسال ID صحيح (أرقام فقط).")

        if os.path.exists(ADMIN_FILES["state"]):
            os.remove(ADMIN_FILES["state"])
        return


    if state == "waiting_new_owner" and text:

        if str(user_id) != str(DEVELOPER_ID):
            await message.reply_text("⚠️ فقط المطور الأساسي يمكنه تغيير المالك!")
            if os.path.exists(ADMIN_FILES["state"]):
                os.remove(ADMIN_FILES["state"])
            return

        if text.isdigit():
            new_owner = text
            if change_owner(new_owner):
                await message.reply_text(f"✅ تم تغيير المالك إلى `{new_owner}` بنجاح!", parse_mode="MarkDown")
            else:
                await message.reply_text("❌ فشل تغيير المالك، تأكد من أن ID صحيح.")
        else:
            await message.reply_text("❌ يرجى إرسال ID صحيح (أرقام فقط).")

        if os.path.exists(ADMIN_FILES["state"]):
            os.remove(ADMIN_FILES["state"])
        return


    if state == "Dyler0" and text:
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="section_subscription")]]
        await message.reply_text(
            "- لقد تم وضع القناة بنجاح 📣\n- قم برفع البوت أدمن داخل القناة 🗞",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        write_to_admin_file(ADMIN_FILES["channel1"], text)
        if os.path.exists(ADMIN_FILES["state"]):
            os.remove(ADMIN_FILES["state"])
        return


    if state == "Dyler1" and text:
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="section_subscription")]]
        await message.reply_text(
            "- لقد تم وضع القناة بنجاح 📣\n- قم برفع البوت أدمن داخل القناة 🗞",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        write_to_admin_file(ADMIN_FILES["channel2"], text)
        if os.path.exists(ADMIN_FILES["state"]):
            os.remove(ADMIN_FILES["state"])
        return


    if state == "Dyler2":
        success_count = 0
        fail_count = 0
        status_msg = await message.reply_text("⏳ جاري إرسال التوجيه للمستخدمين...")

        for user in users_list:
            if user and str(user) != str(user_id):

                if is_banned(int(user)):
                    continue
                try:
                    await context.bot.forward_message(
                        chat_id=int(user),
                        from_chat_id=chat_id,
                        message_id=message_id
                    )
                    success_count += 1
                    await asyncio.sleep(0.5)
                except Exception as e:
                    fail_count += 1
                    logger.error(f"فشل التوجيه للمستخدم {user}: {e}")

        await status_msg.edit_text(
            f"✅ تم التوجيه بنجاح\n"
            f"📨 تم الإرسال لـ {success_count} مستخدم\n"
            f"❌ فشل الإرسال لـ {fail_count} مستخدم"
        )

        if os.path.exists(ADMIN_FILES["state"]):
            os.remove(ADMIN_FILES["state"])
        return


    if state == "Dyler3" and text:
        success_count = 0
        fail_count = 0
        status_msg = await message.reply_text("⏳ جاري إرسال الرسالة للمستخدمين...")

        for user in users_list:
            if user and str(user) != str(user_id):

                if is_banned(int(user)):
                    continue
                try:
                    await context.bot.send_message(chat_id=int(user), text=text)
                    success_count += 1
                    await asyncio.sleep(0.5)
                except Exception as e:
                    fail_count += 1
                    logger.error(f"فشل الإرسال للمستخدم {user}: {e}")

        await status_msg.edit_text(
            f"✅ تم النشر بنجاح\n"
            f"📨 تم الإرسال لـ {success_count} مستخدم\n"
            f"❌ فشل الإرسال لـ {fail_count} مستخدم"
        )

        if os.path.exists(ADMIN_FILES["state"]):
            os.remove(ADMIN_FILES["state"])
        return


    if state == "DylerGro":
        success_count = 0
        fail_count = 0
        status_msg = await message.reply_text("⏳ جاري إرسال التوجيه للمجموعات...")

        for group in groups_list:
            if group:
                try:
                    await context.bot.forward_message(
                        chat_id=int(group),
                        from_chat_id=chat_id,
                        message_id=message_id
                    )
                    success_count += 1
                    await asyncio.sleep(1)
                except Exception as e:
                    fail_count += 1
                    logger.error(f"فشل التوجيه للمجموعة {group}: {e}")

        await status_msg.edit_text(
            f"✅ تم التوجيه بنجاح\n"
            f"📨 تم الإرسال لـ {success_count} مجموعة\n"
            f"❌ فشل الإرسال لـ {fail_count} مجموعة"
        )

        if os.path.exists(ADMIN_FILES["state"]):
            os.remove(ADMIN_FILES["state"])
        return


    if state == "DylerGr" and text:
        success_count = 0
        fail_count = 0
        status_msg = await message.reply_text("⏳ جاري إرسال الرسالة للمجموعات...")

        for group in groups_list:
            if group:
                try:
                    await context.bot.send_message(chat_id=int(group), text=text)
                    success_count += 1
                    await asyncio.sleep(1)
                except Exception as e:
                    fail_count += 1
                    logger.error(f"فشل الإرسال للمجموعة {group}: {e}")

        await status_msg.edit_text(
            f"✅ تم النشر بنجاح\n"
            f"📨 تم الإرسال لـ {success_count} مجموعة\n"
            f"❌ فشل الإرسال لـ {fail_count} مجموعة"
        )

        if os.path.exists(ADMIN_FILES["state"]):
            os.remove(ADMIN_FILES["state"])
        return


    if state == "Dylerch":
        success_count = 0
        fail_count = 0
        status_msg = await message.reply_text("⏳ جاري إرسال التوجيه للقنوات...")

        for channel in channels_list:
            if channel:
                try:
                    await context.bot.forward_message(
                        chat_id=int(channel),
                        from_chat_id=chat_id,
                        message_id=message_id
                    )
                    success_count += 1
                    await asyncio.sleep(1)
                except Exception as e:
                    fail_count += 1
                    logger.error(f"فشل التوجيه للقناة {channel}: {e}")

        await status_msg.edit_text(
            f"✅ تم التوجيه بنجاح\n"
            f"📨 تم الإرسال لـ {success_count} قناة\n"
            f"❌ فشل الإرسال لـ {fail_count} قناة"
        )

        if os.path.exists(ADMIN_FILES["state"]):
            os.remove(ADMIN_FILES["state"])
        return


    if state == "Dyleroch" and text:
        success_count = 0
        fail_count = 0
        status_msg = await message.reply_text("⏳ جاري إرسال الرسالة للقنوات...")

        for channel in channels_list:
            if channel:
                try:
                    await context.bot.send_message(chat_id=int(channel), text=text)
                    success_count += 1
                    await asyncio.sleep(1)
                except Exception as e:
                    fail_count += 1
                    logger.error(f"فشل الإرسال للقناة {channel}: {e}")

        await status_msg.edit_text(
            f"✅ تم النشر بنجاح\n"
            f"📨 تم الإرسال لـ {success_count} قناة\n"
            f"❌ فشل الإرسال لـ {fail_count} قناة"
        )

        if os.path.exists(ADMIN_FILES["state"]):
            os.remove(ADMIN_FILES["state"])
        return


async def settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض لوحة الإعدادات"""
    query = update.callback_query
    await query.answer()
    
    settings = load_settings()
    
    text = (
        "⚙️ **لوحة إعدادات البوت**\n"
        "﹎﹎﹎﹎﹎﹎﹎﹎﹎﹎﹎﹎\n"
        "من هنا يمكنك التحكم في:\n"
        "• عدد الحسابات المسموحة\n"
        "• سرعة الإضافة والتأخيرات\n"
        "• عدد الرسائل للفحص\n"
        "• قوة المعالجة المتوازية\n"
        "﹎﹎﹎﹎﹎﹎﹎﹎﹎﹎﹎﹎\n"
        f"📊 **الإعدادات الحالية:**\n"
        f"• أقصى حسابات: `{settings['MAX_ACCOUNTS']}`\n"
        f"• جهات اتصال/حساب: `{settings['CONTACTS_PER_ACCOUNT']}`\n"
        f"• تأخير الإضافة: `{settings['ADD_DELAY']} ثانية`\n"
        f"• تأخير إضافة جهات: `{settings['CONTACT_ADD_DELAY']} ثانية`\n"
        f"• حجم دفعة السحب: `{settings['SCRAPE_BATCH_SIZE']}`\n"
        f"• عدد الرسائل للفحص: `{settings['MAX_MESSAGES_SCRAPE']:,}`\n"
        f"• عمال متوازيين: `{settings['PARALLEL_WORKERS']}`\n"
        "﹎﹎﹎﹎﹎﹎﹎﹎﹎﹎﹎﹎\n"
        "⚠️ **تنبيه:** تغيير الإعدادات يؤثر على سرعة وأمان البوت!"
    )
    
    await query.edit_message_text(text, reply_markup=get_settings_keyboard(), parse_mode="Markdown")

async def handle_settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة تعديل الإعدادات"""
    query = update.callback_query
    data = query.data
    
    if not data.startswith("set_") and data != "reset_all_settings" and data != "view_all_settings":
        return
    
    await query.answer()
    
    settings = load_settings()
    
    # معالجة الأزرار
    if data == "set_MAX_ACCOUNTS_down":
        settings['MAX_ACCOUNTS'] = max(10, settings['MAX_ACCOUNTS'] - 10)
    elif data == "set_MAX_ACCOUNTS_up":
        settings['MAX_ACCOUNTS'] = min(1000, settings['MAX_ACCOUNTS'] + 10)
    
    elif data == "set_CONTACTS_PER_ACCOUNT_down":
        settings['CONTACTS_PER_ACCOUNT'] = max(10, settings['CONTACTS_PER_ACCOUNT'] - 10)
    elif data == "set_CONTACTS_PER_ACCOUNT_up":
        settings['CONTACTS_PER_ACCOUNT'] = min(500, settings['CONTACTS_PER_ACCOUNT'] + 10)
    
    elif data == "set_ADD_DELAY_down":
        settings['ADD_DELAY'] = max(1, settings['ADD_DELAY'] - 1)
    elif data == "set_ADD_DELAY_up":
        settings['ADD_DELAY'] = min(30, settings['ADD_DELAY'] + 1)
    
    elif data == "set_CONTACT_ADD_DELAY_down":
        settings['CONTACT_ADD_DELAY'] = max(0.2, round(settings['CONTACT_ADD_DELAY'] - 0.2, 1))
    elif data == "set_CONTACT_ADD_DELAY_up":
        settings['CONTACT_ADD_DELAY'] = min(5, round(settings['CONTACT_ADD_DELAY'] + 0.2, 1))
    
    elif data == "set_SCRAPE_BATCH_SIZE_down":
        settings['SCRAPE_BATCH_SIZE'] = max(10, settings['SCRAPE_BATCH_SIZE'] - 10)
    elif data == "set_SCRAPE_BATCH_SIZE_up":
        settings['SCRAPE_BATCH_SIZE'] = min(500, settings['SCRAPE_BATCH_SIZE'] + 10)
    
    elif data == "set_MAX_MESSAGES_SCRAPE_down":
        settings['MAX_MESSAGES_SCRAPE'] = max(1000, settings['MAX_MESSAGES_SCRAPE'] - 1000)
    elif data == "set_MAX_MESSAGES_SCRAPE_up":
        settings['MAX_MESSAGES_SCRAPE'] = min(100000, settings['MAX_MESSAGES_SCRAPE'] + 1000)
    
    elif data == "set_PARALLEL_WORKERS_down":
        settings['PARALLEL_WORKERS'] = max(1, settings['PARALLEL_WORKERS'] - 1)
    elif data == "set_PARALLEL_WORKERS_up":
        settings['PARALLEL_WORKERS'] = min(20, settings['PARALLEL_WORKERS'] + 1)
    
    elif data == "reset_all_settings":
        settings = DEFAULT_SETTINGS.copy()
        await query.answer("✅ تم إعادة ضبط جميع الإعدادات!", show_alert=True)
    
    elif data == "view_all_settings":
        text = (
            "📋 جميع إعدادات البوت\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            f"MAX_ACCOUNTS: {settings['MAX_ACCOUNTS']}\n"
            f"CONTACTS_PER_ACCOUNT: {settings['CONTACTS_PER_ACCOUNT']}\n"
            f"ADD_DELAY: {settings['ADD_DELAY']}\n"
            f"CONTACT_ADD_DELAY: {settings['CONTACT_ADD_DELAY']}\n"
            f"SCRAPE_BATCH_SIZE: {settings['SCRAPE_BATCH_SIZE']}\n"
            f"MAX_MESSAGES_SCRAPE: {settings['MAX_MESSAGES_SCRAPE']}\n"
            f"PARALLEL_WORKERS: {settings['PARALLEL_WORKERS']}\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "تم حفظ الإعدادات بنجاح!"
        )
        try:
            await query.edit_message_text(text, parse_mode=None)
        except:
            await query.message.reply_text(text)
        await asyncio.sleep(3)
        await query.edit_message_text(
            "⚙️ لوحة إعدادات البوت",
            reply_markup=get_settings_keyboard()
        )
        return
    
    # حفظ الإعدادات
    save_settings(settings)
    
    # تحديث المتغيرات العامة
    global BOT_SETTINGS, MAX_ACCOUNTS, CONTACTS_PER_ACCOUNT, ADD_DELAY
    global CONTACT_ADD_DELAY, SCRAPE_BATCH_SIZE, MAX_MESSAGES_SCRAPE
    
    BOT_SETTINGS = settings
    MAX_ACCOUNTS = settings['MAX_ACCOUNTS']
    CONTACTS_PER_ACCOUNT = settings['CONTACTS_PER_ACCOUNT']
    ADD_DELAY = settings['ADD_DELAY']
    CONTACT_ADD_DELAY = settings['CONTACT_ADD_DELAY']
    SCRAPE_BATCH_SIZE = settings['SCRAPE_BATCH_SIZE']
    MAX_MESSAGES_SCRAPE = settings['MAX_MESSAGES_SCRAPE']
    
    # نص بدون HTML لتجنب أخطاء التحليل
    text = (
        "⚙️ لوحة إعدادات البوت\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"تم تحديث الإعدادات!\n\n"
        f"MAX_ACCOUNTS: {settings['MAX_ACCOUNTS']}\n"
        f"CONTACTS_PER_ACCOUNT: {settings['CONTACTS_PER_ACCOUNT']}\n"
        f"ADD_DELAY: {settings['ADD_DELAY']} ثانية\n"
        f"CONTACT_ADD_DELAY: {settings['CONTACT_ADD_DELAY']} ثانية\n"
        f"SCRAPE_BATCH_SIZE: {settings['SCRAPE_BATCH_SIZE']}\n"
        f"MAX_MESSAGES_SCRAPE: {settings['MAX_MESSAGES_SCRAPE']}\n"
        f"PARALLEL_WORKERS: {settings['PARALLEL_WORKERS']}\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "تغيير الإعدادات يؤثر على سرعة وأمان البوت!"
    )
    
    try:
        await query.edit_message_text(text, parse_mode=None, reply_markup=get_settings_keyboard())
    except Exception as e:
        # إذا فشل التعديل، أرسل رسالة جديدة
        await query.message.reply_text(text, reply_markup=get_settings_keyboard())

async def handle_new_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة المستخدمين الجدد وإضافتهم للملفات"""
    message = update.message
    if not message:
        return

    chat = message.chat
    from_user = message.from_user
    chat_type = chat.type
    user_id = from_user.id
    chat_id = chat.id

    forward_enabled = get_admin_file_content(ADMIN_FILES["forward"])
    notify_enabled = get_admin_file_content(ADMIN_FILES["notify"])


    if chat_type == "private":
        users_list = get_admin_file_lines(ADMIN_FILES["users"])
        if str(user_id) not in users_list:
            write_to_admin_file(ADMIN_FILES["users"], user_id, append=True)


            if notify_enabled == "Dyler" and user_id != ADMIN_ID:
                first_name = from_user.first_name or ""
                username = from_user.username or ""
                users_count = len(get_admin_file_lines(ADMIN_FILES["users"]))
                try:
                    await context.bot.send_message(
                        chat_id=ADMIN_ID,
                        text=f"- عضو جديد قام بالدخول الى البوت 🛡\n- الاسم {first_name}\n- المعرف @{username}\n- الايدي `{user_id}`\n﹎﹎﹎﹎﹎﹎﹎﹎﹎﹎﹎﹎\n~ عدد المشتركين {users_count} 🦑",
                        parse_mode="MarkDown"
                    )
                except Exception as e:
                    logger.error(f"فشل إرسال الإشعار: {e}")

    elif chat_type in ["group", "supergroup"]:
        groups_list = get_admin_file_lines(ADMIN_FILES["groups"])
        if str(chat_id) not in groups_list:
            write_to_admin_file(ADMIN_FILES["groups"], chat_id, append=True)

    elif chat_type == "channel":
        channels_list = get_admin_file_lines(ADMIN_FILES["channels"])
        if str(chat_id) not in channels_list:
            write_to_admin_file(ADMIN_FILES["channels"], chat_id, append=True)


    if forward_enabled == "Dyler" and chat_type == "private" and user_id != ADMIN_ID:
        try:
            await context.bot.forward_message(
                chat_id=ADMIN_ID,
                from_chat_id=user_id,
                message_id=message.message_id
            )
        except Exception as e:
            logger.error(f"فشل توجيه الرسالة: {e}")


    if forward_enabled == "Dyler" and user_id == ADMIN_ID and message.reply_to_message:
        reply_to = message.reply_to_message
        if reply_to.forward_from:
            target_id = reply_to.forward_from.id
            if target_id and text:
                try:
                    await context.bot.send_message(chat_id=target_id, text=text)
                except Exception as e:
                    logger.error(f"فشل إرسال الرد: {e}")


async def stop_process_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global STOP_PROCESS
    STOP_PROCESS = True
    await update.callback_query.answer("⚠️ تم إرسال طلب الإيقاف، سيتم التوقف قريباً...")

async def check_subscription_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """التحقق من اشتراك المستخدم في القنوات الإجبارية"""
    query = update.callback_query
    user_id = query.from_user.id

    await query.answer("⏳ جاري التحقق من اشتراكك...")

    channel1 = get_admin_file_content(ADMIN_FILES["channel1"])
    channel2 = get_admin_file_content(ADMIN_FILES["channel2"])


    def extract_channel_username(channel):
        if not channel:
            return None
        if channel.startswith('https://t.me/'):
            return channel.replace('https://t.me/', '').split('?')[0]
        if channel.startswith('@'):
            return channel[1:]
        return channel.replace('@', '')

    username1 = extract_channel_username(channel1)
    username2 = extract_channel_username(channel2)

    not_subscribed = []

    try:
        if username1:
            resp = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getChatMember", params={
                "chat_id": f"@{username1}", "user_id": user_id
            })
            data = resp.json()
            status = data.get("result", {}).get("status", "")
            if status in ["left", "kicked"]:
                not_subscribed.append(channel1)

        if username2:
            resp = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getChatMember", params={
                "chat_id": f"@{username2}", "user_id": user_id
            })
            data = resp.json()
            status = data.get("result", {}).get("status", "")
            if status in ["left", "kicked"]:
                not_subscribed.append(channel2)

        if not_subscribed:
            keyboard = []
            for ch in not_subscribed:
                link = format_channel_link(ch)
                if link:
                    keyboard.append([InlineKeyboardButton("📢 اشترك الآن", url=link)])
            keyboard.append([InlineKeyboardButton("🔄 إعادة التحقق", callback_data="check_subscription")])

            await query.message.reply_text(
                f"⚠️ لم تشترك بعد في القنوات التالية: ⚠️\n\n"
                f"• {chr(10).join(not_subscribed)}\n\n"
                f"📢 اشترك ثم اضغط على زر إعادة التحقق.",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
            try:
                await query.message.delete()
            except:
                pass
        else:
            await query.message.edit_text(
                f"✅ تم التحقق بنجاح!\n\n"
                f"أهلاً بك في البوت 🎉",
                parse_mode="Markdown"
            )
            await start(update, context)

    except Exception as e:
        logger.error(f"خطأ في التحقق من الاشتراك: {e}")
        await query.message.reply_text(
            "❌ حدث خطأ أثناء التحقق، يرجى المحاولة مرة أخرى.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 إعادة المحاولة", callback_data="check_subscription")]])
        )



async def add_acc_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بدء إضافة حساب جديد - استخراج API تلقائي"""
    query = update.callback_query
    await query.answer()

    if db.get_account_count() >= MAX_ACCOUNTS:
        await query.edit_message_text("⚠️ وصلت للحد الأقصى من الحسابات (500).")
        return ConversationHandler.END

    await query.edit_message_text(
        "🤖 إضافة حساب جديد - استخراج تلقائي للـ API\n\n"
        "📱 يرجى إرسال رقم الهاتف (مع رمز الدولة)\n"
        "مثال: `+218910000000`\n\n"
        "⚠️ سيتم استخراج `api_id` و `api_hash` تلقائياً بعد التحقق.",
        parse_mode="Markdown"
    )
    return A_PHONE

async def a_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة رقم الهاتف وبدء عملية استخراج API"""
    phone = update.message.text.strip().replace(" ", "")

    if not phone.startswith('+') or not phone[1:].isdigit():
        await update.message.reply_text(
            "❌ صيغة غير صحيحة!\nيرجى إرسال الرقم بالصيغة الدولية:\nمثال: `+218910000000`",
            parse_mode="Markdown"
        )
        return A_PHONE

    context.user_data['auto_phone'] = phone


    from datetime import datetime
    creator = TelegramAPICreator(update.effective_user.id)
    creator.phone_number = phone
    context.user_data['auto_api_creator'] = creator

    msg = await update.message.reply_text("⏳ جاري إرسال رمز التحقق إلى هاتفك...")

    if creator.send_password():
        await msg.edit_text(
            "✅ تم إرسال رمز التحقق!\n\n"
            "📲 يرجى إدخال الرمز الذي تلقيته على هاتفك:",
            parse_mode="Markdown"
        )
        return A_CODE
    else:
        await msg.edit_text(
            "❌ فشل في إرسال رمز التحقق!\n\n"
            "الرجاء التأكد من صحة رقم الهاتف والمحاولة مرة أخرى.\n"
            "الأسباب المحتملة:\n"
            "• رقم الهاتف غير صحيح\n"
            "• مشكلة في الاتصال بخوادم تيليجرام\n"
            "• تم إرسال طلبات كثيرة مؤخراً\n\n"
            "أو أرسل /start للبدء من جديد.",
            parse_mode="Markdown"
        )
        return ConversationHandler.END

async def a_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الكود - يجب أن يكون الرقم من my.telegram.org"""
    import random
    import string

    code = update.message.text.strip()
    creator = context.user_data.get('auto_api_creator')
    phone = context.user_data.get('auto_phone')

    if not creator or not phone:
        await update.message.reply_text("❌ حدث خطأ، يرجى إرسال /start للبدء من جديد.")
        return ConversationHandler.END


    if not code:
        await update.message.reply_text(
            "❌ رمز التحقق غير صحيح!\n\n"
            "الرجاء إدخال رمز التحقق.\n\n"
            "📌 ملاحظة: هذا الرمز يصل من موقع my.telegram.org، وليس من تطبيق تيليجرام.",
            parse_mode="Markdown"
        )
        return A_CODE

    msg = await update.message.reply_text("⏳ جاري التحقق من الكود واستخراج بيانات API...")


    if creator.auth_login(code):
        await msg.edit_text("✅ تم تسجيل الدخول إلى my.telegram.org بنجاح!\n\n🔍 جاري البحث عن التطبيقات المسجلة...", parse_mode="Markdown")


        api_data = creator.get_app_data()

        if not api_data:
            await msg.edit_text("📝 لم يتم العثور على تطبيقات، جاري إنشاء تطبيق جديد تلقائياً...")

            random_suffix = ''.join(random.choices(string.ascii_lowercase, k=6))
            creator.app_title = f"AutoApp_{random_suffix}"
            creator.app_shortname = f"autoapp_{random_suffix}"
            creator.app_url = f"https://{random_suffix}.com"
            creator.app_platform = "desktop"
            creator.app_desc = f"Auto created app for {phone}"

            api_data = creator.create_new_app()

        if api_data:
            api_id, api_hash = api_data

            await msg.edit_text(
                f"✅ تم استخراج بيانات API بنجاح!\n\n"
                f"🆔 API ID: `{api_id}`\n"
                f"🔑 API Hash: `{api_hash}`\n\n"
                f"⏳ جاري إنشاء جلسة Telethon وإضافة الحساب...\n"
                f"📌 ملاحظة: قد تحتاج إلى إدخال رمز آخر من تطبيق تيليجرام.",
                parse_mode="Markdown"
            )


            device = random.choice(DEVICES)
            client = TelegramClient(
                f"{SESSIONS_DIR}/{phone}",
                int(api_id),
                api_hash,
                device_model=device["model"],
                system_version=device["sys"],
                app_version="4.8.4",
                lang_code="ar",
                system_lang_code="ar-SA"
            )

            try:
                await client.connect()


                if not await client.is_user_authorized():

                    await msg.edit_text(
                        "⚠️ هذا رمز مختلف عن الرمز الأول!\n"
                        "سيصلك رمز جديد من تطبيق تيليجرام (5 أرقام).\n\n"
                        "الرجاء إدخال هذا الرمز:",
                        parse_mode="Markdown"
                    )


                    context.user_data['temp_client'] = client
                    context.user_data['temp_api_id'] = api_id
                    context.user_data['temp_api_hash'] = api_hash
                    context.user_data['temp_phone'] = phone


                    try:
                        await client.send_code_request(phone)
                        return TELETHON_CODE
                    except Exception as e:
                        await msg.edit_text(f"❌ خطأ في إرسال رمز تيليجرام: {e}")
                        await client.disconnect()
                        return ConversationHandler.END
                else:

                    await finalize_account_addition(update, context, client, phone, api_id, api_hash, msg)
                    return ConversationHandler.END

            except Exception as e:
                await msg.edit_text(f"❌ خطأ في إنشاء الجلسة: {e}")
                try:
                    await client.disconnect()
                except:
                    pass
                return ConversationHandler.END
        else:
            await msg.edit_text("❌ فشل في استخراج أو إنشاء بيانات API!", parse_mode="Markdown")
            return ConversationHandler.END
    else:
        await msg.edit_text(
            "❌ فشل في تسجيل الدخول إلى my.telegram.org!\n\n"
            "الرجاء التأكد من صحة رمز التحقق.\n"
            "⚠️ رمز التحقق يكون أرقام فقط (مثال: 12345)",
            parse_mode="Markdown"
        )
        return A_CODE


TELETHON_CODE = 33

async def telethon_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة رمز Telethon (رمز تطبيق تيليجرام - 5 أرقام)"""
    code = update.message.text.strip()
    client = context.user_data.get('temp_client')
    phone = context.user_data.get('temp_phone')
    api_id = context.user_data.get('temp_api_id')
    api_hash = context.user_data.get('temp_api_hash')

    if not client:
        await update.message.reply_text("❌ حدث خطأ، يرجى إرسال /start للبدء من جديد.")
        return ConversationHandler.END

    msg = await update.message.reply_text("⏳ جاري تسجيل الدخول إلى تيليجرام...")

    try:
        await client.sign_in(phone, code)
        await finalize_account_addition(update, context, client, phone, api_id, api_hash, msg)
        return ConversationHandler.END

    except errors.SessionPasswordNeededError:
        await msg.edit_text("🔐 الحساب محمي بكلمة سر من خطوتين\n\nيرجى إرسال كلمة السر:")
        context.user_data['auto_client'] = client
        context.user_data['auto_api_id'] = api_id
        context.user_data['auto_api_hash'] = api_hash
        context.user_data['auto_phone'] = phone
        return A_PASSWORD

    except Exception as e:
        await msg.edit_text(f"❌ خطأ في تسجيل الدخول: {e}", parse_mode="Markdown")
        try:
            await client.disconnect()
        except:
            pass
        return ConversationHandler.END

async def finalize_account_addition(update, context, client, phone, api_id, api_hash, msg):
    """إكمال إضافة الحساب بعد تسجيل الدخول بنجاح"""

    channel1 = get_admin_file_content(ADMIN_FILES["channel1"])
    channel2 = get_admin_file_content(ADMIN_FILES["channel2"])

    if channel1 or channel2:
        await msg.edit_text("⏳ جاري تسجيل الحساب في قنوات الإشتراك الإجباري...")
        await add_account_to_channels(client, channel1, channel2)


    owner_id = str(update.effective_user.id)
    db.add_account(phone, int(api_id), api_hash, phone, owner_id)

    await msg.edit_text(
        f"✅ تم إضافة الحساب بنجاح!\n\n"
        f"📱 رقم الهاتف: `{phone}`\n"
        f"🆔 API ID: `{api_id}`\n"
        f"🔑 API Hash: `{api_hash}`\n\n"
        f"⚠️ احتفظ بهذه البيانات في مكان آمن.",
        parse_mode="Markdown"
    )

    await client.disconnect()


    for key in ['auto_api_creator', 'auto_phone', 'temp_client', 'temp_api_id', 'temp_api_hash', 'auto_client', 'auto_api_id', 'auto_api_hash']:
        if key in context.user_data:
            del context.user_data[key]

async def a_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة كلمة السر للحسابات المحمية"""
    password = update.message.text.strip()
    client = context.user_data.get('auto_client')
    phone = context.user_data.get('auto_phone')
    api_id = context.user_data.get('auto_api_id')
    api_hash = context.user_data.get('auto_api_hash')

    if not client:
        await update.message.reply_text("❌ حدث خطأ، يرجى إرسال /start للبدء من جديد.")
        return ConversationHandler.END

    msg = await update.message.reply_text("⏳ جاري تسجيل الدخول بكلمة السر...")

    try:
        await client.sign_in(password=password)


        channel1 = get_admin_file_content(ADMIN_FILES["channel1"])
        channel2 = get_admin_file_content(ADMIN_FILES["channel2"])

        if channel1 or channel2:
            await msg.edit_text("⏳ جاري تسجيل الحساب في قنوات الإشتراك الإجباري...")
            await add_account_to_channels(client, channel1, channel2)


        owner_id = str(update.effective_user.id)
        db.add_account(phone, int(api_id), api_hash, phone, owner_id)


        try:
            await clear_contacts_for_account(client)
        except:
            pass

        await msg.edit_text(
            f"✅ تم إضافة الحساب بنجاح!\n\n"
            f"📱 رقم الهاتف: `{phone}`\n"
            f"🆔 API ID: `{api_id}`\n"
            f"🔑 API Hash: `{api_hash}`\n\n"
            f"⚠️ تنبيه: احتفظ بهذه البيانات في مكان آمن.",
            parse_mode="Markdown"
        )

        await client.disconnect()


        keys_to_remove = ['auto_client', 'auto_api_creator', 'auto_phone', 'auto_api_id', 'auto_api_hash']
        for key in keys_to_remove:
            if key in context.user_data:
                del context.user_data[key]

        return ConversationHandler.END

    except Exception as e:
        error_msg = str(e)
        if "FLOOD_WAIT" in error_msg:
            await msg.edit_text(
                f"❌ تم حظر الحساب مؤقتاً!\n\n"
                f"{error_msg}\n\n"
                f"يرجى المحاولة بعد ساعة.",
                parse_mode="Markdown"
            )
        else:
            await msg.edit_text(
                f"❌ خطأ في كلمة السر:\n\n"
                f"`{error_msg}`\n\n"
                f"يرجى التأكد من صحة كلمة السر والمحاولة مرة أخرى.",
                parse_mode="Markdown"
            )
        return A_PASSWORD

async def import_session_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """📥 استيراد جلسات - شرح الخدمة"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "📥 استيراد جلسات Telethon\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "📌 شرح خدمه الزر:\n"
        "• تقوم برفع ملفات الجلسات (.session)\n"
        "• البوت يستخرج بيانات الحساب من الملف\n"
        "• يضيف الحساب إلى قاعدة البيانات\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "📁 طريقة الاستخدام:\n"
        "1️⃣ أرسل ملفات `.session` دفعة واحدة أو فردياً\n"
        "2️⃣ يمكنك كتابة `API_ID|API_HASH` في وصف الملف\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "📝 مثال وصف الملف:\n"
        "`2040|b18441a1ff607e10a989891a5462e627`\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "⚠️ ملاحظات:\n"
        "• إذا لم تكتب API سيتم استخدام القيم الافتراضية\n"
        "• قد لا تعمل القيم الافتراضية مع جميع الحسابات\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "📤 الخطوة التالية:\n"
        "• أرسل ملف/ملفات الجلسات",
        parse_mode="Markdown"
    )
    return IMPORT_SESSION_FILE


async def import_session_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """📥 استقبال ملفات الجلسات"""
    if not update.message.document:
        await update.message.reply_text(
            "❌ خطأ: لم يتم إرسال ملف!\n"
            "📤 يرجى إرسال ملف `.session` صحيح.",
            parse_mode="Markdown"
        )
        return IMPORT_SESSION_FILE
    
    doc = update.message.document
    file_name = doc.file_name
    
    if not file_name.endswith('.session'):
        await update.message.reply_text(
            f"❌ صيغة غير مدعومة!\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"📁 الملف: `{file_name}`\n"
            f"⚠️ يجب أن يكون الملف بصيغة `.session`\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"💡 تأكد من أن الملف هو ملف جلسة Telethon صحيح.",
            parse_mode="Markdown"
        )
        return IMPORT_SESSION_FILE
    
    phone = file_name.replace('.session', '').strip()
    
    default_api_id = 2040
    default_api_hash = "b18441a1ff607e10a989891a5462e627"
    
    caption = update.message.caption or ""
    api_id = default_api_id
    api_hash = default_api_hash
    
    if '|' in caption:
        try:
            parts = caption.strip().split('|')
            api_id = int(parts[0].strip())
            api_hash = parts[1].strip()
        except:
            await update.message.reply_text(
                "⚠️ تنبيه: صيغة API غير صحيحة!\n"
                f"سيتم استخدام القيم الافتراضية:\n"
                f"🆔 API ID: `{default_api_id}`\n"
                f"🔑 API Hash: `{default_api_hash}`",
                parse_mode="Markdown"
            )
    
    status_msg = await update.message.reply_text(
        f"⏳ جاري معالجة الملف...\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📁 الملف: `{file_name}`\n"
        f"📱 رقم الهاتف: `{phone}`\n"
        f"🆔 API ID: `{api_id}`\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"⏳ جاري تحميل الملف...",
        parse_mode="Markdown"
    )
    
    try:
        file = await context.bot.get_file(doc.file_id)
        await file.download_to_drive(f"{SESSIONS_DIR}/{phone}.session")
        
        await status_msg.edit_text(
            f"⏳ جاري التحقق من الجلسة...\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"📱 رقم: `{phone}`\n"
            f"🔌 جاري الاتصال بخوادم تيليجرام...",
            parse_mode="Markdown"
        )
        
        device = random.choice(DEVICES)
        client = TelegramClient(f"{SESSIONS_DIR}/{phone}", api_id, api_hash, device_model=device["model"], system_version=device["sys"])
        await client.connect()
        
        if await client.is_user_authorized():
            # تسجيل الحساب في قنوات الإشتراك الإجباري
            channel1 = get_admin_file_content(ADMIN_FILES["channel1"])
            channel2 = get_admin_file_content(ADMIN_FILES["channel2"])
            
            if channel1 or channel2:
                await status_msg.edit_text(
                    f"⏳ جاري تسجيل الحساب في القنوات الإجبارية...\n"
                    f"━━━━━━━━━━━━━━━━━━━━━\n"
                    f"📱 رقم: `{phone}`\n"
                    f"📢 جاري الانضمام للقنوات...",
                    parse_mode="Markdown"
                )
                await add_account_to_channels(client, channel1, channel2)
            
            owner_id = str(update.effective_user.id)
            db.add_account(phone, api_id, api_hash, phone, owner_id)
            
            await status_msg.edit_text(
                f"✅ تم استيراد الحساب بنجاح!\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"📱 رقم الهاتف: `{phone}`\n"
                f"🆔 API ID: `{api_id}`\n"
                f"🔑 API Hash: `{api_hash}`\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"💾 تم حفظ الحساب في قاعدة البيانات\n"
                f"🔐 الجلسة صالحة وتم التحقق منها",
                parse_mode="Markdown"
            )
        else:
            await status_msg.edit_text(
                f"❌ الجلسة غير صالحة!\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"📱 رقم: `{phone}`\n"
                f"⚠️ الجلسة منتهية أو غير صالحة\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"💡 الحلول:\n"
                f"• قم بتصدير جلسة جديدة من الحساب\n"
                f"• تأكد من صحة API ID و API Hash\n"
                f"• حاول إنشاء جلسة جديدة من البوت",
                parse_mode="Markdown"
            )
            if os.path.exists(f"{SESSIONS_DIR}/{phone}.session"):
                os.remove(f"{SESSIONS_DIR}/{phone}.session")
        await client.disconnect()
        
    except Exception as e:
        await status_msg.edit_text(
            f"❌ خطأ في استيراد الجلسة!\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"📁 الملف: `{file_name}`\n"
            f"❌ الخطأ: `{str(e)[:200]}`\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"💡 تأكد من:\n"
            f"• صحة ملف الجلسة\n"
            f"• صحة API ID و API Hash\n"
            f"• اتصال الإنترنت",
            parse_mode="Markdown"
        )
    
    return IMPORT_SESSION_FILE


async def del_acc_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """🗑️ حذف حساب - عرض قائمة الحسابات"""
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    accounts = db.get_user_accounts(user_id)
    
    if not accounts:
        await query.edit_message_text(
            "📭 لا توجد حسابات مسجلة!\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "💡 يمكنك إضافة حسابات جديدة باستخدام:\n"
            "• '➕ إضافة حساب جديد'\n"
            "• '📥 استيراد جلسات'\n"
            "━━━━━━━━━━━━━━━━━━━━━",
            parse_mode="Markdown"
        )
        return
    
    keyboard = []
    for acc in accounts:
        keyboard.append([InlineKeyboardButton(f"📱 {acc[0]}", callback_data=f"view_del_{acc[0]}")])
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data='main_menu')])
    
    await query.edit_message_text(
        f"🗑️ حذف حساب\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📱 عدد حساباتك: `{len(accounts)}`\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📌 اختر الحساب المراد حذفه:\n"
        f"⚠️ تحذير: لا يمكن استرداد الحساب بعد الحذف",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )


async def view_del_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """⚠️ تأكيد حذف حساب"""
    query = update.callback_query
    phone = query.data.replace("view_del_", "")
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("❌ نعم، احذف الحساب", callback_data=f"confirm_del_{phone}")],
        [InlineKeyboardButton("🔙 إلغاء", callback_data='del_acc')]
    ]
    
    await query.edit_message_text(
        f"⚠️ تأكيد حذف الحساب\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📱 الحساب: `{phone}`\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"❓ هل أنت متأكد من حذف هذا الحساب؟\n"
        f"⚠️ تحذير: هذا الإجراء لا يمكن التراجع عنه!\n"
        f"• سيتم حذف الحساب من قاعدة البيانات\n"
        f"• سيتم حذف ملف الجلسة نهائياً\n"
        f"━━━━━━━━━━━━━━━━━━━━━",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )


async def confirm_del_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """🗑️ تنفيذ حذف الحساب"""
    query = update.callback_query
    phone = query.data.replace("confirm_del_", "")
    
    # حذف من قاعدة البيانات
    db.remove_account(phone)
    
    # حذف ملف الجلسة
    session_file = f"{SESSIONS_DIR}/{phone}.session"
    if os.path.exists(session_file):
        os.remove(session_file)
    
    await query.answer(f"✅ تم حذف {phone}")
    await query.edit_message_text(
        f"✅ تم حذف الحساب بنجاح!\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📱 الحساب: `{phone}`\n"
        f"🗑️ تم حذف:\n"
        f"• البيانات من قاعدة البيانات\n"
        f"• ملف الجلسة من الخادم\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔄 جاري العودة للقائمة الرئيسية...",
        parse_mode="Markdown"
    )
    await asyncio.sleep(2)
    await start(update, context)


async def list_accs_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """📋 عرض قائمة الحسابات"""
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    accounts = db.get_user_accounts(user_id)
    
    if not accounts:
        await query.edit_message_text(
            "📭 لا توجد حسابات مسجلة!\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "💡 يمكنك إضافة حسابات جديدة باستخدام:\n"
            "• '➕ إضافة حساب جديد'\n"
            "• '📥 استيراد جلسات'",
            parse_mode="Markdown"
        )
        return
    
    # ترقيم الحسابات
    acc_list = "\n".join([f"{i+1} 📱 `{acc[0]}`" for i, acc in enumerate(accounts)])
    
    text = (
        f"📋 قائمة حساباتك المسجلة\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 إجمالي الحسابات: `{len(accounts)}`\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"{acc_list}\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"💡 نصائح:\n"
        f"• يمكنك استخدام هذه الحسابات في عمليات النقل\n"
        f"• لحذف حساب استخدم زر '🗑️ حذف حساب'"
    )
    
    keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data='main_menu')]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")


async def join_group_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """➕ انضمام لمجموعة/قناة - شرح الخدمة"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    accounts = db.get_user_accounts(user_id)
    
    if not accounts:
        # إنشاء زر إضافة حساب
        keyboard = [
            [InlineKeyboardButton("➕ إضافة حساب جديد", callback_data='add_acc')],
            [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data='main_menu')]
        ]
        await query.edit_message_text(
            "📭 ملكش حسابات!\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "⚠️ لا يمكنك استخدام خدمة دخول المجموعة\n"
            "لأنه ليس لديك أي حسابات مسجلة.\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "➕ اضغط على الزر أدناه لإضافة حساب:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        return
    
    await query.edit_message_text(
        "➕ انضمام لمجموعة أو قناة\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "📌 شرح خدمه الزر:\n"
        "• ستقوم بإدخال عدد الحسابات المراد استخدامها\n"
        "• ثم إرسال رابط المجموعة أو القناة\n"
        "• البوت سيقوم بانضمام الحسابات المحددة\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"📱 حساباتك المتاحة: `{len(accounts)}`\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "🔢 الخطوة التالية:\n"
        "• أرسل عدد الحسابات المراد إدخالها (رقم)",
        parse_mode="Markdown"
    )
    return JOIN_COUNT


async def join_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """🔢 استقبال عدد الحسابات"""
    try:
        count = int(update.message.text)
        user_id = str(update.effective_user.id)
        accounts = db.get_user_accounts(user_id)
        
        if count > len(accounts):
            await update.message.reply_text(
                f"❌ عدد غير متاح!\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"📱 الحسابات المتاحة: `{len(accounts)}`\n"
                f"📊 العدد المطلوب: `{count}`\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"💡 يرجى إدخال رقم أقل أو يساوي `{len(accounts)}`",
                parse_mode="Markdown"
            )
            return JOIN_COUNT
        
        if count <= 0:
            await update.message.reply_text(
                "❌ عدد غير صحيح!\n"
                "━━━━━━━━━━━━━━━━━━━━━\n"
                "💡 يرجى إدخال رقم أكبر من 0",
                parse_mode="Markdown"
            )
            return JOIN_COUNT
        
        context.user_data['join_count'] = count
        await update.message.reply_text(
            f"✅ تم تحديد العدد: `{count}` حساب\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"🔗 الخطوة التالية:\n"
            f"• أرسل رابط المجموعة أو القناة\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"📝 مثال:\n"
            f"`https://t.me/username`\n"
            f"أو\n"
            f"`@username`\n"
            f"أو رابط دعوة: `t.me/joinchat/xxxxx`",
            parse_mode="Markdown"
        )
        return JOIN_LINK
    except ValueError:
        await update.message.reply_text(
            "❌ خطأ في الإدخال!\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "💡 يرجى إرسال رقم صحيح (مثال: `5`)",
            parse_mode="Markdown"
        )
        return JOIN_COUNT


async def join_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """🔗 استقبال الرابط وتنفيذ الانضمام"""
    link = update.message.text.strip()
    count = context.user_data.get('join_count', 0)
    user_id = str(update.effective_user.id)
    all_user_accounts = db.get_user_accounts(user_id)
    accounts = all_user_accounts[:count]
    
    msg = await update.message.reply_text(
        f"⏳ جاري تنفيذ الانضمام...\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📱 عدد الحسابات: `{len(accounts)}`\n"
        f"🔗 الرابط: `{link}`\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"⏳ جاري انضمام الحسابات...",
        parse_mode="Markdown"
    )
    
    success, failed = 0, 0
    results = []
    
    for i, acc in enumerate(accounts):
        client = await get_client(acc)
        try:
            if 'joinchat' in link or '+' in link:
                hash_link = link.split('/')[-1].replace('+', '')
                await client(functions.messages.ImportChatInviteRequest(hash_link))
            else:
                await client(JoinChannelRequest(link))
            success += 1
            results.append(f"✅ `{acc[0][-8:]}`: انضم بنجاح")
            await msg.edit_text(
                f"⏳ جاري الانضمام...\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"📊 التقدم: `{i+1}/{len(accounts)}`\n"
                f"✅ نجح: `{success}` | ❌ فشل: `{failed}`\n"
                f"━━━━━━━━━━━━━━━━━━━━━",
                parse_mode="Markdown"
            )
        except Exception as e:
            failed += 1
            results.append(f"❌ `{acc[0][-8:]}`: {str(e)[:50]}")
        finally:
            await client.disconnect()
        await asyncio.sleep(1)
    
    result_text = (
        f"✅ نتائج الانضمام\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔗 الرابط: `{link}`\n"
        f"✅ نجح: `{success}` حساب\n"
        f"❌ فشل: `{failed}` حساب\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        + "\n".join(results[:10])
    )
    
    if len(results) > 10:
        result_text += f"\n... و {len(results)-10} حسابات أخرى"
    
    await msg.edit_text(result_text, parse_mode="Markdown")
    return ConversationHandler.END


async def leave_group_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """➖ مغادرة مجموعة/قناة - شرح الخدمة"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    accounts = db.get_user_accounts(user_id)
    
    if not accounts:
        keyboard = [
            [InlineKeyboardButton("➕ إضافة حساب جديد", callback_data='add_acc')],
            [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data='main_menu')]
        ]
        await query.edit_message_text(
            "📭 ملكش حسابات!\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "⚠️ لا يمكنك استخدام خدمة مغادرة المجموعة\n"
            "لأنه ليس لديك أي حسابات مسجلة.\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "➕ اضغط على الزر أدناه لإضافة حساب:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        return
    
    await query.edit_message_text(
        "➖ مغادرة مجموعة أو قناة\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "📌 شرح خدمه الزر:\n"
        "• ستقوم بإرسال رابط المجموعة أو القناة\n"
        "• البوت سيغادرها بجميع حساباتك\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"📱 عدد حساباتك: `{len(accounts)}`\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "🔗 الخطوة التالية:\n"
        "• أرسل رابط المجموعة أو القناة المراد مغادرتها\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "⚠️ تنبيه:\n"
        "• سيتم مغادرة جميع حساباتك من هذه المجموعة\n"
        "• لا يمكن التراجع عن هذا الإجراء",
        parse_mode="Markdown"
    )
    return LEAVE_LINK


async def leave_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """🔗 استقبال الرابط وتنفيذ المغادرة"""
    link = update.message.text.strip()
    user_id = str(update.effective_user.id)
    accounts = db.get_user_accounts(user_id)
    
    msg = await update.message.reply_text(
        f"⏳ جاري تنفيذ المغادرة...\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📱 عدد الحسابات: `{len(accounts)}`\n"
        f"🔗 الرابط: `{link}`\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"⏳ جاري مغادرة الحسابات...",
        parse_mode="Markdown"
    )
    
    success_count = 0
    results = []
    
    for i, acc in enumerate(accounts):
        client = await get_client(acc)
        try:
            await client(LeaveChannelRequest(link))
            success_count += 1
            results.append(f"✅ `{acc[0][-8:]}`: غادر بنجاح")
            await msg.edit_text(
                f"⏳ جاري المغادرة...\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"📊 التقدم: `{i+1}/{len(accounts)}`\n"
                f"✅ غادر: `{success_count}` حساب\n"
                f"━━━━━━━━━━━━━━━━━━━━━",
                parse_mode="Markdown"
            )
        except Exception as e:
            results.append(f"❌ `{acc[0][-8:]}`: {str(e)[:50]}")
        finally:
            await client.disconnect()
    
    result_text = (
        f"✅ نتائج المغادرة\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔗 الرابط: `{link}`\n"
        f"✅ غادر: `{success_count}` حساب\n"
        f"❌ فشل: `{len(accounts)-success_count}` حساب\n"
        f"━━━━━━━━━━━━━━━━━━━━━"
    )
    
    await msg.edit_text(result_text, parse_mode="Markdown")
    return ConversationHandler.END


EXTRACT_API_PHONE, EXTRACT_API_CODE, EXTRACT_API_APP_DETAILS = range(20, 23)

async def extract_api_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بدء عملية استخراج API - باستخدام الكود الشغال"""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id


    if 'extract_api_data' not in context.user_data:
        context.user_data['extract_api_data'] = {}

    context.user_data['extract_api_data'][user_id] = {
        "state": "phone",
        "creator": None
    }

    await query.edit_message_text(
        "🤖 مرحباً بك في أداة استخراج API!\n\n"
        "سأساعدك في إنشاء `api_id` و `api_hash` لحسابك في تيليجرام.\n\n"
        "📱 الرجاء إرسال رقم هاتفك بالصيغة الدولية:\n"
        "مثال: `+201234567890`\n\n"
        "⚠️ ملاحظة: هذا البوت لا يخزن أي بيانات شخصية.",
        parse_mode="Markdown"
    )
    return EXTRACT_API_PHONE

async def extract_api_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة رقم الهاتف"""
    user_id = update.effective_user.id
    phone_number = update.message.text.strip()


    if 'extract_api_data' not in context.user_data:
        context.user_data['extract_api_data'] = {}

    if user_id not in context.user_data['extract_api_data']:
        context.user_data['extract_api_data'][user_id] = {}

    if not phone_number.startswith('+') or not phone_number[1:].replace(' ', '').isdigit():
        await update.message.reply_text(
            "❌ صيغة غير صحيحة!\n\n"
            "يرجى إرسال رقم الهاتف بالصيغة الدولية:\n"
            "مثال: `+201234567890`",
            parse_mode="Markdown"
        )
        return EXTRACT_API_PHONE


    creator = TelegramAPICreator(user_id)
    creator.phone_number = phone_number

    context.user_data['extract_api_data'][user_id]['creator'] = creator
    context.user_data['extract_api_data'][user_id]['phone'] = phone_number

    msg = await update.message.reply_text("⏳ جاري إرسال رمز التحقق إلى هاتفك...")

    if creator.send_password():
        await msg.edit_text(
            "✅ تم إرسال رمز التحقق!\n\n"
            "📲 يرجى إدخال الرمز الذي تلقيته :",
            parse_mode="Markdown"
        )
        return EXTRACT_API_CODE
    else:
        await msg.edit_text(
            "❌ فشل في إرسال رمز التحقق!\n\n"
            "الرجاء التأكد من صحة رقم الهاتف والمحاولة مرة أخرى.\n"
            "أو أرسل /start للبدء من جديد.",
            parse_mode="Markdown"
        )
        return ConversationHandler.END

async def extract_api_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة رمز التحقق"""
    user_id = update.effective_user.id
    code = update.message.text.strip()

    if user_id not in context.user_data.get('extract_api_data', {}):
        await update.message.reply_text("❌ يرجى إرسال /start للبدء من جديد.")
        return ConversationHandler.END

    creator = context.user_data['extract_api_data'][user_id].get('creator')
    if not creator:
        await update.message.reply_text("❌ حدث خطأ، يرجى البدء من جديد.")
        return ConversationHandler.END

    msg = await update.message.reply_text("⏳ جاري تسجيل الدخول...")

    if creator.auth_login(code):
        await msg.edit_text("✅ تم تسجيل الدخول بنجاح!\n\n🔍 جاري البحث عن التطبيقات المسجلة...", parse_mode="Markdown")

        existing_app = creator.get_app_data()

        if existing_app:
            api_id, api_hash = existing_app
            await send_extracted_credentials(update, api_id, api_hash, creator)

            del context.user_data['extract_api_data'][user_id]
            return ConversationHandler.END
        else:

            keyboard = [
                [InlineKeyboardButton("✅ استخدام القيم الافتراضية", callback_data="extract_default")],
                [InlineKeyboardButton("✏️ إدخال بيانات مخصصة", callback_data="extract_custom")],
                [InlineKeyboardButton("🔄 إنشاء تلقائي", callback_data="extract_auto")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await msg.edit_text(
                "📝 لم يتم العثور على تطبيقات مسجلة!\n\n"
                "كيف تريد إنشاء التطبيق؟\n\n"
                "🔹 القيم الافتراضية:\n"
                "• اسم التطبيق: MyApp\n"
                "• الاسم المختصر: myapp\n"
                "• الرابط: https://myapp.com\n"
                "• المنصة: desktop\n"
                "• الوصف: My Telegram App\n\n"
                "🔹 مخصص: أدخل بياناتك الخاصة\n\n"
                "🔹 تلقائي: سيحاول البوت إنشاء تطبيق بقيم مناسبة",
                parse_mode="Markdown",
                reply_markup=reply_markup
            )
            return EXTRACT_API_APP_DETAILS
    else:
        await msg.edit_text(
            "❌ فشل في تسجيل الدخول!\n\n"
            "الرجاء التأكد من صحة رمز التحقق والمحاولة مرة أخرى.\n"
            "أو أرسل /start للبدء من جديد.",
            parse_mode="Markdown"
        )
        return EXTRACT_API_CODE

async def send_extracted_credentials(update: Update, api_id: str, api_hash: str, creator):
    """إرسال بيانات الاعتماد للمستخدم"""
    message = (
        "🎉 تم استخراج/إنشاء التطبيق بنجاح! 🎉\n\n"
        "📊 بيانات API الخاصة بك:\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"🆔 API ID: `{api_id}`\n"
        f"🔑 API Hash: `{api_hash}`\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        "📱 تفاصيل التطبيق:\n"
        f"• الاسم: `{creator.app_title if creator.app_title else 'غير محدد'}`\n"
        f"• الاسم المختصر: `{creator.app_shortname if creator.app_shortname else 'غير محدد'}`\n"
        f"• الرابط: `{creator.app_url if creator.app_url else 'غير محدد'}`\n"
        f"• المنصة: `{creator.app_platform if creator.app_platform else 'غير محدد'}`\n\n"
        "⚠️ تنبيهات مهمة:\n"
        "• 🔒 احفظ هذه البيانات في مكان آمن\n"
        "• 🚫 لا تشارك `api_hash` مع أي شخص\n"
        "• ✅ يمكنك استخدامها في تطبيقات تيليجرام API\n"
        "• 📝 يمكنك إدارة تطبيقاتك من: https://my.telegram.org/apps\n\n"
        "➕ هل تريد إضافة هذا الحساب؟\n"
        "استخدم الأمر /start ثم اختر 'إضافة حساب جديد'"
    )

    await update.message.reply_text(message, parse_mode="Markdown")

async def extract_app_options_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة اختيارات إنشاء التطبيق"""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id

    if user_id not in context.user_data.get('extract_api_data', {}):
        await query.edit_message_text("❌ يرجى إرسال /start للبدء من جديد.")
        return ConversationHandler.END

    creator = context.user_data['extract_api_data'][user_id].get('creator')
    if not creator:
        await query.edit_message_text("❌ حدث خطأ، يرجى البدء من جديد.")
        return ConversationHandler.END

    if query.data == "extract_default":
        creator.app_title = "MyApp"
        creator.app_shortname = "myapp"
        creator.app_url = "https://myapp.com"
        creator.app_platform = "desktop"
        creator.app_desc = "My Telegram Application"

        await query.edit_message_text("⏳ جاري إنشاء التطبيق الجديد... (قد يستغرق 10-15 ثانية)")

        result = creator.create_new_app()
        if result:
            api_id, api_hash = result
            await send_extracted_credentials_from_query(query, api_id, api_hash, creator)
            del context.user_data['extract_api_data'][user_id]
        else:
            await query.edit_message_text(
                "❌ فشل في إنشاء التطبيق!\n\n"
                "الأسباب المحتملة:\n"
                "1️⃣ تم إنشاء العدد الأقصى من التطبيقات (الحد 10 تطبيقات)\n"
                "2️⃣ مشكلة في الاتصال بخوادم تيليجرام\n\n"
                "💡 الحلول:\n"
                "• احذف بعض التطبيقات القديمة من https://my.telegram.org/apps\n"
                "• أو أرسل /start للمحاولة مرة أخرى",
                parse_mode="Markdown"
            )

        return ConversationHandler.END

    elif query.data == "extract_auto":

        import random
        import string

        random_suffix = ''.join(random.choices(string.ascii_lowercase, k=6))
        creator.app_title = f"App_{random_suffix}"
        creator.app_shortname = f"app_{random_suffix}"
        creator.app_url = f"https://{random_suffix}.com"
        creator.app_platform = "desktop"
        creator.app_desc = f"Auto created app {random_suffix}"

        await query.edit_message_text("⏳ جاري الإنشاء التلقائي للتطبيق... (قد يستغرق 10-15 ثانية)")

        result = creator.create_new_app()
        if result:
            api_id, api_hash = result
            await send_extracted_credentials_from_query(query, api_id, api_hash, creator)
            del context.user_data['extract_api_data'][user_id]
        else:
            await query.edit_message_text(
                "❌ فشل الإنشاء التلقائي!\n\n"
                "يرجى المحاولة باستخدام البيانات المخصصة",
                parse_mode="Markdown"
            )

        return ConversationHandler.END

    elif query.data == "extract_custom":
        await query.edit_message_text(
            "📝 يرجى إرسال بيانات التطبيق بالصيغة التالية:\n\n"
            "`اسم التطبيق | الاسم المختصر | الرابط | المنصة | الوصف`\n\n"
            "مثال:\n"
            "`MoraApp | mora | https://mora.com | android | تطبيق تجريبي`\n\n"
            "📌 ملاحظات:\n"
            "• المنصات المدعومة: desktop, android, ios, web\n"
            "• يمكنك ترك أي حقل فارغاً",
            parse_mode="Markdown"
        )
        return EXTRACT_API_APP_DETAILS

async def send_extracted_credentials_from_query(query, api_id: str, api_hash: str, creator):
    """إرسال بيانات الاعتماد من خلال callback query"""
    message = (
        "📊 بيانات API الخاصة بك:\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"🆔 API ID: `{api_id}`\n"
        f"🔑 API Hash: `{api_hash}`\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        "📱 تفاصيل التطبيق:\n"
        f"• الاسم: `{creator.app_title}`\n"
        f"• الاسم المختصر: `{creator.app_shortname}`\n"
        f"• الرابط: `{creator.app_url}`\n"
        f"• المنصة: `{creator.app_platform}`\n\n"
        "⚠️ تنبيهات مهمة:\n"
        "• 🔒 احفظ هذه البيانات في مكان آمن\n"
        "• 🚫 لا تشارك `api_hash` مع أي شخص\n\n"
    )


    await query.message.reply_text(message, parse_mode="Markdown")


    try:
        await query.message.delete()
    except:
        pass

async def extract_api_app_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة البيانات المخصصة للتطبيق (من الكود الثاني الشغال)"""
    user_id = update.effective_user.id
    text = update.message.text.strip()

    if user_id not in context.user_data.get('extract_api_data', {}):
        await update.message.reply_text("❌ يرجى إرسال /start للبدء من جديد.")
        return ConversationHandler.END

    creator = context.user_data['extract_api_data'][user_id].get('creator')
    if not creator:
        await update.message.reply_text("❌ حدث خطأ، يرجى البدء من جديد.")
        return ConversationHandler.END

    parts = text.split('|')


    creator.app_title = parts[0].strip() if len(parts) > 0 and parts[0].strip() else f"App_{user_id}"
    creator.app_shortname = parts[1].strip() if len(parts) > 1 and parts[1].strip() else creator.app_title.lower().replace(' ', '')
    creator.app_url = parts[2].strip() if len(parts) > 2 and parts[2].strip() else f"https://{creator.app_shortname}.com"
    creator.app_platform = parts[3].strip() if len(parts) > 3 and parts[3].strip() else "desktop"
    creator.app_desc = parts[4].strip() if len(parts) > 4 and parts[4].strip() else f"Application {creator.app_title}"

    await update.message.reply_text(
        f"⏳ جاري إنشاء التطبيق...\n\n"
        f"📱 البيانات المستخدمة:\n"
        f"• الاسم: {creator.app_title}\n"
        f"• المنصة: {creator.app_platform}\n\n"
        f"قد يستغرق هذا 10-15 ثانية..."
    )

    result = creator.create_new_app()
    if result:
        api_id, api_hash = result
        await send_extracted_credentials(update, api_id, api_hash, creator)
        del context.user_data['extract_api_data'][user_id]
    else:
        await update.message.reply_text(
            "❌ فشل في إنشاء التطبيق!\n\n"
            "💡 حلول مقترحة:\n"
            "1️⃣ تحقق من عدد التطبيقات المسجلة (الحد الأقصى 10)\n"
            "2️⃣ اذهب إلى https://my.telegram.org/apps واحذف بعض التطبيقات القديمة\n"
            "3️⃣ جرب استخدام اسم تطبيق مختلف\n\n"
            "🔄 أرسل /start للمحاولة مرة أخرى",
            parse_mode="Markdown"
        )

    return ConversationHandler.END

async def copy_api_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نسخ API ID أو API Hash"""
    query = update.callback_query
    data = query.data

    if data.startswith("copy_api_id_"):
        api_id = data.replace("copy_api_id_", "")
        await query.answer(f"✅ تم نسخ API ID: {api_id}", show_alert=True)
    elif data.startswith("copy_api_hash_"):
        api_hash = data.replace("copy_api_hash_", "")
        await query.answer(f"✅ تم نسخ API HASH: {api_hash}", show_alert=True)

    await query.answer()

async def auto_add_account_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إضافة الحساب تلقائياً باستخدام البيانات المستخرجة"""
    query = update.callback_query
    data = query.data


    parts = data.replace("auto_add_account_", "").split("|")
    if len(parts) >= 3:
        phone = parts[0]
        api_id = int(parts[1])
        api_hash = parts[2]

        owner_id = str(query.from_user.id)


        existing_accounts = db.get_user_accounts(owner_id)
        for acc in existing_accounts:
            if acc[0] == phone:
                await query.answer("⚠️ هذا الحساب مضاف مسبقاً!", show_alert=True)
                return


        db.add_account(phone, api_id, api_hash, phone, owner_id)


        device = random.choice(DEVICES)
        client = TelegramClient(
            f"{SESSIONS_DIR}/{phone}",
            api_id,
            api_hash,
            device_model=device["model"],
            system_version=device["sys"]
        )

        await query.answer("⏳ جاري إنشاء الجلسة...")

        try:
            await client.connect()


            if not await client.is_user_authorized():
                await query.edit_message_text(
                    f"⚠️ تحتاج إلى تسجيل الدخول يدوياً!\n\n"
                    f"رقم: `{phone}`\n"
                    f"API ID: `{api_id}`\n\n"
                    f"يرجى استخدام أمر 'إضافة حساب جديد' لإكمال التسجيل.",
                    parse_mode="MarkDown"
                )
            else:
                await query.edit_message_text(
                    f"✅ تم إضافة الحساب بنجاح!\n\n"
                    f"📱 رقم الهاتف: `{phone}`",
                    parse_mode="MarkDown"
                )

            await client.disconnect()

        except Exception as e:
            await query.edit_message_text(
                f"⚠️ تم حفظ البيانات لكن حدث خطأ في إنشاء الجلسة:\n{str(e)}\n\n"
                f"يمكنك إضافة الحساب يدوياً باستخدام البيانات المستخرجة.",
                parse_mode="MarkDown"
            )

    await query.answer()


async def check_account_subscription(client, channel_username):
    """التحقق من اشتراك حساب معين في قناة"""
    try:

        channel = await client.get_entity(channel_username)
        me = await client.get_me()
        participant = await client.get_participant(channel, me.id)
        return True
    except errors.UserNotParticipantError:
        return False
    except Exception as e:
        logger.error(f"خطأ في التحقق من اشتراك الحساب: {e}")
        return False

async def check_all_accounts_subscription():
    """التحقق من اشتراك جميع الحسابات في القنوات الإجبارية"""
    channel1 = get_admin_file_content(ADMIN_FILES["channel1"])
    channel2 = get_admin_file_content(ADMIN_FILES["channel2"])

    if not channel1 and not channel2:
        return

    accounts = db.get_accounts()
    accounts_to_remove = []

    for acc in accounts:
        client = await get_client(acc)
        try:

            await client.connect()

            if not await client.is_user_authorized():

                accounts_to_remove.append(acc[0])
                continue


            if channel1:
                if not await check_account_subscription(client, channel1):
                    accounts_to_remove.append(acc[0])
                    continue


            if channel2:
                if not await check_account_subscription(client, channel2):
                    accounts_to_remove.append(acc[0])
                    continue

        except Exception as e:
            logger.error(f"خطأ في فحص الحساب {acc[0]}: {e}")
            accounts_to_remove.append(acc[0])
        finally:
            await client.disconnect()


    for phone in accounts_to_remove:
        db.remove_account(phone)
        session_file = f"{SESSIONS_DIR}/{phone}.session"
        if os.path.exists(session_file):
            os.remove(session_file)
        logger.info(f"❌ تم حذف الحساب {phone} بسبب عدم الاشتراك في القنوات الإجبارية")

    return len(accounts_to_remove)

async def add_account_to_channels(client, channel1, channel2):
    """إضافة حساب جديد إلى قنوات الإشتراك الإجباري"""
    joined = []

    try:

        if channel1:
            try:
                if 'joinchat' in channel1 or '+' in channel1:
                    hash_link = channel1.split('/')[-1].replace('+', '')
                    await client(functions.messages.ImportChatInviteRequest(hash_link))
                else:
                    await client(JoinChannelRequest(channel1))
                joined.append(channel1)
                logger.info(f"✅ تم انضمام الحساب إلى القناة {channel1}")
            except errors.UserAlreadyParticipantError:
                logger.info(f"الحساب عضو بالفعل في القناة {channel1}")
            except Exception as e:
                logger.error(f"خطأ في الانضمام للقناة {channel1}: {e}")


        if channel2:
            try:
                if 'joinchat' in channel2 or '+' in channel2:
                    hash_link = channel2.split('/')[-1].replace('+', '')
                    await client(functions.messages.ImportChatInviteRequest(hash_link))
                else:
                    await client(JoinChannelRequest(channel2))
                joined.append(channel2)
                logger.info(f"✅ تم انضمام الحساب إلى القناة {channel2}")
            except errors.UserAlreadyParticipantError:
                logger.info(f"الحساب عضو بالفعل في القناة {channel2}")
            except Exception as e:
                logger.error(f"خطأ في الانضمام للقناة {channel2}: {e}")

    except Exception as e:
        logger.error(f"خطأ في إضافة الحساب للقنوات: {e}")

    return joined

async def process_adding(update, status_msg, members, target, accounts, auto_switch_enabled_for_user):
    global STOP_PROCESS
    STOP_PROCESS = False

    added_count = 0
    failed_count = 0
    member_index = 0
    total_members = len(members)
    failed_accounts = []
    flood_wait_accounts = []
    processed_accounts = 0
    auto_switched_accounts = []  # لتسجيل الحسابات التي تم التبديل منها تلقائياً

    members_per_account = max(5, min(15, total_members // len(accounts) + 1))
    account_delay = random.uniform(5, 10)
    
    acc_index = 0
    
    while acc_index < len(accounts) and member_index < total_members and not STOP_PROCESS:
        
        acc = accounts[acc_index]
        
        # تخطي الحسابات المعطلة
        if acc[0] in flood_wait_accounts:
            logger.warning(f"⏳ تخطي الحساب {acc[0]} بسبب الفلود السابق، جاري التبديل التلقائي...")
            if auto_switch_enabled_for_user:
                auto_switched_accounts.append(acc[0])
                acc_index += 1
                continue
            else:
                failed_accounts.append(acc[0])
                acc_index += 1
                continue
        
        processed_accounts += 1
        client = None
        account_added = 0
        account_failed = 0

        try:
            client = await get_client(acc)
            
            # محاولة الانضمام للمجموعة
            join_success = False
            join_attempts = 0
            while not join_success and join_attempts < 3:
                try:
                    if 'joinchat' in target or '+' in target:
                        hash_link = target.split('/')[-1].replace('+', '')
                        await client(functions.messages.ImportChatInviteRequest(hash_link))
                    else:
                        await client(JoinChannelRequest(target))
                    join_success = True
                    logger.info(f"✅ الحساب {acc[0]} انضم للمجموعة بنجاح")
                    await asyncio.sleep(random.uniform(2, 4))
                except errors.UserAlreadyParticipantError:
                    join_success = True
                    logger.info(f"✅ الحساب {acc[0]} عضو بالفعل في المجموعة")
                    break
                except errors.FloodWaitError as e:
                    wait_time = e.seconds if hasattr(e, 'seconds') else 60
                    logger.warning(f"⚠️ فلود في الانضمام للحساب {acc[0]}: انتظر {wait_time} ثانية")
                    
                    if wait_time > 30:
                        flood_wait_accounts.append(acc[0])
                        if auto_switch_enabled_for_user:
                            logger.info(f"🔄 التبديل التلقائي: تخطي الحساب {acc[0]} والانتقال للحساب التالي")
                            auto_switched_accounts.append(acc[0])
                            join_success = False
                            break
                        else:
                            await asyncio.sleep(min(wait_time, 60))
                            join_attempts += 1
                    else:
                        await asyncio.sleep(min(wait_time, 60))
                        join_attempts += 1
                except Exception as e:
                    logger.warning(f"⚠️ خطأ في انضمام الحساب {acc[0]}: {e}")
                    join_attempts += 1
                    await asyncio.sleep(5)
            
            if not join_success:
                logger.error(f"❌ فشل انضمام الحساب {acc[0]} للمجموعة")
                failed_accounts.append(acc[0])
                acc_index += 1
                continue
            
            # الحصول على الكيان الهدف
            try:
                target_entity = await client.get_entity(target)
            except Exception as e:
                logger.error(f"❌ لا يمكن الوصول للمجموعة الهدف {target}: {e}")
                failed_accounts.append(acc[0])
                acc_index += 1
                continue
            
            # حساب عدد الأعضاء المتبقين لهذا الحساب
            remaining_members = total_members - member_index
            current_batch_size = min(members_per_account, remaining_members)
            
            # تحديث رسالة الحالة
            await status_msg.edit_text(
                f"⏳ جاري الإضافة...\n\n"
                f"📊 الحساب: `{acc_index + 1}/{len(accounts)}`\n"
                f"📱 رقم: `{acc[0][-8:]}`\n"
                f"✅ تم إضافة: `{added_count}` عضو\n"
                f"❌ فشل: `{failed_count}` عضو\n"
                f"📈 التقدم: `{(member_index / total_members * 100):.1f}%`\n"
                f"👥 متبقي: `{remaining_members}` عضو\n"
                f"⏱️ هذا الحساب: `{account_added}` عضو\n"
                f"{'🔄 التبديل التلقائي: مفعل' if auto_switch_enabled_for_user else '❌ التبديل التلقائي: معطف'}",
                parse_mode="Markdown",
                reply_markup=get_stop_keyboard()
            )
            
            # إضافة الأعضاء
            for batch_idx in range(current_batch_size):
                if STOP_PROCESS:
                    logger.info("🛑 تم إيقاف العملية أثناء الإضافة")
                    break
                
                if member_index >= total_members:
                    break
                
                member = members[member_index]
                member_index += 1
                
                try:
                    username = member[1]
                    if username:
                        add_success = False
                        for retry in range(2):
                            try:
                                await client(InviteToChannelRequest(target_entity, [username]))
                                add_success = True
                                break
                            except errors.FloodWaitError as e:
                                wait_time = e.seconds if hasattr(e, 'seconds') else 30
                                if wait_time > 30:
                                    logger.warning(f"⚠️ فلود كبير للحساب {acc[0]}: انتظر {wait_time} ثانية")
                                    flood_wait_accounts.append(acc[0])
                                    if auto_switch_enabled_for_user:
                                        logger.info(f"🔄 التبديل التلقائي: حساب {acc[0]} دخل فلود، التبديل للحساب التالي")
                                        member_index -= 1  # نرجع العضو لأنه لم يضاف
                                        raise Exception("AUTO_SWITCH_FLOOD")
                                    else:
                                        await asyncio.sleep(min(wait_time, 60))
                                        continue
                                logger.warning(f"⚠️ فلود: انتظر {wait_time} ثانية للحساب {acc[0]}")
                                await asyncio.sleep(min(wait_time, 30))
                            except errors.UserAlreadyParticipantError:
                                add_success = True
                                break
                            except Exception as e:
                                if retry == 0:
                                    await asyncio.sleep(2)
                                    continue
                                raise e
                        
                        if add_success:
                            added_count += 1
                            account_added += 1
                            logger.info(f"✅ تم إضافة {username} بواسطة {acc[0][-8:]}")
                        else:
                            failed_count += 1
                            account_failed += 1
                            logger.warning(f"❌ فشل إضافة {username}")
                        
                        # تحديث التقدم كل 3 إضافات
                        if added_count % 3 == 0 or added_count == 1:
                            current_progress = (member_index / total_members) * 100
                            await status_msg.edit_text(
                                f"⏳ جاري الإضافة...\n\n"
                                f"📊 الحساب: `{acc_index + 1}/{len(accounts)}`\n"
                                f"📱 رقم: `{acc[0][-8:]}`\n"
                                f"✅ تم إضافة: `{added_count}` عضو\n"
                                f"❌ فشل: `{failed_count}` عضو\n"
                                f"📈 التقدم: `{current_progress:.1f}%`\n"
                                f"⏱️ هذا الحساب: `{account_added}` عضو\n"
                                f"{'🔄 التبديل التلقائي: مفعل' if auto_switch_enabled_for_user else '❌ التبديل التلقائي: معطف'}",
                                parse_mode="Markdown",
                                reply_markup=get_stop_keyboard()
                            )
                        
                        # تأخير بين الإضافات
                        if add_success:
                            delay = ADD_DELAY + random.uniform(1, 4)
                        else:
                            delay = random.uniform(3, 6)
                        await asyncio.sleep(delay)
                        
                except Exception as e:
                    if str(e) == "AUTO_SWITCH_FLOOD":
                        # التبديل التلقائي بسبب الفلود
                        member_index -= 1  # نرجع العضو
                        break
                    elif "PeerFloodError" in str(type(e).__name__) or "Flood" in str(e):
                        logger.error(f"🚫 فلود شديد للحساب {acc[0]} - تم حظره مؤقتاً")
                        failed_accounts.append(acc[0])
                        flood_wait_accounts.append(acc[0])
                        if auto_switch_enabled_for_user:
                            logger.info(f"🔄 التبديل التلقائي: حساب {acc[0]} دخل فلود شديد، التبديل للحساب التالي")
                            break
                        else:
                            failed_count += (current_batch_size - batch_idx)
                            break
                    elif "UserPrivacyRestrictedError" in str(type(e).__name__):
                        failed_count += 1
                        continue
                    elif "UserNotMutualContactError" in str(type(e).__name__):
                        failed_count += 1
                        continue
                    elif "UserChannelsTooMuchError" in str(type(e).__name__):
                        failed_count += 1
                        continue
                    elif "ChatWriteForbiddenError" in str(type(e).__name__):
                        logger.error(f"✍️ لا يمكن الكتابة في المجموعة الهدف {target}")
                        failed_count += (current_batch_size - batch_idx)
                        break
                    elif "InviteHashExpiredError" in str(type(e).__name__):
                        logger.error(f"⏰ رابط الدعوة منتهي الصلاحية")
                        await status_msg.edit_text("❌ رابط الدعوة منتهي الصلاحية! يرجى تحديث الرابط.")
                        return added_count, failed_count + (current_batch_size - batch_idx), failed_accounts
                    else:
                        logger.error(f"⚠️ خطأ غير متوقع: {type(e).__name__} - {e}")
                        failed_count += 1
                        continue
            
            # حذف جهات الاتصال بعد انتهاء الحساب
            if account_added > 0:
                try:
                    deleted = await clear_contacts_for_account(client)
                    logger.info(f"🧹 تم حذف {deleted} جهة اتصال من الحساب {acc[0][-8:]}")
                except Exception as e:
                    logger.warning(f"⚠️ خطأ في حذف جهات الاتصال: {e}")
            
            # انتظار قبل الحساب التالي
            if acc_index < len(accounts) - 1 and not STOP_PROCESS and member_index < total_members:
                wait_time = account_delay + random.uniform(0, 3)
                logger.info(f"⏳ انتظار {wait_time:.1f} ثانية قبل الحساب التالي...")
                await asyncio.sleep(wait_time)
            
            acc_index += 1
            
        except errors.FloodWaitError as e:
            wait_time = e.seconds if hasattr(e, 'seconds') else 60
            logger.error(f"🌊 فلود للحساب {acc[0]}: انتظر {wait_time} ثانية")
            failed_accounts.append(acc[0])
            flood_wait_accounts.append(acc[0])
            if auto_switch_enabled_for_user:
                logger.info(f"🔄 التبديل التلقائي: تخطي الحساب {acc[0]} والانتقال للحساب التالي")
                acc_index += 1
            elif wait_time <= 30:
                await asyncio.sleep(wait_time)
                acc_index += 1
            else:
                acc_index += 1
                
        except Exception as e:
            logger.error(f"💥 خطأ فادح في الحساب {acc[0] if acc else 'unknown'}: {type(e).__name__} - {e}")
            failed_accounts.append(acc[0] if acc else 'unknown')
            acc_index += 1
            
        finally:
            if client:
                try:
                    await client.disconnect()
                    logger.info(f"🔌 تم فصل الحساب {acc[0][-8:] if acc else 'unknown'}")
                except:
                    pass
    
    # حساب نسبة النجاح
    success_rate = (added_count / total_members * 100) if total_members > 0 else 0
    
    final_text = (
        f"📊 نتائج عملية الإضافة\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"👥 إجمالي الأعضاء: `{total_members}`\n"
        f"✅ تم إضافة: `{added_count}`\n"
        f"❌ فشل: `{failed_count}`\n"
        f"📈 نسبة النجاح: `{success_rate:.1f}%`\n"
        f"📱 حسابات مستخدمة: `{processed_accounts}/{len(accounts)}`\n"
    )
    
    if auto_switched_accounts:
        final_text += f"\n🔄 تم التبديل التلقائي من: `{len(set(auto_switched_accounts))}` حسابات"
    
    if flood_wait_accounts:
        final_text += f"\n⚠️ حسابات دخلت فلود: `{len(set(flood_wait_accounts))}`"
    
    if failed_accounts:
        final_text += f"\n❌ حسابات فشلت: `{len(set(failed_accounts))}`"
    
    if STOP_PROCESS:
        final_text += f"\n\n🛑 تم إيقاف العملية يدوياً"
    
    if auto_switch_enabled_for_user:
        final_text += f"\n\n🔄 وضع التبديل التلقائي: مفعل ✅"
    else:
        final_text += f"\n\n❌ وضع التبديل التلقائي: معطل"
    
    try:
        await status_msg.edit_text(final_text, parse_mode="Markdown")
    except:
        if update and update.message:
            await update.message.reply_text(final_text, parse_mode="Markdown")
    
    STOP_PROCESS = False
    return added_count, failed_count, failed_accounts

async def scrape_hidden_members(client, entity, status_msg, max_messages=20000):
    global STOP_PROCESS
    STOP_PROCESS = False

    users_to_save = []
    seen_ids = set()
    offset_id = 0
    batch_size = 100
    total_scraped = 0
    messages_processed = 0

    while messages_processed < max_messages and not STOP_PROCESS:
        try:
            messages = await client(GetHistoryRequest(
                peer=entity,
                limit=batch_size,
                offset_date=None,
                offset_id=offset_id,
                max_id=0,
                min_id=0,
                add_offset=0,
                hash=0
            ))

            if not messages.messages:
                break

            for m in messages.messages:
                messages_processed += 1
                if m.from_id and isinstance(m.from_id, types.PeerUser):
                    u_id = m.from_id.user_id
                    if u_id not in seen_ids:
                        try:
                            user = await client.get_entity(u_id)
                            if not user.bot and user.username:
                                users_to_save.append((user.id, user.username, user.access_hash, None, 'hidden'))
                                seen_ids.add(u_id)
                                total_scraped += 1
                        except:
                            continue

            if messages_processed % 500 == 0:
                await status_msg.edit_text(
                    f"⏳ جاري السحب...\n"
                    f"📨 الرسائل المعالجة: {messages_processed}/{max_messages}\n"
                    f"👥 الأعضاء المسحوبين: {total_scraped}",
                    reply_markup=get_stop_keyboard()
                )

            offset_id = messages.messages[-1].id
            await asyncio.sleep(0.5)

        except Exception as e:
            logger.error(f"خطأ في السحب: {e}")
            break

    if STOP_PROCESS:
        STOP_PROCESS = False

    return users_to_save

async def trans_hidden_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    accounts = db.get_user_accounts(user_id)
    
    if not accounts:
        keyboard = [
            [InlineKeyboardButton("➕ إضافة حساب جديد", callback_data='add_acc')],
            [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data='main_menu')]
        ]
        await query.edit_message_text(
            "📭 ملكش حسابات!\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "⚠️ لا يمكنك استخدام خدمة نقل الأعضاء المخفيين\n"
            "لأنه ليس لديك أي حسابات مسجلة.\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "➕ اضغط على الزر أدناه لإضافة حساب:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        return
    
    await query.edit_message_text("🔗 أرسل رابط المجموعة (المصدر) لسحب المخفيين:")
    return TRANSFER_HIDDEN_SOURCE

async def trans_hidden_source(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['source'] = update.message.text.strip()
    await update.message.reply_text("🎯 أرسل رابط المجموعة (الهدف) للإضافة إليها:")
    return TRANSFER_HIDDEN_TARGET

async def trans_hidden_target(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target = update.message.text.strip()
    source = context.user_data['source']
    user_id = update.effective_user.id
    accounts = db.get_user_accounts(str(user_id))

    if not accounts:
        await update.message.reply_text("📭 لم تقم بإضافة أي حساب خاص بك!")
        return ConversationHandler.END

    auto_switch_status = is_auto_switch_enabled_for_user(user_id)

    status_msg = await update.message.reply_text(
        "⚡ جاري السحب المتوازي السريع للمخفيين...\n"
        "📨 سيتم تحليل آخر 20,000 رسالة بشكل متوازي",
        reply_markup=get_stop_keyboard(),
        parse_mode="Markdown"
    )
    
    db.clear_members('hidden')

    client = await get_client(accounts[0])
    try:
        # محاولة الانضمام للمجموعة
        try:
            if 'joinchat' in source or '+' in source:
                hash_link = source.split('/')[-1].replace('+', '')
                await client(functions.messages.ImportChatInviteRequest(hash_link))
            else:
                await client(JoinChannelRequest(source))
        except:
            pass

        entity = await client.get_entity(source)
        
        # استخدام النسخة السريعة المتوازية
        users_to_save = await scrape_hidden_members_parallel(client, entity, status_msg, MAX_MESSAGES_SCRAPE)

        if users_to_save:
            db.save_members(users_to_save)
            scraped_count = len(users_to_save)
        else:
            scraped_count = 0

    except Exception as e:
        await status_msg.edit_text(f"❌ خطأ أثناء السحب: {e}")
        await client.disconnect()
        return ConversationHandler.END
    finally:
        await client.disconnect()

    if scraped_count == 0:
        await status_msg.edit_text("📭 لم يتم العثور على أعضاء مخفيين.")
        return ConversationHandler.END

    await status_msg.edit_text(f"✅ تم سحب {scraped_count} عضو (بسرعة متوازية).\n⏳ جاري البدء في الإضافة...", reply_markup=get_stop_keyboard())
    members = db.get_members_by_type('hidden')
    
    added_count, failed_count, failed_accounts = await process_adding(update, status_msg, members, target, accounts, auto_switch_status)

    success_rate = (added_count / scraped_count * 100) if scraped_count > 0 else 0
    result_text = (
        f"نتائج ميزة نقل المخفيين كيرو\n"
        f"••••••••••••••••••••••••••••\n"
        f"📥 عدد الأعضاء المسحوبين: {scraped_count}\n"
        f"✅ عدد الأعضاء المضافين: {added_count}\n"
        f"❌ عدد الأعضاء الذين فشلت إضافتهم: {failed_count}\n"
        f"📊 نسبة النجاح: {success_rate:.1f}%\n"
        f"⚡ تم السحب بواسطة: معالجة متوازية\n"
        f"••••••••••••••••••••••••••••"
    )
    if failed_accounts:
        result_text += f"\n⚠️ حسابات محظورة مؤقتاً: {len(failed_accounts)}"

    await status_msg.edit_text(result_text)
    return ConversationHandler.END

async def trans_visible_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    accounts = db.get_user_accounts(user_id)
    
    if not accounts:
        keyboard = [
            [InlineKeyboardButton("➕ إضافة حساب جديد", callback_data='add_acc')],
            [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data='main_menu')]
        ]
        await query.edit_message_text(
            "📭 ملكش حسابات!\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "⚠️ لا يمكنك استخدام خدمة نقل الأعضاء الظاهرين\n"
            "لأنه ليس لديك أي حسابات مسجلة.\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "➕ اضغط على الزر أدناه لإضافة حساب:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        return
    
    await query.edit_message_text("🔗 أرسل رابط المجموعة (المصدر) لسحب الظاهرين:")
    return TRANSFER_VISIBLE_SOURCE



async def trans_visible_source(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['source'] = update.message.text.strip()
    await update.message.reply_text("🎯 أرسل رابط المجموعة (الهدف) للإضافة إليها:")
    return TRANSFER_VISIBLE_TARGET

async def trans_visible_target(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target = update.message.text.strip()
    source = context.user_data['source']
    user_id = update.effective_user.id  # <-- استخدام id المستخدم الصحيح
    accounts = db.get_user_accounts(str(user_id))  # <-- تحويل id إلى string للقاعدة

    if not accounts:
        await update.message.reply_text("📭 لم تقم بإضافة أي حساب خاص بك!")
        return ConversationHandler.END

    # قراءة إعداد التبديل التلقائي لهذا المستخدم
    auto_switch_status = is_auto_switch_enabled_for_user(user_id)

    status_msg = await update.message.reply_text("⏳ جاري سحب الأعضاء الظاهرين...", reply_markup=get_stop_keyboard())
    db.clear_members('visible')
    scraped_count = 0

    client = await get_client(accounts[0])
    try:
        try:
            if 'joinchat' in source or '+' in source:
                hash_link = source.split('/')[-1].replace('+', '')
                await client(functions.messages.ImportChatInviteRequest(hash_link))
            else:
                await client(JoinChannelRequest(source))
        except:
            pass

        entity = await client.get_entity(source)
        users_to_save = []
        batch_count = 0

        async for p in client.iter_participants(entity):
            if STOP_PROCESS: break
            if not p.bot and p.username:
                users_to_save.append((p.id, p.username, p.access_hash, None, 'visible'))
                batch_count += 1

                if batch_count % SCRAPE_BATCH_SIZE == 0:
                    await status_msg.edit_text(f"⏳ تم سحب {batch_count} عضو...", reply_markup=get_stop_keyboard())

        if users_to_save:
            db.save_members(users_to_save)
            scraped_count = len(users_to_save)
    except Exception as e:
        await status_msg.edit_text(f"❌ خطأ أثناء سحب الظاهرين: {e}")
        await client.disconnect()
        return ConversationHandler.END
    finally:
        await client.disconnect()

    if scraped_count == 0:
        await status_msg.edit_text("📭 لم يتم العثور على أعضاء ظاهرين.")
        return ConversationHandler.END

    await status_msg.edit_text(f"✅ تم سحب {scraped_count} عضو.\n⏳ جاري البدء في الإضافة...", reply_markup=get_stop_keyboard())
    members = db.get_members_by_type('visible')
    
    # تمرير إعداد التبديل التلقائي للمستخدم
    added_count, failed_count, failed_accounts = await process_adding(update, status_msg, members, target, accounts, auto_switch_status)

    success_rate = (added_count / scraped_count * 100) if scraped_count > 0 else 0
    result_text = (
        f"نتائج ميزة نقل الظاهرين كيرو\n"
        f"••••••••••••••••••••••••••••\n"
        f"📥 عدد الأعضاء المسحوبين: {scraped_count}\n"
        f"✅ عدد الأعضاء المضافين: {added_count}\n"
        f"❌ عدد الأعضاء الذين فشلت إضافتهم: {failed_count}\n"
        f"📊 نسبة النجاح: {success_rate:.1f}%\n"
        f"••••••••••••••••••••••••••••"
    )
    if failed_accounts:
        result_text += f"\n⚠️ حسابات محظورة مؤقتاً: {len(failed_accounts)}"

    await status_msg.edit_text(result_text)
    return ConversationHandler.END

async def trans_file_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """📂 نقل أعضاء من ملف - شرح الخدمة"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    accounts = db.get_user_accounts(user_id)
    
    if not accounts:
        keyboard = [
            [InlineKeyboardButton("➕ إضافة حساب جديد", callback_data='add_acc')],
            [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data='main_menu')]
        ]
        await query.edit_message_text(
            "📭 ملكش حسابات!\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "⚠️ لا يمكنك استخدام خدمة نقل الأعضاء من ملف\n"
            "لأنه ليس لديك أي حسابات مسجلة.\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "➕ اضغط على الزر أدناه لإضافة حساب:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        return
    
    await query.edit_message_text(
        "📂 نقل أعضاء من ملف\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "📌 شرح خدمه الزر:\n"
        "• تقوم برفع ملف يحتوي على يوزرات الأعضاء\n"
        "• البوت يقرأ الملف ويستخرج اليوزرات\n"
        "• ثم يقوم بإضافة هؤلاء الأعضاء إلى مجموعتك\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "📁 صيغ الملفات المدعومة:\n"
        "• `JSON` - ملف بصيغة JSON\n"
        "• `TXT` - ملف نصي سطر لكل يوزر\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "📝 مثال ملف TXT:\n"
        "`@user1`\n`@user2`\n`user3`\n\n"
        "📝 مثال ملف JSON:\n"
        "`[{\"username\": \"user1\"}, {\"username\": \"user2\"}]`\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "📤 الخطوة التالية:\n"
        "• أرسل الملف الذي تريد نقل الأعضاء منه",
        parse_mode="Markdown"
    )
    return TRANSFER_FILE_DOC

async def trans_file_doc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """📂 استقبال ملف الأعضاء"""
    if not update.message.document:
        await update.message.reply_text(
            "❌ خطأ: لم يتم إرسال ملف!\n"
            "📤 يرجى إرسال ملف JSON أو TXT صحيح.",
            parse_mode="Markdown"
        )
        return TRANSFER_FILE_DOC
    
    doc = update.message.document
    if not doc.file_name.endswith(('.json', '.txt')):
        await update.message.reply_text(
            "❌ صيغة غير مدعومة!\n"
            "📁 يرجى إرسال ملف بصيغة `.json` أو `.txt` فقط.",
            parse_mode="Markdown"
        )
        return TRANSFER_FILE_DOC
    
    file_path = f"{UPLOAD_DIR}/{doc.file_name}"
    file = await context.bot.get_file(doc.file_id)
    await file.download_to_drive(file_path)
    
    context.user_data['members_file'] = file_path
    
    await update.message.reply_text(
        "✅ تم استلام الملف بنجاح!\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"📁 اسم الملف: `{doc.file_name}`\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "🎯 الخطوة التالية:\n"
        "• أرسل رابط المجموعة أو القناة الهدف\n"
        "• سيتم إضافة الأعضاء إليها\n\n"
        "📝 مثال:\n"
        "`https://t.me/username`\n"
        "أو\n"
        "`@username`",
        parse_mode="Markdown"
    )
    return TRANSFER_FILE_TARGET

async def trans_file_target(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """🎯 استقبال الرابط الهدف وبدء الإضافة"""
    target = update.message.text.strip()
    file_path = context.user_data.get('members_file')
    
    if not file_path or not os.path.exists(file_path):
        await update.message.reply_text(
            "❌ خطأ: لم يتم العثور على الملف!\n"
            "📂 يرجى البدء من جديد باستخدام زر 'نقل من ملف'",
            parse_mode="Markdown"
        )
        return ConversationHandler.END
    
    user_id = update.effective_user.id  # <-- استخدام id المستخدم الصحيح
    accounts = db.get_user_accounts(str(user_id))  # <-- تحويل id إلى string للقاعدة
    
    if not accounts:
        await update.message.reply_text(
            "📭 لا توجد حسابات!\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "⚠️ يجب عليك إضافة حسابات أولاً.\n"
            "• استخدم زر '➕ إضافة حساب'\n"
            "• أو '📥 استيراد جلسات'\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "🔄 ثم حاول مرة أخرى.",
            parse_mode="Markdown"
        )
        return ConversationHandler.END
    
    # قراءة إعداد التبديل التلقائي لهذا المستخدم
    auto_switch_status = is_auto_switch_enabled_for_user(user_id)
    
    status_msg = await update.message.reply_text(
        "⏳ جاري تجهيز الملف...\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "📁 قراءة الملف واستخراج الأعضاء...",
        parse_mode="Markdown"
    )
    members = []
    
    try:
        if file_path.endswith('.json'):
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for item in data:
                    if isinstance(item, dict) and 'username' in item:
                        username = item['username'].replace('@', '')
                        if username:
                            members.append((None, username, None, None, 'file'))
                    elif isinstance(item, str):
                        username = item.replace('@', '')
                        if username:
                            members.append((None, username, None, None, 'file'))
        else:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    username = line.strip().replace('@', '')
                    if username:
                        members.append((None, username, None, None, 'file'))
        
        if not members:
            await status_msg.edit_text(
                "📭 الملف فارغ أو لا يحتوي على أعضاء صالحين!\n"
                "━━━━━━━━━━━━━━━━━━━━━\n"
                "💡 تأكد من:\n"
                "• وجود يوزرات صحيحة في الملف\n"
                "• التنسيق الصحيح (يوزر واحد لكل سطر)\n"
                "━━━━━━━━━━━━━━━━━━━━━\n"
                "🔄 يرجى المحاولة مرة أخرى.",
                parse_mode="Markdown"
            )
            return ConversationHandler.END
        
        await status_msg.edit_text(
            f"✅ تم تحميل الملف بنجاح!\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"👥 عدد الأعضاء: `{len(members)}` عضو\n"
            f"🎯 المجموعة الهدف: `{target}`\n"
            f"📱 عدد الحسابات: `{len(accounts)}` حساب\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"⏳ جاري بدء عملية الإضافة...\n"
            f"⚠️ قد تستغرق العملية عدة دقائق",
            parse_mode="Markdown",
            reply_markup=get_stop_keyboard()
        )
        
        # تمرير إعداد التبديل التلقائي للمستخدم
        added_count, failed_count, failed_accounts = await process_adding(update, status_msg, members, target, accounts, auto_switch_status)
        
        success_rate = (added_count / len(members) * 100) if members else 0
        
        final_text = (
            f"✅ اكتمل نقل الأعضاء من الملف!\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"📁 الملف: `{os.path.basename(file_path)}`\n"
            f"👥 إجمالي الأعضاء: `{len(members)}`\n"
            f"✅ تم الإضافة: `{added_count}`\n"
            f"❌ فشل: `{failed_count}`\n"
            f"📈 نسبة النجاح: `{success_rate:.1f}%`\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"🎯 المجموعة الهدف: `{target}`"
        )
        
        if failed_accounts:
            final_text += f"\n⚠️ حسابات فشلت: `{len(set(failed_accounts))}`"
        
        await status_msg.edit_text(final_text, parse_mode="Markdown")
        
        # حذف الملف المؤقت
        try:
            os.remove(file_path)
        except:
            pass
        
    except Exception as e:
        await status_msg.edit_text(
            f"❌ خطأ في معالجة الملف!\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"الخطأ: `{str(e)[:200]}`\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"💡 يرجى التأكد من صيغة الملف والمحاولة مرة أخرى.",
            parse_mode="Markdown"
        )
    
    return ConversationHandler.END


async def store_hidden_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """💾 تخزين الأعضاء المخفيين - شرح الخدمة"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    accounts = db.get_user_accounts(user_id)
    
    if not accounts:
        keyboard = [
            [InlineKeyboardButton("➕ إضافة حساب جديد", callback_data='add_acc')],
            [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data='main_menu')]
        ]
        await query.edit_message_text(
            "📭 ملكش حسابات!\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "⚠️ لا يمكنك استخدام خدمة تخزين الأعضاء المخفيين\n"
            "لأنه ليس لديك أي حسابات مسجلة.\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "➕ اضغط على الزر أدناه لإضافة حساب:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        return
    
    await query.edit_message_text(
        "💾 تخزين الأعضاء المخفيين\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "📌 شرح خدمه الزر:\n"
        "• يقوم البوت بسحب الأعضاء المخفيين من آخر 20,000 رسالة\n"
        "• الأعضاء المخفيين: هم الذين يظهرون في الرسائل ولكنهم ليسوا أعضاء ظاهرين\n"
        "• يتم تخزينهم في قاعدة البيانات لاستخدامهم لاحقاً\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "📌 الاستخدام:\n"
        "• سيُطلب منك رابط المجموعة المصدر\n"
        "• البوت يحلل آخر 20,000 رسالة\n"
        "• يستخرج الحسابات التي كتبت رسائل\n"
        "• يحفظها في قاعدة البيانات\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "🔗 الخطوة التالية:\n"
        "• أرسل رابط المجموعة أو القناة المصدر",
        parse_mode="Markdown"
    )
    return STORE_HIDDEN_SOURCE

async def toggle_auto_switch_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تشغيل/إيقاف خاصية التبديل التلقائي للمستخدم الحالي فقط"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    if is_auto_switch_enabled_for_user(user_id):
        disable_auto_switch_for_user(user_id)
        await query.edit_message_text(
            "❌ تم تعطيل خاصية التبديل التلقائي **لحساباتك فقط**!\n\n"
            "📌 عند تعطيلها:\n"
            "• عند وصول حساب لحالة فلود، يتم تخطيه والتوقف\n"
            "• لن يتم التبديل تلقائياً للحساب التالي",
            parse_mode="Markdown"
        )
    else:
        enable_auto_switch_for_user(user_id)
        await query.edit_message_text(
            "✅ تم تفعيل خاصية التبديل التلقائي **لحساباتك فقط**!\n\n"
            "📌 عند تفعيلها:\n"
            "• عند وصول حساب لحالة فلود، يتحول تلقائياً للحساب التالي\n"
            "• تستمر العملية دون توقف\n"
            "• يتم تسجيل الحسابات التي تم التبديل منها",
            parse_mode="Markdown"
        )
    
    await asyncio.sleep(2)
    await start(update, context)

async def store_visible_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """💾 تخزين الأعضاء الظاهرين - شرح الخدمة"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    accounts = db.get_user_accounts(user_id)
    
    if not accounts:
        keyboard = [
            [InlineKeyboardButton("➕ إضافة حساب جديد", callback_data='add_acc')],
            [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data='main_menu')]
        ]
        await query.edit_message_text(
            "📭 ملكش حسابات!\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "⚠️ لا يمكنك استخدام خدمة تخزين الأعضاء الظاهرين\n"
            "لأنه ليس لديك أي حسابات مسجلة.\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "➕ اضغط على الزر أدناه لإضافة حساب:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        return
    
    await query.edit_message_text(
        "💾 تخزين الأعضاء الظاهرين\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "📌 شرح خدمة الزر:\n"
        "• يقوم البوت بسحب جميع الأعضاء الظاهرين من المجموعة أو القناة\n"
        "• الأعضاء الظاهرين: هم الأعضاء الموجودين في قائمة الأعضاء\n"
        "• يتم تخزينهم في قاعدة البيانات لاستخدامهم لاحقاً\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "📌 الاستخدام:\n"
        "• سيُطلب منك رابط المجموعة أو القناة المصدر\n"
        "• البوت يسحب جميع الأعضاء الظاهرين\n"
        "• يحفظهم في قاعدة البيانات\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "⚠️ ملاحظة:\n"
        "• المجموعات الكبيرة قد تستغرق وقتاً أطول\n"
        "• الحساب المستخدم يجب أن يكون عضو في المجموعة\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "🔗 الخطوة التالية:\n"
        "• أرسل رابط المجموعة أو القناة المصدر",
        parse_mode="Markdown"
    )
    return STORE_VISIBLE_SOURCE

async def store_visible_source(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """🔗 استقبال الرابط المصدر وبدء تخزين الأعضاء الظاهرين"""
    source = update.message.text.strip()
    user_id = str(update.effective_user.id)
    accounts = db.get_user_accounts(user_id)
    
    if not accounts:
        await update.message.reply_text(
            "📭 لا توجد حسابات!\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "⚠️ يجب عليك إضافة حسابات أولاً.\n"
            "• استخدم زر '➕ إضافة حساب جديد'\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "🔄 ثم حاول مرة أخرى.",
            parse_mode="Markdown"
        )
        return ConversationHandler.END
    
    status_msg = await update.message.reply_text(
        "⏳ جاري تجهيز عملية السحب...\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔗 المجموعة المصدر: `{source}`\n"
        "⏳ جاري الاتصال بالمجموعة...",
        parse_mode="Markdown",
        reply_markup=get_stop_keyboard()
    )
    
    client = await get_client(accounts[0])
    scraped_count = 0
    users_to_save = []
    
    try:
        # محاولة الانضمام للمجموعة
        try:
            if 'joinchat' in source or '+' in source:
                hash_link = source.split('/')[-1].replace('+', '')
                await client(functions.messages.ImportChatInviteRequest(hash_link))
            else:
                await client(JoinChannelRequest(source))
            await status_msg.edit_text(
                "✅ تم الانضمام للمجموعة بنجاح!\n"
                "⏳ جاري سحب الأعضاء الظاهرين...\n"
                "👥 جاري استخراج قائمة الأعضاء...",
                parse_mode="Markdown",
                reply_markup=get_stop_keyboard()
            )
        except Exception as e:
            await status_msg.edit_text(
                f"⚠️ تنبيه: {str(e)[:100]}\n"
                f"⏳ جاري المحاولة بدون انضمام...",
                parse_mode="Markdown"
            )
        
        entity = await client.get_entity(source)
        
        # سحب الأعضاء الظاهرين
        async for p in client.iter_participants(entity):
            if STOP_PROCESS:
                break
            if not p.bot and p.username:
                users_to_save.append((p.id, p.username, p.access_hash, None, 'visible'))
                scraped_count += 1
                
                # تحديث التقدم كل 100 عضو
                if scraped_count % 100 == 0:
                    await status_msg.edit_text(
                        f"⏳ جاري سحب الأعضاء الظاهرين...\n"
                        f"━━━━━━━━━━━━━━━━━━━━━\n"
                        f"👥 تم السحب: `{scraped_count}` عضو\n"
                        f"⏳ جاري المتابعة...",
                        parse_mode="Markdown",
                        reply_markup=get_stop_keyboard()
                    )
        
        if users_to_save:
            db.save_members(users_to_save)
            await status_msg.edit_text(
                f"✅ تم تخزين الأعضاء الظاهرين بنجاح!\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"👥 عدد الأعضاء المخزنين: `{len(users_to_save)}`\n"
                f"💾 تم الحفظ في قاعدة البيانات\n"
                f"📁 تم الحفظ في ملف JSON\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"💡 يمكنك الآن استخدام زر 'نقل ظاهر' لإضافتهم",
                parse_mode="Markdown"
            )
        else:
            await status_msg.edit_text(
                "📭 لم يتم العثور على أعضاء ظاهرين!\n"
                "━━━━━━━━━━━━━━━━━━━━━\n"
                "💡 أسباب محتملة:\n"
                "• المجموعة ليس بها أعضاء\n"
                "• الأعضاء ليس لديهم يوزرات\n"
                "• البوت ليس لديه صلاحيات كافية\n"
                "━━━━━━━━━━━━━━━━━━━━━\n"
                "🔄 حاول مرة أخرى مع مجموعة أخرى.",
                parse_mode="Markdown"
            )
    except Exception as e:
        await status_msg.edit_text(
            f"❌ خطأ أثناء السحب!\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"الخطأ: `{str(e)[:200]}`\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"💡 تأكد من:\n"
            f"• صحة رابط المجموعة\n"
            f"• أن البوت عضو في المجموعة\n"
            f"• أن لديك صلاحيات الوصول",
            parse_mode="Markdown"
        )
    finally:
        await client.disconnect()
    
    return ConversationHandler.END

async def store_hidden_source(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """🔗 استقبال الرابط المصدر وبدء التخزين (باستخدام المعالجة المتوازية)"""
    source = update.message.text.strip()
    user_id = str(update.effective_user.id)
    accounts = db.get_user_accounts(user_id)
    
    if not accounts:
        await update.message.reply_text(
            "📭 لا توجد حسابات!\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "⚠️ يجب عليك إضافة حسابات أولاً.\n"
            "• استخدم زر '➕ إضافة حساب'\n"
            "• أو '📥 استيراد جلسات'\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "🔄 ثم حاول مرة أخرى.",
            parse_mode="Markdown"
        )
        return ConversationHandler.END
    
    status_msg = await update.message.reply_text(
        "⚡ جاري السحب المتوازي السريع للمخفيين...\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔗 المجموعة المصدر: `{source}`\n"
        "⚡ استخدام المعالجة المتوازية للتسريع...",
        parse_mode="Markdown",
        reply_markup=get_stop_keyboard()
    )
    
    client = await get_client(accounts[0])
    
    try:
        # محاولة الانضمام للمجموعة
        try:
            if 'joinchat' in source or '+' in source:
                hash_link = source.split('/')[-1].replace('+', '')
                await client(functions.messages.ImportChatInviteRequest(hash_link))
            else:
                await client(JoinChannelRequest(source))
        except Exception as e:
            await status_msg.edit_text(
                f"⚠️ تنبيه: {str(e)[:100]}\n"
                f"⏳ جاري المحاولة بدون انضمام...",
                parse_mode="Markdown"
            )
        
        entity = await client.get_entity(source)
        
        # استخدام النسخة السريعة المتوازية
        users_to_save = await scrape_hidden_members_parallel(client, entity, status_msg, MAX_MESSAGES_SCRAPE)
        
        if users_to_save:
            db.save_members(users_to_save)
            await status_msg.edit_text(
                f"✅ تم تخزين الأعضاء المخفيين بنجاح!\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"👥 عدد الأعضاء المخزنين: `{len(users_to_save)}`\n"
                f"💾 تم الحفظ في قاعدة البيانات\n"
                f"📁 تم الحفظ في ملف JSON\n"
                f"⚡ تم السحب باستخدام: معالجة متوازية\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"💡 يمكنك الآن استخدام زر 'نقل مخفيين' لإضافتهم",
                parse_mode="Markdown"
            )
        else:
            await status_msg.edit_text(
                "📭 لم يتم العثور على أعضاء مخفيين!\n"
                "━━━━━━━━━━━━━━━━━━━━━\n"
                "💡 أسباب محتملة:\n"
                "• المجموعة ليس بها تفاعل كافٍ\n"
                "• تم سحب الأعضاء من قبل\n"
                "• المجموعة جديدة أو صغيرة\n"
                "━━━━━━━━━━━━━━━━━━━━━\n"
                "🔄 حاول مرة أخرى مع مجموعة أخرى.",
                parse_mode="Markdown"
            )
    except Exception as e:
        await status_msg.edit_text(
            f"❌ خطأ أثناء السحب!\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"الخطأ: `{str(e)[:200]}`\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"💡 تأكد من:\n"
            f"• صحة رابط المجموعة\n"
            f"• أن البوت عضو في المجموعة\n"
            f"• أن لديك صلاحيات الوصول",
            parse_mode="Markdown"
        )
    finally:
        await client.disconnect()
    
    return ConversationHandler.END


async def del_contacts_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """🚫 حذف جهات الاتصال - شرح الخدمة"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    accounts = db.get_user_accounts(user_id)
    
    if not accounts:
        keyboard = [
            [InlineKeyboardButton("➕ إضافة حساب جديد", callback_data='add_acc')],
            [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data='main_menu')]
        ]
        await query.edit_message_text(
            "📭 ملكش حسابات!\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "⚠️ لا يمكنك استخدام خدمة حذف جهات الاتصال\n"
            "لأنه ليس لديك أي حسابات مسجلة.\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "➕ اضغط على الزر أدناه لإضافة حساب:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        return
    
    status_msg = await query.edit_message_text(
        "🚫 جاري حذف جهات الاتصال\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"📱 عدد الحسابات: `{len(accounts)}`\n"
        "⏳ جاري حذف جهات الاتصال من كل حساب...\n"
        "⚠️ قد تستغرق العملية بضع ثوانٍ",
        parse_mode="Markdown"
    )
    
    deleted_total = 0
    results = []
    
    for acc in accounts:
        client = await get_client(acc)
        try:
            deleted = await clear_contacts_for_account(client)
            deleted_total += deleted
            results.append(f"📱 `{acc[0][-8:]}`: ✅ {deleted} جهة")
        except Exception as e:
            results.append(f"📱 `{acc[0][-8:]}`: ❌ فشل")
        finally:
            await client.disconnect()
    
    result_text = (
        f"✅ تم حذف جهات الاتصال!\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📱 إجمالي المحذوف: `{deleted_total}` جهة اتصال\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        + "\n".join(results)
    )
    
    await status_msg.edit_text(result_text, parse_mode="Markdown")


async def backup_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """📁 النسخ الاحتياطي - شرح الخدمة"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "💾 النسخ الاحتياطي\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "📌 شرح خدمه الزر:\n"
        "• تقوم بتحميل نسخة من قاعدة البيانات\n"
        "• تحتوي على جميع الأعضاء المخزنين\n"
        "• يمكنك استخدامها لاستعادة البيانات لاحقاً\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "📁 الملفات المتاحة:\n"
        "• قاعدة البيانات (SQLite)\n"
        "• ملف الأعضاء (JSON)\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "📤 جاري إرسال الملفات...",
        parse_mode="Markdown"
    )
    
    sent = 0
    if os.path.exists(DATABASE_PATH):
        await query.message.reply_document(
            open(DATABASE_PATH, 'rb'), 
            caption="📁 نسخة احتياطية - قاعدة البيانات\n`bot_v3_2.db`",
            parse_mode="Markdown"
        )
        sent += 1
        await asyncio.sleep(0.5)
    
    if os.path.exists(JSON_DATA_PATH):
        await query.message.reply_document(
            open(JSON_DATA_PATH, 'rb'), 
            caption="📁 نسخة احتياطية - بيانات الأعضاء\n`members_data.json`",
            parse_mode="Markdown"
        )
        sent += 1
    
    if sent == 0:
        await query.message.reply_text(
            "❌ لا توجد نسخ احتياطية!\n"
            "📭 لم يتم العثور على ملفات للنسخ الاحتياطي.",
            parse_mode="Markdown"
        )
    else:
        await query.message.reply_text(
            f"✅ تم إرسال {sent} ملف(ات) نسخ احتياطي",
            parse_mode="Markdown"
        )


async def upload_file_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """📤 رفع ملف أعضاء - شرح الخدمة"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "📤 رفع ملف أعضاء\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "📌 شرح خدمه الزر:\n"
        "• تقوم برفع ملف يحتوي على يوزرات الأعضاء\n"
        "• البوت يحفظ الأعضاء في قاعدة البيانات\n"
        "• يمكنك استخدامهم لاحقاً في عمليات النقل\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "📁 صيغ الملفات المدعومة:\n"
        "• `JSON` - ملف بصيغة JSON\n"
        "• `TXT` - ملف نصي (يوزر واحد لكل سطر)\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "📝 مثال ملف TXT:\n"
        "`@user1`\n`@user2`\n`user3`\n\n"
        "📝 مثال ملف JSON:\n"
        "`[{\"username\": \"user1\"}, {\"username\": \"user2\"}]`\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "📤 الخطوة التالية:\n"
        "• أرسل الملف الذي تريد رفعه\n"
        "• سيتم حفظ الأعضاء في قاعدة البيانات",
        parse_mode="Markdown"
    )
    return UPLOAD_FILE_DOC


async def del_file_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """🗑️ حذف ملف أعضاء - شرح الخدمة"""
    query = update.callback_query
    await query.answer()
    
    files = []
    for f in os.listdir(UPLOAD_DIR):
        if f.endswith(('.json', '.txt')):
            files.append(f)
    
    if not files:
        await query.edit_message_text(
            "📭 لا توجد ملفات أعضاء محفوظة!\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "💡 يمكنك رفع ملفات جديدة باستخدام:\n"
            "• زر '📤 رفع ملف أعضاء'",
            parse_mode="Markdown"
        )
        return
    
    keyboard = []
    for f in files:
        keyboard.append([InlineKeyboardButton(f"🗑️ {f}", callback_data=f"del_file_{f}")])
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")])
    
    await query.edit_message_text(
        "🗑️ حذف ملف أعضاء\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"📁 عدد الملفات المحفوظة: `{len(files)}`\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "📌 اختر الملف الذي تريد حذفه:\n"
        "⚠️ تحذير: لا يمكن استعادة الملف بعد الحذف",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )


async def confirm_del_file_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """🗑️ تأكيد حذف ملف"""
    query = update.callback_query
    filename = query.data.replace("del_file_", "")
    filepath = os.path.join(UPLOAD_DIR, filename)
    
    if os.path.exists(filepath):
        os.remove(filepath)
        await query.answer(f"✅ تم حذف {filename}")
        await query.edit_message_text(
            f"✅ تم حذف الملف بنجاح!\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"📁 الملف: `{filename}`\n"
            f"🗑️ تم حذفه نهائياً من الخادم",
            parse_mode="Markdown"
        )
    else:
        await query.answer("❌ الملف غير موجود")
        await query.edit_message_text(
            "❌ الملف غير موجود!\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "📁 ربما تم حذفه من قبل",
            parse_mode="Markdown"
        )
    
    await asyncio.sleep(2)
    await start(update, context)


async def extract_files_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """📑 استخراج الملفات - إرسال جميع ملفات الأعضاء"""
    query = update.callback_query
    
    # تأكد من أن الاستعلام صالح
    try:
        await query.answer()
    except:
        pass
    
    # جلب الملفات من مجلد uploads
    files = []
    if os.path.exists(UPLOAD_DIR):
        for f in os.listdir(UPLOAD_DIR):
            if f.endswith(('.json', '.txt')):
                files.append(f)
    
    if not files:
        try:
            await query.edit_message_text(
                "📭 لا توجد ملفات أعضاء محفوظة!\n\n"
                "💡 يمكنك رفع ملفات جديدة باستخدام:\n"
                "• زر '📤 رفع ملف أعضاء'"
            )
        except:
            await query.message.reply_text(
                "📭 لا توجد ملفات أعضاء محفوظة!\n\n"
                "💡 يمكنك رفع ملفات جديدة باستخدام:\n"
                "• زر '📤 رفع ملف أعضاء'"
            )
        return
    
    # رسالة تأكيد البداية
    try:
        await query.edit_message_text(
            f"📁 جاري إرسال {len(files)} ملف...\n"
            f"⏳ الرجاء الانتظار..."
        )
    except:
        await query.message.reply_text(
            f"📁 جاري إرسال {len(files)} ملف...\n"
            f"⏳ الرجاء الانتظار..."
        )
    
    sent = 0
    for f in files:
        filepath = os.path.join(UPLOAD_DIR, f)
        try:
            with open(filepath, 'rb') as file:
                await query.message.reply_document(
                    document=file,
                    caption=f"📄 ملف: {f}"
                )
            sent += 1
            await asyncio.sleep(0.5)
        except Exception as e:
            logger.error(f"خطأ في إرسال الملف {f}: {e}")
    
    await query.message.reply_text(f"✅ تم إرسال {sent} من {len(files)} ملف بنجاح")

async def add_contacts_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إضافة إلى جهات الاتصال"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    accounts = db.get_user_accounts(user_id)
    
    if not accounts:
        keyboard = [
            [InlineKeyboardButton("➕ إضافة حساب جديد", callback_data='add_acc')],
            [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data='main_menu')]
        ]
        await query.edit_message_text(
            "📭 ملكش حسابات!\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "⚠️ لا يمكنك استخدام خدمة إضافة جهات الاتصال\n"
            "لأنه ليس لديك أي حسابات مسجلة.\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "➕ اضغط على الزر أدناه لإضافة حساب:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        return
    
    await query.edit_message_text(
        "📞 إضافة إلى جهات الاتصال\n\n"
        "يرجى إرسال ملف TXT يحتوي على أرقام الهواتف (سطر واحد لكل رقم).\n\n"
        "مثال:\n"
        "`+201234567890`\n"
        "`+201234567891`\n\n"
        "سيتم إضافة هذه الأرقام كجهات اتصال في حساباتك.",
        parse_mode="Markdown"
    )
    return ADD_CONTACTS_SOURCE

async def upload_backup_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """رفع نسخة احتياطية"""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "📤 رفع نسخة احتياطية\n\n"
        "يرجى إرسال ملف النسخة الاحتياطية (JSON) لاستعادته.\n\n"
        "⚠️ تحذير: هذا سوف يستبدل قاعدة البيانات الحالية!",
        parse_mode="Markdown"
    )
    return UPLOAD_BACKUP

async def process_upload_backup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة رفع النسخة الاحتياطية"""
    if not update.message.document:
        await update.message.reply_text("❌ يرجى إرسال ملف صحيح.")
        return UPLOAD_BACKUP

    doc = update.message.document
    if not doc.file_name.endswith('.json'):
        await update.message.reply_text("❌ يرجى إرسال ملف JSON فقط.")
        return UPLOAD_BACKUP

    file_path = os.path.join(UPLOAD_DIR, f"backup_{int(time.time())}.json")
    file = await context.bot.get_file(doc.file_id)
    await file.download_to_drive(file_path)


    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            backup_data = json.load(f)


        with open(JSON_DATA_PATH, 'w', encoding='utf-8') as f:
            json.dump(backup_data, f, ensure_ascii=False, indent=4)

        await update.message.reply_text(f"✅ تم استعادة النسخة الاحتياطية بنجاح!\n📊 عدد السجلات: {len(backup_data)}")
    except Exception as e:
        await update.message.reply_text(f"❌ خطأ في استعادة البيانات: {e}")

    return ConversationHandler.END

async def check_accs_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    accounts = db.get_user_accounts(user_id)
    active, dead = 0, 0

    await query.edit_message_text(f"⏳ جاري فحص {len(accounts)} حساب...")

    for acc in accounts:
        client = await get_client(acc)
        try:
            if await client.is_user_authorized():
                active += 1
            else:
                dead += 1
        except:
            dead += 1
        finally:
            await client.disconnect()

    await query.edit_message_text(f"🔍 نتائج الفحص:\n✅ نشط: {active}\n❌ معطل: {dead}")

async def main_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await start(update, context)

async def check_accounts_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر يدوي لفحص جميع الحسابات"""
    user_id = update.effective_user.id

    if not is_admin(user_id):
        await update.message.reply_text("⚠️ هذا الأمر مخصص للأدمن فقط!")
        return

    status_msg = await update.message.reply_text("⏳ جاري فحص اشتراكات جميع الحسابات...")
    removed = await check_all_accounts_subscription()

    if removed > 0:
        await status_msg.edit_text(f"✅ تم فحص الحسابات.\n❌ تم حذف {removed} حساب因为他们 não مشتركين في القنوات الإجبارية.")
    else:
        await status_msg.edit_text("✅ تم فحص الحسابات.\n📭 جميع الحسابات مشتركة في القنوات الإجبارية.")




async def process_contacts_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة ملف جهات الاتصال"""
    if not update.message.document:
        return ADD_CONTACTS_SOURCE

    doc = update.message.document
    if not doc.file_name.endswith('.txt'):
        await update.message.reply_text("❌ يرجى إرسال ملف TXT.")
        return ADD_CONTACTS_SOURCE

    file_path = os.path.join(UPLOAD_DIR, f"contacts_{int(time.time())}.txt")
    file = await context.bot.get_file(doc.file_id)
    await file.download_to_drive(file_path)


    phones = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            phone = line.strip()
            if phone and phone.startswith('+'):
                phones.append(phone)

    if not phones:
        await update.message.reply_text("❌ لم يتم العثور على أرقام صالحة في الملف.")
        return ConversationHandler.END

    user_id = str(update.effective_user.id)
    accounts = db.get_user_accounts(user_id)

    if not accounts:
        await update.message.reply_text("📭 لا توجد حسابات لإضافة جهات الاتصال إليها.")
        return ConversationHandler.END

    status_msg = await update.message.reply_text(f"⏳ جاري إضافة {len(phones)} رقم إلى {len(accounts)} حساب...")

    total_added = 0
    for acc in accounts:
        client = await get_client(acc)
        try:
            contacts = []
            for phone in phones[:CONTACTS_PER_ACCOUNT]:
                contacts.append(InputPhoneContact(
                    client_id=random.randint(10000, 99999),
                    phone=phone,
                    first_name=f"Contact_{phone[-4:]}"
                ))

            if contacts:
                result = await client(ImportContactsRequest(contacts))
                total_added += len(result.users)
                await asyncio.sleep(CONTACT_ADD_DELAY)
        except Exception as e:
            logger.error(f"خطأ في إضافة جهات الاتصال للحساب {acc[0]}: {e}")
        finally:
            await client.disconnect()

    await status_msg.edit_text(f"✅ تم إضافة {total_added} جهة اتصال بنجاح.")
    return ConversationHandler.END

async def process_uploaded_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة ملف الأعضاء المرفوع"""
    if not update.message.document:
        return UPLOAD_FILE_DOC

    doc = update.message.document
    file_path = os.path.join(UPLOAD_DIR, doc.file_name)
    file = await context.bot.get_file(doc.file_id)
    await file.download_to_drive(file_path)


    members = []
    try:
        if file_path.endswith('.json'):
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for item in data:
                    if isinstance(item, dict) and 'username' in item:
                        username = item['username'].replace('@', '')
                        if username:
                            members.append((None, username, None, None, 'uploaded'))
        else:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    username = line.strip().replace('@', '')
                    if username:
                        members.append((None, username, None, None, 'uploaded'))

        if members:
            db.save_members(members)
            await update.message.reply_text(f"✅ تم رفع وحفظ {len(members)} عضو في قاعدة البيانات.")
        else:
            await update.message.reply_text("❌ الملف لا يحتوي على أعضاء صالحين.")

    except Exception as e:
        await update.message.reply_text(f"❌ خطأ في معالجة الملف: {e}")

    return ConversationHandler.END


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(msg="Exception while handling an update:", exc_info=context.error)

    if isinstance(context.error, Conflict):
        logger.warning("Conflict detected! Attempting to drop pending updates...")
        resolve_conflict(BOT_TOKEN)
    elif isinstance(context.error, NetworkError):
        logger.warning("Network error detected. Retrying...")
    elif isinstance(context.error, TelegramError):
        logger.error(f"Telegram error: {context.error}")


def main():
    resolve_conflict(BOT_TOKEN)

    application = Application.builder().token(BOT_TOKEN).build()


    async def start_periodic_check():
        await periodic_check()


    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    task = loop.create_task(periodic_check())

    application.add_error_handler(error_handler)


    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('start', start),
            CallbackQueryHandler(add_acc_callback, pattern='^add_acc$'),
            CallbackQueryHandler(import_session_callback, pattern='^import_session$'),
            CallbackQueryHandler(del_acc_callback, pattern='^del_acc$'),
            CallbackQueryHandler(list_accs_callback, pattern='^list_accs$'),
            CallbackQueryHandler(join_group_callback, pattern='^join_group$'),
            CallbackQueryHandler(leave_group_callback, pattern='^leave_group$'),
            CallbackQueryHandler(trans_hidden_callback, pattern='^trans_hidden$'),
            CallbackQueryHandler(trans_visible_callback, pattern='^trans_visible$'),
            CallbackQueryHandler(trans_file_callback, pattern='^trans_file$'),
            CallbackQueryHandler(store_hidden_callback, pattern='^store_hidden$'),
            CallbackQueryHandler(extract_api_callback, pattern='^extract_api$'),
            CallbackQueryHandler(extract_app_options_callback, pattern='^extract_'),
            CallbackQueryHandler(del_contacts_callback, pattern='^del_contacts$'),
            CallbackQueryHandler(backup_callback, pattern='^backup$'),
            CallbackQueryHandler(check_accs_callback, pattern='^check_accs$'),
            CallbackQueryHandler(main_menu_callback, pattern='^main_menu$'),
            CallbackQueryHandler(settings_callback, pattern='^section_settings$'),
            CallbackQueryHandler(handle_settings_callback, pattern='^set_'),
            CallbackQueryHandler(handle_settings_callback, pattern='^reset_all_settings$'),
            CallbackQueryHandler(handle_settings_callback, pattern='^view_all_settings$'),
            CallbackQueryHandler(view_del_callback, pattern='^view_del_'),
            CallbackQueryHandler(confirm_del_callback, pattern='^confirm_del_'),
            CallbackQueryHandler(stop_process_callback, pattern='^stop_process$'),
            CallbackQueryHandler(handle_admin_callback, pattern='^section_customize$'),
            CallbackQueryHandler(handle_admin_callback, pattern='^edit_welcome$'),
            CallbackQueryHandler(handle_admin_callback, pattern='^save_welcome$'),
            CallbackQueryHandler(handle_admin_callback, pattern='^preview_welcome$'),
            CallbackQueryHandler(handle_admin_callback, pattern='^reset_welcome$'),
            CallbackQueryHandler(admin_panel_callback, pattern='^admin_panel$'),
            CallbackQueryHandler(store_visible_callback, pattern='^store_visible$'),
            CallbackQueryHandler(upload_file_callback, pattern='^upload_file$'),
            CallbackQueryHandler(toggle_auto_switch_callback, pattern='^toggle_auto_switch$'),
            CallbackQueryHandler(del_file_callback, pattern='^del_file$'),
            CallbackQueryHandler(add_contacts_callback, pattern='^add_contacts$'),
            CallbackQueryHandler(check_subscription_callback, pattern='^check_subscription$'),
            CallbackQueryHandler(upload_backup_callback, pattern='^upload_backup$'),
            CallbackQueryHandler(confirm_del_file_callback, pattern='^del_file_'),
            CallbackQueryHandler(handle_admin_callback, pattern='^Dyler'),
            CallbackQueryHandler(handle_admin_callback, pattern='^delete11$'),
            CallbackQueryHandler(handle_admin_callback, pattern='^delete22$'),
            CallbackQueryHandler(handle_admin_callback, pattern='^sub[12]$'),
            CallbackQueryHandler(handle_admin_callback, pattern='^broadcast$'),
            CallbackQueryHandler(handle_admin_callback, pattern='^alert$'),
            CallbackQueryHandler(handle_admin_callback, pattern='^forward$'),
            CallbackQueryHandler(handle_admin_callback, pattern='^admin_sections$'),
            CallbackQueryHandler(handle_admin_callback, pattern='^section_subscription$'),
            CallbackQueryHandler(handle_admin_callback, pattern='^section_broadcast$'),
            CallbackQueryHandler(handle_admin_callback, pattern='^section_stats$'),
            CallbackQueryHandler(handle_admin_callback, pattern='^section_alerts$'),
            CallbackQueryHandler(handle_admin_callback, pattern='^section_forward$'),
            CallbackQueryHandler(handle_admin_callback, pattern='^section_users_management$'),
            CallbackQueryHandler(handle_admin_callback, pattern='^sub1_info$'),
            CallbackQueryHandler(handle_admin_callback, pattern='^sub2_info$'),
            CallbackQueryHandler(handle_admin_callback, pattern='^add_admin$'),
            CallbackQueryHandler(handle_admin_callback, pattern='^remove_admin$'),
            CallbackQueryHandler(handle_admin_callback, pattern='^remove_admin_'),
            CallbackQueryHandler(handle_admin_callback, pattern='^ban_user$'),
            CallbackQueryHandler(handle_admin_callback, pattern='^unban_user$'),
            CallbackQueryHandler(handle_admin_callback, pattern='^unban_'),
            CallbackQueryHandler(handle_admin_callback, pattern='^change_owner$'),
            CallbackQueryHandler(handle_admin_callback, pattern='^list_admins$'),
            CallbackQueryHandler(handle_admin_callback, pattern='^list_banned$'),
            CallbackQueryHandler(handle_admin_callback, pattern='^list_all_users$'),
            CallbackQueryHandler(handle_admin_callback, pattern='^broadcast_users$'),
            CallbackQueryHandler(handle_admin_callback, pattern='^broadcast_groups$'),
            CallbackQueryHandler(handle_admin_callback, pattern='^broadcast_channels$'),
            CallbackQueryHandler(handle_admin_callback, pattern='^refresh_stats$'),
            CallbackQueryHandler(handle_admin_callback, pattern='^noop$'),
            CallbackQueryHandler(copy_api_callback, pattern='^copy_api_id_'),
            CallbackQueryHandler(copy_api_callback, pattern='^copy_api_hash_'),
            CallbackQueryHandler(auto_add_account_callback, pattern='^auto_add_account_'),
        ],
        states={

            A_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, a_phone)],
            A_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, a_code)],

            TELETHON_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, telethon_code)],
            A_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, a_password)],


            EXTRACT_API_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, extract_api_phone)],
            EXTRACT_API_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, extract_api_code)],
            EXTRACT_API_APP_DETAILS: [
                CallbackQueryHandler(extract_app_options_callback, pattern='^extract_'),
                MessageHandler(filters.TEXT & ~filters.COMMAND, extract_api_app_details)
            ],


            UPLOAD_BACKUP: [
                MessageHandler(filters.Document.ALL, process_upload_backup)
            ],
            ADD_CONTACTS_SOURCE: [
                MessageHandler(filters.Document.ALL, process_contacts_file)
            ],
            UPLOAD_FILE_DOC: [
                MessageHandler(filters.Document.ALL, process_uploaded_members)
            ],
            JOIN_COUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, join_count)],
            JOIN_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, join_link)],
            LEAVE_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, leave_link)],
            TRANSFER_HIDDEN_SOURCE: [MessageHandler(filters.TEXT & ~filters.COMMAND, trans_hidden_source)],
            TRANSFER_HIDDEN_TARGET: [MessageHandler(filters.TEXT & ~filters.COMMAND, trans_hidden_target)],
            TRANSFER_VISIBLE_SOURCE: [MessageHandler(filters.TEXT & ~filters.COMMAND, trans_visible_source)],
            TRANSFER_VISIBLE_TARGET: [MessageHandler(filters.TEXT & ~filters.COMMAND, trans_visible_target)],
            TRANSFER_FILE_DOC: [MessageHandler(filters.Document.ALL, trans_file_doc)],
            TRANSFER_FILE_TARGET: [MessageHandler(filters.TEXT & ~filters.COMMAND, trans_file_target)],
            STORE_HIDDEN_SOURCE: [MessageHandler(filters.TEXT & ~filters.COMMAND, store_hidden_source)],
            STORE_VISIBLE_SOURCE: [MessageHandler(filters.TEXT & ~filters.COMMAND, store_visible_source)],
            IMPORT_SESSION_FILE: [MessageHandler(filters.Document.ALL, import_session_file)],
        },
        fallbacks=[CommandHandler('start', start)],
        allow_reentry=True
    )

    application.add_handler(conv_handler)
    application.add_handler(CommandHandler('admin', admin_command))
    application.add_handler(CommandHandler('checkaccounts', check_accounts_command))
    application.add_handler(CallbackQueryHandler(extract_files_callback, pattern='^extract_files$'))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_messages))
    application.add_handler(MessageHandler(filters.ALL, handle_new_user))
    application.add_handler(MessageHandler(filters.ALL & filters.ChatType.PRIVATE, start))

    print("✅ البوت يعمل الآن... « كارلو  مع لوحة الأدمن وإضافة الحساب التلقائية »")


    try:

        import threading
        def run_async_task():
            asyncio.run(periodic_check())

        thread = threading.Thread(target=run_async_task, daemon=True)
        thread.start()


        application.run_polling(drop_pending_updates=True)
    except KeyboardInterrupt:
        print("\n🛑 تم إيقاف البوت")
        sys.exit(0)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception as e:
        logger.critical(f"Fatal error: {e}")
        sys.exit(1)
