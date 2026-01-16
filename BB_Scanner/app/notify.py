"""Notifications (sound + Windows toast)"""

import winsound
import os
from pathlib import Path
from app.models import Signal

try:
    from winotify import Notification
    WINOTIFY_AVAILABLE = True
except ImportError:
    WINOTIFY_AVAILABLE = False


def play_alert_sound():
    """Play system alert sound"""
    try:
        # Windows system sound
        winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
        # Additional beep
        winsound.Beep(800, 300)
    except Exception:
        pass


def show_toast_notification(signal: Signal):
    """Show Windows toast notification"""
    if not WINOTIFY_AVAILABLE:
        return
    
    try:
        signal_type_map = {
            "A": "TYPE A",
            "B": "TYPE B",
            "C": "TYPE C"
        }
        signal_type = signal_type_map.get(signal.reason_type, f"TYPE {signal.reason_type}")
        
        toast = Notification(
            app_id="BetBoom Scanner",
            title=f"🎾 IRON BET FOUND ({signal_type})",
            msg=f"DOMINANCE: {signal.dominance}/100\n"
                f"{signal.match_name}\n"
                f"BET: Fav wins Set 3 @ {signal.set3_odds:.2f}\n"
                f"Фаворит: {signal.favorite_side} (кф {signal.match_odds:.2f})\n"
                f"Счёт: {signal.sets_score} | 3-й сет: {signal.current_set_score}",
            duration="long",
            icon=str(Path(__file__).parent.parent / "icon.ico") if Path(__file__).parent.parent.joinpath("icon.ico").exists() else None
        )
        toast.show()
    except Exception:
        pass


def notify_signal(signal: Signal):
    """Notify about signal (sound + toast)"""
    play_alert_sound()
    show_toast_notification(signal)

