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
from telethon import TelegramClient, errors, functions, types
from telethon.tl.functions.channels import JoinChannelRequest, LeaveChannelRequest, InviteToChannelRequest, GetFullChannelRequest
from telethon.tl.functions.messages import GetHistoryRequest, GetDialogsRequest
from telethon.tl.functions.contacts import ImportContactsRequest, DeleteContactsRequest
from telethon.tl.types import InputPhoneContact, ChannelParticipantsRecent, ChannelParticipantsSearch
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, 
    MessageHandler, filters, ContextTypes, ConversationHandler
)
from telegram.error import Conflict, NetworkError, TelegramError

# --- الإعدادات ---
DEVELOPER_ID = 8405201865  # معرف المطور
DEVELOPER_USERNAME = "@ka_1lo"  # يوزر المطور
SESSIONS_DIR = "sessions"
DATABASE_PATH = "data/bot_v3_2.db"
JSON_DATA_PATH = "data/members_data.json"
UPLOAD_DIR = "uploads"
MAX_ACCOUNTS = 500
CONTACTS_PER_ACCOUNT = 120
ADD_DELAY = 12.0  # تأخير محسن للإضافة
CONTACT_ADD_DELAY = 1.5  # تأخير جهات الاتصال
SCRAPE_BATCH_SIZE = 50  # حجم الدفعة للسحب
MAX_MESSAGES_SCRAPE = 20000  # الحد الأقصى للرسائل المسحوبة

# التوكن الخاص بك
BOT_TOKEN = "8263138216:AAHOxcueT0rvJALqHHJD3CAMSqJPf4OCagM"

# متغير عالمي للتحكم في عملية السحب والإضافة
STOP_PROCESS = False

# إنشاء المجلدات
os.makedirs(SESSIONS_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)

# إعداد التسجيل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- وظيفة حل التعارض الجذري ---
def resolve_conflict(token):
    """حذف الويب هوك وإلغاء أي طلبات معلقة لإجبار التليجرام على قبول النسخة الجديدة"""
    try:
        url = f"https://api.telegram.org/bot{token}/deleteWebhook?drop_pending_updates=True"
        response = requests.get(url)
        if response.status_code == 200:
            logger.info("✅ تم تصفية كافة الجلسات المعلقة بنجاح.")
            return True
    except Exception as e:
        logger.error(f"❌ فشل في تصفية الجلسات: {e}")
    return False

# --- نظام JSON ---
def save_to_json(data, filename=JSON_DATA_PATH):
    """حفظ البيانات في ملف JSON تلقائياً"""
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

# --- قاعدة البيانات ---
class Database:
    def __init__(self, db_path):
        self.db_path = db_path
        self.init_db()

    def get_connection(self):
        return sqlite3.connect(self.db_path)

    def init_db(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('CREATE TABLE IF NOT EXISTS accounts (phone TEXT PRIMARY KEY, api_id INTEGER, api_hash TEXT, session_name TEXT)')
            cursor.execute('CREATE TABLE IF NOT EXISTS admins (user_id INTEGER PRIMARY KEY)')
            cursor.execute('CREATE TABLE IF NOT EXISTS members (user_id INTEGER PRIMARY KEY, username TEXT, access_hash TEXT, phone TEXT, type TEXT)')
            conn.commit()

    def add_account(self, phone, api_id, api_hash, session_name):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('INSERT OR REPLACE INTO accounts VALUES (?, ?, ?, ?)', (phone, api_id, api_hash, session_name))
            conn.commit()

    def get_accounts(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM accounts')
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

db = Database(DATABASE_PATH)

# --- حالات المحادثة ---
(
    A_PHONE, A_API_ID, A_API_HASH, A_CODE, A_PASSWORD,
    JOIN_COUNT, JOIN_LINK,
    LEAVE_LINK,
    TRANSFER_HIDDEN_SOURCE, TRANSFER_HIDDEN_TARGET,
    TRANSFER_VISIBLE_SOURCE, TRANSFER_VISIBLE_TARGET,
    TRANSFER_FILE_DOC, TRANSFER_FILE_TARGET,
    STORE_HIDDEN_SOURCE,
    UPLOAD_FILE_DOC,
    ADD_CONTACTS_SOURCE,
    IMPORT_SESSION_FILE
) = range(18)

# --- أجهزة المحاكاة ---
DEVICES = [
    {"model": "Samsung Galaxy S21", "sys": "Android 12"},
    {"model": "Infinix Note 12", "sys": "Android 11"},
    {"model": "iPhone 13 Pro", "sys": "iOS 15.4"},
    {"model": "Huawei P50 Pro", "sys": "Android 11"},
    {"model": "Redmi Note 11", "sys": "Android 11"}
]

# --- المساعدات ---
async def get_client(acc):
    """إنشاء عميل تيليجرام للحساب مع محاكاة جهاز عشوائي"""
    phone, api_id, api_hash, session_name = acc
    device = random.choice(DEVICES)
    client = TelegramClient(
        f"{SESSIONS_DIR}/{phone}", 
        api_id, 
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

def get_main_keyboard():
    """لوحة المفاتيح الرئيسية"""
    keyboard = [
        [InlineKeyboardButton("🆕 إضافة حساب جديد", callback_data='add_acc'), InlineKeyboardButton("🗑️ حذف حساب", callback_data='del_acc')],
        [InlineKeyboardButton("📥 استيراد جلسات (متعدد)", callback_data='import_session')],
        [InlineKeyboardButton("🔔 انضمام للقروب", callback_data='join_group'), InlineKeyboardButton("🛑 مغادرة قروب", callback_data='leave_group')],
        [InlineKeyboardButton("📋 حساباتك المسجلة", callback_data='list_accs')],
        [InlineKeyboardButton("👤 نقل أعضاء مخفيين", callback_data='trans_hidden'), InlineKeyboardButton("👥 نقل الأعضاء الظاهرين", callback_data='trans_visible')],
        [InlineKeyboardButton("📥 نقل من جهات الاتصال", callback_data='trans_contacts'), InlineKeyboardButton("📂 نقل أعضاء من الملفات", callback_data='trans_file')],
        [InlineKeyboardButton("☁️ تخزين مخفي", callback_data='store_hidden')],
        [InlineKeyboardButton("📄 رفع ملف أعضاء", callback_data='upload_file'), InlineKeyboardButton("🗑️ حذف ملف أعضاء", callback_data='del_file')],
        [InlineKeyboardButton("📑 استخراج ملفات أعضاء", callback_data='extract_files')],
        [InlineKeyboardButton("🚫 حذف جهات الاتصال", callback_data='del_contacts'), InlineKeyboardButton("➕ إضافة إلى جهات الاتصال", callback_data='add_contacts')],
        [InlineKeyboardButton("📤 رفع نسخة احتياطية", callback_data='upload_backup'), InlineKeyboardButton("📁 نسخة احتياطية", callback_data='backup')],
        [InlineKeyboardButton("🧨 حذف كل الحسابات", callback_data='del_all_accs')],
        [InlineKeyboardButton("🔍 فحص الحسابات", callback_data='check_accs')]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_stop_keyboard():
    """زر إيقاف العملية"""
    return InlineKeyboardMarkup([[InlineKeyboardButton("🛑 إيقاف العملية", callback_data='stop_process')]])

# --- الأوامر ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر البداية - تم إصلاح خطأ التنسيق لضمان الرد"""
    user = update.effective_user
    if not user: return
    
    # تم إزالة علامات الاقتباس الخاصة بـ Markdown لتجنب خطأ BadRequest
    text = (
        f"أهلاً بك {user.first_name} في بوت السحب النسخة المحسّنة من سورس مارو\n\n"
        f"المطور | {DEVELOPER_USERNAME}"
    )
    
    try:
        if update.message:
            await update.message.reply_text(text, reply_markup=get_main_keyboard())
        elif update.callback_query:
            await update.callback_query.edit_message_text(text, reply_markup=get_main_keyboard())
    except Exception as e:
        logger.error(f"خطأ في إرسال رسالة البداية: {e}")
        # محاولة إرسال رسالة بسيطة جداً في حال فشل التنسيق
        if update.message:
            await update.message.reply_text("أهلاً بك في البوت!", reply_markup=get_main_keyboard())
            
    return ConversationHandler.END

# --- إيقاف العملية ---
async def stop_process_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global STOP_PROCESS
    STOP_PROCESS = True
    await update.callback_query.answer("⚠️ تم إرسال طلب الإيقاف، سيتم التوقف قريباً...")

# --- إضافة حساب ---
async def add_acc_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بدء إضافة حساب جديد"""
    query = update.callback_query
    await query.answer()
    if db.get_account_count() >= MAX_ACCOUNTS:
        await query.edit_message_text("⚠️ وصلت للحد الأقصى من الحسابات (500).")
        return ConversationHandler.END
    await query.edit_message_text("📱 يرجى إرسال رقم الهاتف (مع رمز الدولة، مثال: +218910000000):")
    return A_PHONE

async def a_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """استلام رقم الهاتف"""
    context.user_data['phone'] = update.message.text.strip().replace(" ", "")
    await update.message.reply_text("🔑 أرسل API ID:")
    return A_API_ID

async def a_api_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """استلام API ID"""
    context.user_data['api_id'] = update.message.text.strip()
    await update.message.reply_text("🔐 أرسل API HASH:")
    return A_API_HASH

async def a_api_hash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """استلام API HASH وإرسال رمز التحقق"""
    context.user_data['api_hash'] = update.message.text.strip()
    phone = context.user_data['phone']
    api_id = int(context.user_data['api_id'])
    api_hash = context.user_data['api_hash']
    
    device = random.choice(DEVICES)
    client = TelegramClient(
        f"{SESSIONS_DIR}/{phone}", 
        api_id, 
        api_hash, 
        device_model=device["model"], 
        system_version=device["sys"]
    )
    await client.connect()
    context.user_data['client'] = client
    
    try:
        if not await client.is_user_authorized():
            await client.send_code_request(phone)
            await update.message.reply_text("📩 أرسل رمز التحقق الذي وصلك:")
            return A_CODE
        else:
            db.add_account(phone, api_id, api_hash, phone)
            await update.message.reply_text(f"✅ الحساب {phone} مسجل بالفعل وجاهز!")
            await client.disconnect()
            return ConversationHandler.END
    except Exception as e:
        await update.message.reply_text(f"❌ خطأ: {e}")
        await client.disconnect()
        return ConversationHandler.END

async def a_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """استلام رمز التحقق"""
    code = update.message.text.strip()
    client = context.user_data['client']
    phone = context.user_data['phone']
    api_id = int(context.user_data['api_id'])
    api_hash = context.user_data['api_hash']
    
    try:
        await client.sign_in(phone, code)
        db.add_account(phone, api_id, api_hash, phone)
        await update.message.reply_text(f"✅ تم إضافة الحساب {phone} بنجاح!")
        await client.disconnect()
        return ConversationHandler.END
    except errors.SessionPasswordNeededError:
        await update.message.reply_text("🔐 الحساب محمي بكلمة سر، أرسلها:")
        return A_PASSWORD
    except Exception as e:
        await update.message.reply_text(f"❌ خطأ: {e}")
        await client.disconnect()
        return ConversationHandler.END

async def a_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """استلام كلمة السر"""
    password = update.message.text.strip()
    client = context.user_data['client']
    phone = context.user_data['phone']
    api_id = int(context.user_data['api_id'])
    api_hash = context.user_data['api_hash']
    
    try:
        await client.sign_in(password=password)
        db.add_account(phone, api_id, api_hash, phone)
        await update.message.reply_text(f"✅ تم إضافة الحساب {phone} بنجاح!")
        await client.disconnect()
        return ConversationHandler.END
    except Exception as e:
        await update.message.reply_text(f"❌ خطأ: {e}")
        await client.disconnect()
        return ConversationHandler.END

# --- استيراد جلسة ---
async def import_session_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بدء استيراد الجلسات"""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("📥 يرجى إرسال ملفات الجلسات (.session) دفعة واحدة أو واحداً تلو الآخر.\n\nيمكنك كتابة API_ID|API_HASH في وصف الملف لاستخدامها.")
    return IMPORT_SESSION_FILE

async def import_session_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة ملفات الجلسات المرسلة (يدعم التعدد)"""
    if not update.message.document:
        return IMPORT_SESSION_FILE
    
    doc = update.message.document
    file_name = doc.file_name
    
    if not file_name.endswith('.session'):
        await update.message.reply_text(f"❌ الملف {file_name} ليس ملف جلسة.")
        return IMPORT_SESSION_FILE
    
    phone = file_name.replace('.session', '').strip()
    
    # API افتراضي
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
            pass
    
    status_msg = await update.message.reply_text(f"⏳ جاري معالجة {file_name}...")
    
    try:
        file = await context.bot.get_file(doc.file_id)
        await file.download_to_drive(f"{SESSIONS_DIR}/{phone}.session")
        
        # التحقق من الجلسة مع محاكاة جهاز
        device = random.choice(DEVICES)
        client = TelegramClient(f"{SESSIONS_DIR}/{phone}", api_id, api_hash, device_model=device["model"], system_version=device["sys"])
        await client.connect()
        
        if await client.is_user_authorized():
            db.add_account(phone, api_id, api_hash, phone)
            await status_msg.edit_text(f"✅ تم استيراد الحساب {phone} بنجاح!")
        else:
            await status_msg.edit_text(f"❌ الجلسة {phone} غير صالحة أو منتهية.")
            if os.path.exists(f"{SESSIONS_DIR}/{phone}.session"):
                os.remove(f"{SESSIONS_DIR}/{phone}.session")
        await client.disconnect()
    except Exception as e:
        await status_msg.edit_text(f"❌ خطأ في {file_name}: {e}")
    
    return IMPORT_SESSION_FILE

# --- حذف حساب ---
async def del_acc_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض قائمة الحسابات للحذف"""
    query = update.callback_query
    await query.answer()
    accounts = db.get_accounts()
    
    if not accounts:
        await query.edit_message_text("📭 لا توجد حسابات مسجلة.")
        return
    
    keyboard = []
    for acc in accounts:
        keyboard.append([InlineKeyboardButton(f"📱 {acc[0]}", callback_data=f"view_del_{acc[0]}")])
    keyboard.append([InlineKeyboardButton("🔙 عودة", callback_data='main_menu')])
    await query.edit_message_text("🗑️ اختر الحساب المراد حذفه:", reply_markup=InlineKeyboardMarkup(keyboard))

async def view_del_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تأكيد حذف الحساب"""
    query = update.callback_query
    phone = query.data.replace("view_del_", "")
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("❌ نعم، قم بالحذف", callback_data=f"confirm_del_{phone}")],
        [InlineKeyboardButton("🔙 إلغاء", callback_data='del_acc')]
    ]
    await query.edit_message_text(f"⚠️ هل أنت متأكد من حذف الحساب {phone}؟", reply_markup=InlineKeyboardMarkup(keyboard))

async def confirm_del_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تنفيذ حذف الحساب"""
    query = update.callback_query
    phone = query.data.replace("confirm_del_", "")
    
    db.remove_account(phone)
    session_file = f"{SESSIONS_DIR}/{phone}.session"
    if os.path.exists(session_file):
        os.remove(session_file)
    
    await query.answer(f"تم حذف {phone}")
    await query.edit_message_text(f"✅ تم حذف الحساب {phone} بنجاح.")
    await asyncio.sleep(1)
    await start(update, context)

# --- عرض الحسابات ---
async def list_accs_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض قائمة الحسابات المسجلة"""
    query = update.callback_query
    await query.answer()
    accounts = db.get_accounts()
    
    if not accounts:
        await query.edit_message_text("📭 لا توجد حسابات مسجلة.")
        return
    
    acc_list = "\n".join([f"📱 {acc[0]}" for acc in accounts])
    text = f"📋 قائمة الحسابات المسجلة ({len(accounts)}):\n\n{acc_list}"
    keyboard = [[InlineKeyboardButton("🔙 عودة", callback_data='main_menu')]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

# --- انضمام للقروب ---
async def join_group_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بدء عملية الانضمام للمجموعة"""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("🔢 أرسل عدد الحسابات المراد إدخالها للمجموعة:")
    return JOIN_COUNT

async def join_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """استلام عدد الحسابات"""
    try:
        count = int(update.message.text)
        context.user_data['join_count'] = count
        await update.message.reply_text("🔗 أرسل رابط المجموعة (أو الرابط الخاص):")
        return JOIN_LINK
    except:
        await update.message.reply_text("❌ يرجى إرسال رقم صحيح.")
        return JOIN_COUNT

async def join_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تنفيذ الانضمام"""
    link = update.message.text.strip()
    count = context.user_data['join_count']
    accounts = db.get_accounts()[:count]
    
    msg = await update.message.reply_text(f"⏳ جاري محاولة انضمام {len(accounts)} حساب...")
    success, failed = 0, 0
    
    for acc in accounts:
        client = await get_client(acc)
        try:
            if 'joinchat' in link or '+' in link:
                hash_link = link.split('/')[-1].replace('+', '')
                await client(functions.messages.ImportChatInviteRequest(hash_link))
            else:
                await client(JoinChannelRequest(link))
            success += 1
        except:
            failed += 1
        finally:
            await client.disconnect()
        await asyncio.sleep(1)
    
    result_text = (
        f"نتائج ميزة الانضمام مارو\n"
        f"••••••••••••••••••••••••••••\n"
        f"✅ عدد الحسابات التي انضمت: {success}\n"
        f"❌ عدد الحسابات التي لم تنضم: {failed}\n"
        f"••••••••••••••••••••••••••••"
    )
    await msg.edit_text(result_text)
    return ConversationHandler.END

# --- مغادرة قروب ---
async def leave_group_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بدء عملية مغادرة المجموعة"""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("🔗 أرسل رابط القروب المراد مغادرته بجميع الحسابات:")
    return LEAVE_LINK

async def leave_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تنفيذ مغادرة المجموعة"""
    link = update.message.text.strip()
    accounts = db.get_accounts()
    
    msg = await update.message.reply_text(f"⏳ جاري مغادرة {len(accounts)} حساب من المجموعة...")
    success_count = 0
    
    for acc in accounts:
        client = await get_client(acc)
        try:
            await client(LeaveChannelRequest(link))
            success_count += 1
        except:
            pass
        finally:
            await client.disconnect()
    
    await msg.edit_text(f"✅ تمت عملية المغادرة بنجاح من {success_count} حساب.")
    return ConversationHandler.END

# --- وظيفة الإضافة المحسنة ---
async def process_adding(update, status_msg, members, target, accounts):
    """وظيفة إضافة محسنة مع زر إيقاف وحساب دقيق"""
    global STOP_PROCESS
    STOP_PROCESS = False
    
    added_count = 0
    failed_count = 0
    member_index = 0
    total_members = len(members)
    failed_accounts = []
    
    members_per_account = max(10, min(20, total_members // len(accounts) + 1))
    
    for acc_index, acc in enumerate(accounts):
        if member_index >= total_members or STOP_PROCESS:
            break
            
        client = await get_client(acc)
        account_added = 0
        
        try:
            # الانضمام للمجموعة أولاً
            try:
                if 'joinchat' in target or '+' in target:
                    hash_link = target.split('/')[-1].replace('+', '')
                    await client(functions.messages.ImportChatInviteRequest(hash_link))
                else:
                    await client(JoinChannelRequest(target))
                await asyncio.sleep(2)
            except errors.UserAlreadyParticipantError:
                pass
            except Exception as e:
                logger.warning(f"خطأ انضمام للحساب {acc[0]}: {e}")
            
            try:
                target_entity = await client.get_entity(target)
            except Exception as e:
                logger.error(f"لا يمكن الوصول للمجموعة الهدف {target}: {e}")
                await client.disconnect()
                continue
            
            # إضافة الأعضاء
            for _ in range(members_per_account):
                if member_index >= total_members or STOP_PROCESS:
                    break
                    
                member = members[member_index]
                member_index += 1
                
                try:
                    username = member[1]
                    if username:
                        await client(InviteToChannelRequest(target_entity, [username]))
                        added_count += 1
                        account_added += 1
                        
                        if added_count % 2 == 0:
                            progress = (member_index / total_members) * 100
                            await status_msg.edit_text(
                                f"⏳ جاري الإضافة...\n"
                                f"✅ تم إضافة: {added_count}\n"
                                f"❌ فشل الإضافة: {failed_count}\n"
                                f"📊 التقدم: {progress:.1f}%\n"
                                f"📱 الحساب: {acc_index + 1}/{len(accounts)}",
                                reply_markup=get_stop_keyboard()
                            )
                        
                        delay = ADD_DELAY + random.uniform(2, 6)
                        await asyncio.sleep(delay)
                        
                except errors.PeerFloodError:
                    logger.warning(f"خطأ Flood للحساب {acc[0]}")
                    failed_accounts.append(acc[0])
                    failed_count += 1
                    break
                except (errors.UserPrivacyRestrictedError, errors.UserNotMutualContactError, errors.UserChannelsTooMuchError):
                    failed_count += 1
                    continue
                except errors.ChatWriteForbiddenError:
                    failed_count += 1
                    break
                except Exception as e:
                    logger.error(f"خطأ إضافة {member[1]}: {e}")
                    failed_count += 1
                    continue
            
            await clear_contacts_for_account(client)
            
        except Exception as e:
            logger.error(f"خطأ الحساب {acc[0]}: {e}")
        finally:
            await client.disconnect()
            
        if acc_index < len(accounts) - 1 and not STOP_PROCESS:
            await asyncio.sleep(3)
    
    if STOP_PROCESS:
        await status_msg.edit_text(f"🛑 تم إيقاف العملية يدوياً.\n✅ المضافين حتى الآن: {added_count}")
        STOP_PROCESS = False # إعادة التعيين
        
    return added_count, failed_count, failed_accounts

# --- سحب الأعضاء المخفيين ---
async def scrape_hidden_members(client, entity, status_msg, max_messages=20000):
    """سحب الأعضاء المخفيين من آخر 20000 رسالة مع زر إيقاف"""
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

# --- نقل الأعضاء المخفيين ---
async def trans_hidden_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بدء نقل الأعضاء المخفيين"""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("🔗 أرسل رابط المجموعة (المصدر) لسحب المخفيين:")
    return TRANSFER_HIDDEN_SOURCE

async def trans_hidden_source(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """استلام رابط المصدر"""
    context.user_data['source'] = update.message.text.strip()
    await update.message.reply_text("🎯 أرسل رابط المجموعة (الهدف) للإضافة إليها:")
    return TRANSFER_HIDDEN_TARGET

async def trans_hidden_target(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تنفيذ نقل الأعضاء المخفيين"""
    target = update.message.text.strip()
    source = context.user_data['source']
    accounts = db.get_accounts()
    
    if not accounts:
        await update.message.reply_text("📭 لا توجد حسابات!")
        return ConversationHandler.END
    
    status_msg = await update.message.reply_text("⏳ جاري سحب الأعضاء المخفيين من آخر 20,000 رسالة...", reply_markup=get_stop_keyboard())
    db.clear_members('hidden')
    
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
        users_to_save = await scrape_hidden_members(client, entity, status_msg, MAX_MESSAGES_SCRAPE)
        
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

    await status_msg.edit_text(f"✅ تم سحب {scraped_count} عضو.\n⏳ جاري البدء في الإضافة...", reply_markup=get_stop_keyboard())
    members = db.get_members_by_type('hidden')
    added_count, failed_count, failed_accounts = await process_adding(update, status_msg, members, target, accounts)

    success_rate = (added_count / scraped_count * 100) if scraped_count > 0 else 0
    result_text = (
        f"نتائج ميزة نقل المخفيين مارو\n"
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

# --- نقل الأعضاء الظاهرين ---
async def trans_visible_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بدء نقل الأعضاء الظاهرين"""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("🔗 أرسل رابط المجموعة (المصدر) لسحب الظاهرين:")
    return TRANSFER_VISIBLE_SOURCE

async def trans_visible_source(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """استلام رابط المصدر"""
    context.user_data['source'] = update.message.text.strip()
    await update.message.reply_text("🎯 أرسل رابط المجموعة (الهدف) للإضافة إليها:")
    return TRANSFER_VISIBLE_TARGET

async def trans_visible_target(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تنفيذ نقل الأعضاء الظاهرين"""
    target = update.message.text.strip()
    source = context.user_data['source']
    accounts = db.get_accounts()
    
    if not accounts:
        await update.message.reply_text("📭 لا توجد حسابات!")
        return ConversationHandler.END
        
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
    added_count, failed_count, failed_accounts = await process_adding(update, status_msg, members, target, accounts)

    success_rate = (added_count / scraped_count * 100) if scraped_count > 0 else 0
    result_text = (
        f"نتائج ميزة نقل الظاهرين مارو\n"
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

# --- نقل من الملفات ---
async def trans_file_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بدء نقل الأعضاء من ملف"""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("📄 يرجى إرسال ملف JSON أو TXT يحتوي على يوزرات الأعضاء:")
    return TRANSFER_FILE_DOC

async def trans_file_doc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """استلام ملف الأعضاء"""
    if not update.message.document:
        await update.message.reply_text("❌ يرجى إرسال ملف صحيح.")
        return TRANSFER_FILE_DOC
    
    doc = update.message.document
    file_path = f"{UPLOAD_DIR}/{doc.file_name}"
    file = await context.bot.get_file(doc.file_id)
    await file.download_to_drive(file_path)
    
    context.user_data['members_file'] = file_path
    await update.message.reply_text("🎯 أرسل رابط المجموعة الهدف للإضافة إليها:")
    return TRANSFER_FILE_TARGET

async def trans_file_target(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تنفيذ النقل من الملف"""
    target = update.message.text.strip()
    file_path = context.user_data['members_file']
    accounts = db.get_accounts()
    
    if not accounts:
        await update.message.reply_text("📭 لا توجد حسابات!")
        return ConversationHandler.END
    
    status_msg = await update.message.reply_text("⏳ جاري قراءة الملف وتحضير الأعضاء...")
    members = []
    
    try:
        if file_path.endswith('.json'):
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for item in data:
                    if isinstance(item, dict) and 'username' in item:
                        members.append((None, item['username'], None, None, 'file'))
                    elif isinstance(item, str):
                        members.append((None, item.replace('@', ''), None, None, 'file'))
        else:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    user = line.strip().replace('@', '')
                    if user:
                        members.append((None, user, None, None, 'file'))
        
        if not members:
            await status_msg.edit_text("📭 الملف فارغ أو بتنسيق غير مدعوم.")
            return ConversationHandler.END
            
        await status_msg.edit_text(f"✅ تم تحميل {len(members)} عضو من الملف.\n⏳ جاري البدء في الإضافة...", reply_markup=get_stop_keyboard())
        added_count, failed_count, failed_accounts = await process_adding(update, status_msg, members, target, accounts)
        
        await status_msg.edit_text(f"✅ اكتمل النقل من الملف.\nتم إضافة: {added_count}\nفشل: {failed_count}")
    except Exception as e:
        await status_msg.edit_text(f"❌ خطأ في معالجة الملف: {e}")
    
    return ConversationHandler.END

# --- تخزين مخفي ---
async def store_hidden_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بدء تخزين الأعضاء المخفيين"""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("🔗 أرسل رابط المجموعة المصدر لتخزين أعضائها المخفيين:")
    return STORE_HIDDEN_SOURCE

async def store_hidden_source(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تنفيذ تخزين الأعضاء المخفيين"""
    source = update.message.text.strip()
    accounts = db.get_accounts()
    
    if not accounts:
        await update.message.reply_text("📭 لا توجد حسابات!")
        return ConversationHandler.END
    
    status_msg = await update.message.reply_text("⏳ جاري سحب وتخزين الأعضاء المخفيين من آخر 20,000 رسالة...", reply_markup=get_stop_keyboard())
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
        users_to_save = await scrape_hidden_members(client, entity, status_msg, MAX_MESSAGES_SCRAPE)
        
        if users_to_save:
            db.save_members(users_to_save)
            await status_msg.edit_text(f"✅ تم تخزين {len(users_to_save)} عضو مخفي في قاعدة البيانات وملف JSON.")
        else:
            await status_msg.edit_text("📭 لم يتم العثور على أعضاء.")
    except Exception as e:
        await status_msg.edit_text(f"❌ خطأ: {e}")
    finally:
        await client.disconnect()
    
    return ConversationHandler.END

async def del_contacts_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """حذف جهات الاتصال من جميع الحسابات"""
    query = update.callback_query
    await query.answer()
    
    status_msg = await query.edit_message_text("⏳ جاري حذف جهات الاتصال من جميع الحسابات...")
    accounts = db.get_accounts()
    deleted_total = 0
    
    for acc in accounts:
        client = await get_client(acc)
        deleted_total += await clear_contacts_for_account(client)
        await client.disconnect()
    
    await status_msg.edit_text(f"✅ تم حذف {deleted_total} جهة اتصال بنجاح.")

async def backup_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إنشاء نسخة احتياطية"""
    query = update.callback_query
    await query.answer()
    
    if os.path.exists(DATABASE_PATH):
        await query.message.reply_document(open(DATABASE_PATH, 'rb'), caption="📁 نسخة احتياطية لقاعدة البيانات.")
    if os.path.exists(JSON_DATA_PATH):
        await query.message.reply_document(open(JSON_DATA_PATH, 'rb'), caption="📁 نسخة احتياطية لبيانات الأعضاء (JSON).")

async def check_accs_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """فحص حالة الحسابات"""
    query = update.callback_query
    await query.answer()
    accounts = db.get_accounts()
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
    """العودة للقائمة الرئيسية"""
    query = update.callback_query
    await query.answer()
    await start(update, context)

# --- معالج الأخطاء ---
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """معالجة الأخطاء لضمان استمرار عمل البوت"""
    logger.error(msg="Exception while handling an update:", exc_info=context.error)
    
    if isinstance(context.error, Conflict):
        logger.warning("Conflict detected! Attempting to drop pending updates...")
        resolve_conflict(BOT_TOKEN)
    elif isinstance(context.error, NetworkError):
        logger.warning("Network error detected. Retrying...")
    elif isinstance(context.error, TelegramError):
        logger.error(f"Telegram error: {context.error}")

# --- تشغيل البوت ---
def main():
    # تصفية الجلسات قبل البدء
    resolve_conflict(BOT_TOKEN)
    
    # بناء التطبيق
    application = Application.builder().token(BOT_TOKEN).build()
    
    # إضافة معالج الأخطاء
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
            CallbackQueryHandler(del_contacts_callback, pattern='^del_contacts$'),
            CallbackQueryHandler(backup_callback, pattern='^backup$'),
            CallbackQueryHandler(check_accs_callback, pattern='^check_accs$'),
            CallbackQueryHandler(main_menu_callback, pattern='^main_menu$'),
            CallbackQueryHandler(view_del_callback, pattern='^view_del_'),
            CallbackQueryHandler(confirm_del_callback, pattern='^confirm_del_'),
            CallbackQueryHandler(stop_process_callback, pattern='^stop_process$'),
        ],
        states={
            A_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, a_phone)],
            A_API_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, a_api_id)],
            A_API_HASH: [MessageHandler(filters.TEXT & ~filters.COMMAND, a_api_hash)],
            A_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, a_code)],
            A_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, a_password)],
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
            IMPORT_SESSION_FILE: [MessageHandler(filters.Document.ALL, import_session_file)],
        },
        fallbacks=[CommandHandler('start', start)],
        allow_reentry=True
    )
    
    application.add_handler(conv_handler)
    
    # معالج عام لضمان الرد على أي رسالة في الخاص
    application.add_handler(MessageHandler(filters.ALL & filters.ChatType.PRIVATE, start))
    
    print("البوت يعمل الآن... « مارو »")
    
    # تشغيل البوت مع حذف التحديثات المعلقة
    application.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception as e:
        logger.critical(f"Fatal error: {e}")
        sys.exit(1)
