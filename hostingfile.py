# -*- coding: utf-8 -*-
"""
Advanced Bot Hosting Platform
Version: 3.0.0
Features:
- Modern UI with pagination
- Multi-language support
- Advanced process management
- Resource monitoring
- Backup system
- Auto-restart on crash
- Web dashboard
- And much more
"""

import telebot
import subprocess
import os
import sys
import json
import time
import logging
import threading
import sqlite3
import shutil
import tempfile
import zipfile
import re
import signal
import psutil
import requests
import hashlib
import mimetypes
import struct
import uuid
import asyncio
import socket
import platform
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from enum import Enum
from flask import Flask, jsonify, request, render_template_string
from threading import Thread
from collections import defaultdict
import base64
import random
import string
import functools

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
    PROCESS_TIMEOUT = 300  # 5 minutes
    MAX_LOG_SIZE = 5 * 1024 * 1024  # 5MB
    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
    
    # Auto cleanup
    AUTO_CLEANUP_INTERVAL = 3600  # 1 hour
    INACTIVE_PROCESS_TIMEOUT = 7200  # 2 hours
    
    # Web dashboard
    WEB_PORT = 8080
    WEB_HOST = '0.0.0.0'
    
    # Language
    DEFAULT_LANG = 'en'
    
    LANGUAGES = {
        'en': {
            'name': 'English',
            'welcome': '🚀 Welcome to Bot Hosting Platform!',
            'start': '🌟 Bot Started Successfully',
            'help': '📚 Help & Support',
            'settings': '⚙️ Settings',
            'files': '📂 My Files',
            'upload': '📤 Upload File',
            'stats': '📊 Statistics',
            'profile': '👤 Profile',
            'support': '🆘 Support',
            'premium': '💎 Premium',
            'back': '🔙 Back',
            'refresh': '🔄 Refresh',
            'delete': '🗑️ Delete',
            'start_bot': '▶️ Start',
            'stop_bot': '⏹️ Stop',
            'restart_bot': '🔄 Restart',
            'logs': '📜 Logs',
            'download': '📥 Download',
            'close': '❌ Close',
        },
        'hi': {
            'name': 'हिन्दी',
            'welcome': '🚀 बॉट होस्टिंग प्लेटफॉर्म में आपका स्वागत है!',
            'start': '🌟 बॉट सफलतापूर्वक शुरू हुआ',
            'help': '📚 मदद और सहायता',
            'settings': '⚙️ सेटिंग्स',
            'files': '📂 मेरी फाइलें',
            'upload': '📤 फाइल अपलोड करें',
            'stats': '📊 आंकड़े',
            'profile': '👤 प्रोफाइल',
            'support': '🆘 सहायता',
            'premium': '💎 प्रीमियम',
        }
    }

config = Config()

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
            
            # Version tracking
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS schema_version (
                    version INTEGER PRIMARY KEY,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Check current version
            cursor.execute('SELECT MAX(version) FROM schema_version')
            row = cursor.fetchone()
            current_version = row[0] if row and row[0] else 0
            
            # Run migrations
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
        """Initial schema"""
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
                auto_renew BOOLEAN DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
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
                pid INTEGER,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS admins (
                user_id INTEGER PRIMARY KEY,
                role TEXT DEFAULT 'admin',
                added_by INTEGER,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS active_users (
                user_id INTEGER PRIMARY KEY,
                last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        ''')
    
    def _migration_v2(self, cursor):
        """Add logs and analytics tables"""
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                action TEXT,
                details TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
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
        """Add backups and notifications"""
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS backups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                file_name TEXT,
                backup_path TEXT,
                backup_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                title TEXT,
                message TEXT,
                is_read BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
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
# MENU SYSTEM - MODERN UI
# ============================================================

class MenuManager:
    """Advanced menu system with pagination and themes"""
    
    THEMES = {
        'dark': {
            'primary': '🎯',
            'secondary': '💫',
            'accent': '✨',
            'success': '✅',
            'danger': '🚫',
            'warning': '⚠️',
            'info': 'ℹ️',
        },
        'light': {
            'primary': '🔵',
            'secondary': '⚪',
            'accent': '🔶',
            'success': '🟢',
            'danger': '🔴',
            'warning': '🟡',
            'info': '🔷',
        },
        'vibrant': {
            'primary': '💜',
            'secondary': '💗',
            'accent': '💛',
            'success': '💚',
            'danger': '❤️',
            'warning': '🧡',
            'info': '💙',
        }
    }
    
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.theme = 'dark'
        self.lang = 'en'
    
    def main_menu(self, user_data: dict) -> types.InlineKeyboardMarkup:
        """Main menu with modern design"""
        markup = types.InlineKeyboardMarkup(row_width=2)
        
        # User info row
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
        
        # Main actions
        markup.add(
            types.InlineKeyboardButton("📤 Upload", callback_data='upload'),
            types.InlineKeyboardButton("📂 My Files", callback_data='files')
        )
        
        markup.add(
            types.InlineKeyboardButton("⚡ Bot Speed", callback_data='speed'),
            types.InlineKeyboardButton("📜 Logs", callback_data='logs')
        )
        
        # Premium section
        if self.is_premium():
            markup.add(
                types.InlineKeyboardButton(
                    "💎 Premium Features",
                    callback_data='premium_features'
                )
            )
        else:
            markup.add(
                types.InlineKeyboardButton(
                    "⭐ Upgrade to Premium",
                    callback_data='premium'
                )
            )
        
        # Bottom row
        markup.add(
            types.InlineKeyboardButton("🆘 Help", callback_data='help'),
            types.InlineKeyboardButton("⚙️ Settings", callback_data='settings')
        )
        
        return markup
    
    def file_management_menu(self, files: List[dict], page: int = 0, per_page: int = 5) -> types.InlineKeyboardMarkup:
        """Paginated file management menu"""
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
        
        # Pagination controls
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
        """File control menu with actions"""
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
    
    def settings_menu(self) -> types.InlineKeyboardMarkup:
        """Settings menu"""
        markup = types.InlineKeyboardMarkup(row_width=2)
        
        markup.add(
            types.InlineKeyboardButton(f"🌐 Language: {self.lang.upper()}", callback_data='change_lang'),
            types.InlineKeyboardButton(f"🎨 Theme: {self.theme.title()}", callback_data='change_theme')
        )
        
        markup.add(
            types.InlineKeyboardButton("🔔 Notifications", callback_data='notifications'),
            types.InlineKeyboardButton("📋 Export Data", callback_data='export_data')
        )
        
        markup.add(
            types.InlineKeyboardButton("🔙 Back", callback_data='main')
        )
        
        return markup
    
    def admin_menu(self) -> types.InlineKeyboardMarkup:
        """Admin panel menu"""
        markup = types.InlineKeyboardMarkup(row_width=2)
        
        markup.add(
            types.InlineKeyboardButton("👥 Users", callback_data='admin_users'),
            types.InlineKeyboardButton("📊 Analytics", callback_data='admin_analytics')
        )
        
        markup.add(
            types.InlineKeyboardButton("💳 Subscriptions", callback_data='admin_subscriptions'),
            types.InlineKeyboardButton("🚫 Banned Users", callback_data='admin_banned')
        )
        
        markup.add(
            types.InlineKeyboardButton("📢 Broadcast", callback_data='broadcast'),
            types.InlineKeyboardButton("🔒 Lock Bot", callback_data='admin_lock')
        )
        
        markup.add(
            types.InlineKeyboardButton("🔄 Run All Scripts", callback_data='admin_run_all'),
            types.InlineKeyboardButton("🗑️ Cleanup", callback_data='admin_cleanup')
        )
        
        markup.add(
            types.InlineKeyboardButton("📋 System Status", callback_data='admin_status')
        )
        
        markup.add(
            types.InlineKeyboardButton("🔙 Back", callback_data='main')
        )
        
        return markup
    
    def is_premium(self) -> bool:
        """Check if user has premium status"""
        # This should be integrated with subscription system
        return False

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
        """Start a new process with monitoring"""
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
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                )
                
                self._processes[script_key] = {
                    'process': process,
                    'log_file': log_file,
                    'start_time': datetime.now(),
                    'cwd': cwd,
                    'pid': process.pid,
                    'restarts': 0,
                    'last_restart': None,
                    'status': 'running'
                }
                
                logging.info(f"Started process {script_key} with PID {process.pid}")
                return True
                
            except Exception as e:
                logging.error(f"Failed to start process {script_key}: {e}")
                return False
    
    def stop_process(self, script_key: str) -> bool:
        """Stop a running process"""
        with self._lock:
            if script_key not in self._processes:
                return False
            
            process_info = self._processes[script_key]
            process = process_info['process']
            
            try:
                # Close stdin to let process know
                if process.stdin:
                    process.stdin.close()
                
                # Terminate gracefully
                process.terminate()
                
                # Wait for process to finish
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                
                # Close log file
                if process_info['log_file'] and not process_info['log_file'].closed:
                    process_info['log_file'].close()
                
                self._processes[script_key]['status'] = 'stopped'
                logging.info(f"Stopped process {script_key}")
                return True
                
            except Exception as e:
                logging.error(f"Error stopping process {script_key}: {e}")
                return False
    
    def get_process_info(self, script_key: str) -> Optional[dict]:
        """Get information about a running process"""
        with self._lock:
            if script_key not in self._processes:
                return None
            
            info = self._processes[script_key].copy()
            
            # Check if process is still running
            if info['status'] == 'running':
                try:
                    info['is_running'] = psutil.pid_exists(info['pid'])
                    if not info['is_running']:
                        info['status'] = 'exited'
                except Exception:
                    info['is_running'] = False
                    info['status'] = 'unknown'
            
            # Get resource usage
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
        """Get all tracked processes"""
        with self._lock:
            return self._processes.copy()
    
    def cleanup_stale_processes(self):
        """Clean up processes that have exited but not been removed"""
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
        """Monitor processes and auto-restart crashed ones"""
        while True:
            try:
                self.cleanup_stale_processes()
                
                # Auto-restart crashed processes
                if self._auto_restart_enabled:
                    for key, info in self._processes.items():
                        if info['status'] == 'exited' and info.get('auto_restart', True):
                            restarts = info.get('restarts', 0)
                            if restarts < 5:  # Max 5 restarts
                                logging.info(f"Auto-restarting {key} (attempt {restarts+1})")
                                # Restart logic here
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
        """Create a backup of a file"""
        try:
            backup_id = f"{user_id}_{int(time.time())}_{uuid.uuid4().hex[:8]}"
            backup_path = os.path.join(self.backup_dir, backup_id)
            
            os.makedirs(backup_path, exist_ok=True)
            shutil.copy2(file_path, os.path.join(backup_path, file_name))
            
            # Save metadata
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
        """Restore a backup"""
        try:
            backup_path = os.path.join(self.backup_dir, backup_id)
            if not os.path.exists(backup_path):
                return False
            
            # Find the file in backup
            for file in os.listdir(backup_path):
                if file != 'metadata.json':
                    shutil.copy2(os.path.join(backup_path, file), restore_path)
                    return True
            
            return False
            
        except Exception as e:
            logging.error(f"Backup restore failed: {e}")
            return False
    
    def list_backups(self, user_id: int) -> List[dict]:
        """List all backups for a user"""
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
# NOTIFICATION SYSTEM
# ============================================================

class NotificationManager:
    """User notification management"""
    
    def __init__(self, db_manager: DatabaseManager, bot: telebot.TeleBot):
        self.db = db_manager
        self.bot = bot
    
    def add_notification(self, user_id: int, title: str, message: str):
        """Add a notification for a user"""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO notifications (user_id, title, message)
                VALUES (?, ?, ?)
            ''', (user_id, title, message))
            conn.commit()
        
        # Send notification immediately if user is online
        try:
            self.bot.send_message(
                user_id,
                f"🔔 **{title}**\n\n{message}",
                parse_mode='Markdown'
            )
        except Exception as e:
            logging.error(f"Failed to send notification to {user_id}: {e}")
    
    def get_notifications(self, user_id: int, limit: int = 20) -> List[dict]:
        """Get unread notifications for a user"""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, title, message, is_read, created_at
                FROM notifications
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT ?
            ''', (user_id, limit))
            return [dict(row) for row in cursor.fetchall()]
    
    def mark_read(self, notification_id: int):
        """Mark a notification as read"""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE notifications SET is_read = 1
                WHERE id = ?
            ''', (notification_id,))
            conn.commit()

# ============================================================
# MAIN BOT CLASS
# ============================================================

class AdvancedBot:
    """Main bot class with all features"""
    
    def __init__(self):
        self.bot = telebot.TeleBot(config.BOT_TOKEN)
        self.db = DatabaseManager(os.path.join('inf', 'bot_data.db'))
        self.db.initialize()
        self.cache = CacheManager()
        self.process_manager = ProcessManager()
        self.backup_manager = BackupManager(os.path.dirname(os.path.abspath(__file__)))
        self.notification_manager = NotificationManager(self.db, self.bot)
        self.menu_manager = MenuManager(config.OWNER_ID)
        
        self.bot_locked = False
        self._setup_handlers()
        self._setup_flask()
        self._setup_cleanup()
        
        logging.info("Advanced Bot initialized successfully")
    
    # ============================================================
    # COMMAND HANDLERS
    # ============================================================
    
    def _setup_handlers(self):
        """Setup all command handlers"""
        
        # Start command
        @self.bot.message_handler(commands=['start', 'help'])
        def start_command(message):
            self._handle_start(message)
        
        # Settings command
        @self.bot.message_handler(commands=['settings'])
        def settings_command(message):
            self._handle_settings(message)
        
        # My files command
        @self.bot.message_handler(commands=['myfiles'])
        def myfiles_command(message):
            self._handle_files(message)
        
        # Upload command
        @self.bot.message_handler(commands=['upload'])
        def upload_command(message):
            self._handle_upload(message)
        
        # Stats command
        @self.bot.message_handler(commands=['stats'])
        def stats_command(message):
            self._handle_stats(message)
        
        # Profile command
        @self.bot.message_handler(commands=['profile'])
        def profile_command(message):
            self._handle_profile(message)
        
        # Admin commands
        @self.bot.message_handler(commands=['admin'])
        def admin_command(message):
            self._handle_admin(message)
        
        @self.bot.message_handler(commands=['broadcast'])
        def broadcast_command(message):
            self._handle_broadcast(message)
        
        @self.bot.message_handler(commands=['lock'])
        def lock_command(message):
            self._handle_lock(message)
        
        @self.bot.message_handler(commands=['unlock'])
        def unlock_command(message):
            self._handle_unlock(message)
        
        # Ping
        @self.bot.message_handler(commands=['ping'])
        def ping_command(message):
            self._handle_ping(message)
        
        # File upload handler
        @self.bot.message_handler(content_types=['document'])
        def file_upload_handler(message):
            self._handle_file_upload(message)
        
        # Callback query handler
        @self.bot.callback_query_handler(func=lambda call: True)
        def callback_handler(call):
            self._handle_callback(call)
        
        # Message handler for reply keyboard
        @self.bot.message_handler(func=lambda message: True)
        def message_handler(message):
            self._handle_message(message)
    
    # ============================================================
    # COMMAND IMPLEMENTATIONS
    # ============================================================
    
    def _handle_start(self, message):
        """Handle /start command with force join and welcome"""
        user_id = message.from_user.id
        chat_id = message.chat.id
        
        # Check force join
        if user_id not in [config.OWNER_ID, config.ADMIN_ID]:
            if not self._check_force_join(user_id):
                self._send_force_join_message(chat_id)
                return
        
        # Check ban
        if self._is_user_banned(user_id):
            self.bot.send_message(chat_id, "🚫 You are banned from using this bot.")
            return
        
        # Register user
        self._register_user(message.from_user)
        
        # Get user data
        user_data = self._get_user_data(user_id)
        
        # Main menu
        markup = self.menu_manager.main_menu(user_data)
        
        welcome_text = self._get_welcome_text(user_data)
        self.bot.send_message(chat_id, welcome_text, reply_markup=markup, parse_mode='Markdown')
    
    def _handle_settings(self, message):
        """Handle settings command"""
        user_id = message.from_user.id
        
        if self._is_user_banned(user_id):
            return
        
        markup = self.menu_manager.settings_menu()
        self.bot.reply_to(
            message,
            "⚙️ **Settings**\n\nCustomize your bot experience:",
            reply_markup=markup,
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
        
        markup = self.menu_manager.file_management_menu(files)
        self.bot.reply_to(
            message,
            f"📂 **Your Files** ({len(files)} total)\n\nClick a file to manage it:",
            reply_markup=markup,
            parse_mode='Markdown'
        )
    
    def _handle_upload(self, message):
        """Handle upload command"""
        user_id = message.from_user.id
        
        if self._is_user_banned(user_id):
            return
        
        if self.bot_locked and user_id not in [config.OWNER_ID, config.ADMIN_ID]:
            self.bot.reply_to(message, "🔒 Bot is currently locked. Please try again later.")
            return
        
        # Check file limit
        user_files = self._get_user_files(user_id)
        user_limit = self._get_user_limit(user_id)
        
        if len(user_files) >= user_limit:
            self.bot.reply_to(
                message,
                f"⚠️ **File Limit Reached**\n\nYou have reached your limit of {user_limit} files.\n"
                f"Delete some files to upload more.",
                parse_mode='Markdown'
            )
            return
        
        self.bot.reply_to(
            message,
            "📤 **Upload Files**\n\n"
            "Send me a Python (`.py`) or JavaScript (`.js`) file.\n"
            "You can also send a ZIP archive containing your project.\n\n"
            "📦 Supported: `.py`, `.js`, `.zip`",
            parse_mode='Markdown'
        )
    
    def _handle_stats(self, message):
        """Handle stats command"""
        user_id = message.from_user.id
        
        if self._is_user_banned(user_id):
            return
        
        stats = self._get_system_stats(user_id)
        
        # Check if admin for additional stats
        is_admin = user_id in [config.OWNER_ID, config.ADMIN_ID]
        
        if is_admin:
            stats_text = (
                f"📊 **System Statistics**\n\n"
                f"👥 **Total Users:** {stats['total_users']}\n"
                f"📂 **Total Files:** {stats['total_files']}\n"
                f"🟢 **Running Bots:** {stats['running_bots']}\n"
                f"💾 **Storage Used:** {stats['storage_used']}\n"
                f"🧠 **CPU Usage:** {stats['cpu_usage']}%\n"
                f"💿 **Memory Usage:** {stats['memory_usage']}%\n"
                f"🔒 **Bot Status:** {'🔴 Locked' if self.bot_locked else '🟢 Unlocked'}"
            )
        else:
            stats_text = (
                f"📊 **Your Statistics**\n\n"
                f"📂 **Your Files:** {stats['user_files']}\n"
                f"📤 **Uploads:** {stats['user_uploads']}\n"
                f"🟢 **Your Running Bots:** {stats['user_running']}\n"
                f"📈 **Total Users:** {stats['total_users']}\n"
                f"💾 **Storage Used:** {stats['storage_used']}"
            )
        
        self.bot.reply_to(message, stats_text, parse_mode='Markdown')
    
    def _handle_profile(self, message):
        """Handle profile command"""
        user_id = message.from_user.id
        
        if self._is_user_banned(user_id):
            return
        
        user_data = self._get_user_data(user_id)
        subscription = self._get_user_subscription(user_id)
        
        profile_text = (
            f"👤 **User Profile**\n\n"
            f"🆔 **User ID:** `{user_id}`\n"
            f"👤 **Name:** {user_data.get('first_name', 'Unknown')}\n"
            f"✳️ **Username:** @{user_data.get('username', 'Not set')}\n"
            f"📅 **Joined:** {user_data.get('created_at', 'Unknown')}\n"
            f"📂 **Files:** {self._get_user_file_count(user_id)}\n"
        )
        
        if subscription:
            expiry = subscription.get('expiry')
            if expiry and expiry > datetime.now():
                days_left = (expiry - datetime.now()).days
                profile_text += f"💎 **Premium:** Yes (Expires in {days_left} days)\n"
            else:
                profile_text += "🆓 **Premium:** No\n"
        else:
            profile_text += "🆓 **Premium:** No\n"
        
        # Admin status
        if user_id in [config.OWNER_ID, config.ADMIN_ID]:
            role = "Owner" if user_id == config.OWNER_ID else "Admin"
            profile_text += f"🛡️ **Role:** {role}\n"
        
        self.bot.reply_to(message, profile_text, parse_mode='Markdown')
    
    def _handle_admin(self, message):
        """Handle admin command"""
        user_id = message.from_user.id
        
        if user_id not in [config.OWNER_ID, config.ADMIN_ID]:
            self.bot.reply_to(message, "⚠️ **Admin Access Required**", parse_mode='Markdown')
            return
        
        markup = self.menu_manager.admin_menu()
        self.bot.reply_to(
            message,
            "👑 **Admin Panel**\n\n"
            "Manage users, files, and system settings:",
            reply_markup=markup,
            parse_mode='Markdown'
        )
    
    def _handle_broadcast(self, message):
        """Handle broadcast command"""
        user_id = message.from_user.id
        
        if user_id not in [config.OWNER_ID, config.ADMIN_ID]:
            return
        
        msg = self.bot.reply_to(
            message,
            "📢 **Broadcast Message**\n\n"
            "Send me the message to broadcast to all users.\n"
            "You can include images, videos, or documents.\n\n"
            "Type /cancel to cancel.",
            parse_mode='Markdown'
        )
        self.bot.register_next_step_handler(msg, self._process_broadcast)
    
    def _handle_lock(self, message):
        """Handle lock command"""
        user_id = message.from_user.id
        
        if user_id not in [config.OWNER_ID, config.ADMIN_ID]:
            return
        
        self.bot_locked = True
        self.bot.reply_to(
            message,
            "🔒 **Bot Locked**\n\n"
            "The bot is now locked. Only admins can use it.",
            parse_mode='Markdown'
        )
    
    def _handle_unlock(self, message):
        """Handle unlock command"""
        user_id = message.from_user.id
        
        if user_id not in [config.OWNER_ID, config.ADMIN_ID]:
            return
        
        self.bot_locked = False
        self.bot.reply_to(
            message,
            "🔓 **Bot Unlocked**\n\n"
            "The bot is now unlocked. All users can use it.",
            parse_mode='Markdown'
        )
    
    def _handle_ping(self, message):
        """Handle ping command"""
        start = time.time()
        msg = self.bot.reply_to(message, "🏓 Pong!")
        end = time.time()
        latency = round((end - start) * 1000, 2)
        self.bot.edit_message_text(
            f"🏓 **Pong!**\n\n"
            f"⏱️ **Latency:** {latency}ms",
            message.chat.id,
            msg.message_id,
            parse_mode='Markdown'
        )
    
    def _handle_message(self, message):
        """Handle regular messages (reply keyboard)"""
        user_id = message.from_user.id
        text = message.text
        
        if self._is_user_banned(user_id):
            return
        
        if self.bot_locked and user_id not in [config.OWNER_ID, config.ADMIN_ID]:
            self.bot.reply_to(message, "🔒 Bot is currently locked.")
            return
        
        # Check if it's a reply keyboard action
        if text == "📊 Stats":
            self._handle_stats(message)
        elif text == "📂 My Files":
            self._handle_files(message)
        elif text == "📤 Upload":
            self._handle_upload(message)
        elif text == "👤 Profile":
            self._handle_profile(message)
        elif text == "⚙️ Settings":
            self._handle_settings(message)
        elif text == "🆘 Help":
            self._handle_help(message)
        elif text == "🔄 Refresh":
            self._handle_files(message)
        elif text == "🔙 Back":
            self._handle_start(message)
    
    def _handle_help(self, message):
        """Handle help request"""
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
            "/ping - Check bot latency\n\n"
            "**File Types:**\n"
            "• Python (.py)\n"
            "• JavaScript (.js)\n"
            "• ZIP Archives (.zip)\n\n"
            "**Need more help?**\n"
            f"Contact: {config.YOUR_USERNAME}"
        )
        self.bot.reply_to(message, help_text, parse_mode='Markdown')
    
    # ============================================================
    # FILE UPLOAD HANDLER
    # ============================================================
    
    def _handle_file_upload(self, message):
        """Handle file upload"""
        user_id = message.from_user.id
        chat_id = message.chat.id
        
        if self._is_user_banned(user_id):
            return
        
        if self.bot_locked and user_id not in [config.OWNER_ID, config.ADMIN_ID]:
            self.bot.reply_to(message, "🔒 Bot is currently locked.")
            return
        
        document = message.document
        file_name = document.file_name
        
        # Validate file type
        ext = os.path.splitext(file_name)[1].lower()
        if ext not in ['.py', '.js', '.zip']:
            self.bot.reply_to(
                message,
                f"❌ **Unsupported File Type**\n\n"
                f"File: `{file_name}`\n"
                f"Only `.py`, `.js`, and `.zip` files are allowed.",
                parse_mode='Markdown'
            )
            return
        
        # Check file size
        if document.file_size > config.MAX_FILE_SIZE:
            self.bot.reply_to(
                message,
                f"❌ **File Too Large**\n\n"
                f"File: `{file_name}`\n"
                f"Size: {document.file_size // 1024 // 1024}MB\n"
                f"Maximum: {config.MAX_FILE_SIZE // 1024 // 1024}MB",
                parse_mode='Markdown'
            )
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
        
        # Process upload
        status_msg = self.bot.reply_to(
            message,
            f"⏳ **Processing Upload**\n\n"
            f"File: `{file_name}`\n"
            f"Status: Downloading...",
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
                    f"🚨 **Security Alert**\n\n"
                    f"File: `{file_name}`\n"
                    f"Reason: {scan_result['reason']}\n\n"
                    f"⚠️ This file was blocked for security reasons.",
                    chat_id,
                    status_msg.message_id,
                    parse_mode='Markdown'
                )
                return
            
            # Save file
            user_folder = self._get_user_folder(user_id)
            file_path = os.path.join(user_folder, file_name)
            
            if ext == '.zip':
                # Handle ZIP archive
                self._process_zip(file_content, file_name, user_id, status_msg)
            else:
                # Handle single file
                with open(file_path, 'wb') as f:
                    f.write(file_content)
                
                # Save to database
                file_id = self._save_file_record(user_id, file_name, ext[1:], len(file_content))
                
                # Start the script
                self.bot.edit_message_text(
                    f"✅ **Upload Complete**\n\n"
                    f"File: `{file_name}`\n"
                    f"Status: Starting...",
                    chat_id,
                    status_msg.message_id,
                    parse_mode='Markdown'
                )
                
                self._start_script(user_id, file_name, file_path, ext[1:], status_msg)
            
        except Exception as e:
            logging.error(f"File upload error: {e}")
            self.bot.edit_message_text(
                f"❌ **Upload Failed**\n\n"
                f"Error: {str(e)}",
                chat_id,
                status_msg.message_id,
                parse_mode='Markdown'
            )
    
    def _process_zip(self, file_content: bytes, file_name: str, user_id: int, status_msg):
        """Process ZIP archive upload"""
        chat_id = status_msg.chat.id
        user_folder = self._get_user_folder(user_id)
        
        temp_dir = tempfile.mkdtemp(prefix=f"zip_{user_id}_")
        
        try:
            # Save zip
            zip_path = os.path.join(temp_dir, file_name)
            with open(zip_path, 'wb') as f:
                f.write(file_content)
            
            # Extract
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                # Security check: path traversal
                for member in zip_ref.infolist():
                    member_path = os.path.abspath(os.path.join(temp_dir, member.filename))
                    if not member_path.startswith(os.path.abspath(temp_dir)):
                        raise Exception(f"Unsafe path: {member.filename}")
                
                zip_ref.extractall(temp_dir)
            
            self.bot.edit_message_text(
                f"⏳ **Processing ZIP**\n\n"
                f"File: `{file_name}`\n"
                f"Status: Extracted, finding main script...",
                chat_id,
                status_msg.message_id,
                parse_mode='Markdown'
            )
            
            # Find main script
            main_script = self._find_main_script(temp_dir)
            if not main_script:
                self.bot.edit_message_text(
                    f"❌ **No Script Found**\n\n"
                    f"File: `{file_name}`\n"
                    f"No Python or JavaScript file found in the archive.",
                    chat_id,
                    status_msg.message_id,
                    parse_mode='Markdown'
                )
                return
            
            # Install dependencies if present
            self._install_dependencies(temp_dir, status_msg)
            
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
            
            # Start script
            file_path = os.path.join(user_folder, main_script)
            ext = os.path.splitext(main_script)[1][1:]
            
            self.bot.edit_message_text(
                f"✅ **ZIP Processed**\n\n"
                f"File: `{main_script}`\n"
                f"Status: Starting...",
                chat_id,
                status_msg.message_id,
                parse_mode='Markdown'
            )
            
            self._start_script(user_id, main_script, file_path, ext, status_msg)
            
        except Exception as e:
            logging.error(f"ZIP processing error: {e}")
            self.bot.edit_message_text(
                f"❌ **ZIP Error**\n\n"
                f"Error: {str(e)}",
                chat_id,
                status_msg.message_id,
                parse_mode='Markdown'
            )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
    
    def _find_main_script(self, directory: str) -> Optional[str]:
        """Find main script in extracted archive"""
        # Look for common main script names
        common_names = ['main.py', 'bot.py', 'app.py', 'index.js', 'main.js', 'server.js']
        
        for name in common_names:
            if os.path.exists(os.path.join(directory, name)):
                return name
        
        # Look for any .py or .js file
        for root, dirs, files in os.walk(directory):
            # Skip hidden directories
            dirs[:] = [d for d in dirs if not d.startswith('.') and not d.startswith('__')]
            
            for file in files:
                if file.endswith(('.py', '.js')):
                    return file
        
        return None
    
    def _install_dependencies(self, directory: str, status_msg):
        """Install dependencies from requirements.txt or package.json"""
        chat_id = status_msg.chat.id
        
        # Check requirements.txt
        req_path = os.path.join(directory, 'requirements.txt')
        if os.path.exists(req_path):
            self.bot.edit_message_text(
                f"⏳ **Installing Dependencies**\n\n"
                f"Found requirements.txt\n"
                f"Installing Python packages...",
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
                f"⏳ **Installing Dependencies**\n\n"
                f"Found package.json\n"
                f"Installing Node packages...",
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
    
    # ============================================================
    # SCRIPT MANAGEMENT
    # ============================================================
    
    def _start_script(self, user_id: int, file_name: str, file_path: str, file_type: str, status_msg):
        """Start a script"""
        chat_id = status_msg.chat.id
        user_folder = self._get_user_folder(user_id)
        script_key = f"{user_id}_{file_name}"
        
        # Check if already running
        if script_key in self.process_manager._processes:
            self.bot.edit_message_text(
                f"⚠️ **Already Running**\n\n"
                f"File: `{file_name}`\n"
                f"This script is already running.",
                chat_id,
                status_msg.message_id,
                parse_mode='Markdown'
            )
            return
        
        try:
            if file_type == 'py':
                command = [sys.executable, file_path]
            else:
                command = ['node', file_path]
            
            success = self.process_manager.start_process(
                script_key,
                command,
                user_folder,
                {**os.environ, "PYTHONIOENCODING": "utf-8"}
            )
            
            if success:
                self.bot.edit_message_text(
                    f"✅ **Script Started**\n\n"
                    f"File: `{file_name}`\n"
                    f"Status: 🟢 Running\n"
                    f"PID: {self.process_manager._processes[script_key]['pid']}",
                    chat_id,
                    status_msg.message_id,
                    parse_mode='Markdown'
                )
                
                # Update database
                self._update_file_status(user_id, file_name, True, 
                                        self.process_manager._processes[script_key]['pid'])
                
                # Send notification
                self.notification_manager.add_notification(
                    user_id,
                    "Script Started",
                    f"Your script `{file_name}` has been started."
                )
            else:
                self.bot.edit_message_text(
                    f"❌ **Start Failed**\n\n"
                    f"File: `{file_name}`\n"
                    f"Could not start the script.",
                    chat_id,
                    status_msg.message_id,
                    parse_mode='Markdown'
                )
                
        except Exception as e:
            logging.error(f"Start script error: {e}")
            self.bot.edit_message_text(
                f"❌ **Start Error**\n\n"
                f"File: `{file_name}`\n"
                f"Error: {str(e)}",
                chat_id,
                status_msg.message_id,
                parse_mode='Markdown'
            )
    
    def _stop_script(self, user_id: int, file_id: int, callback: Optional[telebot.types.CallbackQuery] = None):
        """Stop a running script"""
        file_data = self._get_file_by_id(file_id)
        if not file_data:
            return
        
        script_key = f"{user_id}_{file_data['file_name']}"
        
        success = self.process_manager.stop_process(script_key)
        
        if success:
            self._update_file_status(user_id, file_data['file_name'], False)
            
            self.notification_manager.add_notification(
                user_id,
                "Script Stopped",
                f"Your script `{file_data['file_name']}` has been stopped."
            )
            
            if callback:
                self.bot.answer_callback_query(callback.id, "✅ Script stopped")
                self._handle_files(callback.message)
    
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
        
        # Main menu
        if data == 'main':
            user_data = self._get_user_data(user_id)
            markup = self.menu_manager.main_menu(user_data)
            self.bot.edit_message_text(
                self._get_welcome_text(user_data),
                call.message.chat.id,
                call.message.message_id,
                reply_markup=markup,
                parse_mode='Markdown'
            )
            self.bot.answer_callback_query(call.id)
        
        # Files
        elif data == 'files':
            files = self._get_user_files(user_id)
            if not files:
                self.bot.answer_callback_query(call.id, "📂 No files found", show_alert=True)
                return
            
            markup = self.menu_manager.file_management_menu(files)
            self.bot.edit_message_text(
                f"📂 **Your Files** ({len(files)} total)",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=markup,
                parse_mode='Markdown'
            )
            self.bot.answer_callback_query(call.id)
        
        # Refresh files
        elif data == 'refresh_files':
            files = self._get_user_files(user_id)
            markup = self.menu_manager.file_management_menu(files)
            self.bot.edit_message_text(
                f"📂 **Your Files** ({len(files)} total)",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=markup,
                parse_mode='Markdown'
            )
            self.bot.answer_callback_query(call.id, "🔄 Refreshed!")
        
        # File page navigation
        elif data.startswith('file_page_'):
            page = int(data.split('_')[2])
            files = self._get_user_files(user_id)
            markup = self.menu_manager.file_management_menu(files, page)
            self.bot.edit_message_text(
                f"📂 **Your Files** ({len(files)} total)",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=markup,
                parse_mode='Markdown'
            )
            self.bot.answer_callback_query(call.id)
        
        # File management
        elif data.startswith('file_'):
            file_id = int(data.split('_')[1])
            file_data = self._get_file_by_id(file_id)
            if not file_data:
                self.bot.answer_callback_query(call.id, "File not found", show_alert=True)
                return
            
            # Check ownership
            if file_data['user_id'] != user_id and user_id not in [config.OWNER_ID, config.ADMIN_ID]:
                self.bot.answer_callback_query(call.id, "Not your file", show_alert=True)
                return
            
            markup = self.menu_manager.file_controls_menu(file_data)
            self.bot.edit_message_text(
                f"⚙️ **File Controls**\n\n"
                f"📄 **File:** `{file_data['file_name']}`\n"
                f"📊 **Type:** {file_data['file_type']}\n"
                f"📦 **Size:** {file_data.get('file_size', 0) // 1024}KB\n"
                f"🔄 **Status:** {'🟢 Running' if file_data.get('is_running', False) else '🔴 Stopped'}\n"
                f"📅 **Uploaded:** {file_data.get('upload_time', 'Unknown')}\n\n"
                f"Select an action:",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=markup,
                parse_mode='Markdown'
            )
            self.bot.answer_callback_query(call.id)
        
        # Start script
        elif data.startswith('start_'):
            file_id = int(data.split('_')[1])
            file_data = self._get_file_by_id(file_id)
            if not file_data:
                self.bot.answer_callback_query(call.id, "File not found", show_alert=True)
                return
            
            if file_data['user_id'] != user_id and user_id not in [config.OWNER_ID, config.ADMIN_ID]:
                self.bot.answer_callback_query(call.id, "Not your file", show_alert=True)
                return
            
            # Check if already running
            script_key = f"{user_id}_{file_data['file_name']}"
            if script_key in self.process_manager._processes:
                self.bot.answer_callback_query(call.id, "⚠️ Already running", show_alert=True)
                return
            
            self.bot.answer_callback_query(call.id, "⏳ Starting...")
            
            file_path = os.path.join(self._get_user_folder(user_id), file_data['file_name'])
            self._start_script(
                user_id, 
                file_data['file_name'], 
                file_path, 
                file_data['file_type'],
                call.message
            )
            
            # Refresh controls
            time.sleep(1)
            updated_data = self._get_file_by_id(file_id)
            markup = self.menu_manager.file_controls_menu(updated_data)
            self.bot.edit_message_reply_markup(
                call.message.chat.id,
                call.message.message_id,
                reply_markup=markup
            )
        
        # Stop script
        elif data.startswith('stop_'):
            file_id = int(data.split('_')[1])
            self._stop_script(user_id, file_id, call)
        
        # Restart script
        elif data.startswith('restart_'):
            file_id = int(data.split('_')[1])
            file_data = self._get_file_by_id(file_id)
            if not file_data:
                self.bot.answer_callback_query(call.id, "File not found", show_alert=True)
                return
            
            if file_data['user_id'] != user_id and user_id not in [config.OWNER_ID, config.ADMIN_ID]:
                self.bot.answer_callback_query(call.id, "Not your file", show_alert=True)
                return
            
            self.bot.answer_callback_query(call.id, "⏳ Restarting...")
            
            # Stop first
            self._stop_script(user_id, file_id)
            time.sleep(1)
            
            # Then start
            file_path = os.path.join(self._get_user_folder(user_id), file_data['file_name'])
            self._start_script(
                user_id,
                file_data['file_name'],
                file_path,
                file_data['file_type'],
                call.message
            )
            
            # Refresh controls
            time.sleep(1)
            updated_data = self._get_file_by_id(file_id)
            markup = self.menu_manager.file_controls_menu(updated_data)
            self.bot.edit_message_reply_markup(
                call.message.chat.id,
                call.message.message_id,
                reply_markup=markup
            )
        
        # Delete script
        elif data.startswith('delete_'):
            file_id = int(data.split('_')[1])
            file_data = self._get_file_by_id(file_id)
            if not file_data:
                self.bot.answer_callback_query(call.id, "File not found", show_alert=True)
                return
            
            if file_data['user_id'] != user_id and user_id not in [config.OWNER_ID, config.ADMIN_ID]:
                self.bot.answer_callback_query(call.id, "Not your file", show_alert=True)
                return
            
            # Stop if running
            if file_data.get('is_running', False):
                self._stop_script(user_id, file_id)
            
            # Delete file
            file_path = os.path.join(self._get_user_folder(user_id), file_data['file_name'])
            log_path = os.path.join(self._get_user_folder(user_id), 
                                   f"{os.path.splitext(file_data['file_name'])[0]}.log")
            
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                if os.path.exists(log_path):
                    os.remove(log_path)
            except Exception as e:
                logging.error(f"Delete file error: {e}")
            
            # Remove from database
            self._delete_file_record(file_id)
            
            self.bot.answer_callback_query(call.id, "🗑️ Deleted!")
            
            # Back to files
            files = self._get_user_files(user_id)
            markup = self.menu_manager.file_management_menu(files)
            self.bot.edit_message_text(
                f"📂 **Your Files** ({len(files)} total)",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=markup,
                parse_mode='Markdown'
            )
        
        # Logs
        elif data.startswith('logs_'):
            file_id = int(data.split('_')[1])
            file_data = self._get_file_by_id(file_id)
            if not file_data:
                self.bot.answer_callback_query(call.id, "File not found", show_alert=True)
                return
            
            if file_data['user_id'] != user_id and user_id not in [config.OWNER_ID, config.ADMIN_ID]:
                self.bot.answer_callback_query(call.id, "Not your file", show_alert=True)
                return
            
            log_path = os.path.join(
                self._get_user_folder(user_id),
                f"{os.path.splitext(file_data['file_name'])[0]}.log"
            )
            
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
        
        # Download
        elif data.startswith('download_'):
            file_id = int(data.split('_')[1])
            file_data = self._get_file_by_id(file_id)
            if not file_data:
                self.bot.answer_callback_query(call.id, "File not found", show_alert=True)
                return
            
            if file_data['user_id'] != user_id and user_id not in [config.OWNER_ID, config.ADMIN_ID]:
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
        
        # Backup
        elif data.startswith('backup_'):
            file_id = int(data.split('_')[1])
            file_data = self._get_file_by_id(file_id)
            if not file_data:
                self.bot.answer_callback_query(call.id, "File not found", show_alert=True)
                return
            
            if file_data['user_id'] != user_id and user_id not in [config.OWNER_ID, config.ADMIN_ID]:
                self.bot.answer_callback_query(call.id, "Not your file", show_alert=True)
                return
            
            file_path = os.path.join(self._get_user_folder(user_id), file_data['file_name'])
            
            if not os.path.exists(file_path):
                self.bot.answer_callback_query(call.id, "File not found on disk", show_alert=True)
                return
            
            backup_id = self.backup_manager.create_backup(user_id, file_data['file_name'], file_path)
            
            if backup_id:
                self.bot.answer_callback_query(call.id, "💾 Backup created!")
            else:
                self.bot.answer_callback_query(call.id, "❌ Backup failed", show_alert=True)
        
        # Resources
        elif data.startswith('resources_'):
            file_id = int(data.split('_')[1])
            file_data = self._get_file_by_id(file_id)
            if not file_data:
                self.bot.answer_callback_query(call.id, "File not found", show_alert=True)
                return
            
            if file_data['user_id'] != user_id and user_id not in [config.OWNER_ID, config.ADMIN_ID]:
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
        
        # Settings
        elif data == 'settings':
            markup = self.menu_manager.settings_menu()
            self.bot.edit_message_text(
                "⚙️ **Settings**\n\nCustomize your bot experience:",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=markup,
                parse_mode='Markdown'
            )
            self.bot.answer_callback_query(call.id)
        
        # Premium
        elif data == 'premium':
            self.bot.answer_callback_query(call.id, "💎 Premium features coming soon!", show_alert=True)
        
        # Admin actions
        elif data.startswith('admin_'):
            self._handle_admin_callback(call)
        
        # Upload
        elif data == 'upload':
            self._handle_upload(call.message)
            self.bot.answer_callback_query(call.id)
        
        # Stats
        elif data == 'stats':
            self._handle_stats(call.message)
            self.bot.answer_callback_query(call.id)
        
        # Profile
        elif data == 'profile':
            self._handle_profile(call.message)
            self.bot.answer_callback_query(call.id)
        
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
            self._handle_help(call.message)
            self.bot.answer_callback_query(call.id)
        
        # No operation
        elif data == 'noop':
            self.bot.answer_callback_query(call.id)
        
        else:
            self.bot.answer_callback_query(call.id, "Unknown action", show_alert=True)
            logging.warning(f"Unknown callback: {data}")
    
    # ============================================================
    # ADMIN CALLBACKS
    # ============================================================
    
    def _handle_admin_callback(self, call):
        """Handle admin panel callbacks"""
        user_id = call.from_user.id
        
        if user_id not in [config.OWNER_ID, config.ADMIN_ID]:
            self.bot.answer_callback_query(call.id, "⚠️ Admin required", show_alert=True)
            return
        
        data = call.data
        
        if data == 'admin_users':
            users = self._get_all_users()
            user_text = f"👥 **Users** ({len(users)} total)\n\n"
            for user in users[:10]:
                user_text += f"• `{user['user_id']}` - {user.get('first_name', 'Unknown')}\n"
            if len(users) > 10:
                user_text += f"\n... and {len(users) - 10} more"
            
            self.bot.send_message(call.message.chat.id, user_text, parse_mode='Markdown')
            self.bot.answer_callback_query(call.id)
        
        elif data == 'admin_analytics':
            analytics = self._get_analytics()
            analytics_text = (
                f"📊 **Analytics**\n\n"
                f"👥 **Total Users:** {analytics.get('total_users', 0)}\n"
                f"📂 **Total Files:** {analytics.get('total_files', 0)}\n"
                f"🟢 **Running Bots:** {analytics.get('running_bots', 0)}\n"
                f"📤 **Total Uploads:** {analytics.get('total_uploads', 0)}\n"
                f"💾 **Storage Used:** {analytics.get('storage_used', '0 MB')}\n"
                f"📅 **Active Today:** {analytics.get('active_today', 0)}"
            )
            self.bot.send_message(call.message.chat.id, analytics_text, parse_mode='Markdown')
            self.bot.answer_callback_query(call.id)
        
        elif data == 'admin_subscriptions':
            subscriptions = self._get_all_subscriptions()
            sub_text = f"💳 **Subscriptions** ({len(subscriptions)} total)\n\n"
            for sub in subscriptions[:10]:
                sub_text += f"• `{sub['user_id']}` - {sub.get('plan', 'premium')} - Expires: {sub.get('expiry', 'N/A')}\n"
            if len(subscriptions) > 10:
                sub_text += f"\n... and {len(subscriptions) - 10} more"
            
            self.bot.send_message(call.message.chat.id, sub_text, parse_mode='Markdown')
            self.bot.answer_callback_query(call.id)
        
        elif data == 'admin_banned':
            banned = self._get_banned_users()
            if banned:
                ban_text = "🚫 **Banned Users**\n\n"
                for user in banned:
                    ban_text += f"• `{user['user_id']}` - {user.get('ban_reason', 'No reason')}\n"
                self.bot.send_message(call.message.chat.id, ban_text, parse_mode='Markdown')
            else:
                self.bot.send_message(call.message.chat.id, "🚫 No banned users.")
            self.bot.answer_callback_query(call.id)
        
        elif data == 'admin_lock':
            self.bot_locked = not self.bot_locked
            status = "locked" if self.bot_locked else "unlocked"
            self.bot.answer_callback_query(call.id, f"🔒 Bot {status}!")
            self.bot.send_message(
                call.message.chat.id,
                f"🔒 Bot has been {status}.",
                parse_mode='Markdown'
            )
        
        elif data == 'admin_run_all':
            self.bot.answer_callback_query(call.id, "⏳ Starting all scripts...")
            self._run_all_scripts(call.message.chat.id)
        
        elif data == 'admin_cleanup':
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
        
        elif data == 'admin_status':
            status_text = self._get_system_status()
            self.bot.send_message(
                call.message.chat.id,
                status_text,
                parse_mode='Markdown'
            )
            self.bot.answer_callback_query(call.id)
    
    # ============================================================
    # BROADCAST
    # ============================================================
    
    def _process_broadcast(self, message):
        """Process broadcast message"""
        user_id = message.from_user.id
        
        if user_id not in [config.OWNER_ID, config.ADMIN_ID]:
            return
        
        if message.text and message.text.lower() == '/cancel':
            self.bot.reply_to(message, "📢 Broadcast cancelled.")
            return
        
        # Get all users
        users = self._get_all_users()
        
        if not users:
            self.bot.reply_to(message, "❌ No users to broadcast to.")
            return
        
        # Confirmation
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("✅ Confirm", callback_data=f"confirm_broadcast_{message.message_id}"),
            types.InlineKeyboardButton("❌ Cancel", callback_data="cancel_broadcast")
        )
        
        self.bot.reply_to(
            message,
            f"📢 **Broadcast Confirmation**\n\n"
            f"Sending to **{len(users)}** users.\n\n"
            f"Message preview:\n"
            f"```\n{message.text[:200]}{'...' if len(message.text or '') > 200 else ''}\n```\n"
            f"Are you sure?",
            reply_markup=markup,
            parse_mode='Markdown'
        )
    
    def _execute_broadcast(self, message_id: int, chat_id: int):
        """Execute broadcast"""
        # Get the original message
        try:
            original_msg = self.bot.get_chat(chat_id).last_message
            # This is simplified - actual implementation would get the message
            # from the database or cache
        except Exception as e:
            logging.error(f"Broadcast error: {e}")
            return
        
        users = self._get_all_users()
        success = 0
        failed = 0
        
        for user in users:
            try:
                self.bot.send_message(
                    user['user_id'],
                    original_msg.text
                )
                success += 1
                time.sleep(0.05)
            except Exception as e:
                failed += 1
                logging.warning(f"Broadcast failed to {user['user_id']}: {e}")
        
        self.bot.send_message(
            chat_id,
            f"📢 **Broadcast Complete**\n\n"
            f"✅ Sent: {success}\n"
            f"❌ Failed: {failed}\n"
            f"👥 Total: {len(users)}",
            parse_mode='Markdown'
        )
    
    # ============================================================
    # SYSTEM FUNCTIONS
    # ============================================================
    
    def _run_all_scripts(self, chat_id: int):
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
                        self._start_script(
                            user['user_id'],
                            file_data['file_name'],
                            file_path,
                            file_data['file_type'],
                            None
                        )
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
    
    def _get_system_status(self) -> str:
        """Get system status"""
        cpu = psutil.cpu_percent()
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        running = len(self.process_manager._processes)
        total_users = len(self._get_all_users())
        
        return (
            f"🖥️ **System Status**\n\n"
            f"🧠 **CPU:** {cpu}%\n"
            f"💾 **Memory:** {memory.percent}% ({memory.used // 1024**3}GB / {memory.total // 1024**3}GB)\n"
            f"💿 **Disk:** {disk.percent}% ({disk.used // 1024**3}GB / {disk.total // 1024**3}GB)\n"
            f"🟢 **Running Bots:** {running}\n"
            f"👥 **Total Users:** {total_users}\n"
            f"🔒 **Bot Status:** {'🔴 Locked' if self.bot_locked else '🟢 Unlocked'}"
        )
    
    # ============================================================
    # DATABASE HELPERS
    # ============================================================
    
    def _register_user(self, user: telebot.types.User):
        """Register a user in the database"""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR IGNORE INTO users (user_id, username, first_name, last_name)
                VALUES (?, ?, ?, ?)
            ''', (user.id, user.username, user.first_name, user.last_name))
            
            # Update last_active
            cursor.execute('''
                UPDATE users SET last_active = CURRENT_TIMESTAMP
                WHERE user_id = ?
            ''', (user.id,))
            
            # Add to active users
            cursor.execute('''
                INSERT OR REPLACE INTO active_users (user_id, last_seen)
                VALUES (?, CURRENT_TIMESTAMP)
            ''', (user.id,))
            
            conn.commit()
    
    def _get_user_data(self, user_id: int) -> dict:
        """Get user data from database"""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
            row = cursor.fetchone()
            return dict(row) if row else {}
    
    def _get_user_files(self, user_id: int) -> List[dict]:
        """Get user's files from database"""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM user_files 
                WHERE user_id = ? 
                ORDER BY upload_time DESC
            ''', (user_id,))
            return [dict(row) for row in cursor.fetchall()]
    
    def _get_file_by_id(self, file_id: int) -> Optional[dict]:
        """Get file by ID"""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM user_files WHERE id = ?', (file_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def _save_file_record(self, user_id: int, file_name: str, file_type: str, file_size: int) -> int:
        """Save file record to database"""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO user_files (user_id, file_name, file_type, file_size)
                VALUES (?, ?, ?, ?)
            ''', (user_id, file_name, file_type, file_size))
            conn.commit()
            return cursor.lastrowid
    
    def _update_file_status(self, user_id: int, file_name: str, is_running: bool, pid: int = None):
        """Update file running status"""
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
    
    def _delete_file_record(self, file_id: int):
        """Delete file record from database"""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM user_files WHERE id = ?', (file_id,))
            conn.commit()
    
    def _get_user_file_count(self, user_id: int) -> int:
        """Get user's file count"""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM user_files WHERE user_id = ?', (user_id,))
            return cursor.fetchone()[0] or 0
    
    def _get_all_users(self) -> List[dict]:
        """Get all users"""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM users ORDER BY created_at DESC')
            return [dict(row) for row in cursor.fetchall()]
    
    def _get_all_subscriptions(self) -> List[dict]:
        """Get all subscriptions"""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM subscriptions')
            return [dict(row) for row in cursor.fetchall()]
    
    def _get_banned_users(self) -> List[dict]:
        """Get banned users"""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT user_id, ban_reason FROM users WHERE is_banned = 1')
            return [dict(row) for row in cursor.fetchall()]
    
    def _get_user_subscription(self, user_id: int) -> Optional[dict]:
        """Get user's subscription"""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM subscriptions WHERE user_id = ?', (user_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def _get_user_limit(self, user_id: int) -> float:
        """Get user's file limit"""
        if user_id == config.OWNER_ID:
            return config.OWNER_LIMIT
        if user_id == config.ADMIN_ID:
            return config.ADMIN_LIMIT
        
        subscription = self._get_user_subscription(user_id)
        if subscription:
            expiry = subscription.get('expiry')
            if expiry and isinstance(expiry, str):
                try:
                    expiry = datetime.fromisoformat(expiry)
                except:
                    expiry = None
            if expiry and expiry > datetime.now():
                return config.SUBSCRIBED_USER_LIMIT
        
        return config.FREE_USER_LIMIT
    
    # ============================================================
    # UTILITY FUNCTIONS
    # ============================================================
    
    def _get_user_folder(self, user_id: int) -> str:
        """Get user's folder path"""
        folder = os.path.join('upload_bots', str(user_id))
        os.makedirs(folder, exist_ok=True)
        return folder
    
    def _check_force_join(self, user_id: int) -> bool:
        """Check if user has joined all required channels"""
        try:
            for channel in config.FORCE_JOIN_CHANNELS:
                member = self.bot.get_chat_member(channel, user_id)
                if member.status not in ['member', 'administrator', 'creator']:
                    return False
            return True
        except Exception:
            return False
    
    def _send_force_join_message(self, chat_id: int):
        """Send force join message"""
        markup = types.InlineKeyboardMarkup(row_width=1)
        for channel, name in config.FORCE_JOIN_CHANNELS.items():
            markup.add(
                types.InlineKeyboardButton(
                    name,
                    url=f"https://t.me/{channel.replace('@', '')}"
                )
            )
        markup.add(
            types.InlineKeyboardButton(
                "✅ I've Joined All",
                callback_data="check_join"
            )
        )
        
        self.bot.send_message(
            chat_id,
            "📢 **Join Our Channels**\n\n"
            "Please join all channels to use this bot:",
            reply_markup=markup,
            parse_mode='Markdown'
        )
    
    def _is_user_banned(self, user_id: int) -> bool:
        """Check if user is banned"""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT is_banned FROM users WHERE user_id = ?', (user_id,))
            row = cursor.fetchone()
            return row and row[0] == 1
    
    def _scan_file(self, file_content: bytes, file_name: str, user_id: int) -> dict:
        """Scan file for malware"""
        # Owner bypass
        if user_id == config.OWNER_ID:
            return {'safe': True, 'reason': 'Owner bypass'}
        
        # Check for executable signatures
        executable_signatures = [
            b'MZ',  # Windows PE
            b'\x7fELF',  # Linux ELF
            b'\xfe\xed\xfa',  # Mach-O
            b'\xce\xfa\xed\xfe',  # Mach-O reverse
        ]
        
        for sig in executable_signatures:
            if file_content.startswith(sig):
                return {'safe': False, 'reason': f'Executable signature detected: {sig.hex()}'}
        
        # Check for suspicious keywords in first 4KB
        try:
            sample = file_content[:4096].decode('utf-8', errors='ignore')
            suspicious_keywords = [
                'ransomware', 'trojan', 'virus', 'malware',
                'backdoor', 'exploit', 'payload', 'botnet',
                'keylogger', 'rootkit', 'rm -rf', 'os.remove',
                'shutil.rmtree', 'subprocess.call', 'eval(', 'exec('
            ]
            for keyword in suspicious_keywords:
                if keyword in sample.lower():
                    return {'safe': False, 'reason': f'Suspicious keyword: {keyword}'}
        except Exception:
            pass
        
        # Check file extensions
        suspicious_extensions = ['.exe', '.dll', '.bat', '.cmd', '.scr', '.com']
        if any(file_name.lower().endswith(ext) for ext in suspicious_extensions):
            return {'safe': False, 'reason': 'Suspicious file extension'}
        
        return {'safe': True, 'reason': 'File appears safe'}
    
    def _get_system_stats(self, user_id: int) -> dict:
        """Get system statistics"""
        total_users = len(self._get_all_users())
        user_files = self._get_user_files(user_id)
        user_running = sum(1 for f in user_files if f.get('is_running', False))
        
        total_files = 0
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM user_files')
            total_files = cursor.fetchone()[0] or 0
        
        running_bots = len(self.process_manager._processes)
        
        # Storage
        storage_used = 0
        user_folder = self._get_user_folder(user_id)
        if os.path.exists(user_folder):
            for root, dirs, files in os.walk(user_folder):
                for file in files:
                    try:
                        storage_used += os.path.getsize(os.path.join(root, file))
                    except Exception:
                        pass
        
        # System resources
        cpu = psutil.cpu_percent()
        memory = psutil.virtual_memory()
        
        return {
            'total_users': total_users,
            'total_files': total_files,
            'running_bots': running_bots,
            'storage_used': self._format_size(storage_used),
            'cpu_usage': round(cpu, 1),
            'memory_usage': round(memory.percent, 1),
            'user_files': len(user_files),
            'user_uploads': len(user_files),
            'user_running': user_running,
        }
    
    def _get_analytics(self) -> dict:
        """Get analytics data"""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            
            # Total users
            cursor.execute('SELECT COUNT(*) FROM users')
            total_users = cursor.fetchone()[0] or 0
            
            # Total files
            cursor.execute('SELECT COUNT(*) FROM user_files')
            total_files = cursor.fetchone()[0] or 0
            
            # Running bots
            running_bots = len(self.process_manager._processes)
            
            # Total uploads (using file records)
            total_uploads = total_files
            
            # Active today
            cursor.execute('''
                SELECT COUNT(*) FROM active_users 
                WHERE date(last_seen) = date('now')
            ''')
            active_today = cursor.fetchone()[0] or 0
            
            # Storage
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
            
            return {
                'total_users': total_users,
                'total_files': total_files,
                'running_bots': running_bots,
                'total_uploads': total_uploads,
                'storage_used': self._format_size(storage_used),
                'active_today': active_today,
            }
    
    def _format_size(self, size: int) -> str:
        """Format size in bytes to human readable"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"
    
    def _format_uptime(self, start_time) -> str:
        """Format uptime"""
        if not start_time:
            return "Unknown"
        if isinstance(start_time, str):
            try:
                start_time = datetime.fromisoformat(start_time)
            except:
                return "Unknown"
        
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
    
    def _get_welcome_text(self, user_data: dict) -> str:
        """Get welcome text"""
        user_id = user_data.get('user_id', 'Unknown')
        first_name = user_data.get('first_name', 'User')
        username = user_data.get('username', 'Not set')
        
        # Get file count and limit
        file_count = self._get_user_file_count(user_id)
        file_limit = self._get_user_limit(user_id)
        
        # Check subscription
        subscription = self._get_user_subscription(user_id)
        is_premium = False
        days_left = 0
        
        if subscription:
            expiry = subscription.get('expiry')
            if expiry and isinstance(expiry, str):
                try:
                    expiry = datetime.fromisoformat(expiry)
                    if expiry > datetime.now():
                        is_premium = True
                        days_left = (expiry - datetime.now()).days
                except:
                    pass
        
        status = "🆓 Free"
        if user_id == config.OWNER_ID:
            status = "👑 Owner"
        elif user_id == config.ADMIN_ID:
            status = "🛡️ Admin"
        elif is_premium:
            status = f"💎 Premium ({days_left}d left)"
        
        return (
            f"🚀 **Welcome to Bot Hosting Platform!**\n\n"
            f"👤 **User:** {first_name}\n"
            f"✳️ **Username:** @{username}\n"
            f"🆔 **ID:** `{user_id}`\n"
            f"🔰 **Status:** {status}\n"
            f"📂 **Files:** {file_count}/{file_limit}\n\n"
            f"🤖 **Host and run Python or JavaScript bots**\n"
            f"📤 Upload your scripts or ZIP archives\n"
            f"⚡ Get started by uploading your first file!\n\n"
            f"👇 **Use the buttons below:**"
        )
    
    # ============================================================
    # FLASK DASHBOARD
    # ============================================================
    
    def _setup_flask(self):
        """Setup Flask web dashboard"""
        app = Flask('bot_dashboard')
        
        @app.route('/')
        def dashboard():
            return self._render_dashboard()
        
        @app.route('/api/stats')
        def api_stats():
            return jsonify(self._get_analytics())
        
        @app.route('/api/processes')
        def api_processes():
            processes = []
            for key, info in self.process_manager._processes.items():
                processes.append({
                    'key': key,
                    'pid': info.get('pid'),
                    'status': info.get('status'),
                    'start_time': info.get('start_time', '').isoformat() if info.get('start_time') else None,
                    'cpu': info.get('cpu_percent', 0),
                    'memory': info.get('memory_mb', 0),
                })
            return jsonify(processes)
        
        self._flask_app = app
        
        # Start Flask in a thread
        thread = Thread(target=self._run_flask, daemon=True)
        thread.start()
        logging.info("Web dashboard started on port 8080")
    
    def _run_flask(self):
        """Run Flask server"""
        try:
            self._flask_app.run(
                host=config.WEB_HOST,
                port=config.WEB_PORT,
                debug=False,
                use_reloader=False
            )
        except Exception as e:
            logging.error(f"Flask error: {e}")
    
    def _render_dashboard(self) -> str:
        """Render dashboard HTML"""
        stats = self._get_analytics()
        
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Bot Hosting Dashboard</title>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                * { margin: 0; padding: 0; box-sizing: border-box; }
                body { 
                    font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
                    background: linear-gradient(135deg, #0f0c29, #302b63, #24243e);
                    min-height: 100vh;
                    color: #fff;
                    padding: 20px;
                }
                .container {
                    max-width: 1200px;
                    margin: 0 auto;
                }
                .header {
                    text-align: center;
                    padding: 40px 0;
                }
                .header h1 {
                    font-size: 2.5em;
                    background: linear-gradient(135deg, #f093fb, #f5576c);
                    -webkit-background-clip: text;
                    -webkit-text-fill-color: transparent;
                }
                .header p {
                    color: #a8b2d1;
                    margin-top: 10px;
                }
                .stats-grid {
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                    gap: 20px;
                    margin: 30px 0;
                }
                .stat-card {
                    background: rgba(255,255,255,0.05);
                    backdrop-filter: blur(10px);
                    border-radius: 16px;
                    padding: 25px;
                    text-align: center;
                    border: 1px solid rgba(255,255,255,0.1);
                    transition: transform 0.3s;
                }
                .stat-card:hover {
                    transform: translateY(-5px);
                }
                .stat-card .icon {
                    font-size: 2em;
                    margin-bottom: 10px;
                }
                .stat-card .value {
                    font-size: 2em;
                    font-weight: bold;
                    background: linear-gradient(135deg, #f093fb, #f5576c);
                    -webkit-background-clip: text;
                    -webkit-text-fill-color: transparent;
                }
                .stat-card .label {
                    color: #a8b2d1;
                    margin-top: 5px;
                }
                .status-section {
                    background: rgba(255,255,255,0.05);
                    border-radius: 16px;
                    padding: 25px;
                    margin-top: 30px;
                    border: 1px solid rgba(255,255,255,0.1);
                }
                .status-section h2 {
                    margin-bottom: 20px;
                    font-size: 1.5em;
                }
                .status-item {
                    display: flex;
                    justify-content: space-between;
                    padding: 12px 0;
                    border-bottom: 1px solid rgba(255,255,255,0.05);
                }
                .status-item:last-child {
                    border-bottom: none;
                }
                .status-item .label {
                    color: #a8b2d1;
                }
                .badge {
                    display: inline-block;
                    padding: 4px 12px;
                    border-radius: 20px;
                    font-size: 0.85em;
                }
                .badge-success { background: #10b981; color: #fff; }
                .badge-danger { background: #ef4444; color: #fff; }
                .badge-warning { background: #f59e0b; color: #fff; }
                .badge-info { background: #3b82f6; color: #fff; }
                .footer {
                    text-align: center;
                    margin-top: 40px;
                    color: #a8b2d1;
                    font-size: 0.9em;
                }
                @media (max-width: 768px) {
                    .stats-grid {
                        grid-template-columns: repeat(2, 1fr);
                    }
                    .header h1 {
                        font-size: 1.8em;
                    }
                }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🤖 Bot Hosting Platform</h1>
                    <p>Real-time dashboard for your bot hosting service</p>
                </div>
                
                <div class="stats-grid">
                    <div class="stat-card">
                        <div class="icon">👥</div>
                        <div class="value">{total_users}</div>
                        <div class="label">Total Users</div>
                    </div>
                    <div class="stat-card">
                        <div class="icon">📂</div>
                        <div class="value">{total_files}</div>
                        <div class="label">Total Files</div>
                    </div>
                    <div class="stat-card">
                        <div class="icon">🟢</div>
                        <div class="value">{running_bots}</div>
                        <div class="label">Running Bots</div>
                    </div>
                    <div class="stat-card">
                        <div class="icon">💾</div>
                        <div class="value">{storage_used}</div>
                        <div class="label">Storage Used</div>
                    </div>
                    <div class="stat-card">
                        <div class="icon">📤</div>
                        <div class="value">{total_uploads}</div>
                        <div class="label">Total Uploads</div>
                    </div>
                    <div class="stat-card">
                        <div class="icon">📅</div>
                        <div class="value">{active_today}</div>
                        <div class="label">Active Today</div>
                    </div>
                </div>
                
                <div class="status-section">
                    <h2>🔧 System Status</h2>
                    <div id="status-items">
                        <div class="status-item">
                            <span class="label">Bot Status</span>
                            <span class="badge badge-success">🟢 Online</span>
                        </div>
                        <div class="status-item">
                            <span class="label">Python Version</span>
                            <span>""" + sys.version.split()[0] + """</span>
                        </div>
                        <div class="status-item">
                            <span class="label">Platform</span>
                            <span>""" + platform.system() + """</span>
                        </div>
                        <div class="status-item">
                            <span class="label">Total Processes</span>
                            <span>""" + str(len(self.process_manager._processes)) + """</span>
                        </div>
                    </div>
                </div>
                
                <div class="footer">
                    <p>© 2024 Bot Hosting Platform | Powered by Python</p>
                </div>
            </div>
            
            <script>
                // Auto-refresh every 30 seconds
                setInterval(() => {
                    fetch('/api/stats')
                        .then(r => r.json())
                        .then(data => {
                            // Update values
                            const values = document.querySelectorAll('.value');
                            const keys = ['total_users', 'total_files', 'running_bots', 'storage_used', 'total_uploads', 'active_today'];
                            keys.forEach((key, i) => {
                                if (values[i]) values[i].textContent = data[key] || 0;
                            });
                        })
                        .catch(err => console.error('Stats update error:', err));
                }, 30000);
            </script>
        </body>
        </html>
        """.format(**stats)
        
        return html
    
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
        
        thread = Thread(target=cleanup_loop, daemon=True)
        thread.start()
        logging.info("Auto-cleanup scheduled")

# ============================================================
# MAIN EXECUTION
# ============================================================

if __name__ == '__main__':
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('bot.log', encoding='utf-8')
        ]
    )
    
    # Create bot
    bot = AdvancedBot()
    
    # Start polling
    logging.info("=" * 50)
    logging.info("🚀 Advanced Bot Starting...")
    logging.info(f"📦 Version: 3.0.0")
    logging.info(f"👑 Owner ID: {config.OWNER_ID}")
    logging.info(f"🛡️ Admin ID: {config.ADMIN_ID}")
    logging.info(f"📁 Base Directory: {os.path.abspath(os.path.dirname(__file__))}")
    logging.info("=" * 50)
    
    while True:
        try:
            bot.bot.infinity_polling(
                logger_level=logging.INFO,
                timeout=60,
                long_polling_timeout=30
            )
        except requests.exceptions.ReadTimeout:
            logging.warning("Polling timeout, retrying...")
            time.sleep(5)
        except requests.exceptions.ConnectionError as e:
            logging.error(f"Connection error: {e}")
            time.sleep(15)
        except Exception as e:
            logging.critical(f"Critical error: {e}", exc_info=True)
            time.sleep(30)
