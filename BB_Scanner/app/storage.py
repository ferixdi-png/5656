"""Storage for signals (CSV + SQLite)"""

import sqlite3
import csv
import os
from pathlib import Path
from datetime import datetime
from typing import List
from app.config import APP_DATA_DIR, SIGNALS_CSV, SIGNALS_DB
from app.models import Signal


class Storage:
    """Manages signal storage in CSV and SQLite"""
    
    def __init__(self):
        self.data_dir = Path(APP_DATA_DIR)
        self.data_dir.mkdir(exist_ok=True)
        
        self.csv_path = self.data_dir / SIGNALS_CSV
        self.db_path = self.data_dir / SIGNALS_DB
        
        self._init_csv()
        self._init_db()
    
    def _init_csv(self):
        """Initialize CSV file with headers"""
        if not self.csv_path.exists():
            with open(self.csv_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'match_id', 'match_name', 'match_url',
                    'favorite_side', 'match_odds', 'set3_odds',
                    'sets_score', 'current_set_score', 'reason_type',
                    'dominance', 'margin_total',
                    'set2_score_on_trigger', 'set2_lead_margin', 'trigger_reason',
                    'detected_at'
                ])
    
    def _init_db(self):
        """Initialize SQLite database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                match_id TEXT NOT NULL,
                match_name TEXT NOT NULL,
                match_url TEXT NOT NULL,
                favorite_side TEXT NOT NULL,
                match_odds REAL NOT NULL,
                set3_odds REAL NOT NULL,
                sets_score TEXT NOT NULL,
                current_set_score TEXT NOT NULL,
                reason_type TEXT NOT NULL DEFAULT 'A',
                dominance INTEGER DEFAULT 0,
                margin_total INTEGER DEFAULT 0,
                set2_score_on_trigger TEXT,
                set2_lead_margin INTEGER,
                trigger_reason TEXT,
                detected_at TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Добавляем новые колонки если их нет (миграция)
        try:
            cursor.execute('ALTER TABLE signals ADD COLUMN reason_type TEXT DEFAULT "A"')
        except sqlite3.OperationalError:
            pass
        try:
            cursor.execute('ALTER TABLE signals ADD COLUMN dominance INTEGER DEFAULT 0')
        except sqlite3.OperationalError:
            pass
        try:
            cursor.execute('ALTER TABLE signals ADD COLUMN margin_total INTEGER DEFAULT 0')
        except sqlite3.OperationalError:
            pass
        try:
            cursor.execute('ALTER TABLE signals ADD COLUMN set2_score_on_trigger TEXT')
        except sqlite3.OperationalError:
            pass
        try:
            cursor.execute('ALTER TABLE signals ADD COLUMN set2_lead_margin INTEGER')
        except sqlite3.OperationalError:
            pass
        try:
            cursor.execute('ALTER TABLE signals ADD COLUMN trigger_reason TEXT')
        except sqlite3.OperationalError:
            pass
        
        conn.commit()
        conn.close()
    
    def save_signal(self, signal: Signal):
        """Save signal to both CSV and SQLite"""
        # Save to CSV
        with open(self.csv_path, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                signal.match_id,
                signal.match_name,
                signal.match_url,
                signal.favorite_side,
                signal.match_odds,
                signal.set3_odds,
                signal.sets_score,
                signal.current_set_score,
                signal.reason_type,
                signal.dominance,
                signal.margin_total,
                signal.set2_score_on_trigger,
                signal.set2_lead_margin,
                signal.trigger_reason,
                signal.detected_at.isoformat()
            ])
        
        # Save to SQLite
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO signals 
            (match_id, match_name, match_url, favorite_side, match_odds, 
             set3_odds, sets_score, current_set_score, reason_type, dominance, margin_total,
             set2_score_on_trigger, set2_lead_margin, trigger_reason, detected_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            signal.match_id,
            signal.match_name,
            signal.match_url,
            signal.favorite_side,
            signal.match_odds,
            signal.set3_odds,
            signal.sets_score,
            signal.current_set_score,
            signal.reason_type,
            signal.dominance,
            signal.margin_total,
            signal.set2_score_on_trigger,
            signal.set2_lead_margin,
            signal.trigger_reason,
            signal.detected_at.isoformat()
        ))
        
        conn.commit()
        conn.close()
    
    def get_today_signals_count(self) -> int:
        """Get count of signals detected today"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        today = datetime.now().date().isoformat()
        cursor.execute('''
            SELECT COUNT(*) FROM signals 
            WHERE DATE(detected_at) = ?
        ''', (today,))
        
        count = cursor.fetchone()[0]
        conn.close()
        
        return count
    
    def get_csv_path(self) -> str:
        """Get path to CSV file"""
        return str(self.csv_path)
    
    def get_data_dir(self) -> str:
        """Get path to data directory"""
        return str(self.data_dir)

