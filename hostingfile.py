# -*- coding: utf-8 -*-
import telebot
import subprocess
import os
import sys

os.environ["PYTHONIOENCODING"] = "utf-8"

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except:
    pass
    
import zipfile
import tempfile
import shutil
from telebot import types
import time
from datetime import datetime, timedelta
import psutil
import sqlite3
import json
import logging
import signal
import threading
import re
import atexit
import requests
import hashlib
import mimetypes
import struct

# --- Flask Keep Alive ---
from flask import Flask
from threading import Thread

app = Flask('')

@app.route('/')
def home():
    return "bot is running...."

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_flask)
    t.daemon = True
    t.start()
    print("Flask Keep-Alive server started.")
# --- End Flask Keep Alive ---

# --- Configuration ---
TOKEN = os.environ.get("BOT_TOKEN", )
OWNER_ID = int(os.environ.get("OWNER_ID", 7769604048))
ADMIN_ID = int(os.environ.get("ADMIN_ID", 7769604048))
YOUR_USERNAME = os.environ.get("YOUR_USERNAME", '@zyrex_14_18')
UPDATE_CHANNEL = os.environ.get("UPDATE_CHANNEL", 'https://t.me/Elite_404OP')

# 🔐 PASSWORD SYSTEM CONFIGURATION
BOT_ACCESS_PASSWORD = os.environ.get("BOT_PASSWORD", "180310")
PASSWORD_REQUIRED = True  # Set to False to disable password requirement

# ⚡ AUTO-APPROVE MODE (Dynamic - can be toggled from bot)
# This is the DEFAULT value used only on first startup.
# Actual runtime value is loaded from DB and can be toggled via bot.
AUTO_APPROVE_DEFAULT = True
auto_approve_enabled = AUTO_APPROVE_DEFAULT  # Runtime variable

# Folder setup - using absolute paths
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATA_DIR = os.environ.get("RAILWAY_VOLUME_MOUNT_PATH", BASE_DIR)
UPLOAD_BOTS_DIR = os.path.join(DATA_DIR, 'upload_bots')
IROTECH_DIR = os.path.join(DATA_DIR, 'inf')
DATABASE_PATH = os.path.join(IROTECH_DIR, 'bot_data.db')

# File upload limits
FREE_USER_LIMIT = 10
SUBSCRIBED_USER_LIMIT = 350
ADMIN_LIMIT = 500
OWNER_LIMIT = float('inf')

# Create necessary directories
os.makedirs(UPLOAD_BOTS_DIR, exist_ok=True)
os.makedirs(IROTECH_DIR, exist_ok=True)

# Initialize bot
bot = telebot.TeleBot(TOKEN)

# --- Data structures ---
bot_scripts = {}
user_subscriptions = {}
user_files = {}
active_users = set()
admin_ids = {ADMIN_ID, OWNER_ID}
bot_locked = False
file_db = {}

# 👉 PASSWORD SYSTEM DATA
authenticated_users = set()
pending_auth_users = {}
banned_users = set()
banned_usernames = set()

# --- FILE APPROVAL SYSTEM ---
pending_files = {}
pending_file_counter = 0

# --- Malware Detection Configuration ---
MALWARE_SIGNATURES = [
    b'MZ', b'\x7fELF', b'\xfe\xed\xfa', b'\xce\xfa\xed\xfe', b'PK', b'Rar!',
]

ENCRYPTED_FILE_INDICATORS = [
    b'openssl', b'encrypted', b'cipher', b'DES', b'RSA', b'GPG', b'PGP',
]

SUSPICIOUS_KEYWORDS = [
    b'ransomware', b'trojan', b'virus', b'malware', b'backdoor', b'exploit',
    b'payload', b'botnet', b'keylogger', b'rootkit',
]

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Cool UI Constants ---
DIVIDER = "━━━━━━━━━━━━━━━━━━━━━━━━━━━"
DIVIDER_THIN = "┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄"
EMOJI_HEADER = "╔══════════════════════════╗"
EMOJI_FOOTER = "╚══════════════════════════╝"

# --- Command Button Layouts ---
COMMAND_BUTTONS_LAYOUT_USER_SPEC = [
    ["📢 Updates Channel"],
    ["📤 Upload File", "📂 Check Files"],
    ["⚡ Bot Speed", "📊 Statistics"],
    ["📤 Send Command", "📞 Contact Owner"]
]

ADMIN_COMMAND_BUTTONS_LAYOUT_USER_SPEC = [
    ["📢 Updates Channel"],
    ["📤 Upload File", "📂 Check Files"],
    ["⚡ Bot Speed", "📊 Statistics"],
    ["💳 Subscriptions", "📢 Broadcast"],
    ["🔒 Lock Bot", "🟢 Running All Code"],
    ["📤 Send Command", "👑 Admin Panel"],
    ["📞 Contact Owner"],
    ["📥 Pending Approvals"],
    ["🔐 Auth Requests", "⚙️ Auto-Approve"]
]

# --- Database Setup ---
DB_LOCK = threading.Lock()

def init_db():
    logger.info(f"Initializing database at: {DATABASE_PATH}")
    try:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS subscriptions
                     (user_id INTEGER PRIMARY KEY, expiry TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS user_files
                     (user_id INTEGER, file_name TEXT, file_type TEXT,
                      PRIMARY KEY (user_id, file_name))''')
        c.execute('''CREATE TABLE IF NOT EXISTS active_users
                     (user_id INTEGER PRIMARY KEY)''')
        c.execute('''CREATE TABLE IF NOT EXISTS admins
                     (user_id INTEGER PRIMARY KEY)''')
        c.execute('''CREATE TABLE IF NOT EXISTS pending_files
                     (file_id INTEGER PRIMARY KEY AUTOINCREMENT,
                      user_id INTEGER,
                      file_name TEXT,
                      file_path TEXT,
                      file_type TEXT,
                      timestamp TEXT,
                      message_id INTEGER,
                      status TEXT DEFAULT 'pending')''')
        c.execute('''CREATE TABLE IF NOT EXISTS authenticated_users
                     (user_id INTEGER PRIMARY KEY,
                      authenticated_at TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS bot_settings
                     (key TEXT PRIMARY KEY,
                      value TEXT)''')
        c.execute('INSERT OR IGNORE INTO admins (user_id) VALUES (?)', (OWNER_ID,))
        if ADMIN_ID != OWNER_ID:
            c.execute('INSERT OR IGNORE INTO admins (user_id) VALUES (?)', (ADMIN_ID,))
        conn.commit()
        conn.close()
        logger.info("Database initialized successfully.")
    except Exception as e:
        logger.error(f"❌ Database initialization error: {e}", exc_info=True)

def load_data():
    logger.info("Loading data from database...")
    global authenticated_users
    try:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()

        c.execute('SELECT user_id, expiry FROM subscriptions')
        for user_id, expiry in c.fetchall():
            try:
                user_subscriptions[user_id] = {'expiry': datetime.fromisoformat(expiry)}
            except ValueError:
                logger.warning(f"⚠️ Invalid expiry for user {user_id}: {expiry}")

        c.execute('SELECT user_id, file_name, file_type FROM user_files')
        for user_id, file_name, file_type in c.fetchall():
            if user_id not in user_files:
                user_files[user_id] = []
            user_files[user_id].append((file_name, file_type))

        c.execute('SELECT user_id FROM active_users')
        active_users.update(user_id for (user_id,) in c.fetchall())

        c.execute('SELECT user_id FROM admins')
        admin_ids.update(user_id for (user_id,) in c.fetchall())

        c.execute('SELECT user_id FROM authenticated_users')
        authenticated_users.update(user_id for (user_id,) in c.fetchall())

        conn.close()
        logger.info(f"Data loaded: {len(active_users)} users, {len(user_subscriptions)} subs, {len(admin_ids)} admins, {len(authenticated_users)} auth'd.")
    except Exception as e:
        logger.error(f"❌ Error loading data: {e}", exc_info=True)

# --- ⚙️ Bot Settings Functions ---
def load_bot_settings():
    """Load bot settings from database at startup"""
    global auto_approve_enabled
    try:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute('SELECT value FROM bot_settings WHERE key = ?', ('auto_approve',))
        row = c.fetchone()
        if row:
            auto_approve_enabled = row[0].lower() == 'true'
            logger.info(f"⚙️ Loaded auto_approve from DB: {auto_approve_enabled}")
        else:
            auto_approve_enabled = AUTO_APPROVE_DEFAULT
            c.execute('INSERT OR REPLACE INTO bot_settings (key, value) VALUES (?, ?)',
                      ('auto_approve', str(auto_approve_enabled).lower()))
            conn.commit()
            logger.info(f"⚙️ Initialized auto_approve: {auto_approve_enabled}")
        conn.close()
    except Exception as e:
        logger.error(f"❌ Error loading bot settings: {e}", exc_info=True)
        auto_approve_enabled = AUTO_APPROVE_DEFAULT

def save_bot_setting(key, value):
    """Save a bot setting to database"""
    with DB_LOCK:
        try:
            conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
            c = conn.cursor()
            c.execute('INSERT OR REPLACE INTO bot_settings (key, value) VALUES (?, ?)',
                      (key, str(value).lower()))
            conn.commit()
            conn.close()
            logger.info(f"⚙️ Saved setting {key} = {value}")
            return True
        except Exception as e:
            logger.error(f"❌ Error saving setting: {e}", exc_info=True)
            return False

def get_auto_approve_status():
    """Get current auto-approve status"""
    return auto_approve_enabled

def toggle_auto_approve():
    """Toggle auto-approve and return new value"""
    global auto_approve_enabled
    auto_approve_enabled = not auto_approve_enabled
    save_bot_setting('auto_approve', auto_approve_enabled)
    logger.info(f"⚙️ Auto-approve toggled to: {auto_approve_enabled}")
    return auto_approve_enabled

init_db()
load_data()
load_bot_settings()
# --- End Database Setup ---

# --- Password Authentication Functions ---
def save_authenticated_user(user_id):
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        try:
            c.execute('INSERT OR REPLACE INTO authenticated_users (user_id, authenticated_at) VALUES (?, ?)',
                      (user_id, datetime.now().isoformat()))
            conn.commit()
            authenticated_users.add(user_id)
            logger.info(f"✅ Saved authenticated user {user_id}")
            return True
        except sqlite3.Error as e:
            logger.error(f"❌ SQLite error saving authenticated user: {e}")
            return False
        finally:
            conn.close()

def remove_authenticated_user(user_id):
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        try:
            c.execute('DELETE FROM authenticated_users WHERE user_id = ?', (user_id,))
            conn.commit()
            authenticated_users.discard(user_id)
            logger.info(f"Removed authenticated user {user_id}")
            return True
        except sqlite3.Error as e:
            logger.error(f"❌ SQLite error removing auth user: {e}")
            return False
        finally:
            conn.close()

def is_user_authenticated(user_id):
    if not PASSWORD_REQUIRED:
        return True
    if user_id in admin_ids:
        return True
    return user_id in authenticated_users

def send_password_prompt(chat_id, user_name=""):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("🔐 ᴇɴᴛᴇʀ ᴘᴀꜱꜱᴡᴏʀᴅ", callback_data="enter_password")
    )
    
    welcome_text = f"""
{EMOJI_HEADER}
   🔐 ᴀᴄᴄᴇꜱꜱ ʀᴇQᴜɪʀᴇᴅ
{EMOJI_FOOTER}

👋 ʜᴇʟʟᴏ {user_name}!

{DIVIDER_THIN}

🔒 ᴛʜɪꜱ ʙᴏᴛ ɪꜱ ᴘʀɪᴠᴀᴛᴇ ᴀɴᴅ ʀᴇQᴜɪʀᴇꜱ ᴀ ᴘᴀꜱꜱᴡᴏʀᴅ ᴛᴏ ᴀᴄᴄᴇꜱꜱ.

📝 ᴛᴏ ɢᴇᴛ ᴀᴄᴄᴇꜱꜱ:
   • ᴄʟɪᴄᴋ ᴛʜᴇ ʙᴜᴛᴛᴏɴ ʙᴇʟᴏᴡ
   • ᴇɴᴛᴇʀ ᴛʜᴇ ᴄᴏʀʀᴇᴄᴛ ᴘᴀꜱꜱᴡᴏʀᴅ

{DIVIDER_THIN}

💡 ᴅᴏɴ'ᴛ ʜᴀᴠᴇ ᴀ ᴘᴀꜱꜱᴡᴏʀᴅ?
   ᴄᴏɴᴛᴀᴄᴛ: {YOUR_USERNAME}

{DIVIDER}
"""
    
    try:
        bot.send_message(chat_id, welcome_text, reply_markup=markup)
        logger.info(f"📨 Sent password prompt to {chat_id}")
    except Exception as e:
        logger.error(f"Error sending password prompt: {e}")

def process_password_entry(message):
    """Process password entered by user"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    user_name = message.from_user.first_name
    user_username = message.from_user.username
    
    entered_password = message.text.strip()
    
    logger.info(f"🔐 Password attempt: user={user_id}, len={len(entered_password)}")
    
    if entered_password == BOT_ACCESS_PASSWORD:
        logger.info(f"✅ Password CORRECT for user {user_id}")
        
        # ⚙️ Check dynamic auto-approve status
        if not get_auto_approve_status() and user_id in pending_auth_users:
            bot.reply_to(message, f"""
{DIVIDER_THIN}
⏳ ʏᴏᴜʀ ʀᴇQᴜᴇꜱᴛ ɪꜱ ᴀʟʀᴇᴀᴅʏ ᴘᴇɴᴅɪɴɢ!

ᴘʟᴇᴀꜱᴇ ᴡᴀɪᴛ ꜰᴏʀ ᴛʜᴇ ᴏᴡɴᴇʀ ᴛᴏ ᴀᴘᴘʀᴏᴠᴇ ʏᴏᴜʀ ᴀᴄᴄᴇꜱꜱ.
{DIVIDER_THIN}
""")
            return
        
        if get_auto_approve_status():
            # 🔥 INSTANT APPROVAL (auto-approve ON)
            save_authenticated_user(user_id)
            pending_auth_users.pop(user_id, None)
            
            bot.reply_to(message, f"""
{EMOJI_HEADER}
   ✅ ᴀᴄᴄᴇꜱꜱ ɢʀᴀɴᴛᴇᴅ!
{EMOJI_FOOTER}

🎉 ᴡᴇʟᴄᴏᴍᴇ! ʏᴏᴜʀ ᴘᴀꜱꜱᴡᴏʀᴅ ɪꜱ ᴄᴏʀʀᴇᴄᴛ.

🚀 ʏᴏᴜ ᴄᴀɴ ɴᴏᴡ ᴜꜱᴇ ᴛʜᴇ ʙᴏᴛ.

📝 ꜱᴇɴᴅ /start ᴛᴏ ʙᴇɢɪɴ.

{DIVIDER}
""")
            
            # 📢 Notify admins (informational)
            try:
                for admin_id in admin_ids:
                    try:
                        bot.send_message(
                            admin_id,
                            f"🔔 ɴᴇᴡ ᴜꜱᴇʀ ᴀᴜᴛʜᴇɴᴛɪᴄᴀᴛᴇᴅ\n\n"
                            f"👤 {user_name}\n"
                            f"✳️ @{user_username or 'ɴ/ᴀ'}\n"
                            f"🆔 `{user_id}`\n\n"
                            f"✅ ᴀᴜᴛᴏ-ᴀᴘᴘʀᴏᴠᴇᴅ",
                            parse_mode='Markdown'
                        )
                    except Exception as e:
                        logger.error(f"Failed to notify admin {admin_id}: {e}")
            except Exception as e:
                logger.error(f"Error notifying admins: {e}")
        
        else:
            # ⏳ MANUAL APPROVAL FLOW (auto-approve OFF)
            pending_auth_users[user_id] = {
                'password': entered_password,
                'timestamp': datetime.now(),
                'name': user_name,
                'username': user_username
            }
            
            logger.info(f"📝 Added {user_id} to pending. Total: {len(pending_auth_users)}")
            
            bot.reply_to(message, f"""
{EMOJI_HEADER}
   ✅ ᴘᴀꜱꜱᴡᴏʀᴅ ᴄᴏʀʀᴇᴄᴛ!
{EMOJI_FOOTER}

⏳ ʏᴏᴜʀ ᴀᴄᴄᴇꜱꜱ ʀᴇQᴜᴇꜱᴛ ʜᴀꜱ ʙᴇᴇɴ ꜱᴇɴᴛ ᴛᴏ ᴛʜᴇ ᴏᴡɴᴇʀ.

📌 ᴘʟᴇᴀꜱᴇ ᴡᴀɪᴛ ꜰᴏʀ ᴀᴘᴘʀᴏᴠᴀʟ.
   ʏᴏᴜ'ʟʟ ʙᴇ ɴᴏᴛɪꜰɪᴇᴅ ᴏɴᴄᴇ ᴀᴘᴘʀᴏᴠᴇᴅ.

{DIVIDER}
""")
            
            # 🔔 Notify owner with approval buttons
            notify_owner_about_auth_request(user_id, user_name, user_username)
        
    else:
        logger.warning(f"❌ Wrong password for user {user_id}")
        bot.reply_to(message, f"""
{EMOJI_HEADER}
   ❌ ᴡʀᴏɴɢ ᴘᴀꜱꜱᴡᴏʀᴅ!
{EMOJI_FOOTER}

🔒 ᴛʜᴇ ᴘᴀꜱꜱᴡᴏʀᴅ ʏᴏᴜ ᴇɴᴛᴇʀᴇᴅ ɪꜱ ɪɴᴄᴏʀʀᴇᴄᴛ.

📝 ᴘʟᴇᴀꜱᴇ ᴛʀʏ ᴀɢᴀɪɴ ᴡɪᴛʜ ᴛʜᴇ ᴄᴏʀʀᴇᴄᴛ ᴘᴀꜱꜱᴡᴏʀᴅ.

{DIVIDER}
""")
        send_password_prompt(chat_id, user_name)

def notify_owner_about_auth_request(user_id, user_name, user_username):
    """Notify owner about new auth request with approve/reject buttons"""
    logger.info(f"🔔 notify_owner CALLED: user_id={user_id}, admins={admin_ids}")
    
    try:
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.row(
            types.InlineKeyboardButton("✅ ᴀᴘᴘʀᴏᴠᴇ", callback_data=f'auth_approve_{user_id}'),
            types.InlineKeyboardButton("❌ ʀᴇᴊᴇᴄᴛ", callback_data=f'auth_reject_{user_id}')
        )
        
        notification = f"""
╔══════════════════════════╗
   🔐 ɴᴇᴡ ᴀᴄᴄᴇꜱꜱ ʀᴇQᴜᴇꜱᴛ
╚══════════════════════════╝

👤 ɴᴀᴍᴇ: {user_name}
✳️ ᴜꜱᴇʀɴᴀᴍᴇ: @{user_username or 'ɴ/ᴀ'}
🆔 ɪᴅ: `{user_id}`

┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄

✅ ᴘᴀꜱꜱᴡᴏʀᴅ ᴠᴇʀɪꜰɪᴇᴅ

┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄

ᴄʜᴏᴏꜱᴇ ᴀɴ ᴀᴄᴛɪᴏɴ ʙᴇʟᴏᴡ:
"""
        
        sent_count = 0
        for admin_id in admin_ids:
            logger.info(f"🔔 Sending to admin {admin_id}...")
            try:
                result = bot.send_message(admin_id, notification, parse_mode='Markdown', reply_markup=markup)
                logger.info(f"✅ Sent to admin {admin_id}")
                sent_count += 1
            except Exception as e:
                logger.error(f"❌ FAILED to send to admin {admin_id}: {e}", exc_info=True)
        
        if sent_count == 0:
            logger.error("❌ No admin received the notification!")
    except Exception as e:
        logger.error(f"❌ Outer error in notify_owner: {e}", exc_info=True)

def approve_user_auth(call):
    try:
        parts = call.data.split('_')
        user_id = int(parts[2])
        admin_id = call.from_user.id
        
        logger.info(f"🔓 Approve: admin={admin_id}, user={user_id}")
        
        if admin_id not in admin_ids:
            bot.answer_callback_query(call.id, "⚠️ Admin permissions required.", show_alert=True)
            return
        
        save_authenticated_user(user_id)
        pending_auth_users.pop(user_id, None)
        
        try:
            bot.send_message(user_id, f"""
{EMOJI_HEADER}
   🎉 ᴀᴄᴄᴇꜱꜱ ɢʀᴀɴᴛᴇᴅ!
{EMOJI_FOOTER}

✅ ʏᴏᴜʀ ᴀᴄᴄᴇꜱꜱ ʜᴀꜱ ʙᴇᴇɴ ᴀᴘᴘʀᴏᴠᴇᴅ ʙʏ ᴛʜᴇ ᴏᴡɴᴇʀ!

🚀 ʏᴏᴜ ᴄᴀɴ ɴᴏᴡ ᴜꜱᴇ ᴛʜᴇ ʙᴏᴛ.

📝 ꜱᴇɴᴅ /start ᴛᴏ ʙᴇɢɪɴ.

{DIVIDER}
""")
        except Exception as e:
            logger.error(f"Failed to notify user {user_id}: {e}")
        
        bot.answer_callback_query(call.id, f"✅ User {user_id} approved!")
        
        try:
            bot.edit_message_text(
                f"✅ ᴀᴘᴘʀᴏᴠᴇᴅ ᴜꜱᴇʀ `{user_id}`",
                call.message.chat.id,
                call.message.message_id,
                parse_mode='Markdown'
            )
        except Exception:
            pass
            
    except Exception as e:
        logger.error(f"Error approving: {e}", exc_info=True)
        bot.answer_callback_query(call.id, f"Error: {str(e)}", show_alert=True)

def reject_user_auth(call):
    try:
        parts = call.data.split('_')
        user_id = int(parts[2])
        admin_id = call.from_user.id
        
        logger.info(f"🚫 Reject: admin={admin_id}, user={user_id}")
        
        if admin_id not in admin_ids:
            bot.answer_callback_query(call.id, "⚠️ Admin permissions required.", show_alert=True)
            return
        
        pending_auth_users.pop(user_id, None)
        
        try:
            bot.send_message(user_id, f"""
{EMOJI_HEADER}
   ❌ ᴀᴄᴄᴇꜱꜱ ᴅᴇɴɪᴇᴅ
{EMOJI_FOOTER}

😔 ʏᴏᴜʀ ᴀᴄᴄᴇꜱꜱ ʀᴇQᴜᴇꜱᴛ ʜᴀꜱ ʙᴇᴇɴ ʀᴇᴊᴇᴄᴛᴇᴅ.

📞 ᴄᴏɴᴛᴀᴄᴛ ᴛʜᴇ ᴏᴡɴᴇʀ:
   {YOUR_USERNAME}

{DIVIDER}
""")
        except Exception as e:
            logger.error(f"Failed to notify user {user_id}: {e}")
        
        bot.answer_callback_query(call.id, f"❌ User {user_id} rejected!")
        
        try:
            bot.edit_message_text(
                f"❌ ʀᴇᴊᴇᴄᴛᴇᴅ ᴜꜱᴇʀ `{user_id}`",
                call.message.chat.id,
                call.message.message_id,
                parse_mode='Markdown'
            )
        except Exception:
            pass
            
    except Exception as e:
        logger.error(f"Error rejecting: {e}", exc_info=True)
        bot.answer_callback_query(call.id, f"Error: {str(e)}", show_alert=True)

def show_auth_requests(message_or_call):
    """Show pending auth requests to admin"""
    if isinstance(message_or_call, telebot.types.Message):
        user_id = message_or_call.from_user.id
        chat_id = message_or_call.chat.id
        reply_func = lambda text, **kwargs: bot.reply_to(message_or_call, text, **kwargs)
    else:
        user_id = message_or_call.from_user.id
        chat_id = message_or_call.message.chat.id
        reply_func = lambda text, **kwargs: bot.send_message(chat_id, text, **kwargs)
        bot.answer_callback_query(message_or_call.id)
    
    if user_id not in admin_ids:
        reply_func("⚠️ Admin permissions required.")
        return
    
    if not pending_auth_users:
        reply_func(f"""
{EMOJI_HEADER}
   📭 ɴᴏ ᴘᴇɴᴅɪɴɢ ʀᴇQᴜᴇꜱᴛꜱ
{EMOJI_FOOTER}

ᴛʜᴇʀᴇ ᴀʀᴇ ᴄᴜʀʀᴇɴᴛʟʏ ɴᴏ ᴘᴇɴᴅɪɴɢ ᴀᴜᴛʜ ʀᴇQᴜᴇꜱᴛꜱ.

{'💡 ᴀᴜᴛᴏ-ᴀᴘᴘʀᴏᴠᴇ ɪꜱ ᴏɴ' if get_auto_approve_status() else '💡 ᴀᴜᴛᴏ-ᴀᴘᴘʀᴏᴠᴇ ɪꜱ ᴏꜰꜰ'}

{DIVIDER}
""")
        return
    
    text = f"""
{EMOJI_HEADER}
   🔐 ᴘᴇɴᴅɪɴɢ ᴀᴜᴛʜ ʀᴇQᴜᴇꜱᴛꜱ
{EMOJI_FOOTER}

📊 ᴛᴏᴛᴀʟ: {len(pending_auth_users)}

{DIVIDER_THIN}
"""
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    for uid, data in pending_auth_users.items():
        text += f"\n👤 {data['name']} (@{data['username'] or 'N/A'})\n🆔 `{uid}`\n"
        markup.row(
            types.InlineKeyboardButton(f"✅ {data['name'][:20]}", callback_data=f'auth_approve_{uid}'),
            types.InlineKeyboardButton(f"❌ {data['name'][:20]}", callback_data=f'auth_reject_{uid}')
        )
    
    text += f"\n{DIVIDER}"
    
    reply_func(text, parse_mode='Markdown', reply_markup=markup)

# --- Malware Detection ---
def get_file_type(file_content):
    signatures = {
        b'\x7fELF': 'application/x-executable',
        b'MZ': 'application/x-dosexec',
        b'\xfe\xed\xfa': 'application/x-mach-binary',
        b'\xce\xfa\xed\xfe': 'application/x-mach-binary',
        b'PK': 'application/zip',
        b'Rar!': 'application/x-rar',
    }
    for signature, mime_type in signatures.items():
        if file_content.startswith(signature):
            return mime_type
    return 'application/octet-stream'

def is_suspicious_file(file_content, file_name):
    file_lower = file_name.lower()
    suspicious_extensions = ['.exe', '.dll', '.bat', '.cmd', '.scr', '.com', '.pif', '.application', '.gadget',
                            '.msi', '.msp', '.hta', '.cpl', '.msc', '.jar', '.bin', '.deb', '.rpm',
                            '.apk', '.app', '.dmg', '.iso', '.img']
    
    if any(file_lower.endswith(ext) for ext in suspicious_extensions):
        return True, f"Suspicious extension: {file_name}"
    
    for signature in MALWARE_SIGNATURES:
        if file_content.startswith(signature):
            return True, f"Malware signature: {signature}"
    
    sample_size = min(len(file_content), 4096)
    file_sample = file_content[:sample_size]
    
    for indicator in ENCRYPTED_FILE_INDICATORS:
        if indicator in file_sample:
            return True, f"Encrypted file indicator"
    
    sample_text = file_sample.decode('utf-8', errors='ignore').lower()
    for keyword in SUSPICIOUS_KEYWORDS:
        if keyword.decode('utf-8').lower() in sample_text:
            return True, f"Suspicious keyword"
    
    try:
        file_type = get_file_type(file_sample)
        if file_type in ['application/x-dosexec', 'application/x-executable', 'application/x-mach-binary']:
            return True, f"Executable file type"
    except Exception as e:
        pass
    
    return False, "File appears safe"

def scan_file_for_malware(file_content, file_name, user_id):
    if user_id == OWNER_ID:
        return True, "Owner bypass"
    is_suspicious, reason = is_suspicious_file(file_content, file_name)
    if is_suspicious:
        return False, f"Security violation: {reason}"
    return True, "File passed"

# --- Helper Functions ---
def get_user_folder(user_id):
    user_folder = os.path.join(UPLOAD_BOTS_DIR, str(user_id))
    os.makedirs(user_folder, exist_ok=True)
    return user_folder

def get_user_file_limit(user_id):
    if user_id == OWNER_ID: return OWNER_LIMIT
    if user_id in admin_ids: return ADMIN_LIMIT
    if user_id in user_subscriptions and user_subscriptions[user_id]['expiry'] > datetime.now():
        return SUBSCRIBED_USER_LIMIT
    return FREE_USER_LIMIT

def get_user_file_count(user_id):
    return len(user_files.get(user_id, []))

def is_bot_running(script_owner_id, file_name):
    script_key = f"{script_owner_id}_{file_name}"
    script_info = bot_scripts.get(script_key)
    if script_info and script_info.get('process'):
        try:
            proc = psutil.Process(script_info['process'].pid)
            is_running = proc.is_running() and proc.status() != psutil.STATUS_ZOMBIE
            if not is_running:
                if 'log_file' in script_info and hasattr(script_info['log_file'], 'close') and not script_info['log_file'].closed:
                    try: script_info['log_file'].close()
                    except: pass
                if script_key in bot_scripts:
                    del bot_scripts[script_key]
            return is_running
        except psutil.NoSuchProcess:
            if 'log_file' in script_info and hasattr(script_info['log_file'], 'close') and not script_info['log_file'].closed:
                try: script_info['log_file'].close()
                except: pass
            if script_key in bot_scripts:
                del bot_scripts[script_key]
            return False
        except Exception as e:
            return False
    return False

def kill_process_tree(process_info):
    pid = None
    script_key = process_info.get('script_key', 'N/A')
    try:
        if 'log_file' in process_info and hasattr(process_info['log_file'], 'close') and not process_info['log_file'].closed:
            try:
                process_info['log_file'].close()
            except Exception as log_e:
                logger.error(f"Error closing log: {log_e}")

        process = process_info.get('process')
        if process and hasattr(process, 'pid'):
            pid = process.pid
            if pid:
                try:
                    parent = psutil.Process(pid)
                    children = parent.children(recursive=True)
                    for child in children:
                        try: child.terminate()
                        except psutil.NoSuchProcess: pass
                        except Exception:
                            try: child.kill()
                            except: pass
                    gone, alive = psutil.wait_procs(children, timeout=1)
                    for p in alive:
                        try: p.kill()
                        except: pass
                    try:
                        parent.terminate()
                        try: parent.wait(timeout=1)
                        except psutil.TimeoutExpired: parent.kill()
                    except psutil.NoSuchProcess: pass
                    except Exception:
                        try: parent.kill()
                        except: pass
                except psutil.NoSuchProcess: pass
    except Exception as e:
        logger.error(f"Error killing {script_key}: {e}", exc_info=True)

# --- Package Installation ---
TELEGRAM_MODULES = {
    'telebot': 'pyTelegramBotAPI', 'telegram': 'python-telegram-bot',
    'aiogram': 'aiogram', 'pyrogram': 'pyrogram', 'telethon': 'telethon',
    'telepot': 'telepot', 'tgcrypto': 'tgcrypto',
    'telegram_upload': 'telegram-upload', 'telegram_send': 'telegram-send',
    'bs4': 'beautifulsoup4', 'requests': 'requests', 'pillow': 'Pillow',
    'cv2': 'opencv-python', 'yaml': 'PyYAML', 'dotenv': 'python-dotenv',
    'dateutil': 'python-dateutil', 'pandas': 'pandas', 'numpy': 'numpy',
    'flask': 'Flask', 'django': 'Django', 'sqlalchemy': 'SQLAlchemy',
    'psutil': 'psutil',
    'asyncio': None, 'json': None, 'datetime': None, 'os': None, 'sys': None,
    're': None, 'time': None, 'math': None, 'random': None, 'logging': None,
    'threading': None, 'subprocess': None, 'zipfile': None, 'tempfile': None,
    'shutil': None, 'sqlite3': None, 'atexit': None
}

def attempt_install_pip(module_name, message):
    package_name = TELEGRAM_MODULES.get(module_name.lower(), module_name)
    if module_name.lower() == "pil":
        package_name = "pillow"
    if package_name is None:
        return False
    try:
        bot.reply_to(message, f"🐍 Installing `{package_name}`...", parse_mode='Markdown')
        command = [sys.executable, '-m', 'pip', 'install', package_name]
        result = subprocess.run(command, capture_output=True, text=True, check=False,
                              encoding='utf-8', errors='replace',
                              env={**os.environ, "PYTHONIOENCODING": "utf-8"})
        if result.returncode == 0:
            bot.reply_to(message, f"✅ Installed `{package_name}`.", parse_mode='Markdown')
            return True
        else:
            bot.reply_to(message, f"❌ Install failed.", parse_mode='Markdown')
            return False
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")
        return False

def attempt_install_npm(module_name, user_folder, message):
    try:
        bot.reply_to(message, f"🟠 Installing Node `{module_name}`...", parse_mode='Markdown')
        command = ['npm', 'install', module_name]
        result = subprocess.run(command, capture_output=True, text=True, check=False,
                              cwd=user_folder, encoding='utf-8', errors='replace')
        if result.returncode == 0:
            bot.reply_to(message, f"✅ Installed `{module_name}`.", parse_mode='Markdown')
            return True
        else:
            bot.reply_to(message, f"❌ Install failed.", parse_mode='Markdown')
            return False
    except FileNotFoundError:
        bot.reply_to(message, "❌ 'npm' not found.")
        return False
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")
        return False

def run_script(script_path, script_owner_id, user_folder, file_name, message_obj_for_reply, attempt=1):
    max_attempts = 2
    if attempt > max_attempts:
        bot.reply_to(message_obj_for_reply, f"❌ Failed '{file_name}' after {max_attempts} attempts.")
        return
    script_key = f"{script_owner_id}_{file_name}"

    try:
        if not os.path.exists(script_path):
            bot.reply_to(message_obj_for_reply, f"❌ Script '{file_name}' not found!")
            if script_owner_id in user_files:
                user_files[script_owner_id] = [f for f in user_files.get(script_owner_id, []) if f[0] != file_name]
            remove_user_file_db(script_owner_id, file_name)
            return

        if attempt == 1:
            check_command = [sys.executable, script_path]
            check_proc = None
            try:
                check_proc = subprocess.Popen(check_command, cwd=user_folder, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                            text=True, encoding='utf-8', errors='replace',
                                            env={**os.environ, "PYTHONIOENCODING": "utf-8"})
                stdout, stderr = check_proc.communicate(timeout=5)
                return_code = check_proc.returncode
                
                if return_code != 0 and stderr:
                    match_py = re.search(r"ModuleNotFoundError: No module named '(.+?)'", stderr)
                    if match_py:
                        module_name = match_py.group(1).strip()
                        if attempt_install_pip(module_name, message_obj_for_reply):
                            time.sleep(2)
                            threading.Thread(target=run_script, args=(script_path, script_owner_id, user_folder,
                                                                     file_name, message_obj_for_reply, attempt + 1)).start()
                            return
                        else:
                            return
                    else:
                        bot.reply_to(message_obj_for_reply, f"❌ Error:\n```{stderr[:500]}```", parse_mode='Markdown')
                        return
            except subprocess.TimeoutExpired:
                if check_proc and check_proc.poll() is None:
                    check_proc.kill()
                    check_proc.communicate()
            except FileNotFoundError:
                bot.reply_to(message_obj_for_reply, f"❌ Python not found.")
                return
            except Exception as e:
                bot.reply_to(message_obj_for_reply, f"❌ Pre-check error: {e}")
                return
            finally:
                if check_proc and check_proc.poll() is None:
                    check_proc.kill()
                    check_proc.communicate()

        log_file_path = os.path.join(user_folder, f"{os.path.splitext(file_name)[0]}.log")
        log_file = None
        process = None
        try:
            log_file = open(log_file_path, 'w', encoding='utf-8', errors='replace')
        except Exception as e:
            bot.reply_to(message_obj_for_reply, f"❌ Failed to open log: {e}")
            return
        try:
            startupinfo = None
            creationflags = 0
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE
            process = subprocess.Popen([sys.executable, script_path], cwd=user_folder, stdout=log_file, stderr=log_file,
                                     stdin=subprocess.PIPE, startupinfo=startupinfo, creationflags=creationflags,
                                     text=True, encoding='utf-8', errors='replace',
                                     env={**os.environ, "PYTHONIOENCODING": "utf-8"})
            bot_scripts[script_key] = {
                'process': process, 'log_file': log_file, 'file_name': file_name,
                'chat_id': message_obj_for_reply.chat.id, 'script_owner_id': script_owner_id,
                'start_time': datetime.now(), 'user_folder': user_folder, 'type': 'py', 'script_key': script_key
            }
            bot.reply_to(message_obj_for_reply, f"✅ Python '{file_name}' started!\n🆔 PID: {process.pid}")
        except FileNotFoundError:
            bot.reply_to(message_obj_for_reply, "❌ Python not found.")
            if log_file and not log_file.closed: log_file.close()
        except Exception as e:
            if log_file and not log_file.closed: log_file.close()
            bot.reply_to(message_obj_for_reply, f"❌ Failed: {e}")
            if process and process.poll() is None:
                kill_process_tree({'process': process, 'log_file': log_file, 'script_key': script_key})
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        bot.reply_to(message_obj_for_reply, f"❌ Error: {e}")
        if script_key in bot_scripts:
            kill_process_tree(bot_scripts[script_key])
            del bot_scripts[script_key]

def run_js_script(script_path, script_owner_id, user_folder, file_name, message_obj_for_reply, attempt=1):
    max_attempts = 2
    if attempt > max_attempts:
        bot.reply_to(message_obj_for_reply, f"❌ Failed '{file_name}' after {max_attempts} attempts.")
        return
    script_key = f"{script_owner_id}_{file_name}"

    try:
        if not os.path.exists(script_path):
            bot.reply_to(message_obj_for_reply, f"❌ Script '{file_name}' not found!")
            if script_owner_id in user_files:
                user_files[script_owner_id] = [f for f in user_files.get(script_owner_id, []) if f[0] != file_name]
            remove_user_file_db(script_owner_id, file_name)
            return

        if attempt == 1:
            check_command = ['node', script_path]
            check_proc = None
            try:
                check_proc = subprocess.Popen(check_command, cwd=user_folder, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                            text=True, encoding='utf-8', errors='replace',
                                            env={**os.environ, "PYTHONIOENCODING": "utf-8"})
                stdout, stderr = check_proc.communicate(timeout=5)
                return_code = check_proc.returncode

                if return_code != 0 and stderr:
                    match_js = re.search(r"Cannot find module '(.+?)'", stderr)
                    if match_js:
                        module_name = match_js.group(1).strip()
                        if not module_name.startswith('.') and not module_name.startswith('/'):
                            if attempt_install_npm(module_name, user_folder, message_obj_for_reply):
                                time.sleep(2)
                                threading.Thread(target=run_js_script, args=(script_path, script_owner_id, user_folder,
                                                                             file_name, message_obj_for_reply, attempt + 1)).start()
                                return
                            else:
                                return
                    bot.reply_to(message_obj_for_reply, f"❌ JS Error:\n```{stderr[:500]}```", parse_mode='Markdown')
                    return
            except subprocess.TimeoutExpired:
                if check_proc and check_proc.poll() is None:
                    check_proc.kill()
                    check_proc.communicate()
            except FileNotFoundError:
                bot.reply_to(message_obj_for_reply, "❌ Node.js not installed.")
                return
            except Exception as e:
                bot.reply_to(message_obj_for_reply, f"❌ JS pre-check: {e}")
                return
            finally:
                if check_proc and check_proc.poll() is None:
                    check_proc.kill()
                    check_proc.communicate()

        log_file_path = os.path.join(user_folder, f"{os.path.splitext(file_name)[0]}.log")
        log_file = None
        process = None
        try:
            log_file = open(log_file_path, 'w', encoding='utf-8', errors='replace')
        except Exception as e:
            bot.reply_to(message_obj_for_reply, f"❌ Failed to open log: {e}")
            return
        try:
            startupinfo = None
            creationflags = 0
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE
            process = subprocess.Popen(['node', script_path], cwd=user_folder, stdout=log_file, stderr=log_file,
                                     stdin=subprocess.PIPE, startupinfo=startupinfo, creationflags=creationflags,
                                     text=True, encoding='utf-8', errors='replace',
                                     env={**os.environ, "PYTHONIOENCODING": "utf-8"})
            bot_scripts[script_key] = {
                'process': process, 'log_file': log_file, 'file_name': file_name,
                'chat_id': message_obj_for_reply.chat.id, 'script_owner_id': script_owner_id,
                'start_time': datetime.now(), 'user_folder': user_folder, 'type': 'js', 'script_key': script_key
            }
            bot.reply_to(message_obj_for_reply, f"✅ JS '{file_name}' started!\n🆔 PID: {process.pid}")
        except FileNotFoundError:
            bot.reply_to(message_obj_for_reply, "❌ Node.js not installed.")
            if log_file and not log_file.closed: log_file.close()
        except Exception as e:
            if log_file and not log_file.closed: log_file.close()
            bot.reply_to(message_obj_for_reply, f"❌ Failed: {e}")
            if process and process.poll() is None:
                kill_process_tree({'process': process, 'log_file': log_file, 'script_key': script_key})
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        bot.reply_to(message_obj_for_reply, f"❌ Error: {e}")
        if script_key in bot_scripts:
            kill_process_tree(bot_scripts[script_key])
            del bot_scripts[script_key]

# --- Database Operations ---
def save_user_file(user_id, file_name, file_type='py'):
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        try:
            c.execute('INSERT OR REPLACE INTO user_files (user_id, file_name, file_type) VALUES (?, ?, ?)',
                      (user_id, file_name, file_type))
            conn.commit()
            if user_id not in user_files: user_files[user_id] = []
            user_files[user_id] = [(fn, ft) for fn, ft in user_files[user_id] if fn != file_name]
            user_files[user_id].append((file_name, file_type))
        except Exception as e:
            logger.error(f"Error: {e}")
        finally: conn.close()

def remove_user_file_db(user_id, file_name):
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        try:
            c.execute('DELETE FROM user_files WHERE user_id = ? AND file_name = ?', (user_id, file_name))
            conn.commit()
            if user_id in user_files:
                user_files[user_id] = [f for f in user_files[user_id] if f[0] != file_name]
                if not user_files[user_id]: del user_files[user_id]
        except Exception as e:
            logger.error(f"Error: {e}")
        finally: conn.close()

def add_active_user(user_id):
    active_users.add(user_id)
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        try:
            c.execute('INSERT OR IGNORE INTO active_users (user_id) VALUES (?)', (user_id,))
            conn.commit()
        except Exception as e:
            logger.error(f"Error: {e}")
        finally: conn.close()

def save_subscription(user_id, expiry):
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        try:
            expiry_str = expiry.isoformat()
            c.execute('INSERT OR REPLACE INTO subscriptions (user_id, expiry) VALUES (?, ?)', (user_id, expiry_str))
            conn.commit()
            user_subscriptions[user_id] = {'expiry': expiry}
        except Exception as e:
            logger.error(f"Error: {e}")
        finally: conn.close()

def remove_subscription_db(user_id):
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        try:
            c.execute('DELETE FROM subscriptions WHERE user_id = ?', (user_id,))
            conn.commit()
            if user_id in user_subscriptions: del user_subscriptions[user_id]
        except Exception as e:
            logger.error(f"Error: {e}")
        finally: conn.close()

def add_admin_db(admin_id):
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        try:
            c.execute('INSERT OR IGNORE INTO admins (user_id) VALUES (?)', (admin_id,))
            conn.commit()
            admin_ids.add(admin_id)
        except Exception as e:
            logger.error(f"Error: {e}")
        finally: conn.close()

def remove_admin_db(admin_id):
    if admin_id == OWNER_ID:
        return False
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        removed = False
        try:
            c.execute('DELETE FROM admins WHERE user_id = ?', (admin_id,))
            conn.commit()
            removed = c.rowcount > 0
            if removed:
                admin_ids.discard(admin_id)
            return removed
        except Exception as e:
            logger.error(f"Error: {e}")
            return False
        finally: conn.close()

# --- File Approval DB ---
def save_pending_file_to_db(user_id, file_name, file_path, file_type, message_id):
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        try:
            timestamp = datetime.now().isoformat()
            c.execute('''INSERT INTO pending_files (user_id, file_name, file_path, file_type, timestamp, message_id, status)
                         VALUES (?, ?, ?, ?, ?, ?, 'pending')''', (user_id, file_name, file_path, file_type, timestamp, message_id))
            conn.commit()
            return c.lastrowid
        except Exception as e:
            logger.error(f"Error: {e}")
            return None
        finally: conn.close()

def load_pending_files_from_db():
    global pending_files
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        try:
            c.execute('''SELECT file_id, user_id, file_name, file_path, file_type, timestamp, message_id 
                         FROM pending_files WHERE status = 'pending' ORDER BY timestamp''')
            rows = c.fetchall()
            pending_files = {}
            for row in rows:
                file_id, user_id, file_name, file_path, file_type, timestamp_str, message_id = row
                pending_files[file_id] = {
                    'user_id': user_id, 'file_name': file_name, 'file_path': file_path,
                    'file_type': file_type,
                    'timestamp': datetime.fromisoformat(timestamp_str) if timestamp_str else datetime.now(),
                    'message_id': message_id
                }
            return pending_files
        except Exception as e:
            logger.error(f"Error: {e}")
            return {}
        finally: conn.close()

def update_pending_file_status(file_id, status):
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        try:
            c.execute('UPDATE pending_files SET status = ? WHERE file_id = ?', (status, file_id))
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error: {e}")
            return False
        finally: conn.close()

def get_pending_files_count():
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        try:
            c.execute('SELECT COUNT(*) FROM pending_files WHERE status = "pending"')
            return c.fetchone()[0]
        except Exception as e:
            return 0
        finally: conn.close()

def get_pending_file_by_id(file_id):
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        try:
            c.execute('''SELECT file_id, user_id, file_name, file_path, file_type, timestamp, message_id 
                         FROM pending_files WHERE file_id = ? AND status = 'pending' ''', (file_id,))
            row = c.fetchone()
            if row:
                return {
                    'file_id': row[0], 'user_id': row[1], 'file_name': row[2], 'file_path': row[3],
                    'file_type': row[4], 'timestamp': datetime.fromisoformat(row[5]) if row[5] else datetime.now(),
                    'message_id': row[6]
                }
            return None
        except Exception as e:
            return None
        finally: conn.close()

def get_pending_files_for_admin():
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        try:
            c.execute('''SELECT file_id, user_id, file_name, file_type, timestamp 
                         FROM pending_files WHERE status = 'pending' ORDER BY timestamp''')
            return c.fetchall()
        except Exception as e:
            return []
        finally: conn.close()

load_pending_files_from_db()

# --- Menu Creation ---
def create_main_menu_inline(user_id):
    markup = types.InlineKeyboardMarkup(row_width=2)
    buttons = [
        types.InlineKeyboardButton('📢 ᴜᴘᴅᴀᴛᴇꜱ ᴄʜᴀɴɴᴇʟ', url=UPDATE_CHANNEL),
        types.InlineKeyboardButton('📤 ᴜᴘʟᴏᴀᴅ ꜰɪʟᴇ', callback_data='upload'),
        types.InlineKeyboardButton('📂 ᴄʜᴇᴄᴋ ꜰɪʟᴇꜱ', callback_data='check_files'),
        types.InlineKeyboardButton('⚡ ʙᴏᴛ ꜱᴘᴇᴇᴅ', callback_data='speed'),
        types.InlineKeyboardButton('📤 ꜱᴇɴᴅ ᴄᴏᴍᴍᴀɴᴅ', callback_data='send_command'),
        types.InlineKeyboardButton('📞 ᴄᴏɴᴛᴀᴄᴛ ᴏᴡɴᴇʀ', url=f'https://t.me/{YOUR_USERNAME.replace("@", "")}')
    ]

    if user_id in admin_ids:
        pending_count = get_pending_files_count()
        pending_text = f"📥 ᴘᴇɴᴅɪɴɢ ({pending_count})" if pending_count > 0 else "📥 ᴘᴇɴᴅɪɴɢ"
        auth_count = len(pending_auth_users)
        auth_text = f"🔐 ᴀᴜᴛʜ ({auth_count})" if auth_count > 0 else "🔐 ᴀᴜᴛʜ ʀᴇQᴜᴇꜱᴛꜱ"
        auto_status = "🟢" if get_auto_approve_status() else "🔴"
        
        admin_buttons = [
            types.InlineKeyboardButton('💳 ꜱᴜʙꜱᴄʀɪᴘᴛɪᴏɴꜱ', callback_data='subscription'),
            types.InlineKeyboardButton('📊 ꜱᴛᴀᴛɪꜱᴛɪᴄꜱ', callback_data='stats'),
            types.InlineKeyboardButton('🔒 ʟᴏᴄᴋ ʙᴏᴛ' if not bot_locked else '🔓 ᴜɴʟᴏᴄᴋ ʙᴏᴛ',
                                     callback_data='lock_bot' if not bot_locked else 'unlock_bot'),
            types.InlineKeyboardButton('📢 ʙʀᴏᴀᴅᴄᴀꜱᴛ', callback_data='broadcast'),
            types.InlineKeyboardButton('👑 ᴀᴅᴍɪɴ ᴘᴀɴᴇʟ', callback_data='admin_panel'),
            types.InlineKeyboardButton('🟢 ʀᴜɴ ᴀʟʟ ꜱᴄʀɪᴘᴛꜱ', callback_data='run_all_scripts'),
            types.InlineKeyboardButton(pending_text, callback_data='pending_approvals'),
            types.InlineKeyboardButton(auth_text, callback_data='auth_requests'),
            types.InlineKeyboardButton(f'{auto_status} ᴀᴜᴛᴏ-ᴀᴘᴘʀᴏᴠᴇ', callback_data='toggle_auto_approve')
        ]
        markup.add(buttons[0])
        markup.add(buttons[1], buttons[2])
        markup.add(buttons[3], admin_buttons[0])
        markup.add(admin_buttons[1], admin_buttons[3])
        markup.add(admin_buttons[2], admin_buttons[5])
        markup.add(buttons[4])
        markup.add(admin_buttons[4])
        markup.add(admin_buttons[6])
        markup.add(admin_buttons[7])
        markup.add(admin_buttons[8])  # ⚙️ Auto-Approve Toggle
        markup.add(buttons[5])
    else:
        markup.add(buttons[0])
        markup.add(buttons[1], buttons[2])
        markup.add(buttons[3])
        markup.add(buttons[4])
        markup.add(types.InlineKeyboardButton('📊 ꜱᴛᴀᴛɪꜱᴛɪᴄꜱ', callback_data='stats'))
        markup.add(buttons[5])
    return markup

def create_reply_keyboard_main_menu(user_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    layout_to_use = ADMIN_COMMAND_BUTTONS_LAYOUT_USER_SPEC if user_id in admin_ids else COMMAND_BUTTONS_LAYOUT_USER_SPEC
    for row_buttons_text in layout_to_use:
        markup.add(*[types.KeyboardButton(text) for text in row_buttons_text])
    return markup

def create_control_buttons(script_owner_id, file_name, is_running=True):
    markup = types.InlineKeyboardMarkup(row_width=2)
    if is_running:
        markup.row(
            types.InlineKeyboardButton("🔴 ꜱᴛᴏᴘ", callback_data=f'stop_{script_owner_id}_{file_name}'),
            types.InlineKeyboardButton("🔄 ʀᴇꜱᴛᴀʀᴛ", callback_data=f'restart_{script_owner_id}_{file_name}')
        )
        markup.row(
            types.InlineKeyboardButton("🗑️ ᴅᴇʟᴇᴛᴇ", callback_data=f'delete_{script_owner_id}_{file_name}'),
            types.InlineKeyboardButton("📜 ʟᴏɢꜱ", callback_data=f'logs_{script_owner_id}_{file_name}')
        )
    else:
        markup.row(
            types.InlineKeyboardButton("🟢 ꜱᴛᴀʀᴛ", callback_data=f'start_{script_owner_id}_{file_name}'),
            types.InlineKeyboardButton("🗑️ ᴅᴇʟᴇᴛᴇ", callback_data=f'delete_{script_owner_id}_{file_name}')
        )
        markup.row(
            types.InlineKeyboardButton("📜 ᴠɪᴇᴡ ʟᴏɢꜱ", callback_data=f'logs_{script_owner_id}_{file_name}')
        )
    markup.add(types.InlineKeyboardButton("🔙 ʙᴀᴄᴋ", callback_data='check_files'))
    return markup

def create_admin_panel():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.row(
        types.InlineKeyboardButton('➕ ᴀᴅᴅ ᴀᴅᴍɪɴ', callback_data='add_admin'),
        types.InlineKeyboardButton('➖ ʀᴇᴍᴏᴠᴇ ᴀᴅᴍɪɴ', callback_data='remove_admin')
    )
    markup.row(types.InlineKeyboardButton('📋 ʟɪꜱᴛ ᴀᴅᴍɪɴꜱ', callback_data='list_admins'))
    markup.row(types.InlineKeyboardButton('🔙 ʙᴀᴄᴋ', callback_data='back_to_main'))
    return markup

def create_subscription_menu():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.row(
        types.InlineKeyboardButton('➕ ᴀᴅᴅ', callback_data='add_subscription'),
        types.InlineKeyboardButton('➖ ʀᴇᴍᴏᴠᴇ', callback_data='remove_subscription')
    )
    markup.row(types.InlineKeyboardButton('🔍 ᴄʜᴇᴄᴋ', callback_data='check_subscription'))
    markup.row(types.InlineKeyboardButton('🔙 ʙᴀᴄᴋ', callback_data='back_to_main'))
    return markup

def create_send_command_menu():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.row(
        types.InlineKeyboardButton('📝 ꜱᴇɴᴅ ᴛᴏ ᴘʀᴏᴄᴇꜱꜱ', callback_data='send_to_process'),
        types.InlineKeyboardButton('🔍 ᴀʟʟ ʟᴏɢꜱ', callback_data='view_all_logs')
    )
    markup.row(types.InlineKeyboardButton('🔙 ʙᴀᴄᴋ', callback_data='back_to_main'))
    return markup

# --- File Handling ---
def handle_zip_file(downloaded_file_content, file_name_zip, message):
    user_id = message.from_user.id
    user_folder = get_user_folder(user_id)
    temp_dir = None
    
    if user_id != OWNER_ID:
        is_safe, reason = scan_file_for_malware(downloaded_file_content, file_name_zip, user_id)
        if not is_safe:
            bot.reply_to(message, f"🚨 Security Alert: {reason}")
            return
    
    try:
        temp_dir = tempfile.mkdtemp(prefix=f"user_{user_id}_zip_")
        zip_path = os.path.join(temp_dir, file_name_zip)
        with open(zip_path, 'wb') as new_file:
            new_file.write(downloaded_file_content)
        
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            if user_id != OWNER_ID:
                for member in zip_ref.infolist():
                    member_name_lower = member.filename.lower()
                    suspicious_extensions = ['.exe', '.dll', '.bat', '.cmd', '.scr', '.com']
                    if any(member_name_lower.endswith(ext) for ext in suspicious_extensions):
                        bot.reply_to(message, f"🚨 ZIP has suspicious file: {member.filename}")
                        return
                    member_path = os.path.abspath(os.path.join(temp_dir, member.filename))
                    if not member_path.startswith(os.path.abspath(temp_dir)):
                        raise zipfile.BadZipFile(f"Unsafe path: {member.filename}")
            zip_ref.extractall(temp_dir)

        target_dir = temp_dir
        root_files = os.listdir(target_dir)
        
        if not any(f.endswith(('.py', '.js')) for f in root_files):
            for root, dirs, files in os.walk(temp_dir):
                dirs[:] = [d for d in dirs if not d.startswith('.') and not d.startswith('__')]
                if any(f.endswith(('.py', '.js')) for f in files):
                    target_dir = root
                    break
        
        if target_dir != temp_dir:
            for item in os.listdir(target_dir):
                s = os.path.join(target_dir, item)
                d = os.path.join(temp_dir, item)
                if os.path.exists(d):
                    if os.path.isdir(d): shutil.rmtree(d)
                    else: os.remove(d)
                shutil.move(s, d)
            extracted_items = os.listdir(temp_dir)
        else:
            extracted_items = root_files

        py_files = [f for f in extracted_items if f.endswith('.py')]
        js_files = [f for f in extracted_items if f.endswith('.js')]
        req_file = 'requirements.txt' if 'requirements.txt' in extracted_items else None
        pkg_json = 'package.json' if 'package.json' in extracted_items else None

        if user_id not in admin_ids:
            main_script_name = None
            file_type = None
            preferred_py = ['main.py', 'bot.py', 'app.py']
            preferred_js = ['index.js', 'main.js', 'bot.js', 'app.js']
            for p in preferred_py:
                if p in py_files:
                    main_script_name = p
                    file_type = 'py'
                    break
            if not main_script_name:
                for p in preferred_js:
                    if p in js_files:
                        main_script_name = p
                        file_type = 'js'
                        break
            if not main_script_name:
                if py_files:
                    main_script_name = py_files[0]
                    file_type = 'py'
                elif js_files:
                    main_script_name = js_files[0]
                    file_type = 'js'
            
            if not main_script_name:
                bot.reply_to(message, "❌ No `.py` or `.js` found!")
                return
            
            for item_name in os.listdir(temp_dir):
                if item_name == file_name_zip: continue
                src_path = os.path.join(temp_dir, item_name)
                dest_path = os.path.join(user_folder, item_name)
                if os.path.isdir(dest_path): shutil.rmtree(dest_path)
                elif os.path.exists(dest_path): os.remove(dest_path)
                shutil.move(src_path, dest_path)
            
            main_script_path = os.path.join(user_folder, main_script_name)
            approval_msg = bot.send_message(
                message.chat.id,
                f"📤 File `{file_name_zip}` uploaded for approval.\n"
                f"Main: `{main_script_name}`\n"
                f"⏳ Waiting for admin approval."
            )
            
            file_id = save_pending_file_to_db(user_id, main_script_name, main_script_path, file_type, approval_msg.message_id)
            notify_admins_about_pending(user_id, main_script_name, file_type, file_id, file_name_zip)
            return
        
        if req_file:
            req_path = os.path.join(temp_dir, req_file)
            bot.reply_to(message, f"🔄 Installing Python deps...")
            try:
                command = [sys.executable, '-m', 'pip', 'install', '-r', req_path]
                result = subprocess.run(command, capture_output=True, text=True, check=True, encoding='utf-8', errors='ignore')
                bot.reply_to(message, f"✅ Python deps installed.")
            except Exception as e:
                bot.reply_to(message, f"❌ Deps failed: {e}")
                return

        if pkg_json:
            bot.reply_to(message, f"🔄 Installing Node deps...")
            try:
                command = ['npm', 'install']
                result = subprocess.run(command, capture_output=True, text=True, check=True, cwd=temp_dir, encoding='utf-8', errors='ignore')
                bot.reply_to(message, f"✅ Node deps installed.")
            except Exception as e:
                bot.reply_to(message, f"❌ Deps failed: {e}")
                return

        main_script_name = None; file_type = None
        preferred_py = ['main.py', 'bot.py', 'app.py']; preferred_js = ['index.js', 'main.js', 'bot.js', 'app.js']
        for p in preferred_py:
            if p in py_files: main_script_name = p; file_type = 'py'; break
        if not main_script_name:
            for p in preferred_js:
                if p in js_files: main_script_name = p; file_type = 'js'; break
        if not main_script_name:
            if py_files: main_script_name = py_files[0]; file_type = 'py'
            elif js_files: main_script_name = js_files[0]; file_type = 'js'
        if not main_script_name:
            bot.reply_to(message, "❌ No `.py` or `.js` found!"); return

        for item_name in os.listdir(temp_dir):
            if item_name == file_name_zip: continue
            src_path = os.path.join(temp_dir, item_name)
            dest_path = os.path.join(user_folder, item_name)
            if os.path.isdir(dest_path): shutil.rmtree(dest_path)
            elif os.path.exists(dest_path): os.remove(dest_path)
            shutil.move(src_path, dest_path)

        save_user_file(user_id, main_script_name, file_type)
        main_script_path = os.path.join(user_folder, main_script_name)
        bot.reply_to(message, f"✅ Files extracted. Starting `{main_script_name}`...", parse_mode='Markdown')

        if file_type == 'py':
            threading.Thread(target=run_script, args=(main_script_path, user_id, user_folder, main_script_name, message)).start()
        elif file_type == 'js':
            threading.Thread(target=run_js_script, args=(main_script_path, user_id, user_folder, main_script_name, message)).start()

    except zipfile.BadZipFile as e:
        bot.reply_to(message, f"❌ Invalid ZIP. {e}")
    except Exception as e:
        logger.error(f"❌ Error zip: {e}", exc_info=True)
        bot.reply_to(message, f"❌ Error: {str(e)}")
    finally:
        if temp_dir and os.path.exists(temp_dir):
            try: shutil.rmtree(temp_dir)
            except: pass

def handle_js_file(file_path, script_owner_id, user_folder, file_name, message):
    try:
        if script_owner_id not in admin_ids:
            file_id = save_pending_file_to_db(script_owner_id, file_name, file_path, 'js', message.message_id)
            notify_admins_about_pending(script_owner_id, file_name, 'js', file_id, file_name)
            bot.reply_to(message, f"📤 `{file_name}` uploaded for approval.")
            return
        save_user_file(script_owner_id, file_name, 'js')
        threading.Thread(target=run_js_script, args=(file_path, script_owner_id, user_folder, file_name, message)).start()
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

def handle_py_file(file_path, script_owner_id, user_folder, file_name, message):
    try:
        if script_owner_id not in admin_ids:
            file_id = save_pending_file_to_db(script_owner_id, file_name, file_path, 'py', message.message_id)
            notify_admins_about_pending(script_owner_id, file_name, 'py', file_id, file_name)
            bot.reply_to(message, f"📤 `{file_name}` uploaded for approval.")
            return
        save_user_file(script_owner_id, file_name, 'py')
        threading.Thread(target=run_script, args=(file_path, script_owner_id, user_folder, file_name, message)).start()
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

def notify_admins_about_pending(user_id, file_name, file_type, file_id, original_file_name):
    pending_count = get_pending_files_count()
    for admin_id in admin_ids:
        try:
            if admin_id != user_id:
                markup = types.InlineKeyboardMarkup(row_width=2)
                markup.row(
                    types.InlineKeyboardButton("✅ ᴀᴘᴘʀᴏᴠᴇ", callback_data=f'approve_{file_id}'),
                    types.InlineKeyboardButton("❌ ʀᴇᴊᴇᴄᴛ", callback_data=f'reject_{file_id}')
                )
                markup.row(types.InlineKeyboardButton("📥 ᴀʟʟ ᴘᴇɴᴅɪɴɢ", callback_data='pending_approvals'))
                
                bot.send_message(
                    admin_id,
                    f"📥 New file awaiting approval!\n\n"
                    f"👤 User: `{user_id}`\n"
                    f"📁 File: `{file_name}`\n"
                    f"📂 Type: {file_type.upper()}\n"
                    f"📊 Total Pending: {pending_count}",
                    parse_mode='Markdown',
                    reply_markup=markup
                )
        except Exception as e:
            logger.error(f"Failed to notify admin {admin_id}: {e}")

def _logic_pending_approvals(message):
    user_id = message.from_user.id
    if user_id not in admin_ids:
        bot.reply_to(message, "⚠️ Admin permissions required.")
        return
    
    pending_list = get_pending_files_for_admin()
    
    if not pending_list:
        bot.reply_to(message, "📥 No pending approvals.")
        return
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    for file_id, user_id_pending, file_name, file_type, timestamp in pending_list:
        try:
            ts = datetime.fromisoformat(timestamp) if timestamp else datetime.now()
            time_str = ts.strftime("%Y-%m-%d %H:%M")
        except:
            time_str = "Unknown"
        btn_text = f"{file_name} ({file_type.upper()}) - User: {user_id_pending}"
        markup.add(types.InlineKeyboardButton(btn_text, callback_data=f'view_pending_{file_id}'))
    
    markup.add(types.InlineKeyboardButton("🔙 Back", callback_data='back_to_main'))
    bot.reply_to(message, f"📥 Pending Approvals ({len(pending_list)}):", reply_markup=markup)

def view_pending_file_details(call):
    try:
        file_id = int(call.data.split('_')[2])
        pending_file = get_pending_file_by_id(file_id)
        
        if not pending_file:
            bot.answer_callback_query(call.id, "File no longer pending.", show_alert=True)
            _logic_pending_approvals(call.message)
            return
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.row(
            types.InlineKeyboardButton("✅ Approve", callback_data=f'approve_{file_id}'),
            types.InlineKeyboardButton("❌ Reject", callback_data=f'reject_{file_id}')
        )
        
        bot.edit_message_text(
            f"📄 Pending File\n\n"
            f"🆔 File ID: `{file_id}`\n"
            f"👤 Uploader: `{pending_file['user_id']}`\n"
            f"📁 File: `{pending_file['file_name']}`\n"
            f"📂 Type: {pending_file['file_type'].upper()}",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown',
            reply_markup=markup
        )
        bot.answer_callback_query(call.id)
    except Exception as e:
        bot.answer_callback_query(call.id, "Error.")

def approve_pending_file(call):
    try:
        file_id = int(call.data.split('_')[1])
        admin_id = call.from_user.id
        
        if admin_id not in admin_ids:
            bot.answer_callback_query(call.id, "⚠️ Admin required.", show_alert=True)
            return
        
        pending_file = get_pending_file_by_id(file_id)
        if not pending_file:
            bot.answer_callback_query(call.id, "Not pending.", show_alert=True)
            return
        
        user_id = pending_file['user_id']
        file_name = pending_file['file_name']
        file_path = pending_file['file_path']
        file_type = pending_file['file_type']
        
        update_pending_file_status(file_id, 'approved')
        save_user_file(user_id, file_name, file_type)
        
        user_folder = get_user_folder(user_id)
        if file_type == 'py':
            threading.Thread(target=run_script, args=(file_path, user_id, user_folder, file_name, call.message)).start()
        elif file_type == 'js':
            threading.Thread(target=run_js_script, args=(file_path, user_id, user_folder, file_name, call.message)).start()
        
        try:
            bot.send_message(user_id, f"✅ Your file `{file_name}` approved!")
        except: pass
        
        bot.answer_callback_query(call.id, f"✅ Approved!")
        _logic_pending_approvals(call.message)
    except Exception as e:
        bot.answer_callback_query(call.id, f"Error: {str(e)}", show_alert=True)

def reject_pending_file(call):
    try:
        file_id = int(call.data.split('_')[1])
        admin_id = call.from_user.id
        
        if admin_id not in admin_ids:
            bot.answer_callback_query(call.id, "⚠️ Admin required.", show_alert=True)
            return
        
        pending_file = get_pending_file_by_id(file_id)
        if not pending_file:
            bot.answer_callback_query(call.id, "Not pending.", show_alert=True)
            return
        
        user_id = pending_file['user_id']
        file_name = pending_file['file_name']
        file_path = pending_file['file_path']
        
        update_pending_file_status(file_id, 'rejected')
        
        if os.path.exists(file_path):
            try: os.remove(file_path)
            except: pass
        
        try:
            bot.send_message(user_id, f"❌ Your file `{file_name}` rejected.")
        except: pass
        
        bot.answer_callback_query(call.id, f"❌ Rejected!")
        _logic_pending_approvals(call.message)
    except Exception as e:
        bot.answer_callback_query(call.id, f"Error: {str(e)}", show_alert=True)

# --- Toggle Auto-Approve Functions ---
def _logic_toggle_auto_approve(message_or_call):
    """Toggle auto-approve mode"""
    if isinstance(message_or_call, telebot.types.Message):
        user_id = message_or_call.from_user.id
        chat_id = message_or_call.chat.id
        reply_func = lambda text, **kwargs: bot.reply_to(message_or_call, text, **kwargs)
        edit_func = None
        msg_id = None
    else:
        user_id = message_or_call.from_user.id
        chat_id = message_or_call.message.chat.id
        reply_func = lambda text, **kwargs: bot.send_message(chat_id, text, **kwargs)
        edit_func = lambda text, **kwargs: bot.edit_message_text(text, chat_id, message_or_call.message.message_id, **kwargs)
        msg_id = message_or_call.message.message_id
        bot.answer_callback_query(message_or_call.id)
    
    if user_id not in admin_ids:
        reply_func("⚠️ Admin permissions required.")
        return
    
    new_status = toggle_auto_approve()
    
    if new_status:
        status_text = "🟢 ᴇɴᴀʙʟᴇᴅ"
        desc = "ᴜꜱᴇʀꜱ ᴡɪʟʟ ɢᴇᴛ ɪɴꜱᴛᴀɴᴛ ᴀᴄᴄᴇꜱꜱ ᴀꜰᴛᴇʀ ᴇɴᴛᴇʀɪɴɢ ᴛʜᴇ ᴄᴏʀʀᴇᴄᴛ ᴘᴀꜱꜱᴡᴏʀᴅ."
        # Auto-approve existing pending users
        auto_approved_count = 0
        if pending_auth_users:
            pending_ids = list(pending_auth_users.keys())
            for uid in pending_ids:
                save_authenticated_user(uid)
                pending_auth_users.pop(uid, None)
                auto_approved_count += 1
                try:
                    bot.send_message(uid, "🎉 Your access has been approved!")
                except: pass
        extra = f"\n\n✅ ᴀᴜᴛᴏ-ᴀᴘᴘʀᴏᴠᴇᴅ {auto_approved_count} ᴘᴇɴᴅɪɴɢ ᴜꜱᴇʀꜱ" if auto_approved_count > 0 else ""
    else:
        status_text = "🔴 ᴅɪꜱᴀʙʟᴇᴅ"
        desc = "ᴜꜱᴇʀꜱ ᴡɪʟʟ ɴᴇᴇᴅ ᴍᴀɴᴜᴀʟ ᴀᴘᴘʀᴏᴠᴀʟ ꜰʀᴏᴍ ᴀᴅᴍɪɴꜱ."
        extra = ""
    
    result_text = f"""
{EMOJI_HEADER}
   ⚙️ ᴀᴜᴛᴏ-ᴀᴘᴘʀᴏᴠᴇ ᴛᴏɢɢʟᴇᴅ
{EMOJI_FOOTER}

📊 ɴᴇᴡ ꜱᴛᴀᴛᴜꜱ: {status_text}

{DIVIDER_THIN}

📝 {desc}{extra}

{DIVIDER}

💡 ꜱᴇᴛᴛɪɴɢ ꜱᴀᴠᴇᴅ ᴀɴᴅ ᴡɪʟʟ ᴘᴇʀꜱɪꜱᴛ ᴀꜰᴛᴇʀ ʀᴇꜱᴛᴀʀᴛ.
"""
    
    if edit_func:
        try:
            edit_func(result_text, parse_mode='Markdown')
        except Exception as e:
            reply_func(result_text, parse_mode='Markdown')
    else:
        reply_func(result_text, parse_mode='Markdown')

def _logic_auth_status(message):
    """Show current auth status"""
    if message.from_user.id not in admin_ids:
        bot.reply_to(message, "⚠️ Admin permissions required.")
        return
    
    auto_status = "🟢 ᴇɴᴀʙʟᴇᴅ" if get_auto_approve_status() else "🔴 ᴅɪꜱᴀʙʟᴇᴅ"
    pending_count = len(pending_auth_users)
    authed_count = len(authenticated_users)
    
    bot.reply_to(message, f"""
{EMOJI_HEADER}
   🔐 ᴀᴜᴛʜ ꜱᴛᴀᴛᴜꜱ
{EMOJI_FOOTER}

⚙️ ᴀᴜᴛᴏ-ᴀᴘᴘʀᴏᴠᴇ: {auto_status}
📥 ᴘᴇɴᴅɪɴɢ ʀᴇQᴜᴇꜱᴛꜱ: {pending_count}
✅ ᴀᴜᴛʜᴇɴᴛɪᴄᴀᴛᴇᴅ ᴜꜱᴇʀꜱ: {authed_count}

{DIVIDER_THIN}

💡 ᴜꜱᴇ /autoauth ᴛᴏ ᴛᴏɢɢʟᴇ
💡 ᴜꜱᴇ /authrequests ᴛᴏ ᴠɪᴇᴡ ᴘᴇɴᴅɪɴɢ

{DIVIDER}
""")

# --- Send Command ---
def _logic_send_command(message):
    user_id = message.from_user.id
    if bot_locked and user_id not in admin_ids:
        bot.reply_to(message, "⚠️ Bot locked.")
        return
    bot.reply_to(message, "📤 Send Command:", reply_markup=create_send_command_menu())

def send_to_process_init(message):
    user_id = message.from_user.id
    user_running_scripts = []
    for script_key, script_info in bot_scripts.items():
        script_owner_id = script_info['script_owner_id']
        if (user_id == script_owner_id or user_id in admin_ids) and is_bot_running(script_owner_id, script_info['file_name']):
            user_running_scripts.append((script_key, script_info))
    
    if not user_running_scripts:
        bot.reply_to(message, "❌ No running scripts.")
        return
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    for script_key, script_info in user_running_scripts:
        btn_text = f"{script_info['file_name']} (User: {script_info['script_owner_id']})"
        markup.add(types.InlineKeyboardButton(btn_text, callback_data=f'sendcmd_select_{script_key}'))
    
    markup.add(types.InlineKeyboardButton("🔙 Back", callback_data='send_command'))
    bot.reply_to(message, "📝 Select script:", reply_markup=markup)

def process_send_command(message, script_key):
    if script_key not in bot_scripts:
        bot.reply_to(message, "❌ Script not running.")
        return
    script_info = bot_scripts[script_key]
    command_text = message.text
    try:
        process = script_info['process']
        if process and process.poll() is None:
            process.stdin.write(command_text + '\n')
            process.stdin.flush()
            bot.reply_to(message, f"✅ Command sent to `{script_info['file_name']}`", parse_mode='Markdown')
        else:
            bot.reply_to(message, f"❌ Not running.")
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

def view_all_logs(message):
    user_id = message.from_user.id
    user_logs = []
    user_folder = get_user_folder(user_id)
    if os.path.exists(user_folder):
        for file in os.listdir(user_folder):
            if file.endswith('.log'):
                log_path = os.path.join(user_folder, file)
                file_size = os.path.getsize(log_path)
                user_logs.append((file, file_size, log_path))
    
    if not user_logs:
        bot.reply_to(message, "📜 No logs found.")
        return
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    for log_file, size, log_path in sorted(user_logs):
        btn_text = f"{log_file} ({size/1024:.1f} KB)"
        markup.add(types.InlineKeyboardButton(btn_text, callback_data=f'viewlog_{user_id}_{log_file}'))
    
    markup.add(types.InlineKeyboardButton("🔙 Back", callback_data='send_command'))
    bot.reply_to(message, "📜 Logs:", reply_markup=markup)

def send_log_file(message, log_path, log_filename):
    try:
        file_size = os.path.getsize(log_path)
        if file_size > 50 * 1024 * 1024:
            bot.reply_to(message, f"❌ Too large.")
            return
        with open(log_path, 'rb') as log_file:
            bot.send_document(message.chat.id, log_file, caption=f"📜 {log_filename}")
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

# --- Welcome Logic ---
def _logic_send_welcome(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    user_name = message.from_user.first_name
    user_username = message.from_user.username

    logger.info(f"Welcome request from {user_id}")

    # 🔐 PASSWORD CHECK
    if PASSWORD_REQUIRED and user_id not in admin_ids:
        if not is_user_authenticated(user_id):
            if user_id in pending_auth_users:
                bot.send_message(chat_id, f"""
{EMOJI_HEADER}
   ⏳ ᴀᴄᴄᴇꜱꜱ ᴘᴇɴᴅɪɴɢ
{EMOJI_FOOTER}

ᴛʜᴀɴᴋ ʏᴏᴜ ꜰᴏʀ ᴇɴᴛᴇʀɪɴɢ ᴛʜᴇ ᴘᴀꜱꜱᴡᴏʀᴅ!

ᴘʟᴇᴀꜱᴇ ᴡᴀɪᴛ ꜰᴏʀ ᴛʜᴇ ᴏᴡɴᴇʀ ᴛᴏ ᴀᴘᴘʀᴏᴠᴇ.

{DIVIDER}
""")
                return
            else:
                send_password_prompt(chat_id, user_name)
                return

    if bot_locked and user_id not in admin_ids:
        bot.send_message(chat_id, "⚠️ Bot locked.")
        return

    if user_id not in active_users:
        add_active_user(user_id)
        try:
            owner_notification = (f"🎉 New user!\n👤 {user_name}\n✳️ @{user_username or 'N/A'}\n"
                                  f"🆔 `{user_id}`")
            bot.send_message(OWNER_ID, owner_notification, parse_mode='Markdown')
        except Exception as e: logger.error(f"Error: {e}")

    file_limit = get_user_file_limit(user_id)
    current_files = get_user_file_count(user_id)
    limit_str = str(file_limit) if file_limit != float('inf') else "Unlimited"
    expiry_info = ""
    if user_id == OWNER_ID: user_status = "👑 ᴏᴡɴᴇʀ"
    elif user_id in admin_ids: user_status = "⭐ ᴀᴅᴍɪɴ"
    elif user_id in user_subscriptions:
        expiry_date = user_subscriptions[user_id].get('expiry')
        if expiry_date and expiry_date > datetime.now():
            user_status = "💎 ᴘʀᴇᴍɪᴜᴍ"; days_left = (expiry_date - datetime.now()).days
            expiry_info = f"\n⏳ ᴇxᴘɪʀᴇꜱ ɪɴ: {days_left} ᴅᴀʏꜱ"
        else: user_status = "🆓 ꜰʀᴇᴇ"; remove_subscription_db(user_id)
    else: user_status = "🆓 ꜰʀᴇᴇ ᴜꜱᴇʀ"

    pending_count = get_pending_files_count()
    pending_msg = f"\n📥 ᴘᴇɴᴅɪɴɢ: {pending_count}" if user_id in admin_ids and pending_count > 0 else ""
    auto_msg = ""
    if user_id in admin_ids:
        auto_msg = f"\n⚙️ ᴀᴜᴛᴏ-ᴀᴘᴘʀᴏᴠᴇ: {'🟢 ᴏɴ' if get_auto_approve_status() else '🔴 ᴏꜰꜰ'}"

    welcome_msg_text = f"""
{EMOJI_HEADER}
   🌟 ᴡᴇʟᴄᴏᴍᴇ {user_name}!
{EMOJI_FOOTER}

🆔 ʏᴏᴜʀ ɪᴅ: `{user_id}`
✳️ ᴜꜱᴇʀɴᴀᴍᴇ: `@{user_username or 'Not set'}`
🔰 ꜱᴛᴀᴛᴜꜱ: {user_status}{expiry_info}
📁 ꜰɪʟᴇꜱ: {current_files} / {limit_str}{pending_msg}{auto_msg}

{DIVIDER_THIN}

🤖 ʜᴏꜱᴛ ᴘʏᴛʜᴏɴ (`.py`) ᴏʀ ᴊꜱ (`.js`)
📦 ᴜᴘʟᴏᴀᴅ ꜱɪɴɢʟᴇ ᴏʀ `.zip`

{DIVIDER_THIN}

👇 ᴜꜱᴇ ʙᴜᴛᴛᴏɴꜱ ᴏʀ ᴛʏᴘᴇ ᴄᴏᴍᴍᴀɴᴅꜱ

{DIVIDER}
"""
    main_reply_markup = create_reply_keyboard_main_menu(user_id)
    try:
        bot.send_message(chat_id, welcome_msg_text, reply_markup=main_reply_markup, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        try: bot.send_message(chat_id, welcome_msg_text, reply_markup=main_reply_markup, parse_mode='Markdown')
        except Exception as fallback_e: logger.error(f"Fallback failed: {fallback_e}")

def _logic_updates_channel(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton('📢 Channel', url=UPDATE_CHANNEL))
    bot.reply_to(message, "Visit Updates Channel:", reply_markup=markup)

def _logic_upload_file(message):
    user_id = message.from_user.id
    if bot_locked and user_id not in admin_ids:
        bot.reply_to(message, "⚠️ Bot locked.")
        return
    file_limit = get_user_file_limit(user_id)
    current_files = get_user_file_count(user_id)
    if current_files >= file_limit:
        limit_str = str(file_limit) if file_limit != float('inf') else "Unlimited"
        bot.reply_to(message, f"⚠️ Limit ({current_files}/{limit_str}).")
        return
    if user_id in admin_ids:
        bot.reply_to(message, "📤 Send `.py`, `.js`, or `.zip`.\n✅ Auto-approved.")
    else:
        bot.reply_to(message, "📤 Send `.py`, `.js`, or `.zip`.\n⏳ Needs admin approval.")

def _logic_check_files(message):
    user_id = message.from_user.id
    user_files_list = user_files.get(user_id, [])
    if not user_files_list:
        bot.reply_to(message, "📂 No files uploaded.")
        return
    markup = types.InlineKeyboardMarkup(row_width=1)
    for file_name, file_type in sorted(user_files_list):
        is_running = is_bot_running(user_id, file_name)
        status_icon = "🟢" if is_running else "🔴"
        btn_text = f"{status_icon} {file_name} ({file_type})"
        markup.add(types.InlineKeyboardButton(btn_text, callback_data=f'file_{user_id}_{file_name}'))
    bot.reply_to(message, "📂 Your files:", reply_markup=markup)

def _logic_bot_speed(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    start_time_ping = time.time()
    wait_msg = bot.reply_to(message, "🏃 Testing...")
    try:
        bot.send_chat_action(chat_id, 'typing')
        response_time = round((time.time() - start_time_ping) * 1000, 2)
        status = "🔓" if not bot_locked else "🔒"
        if user_id == OWNER_ID: user_level = "👑 Owner"
        elif user_id in admin_ids: user_level = "⭐ Admin"
        elif user_id in user_subscriptions and user_subscriptions[user_id].get('expiry', datetime.min) > datetime.now(): user_level = "💎 Premium"
        else: user_level = "🆓 Free"
        speed_msg = (f"⚡ Bot Speed:\n\n⏱️ {response_time} ms\n"
                     f"🚦 {status}\n"
                     f"👤 {user_level}")
        bot.edit_message_text(speed_msg, chat_id, wait_msg.message_id)
    except Exception as e:
        bot.edit_message_text("❌ Error.", chat_id, wait_msg.message_id)

def _logic_contact_owner(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton('📞 Contact', url=f'https://t.me/{YOUR_USERNAME.replace("@", "")}'))
    bot.reply_to(message, "Contact Owner:", reply_markup=markup)

# --- Admin Logic ---
def _logic_subscriptions_panel(message):
    if message.from_user.id not in admin_ids:
        bot.reply_to(message, "⚠️ Admin only.")
        return
    bot.reply_to(message, "💳 Subscriptions", reply_markup=create_subscription_menu())

def _logic_statistics(message):
    user_id = message.from_user.id
    total_users = len(active_users)
    total_files_records = sum(len(files) for files in user_files.values())
    pending_count = get_pending_files_count()
    running_bots_count = 0
    user_running_bots = 0
    for script_key_iter, script_info_iter in list(bot_scripts.items()):
        try:
            s_owner_id = script_info_iter['script_owner_id']
            if is_bot_running(s_owner_id, script_info_iter['file_name']):
                running_bots_count += 1
                if s_owner_id == user_id: user_running_bots += 1
        except: continue
    stats_msg = (f"📊 Statistics:\n\n"
                 f"👥 Users: {total_users}\n"
                 f"📂 Files: {total_files_records}\n"
                 f"🟢 Running: {running_bots_count}\n"
                 f"📥 Pending: {pending_count}\n")
    if user_id in admin_ids:
        stats_msg += (f"🔒 Bot: {'Locked' if bot_locked else 'Unlocked'}\n"
                      f"⚙️ Auto-Approve: {'🟢 ON' if get_auto_approve_status() else '🔴 OFF'}\n"
                      f"🔐 Authed: {len(authenticated_users)}\n"
                      f"📥 Auth Pending: {len(pending_auth_users)}\n"
                      f"🤖 Your Bots: {user_running_bots}")
    else:
        stats_msg += f"🤖 Your Bots: {user_running_bots}"
    bot.reply_to(message, stats_msg)

def _logic_broadcast_init(message):
    if message.from_user.id not in admin_ids:
        bot.reply_to(message, "⚠️ Admin only.")
        return
    msg = bot.reply_to(message, "📢 Send message to broadcast.\n/cancel to abort.")
    bot.register_next_step_handler(msg, process_broadcast_message)

def _logic_toggle_lock_bot(message):
    if message.from_user.id not in admin_ids:
        bot.reply_to(message, "⚠️ Admin only.")
        return
    global bot_locked
    bot_locked = not bot_locked
    status = "locked" if bot_locked else "unlocked"
    bot.reply_to(message, f"🔒 Bot {status}.")

def _logic_admin_panel(message):
    if message.from_user.id not in admin_ids:
        bot.reply_to(message, "⚠️ Admin only.")
        return
    bot.reply_to(message, "👑 Admin Panel", reply_markup=create_admin_panel())

def _logic_run_all_scripts(message_or_call):
    if isinstance(message_or_call, telebot.types.Message):
        admin_user_id = message_or_call.from_user.id
        admin_chat_id = message_or_call.chat.id
        reply_func = lambda text, **kwargs: bot.reply_to(message_or_call, text, **kwargs)
        admin_message_obj = message_or_call
    elif isinstance(message_or_call, telebot.types.CallbackQuery):
        admin_user_id = message_or_call.from_user.id
        admin_chat_id = message_or_call.message.chat.id
        bot.answer_callback_query(message_or_call.id)
        reply_func = lambda text, **kwargs: bot.send_message(admin_chat_id, text, **kwargs)
        admin_message_obj = message_or_call.message
    else: return

    if admin_user_id not in admin_ids:
        reply_func("⚠️ Admin only.")
        return

    reply_func("⏳ Starting all scripts...")
    started_count = 0; attempted_users = 0; skipped_files = 0
    for target_user_id, files_for_user in dict(user_files).items():
        if not files_for_user: continue
        attempted_users += 1
        user_folder = get_user_folder(target_user_id)
        for file_name, file_type in files_for_user:
            if not is_bot_running(target_user_id, file_name):
                file_path = os.path.join(user_folder, file_name)
                if os.path.exists(file_path):
                    try:
                        if file_type == 'py':
                            threading.Thread(target=run_script, args=(file_path, target_user_id, user_folder, file_name, admin_message_obj)).start()
                            started_count += 1
                        elif file_type == 'js':
                            threading.Thread(target=run_js_script, args=(file_path, target_user_id, user_folder, file_name, admin_message_obj)).start()
                            started_count += 1
                        time.sleep(0.7)
                    except: skipped_files += 1
                else: skipped_files += 1
    reply_func(f"✅ Done:\n▶️ Started: {started_count}\n👥 Users: {attempted_users}\n⚠️ Skipped: {skipped_files}")

# --- Command Handlers ---
@bot.message_handler(commands=['start', 'help'])
def command_send_welcome(message): _logic_send_welcome(message)

@bot.message_handler(commands=['myid'])
def command_my_id(message):
    bot.reply_to(message, f"🆔 Your ID: `{message.from_user.id}`\nOwner: `{OWNER_ID}`", parse_mode='Markdown')

@bot.message_handler(commands=['status'])
def command_show_status(message): _logic_statistics(message)

@bot.message_handler(commands=['autoauth'])
def command_toggle_auto_approve(message): _logic_toggle_auto_approve(message)

@bot.message_handler(commands=['authstatus'])
def command_auth_status(message): _logic_auth_status(message)

BUTTON_TEXT_TO_LOGIC = {
    "📢 Updates Channel": _logic_updates_channel,
    "📤 Upload File": _logic_upload_file,
    "📂 Check Files": _logic_check_files,
    "⚡ Bot Speed": _logic_bot_speed,
    "📤 Send Command": _logic_send_command,
    "📞 Contact Owner": _logic_contact_owner,
    "📊 Statistics": _logic_statistics,
    "💳 Subscriptions": _logic_subscriptions_panel,
    "📢 Broadcast": _logic_broadcast_init,
    "🔒 Lock Bot": _logic_toggle_lock_bot,
    "🟢 Running All Code": _logic_run_all_scripts,
    "👑 Admin Panel": _logic_admin_panel,
    "📥 Pending Approvals": _logic_pending_approvals,
    "🔐 Auth Requests": show_auth_requests,
    "⚙️ Auto-Approve": _logic_toggle_auto_approve,
}

@bot.message_handler(func=lambda message: message.text in BUTTON_TEXT_TO_LOGIC)
def handle_button_text(message):
    logic_func = BUTTON_TEXT_TO_LOGIC.get(message.text)
    if logic_func: logic_func(message)

@bot.message_handler(commands=['updateschannel'])
def command_updates_channel(message): _logic_updates_channel(message)
@bot.message_handler(commands=['uploadfile'])
def command_upload_file(message): _logic_upload_file(message)
@bot.message_handler(commands=['checkfiles'])
def command_check_files(message): _logic_check_files(message)
@bot.message_handler(commands=['botspeed'])
def command_bot_speed(message): _logic_bot_speed(message)
@bot.message_handler(commands=['sendcommand'])
def command_send_command(message): _logic_send_command(message)
@bot.message_handler(commands=['contactowner'])
def command_contact_owner(message): _logic_contact_owner(message)
@bot.message_handler(commands=['subscriptions'])
def command_subscriptions(message): _logic_subscriptions_panel(message)
@bot.message_handler(commands=['statistics'])
def command_statistics(message): _logic_statistics(message)
@bot.message_handler(commands=['broadcast'])
def command_broadcast(message): _logic_broadcast_init(message)
@bot.message_handler(commands=['lockbot'])
def command_lock_bot(message): _logic_toggle_lock_bot(message)
@bot.message_handler(commands=['adminpanel'])
def command_admin_panel(message): _logic_admin_panel(message)
@bot.message_handler(commands=['runningallcode'])
def command_run_all_code(message): _logic_run_all_scripts(message)
@bot.message_handler(commands=['pendingapprovals'])
def command_pending_approvals(message): _logic_pending_approvals(message)
@bot.message_handler(commands=['authrequests'])
def command_auth_requests(message): show_auth_requests(message)

@bot.message_handler(commands=['ping'])
def ping(message):
    start_ping_time = time.time()
    msg = bot.reply_to(message, "Pong!")
    latency = round((time.time() - start_ping_time) * 1000, 2)
    bot.edit_message_text(f"Pong! Latency: {latency} ms", message.chat.id, msg.message_id)

# --- Password Entry Handler ---
@bot.message_handler(func=lambda message: 
                     PASSWORD_REQUIRED and 
                     message.from_user.id not in admin_ids and 
                     not is_user_authenticated(message.from_user.id) and
                     message.from_user.id not in pending_auth_users and
                     message.content_type == 'text' and
                     message.text and
                     not message.text.startswith('/'),
                     content_types=['text'])
def handle_password_entry(message):
    process_password_entry(message)

# --- Document Handler ---
@bot.message_handler(content_types=['document'])
def handle_file_upload_doc(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    doc = message.document

    if PASSWORD_REQUIRED and user_id not in admin_ids and not is_user_authenticated(user_id):
        bot.reply_to(message, "🔐 Please authenticate. Send /start.")
        return

    if bot_locked and user_id not in admin_ids:
        bot.reply_to(message, "⚠️ Bot locked.")
        return

    file_limit = get_user_file_limit(user_id)
    current_files = get_user_file_count(user_id)
    if current_files >= file_limit:
        bot.reply_to(message, f"⚠️ Limit reached.")
        return

    file_name = doc.file_name
    if not file_name: 
        bot.reply_to(message, "⚠️ No filename.")
        return
    file_ext = os.path.splitext(file_name)[1].lower()
    if file_ext not in ['.py', '.js', '.zip']:
        bot.reply_to(message, "⚠️ Only `.py`, `.js`, `.zip`.")
        return
    if doc.file_size > 20 * 1024 * 1024:
        bot.reply_to(message, f"⚠️ Too large (max 20MB).")
        return

    try:
        try: bot.forward_message(OWNER_ID, chat_id, message.message_id)
        except: pass

        download_wait_msg = bot.reply_to(message, f"⏳ Downloading...")
        file_info_tg_doc = bot.get_file(doc.file_id)
        downloaded_file_content = bot.download_file(file_info_tg_doc.file_path)
        
        if user_id != OWNER_ID:
            is_safe, reason = scan_file_for_malware(downloaded_file_content, file_name, user_id)
            if not is_safe:
                bot.edit_message_text(f"🚨 Security: {reason}", chat_id, download_wait_msg.message_id)
                return
        
        bot.edit_message_text(f"✅ Downloaded. Processing...", chat_id, download_wait_msg.message_id)
        user_folder = get_user_folder(user_id)

        if file_ext == '.zip':
            handle_zip_file(downloaded_file_content, file_name, message)
        else:
            file_path = os.path.join(user_folder, file_name)
            with open(file_path, 'wb') as f: f.write(downloaded_file_content)
            if file_ext == '.js': handle_js_file(file_path, user_id, user_folder, file_name, message)
            elif file_ext == '.py': handle_py_file(file_path, user_id, user_folder, file_name, message)
    except telebot.apihelper.ApiTelegramException as e:
        bot.reply_to(message, f"❌ Telegram Error: {str(e)}")
    except Exception as e:
        logger.error(f"❌ Error: {e}", exc_info=True)
        bot.reply_to(message, f"❌ Error: {str(e)}")

# --- Callback Query Handlers ---
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    user_id = call.from_user.id
    data = call.data
    logger.info(f"Callback: User={user_id}, Data='{data}'")

    if data == "enter_password":
        bot.answer_callback_query(call.id)
        try:
            bot.send_message(call.message.chat.id, f"""
{EMOJI_HEADER}
   🔐 ᴇɴᴛᴇʀ ᴘᴀꜱꜱᴡᴏʀᴅ
{EMOJI_FOOTER}

📝 ᴛʏᴘᴇ ᴛʜᴇ ᴘᴀꜱꜱᴡᴏʀᴅ ʙᴇʟᴏᴡ:

{DIVIDER_THIN}

💡 ᴄᴀꜱᴇ-ꜱᴇɴꜱɪᴛɪᴠᴇ

{DIVIDER}
""")
        except Exception as e:
            logger.error(f"Error: {e}")
        return

    if data.startswith('auth_approve_'):
        approve_user_auth(call); return
    if data.startswith('auth_reject_'):
        reject_user_auth(call); return
    if data == 'auth_requests':
        show_auth_requests(call); return
    if data == 'toggle_auto_approve':
        _logic_toggle_auto_approve(call)
        # Refresh the menu
        try:
            bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id,
                                         reply_markup=create_main_menu_inline(call.from_user.id))
        except Exception as e:
            logger.error(f"Error refreshing menu: {e}")
        return

    if bot_locked and user_id not in admin_ids and data not in ['back_to_main', 'speed', 'stats']:
        bot.answer_callback_query(call.id, "⚠️ Bot locked.", show_alert=True)
        return
    
    if PASSWORD_REQUIRED and user_id not in admin_ids and not is_user_authenticated(user_id):
        if data not in ['back_to_main', 'speed', 'stats']:
            bot.answer_callback_query(call.id, "🔐 Authenticate first.", show_alert=True)
            return
    
    try:
        if data == 'upload': upload_callback(call)
        elif data == 'check_files': check_files_callback(call)
        elif data.startswith('file_'): file_control_callback(call)
        elif data.startswith('start_'): start_bot_callback(call)
        elif data.startswith('stop_'): stop_bot_callback(call)
        elif data.startswith('restart_'): restart_bot_callback(call)
        elif data.startswith('delete_'): delete_bot_callback(call)
        elif data.startswith('logs_'): logs_bot_callback(call)
        elif data == 'speed': speed_callback(call)
        elif data == 'back_to_main': back_to_main_callback(call)
        elif data.startswith('confirm_broadcast_'): handle_confirm_broadcast(call)
        elif data == 'cancel_broadcast': handle_cancel_broadcast(call)
        elif data == 'pending_approvals': pending_approvals_callback(call)
        elif data.startswith('view_pending_'): view_pending_file_details(call)
        elif data.startswith('approve_'): approve_pending_file(call)
        elif data.startswith('reject_'): reject_pending_file(call)
        elif data == 'send_command': send_command_callback(call)
        elif data == 'send_to_process': send_to_process_callback(call)
        elif data.startswith('sendcmd_select_'): sendcmd_select_callback(call)
        elif data == 'view_all_logs': view_all_logs_callback(call)
        elif data.startswith('viewlog_'): viewlog_callback(call)
        elif data == 'subscription': admin_required_callback(call, subscription_management_callback)
        elif data == 'stats': stats_callback(call)
        elif data == 'lock_bot': admin_required_callback(call, lock_bot_callback)
        elif data == 'unlock_bot': admin_required_callback(call, unlock_bot_callback)
        elif data == 'run_all_scripts': admin_required_callback(call, run_all_scripts_callback)
        elif data == 'broadcast': admin_required_callback(call, broadcast_init_callback)
        elif data == 'admin_panel': admin_required_callback(call, admin_panel_callback)
        elif data == 'add_admin': owner_required_callback(call, add_admin_init_callback)
        elif data == 'remove_admin': owner_required_callback(call, remove_admin_init_callback)
        elif data == 'list_admins': admin_required_callback(call, list_admins_callback)
        elif data == 'add_subscription': admin_required_callback(call, add_subscription_init_callback)
        elif data == 'remove_subscription': admin_required_callback(call, remove_subscription_init_callback)
        elif data == 'check_subscription': admin_required_callback(call, check_subscription_init_callback)
        else:
            bot.answer_callback_query(call.id, "Unknown.")
    except Exception as e:
        logger.error(f"Error in callback '{data}': {e}", exc_info=True)
        try: bot.answer_callback_query(call.id, "Error.", show_alert=True)
        except: pass

def admin_required_callback(call, func_to_run):
    if call.from_user.id not in admin_ids:
        bot.answer_callback_query(call.id, "⚠️ Admin required.", show_alert=True)
        return
    func_to_run(call)

def owner_required_callback(call, func_to_run):
    if call.from_user.id != OWNER_ID:
        bot.answer_callback_query(call.id, "⚠️ Owner required.", show_alert=True)
        return
    func_to_run(call)

def pending_approvals_callback(call):
    bot.answer_callback_query(call.id)
    _logic_pending_approvals(call.message)

def send_command_callback(call):
    bot.answer_callback_query(call.id)
    try:
        bot.edit_message_text("📤 Send Command:", call.message.chat.id, call.message.message_id,
                              reply_markup=create_send_command_menu())
    except: pass

def send_to_process_callback(call):
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, "📝 Send command:")
    bot.register_next_step_handler(msg, lambda m: send_to_process_init(m))

def sendcmd_select_callback(call):
    try:
        script_key = call.data.replace('sendcmd_select_', '')
        bot.answer_callback_query(call.id)
        msg = bot.send_message(call.message.chat.id, f"📝 Command for {script_key}:")
        bot.register_next_step_handler(msg, lambda m: process_send_command(m, script_key))
    except: pass

def view_all_logs_callback(call):
    bot.answer_callback_query(call.id)
    view_all_logs(call.message)

def viewlog_callback(call):
    try:
        _, user_id_str, log_filename = call.data.split('_', 2)
        user_id = int(user_id_str)
        if not (call.from_user.id == user_id or call.from_user.id in admin_ids):
            bot.answer_callback_query(call.id, "⚠️ Denied.", show_alert=True); return
        user_folder = get_user_folder(user_id)
        log_path = os.path.join(user_folder, log_filename)
        if not os.path.exists(log_path):
            bot.answer_callback_query(call.id, "❌ Not found.", show_alert=True); return
        bot.answer_callback_query(call.id, "📜 Sending...")
        send_log_file(call.message, log_path, log_filename)
    except: pass

def upload_callback(call):
    user_id = call.from_user.id
    file_limit = get_user_file_limit(user_id)
    if get_user_file_count(user_id) >= file_limit:
        bot.answer_callback_query(call.id, f"⚠️ Limit reached.", show_alert=True); return
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, "📤 Send `.py`, `.js`, or `.zip` file.")

def check_files_callback(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    user_files_list = user_files.get(user_id, [])
    if not user_files_list:
        bot.answer_callback_query(call.id, "⚠️ No files.", show_alert=True)
        try:
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 Back", callback_data='back_to_main'))
            bot.edit_message_text("📂 No files.", chat_id, call.message.message_id, reply_markup=markup)
        except: pass
        return
    bot.answer_callback_query(call.id)
    markup = types.InlineKeyboardMarkup(row_width=1)
    for file_name, file_type in sorted(user_files_list):
        is_running = is_bot_running(user_id, file_name)
        status_icon = "🟢" if is_running else "🔴"
        markup.add(types.InlineKeyboardButton(f"{status_icon} {file_name} ({file_type})", callback_data=f'file_{user_id}_{file_name}'))
    markup.add(types.InlineKeyboardButton("🔙 Back", callback_data='back_to_main'))
    try: bot.edit_message_text("📂 Files:", chat_id, call.message.message_id, reply_markup=markup)
    except: pass

def file_control_callback(call):
    try:
        _, script_owner_id_str, file_name = call.data.split('_', 2)
        script_owner_id = int(script_owner_id_str)
        if not (call.from_user.id == script_owner_id or call.from_user.id in admin_ids):
            bot.answer_callback_query(call.id, "⚠️ Denied.", show_alert=True); return
        user_files_list = user_files.get(script_owner_id, [])
        if not any(f[0] == file_name for f in user_files_list):
            bot.answer_callback_query(call.id, "⚠️ Not found.", show_alert=True); return
        bot.answer_callback_query(call.id)
        is_running = is_bot_running(script_owner_id, file_name)
        status_text = '🟢 Running' if is_running else '🔴 Stopped'
        file_type = next((f[1] for f in user_files_list if f[0] == file_name), '?')
        try:
            bot.edit_message_text(f"⚙️ `{file_name}` ({file_type})\n{status_text}",
                call.message.chat.id, call.message.message_id,
                reply_markup=create_control_buttons(script_owner_id, file_name, is_running),
                parse_mode='Markdown')
        except: pass
    except: pass

def start_bot_callback(call):
    try:
        _, script_owner_id_str, file_name = call.data.split('_', 2)
        script_owner_id = int(script_owner_id_str)
        if not (call.from_user.id == script_owner_id or call.from_user.id in admin_ids):
            bot.answer_callback_query(call.id, "⚠️ Denied.", show_alert=True); return
        user_files_list = user_files.get(script_owner_id, [])
        file_info = next((f for f in user_files_list if f[0] == file_name), None)
        if not file_info:
            bot.answer_callback_query(call.id, "⚠️ Not found.", show_alert=True); return
        file_type = file_info[1]
        user_folder = get_user_folder(script_owner_id)
        file_path = os.path.join(user_folder, file_name)
        if not os.path.exists(file_path):
            bot.answer_callback_query(call.id, f"⚠️ Missing!", show_alert=True); return
        if is_bot_running(script_owner_id, file_name):
            bot.answer_callback_query(call.id, f"⚠️ Already running.", show_alert=True); return
        bot.answer_callback_query(call.id, f"⏳ Starting...")
        if file_type == 'py':
            threading.Thread(target=run_script, args=(file_path, script_owner_id, user_folder, file_name, call.message)).start()
        elif file_type == 'js':
            threading.Thread(target=run_js_script, args=(file_path, script_owner_id, user_folder, file_name, call.message)).start()
    except: pass

def stop_bot_callback(call):
    try:
        _, script_owner_id_str, file_name = call.data.split('_', 2)
        script_owner_id = int(script_owner_id_str)
        if not (call.from_user.id == script_owner_id or call.from_user.id in admin_ids):
            bot.answer_callback_query(call.id, "⚠️ Denied.", show_alert=True); return
        script_key = f"{script_owner_id}_{file_name}"
        if not is_bot_running(script_owner_id, file_name):
            bot.answer_callback_query(call.id, f"⚠️ Already stopped.", show_alert=True); return
        bot.answer_callback_query(call.id, f"⏳ Stopping...")
        process_info = bot_scripts.get(script_key)
        if process_info:
            kill_process_tree(process_info)
            if script_key in bot_scripts: del bot_scripts[script_key]
    except: pass

def restart_bot_callback(call):
    try:
        _, script_owner_id_str, file_name = call.data.split('_', 2)
        script_owner_id = int(script_owner_id_str)
        if not (call.from_user.id == script_owner_id or call.from_user.id in admin_ids):
            bot.answer_callback_query(call.id, "⚠️ Denied.", show_alert=True); return
        user_files_list = user_files.get(script_owner_id, [])
        file_info = next((f for f in user_files_list if f[0] == file_name), None)
        if not file_info:
            bot.answer_callback_query(call.id, "⚠️ Not found.", show_alert=True); return
        file_type = file_info[1]
        user_folder = get_user_folder(script_owner_id)
        file_path = os.path.join(user_folder, file_name)
        script_key = f"{script_owner_id}_{file_name}"
        if not os.path.exists(file_path):
            bot.answer_callback_query(call.id, f"⚠️ Missing!", show_alert=True); return
        bot.answer_callback_query(call.id, f"⏳ Restarting...")
        if is_bot_running(script_owner_id, file_name):
            process_info = bot_scripts.get(script_key)
            if process_info: kill_process_tree(process_info)
            if script_key in bot_scripts: del bot_scripts[script_key]
            time.sleep(1.5)
        if file_type == 'py':
            threading.Thread(target=run_script, args=(file_path, script_owner_id, user_folder, file_name, call.message)).start()
        elif file_type == 'js':
            threading.Thread(target=run_js_script, args=(file_path, script_owner_id, user_folder, file_name, call.message)).start()
    except: pass

def delete_bot_callback(call):
    try:
        _, script_owner_id_str, file_name = call.data.split('_', 2)
        script_owner_id = int(script_owner_id_str)
        if not (call.from_user.id == script_owner_id or call.from_user.id in admin_ids):
            bot.answer_callback_query(call.id, "⚠️ Denied.", show_alert=True); return
        bot.answer_callback_query(call.id, f"🗑️ Deleting...")
        script_key = f"{script_owner_id}_{file_name}"
        if is_bot_running(script_owner_id, file_name):
            process_info = bot_scripts.get(script_key)
            if process_info: kill_process_tree(process_info)
            if script_key in bot_scripts: del bot_scripts[script_key]
            time.sleep(0.5)
        user_folder = get_user_folder(script_owner_id)
        file_path = os.path.join(user_folder, file_name)
        log_path = os.path.join(user_folder, f"{os.path.splitext(file_name)[0]}.log")
        if os.path.exists(file_path):
            try: os.remove(file_path)
            except: pass
        if os.path.exists(log_path):
            try: os.remove(log_path)
            except: pass
        remove_user_file_db(script_owner_id, file_name)
        try: bot.edit_message_text(f"🗑️ Deleted `{file_name}`!", call.message.chat.id, call.message.message_id, parse_mode='Markdown')
        except: pass
    except: pass

def logs_bot_callback(call):
    try:
        _, script_owner_id_str, file_name = call.data.split('_', 2)
        script_owner_id = int(script_owner_id_str)
        if not (call.from_user.id == script_owner_id or call.from_user.id in admin_ids):
            bot.answer_callback_query(call.id, "⚠️ Denied.", show_alert=True); return
        user_folder = get_user_folder(script_owner_id)
        log_path = os.path.join(user_folder, f"{os.path.splitext(file_name)[0]}.log")
        if not os.path.exists(log_path):
            bot.answer_callback_query(call.id, f"⚠️ No logs.", show_alert=True); return
        bot.answer_callback_query(call.id)
        try:
            log_content = ""
            file_size = os.path.getsize(log_path)
            if file_size == 0: log_content = "(Empty)"
            elif file_size > 100 * 1024:
                with open(log_path, 'rb') as f: f.seek(-100 * 1024, os.SEEK_END); log_content = f.read().decode('utf-8', errors='ignore')
                log_content = f"(Last 100 KB)\n...\n" + log_content
            else:
                with open(log_path, 'r', encoding='utf-8', errors='ignore') as f: log_content = f.read()
            if len(log_content) > 4096: log_content = log_content[-4096:]
            if not log_content.strip(): log_content = "(No content)"
            bot.send_message(call.message.chat.id, f"📜 `{file_name}`:\n```\n{log_content}\n```", parse_mode='Markdown')
        except Exception as e:
            bot.send_message(call.message.chat.id, f"❌ Error reading log.")
    except: pass

def speed_callback(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    start_cb_ping_time = time.time()
    try:
        bot.edit_message_text("🏃 Testing...", chat_id, call.message.message_id)
        bot.send_chat_action(chat_id, 'typing')
        response_time = round((time.time() - start_cb_ping_time) * 1000, 2)
        status = "🔓 Unlocked" if not bot_locked else "🔒 Locked"
        if user_id == OWNER_ID: user_level = "👑 Owner"
        elif user_id in admin_ids: user_level = "⭐ Admin"
        elif user_id in user_subscriptions and user_subscriptions[user_id].get('expiry', datetime.min) > datetime.now(): user_level = "💎 Premium"
        else: user_level = "🆓 Free"
        speed_msg = (f"⚡ Speed:\n\n⏱️ {response_time} ms\n🚦 {status}\n👤 {user_level}")
        bot.answer_callback_query(call.id)
        bot.edit_message_text(speed_msg, chat_id, call.message.message_id, reply_markup=create_main_menu_inline(user_id))
    except: pass

def back_to_main_callback(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    file_limit = get_user_file_limit(user_id)
    current_files = get_user_file_count(user_id)
    limit_str = str(file_limit) if file_limit != float('inf') else "Unlimited"
    expiry_info = ""
    if user_id == OWNER_ID: user_status = "👑 Owner"
    elif user_id in admin_ids: user_status = "⭐ Admin"
    elif user_id in user_subscriptions:
        expiry_date = user_subscriptions[user_id].get('expiry')
        if expiry_date and expiry_date > datetime.now():
            user_status = "💎 Premium"; days_left = (expiry_date - datetime.now()).days
            expiry_info = f"\n⏳ {days_left} days"
        else: user_status = "🆓 Free (Expired)"
    else: user_status = "🆓 Free"
    pending_count = get_pending_files_count()
    pending_msg = f"\n📥 Pending: {pending_count}" if user_id in admin_ids and pending_count > 0 else ""
    auto_msg = f"\n⚙️ Auto-Approve: {'🟢 ON' if get_auto_approve_status() else '🔴 OFF'}" if user_id in admin_ids else ""
    main_menu_text = (f"〽️ Welcome back, {call.from_user.first_name}!\n\n🆔 ID: `{user_id}`\n"
                      f"🔰 {user_status}{expiry_info}\n📁 {current_files} / {limit_str}{pending_msg}{auto_msg}\n\n"
                      f"👇 Use buttons.")
    try:
        bot.answer_callback_query(call.id)
        bot.edit_message_text(main_menu_text, chat_id, call.message.message_id,
                              reply_markup=create_main_menu_inline(user_id), parse_mode='Markdown')
    except: pass

def subscription_management_callback(call):
    bot.answer_callback_query(call.id)
    try: bot.edit_message_text("💳 Subscriptions", call.message.chat.id, call.message.message_id, reply_markup=create_subscription_menu())
    except: pass

def stats_callback(call):
    bot.answer_callback_query(call.id)
    _logic_statistics(call.message)

def lock_bot_callback(call):
    global bot_locked; bot_locked = True
    bot.answer_callback_query(call.id, "🔒 Bot locked.")
    try: bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=create_main_menu_inline(call.from_user.id))
    except: pass

def unlock_bot_callback(call):
    global bot_locked; bot_locked = False
    bot.answer_callback_query(call.id, "🔓 Bot unlocked.")
    try: bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=create_main_menu_inline(call.from_user.id))
    except: pass

def run_all_scripts_callback(call): _logic_run_all_scripts(call)

def broadcast_init_callback(call):
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, "📢 Send message to broadcast.\n/cancel to abort.")
    bot.register_next_step_handler(msg, process_broadcast_message)

def process_broadcast_message(message):
    user_id = message.from_user.id
    if user_id not in admin_ids: bot.reply_to(message, "⚠️ Not authorized."); return
    if message.text and message.text.lower() == '/cancel': bot.reply_to(message, "Cancelled."); return
    broadcast_content = message.text
    if not broadcast_content:
        bot.reply_to(message, "⚠️ Empty.")
        return
    target_count = len(active_users)
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("✅ Confirm", callback_data=f"confirm_broadcast_{message.message_id}"),
        types.InlineKeyboardButton("❌ Cancel", callback_data="cancel_broadcast")
    )
    bot.reply_to(message, f"⚠️ Confirm:\n\n```\n{broadcast_content[:500]}\n```\nTo {target_count} users?", reply_markup=markup, parse_mode='Markdown')

def handle_confirm_broadcast(call):
    if call.from_user.id not in admin_ids: bot.answer_callback_query(call.id, "⚠️ Admin only.", show_alert=True); return
    try:
        original_message = call.message.reply_to_message
        if not original_message: return
        broadcast_text = original_message.text if original_message.text else None
        if not broadcast_text: return
        bot.answer_callback_query(call.id, "🚀 Starting...")
        bot.edit_message_text(f"📢 Broadcasting to {len(active_users)}...", call.message.chat.id, call.message.message_id, reply_markup=None)
        threading.Thread(target=execute_broadcast, args=(broadcast_text, call.message.chat.id)).start()
    except: pass

def handle_cancel_broadcast(call):
    bot.answer_callback_query(call.id, "Cancelled.")
    bot.delete_message(call.message.chat.id, call.message.message_id)

def execute_broadcast(broadcast_text, admin_chat_id):
    sent = 0; failed = 0; blocked = 0
    for i, uid in enumerate(list(active_users)):
        try:
            bot.send_message(uid, broadcast_text, parse_mode='Markdown')
            sent += 1
        except telebot.apihelper.ApiTelegramException as e:
            if any(s in str(e).lower() for s in ["blocked", "deactivated", "not found"]): blocked += 1
            else: failed += 1
        except: failed += 1
        if (i + 1) % 25 == 0: time.sleep(1.5)
    try: bot.send_message(admin_chat_id, f"📢 Complete!\n✅ {sent}\n❌ {failed}\n🚫 {blocked}\n👥 {len(active_users)}")
    except: pass

def admin_panel_callback(call):
    bot.answer_callback_query(call.id)
    try: bot.edit_message_text("👑 Admin Panel", call.message.chat.id, call.message.message_id, reply_markup=create_admin_panel())
    except: pass

def add_admin_init_callback(call):
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, "👑 Enter User ID to promote.\n/cancel to abort.")
    bot.register_next_step_handler(msg, process_add_admin_id)

def process_add_admin_id(message):
    if message.from_user.id != OWNER_ID: bot.reply_to(message, "⚠️ Owner only."); return
    if message.text.lower() == '/cancel': bot.reply_to(message, "Cancelled."); return
    try:
        new_admin_id = int(message.text.strip())
        if new_admin_id <= 0 or new_admin_id == OWNER_ID or new_admin_id in admin_ids:
            bot.reply_to(message, "⚠️ Invalid or already admin.")
            return
        add_admin_db(new_admin_id)
        bot.reply_to(message, f"✅ Promoted `{new_admin_id}`.")
        try: bot.send_message(new_admin_id, "🎉 You are now Admin!")
        except: pass
    except ValueError:
        bot.reply_to(message, "⚠️ Invalid ID.")
        msg = bot.send_message(message.chat.id, "👑 Enter ID or /cancel.")
        bot.register_next_step_handler(msg, process_add_admin_id)

def remove_admin_init_callback(call):
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, "👑 Enter Admin ID to remove.\n/cancel to abort.")
    bot.register_next_step_handler(msg, process_remove_admin_id)

def process_remove_admin_id(message):
    if message.from_user.id != OWNER_ID: bot.reply_to(message, "⚠️ Owner only."); return
    if message.text.lower() == '/cancel': bot.reply_to(message, "Cancelled."); return
    try:
        admin_id_remove = int(message.text.strip())
        if admin_id_remove == OWNER_ID or admin_id_remove not in admin_ids:
            bot.reply_to(message, "⚠️ Invalid.")
            return
        if remove_admin_db(admin_id_remove):
            bot.reply_to(message, f"✅ Removed.")
            try: bot.send_message(admin_id_remove, "ℹ️ No longer Admin.")
            except: pass
        else: bot.reply_to(message, f"❌ Failed.")
    except ValueError:
        bot.reply_to(message, "⚠️ Invalid ID.")
        msg = bot.send_message(message.chat.id, "👑 Enter ID or /cancel.")
        bot.register_next_step_handler(msg, process_remove_admin_id)

def list_admins_callback(call):
    bot.answer_callback_query(call.id)
    try:
        admin_list_str = "\n".join(f"• `{aid}` {'👑' if aid == OWNER_ID else ''}" for aid in sorted(list(admin_ids)))
        if not admin_list_str: admin_list_str = "(None)"
        bot.edit_message_text(f"👑 Admins:\n\n{admin_list_str}", call.message.chat.id, call.message.message_id,
                              reply_markup=create_admin_panel(), parse_mode='Markdown')
    except: pass

def add_subscription_init_callback(call):
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, "💳 Enter `UserID Days`.\n/cancel to abort.", parse_mode='Markdown')
    bot.register_next_step_handler(msg, process_add_subscription_details)

def process_add_subscription_details(message):
    if message.from_user.id not in admin_ids: return
    if message.text.lower() == '/cancel': bot.reply_to(message, "Cancelled."); return
    try:
        parts = message.text.split()
        if len(parts) != 2: raise ValueError()
        sub_user_id = int(parts[0]); days = int(parts[1])
        if sub_user_id <= 0 or days <= 0: raise ValueError()
        current_expiry = user_subscriptions.get(sub_user_id, {}).get('expiry')
        start = datetime.now()
        if current_expiry and current_expiry > start: start = current_expiry
        new_expiry = start + timedelta(days=days)
        save_subscription(sub_user_id, new_expiry)
        bot.reply_to(message, f"✅ Sub for `{sub_user_id}` by {days} days.")
        try: bot.send_message(sub_user_id, f"🎉 Sub activated! Expires: {new_expiry:%Y-%m-%d}.")
        except: pass
    except:
        bot.reply_to(message, "⚠️ Invalid format. Use: ID Days")
        msg = bot.send_message(message.chat.id, "💳 Enter `ID Days` or /cancel.")
        bot.register_next_step_handler(msg, process_add_subscription_details)

def remove_subscription_init_callback(call):
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, "💳 Enter User ID.\n/cancel to abort.")
    bot.register_next_step_handler(msg, process_remove_subscription_id)

def process_remove_subscription_id(message):
    if message.from_user.id not in admin_ids: return
    if message.text.lower() == '/cancel': bot.reply_to(message, "Cancelled."); return
    try:
        sub_user_id_remove = int(message.text.strip())
        if sub_user_id_remove not in user_subscriptions:
            bot.reply_to(message, f"⚠️ No active sub."); return
        remove_subscription_db(sub_user_id_remove)
        bot.reply_to(message, f"✅ Removed.")
        try: bot.send_message(sub_user_id_remove, "ℹ️ Sub removed.")
        except: pass
    except:
        bot.reply_to(message, "⚠️ Invalid ID.")
        msg = bot.send_message(message.chat.id, "💳 Enter ID or /cancel.")
        bot.register_next_step_handler(msg, process_remove_subscription_id)

def check_subscription_init_callback(call):
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, "💳 Enter User ID.\n/cancel to abort.")
    bot.register_next_step_handler(msg, process_check_subscription_id)

def process_check_subscription_id(message):
    if message.from_user.id not in admin_ids: return
    if message.text.lower() == '/cancel': bot.reply_to(message, "Cancelled."); return
    try:
        sub_user_id_check = int(message.text.strip())
        if sub_user_id_check in user_subscriptions:
            expiry_dt = user_subscriptions[sub_user_id_check].get('expiry')
            if expiry_dt and expiry_dt > datetime.now():
                days_left = (expiry_dt - datetime.now()).days
                bot.reply_to(message, f"✅ Active. Expires: {expiry_dt:%Y-%m-%d} ({days_left} days)")
            else:
                bot.reply_to(message, f"⚠️ Expired.")
                remove_subscription_db(sub_user_id_check)
        else: bot.reply_to(message, f"ℹ️ No sub.")
    except:
        bot.reply_to(message, "⚠️ Invalid ID.")
        msg = bot.send_message(message.chat.id, "💳 Enter ID or /cancel.")
        bot.register_next_step_handler(msg, process_check_subscription_id)

# --- Cleanup ---
def cleanup():
    logger.warning("Shutdown. Cleaning up...")
    for key in list(bot_scripts.keys()):
        if key in bot_scripts: kill_process_tree(bot_scripts[key])
    logger.warning("Cleanup finished.")
atexit.register(cleanup)

# --- Main Execution ---
if __name__ == '__main__':
    logger.info("="*40 + "\n🤖 Bot Starting Up...\n" +
                f"🐍 Python: {sys.version.split()[0]}\n" +
                f"🔑 Owner ID: {OWNER_ID}\n" +
                f"🛡️ Admins: {admin_ids}\n" +
                f"🔐 Password Required: {PASSWORD_REQUIRED}\n" +
                f"⚙️ Auto-Approve: {auto_approve_enabled}\n" + "="*40)
    keep_alive()
    logger.info("🚀 Starting polling...")
    while True:
        try:
            bot.infinity_polling(logger_level=logging.INFO, timeout=60, long_polling_timeout=30)
        except requests.exceptions.ReadTimeout: 
            logger.warning("ReadTimeout. Restarting...")
            time.sleep(5)
        except requests.exceptions.ConnectionError as ce: 
            logger.error(f"ConnectionError: {ce}")
            time.sleep(15)
        except Exception as e:
            logger.critical(f"💥 Polling error: {e}", exc_info=True)
            time.sleep(30)
        finally: 
            time.sleep(1)
