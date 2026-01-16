"""Main application entry point with Tkinter GUI"""

import asyncio
import sys
import logging
import threading
from pathlib import Path
from datetime import datetime
from typing import List
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from app.scanner import BetBoomScanner
from app.models import MatchData, Signal
from app.config import APP_DATA_DIR
from app.storage import Storage

# Setup logging
log_dir = Path(APP_DATA_DIR)
log_dir.mkdir(exist_ok=True)
log_file = log_dir / "errors.log"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


class ScannerGUI:
    """Tkinter GUI for BetBoom Scanner"""
    
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("BetBoom Live Scanner")
        self.root.geometry("1400x700")
        
        self.scanner: BetBoomScanner = None
        self.scanner_thread: threading.Thread = None
        self.loop: asyncio.AbstractEventLoop = None
        self.is_scanning = False
        
        self.storage = Storage()
        
        # Match data storage
        self.matches: List[MatchData] = []
        self.last_scan_time = datetime.now()
        
        self._setup_ui()
        self._setup_event_loop()
    
    def _setup_ui(self):
        """Setup UI components"""
        # Top frame with controls
        control_frame = ttk.Frame(self.root, padding="10")
        control_frame.pack(fill=tk.X)
        
        self.start_btn = ttk.Button(control_frame, text="Start", command=self.start_scanning, width=15)
        self.start_btn.pack(side=tk.LEFT, padx=5)
        
        self.stop_btn = ttk.Button(control_frame, text="Stop", command=self.stop_scanning, state=tk.DISABLED, width=15)
        self.stop_btn.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(control_frame, text="Open signals.csv", command=self.open_signals_csv, width=15).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="Open logs folder", command=self.open_logs_folder, width=15).pack(side=tk.LEFT, padx=5)
        
        # Status bar
        self.status_label = ttk.Label(control_frame, text="Готов к запуску", foreground="gray")
        self.status_label.pack(side=tk.RIGHT, padx=10)
        
        # Main frame with table
        table_frame = ttk.Frame(self.root, padding="10")
        table_frame.pack(fill=tk.BOTH, expand=True)
        
        # Treeview for matches
        columns = ('Игроки', 'Лига', 'Счёт по сетам', 'Текущий счёт 3-го сета', 
                  'Кф матч P1/P2', 'Кф 3-й сет P1/P2', 'Dominance', 'Статус', 'ReasonType', 'Время')
        
        self.tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=20)
        
        # Configure columns
        self.tree.heading('Игроки', text='Игроки')
        self.tree.heading('Лига', text='Лига')
        self.tree.heading('Счёт по сетам', text='Счёт по сетам')
        self.tree.heading('Текущий счёт 3-го сета', text='Текущий счёт 3-го сета')
        self.tree.heading('Кф матч P1/P2', text='Кф матч P1/P2')
        self.tree.heading('Кф 3-й сет P1/P2', text='Кф 3-й сет P1/P2')
        self.tree.heading('Dominance', text='Dominance')
        self.tree.heading('Статус', text='Статус')
        self.tree.heading('ReasonType', text='Type')
        self.tree.heading('Время', text='Время обновления')
        
        self.tree.column('Игроки', width=250)
        self.tree.column('Лига', width=150)
        self.tree.column('Счёт по сетам', width=120)
        self.tree.column('Текущий счёт 3-го сета', width=120)
        self.tree.column('Кф матч P1/P2', width=120)
        self.tree.column('Кф 3-й сет P1/P2', width=120)
        self.tree.column('Dominance', width=80)
        self.tree.column('Статус', width=100)
        self.tree.column('ReasonType', width=60)
        self.tree.column('Время', width=120)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Bottom info frame
        info_frame = ttk.Frame(self.root, padding="10")
        info_frame.pack(fill=tk.X)
        
        self.info_label = ttk.Label(info_frame, text="Матчей: 0 | Сигналов сегодня: 0 | Последний скан: -")
        self.info_label.pack()
        
        # Update info periodically
        self.root.after(1000, self.update_info)
    
    def _setup_event_loop(self):
        """Setup asyncio event loop in separate thread"""
        def run_loop():
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            self.loop.run_forever()
        
        self.loop_thread = threading.Thread(target=run_loop, daemon=True)
        self.loop_thread.start()
    
    def start_scanning(self):
        """Start scanner"""
        if self.is_scanning:
            return
        
        self.is_scanning = True
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        
        # Create scanner
        self.scanner = BetBoomScanner()
        self.scanner.on_match_update = self.on_match_update
        self.scanner.on_signal = self.on_signal
        self.scanner.on_error = self.on_error
        
        # Start scanner in async thread
        asyncio.run_coroutine_threadsafe(self.scanner.start(), self.loop)
        
        self.status_label.config(text="Сканирование...", foreground="green")
        logger.info("Scanner started from GUI")
    
    def stop_scanning(self):
        """Stop scanner"""
        if not self.is_scanning:
            return
        
        self.is_scanning = False
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        
        if self.scanner:
            asyncio.run_coroutine_threadsafe(self.scanner.stop(), self.loop)
        
        self.status_label.config(text="Остановлен", foreground="orange")
        logger.info("Scanner stopped from GUI")
    
    def on_match_update(self, matches: List[MatchData]):
        """Callback for match updates"""
        self.matches = matches
        self.root.after(0, self._update_table)
    
    def _update_table(self):
        """Update table with current matches"""
        # Clear existing items
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # Сортируем: сигналы сверху
        sorted_matches = sorted(self.matches, key=lambda m: (m.status != "SIGNAL", m.last_update), reverse=True)
        
        # Add matches
        for match in sorted_matches:
            # Format players
            players_str = f"{match.player1} vs {match.player2}" if match.player1 and match.player2 else match.match_name
            
            # League
            league_str = match.league or "-"
            
            # Format sets score
            sets_str = " - ".join([f"{s.p1}:{s.p2}" for s in match.match_score.sets[:2]]) if match.match_score.sets else "-"
            
            # Current set score (для 3-го сета или текущего)
            current_str = f"{match.match_score.current_set_score.p1}:{match.match_score.current_set_score.p2}"
            
            # Match odds
            match_odds_str = "-"
            if match.match_odds.p1 is not None and match.match_odds.p2 is not None:
                match_odds_str = f"{match.match_odds.p1:.2f} / {match.match_odds.p2:.2f}"
            
            # Set 3 odds
            set3_odds_str = "-"
            if match.set3_odds.p1 is not None and match.set3_odds.p2 is not None:
                set3_odds_str = f"{match.set3_odds.p1:.2f} / {match.set3_odds.p2:.2f}"
            
            # Dominance
            dominance_str = str(match.dominance) if match.dominance > 0 else "-"
            
            # Status
            status = match.status
            status_display = status
            if status == "SIGNAL":
                status_display = "🎾 СИГНАЛ"
            elif status == "CANDIDATE":
                status_display = "CANDIDATE"
            elif status == "NO_MARKET":
                status_display = "NO MARKET"
            
            # ReasonType
            reason_type_str = match.reason.replace("TYPE ", "") if match.reason.startswith("TYPE ") else (match.reason if match.reason else "")
            
            # Time
            time_str = match.last_update.strftime("%H:%M:%S")
            
            # Insert row
            item = self.tree.insert('', tk.END, values=(
                players_str,
                league_str,
                sets_str,
                current_str,
                match_odds_str,
                set3_odds_str,
                dominance_str,
                status_display,
                reason_type_str,
                time_str
            ))
            
            # Color signal rows
            if status == "SIGNAL":
                self.tree.set(item, 'Статус', '🎾 СИГНАЛ')
                # Подсветка сигнальных строк
                self.tree.set(item, 'ReasonType', reason_type_str)
        
        # Update last scan time
        self.last_scan_time = datetime.now()
    
    def on_signal(self, signal: Signal):
        """Callback for signal detection"""
        logger.info(f"Signal TYPE {signal.reason_type} detected (dom={signal.dominance}): {signal.match_name}")
        
        signal_type_map = {
            "A": "TYPE A (SET3_OVERPRICE_AFTER_2_0)",
            "B": "TYPE B (SET3_OVERPRICE_AFTER_1_0_AND_SET2_LEAD)",
            "C": "TYPE C (SET3_SUSPICIOUS_EQUAL_LINE_UNDER_DOMINANCE)"
        }
        signal_type_name = signal_type_map.get(signal.reason_type, f"TYPE {signal.reason_type}")
        
        # Получаем имена игроков из match_name
        players = signal.match_name.split(" vs ") if " vs " in signal.match_name else [signal.match_name, ""]
        player1 = players[0] if len(players) > 0 else "Unknown"
        player2 = players[1] if len(players) > 1 else "Unknown"
        
        message = (
            f"ЖЕЛЕЗОБЕТОННЫЙ ПЕРЕКОС ({signal_type_name})\n\n"
            f"DOMINANCE: {signal.dominance}/100\n\n"
            f"Матч: {signal.match_name}\n"
            f"СТАВКА: Победа фаворита в 3-м сете @ {signal.set3_odds:.2f}\n\n"
            f"Почему:\n"
            f"• Фаворит по матчу: {signal.favorite_side} (кф {signal.match_odds:.2f})\n"
            f"• Счёт по сетам: {signal.sets_score}\n"
            f"• Суммарная разница очков: {signal.margin_total}\n"
        )
        
        if signal.reason_type in ("B", "C") and signal.set2_score_on_trigger:
            message += f"• Счёт 2-го сета: {signal.set2_score_on_trigger} (преимущество: {signal.set2_lead_margin})\n"
        
        message += f"• 3-й сет: {signal.current_set_score}\n"
        message += f"• Кф на 3-й сет: {signal.set3_odds:.2f}\n\n"
        message += f"Причина: {signal.trigger_reason}"
        
        messagebox.showinfo("🎾 IRON BET FOUND", message)
        
        # Генерируем текст сигнала для копирования
        signal_text = (
            f"ЖЕЛЕЗОБЕТОННЫЙ ПЕРЕКОС (TYPE {signal.reason_type}): {player1} vs {player2}\n"
            f"Доминирование: {signal.dominance}/100 | Сеты: {signal.sets_score} | 3-й сет: {signal.current_set_score}\n"
            f"Фаворит по матчу: {signal.favorite_side} ({signal.match_odds:.2f})\n"
            f"Кэф на фаворита в 3-м: {signal.set3_odds:.2f} | Ссылка: {signal.match_url}"
        )
        
        # Сохраняем в clipboard для удобного копирования
        try:
            import pyperclip
            pyperclip.copy(signal_text)
        except ImportError:
            pass
    
    def on_error(self, error: str):
        """Callback for errors"""
        logger.error(f"Scanner error: {error}")
        self.status_label.config(text=f"Ошибка: {error[:30]}...", foreground="red")
    
    def update_info(self):
        """Update info label"""
        matches_count = len(self.matches)
        signals_count = self.storage.get_today_signals_count()
        last_scan = self.last_scan_time.strftime("%H:%M:%S") if hasattr(self, 'last_scan_time') else "-"
        
        self.info_label.config(
            text=f"Матчей: {matches_count} | Сигналов сегодня: {signals_count} | Последний скан: {last_scan}"
        )
        
        self.root.after(1000, self.update_info)
    
    def open_signals_csv(self):
        """Open signals.csv file"""
        csv_path = self.storage.get_csv_path()
        if Path(csv_path).exists():
            import os
            os.startfile(csv_path)
        else:
            messagebox.showinfo("Info", "Файл signals.csv пока не создан")
    
    def open_logs_folder(self):
        """Open logs folder"""
        data_dir = self.storage.get_data_dir()
        if Path(data_dir).exists():
            import os
            os.startfile(data_dir)
        else:
            messagebox.showinfo("Info", "Папка логов пока не создана")


def main():
    """Main entry point"""
    try:
        root = tk.Tk()
        app = ScannerGUI(root)
        
        # Handle window close
        def on_closing():
            if app.is_scanning:
                app.stop_scanning()
            root.destroy()
            if app.loop:
                app.loop.call_soon_threadsafe(app.loop.stop)
            sys.exit(0)
        
        root.protocol("WM_DELETE_WINDOW", on_closing)
        
        root.mainloop()
        
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        messagebox.showerror("Fatal Error", f"Критическая ошибка: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

