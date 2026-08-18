# -*- coding: utf-8 -*-
import telebot
import subprocess
import os
import sys
import zipfile
import tempfile
import shutil
import time
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
import uuid
import socket
import platform
import base64
import random
import string
import functools
from contextlib import contextmanager
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from enum import Enum
from datetime import datetime, timedelta
from telebot import types
from flask import Flask, jsonify, request, render_template_string
from threading import Thread
from collections import defaultdict

# Set encoding
os.environ["PYTHONIOENCODING"] = "utf-8"

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except:
    pass

# ============================================================
# CONFIGURATION
# ============================================================

class Config:
    """Bot configuration with validation"""
    
    # Bot Token
    BOT_TOKEN = '8762789304:AAG4ROCZMDDRqYvx2KbvOGZ-lNLjmwMQTIE'
    
    # Admins
    OWNER_ID = 8909378644
    ADMIN_ID = 8909378644
    
    # Channels
    UPDATE_CHANNEL = 'https://t.me/botscripts18'
    YOUR_USERNAME = '@anbu_shisui18'
    
    FORCE_JOIN_CHANNELS = {
        "@botscripts18": "💎 𝐎𝐟𝐟𝐢𝐜𝐢𝐚𝐥 𝐂𝐡𝐚𝐧𝐧𝐞𝐥",
    }
    
    # File limits
    FREE_USER_LIMIT = 10
    SUBSCRIBED_USER_LIMIT = 350
    ADMIN_LIMIT = 500
    OWNER_LIMIT = float('inf')
    
    # Timeouts
    PROCESS_TIMEOUT = 300
    MAX_LOG_SIZE = 5 * 1024 * 1024
    MAX_FILE_SIZE = 50 * 1024 * 1024
    
    # Auto cleanup
    AUTO_CLEANUP_INTERVAL = 3600
    INACTIVE_PROCESS_TIMEOUT = 7200
    
    # Web dashboard
    WEB_PORT = 8080
    WEB_HOST = '0.0.0.0'
    
    # Language
    DEFAULT_LANG = 'en'
    
    # Malware Detection
    MALWARE_SIGNATURES = [
        b'MZ',
        b'\x7fELF',
        b'\xfe\xed\xfa',
        b'\xce\xfa\xed\xfe',
        b'PK',
        b'Rar!',
    ]
    
    ENCRYPTED_FILE_INDICATORS = [
        b'openssl',
        b'encrypted',
        b'cipher',
        b'DES',
        b'RSA',
        b'GPG',
        b'PGP',
    ]
    
    SUSPICIOUS_KEYWORDS = [
        b'ransomware',
        b'trojan',
        b'virus',
        b'malware',
        b'backdoor',
        b'exploit',
        b'payload',
        b'botnet',
        b'keylogger',
        b'rootkit',
    ]

config = Config()

# ============================================================
# FLASK KEEP ALIVE
# ============================================================

app = Flask('')

@app.route('/')
def home():
    return "🤖 Bot is running...."

@app.route('/stats')
def stats():
    return jsonify({
        'status': 'online',
        'timestamp': datetime.now().isoformat(),
        'version': '3.0.0'
    })

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_flask)
    t.daemon = True
    t.start()
    print("Flask Keep-Alive server started.")

# ============================================================
# DATABASE MANAGER
# ============================================================

class DatabaseManager:
    """Advanced database management with connection pooling and migrations"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._lock = threading.RLock()
        self._version = 3
        
    @contextmanager
    def get_connection(self):
        """Context manager for database connections"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = sqlite3.connect(self.db_path, check_same_thread=False, timeout=30)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def initialize(self):
        """Initialize database with all tables and migrations"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS schema_version (
                    version INTEGER PRIMARY KEY,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            cursor.execute('SELECT MAX(version) FROM schema_version')
            row = cursor.fetchone()
            current_version = row[0] if row and row[0] else 0
            
            migrations = [
                self._migration_v1,
                self._migration_v2,
                self._migration_v3,
            ]
            
            for version, migration in enumerate(migrations, 1):
                if version > current_version:
                    logging.info(f"Running migration v{version}")
                    migration(cursor)
                    cursor.execute(
                        'INSERT INTO schema_version (version) VALUES (?)',
                        (version,)
                    )
                    conn.commit()
                    logging.info(f"Migration v{version} complete")
    
    def _migration_v1(self, cursor):
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                language TEXT DEFAULT 'en',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_banned BOOLEAN DEFAULT 0,
                ban_reason TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS subscriptions (
                user_id INTEGER PRIMARY KEY,
                expiry TIMESTAMP,
                plan TEXT DEFAULT 'premium',
                auto_renew BOOLEAN DEFAULT 0
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                file_name TEXT,
                file_type TEXT,
                file_size INTEGER,
                upload_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_running BOOLEAN DEFAULT 0,
                last_started TIMESTAMP,
                last_stopped TIMESTAMP,
                pid INTEGER
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS admins (
                user_id INTEGER PRIMARY KEY,
                role TEXT DEFAULT 'admin',
                added_by INTEGER,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS active_users (
                user_id INTEGER PRIMARY KEY,
                last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Insert default admin
        cursor.execute('INSERT OR IGNORE INTO admins (user_id) VALUES (?)', (config.OWNER_ID,))
        if config.ADMIN_ID != config.OWNER_ID:
            cursor.execute('INSERT OR IGNORE INTO admins (user_id) VALUES (?)', (config.ADMIN_ID,))
    
    def _migration_v2(self, cursor):
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                action TEXT,
                details TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS analytics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                metric TEXT,
                value INTEGER,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
    
    def _migration_v3(self, cursor):
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS backups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                file_name TEXT,
                backup_path TEXT,
                backup_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                title TEXT,
                message TEXT,
                is_read BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

# ============================================================
# CACHE MANAGER
# ============================================================

class CacheManager:
    """Simple in-memory cache with TTL"""
    
    def __init__(self, default_ttl: int = 300):
        self._cache: Dict[str, Tuple[Any, float]] = {}
        self._default_ttl = default_ttl
        self._lock = threading.RLock()
        self._cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self._cleanup_thread.start()
    
    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            if key in self._cache:
                value, expiry = self._cache[key]
                if time.time() < expiry:
                    return value
                else:
                    del self._cache[key]
            return None
    
    def set(self, key: str, value: Any, ttl: int = None):
        with self._lock:
            self._cache[key] = (value, time.time() + (ttl or self._default_ttl))
    
    def delete(self, key: str):
        with self._lock:
            if key in self._cache:
                del self._cache[key]
    
    def clear(self):
        with self._lock:
            self._cache.clear()
    
    def _cleanup_loop(self):
        while True:
            time.sleep(60)
            with self._lock:
                current_time = time.time()
                expired_keys = [
                    key for key, (_, expiry) in self._cache.items()
                    if current_time > expiry
                ]
                for key in expired_keys:
                    del self._cache[key]

# ============================================================
# MENU SYSTEM
# ============================================================

class MenuManager:
    """Advanced menu system with pagination and themes"""
    
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.theme = 'dark'
        self.lang = 'en'
    
    def main_menu(self, user_data: dict) -> types.InlineKeyboardMarkup:
        markup = types.InlineKeyboardMarkup(row_width=2)
        
        markup.add(
            types.InlineKeyboardButton(
                f"👤 {user_data.get('first_name', 'User')}",
                callback_data='profile'
            ),
            types.InlineKeyboardButton(
                f"📊 Stats",
                callback_data='stats'
            )
        )
        
        markup.add(
            types.InlineKeyboardButton("📤 Upload", callback_data='upload'),
            types.InlineKeyboardButton("📂 My Files", callback_data='files')
        )
        
        markup.add(
            types.InlineKeyboardButton("⚡ Bot Speed", callback_data='speed'),
            types.InlineKeyboardButton("📜 Logs", callback_data='logs')
        )
        
        markup.add(
            types.InlineKeyboardButton("🆘 Help", callback_data='help'),
            types.InlineKeyboardButton("⚙️ Settings", callback_data='settings')
        )
        
        return markup
    
    def file_management_menu(self, files: List[dict], page: int = 0, per_page: int = 5) -> types.InlineKeyboardMarkup:
        markup = types.InlineKeyboardMarkup(row_width=2)
        
        total_pages = (len(files) + per_page - 1) // per_page
        start_idx = page * per_page
        end_idx = min(start_idx + per_page, len(files))
        
        for file in files[start_idx:end_idx]:
            status = "🟢" if file.get('is_running', False) else "🔴"
            markup.add(
                types.InlineKeyboardButton(
                    f"{status} {file['file_name']}",
                    callback_data=f"file_{file['id']}"
                )
            )
        
        if total_pages > 1:
            nav_buttons = []
            if page > 0:
                nav_buttons.append(
                    types.InlineKeyboardButton("◀️", callback_data=f"file_page_{page-1}")
                )
            nav_buttons.append(
                types.InlineKeyboardButton(f"📄 {page+1}/{total_pages}", callback_data="noop")
            )
            if page < total_pages - 1:
                nav_buttons.append(
                    types.InlineKeyboardButton("▶️", callback_data=f"file_page_{page+1}")
                )
            markup.row(*nav_buttons)
        
        markup.add(
            types.InlineKeyboardButton("🔄 Refresh", callback_data='refresh_files'),
            types.InlineKeyboardButton("🔙 Back", callback_data='main')
        )
        
        return markup
    
    def file_controls_menu(self, file_data: dict) -> types.InlineKeyboardMarkup:
        markup = types.InlineKeyboardMarkup(row_width=2)
        
        is_running = file_data.get('is_running', False)
        
        if is_running:
            markup.add(
                types.InlineKeyboardButton("⏹️ Stop", callback_data=f"stop_{file_data['id']}"),
                types.InlineKeyboardButton("🔄 Restart", callback_data=f"restart_{file_data['id']}")
            )
        else:
            markup.add(
                types.InlineKeyboardButton("▶️ Start", callback_data=f"start_{file_data['id']}")
            )
        
        markup.add(
            types.InlineKeyboardButton("📜 Logs", callback_data=f"logs_{file_data['id']}"),
            types.InlineKeyboardButton("📥 Download", callback_data=f"download_{file_data['id']}")
        )
        
        markup.add(
            types.InlineKeyboardButton("💾 Backup", callback_data=f"backup_{file_data['id']}"),
            types.InlineKeyboardButton("🗑️ Delete", callback_data=f"delete_{file_data['id']}")
        )
        
        markup.add(
            types.InlineKeyboardButton("📊 Resource Usage", callback_data=f"resources_{file_data['id']}")
        )
        
        markup.add(
            types.InlineKeyboardButton("🔙 Back to Files", callback_data='files')
        )
        
        return markup

# ============================================================
# PROCESS MANAGER
# ============================================================

class ProcessManager:
    """Advanced process management with monitoring"""
    
    def __init__(self):
        self._processes: Dict[str, dict] = {}
        self._lock = threading.RLock()
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
        self._auto_restart_enabled = True
    
    def start_process(self, script_key: str, command: List[str], cwd: str, env: dict = None) -> bool:
        with self._lock:
            if script_key in self._processes:
                return False
            
            try:
                log_file = open(
                    os.path.join(cwd, f"{script_key}.log"),
                    'a',
                    encoding='utf-8',
                    errors='replace'
                )
                
                startupinfo = None
                creationflags = 0
                
                if os.name == 'nt':
                    startupinfo = subprocess.STARTUPINFO()
                    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                    startupinfo.wShowWindow = subprocess.SW_HIDE
                    creationflags = subprocess.CREATE_NO_WINDOW
                
                process = subprocess.Popen(
                    command,
                    cwd=cwd,
                    stdout=log_file,
                    stderr=log_file,
                    stdin=subprocess.PIPE,
                    text=True,
                    encoding='utf-8',
                    errors='replace',
                    env=env or os.environ,
                    startupinfo=startupinfo,
                    creationflags=creationflags
                )
                
                self._processes[script_key] = {
                    'process': process,
                    'log_file': log_file,
                    'start_time': datetime.now(),
                    'cwd': cwd,
                    'pid': process.pid,
                    'restarts': 0,
                    'last_restart': None,
                    'status': 'running',
                    'auto_restart': True
                }
                
                logging.info(f"Started process {script_key} with PID {process.pid}")
                return True
                
            except Exception as e:
                logging.error(f"Failed to start process {script_key}: {e}")
                return False
    
    def stop_process(self, script_key: str) -> bool:
        with self._lock:
            if script_key not in self._processes:
                return False
            
            process_info = self._processes[script_key]
            process = process_info['process']
            
            try:
                if process.stdin:
                    process.stdin.close()
                
                process.terminate()
                
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                
                if process_info['log_file'] and not process_info['log_file'].closed:
                    process_info['log_file'].close()
                
                self._processes[script_key]['status'] = 'stopped'
                logging.info(f"Stopped process {script_key}")
                return True
                
            except Exception as e:
                logging.error(f"Error stopping process {script_key}: {e}")
                return False
    
    def get_process_info(self, script_key: str) -> Optional[dict]:
        with self._lock:
            if script_key not in self._processes:
                return None
            
            info = self._processes[script_key].copy()
            
            if info['status'] == 'running':
                try:
                    info['is_running'] = psutil.pid_exists(info['pid'])
                    if not info['is_running']:
                        info['status'] = 'exited'
                except Exception:
                    info['is_running'] = False
                    info['status'] = 'unknown'
            
            try:
                proc = psutil.Process(info['pid'])
                info['cpu_percent'] = proc.cpu_percent(interval=0.1)
                info['memory_mb'] = proc.memory_info().rss / 1024 / 1024
                info['threads'] = proc.num_threads()
            except Exception:
                info['cpu_percent'] = 0
                info['memory_mb'] = 0
                info['threads'] = 0
            
            return info
    
    def get_all_processes(self) -> Dict[str, dict]:
        with self._lock:
            return self._processes.copy()
    
    def cleanup_stale_processes(self):
        with self._lock:
            for key in list(self._processes.keys()):
                info = self._processes[key]
                if info['status'] == 'running':
                    try:
                        if not psutil.pid_exists(info['pid']):
                            info['status'] = 'exited'
                            if info['log_file'] and not info['log_file'].closed:
                                info['log_file'].close()
                    except Exception:
                        pass
    
    def _monitor_loop(self):
        while True:
            try:
                self.cleanup_stale_processes()
                
                if self._auto_restart_enabled:
                    for key, info in self._processes.items():
                        if info['status'] == 'exited' and info.get('auto_restart', True):
                            restarts = info.get('restarts', 0)
                            if restarts < 5:
                                logging.info(f"Auto-restarting {key} (attempt {restarts+1})")
                                info['restarts'] = restarts + 1
                                info['last_restart'] = datetime.now()
            except Exception as e:
                logging.error(f"Monitor loop error: {e}")
            
            time.sleep(30)

# ============================================================
# BACKUP MANAGER
# ============================================================

class BackupManager:
    """File backup management"""
    
    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        self.backup_dir = os.path.join(base_dir, 'backups')
        os.makedirs(self.backup_dir, exist_ok=True)
    
    def create_backup(self, user_id: int, file_name: str, file_path: str) -> Optional[str]:
        try:
            backup_id = f"{user_id}_{int(time.time())}_{uuid.uuid4().hex[:8]}"
            backup_path = os.path.join(self.backup_dir, backup_id)
            
            os.makedirs(backup_path, exist_ok=True)
            shutil.copy2(file_path, os.path.join(backup_path, file_name))
            
            metadata = {
                'user_id': user_id,
                'file_name': file_name,
                'created_at': datetime.now().isoformat(),
                'file_size': os.path.getsize(file_path),
                'backup_id': backup_id
            }
            
            with open(os.path.join(backup_path, 'metadata.json'), 'w') as f:
                json.dump(metadata, f, indent=2)
            
            logging.info(f"Backup created for {file_name} (user {user_id}): {backup_id}")
            return backup_id
            
        except Exception as e:
            logging.error(f"Backup creation failed: {e}")
            return None
    
    def restore_backup(self, backup_id: str, restore_path: str) -> bool:
        try:
            backup_path = os.path.join(self.backup_dir, backup_id)
            if not os.path.exists(backup_path):
                return False
            
            for file in os.listdir(backup_path):
                if file != 'metadata.json':
                    shutil.copy2(os.path.join(backup_path, file), restore_path)
                    return True
            
            return False
            
        except Exception as e:
            logging.error(f"Backup restore failed: {e}")
            return False
    
    def list_backups(self, user_id: int) -> List[dict]:
        backups = []
        try:
            for backup_id in os.listdir(self.backup_dir):
                metadata_path = os.path.join(self.backup_dir, backup_id, 'metadata.json')
                if os.path.exists(metadata_path):
                    with open(metadata_path, 'r') as f:
                        metadata = json.load(f)
                        if metadata.get('user_id') == user_id:
                            backups.append(metadata)
        except Exception as e:
            logging.error(f"Error listing backups: {e}")
        
        return sorted(backups, key=lambda x: x.get('created_at', ''), reverse=True)

# ============================================================
# MAIN BOT CLASS
# ============================================================

class AdvancedBot:
    """Main bot class with all features"""
    
    def __init__(self):
        self.bot = telebot.TeleBot(config.BOT_TOKEN)
        self.db = DatabaseManager('inf/bot_data.db')
        self.db.initialize()
        self.cache = CacheManager()
        self.process_manager = ProcessManager()
        self.backup_manager = BackupManager(os.path.dirname(os.path.abspath(__file__)))
        self.bot_locked = False
        self.active_users = set()
        self.bot_scripts = {}
        self.user_files = {}
        self.user_subscriptions = {}
        self.admin_ids = {config.OWNER_ID, config.ADMIN_ID}
        self.banned_users = set()
        self.banned_usernames = set()
        
        self._setup_handlers()
        self._setup_cleanup()
        keep_alive()
        
        logging.info("Advanced Bot initialized successfully")
    
    # ============================================================
    # HANDLER SETUP
    # ============================================================
    
    def _setup_handlers(self):
        """Setup all command handlers"""
        
        @self.bot.message_handler(commands=['start', 'help'])
        def start_command(message):
            self._handle_start(message)
        
        @self.bot.message_handler(commands=['stats'])
        def stats_command(message):
            self._handle_stats(message)
        
        @self.bot.message_handler(commands=['upload'])
        def upload_command(message):
            self._handle_upload(message)
        
        @self.bot.message_handler(commands=['myfiles'])
        def myfiles_command(message):
            self._handle_files(message)
        
        @self.bot.message_handler(commands=['ping'])
        def ping_command(message):
            self._handle_ping(message)
        
        @self.bot.message_handler(commands=['admin'])
        def admin_command(message):
            self._handle_admin(message)
        
        @self.bot.message_handler(commands=['lock'])
        def lock_command(message):
            self._handle_lock(message)
        
        @self.bot.message_handler(commands=['unlock'])
        def unlock_command(message):
            self._handle_unlock(message)
        
        @self.bot.message_handler(commands=['broadcast'])
        def broadcast_command(message):
            self._handle_broadcast(message)
        
        @self.bot.message_handler(commands=['settings'])
        def settings_command(message):
            self._handle_settings(message)
        
        @self.bot.message_handler(commands=['profile'])
        def profile_command(message):
            self._handle_profile(message)
        
        @self.bot.message_handler(commands=['backup'])
        def backup_command(message):
            self._handle_backup(message)
        
        @self.bot.message_handler(commands=['restore'])
        def restore_command(message):
            self._handle_restore(message)
        
        @self.bot.message_handler(commands=['cleanup'])
        def cleanup_command(message):
            self._handle_cleanup(message)
        
        @self.bot.message_handler(commands=['ban'])
        def ban_command(message):
            self._handle_ban(message)
        
        @self.bot.message_handler(commands=['unban'])
        def unban_command(message):
            self._handle_unban(message)
        
        @self.bot.message_handler(commands=['listusers'])
        def listusers_command(message):
            self._handle_listusers(message)
        
        @self.bot.message_handler(content_types=['document'])
        def file_upload_handler(message):
            self._handle_file_upload(message)
        
        @self.bot.callback_query_handler(func=lambda call: True)
        def callback_handler(call):
            self._handle_callback(call)
        
        @self.bot.message_handler(func=lambda message: True)
        def message_handler(message):
            self._handle_message(message)
    
    # ============================================================
    # COMMAND HANDLERS
    # ============================================================
    
    def _handle_start(self, message):
        """Handle /start command"""
        user_id = message.from_user.id
        chat_id = message.chat.id
        
        # Check ban
        if self._is_user_banned(user_id):
            self.bot.send_message(chat_id, "🚫 You are banned from using this bot.")
            return
        
        # Check force join
        if user_id not in self.admin_ids:
            if not self._check_force_join(user_id):
                self._send_force_join_message(chat_id)
                return
        
        # Register user
        self._register_user(message.from_user)
        
        # Get user data
        user_data = self._get_user_data(user_id)
        file_count = self._get_user_file_count(user_id)
        file_limit = self._get_user_limit(user_id)
        
        # Check subscription
        subscription = self._get_user_subscription(user_id)
        is_premium = False
        days_left = 0
        
        if subscription:
            expiry = subscription.get('expiry')
            if expiry:
                if isinstance(expiry, str):
                    try:
                        expiry = datetime.fromisoformat(expiry)
                    except:
                        expiry = None
                if expiry and expiry > datetime.now():
                    is_premium = True
                    days_left = (expiry - datetime.now()).days
        
        status = "🆓 Free"
        if user_id == config.OWNER_ID:
            status = "👑 Owner"
        elif user_id in self.admin_ids:
            status = "🛡️ Admin"
        elif is_premium:
            status = f"💎 Premium ({days_left}d left)"
        
        welcome_text = (
            f"🚀 **Welcome to Bot Hosting Platform!**\n\n"
            f"👤 **User:** {message.from_user.first_name}\n"
            f"✳️ **Username:** @{message.from_user.username or 'Not set'}\n"
            f"🆔 **ID:** `{user_id}`\n"
            f"🔰 **Status:** {status}\n"
            f"📂 **Files:** {file_count}/{file_limit}\n\n"
            f"🤖 **Host and run Python or JavaScript bots**\n"
            f"📤 Upload your scripts or ZIP archives\n"
            f"⚡ Get started by uploading your first file!\n\n"
            f"👇 **Use the buttons below:**"
        )
        
        markup = self._create_main_menu(user_id)
        self.bot.send_message(chat_id, welcome_text, reply_markup=markup, parse_mode='Markdown')
    
    def _handle_stats(self, message):
        """Handle stats command"""
        user_id = message.from_user.id
        
        if self._is_user_banned(user_id):
            return
        
        # Get user files
        user_files = self._get_user_files(user_id)
        running_count = sum(1 for f in user_files if f.get('is_running', False))
        
        stats_text = (
            f"📊 **Your Statistics**\n\n"
            f"📂 **Total Files:** {len(user_files)}\n"
            f"🟢 **Running Bots:** {running_count}\n"
            f"📤 **Uploads:** {len(user_files)}\n"
        )
        
        # Admin stats
        if user_id in self.admin_ids:
            total_users = len(self._get_all_users())
            total_files = self._get_total_files()
            running_processes = len(self.process_manager.get_all_processes())
            storage_used = self._get_storage_used()
            
            stats_text += f"\n👑 **Admin Stats**\n"
            stats_text += f"👥 **Total Users:** {total_users}\n"
            stats_text += f"📂 **Total Files:** {total_files}\n"
            stats_text += f"🟢 **Running Bots:** {running_processes}\n"
            stats_text += f"💾 **Storage Used:** {self._format_size(storage_used)}\n"
            stats_text += f"🔒 **Bot Status:** {'🔴 Locked' if self.bot_locked else '🟢 Unlocked'}"
        
        self.bot.reply_to(message, stats_text, parse_mode='Markdown')
    
    def _handle_upload(self, message):
        """Handle upload command"""
        user_id = message.from_user.id
        
        if self._is_user_banned(user_id):
            return
        
        if self.bot_locked and user_id not in self.admin_ids:
            self.bot.reply_to(message, "🔒 Bot is currently locked.")
            return
        
        # Check file limit
        user_files = self._get_user_files(user_id)
        user_limit = self._get_user_limit(user_id)
        
        if len(user_files) >= user_limit:
            self.bot.reply_to(
                message,
                f"⚠️ **File Limit Reached**\n\n"
                f"You have reached your limit of {user_limit} files.\n"
                f"Delete some files to upload more.",
                parse_mode='Markdown'
            )
            return
        
        self.bot.reply_to(
            message,
            "📤 **Upload Files**\n\n"
            "Send me a Python (`.py`) or JavaScript (`.js`) file.\n"
            "You can also send a ZIP archive containing your project.\n\n"
            "📦 Supported: `.py`, `.js`, `.zip`\n"
            f"📊 Limit: {len(user_files)}/{user_limit}",
            parse_mode='Markdown'
        )
    
    def _handle_files(self, message):
        """Handle my files command"""
        user_id = message.from_user.id
        
        if self._is_user_banned(user_id):
            return
        
        files = self._get_user_files(user_id)
        
        if not files:
            self.bot.reply_to(
                message,
                "📂 **No Files Found**\n\nYou haven't uploaded any files yet.\nUse /upload to get started!",
                parse_mode='Markdown'
            )
            return
        
        markup = self._create_file_menu(files)
        self.bot.reply_to(
            message,
            f"📂 **Your Files** ({len(files)} total)\n\nClick a file to manage it:",
            reply_markup=markup,
            parse_mode='Markdown'
        )
    
    def _handle_ping(self, message):
        """Handle ping command"""
        start = time.time()
        msg = self.bot.reply_to(message, "🏓 Pong!")
        end = time.time()
        latency = round((end - start) * 1000, 2)
        self.bot.edit_message_text(
            f"🏓 **Pong!**\n\n⏱️ **Latency:** {latency}ms\n"
            f"🖥️ **Server:** {platform.node()}\n"
            f"🐍 **Python:** {sys.version.split()[0]}",
            message.chat.id,
            msg.message_id,
            parse_mode='Markdown'
        )
    
    def _handle_admin(self, message):
        """Handle admin command"""
        user_id = message.from_user.id
        
        if self._is_user_banned(user_id):
            return
        
        if user_id not in self.admin_ids:
            self.bot.reply_to(message, "⚠️ **Admin Access Required**", parse_mode='Markdown')
            return
        
        markup = self._create_admin_menu()
        self.bot.reply_to(
            message,
            "👑 **Admin Panel**\n\nManage users, files, and system settings:",
            reply_markup=markup,
            parse_mode='Markdown'
        )
    
    def _handle_lock(self, message):
        """Handle lock command"""
        user_id = message.from_user.id
        
        if user_id not in self.admin_ids:
            return
        
        self.bot_locked = True
        self.bot.reply_to(message, "🔒 **Bot Locked**\n\nOnly admins can use the bot.", parse_mode='Markdown')
    
    def _handle_unlock(self, message):
        """Handle unlock command"""
        user_id = message.from_user.id
        
        if user_id not in self.admin_ids:
            return
        
        self.bot_locked = False
        self.bot.reply_to(message, "🔓 **Bot Unlocked**\n\nAll users can use the bot.", parse_mode='Markdown')
    
    def _handle_broadcast(self, message):
        """Handle broadcast command"""
        user_id = message.from_user.id
        
        if user_id not in self.admin_ids:
            self.bot.reply_to(message, "⚠️ **Admin Access Required**", parse_mode='Markdown')
            return
        
        msg = self.bot.reply_to(
            message,
            "📢 **Broadcast Message**\n\n"
            "Send me the message to broadcast to all users.\n"
            "You can include text, images, or documents.\n\n"
            "Type /cancel to cancel.",
            parse_mode='Markdown'
        )
        self.bot.register_next_step_handler(msg, self._process_broadcast)
    
    def _process_broadcast(self, message):
        """Process broadcast message"""
        user_id = message.from_user.id
        
        if user_id not in self.admin_ids:
            return
        
        if message.text and message.text.lower() == '/cancel':
            self.bot.reply_to(message, "📢 Broadcast cancelled.")
            return
        
        users = self._get_all_users()
        
        if not users:
            self.bot.reply_to(message, "❌ No users to broadcast to.")
            return
        
        # Show confirmation
        confirm_msg = self.bot.reply_to(
            message,
            f"📢 **Broadcast Confirmation**\n\n"
            f"Sending to **{len(users)}** users.\n\n"
            f"Message preview:\n"
            f"```\n{message.text[:200]}{'...' if len(message.text or '') > 200 else ''}\n```\n"
            f"Are you sure?",
            parse_mode='Markdown'
        )
        
        # Send broadcast
        success = 0
        failed = 0
        blocked = 0
        
        for user in users:
            try:
                if message.text:
                    self.bot.send_message(user['user_id'], message.text)
                elif message.photo:
                    self.bot.send_photo(user['user_id'], message.photo[-1].file_id, caption=message.caption)
                elif message.document:
                    self.bot.send_document(user['user_id'], message.document.file_id, caption=message.caption)
                success += 1
                time.sleep(0.05)
            except Exception as e:
                failed += 1
                if "blocked" in str(e).lower():
                    blocked += 1
                logging.warning(f"Broadcast failed to {user['user_id']}: {e}")
        
        self.bot.edit_message_text(
            f"📢 **Broadcast Complete**\n\n"
            f"✅ Sent: {success}\n"
            f"❌ Failed: {failed}\n"
            f"🚫 Blocked: {blocked}\n"
            f"👥 Total: {len(users)}",
            confirm_msg.chat.id,
            confirm_msg.message_id,
            parse_mode='Markdown'
        )
    
    def _handle_settings(self, message):
        """Handle settings command"""
        user_id = message.from_user.id
        
        if self._is_user_banned(user_id):
            return
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("🌐 Language", callback_data='settings_lang'),
            types.InlineKeyboardButton("🔔 Notifications", callback_data='settings_notif')
        )
        markup.add(
            types.InlineKeyboardButton("📋 Export Data", callback_data='settings_export'),
            types.InlineKeyboardButton("🗑️ Clear Data", callback_data='settings_clear')
        )
        markup.add(types.InlineKeyboardButton("🔙 Back", callback_data='main'))
        
        self.bot.reply_to(
            message,
            "⚙️ **Settings**\n\nCustomize your bot experience:",
            reply_markup=markup,
            parse_mode='Markdown'
        )
    
    def _handle_profile(self, message):
        """Handle profile command"""
        user_id = message.from_user.id
        
        if self._is_user_banned(user_id):
            return
        
        user_data = self._get_user_data(user_id)
        subscription = self._get_user_subscription(user_id)
        files = self._get_user_files(user_id)
        
        profile_text = (
            f"👤 **User Profile**\n\n"
            f"🆔 **User ID:** `{user_id}`\n"
            f"👤 **Name:** {user_data.get('first_name', 'Unknown')}\n"
            f"✳️ **Username:** @{user_data.get('username', 'Not set')}\n"
            f"📅 **Joined:** {user_data.get('created_at', 'Unknown')}\n"
            f"📂 **Files:** {len(files)}\n"
        )
        
        if subscription:
            expiry = subscription.get('expiry')
            if expiry:
                if isinstance(expiry, str):
                    try:
                        expiry = datetime.fromisoformat(expiry)
                    except:
                        expiry = None
                if expiry and expiry > datetime.now():
                    days_left = (expiry - datetime.now()).days
                    profile_text += f"💎 **Premium:** Yes (Expires in {days_left} days)\n"
                else:
                    profile_text += "🆓 **Premium:** No\n"
            else:
                profile_text += "🆓 **Premium:** No\n"
        else:
            profile_text += "🆓 **Premium:** No\n"
        
        if user_id in self.admin_ids:
            role = "Owner" if user_id == config.OWNER_ID else "Admin"
            profile_text += f"🛡️ **Role:** {role}\n"
        
        self.bot.reply_to(message, profile_text, parse_mode='Markdown')
    
    def _handle_backup(self, message):
        """Handle backup command"""
        user_id = message.from_user.id
        
        if self._is_user_banned(user_id):
            return
        
        files = self._get_user_files(user_id)
        if not files:
            self.bot.reply_to(message, "📂 **No Files to Backup**", parse_mode='Markdown')
            return
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        for file in files[:10]:
            markup.add(
                types.InlineKeyboardButton(
                    f"💾 {file['file_name']}",
                    callback_data=f"backup_file_{file['id']}"
                )
            )
        markup.add(types.InlineKeyboardButton("🔙 Back", callback_data='main'))
        
        self.bot.reply_to(
            message,
            "💾 **Backup Manager**\n\nSelect a file to backup:",
            reply_markup=markup,
            parse_mode='Markdown'
        )
    
    def _handle_restore(self, message):
        """Handle restore command"""
        user_id = message.from_user.id
        
        if self._is_user_banned(user_id):
            return
        
        backups = self.backup_manager.list_backups(user_id)
        if not backups:
            self.bot.reply_to(message, "📂 **No Backups Found**", parse_mode='Markdown')
            return
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        for backup in backups[:10]:
            markup.add(
                types.InlineKeyboardButton(
                    f"📥 {backup['file_name']} ({backup['created_at'][:10]})",
                    callback_data=f"restore_{backup['backup_id']}"
                )
            )
        markup.add(types.InlineKeyboardButton("🔙 Back", callback_data='main'))
        
        self.bot.reply_to(
            message,
            "📥 **Restore Manager**\n\nSelect a backup to restore:",
            reply_markup=markup,
            parse_mode='Markdown'
        )
    
    def _handle_cleanup(self, message):
        """Handle cleanup command"""
        user_id = message.from_user.id
        
        if user_id not in self.admin_ids:
            return
        
        self.bot.reply_to(message, "🧹 **Cleaning up system resources...**", parse_mode='Markdown')
        self._cleanup_system()
        self.bot.reply_to(message, "✅ **Cleanup Complete**", parse_mode='Markdown')
    
    def _handle_ban(self, message):
        """Handle ban command"""
        user_id = message.from_user.id
        
        if user_id not in self.admin_ids:
            return
        
        try:
            parts = message.text.split()
            if len(parts) < 2:
                self.bot.reply_to(
                    message,
                    "⚠️ **Usage:** `/ban <user_id> [reason]`",
                    parse_mode='Markdown'
                )
                return
            
            target_id = int(parts[1])
            reason = " ".join(parts[2:]) if len(parts) > 2 else "No reason provided"
            
            if target_id in self.admin_ids:
                self.bot.reply_to(message, "⚠️ Cannot ban an admin.", parse_mode='Markdown')
                return
            
            self._ban_user(target_id, reason)
            self.bot.reply_to(
                message,
                f"✅ **User Banned**\n\nUser ID: `{target_id}`\nReason: {reason}",
                parse_mode='Markdown'
            )
            
            try:
                self.bot.send_message(
                    target_id,
                    f"🚫 **You have been banned**\n\nReason: {reason}",
                    parse_mode='Markdown'
                )
            except:
                pass
                
        except ValueError:
            self.bot.reply_to(message, "⚠️ Invalid user ID.", parse_mode='Markdown')
        except Exception as e:
            self.bot.reply_to(message, f"❌ Error: {str(e)}", parse_mode='Markdown')
    
    def _handle_unban(self, message):
        """Handle unban command"""
        user_id = message.from_user.id
        
        if user_id not in self.admin_ids:
            return
        
        try:
            parts = message.text.split()
            if len(parts) < 2:
                self.bot.reply_to(
                    message,
                    "⚠️ **Usage:** `/unban <user_id>`",
                    parse_mode='Markdown'
                )
                return
            
            target_id = int(parts[1])
            
            self._unban_user(target_id)
            self.bot.reply_to(
                message,
                f"✅ **User Unbanned**\n\nUser ID: `{target_id}`",
                parse_mode='Markdown'
            )
            
            try:
                self.bot.send_message(
                    target_id,
                    "✅ **You have been unbanned**\n\nYou can now use the bot again.",
                    parse_mode='Markdown'
                )
            except:
                pass
                
        except ValueError:
            self.bot.reply_to(message, "⚠️ Invalid user ID.", parse_mode='Markdown')
        except Exception as e:
            self.bot.reply_to(message, f"❌ Error: {str(e)}", parse_mode='Markdown')
    
    def _handle_listusers(self, message):
        """Handle listusers command"""
        user_id = message.from_user.id
        
        if user_id not in self.admin_ids:
            return
        
        users = self._get_all_users()
        if not users:
            self.bot.reply_to(message, "👥 **No Users Found**", parse_mode='Markdown')
            return
        
        user_list = "👥 **Users**\n\n"
        for i, user in enumerate(users[:20], 1):
            status = "🔴 Banned" if user.get('is_banned', False) else "🟢 Active"
            user_list += f"{i}. `{user['user_id']}` - {user.get('first_name', 'Unknown')} ({status})\n"
        
        if len(users) > 20:
            user_list += f"\n... and {len(users) - 20} more users"
        
        self.bot.reply_to(message, user_list, parse_mode='Markdown')
    
    def _handle_message(self, message):
        """Handle regular messages"""
        user_id = message.from_user.id
        text = message.text
        
        if self._is_user_banned(user_id):
            return
        
        if self.bot_locked and user_id not in self.admin_ids:
            self.bot.reply_to(message, "🔒 Bot is currently locked.")
            return
        
        # Reply keyboard actions
        if text == "📊 Stats":
            self._handle_stats(message)
        elif text == "📂 My Files":
            self._handle_files(message)
        elif text == "📤 Upload":
            self._handle_upload(message)
        elif text == "🔄 Refresh":
            self._handle_files(message)
        elif text == "👑 Admin Panel":
            self._handle_admin(message)
        elif text == "📢 Broadcast":
            self._handle_broadcast(message)
        elif text == "⚙️ Settings":
            self._handle_settings(message)
        elif text == "👤 Profile":
            self._handle_profile(message)
        elif text == "💾 Backup":
            self._handle_backup(message)
    
    # ============================================================
    # FILE UPLOAD HANDLER
    # ============================================================
    
    def _handle_file_upload(self, message):
        """Handle file upload"""
        user_id = message.from_user.id
        chat_id = message.chat.id
        
        if self._is_user_banned(user_id):
            return
        
        if self.bot_locked and user_id not in self.admin_ids:
            self.bot.reply_to(message, "🔒 Bot is currently locked.")
            return
        
        document = message.document
        file_name = document.file_name
        
        # Validate file type
        ext = os.path.splitext(file_name)[1].lower()
        if ext not in ['.py', '.js', '.zip']:
            self.bot.reply_to(
                message,
                f"❌ **Unsupported File Type**\n\nOnly `.py`, `.js`, and `.zip` files are allowed.",
                parse_mode='Markdown'
            )
            return
        
        # Check file size
        if document.file_size > config.MAX_FILE_SIZE:
            self.bot.reply_to(
                message,
                f"❌ **File Too Large**\n\nMax size: {config.MAX_FILE_SIZE // 1024 // 1024}MB",
                parse_mode='Markdown'
            )
            return
        
        # Check file limit
        user_files = self._get_user_files(user_id)
        user_limit = self._get_user_limit(user_id)
        if len(user_files) >= user_limit:
            self.bot.reply_to(
                message,
                f"⚠️ **File Limit Reached**\n\nYou have {len(user_files)}/{user_limit} files.",
                parse_mode='Markdown'
            )
            return
        
        status_msg = self.bot.reply_to(
            message,
            f"⏳ **Processing Upload**\n\nFile: `{file_name}`",
            parse_mode='Markdown'
        )
        
        try:
            # Download file
            file_info = self.bot.get_file(document.file_id)
            file_content = self.bot.download_file(file_info.file_path)
            
            # Security scan
            scan_result = self._scan_file(file_content, file_name, user_id)
            if not scan_result['safe']:
                self.bot.edit_message_text(
                    f"🚨 **Security Alert**\n\nFile: `{file_name}`\nReason: {scan_result['reason']}",
                    chat_id,
                    status_msg.message_id,
                    parse_mode='Markdown'
                )
                return
            
            # Save file
            user_folder = self._get_user_folder(user_id)
            file_path = os.path.join(user_folder, file_name)
            
            if ext == '.zip':
                self._process_zip(file_content, file_name, user_id, status_msg)
            else:
                with open(file_path, 'wb') as f:
                    f.write(file_content)
                
                # Save to database
                file_id = self._save_file_record(user_id, file_name, ext[1:], len(file_content))
                
                # Create backup
                self.backup_manager.create_backup(user_id, file_name, file_path)
                
                self.bot.edit_message_text(
                    f"✅ **Upload Complete**\n\nFile: `{file_name}`\nStatus: Ready\n📂 ID: `{file_id}`",
                    chat_id,
                    status_msg.message_id,
                    parse_mode='Markdown'
                )
                
        except Exception as e:
            logging.error(f"File upload error: {e}")
            self.bot.edit_message_text(
                f"❌ **Upload Failed**\n\nError: {str(e)}",
                chat_id,
                status_msg.message_id,
                parse_mode='Markdown'
            )
    
    def _process_zip(self, file_content, file_name, user_id, status_msg):
        """Process ZIP archive"""
        chat_id = status_msg.chat.id
        user_folder = self._get_user_folder(user_id)
        
        temp_dir = tempfile.mkdtemp(prefix=f"zip_{user_id}_")
        
        try:
            zip_path = os.path.join(temp_dir, file_name)
            with open(zip_path, 'wb') as f:
                f.write(file_content)
            
            # Security check for zip
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                for member in zip_ref.infolist():
                    member_path = os.path.abspath(os.path.join(temp_dir, member.filename))
                    if not member_path.startswith(os.path.abspath(temp_dir)):
                        raise Exception(f"Unsafe path: {member.filename}")
                
                zip_ref.extractall(temp_dir)
            
            self.bot.edit_message_text(
                f"⏳ **Processing ZIP**\n\nFile: `{file_name}`\nStatus: Extracted, finding main script...",
                chat_id,
                status_msg.message_id,
                parse_mode='Markdown'
            )
            
            # Install dependencies if present
            self._install_dependencies(temp_dir, status_msg)
            
            # Find main script
            main_script = self._find_main_script(temp_dir)
            if not main_script:
                self.bot.edit_message_text(
                    f"❌ **No Script Found**\n\nNo Python or JavaScript file found in the archive.",
                    chat_id,
                    status_msg.message_id,
                    parse_mode='Markdown'
                )
                return
            
            # Move files to user folder
            for item in os.listdir(temp_dir):
                if item == file_name:
                    continue
                src = os.path.join(temp_dir, item)
                dst = os.path.join(user_folder, item)
                if os.path.exists(dst):
                    if os.path.isdir(dst):
                        shutil.rmtree(dst)
                    else:
                        os.remove(dst)
                shutil.move(src, dst)
            
            # Save to database
            file_id = self._save_file_record(
                user_id, main_script,
                os.path.splitext(main_script)[1][1:],
                os.path.getsize(os.path.join(user_folder, main_script))
            )
            
            # Create backup
            self.backup_manager.create_backup(user_id, main_script, os.path.join(user_folder, main_script))
            
            self.bot.edit_message_text(
                f"✅ **ZIP Processed**\n\nMain Script: `{main_script}`\n📂 ID: `{file_id}`",
                chat_id,
                status_msg.message_id,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logging.error(f"ZIP processing error: {e}")
            self.bot.edit_message_text(
                f"❌ **ZIP Error**\n\n{str(e)}",
                chat_id,
                status_msg.message_id,
                parse_mode='Markdown'
            )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
    
    def _install_dependencies(self, directory, status_msg):
        """Install dependencies from requirements.txt or package.json"""
        chat_id = status_msg.chat.id
        
        # Check requirements.txt
        req_path = os.path.join(directory, 'requirements.txt')
        if os.path.exists(req_path):
            self.bot.edit_message_text(
                f"⏳ **Installing Dependencies**\n\nFound requirements.txt\nInstalling Python packages...",
                chat_id,
                status_msg.message_id,
                parse_mode='Markdown'
            )
            
            try:
                subprocess.run(
                    [sys.executable, '-m', 'pip', 'install', '-r', req_path],
                    capture_output=True,
                    text=True,
                    check=True,
                    timeout=60
                )
            except Exception as e:
                logging.warning(f"Requirements installation warning: {e}")
        
        # Check package.json
        pkg_path = os.path.join(directory, 'package.json')
        if os.path.exists(pkg_path):
            self.bot.edit_message_text(
                f"⏳ **Installing Dependencies**\n\nFound package.json\nInstalling Node packages...",
                chat_id,
                status_msg.message_id,
                parse_mode='Markdown'
            )
            
            try:
                subprocess.run(
                    ['npm', 'install'],
                    cwd=directory,
                    capture_output=True,
                    text=True,
                    check=True,
                    timeout=120
                )
            except Exception as e:
                logging.warning(f"npm install warning: {e}")
    
    def _find_main_script(self, directory):
        """Find main script in extracted archive"""
        common_names = ['main.py', 'bot.py', 'app.py', 'index.js', 'main.js', 'server.js']
        
        for name in common_names:
            if os.path.exists(os.path.join(directory, name)):
                return name
        
        for root, dirs, files in os.walk(directory):
            dirs[:] = [d for d in dirs if not d.startswith('.') and not d.startswith('__')]
            for file in files:
                if file.endswith(('.py', '.js')):
                    return file
        
        return None
    
    # ============================================================
    # SCANNING FUNCTIONS
    # ============================================================
    
    def _scan_file(self, file_content: bytes, file_name: str, user_id: int) -> dict:
        """Scan file for malware"""
        # Owner bypass
        if user_id == config.OWNER_ID:
            return {'safe': True, 'reason': 'Owner bypass'}
        
        # Check for executable signatures
        for sig in config.MALWARE_SIGNATURES:
            if file_content.startswith(sig):
                return {'safe': False, 'reason': f'Executable signature detected: {sig.hex()}'}
        
        # Check for suspicious keywords in first 4KB
        try:
            sample = file_content[:4096].decode('utf-8', errors='ignore')
            suspicious_keywords = [
                'ransomware', 'trojan', 'virus', 'malware',
                'backdoor', 'exploit', 'payload', 'botnet',
                'keylogger', 'rootkit', 'rm -rf', 'os.remove',
                'shutil.rmtree', 'subprocess.call', 'eval(', 'exec(',
                '__import__', 'compile(', 'globals(', 'locals('
            ]
            for keyword in suspicious_keywords:
                if keyword in sample.lower():
                    return {'safe': False, 'reason': f'Suspicious keyword: {keyword}'}
        except Exception:
            pass
        
        # Check file extensions
        suspicious_extensions = ['.exe', '.dll', '.bat', '.cmd', '.scr', '.com', '.pif', '.application']
        if any(file_name.lower().endswith(ext) for ext in suspicious_extensions):
            return {'safe': False, 'reason': 'Suspicious file extension'}
        
        return {'safe': True, 'reason': 'File appears safe'}
    
    # ============================================================
    # CALLBACK HANDLER
    # ============================================================
    
    def _handle_callback(self, call):
        """Handle callback queries"""
        user_id = call.from_user.id
        data = call.data
        
        if self._is_user_banned(user_id):
            self.bot.answer_callback_query(call.id, "🚫 You are banned.", show_alert=True)
            return
        
        # Handle force join check
        if data == 'check_join':
            if self._check_force_join(user_id):
                self.bot.answer_callback_query(call.id, "✅ All channels joined!")
                self._handle_start(call.message)
            else:
                self.bot.answer_callback_query(call.id, "❌ Please join all channels first", show_alert=True)
            return
        
        # Main menu
        if data == 'main':
            markup = self._create_main_menu(user_id)
            self.bot.edit_message_reply_markup(
                call.message.chat.id,
                call.message.message_id,
                reply_markup=markup
            )
            self.bot.answer_callback_query(call.id)
        
        # Files
        elif data == 'files':
            files = self._get_user_files(user_id)
            if not files:
                self.bot.answer_callback_query(call.id, "📂 No files found", show_alert=True)
                return
            markup = self._create_file_menu(files)
            self.bot.edit_message_reply_markup(
                call.message.chat.id,
                call.message.message_id,
                reply_markup=markup
            )
            self.bot.answer_callback_query(call.id)
        
        # Refresh files
        elif data == 'refresh_files':
            files = self._get_user_files(user_id)
            markup = self._create_file_menu(files)
            self.bot.edit_message_reply_markup(
                call.message.chat.id,
                call.message.message_id,
                reply_markup=markup
            )
            self.bot.answer_callback_query(call.id, "🔄 Refreshed!")
        
        # File page navigation
        elif data.startswith('file_page_'):
            page = int(data.split('_')[2])
            files = self._get_user_files(user_id)
            menu_manager = MenuManager(user_id)
            markup = menu_manager.file_management_menu(files, page)
            self.bot.edit_message_reply_markup(
                call.message.chat.id,
                call.message.message_id,
                reply_markup=markup
            )
            self.bot.answer_callback_query(call.id)
        
        # Stats
        elif data == 'stats':
            self.bot.answer_callback_query(call.id)
            self._handle_stats(call.message)
        
        # Upload
        elif data == 'upload':
            self.bot.answer_callback_query(call.id)
            self._handle_upload(call.message)
        
        # Speed
        elif data == 'speed':
            start = time.time()
            self.bot.answer_callback_query(call.id)
            try:
                self.bot.send_chat_action(call.message.chat.id, 'typing')
                latency = round((time.time() - start) * 1000, 2)
                self.bot.send_message(
                    call.message.chat.id,
                    f"⚡ **Bot Speed**\n\n"
                    f"📡 **Latency:** {latency}ms\n"
                    f"🖥️ **Server:** {platform.node()}\n"
                    f"🐍 **Python:** {sys.version.split()[0]}",
                    parse_mode='Markdown'
                )
            except Exception as e:
                logging.error(f"Speed test error: {e}")
        
        # Help
        elif data == 'help':
            help_text = (
                "🆘 **Help & Support**\n\n"
                "**Commands:**\n"
                "/start - Start the bot\n"
                "/help - Show this help\n"
                "/upload - Upload a file\n"
                "/myfiles - View your files\n"
                "/stats - View statistics\n"
                "/profile - View your profile\n"
                "/settings - Change settings\n"
                "/ping - Check bot latency\n"
                "/backup - Backup your files\n"
                "/restore - Restore from backup\n\n"
                "**File Types:**\n"
                "• Python (.py)\n"
                "• JavaScript (.js)\n"
                "• ZIP Archives (.zip)\n\n"
                "**Admin Commands:**\n"
                "/admin - Admin panel\n"
                "/lock - Lock the bot\n"
                "/unlock - Unlock the bot\n"
                "/broadcast - Send broadcast\n"
                "/ban - Ban a user\n"
                "/unban - Unban a user\n"
                "/listusers - List all users\n"
                "/cleanup - Cleanup system\n\n"
                f"**Contact:** {config.YOUR_USERNAME}"
            )
            self.bot.send_message(call.message.chat.id, help_text, parse_mode='Markdown')
            self.bot.answer_callback_query(call.id)
        
        # Settings
        elif data == 'settings':
            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.add(
                types.InlineKeyboardButton("🌐 Language", callback_data='settings_lang'),
                types.InlineKeyboardButton("🔔 Notifications", callback_data='settings_notif')
            )
            markup.add(
                types.InlineKeyboardButton("📋 Export Data", callback_data='settings_export'),
                types.InlineKeyboardButton("🗑️ Clear Data", callback_data='settings_clear')
            )
            markup.add(types.InlineKeyboardButton("🔙 Back", callback_data='main'))
            
            self.bot.edit_message_text(
                "⚙️ **Settings**\n\nCustomize your bot experience:",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=markup,
                parse_mode='Markdown'
            )
            self.bot.answer_callback_query(call.id)
        
        # Profile
        elif data == 'profile':
            self.bot.answer_callback_query(call.id)
            self._handle_profile(call.message)
        
        # File management
        elif data.startswith('file_'):
            file_id = int(data.split('_')[1])
            file_data = self._get_file_by_id(file_id)
            if not file_data:
                self.bot.answer_callback_query(call.id, "File not found", show_alert=True)
                return
            
            # Check ownership
            if file_data['user_id'] != user_id and user_id not in self.admin_ids:
                self.bot.answer_callback_query(call.id, "Not your file", show_alert=True)
                return
            
            markup = self._create_file_controls(file_data)
            self.bot.edit_message_reply_markup(
                call.message.chat.id,
                call.message.message_id,
                reply_markup=markup
            )
            self.bot.answer_callback_query(call.id)
        
        # File controls
        elif data.startswith('start_'):
            file_id = int(data.split('_')[1])
            self._start_file(file_id, user_id, call)
        
        elif data.startswith('stop_'):
            file_id = int(data.split('_')[1])
            self._stop_file(file_id, user_id, call)
        
        elif data.startswith('restart_'):
            file_id = int(data.split('_')[1])
            self._restart_file(file_id, user_id, call)
        
        elif data.startswith('delete_'):
            file_id = int(data.split('_')[1])
            self._delete_file(file_id, user_id, call)
        
        elif data.startswith('logs_'):
            file_id = int(data.split('_')[1])
            self._view_logs(file_id, user_id, call)
        
        elif data.startswith('download_'):
            file_id = int(data.split('_')[1])
            self._download_file(file_id, user_id, call)
        
        elif data.startswith('backup_'):
            file_id = int(data.split('_')[1])
            self._backup_file(file_id, user_id, call)
        
        elif data.startswith('backup_file_'):
            file_id = int(data.split('_')[2])
            self._backup_file(file_id, user_id, call)
        
        elif data.startswith('restore_'):
            backup_id = data.split('_')[1]
            self._restore_backup(backup_id, user_id, call)
        
        elif data.startswith('resources_'):
            file_id = int(data.split('_')[1])
            self._view_resources(file_id, user_id, call)
        
        # Admin panel
        elif data == 'admin_panel':
            if user_id not in self.admin_ids:
                self.bot.answer_callback_query(call.id, "⚠️ Admin required", show_alert=True)
                return
            markup = self._create_admin_menu()
            self.bot.edit_message_reply_markup(
                call.message.chat.id,
                call.message.message_id,
                reply_markup=markup
            )
            self.bot.answer_callback_query(call.id)
        
        elif data == 'admin_stats':
            if user_id not in self.admin_ids:
                return
            total_users = len(self._get_all_users())
            total_files = self._get_total_files()
            running_processes = len(self.process_manager.get_all_processes())
            storage_used = self._get_storage_used()
            
            self.bot.send_message(
                call.message.chat.id,
                f"📊 **Admin Statistics**\n\n"
                f"👥 **Users:** {total_users}\n"
                f"📂 **Files:** {total_files}\n"
                f"🟢 **Running Bots:** {running_processes}\n"
                f"💾 **Storage:** {self._format_size(storage_used)}\n"
                f"🔒 **Bot:** {'Locked' if self.bot_locked else 'Unlocked'}",
                parse_mode='Markdown'
            )
            self.bot.answer_callback_query(call.id)
        
        elif data == 'admin_lock':
            if user_id not in self.admin_ids:
                return
            self.bot_locked = not self.bot_locked
            status = "locked" if self.bot_locked else "unlocked"
            self.bot.answer_callback_query(call.id, f"🔒 Bot {status}!")
            self.bot.send_message(
                call.message.chat.id,
                f"🔒 Bot has been {status}.",
                parse_mode='Markdown'
            )
        
        elif data == 'admin_broadcast':
            if user_id not in self.admin_ids:
                return
            self.bot.answer_callback_query(call.id)
            self._handle_broadcast(call.message)
        
        elif data == 'admin_cleanup':
            if user_id not in self.admin_ids:
                return
            self.bot.answer_callback_query(call.id, "🧹 Cleaning up...")
            self._cleanup_system()
            self.bot.send_message(
                call.message.chat.id,
                "🧹 **Cleanup Complete**\n\n"
                "• Stopped orphaned processes\n"
                "• Removed temporary files\n"
                "• Freed system resources",
                parse_mode='Markdown'
            )
        
        elif data == 'admin_users':
            if user_id not in self.admin_ids:
                return
            users = self._get_all_users()
            user_text = f"👥 **Users** ({len(users)} total)\n\n"
            for i, user in enumerate(users[:20], 1):
                status = "🔴 Banned" if user.get('is_banned', False) else "🟢 Active"
                user_text += f"{i}. `{user['user_id']}` - {user.get('first_name', 'Unknown')} ({status})\n"
            if len(users) > 20:
                user_text += f"\n... and {len(users) - 20} more"
            
            self.bot.send_message(call.message.chat.id, user_text, parse_mode='Markdown')
            self.bot.answer_callback_query(call.id)
        
        elif data == 'admin_banned':
            if user_id not in self.admin_ids:
                return
            banned = self._get_banned_users()
            if banned:
                ban_text = "🚫 **Banned Users**\n\n"
                for user in banned:
                    ban_text += f"• `{user['user_id']}` - {user.get('ban_reason', 'No reason')}\n"
                self.bot.send_message(call.message.chat.id, ban_text, parse_mode='Markdown')
            else:
                self.bot.send_message(call.message.chat.id, "🚫 No banned users.")
            self.bot.answer_callback_query(call.id)
        
        elif data == 'admin_run_all':
            if user_id not in self.admin_ids:
                return
            self.bot.answer_callback_query(call.id, "⏳ Starting all scripts...")
            self._run_all_scripts(call.message.chat.id)
        
        elif data == 'admin_backup_all':
            if user_id not in self.admin_ids:
                return
            self.bot.answer_callback_query(call.id, "💾 Backing up all files...")
            self._backup_all_files(call.message.chat.id)
        
        elif data == 'admin_restore_all':
            if user_id not in self.admin_ids:
                return
            self.bot.answer_callback_query(call.id, "📥 Restoring all files...")
            self._restore_all_files(call.message.chat.id)
        
        # Settings actions
        elif data == 'settings_lang':
            self.bot.answer_callback_query(call.id, "🌐 Language settings coming soon!", show_alert=True)
        
        elif data == 'settings_notif':
            self.bot.answer_callback_query(call.id, "🔔 Notification settings coming soon!", show_alert=True)
        
        elif data == 'settings_export':
            self.bot.answer_callback_query(call.id, "📋 Exporting your data...")
            self._export_user_data(user_id, call.message.chat.id)
        
        elif data == 'settings_clear':
            self.bot.answer_callback_query(call.id, "🗑️ Clear your data? Use /myfiles to delete files.", show_alert=True)
        
        # No operation
        elif data == 'noop':
            self.bot.answer_callback_query(call.id)
        
        else:
            self.bot.answer_callback_query(call.id, "Unknown action", show_alert=True)
            logging.warning(f"Unknown callback: {data}")
    
    # ============================================================
    # FILE CONTROL FUNCTIONS
    # ============================================================
    
    def _start_file(self, file_id, user_id, call):
        """Start a file"""
        file_data = self._get_file_by_id(file_id)
        if not file_data:
            self.bot.answer_callback_query(call.id, "File not found", show_alert=True)
            return
        
        if file_data['user_id'] != user_id and user_id not in self.admin_ids:
            self.bot.answer_callback_query(call.id, "Not your file", show_alert=True)
            return
        
        script_key = f"{user_id}_{file_data['file_name']}"
        
        # Check if already running
        if script_key in self.process_manager._processes:
            self.bot.answer_callback_query(call.id, "⚠️ Already running", show_alert=True)
            return
        
        self.bot.answer_callback_query(call.id, "⏳ Starting...")
        
        file_path = os.path.join(self._get_user_folder(user_id), file_data['file_name'])
        
        if not os.path.exists(file_path):
            self.bot.send_message(call.message.chat.id, f"❌ File `{file_data['file_name']}` not found on disk.", parse_mode='Markdown')
            return
        
        try:
            if file_data['file_type'] == 'py':
                command = [sys.executable, file_path]
            else:
                command = ['node', file_path]
            
            success = self.process_manager.start_process(
                script_key,
                command,
                self._get_user_folder(user_id),
                {**os.environ, "PYTHONIOENCODING": "utf-8"}
            )
            
            if success:
                self._update_file_status(user_id, file_data['file_name'], True, 
                                        self.process_manager._processes[script_key]['pid'])
                self.bot.send_message(
                    call.message.chat.id,
                    f"✅ **Script Started**\n\nFile: `{file_data['file_name']}`\n🟢 Running",
                    parse_mode='Markdown'
                )
            else:
                self.bot.send_message(
                    call.message.chat.id,
                    f"❌ **Start Failed**\n\nFile: `{file_data['file_name']}`",
                    parse_mode='Markdown'
                )
                
        except Exception as e:
            logging.error(f"Start file error: {e}")
            self.bot.send_message(
                call.message.chat.id,
                f"❌ **Start Error**\n\n{str(e)}",
                parse_mode='Markdown'
            )
        
        # Refresh controls
        updated_data = self._get_file_by_id(file_id)
        markup = self._create_file_controls(updated_data)
        self.bot.edit_message_reply_markup(
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup
        )
    
    def _stop_file(self, file_id, user_id, call):
        """Stop a file"""
        file_data = self._get_file_by_id(file_id)
        if not file_data:
            self.bot.answer_callback_query(call.id, "File not found", show_alert=True)
            return
        
        if file_data['user_id'] != user_id and user_id not in self.admin_ids:
            self.bot.answer_callback_query(call.id, "Not your file", show_alert=True)
            return
        
        script_key = f"{user_id}_{file_data['file_name']}"
        
        success = self.process_manager.stop_process(script_key)
        
        if success:
            self._update_file_status(user_id, file_data['file_name'], False)
            self.bot.answer_callback_query(call.id, "⏹️ Stopped!")
            self.bot.send_message(
                call.message.chat.id,
                f"⏹️ **Script Stopped**\n\nFile: `{file_data['file_name']}`\n🔴 Stopped",
                parse_mode='Markdown'
            )
        else:
            self.bot.answer_callback_query(call.id, "❌ Stop failed", show_alert=True)
        
        # Refresh controls
        updated_data = self._get_file_by_id(file_id)
        markup = self._create_file_controls(updated_data)
        self.bot.edit_message_reply_markup(
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup
        )
    
    def _restart_file(self, file_id, user_id, call):
        """Restart a file"""
        self.bot.answer_callback_query(call.id, "⏳ Restarting...")
        
        # Stop first
        self._stop_file(file_id, user_id, call)
        time.sleep(1)
        
        # Then start
        self._start_file(file_id, user_id, call)
    
    def _delete_file(self, file_id, user_id, call):
        """Delete a file"""
        file_data = self._get_file_by_id(file_id)
        if not file_data:
            self.bot.answer_callback_query(call.id, "File not found", show_alert=True)
            return
        
        if file_data['user_id'] != user_id and user_id not in self.admin_ids:
            self.bot.answer_callback_query(call.id, "Not your file", show_alert=True)
            return
        
        # Stop if running
        if file_data.get('is_running', False):
            script_key = f"{user_id}_{file_data['file_name']}"
            self.process_manager.stop_process(script_key)
        
        # Delete from database
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM user_files WHERE id = ?', (file_id,))
            conn.commit()
        
        # Delete from disk
        file_path = os.path.join(self._get_user_folder(user_id), file_data['file_name'])
        if os.path.exists(file_path):
            os.remove(file_path)
        
        # Delete log
        log_path = os.path.join(self._get_user_folder(user_id), 
                               f"{os.path.splitext(file_data['file_name'])[0]}.log")
        if os.path.exists(log_path):
            os.remove(log_path)
        
        self.bot.answer_callback_query(call.id, "🗑️ Deleted!")
        self.bot.send_message(
            call.message.chat.id,
            f"🗑️ **File Deleted**\n\nFile: `{file_data['file_name']}`",
            parse_mode='Markdown'
        )
        
        # Back to files
        files = self._get_user_files(user_id)
        markup = self._create_file_menu(files)
        self.bot.edit_message_text(
            f"📂 **Your Files** ({len(files)} total)",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode='Markdown'
        )
    
    def _view_logs(self, file_id, user_id, call):
        """View file logs"""
        file_data = self._get_file_by_id(file_id)
        if not file_data:
            self.bot.answer_callback_query(call.id, "File not found", show_alert=True)
            return
        
        if file_data['user_id'] != user_id and user_id not in self.admin_ids:
            self.bot.answer_callback_query(call.id, "Not your file", show_alert=True)
            return
        
        log_path = os.path.join(self._get_user_folder(user_id), 
                               f"{os.path.splitext(file_data['file_name'])[0]}.log")
        
        if not os.path.exists(log_path):
            self.bot.answer_callback_query(call.id, "📜 No logs yet", show_alert=True)
            return
        
        try:
            with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
                log_content = f.read()
            
            if len(log_content) > 4000:
                log_content = log_content[-4000:]
                log_content = "...\n" + log_content
            
            self.bot.send_message(
                call.message.chat.id,
                f"📜 **Logs for `{file_data['file_name']}`**\n\n```\n{log_content}\n```",
                parse_mode='Markdown'
            )
            self.bot.answer_callback_query(call.id)
        except Exception as e:
            self.bot.answer_callback_query(call.id, f"Error: {str(e)}", show_alert=True)
    
    def _download_file(self, file_id, user_id, call):
        """Download a file"""
        file_data = self._get_file_by_id(file_id)
        if not file_data:
            self.bot.answer_callback_query(call.id, "File not found", show_alert=True)
            return
        
        if file_data['user_id'] != user_id and user_id not in self.admin_ids:
            self.bot.answer_callback_query(call.id, "Not your file", show_alert=True)
            return
        
        file_path = os.path.join(self._get_user_folder(user_id), file_data['file_name'])
        
        if not os.path.exists(file_path):
            self.bot.answer_callback_query(call.id, "File not found on disk", show_alert=True)
            return
        
        try:
            with open(file_path, 'rb') as f:
                self.bot.send_document(
                    call.message.chat.id,
                    f,
                    caption=f"📥 **{file_data['file_name']}**"
                )
            self.bot.answer_callback_query(call.id, "📥 Downloading...")
        except Exception as e:
            self.bot.answer_callback_query(call.id, f"Error: {str(e)}", show_alert=True)
    
    def _backup_file(self, file_id, user_id, call):
        """Backup a file"""
        file_data = self._get_file_by_id(file_id)
        if not file_data:
            self.bot.answer_callback_query(call.id, "File not found", show_alert=True)
            return
        
        if file_data['user_id'] != user_id and user_id not in self.admin_ids:
            self.bot.answer_callback_query(call.id, "Not your file", show_alert=True)
            return
        
        file_path = os.path.join(self._get_user_folder(user_id), file_data['file_name'])
        
        if not os.path.exists(file_path):
            self.bot.answer_callback_query(call.id, "File not found on disk", show_alert=True)
            return
        
        backup_id = self.backup_manager.create_backup(user_id, file_data['file_name'], file_path)
        
        if backup_id:
            self.bot.answer_callback_query(call.id, "💾 Backup created!")
            self.bot.send_message(
                call.message.chat.id,
                f"💾 **Backup Created**\n\nFile: `{file_data['file_name']}`\nID: `{backup_id}`",
                parse_mode='Markdown'
            )
        else:
            self.bot.answer_callback_query(call.id, "❌ Backup failed", show_alert=True)
    
    def _restore_backup(self, backup_id, user_id, call):
        """Restore from backup"""
        backups = self.backup_manager.list_backups(user_id)
        backup = next((b for b in backups if b['backup_id'] == backup_id), None)
        
        if not backup:
            self.bot.answer_callback_query(call.id, "Backup not found", show_alert=True)
            return
        
        file_name = backup['file_name']
        file_path = os.path.join(self._get_user_folder(user_id), file_name)
        
        success = self.backup_manager.restore_backup(backup_id, file_path)
        
        if success:
            self.bot.answer_callback_query(call.id, "📥 Restored!")
            self.bot.send_message(
                call.message.chat.id,
                f"📥 **Backup Restored**\n\nFile: `{file_name}`",
                parse_mode='Markdown'
            )
        else:
            self.bot.answer_callback_query(call.id, "❌ Restore failed", show_alert=True)
    
    def _view_resources(self, file_id, user_id, call):
        """View resource usage"""
        file_data = self._get_file_by_id(file_id)
        if not file_data:
            self.bot.answer_callback_query(call.id, "File not found", show_alert=True)
            return
        
        if file_data['user_id'] != user_id and user_id not in self.admin_ids:
            self.bot.answer_callback_query(call.id, "Not your file", show_alert=True)
            return
        
        script_key = f"{user_id}_{file_data['file_name']}"
        process_info = self.process_manager.get_process_info(script_key)
        
        if process_info and process_info.get('is_running', False):
            resource_text = (
                f"📊 **Resource Usage**\n\n"
                f"📄 **File:** `{file_data['file_name']}`\n"
                f"🆔 **PID:** {process_info.get('pid', 'N/A')}\n"
                f"🧠 **CPU:** {process_info.get('cpu_percent', 0):.1f}%\n"
                f"💾 **Memory:** {process_info.get('memory_mb', 0):.1f} MB\n"
                f"🧵 **Threads:** {process_info.get('threads', 0)}\n"
                f"⏱️ **Uptime:** {self._format_uptime(process_info.get('start_time'))}"
            )
            self.bot.send_message(
                call.message.chat.id,
                resource_text,
                parse_mode='Markdown'
            )
        else:
            self.bot.answer_callback_query(call.id, "Script is not running", show_alert=True)
        
        self.bot.answer_callback_query(call.id)
    
    # ============================================================
    # ADMIN FUNCTIONS
    # ============================================================
    
    def _run_all_scripts(self, chat_id):
        """Run all user scripts"""
        users = self._get_all_users()
        started = 0
        skipped = 0
        
        for user in users:
            files = self._get_user_files(user['user_id'])
            for file_data in files:
                if not file_data.get('is_running', False):
                    file_path = os.path.join(
                        self._get_user_folder(user['user_id']),
                        file_data['file_name']
                    )
                    if os.path.exists(file_path):
                        if file_data['file_type'] == 'py':
                            command = [sys.executable, file_path]
                        else:
                            command = ['node', file_path]
                        
                        script_key = f"{user['user_id']}_{file_data['file_name']}"
                        self.process_manager.start_process(
                            script_key,
                            command,
                            self._get_user_folder(user['user_id']),
                            {**os.environ, "PYTHONIOENCODING": "utf-8"}
                        )
                        self._update_file_status(user['user_id'], file_data['file_name'], True)
                        started += 1
                        time.sleep(0.5)
                    else:
                        skipped += 1
        
        self.bot.send_message(
            chat_id,
            f"🔄 **Run All Scripts Complete**\n\n"
            f"▶️ Started: {started}\n"
            f"⏭️ Skipped: {skipped}",
            parse_mode='Markdown'
        )
    
    def _backup_all_files(self, chat_id):
        """Backup all files"""
        users = self._get_all_users()
        backed_up = 0
        
        for user in users:
            files = self._get_user_files(user['user_id'])
            for file_data in files:
                file_path = os.path.join(
                    self._get_user_folder(user['user_id']),
                    file_data['file_name']
                )
                if os.path.exists(file_path):
                    self.backup_manager.create_backup(
                        user['user_id'],
                        file_data['file_name'],
                        file_path
                    )
                    backed_up += 1
        
        self.bot.send_message(
            chat_id,
            f"💾 **Backup Complete**\n\n"
            f"✅ Backed up: {backed_up} files",
            parse_mode='Markdown'
        )
    
    def _restore_all_files(self, chat_id):
        """Restore all files from backup"""
        users = self._get_all_users()
        restored = 0
        
        for user in users:
            backups = self.backup_manager.list_backups(user['user_id'])
            for backup in backups:
                file_path = os.path.join(
                    self._get_user_folder(user['user_id']),
                    backup['file_name']
                )
                if self.backup_manager.restore_backup(backup['backup_id'], file_path):
                    restored += 1
        
        self.bot.send_message(
            chat_id,
            f"📥 **Restore Complete**\n\n"
            f"✅ Restored: {restored} files",
            parse_mode='Markdown'
        )
    
    def _cleanup_system(self):
        """Clean up system resources"""
        # Clean up processes
        self.process_manager.cleanup_stale_processes()
        
        # Clean up temporary files
        temp_dir = tempfile.gettempdir()
        for item in os.listdir(temp_dir):
            if item.startswith('zip_'):
                try:
                    shutil.rmtree(os.path.join(temp_dir, item), ignore_errors=True)
                except Exception:
                    pass
        
        # Clean up old logs
        user_folders = [f for f in os.listdir('upload_bots') 
                       if os.path.isdir(os.path.join('upload_bots', f))]
        for folder in user_folders:
            folder_path = os.path.join('upload_bots', folder)
            for file in os.listdir(folder_path):
                if file.endswith('.log'):
                    log_path = os.path.join(folder_path, file)
                    try:
                        if os.path.getsize(log_path) > config.MAX_LOG_SIZE:
                            with open(log_path, 'w') as f:
                                f.write("Log truncated by system cleanup\n")
                    except Exception:
                        pass
    
    def _export_user_data(self, user_id, chat_id):
        """Export user data"""
        try:
            user_data = self._get_user_data(user_id)
            files = self._get_user_files(user_id)
            subscription = self._get_user_subscription(user_id)
            
            export_data = {
                'user': dict(user_data),
                'files': files,
                'subscription': dict(subscription) if subscription else None,
                'exported_at': datetime.now().isoformat()
            }
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                json.dump(export_data, f, indent=2, default=str)
                temp_path = f.name
            
            with open(temp_path, 'rb') as f:
                self.bot.send_document(
                    chat_id,
                    f,
                    caption=f"📋 **Your Data Export**\n\nExported: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                )
            
            os.unlink(temp_path)
            
        except Exception as e:
            logging.error(f"Export error: {e}")
            self.bot.send_message(
                chat_id,
                f"❌ **Export Failed**\n\nError: {str(e)}",
                parse_mode='Markdown'
            )
    
    # ============================================================
    # MENU CREATION FUNCTIONS
    # ============================================================
    
    def _create_main_menu(self, user_id):
        """Create main menu markup"""
        markup = types.InlineKeyboardMarkup(row_width=2)
        
        markup.add(
            types.InlineKeyboardButton("📤 Upload", callback_data='upload'),
            types.InlineKeyboardButton("📂 My Files", callback_data='files')
        )
        
        markup.add(
            types.InlineKeyboardButton("📊 Stats", callback_data='stats'),
            types.InlineKeyboardButton("⚡ Speed", callback_data='speed')
        )
        
        markup.add(
            types.InlineKeyboardButton("👤 Profile", callback_data='profile'),
            types.InlineKeyboardButton("⚙️ Settings", callback_data='settings')
        )
        
        markup.add(
            types.InlineKeyboardButton("💾 Backup", callback_data='backup_all'),
            types.InlineKeyboardButton("🆘 Help", callback_data='help')
        )
        
        if user_id in self.admin_ids:
            markup.add(
                types.InlineKeyboardButton("👑 Admin Panel", callback_data='admin_panel')
            )
        
        return markup
    
    def _create_file_menu(self, files):
        """Create file management menu"""
        markup = types.InlineKeyboardMarkup(row_width=1)
        
        for file in files[:10]:
            status = "🟢" if file.get('is_running', False) else "🔴"
            markup.add(
                types.InlineKeyboardButton(
                    f"{status} {file['file_name']}",
                    callback_data=f"file_{file['id']}"
                )
            )
        
        if len(files) > 10:
            markup.add(
                types.InlineKeyboardButton(
                    f"📄 View All ({len(files)} files)",
                    callback_data="view_all_files"
                )
            )
        
        markup.add(types.InlineKeyboardButton("🔙 Back", callback_data='main'))
        return markup
    
    def _create_file_controls(self, file_data):
        """Create file control menu"""
        markup = types.InlineKeyboardMarkup(row_width=2)
        
        is_running = file_data.get('is_running', False)
        
        if is_running:
            markup.add(
                types.InlineKeyboardButton("⏹️ Stop", callback_data=f"stop_{file_data['id']}"),
                types.InlineKeyboardButton("🔄 Restart", callback_data=f"restart_{file_data['id']}")
            )
        else:
            markup.add(
                types.InlineKeyboardButton("▶️ Start", callback_data=f"start_{file_data['id']}")
            )
        
        markup.add(
            types.InlineKeyboardButton("📜 Logs", callback_data=f"logs_{file_data['id']}"),
            types.InlineKeyboardButton("📥 Download", callback_data=f"download_{file_data['id']}")
        )
        
        markup.add(
            types.InlineKeyboardButton("💾 Backup", callback_data=f"backup_{file_data['id']}"),
            types.InlineKeyboardButton("📊 Resources", callback_data=f"resources_{file_data['id']}")
        )
        
        markup.add(
            types.InlineKeyboardButton("🗑️ Delete", callback_data=f"delete_{file_data['id']}")
        )
        
        markup.add(types.InlineKeyboardButton("🔙 Back to Files", callback_data='files'))
        return markup
    
    def _create_admin_menu(self):
        """Create admin menu"""
        markup = types.InlineKeyboardMarkup(row_width=2)
        
        markup.add(
            types.InlineKeyboardButton("📊 Stats", callback_data='admin_stats'),
            types.InlineKeyboardButton("👥 Users", callback_data='admin_users')
        )
        
        markup.add(
            types.InlineKeyboardButton("🚫 Banned", callback_data='admin_banned'),
            types.InlineKeyboardButton("🔒 Lock/Unlock", callback_data='admin_lock')
        )
        
        markup.add(
            types.InlineKeyboardButton("📢 Broadcast", callback_data='admin_broadcast'),
            types.InlineKeyboardButton("🧹 Cleanup", callback_data='admin_cleanup')
        )
        
        markup.add(
            types.InlineKeyboardButton("🔄 Run All", callback_data='admin_run_all'),
            types.InlineKeyboardButton("💾 Backup All", callback_data='admin_backup_all')
        )
        
        markup.add(
            types.InlineKeyboardButton("📥 Restore All", callback_data='admin_restore_all'),
            types.InlineKeyboardButton("📋 Export Data", callback_data='admin_export_data')
        )
        
        markup.add(types.InlineKeyboardButton("🔙 Back", callback_data='main'))
        return markup
    
    # ============================================================
    # DATABASE FUNCTIONS
    # ============================================================
    
    def _register_user(self, user):
        """Register user in database"""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR IGNORE INTO users (user_id, username, first_name, last_name)
                VALUES (?, ?, ?, ?)
            ''', (user.id, user.username, user.first_name, user.last_name))
            
            cursor.execute('''
                UPDATE users SET last_active = CURRENT_TIMESTAMP
                WHERE user_id = ?
            ''', (user.id,))
            
            cursor.execute('''
                INSERT OR REPLACE INTO active_users (user_id, last_seen)
                VALUES (?, CURRENT_TIMESTAMP)
            ''', (user.id,))
            conn.commit()
    
    def _get_user_data(self, user_id):
        """Get user data"""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
            row = cursor.fetchone()
            return dict(row) if row else {}
    
    def _get_user_files(self, user_id):
        """Get user's files"""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM user_files WHERE user_id = ?
                ORDER BY upload_time DESC
            ''', (user_id,))
            return [dict(row) for row in cursor.fetchall()]
    
    def _get_file_by_id(self, file_id):
        """Get file by ID"""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM user_files WHERE id = ?', (file_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def _save_file_record(self, user_id, file_name, file_type, file_size):
        """Save file record"""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO user_files (user_id, file_name, file_type, file_size)
                VALUES (?, ?, ?, ?)
            ''', (user_id, file_name, file_type, file_size))
            conn.commit()
            return cursor.lastrowid
    
    def _update_file_status(self, user_id, file_name, is_running, pid=None):
        """Update file status"""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            if is_running:
                cursor.execute('''
                    UPDATE user_files 
                    SET is_running = 1, last_started = CURRENT_TIMESTAMP, pid = ?
                    WHERE user_id = ? AND file_name = ?
                ''', (pid, user_id, file_name))
            else:
                cursor.execute('''
                    UPDATE user_files 
                    SET is_running = 0, last_stopped = CURRENT_TIMESTAMP, pid = NULL
                    WHERE user_id = ? AND file_name = ?
                ''', (user_id, file_name))
            conn.commit()
    
    def _get_user_file_count(self, user_id):
        """Get user's file count"""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM user_files WHERE user_id = ?', (user_id,))
            return cursor.fetchone()[0] or 0
    
    def _get_all_users(self):
        """Get all users"""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM users ORDER BY created_at DESC')
            return [dict(row) for row in cursor.fetchall()]
    
    def _get_total_files(self):
        """Get total files count"""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM user_files')
            return cursor.fetchone()[0] or 0
    
    def _get_user_subscription(self, user_id):
        """Get user's subscription"""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM subscriptions WHERE user_id = ?', (user_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def _get_user_limit(self, user_id):
        """Get user's file limit"""
        if user_id == config.OWNER_ID:
            return config.OWNER_LIMIT
        if user_id in self.admin_ids:
            return config.ADMIN_LIMIT
        
        subscription = self._get_user_subscription(user_id)
        if subscription:
            expiry = subscription.get('expiry')
            if expiry:
                if isinstance(expiry, str):
                    try:
                        expiry = datetime.fromisoformat(expiry)
                    except:
                        expiry = None
                if expiry and expiry > datetime.now():
                    return config.SUBSCRIBED_USER_LIMIT
        
        return config.FREE_USER_LIMIT
    
    def _get_banned_users(self):
        """Get banned users"""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT user_id, ban_reason FROM users WHERE is_banned = 1')
            return [dict(row) for row in cursor.fetchall()]
    
    def _get_storage_used(self):
        """Get total storage used"""
        storage_used = 0
        user_folders = [f for f in os.listdir('upload_bots') 
                       if os.path.isdir(os.path.join('upload_bots', f))]
        for folder in user_folders:
            folder_path = os.path.join('upload_bots', folder)
            for root, dirs, files in os.walk(folder_path):
                for file in files:
                    try:
                        storage_used += os.path.getsize(os.path.join(root, file))
                    except Exception:
                        pass
        return storage_used
    
    # ============================================================
    # BAN FUNCTIONS
    # ============================================================
    
    def _is_user_banned(self, user_id):
        """Check if user is banned"""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT is_banned FROM users WHERE user_id = ?', (user_id,))
            row = cursor.fetchone()
            return row and row[0] == 1
    
    def _ban_user(self, user_id, reason):
        """Ban a user"""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE users SET is_banned = 1, ban_reason = ?
                WHERE user_id = ?
            ''', (reason, user_id))
            conn.commit()
        
        self.banned_users.add(user_id)
    
    def _unban_user(self, user_id):
        """Unban a user"""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE users SET is_banned = 0, ban_reason = NULL
                WHERE user_id = ?
            ''', (user_id,))
            conn.commit()
        
        self.banned_users.discard(user_id)
    
    # ============================================================
    # UTILITY FUNCTIONS
    # ============================================================
    
    def _get_user_folder(self, user_id):
        """Get user folder"""
        folder = os.path.join('upload_bots', str(user_id))
        os.makedirs(folder, exist_ok=True)
        return folder
    
    def _check_force_join(self, user_id):
        """Check force join"""
        try:
            for channel in config.FORCE_JOIN_CHANNELS:
                member = self.bot.get_chat_member(channel, user_id)
                if member.status not in ['member', 'administrator', 'creator']:
                    return False
            return True
        except:
            return False
    
    def _send_force_join_message(self, chat_id):
        """Send force join message"""
        markup = types.InlineKeyboardMarkup(row_width=1)
        for channel, name in config.FORCE_JOIN_CHANNELS.items():
            markup.add(
                types.InlineKeyboardButton(
                    name,
                    url=f"https://t.me/{channel.replace('@', '')}"
                )
            )
        markup.add(types.InlineKeyboardButton("✅ I've Joined", callback_data="check_join"))
        
        self.bot.send_message(
            chat_id,
            "📢 **Join Our Channels**\n\nPlease join all channels to use this bot:",
            reply_markup=markup,
            parse_mode='Markdown'
        )
    
    def _format_size(self, size):
        """Format size in bytes to human readable"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"
    
    def _format_uptime(self, start_time):
        """Format uptime"""
        if not start_time:
            return "Unknown"
        if isinstance(start_time, str):
            try:
                start_time = datetime.fromisoformat(start_time)
            except:
                return "Unknown"
        if isinstance(start_time, datetime):
            delta = datetime.now() - start_time
            hours = delta.seconds // 3600
            minutes = (delta.seconds % 3600) // 60
            seconds = delta.seconds % 60
            
            if delta.days > 0:
                return f"{delta.days}d {hours}h {minutes}m"
            elif hours > 0:
                return f"{hours}h {minutes}m {seconds}s"
            elif minutes > 0:
                return f"{minutes}m {seconds}s"
            else:
                return f"{seconds}s"
        return "Unknown"
    
    # ============================================================
    # CLEANUP
    # ============================================================
    
    def _setup_cleanup(self):
        """Setup automatic cleanup"""
        def cleanup_loop():
            while True:
                try:
                    time.sleep(config.AUTO_CLEANUP_INTERVAL)
                    self._cleanup_system()
                    logging.info("Auto-cleanup completed")
                except Exception as e:
                    logging.error(f"Cleanup loop error: {e}")
        
        thread = threading.Thread(target=cleanup_loop, daemon=True)
        thread.start()
        logging.info("Auto-cleanup scheduled")

# ============================================================
# MAIN EXECUTION
# ============================================================

if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('bot.log', encoding='utf-8')
        ]
    )
    
    print("=" * 50)
    print("🤖 Advanced Bot Starting...")
    print(f"👑 Owner ID: {config.OWNER_ID}")
    print(f"🛡️ Admin ID: {config.ADMIN_ID}")
    print("=" * 50)
    
    bot = AdvancedBot()
    
    while True:
        try:
            bot.bot.infinity_polling(timeout=60, long_polling_timeout=30)
        except Exception as e:
            logging.error(f"Polling error: {e}")
            time.sleep(5)
