"""Data models for matches and signals"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Tuple, Dict


@dataclass
class MatchOdds:
    """Коэффициенты на матч"""
    p1: Optional[float] = None
    p2: Optional[float] = None


@dataclass
class SetScore:
    """Счёт сета"""
    p1: int = 0
    p2: int = 0


@dataclass
class MatchScore:
    """Счёт по сетам"""
    sets: list[SetScore] = field(default_factory=list)
    current_set: int = 1
    current_set_score: SetScore = field(default_factory=SetScore)


@dataclass
class MatchData:
    """Данные матча"""
    match_id: str
    match_name: str = ""
    match_url: str = ""
    player1: str = ""  # Фамилия игрока 1
    player2: str = ""  # Фамилия игрока 2
    league: Optional[str] = None  # Лига/турнир
    match_odds: MatchOdds = field(default_factory=MatchOdds)
    match_score: MatchScore = field(default_factory=MatchScore)
    set3_odds: MatchOdds = field(default_factory=MatchOdds)
    last_update: datetime = field(default_factory=datetime.now)
    status: str = "OK"  # OK, SIGNAL, CANDIDATE, NO_MARKET, ERROR
    reason: str = ""  # Пусто, TYPE A, TYPE B, TYPE C
    dominance: int = 0  # Dominance score (0-100)


@dataclass
class Signal:
    """Сигнал для ставки"""
    match_id: str
    match_name: str
    match_url: str
    favorite_side: str  # "P1" or "P2"
    match_odds: float
    set3_odds: float
    sets_score: str  # "2:0" or "1:0"
    current_set_score: str  # "0:0" or "1:0" or "0:1"
    reason_type: str = "A"  # "A", "B", or "C"
    dominance: int = 0  # Dominance score (0-100)
    set2_score_on_trigger: Optional[str] = None  # Для TYPE B: счёт 2-го сета
    set2_lead_margin: Optional[int] = None  # Для TYPE B: преимущество в очках
    margin_total: int = 0  # Суммарная разница очков по завершённым сетам
    trigger_reason: str = ""  # Детальное описание причины
    detected_at: datetime = field(default_factory=datetime.now)


def get_favorite_odds(match_odds: MatchOdds) -> Optional[float]:
    """Возвращает минимальный коэффициент фаворита"""
    if match_odds.p1 is None or match_odds.p2 is None:
        return None
    return min(match_odds.p1, match_odds.p2)


def get_favorite_side(match_odds: MatchOdds) -> Optional[str]:
    """Возвращает сторону фаворита"""
    if match_odds.p1 is None or match_odds.p2 is None:
        return None
    return "P1" if match_odds.p1 < match_odds.p2 else "P2"


def calculate_dominance(match: MatchData, favorite_side: str) -> Tuple[int, Dict[str, int]]:
    """
    Рассчитывает dominance score (0-100) на основе силы фаворита и доминирования.
    Возвращает: (dominance_score, breakdown_dict)
    """
    from app.config import (
        SET2_MIN_LEAD, SET2_MIN_LEADER_POINTS, SET2_MAX_LEADER_POINTS
    )
    
    breakdown = {
        'base_strength': 0,
        'set_control': 0,
        'point_margin': 0,
        'live_momentum': 0
    }
    
    favorite_odds = get_favorite_odds(match.match_odds)
    if favorite_odds is None:
        return 0, breakdown
    
    # 1. BASE_STRENGTH (0-40)
    if favorite_odds <= 1.08:
        breakdown['base_strength'] = 40
    elif favorite_odds <= 1.12:
        breakdown['base_strength'] = 34
    elif favorite_odds <= 1.16:
        breakdown['base_strength'] = 28
    elif favorite_odds <= 1.20:
        breakdown['base_strength'] = 22
    else:
        breakdown['base_strength'] = 0
    
    # 2. SET_CONTROL (0-30)
    sets = match.match_score.sets
    if len(sets) >= 2:
        if favorite_side == "P1":
            is_2_0 = (sets[0].p1 > sets[0].p2 and sets[1].p1 > sets[1].p2)
        else:
            is_2_0 = (sets[0].p2 > sets[0].p1 and sets[1].p2 > sets[1].p1)
        
        if is_2_0:
            breakdown['set_control'] = 30
        elif len(sets) >= 1:
            if favorite_side == "P1":
                is_1_0 = (sets[0].p1 > sets[0].p2)
            else:
                is_1_0 = (sets[0].p2 > sets[0].p1)
            if is_1_0:
                breakdown['set_control'] = 18
    elif len(sets) >= 1:
        if favorite_side == "P1":
            is_1_0 = (sets[0].p1 > sets[0].p2)
        else:
            is_1_0 = (sets[0].p2 > sets[0].p1)
        if is_1_0:
            breakdown['set_control'] = 18
    
    # 3. POINT_MARGIN (0-30)
    margin_total = 0
    for set_score in sets:
        if favorite_side == "P1":
            margin_total += (set_score.p1 - set_score.p2)
        else:
            margin_total += (set_score.p2 - set_score.p1)
    
    if margin_total >= 10:
        breakdown['point_margin'] = 30
    elif margin_total >= 7:
        breakdown['point_margin'] = 24
    elif margin_total >= 4:
        breakdown['point_margin'] = 16
    elif margin_total >= 1:
        breakdown['point_margin'] = 8
    else:
        breakdown['point_margin'] = 0
    
    # 4. LIVE_MOMENTUM (0-20)
    if match.match_score.current_set == 2 and len(sets) >= 1:
        current = match.match_score.current_set_score
        if favorite_side == "P1":
            leader_points = current.p1
            trailer_points = current.p2
        else:
            leader_points = current.p2
            trailer_points = current.p1
        
        lead = leader_points - trailer_points
        if lead >= SET2_MIN_LEAD and SET2_MIN_LEADER_POINTS <= leader_points <= SET2_MAX_LEADER_POINTS:
            breakdown['live_momentum'] = 20
        elif lead == 2:
            breakdown['live_momentum'] = 10
    
    total = sum(breakdown.values())
    dominance_score = min(100, total)
    
    # Добавляем margin_total в breakdown для использования в trigger_reason
    breakdown['margin_total'] = margin_total
    
    return dominance_score, breakdown


def check_signal_conditions(match: MatchData) -> Tuple[bool, Optional[str], Optional[Dict]]:
    """
    Проверяет условия для сигнала с учетом dominance.
    Возвращает: (is_signal, reason_type, signal_info)
    reason_type: "A" (SET3_OVERPRICE_AFTER_2_0), "B" (SET3_OVERPRICE_AFTER_1_0_AND_SET2_LEAD), 
                 или "C" (SET3_SUSPICIOUS_EQUAL_LINE_UNDER_DOMINANCE)
    """
    from app.config import (
        FAV_MATCH_MAX, DOMINANCE_MIN, SET3_HIGH_ODDS, SET3_FAIR_TOO_EQUAL_MIN, 
        SET3_FAIR_TOO_EQUAL_MAX, SET2_MIN_LEAD,
        SET2_MIN_LEADER_POINTS, SET2_MAX_LEADER_POINTS, SET3_EARLY_MAX_POINTS
    )
    
    # 1. Есть явный фаворит по матчу
    favorite_odds = get_favorite_odds(match.match_odds)
    if favorite_odds is None or favorite_odds > FAV_MATCH_MAX:
        return False, None, None
    
    favorite_side = get_favorite_side(match.match_odds)
    if favorite_side is None:
        return False, None, None
    
    # Рассчитываем dominance
    dominance_score, dominance_breakdown = calculate_dominance(match, favorite_side)
    match.dominance = dominance_score
    
    # Проверка dominance порога
    if dominance_score < DOMINANCE_MIN:
        return False, None, None
    
    # Проверка наличия рынка 3-го сета
    set3_odds = match.set3_odds.p1 if favorite_side == "P1" else match.set3_odds.p2
    if set3_odds is None:
        return False, None, None
    
    # Проверяем 3-й сет (должен быть ранним)
    current = match.match_score.current_set_score
    is_set3_early = (
        current.p1 == 0 and current.p2 == 0 or
        current.p1 == 1 and current.p2 == 0 or
        current.p1 == 0 and current.p2 == 1
    )
    
    if not is_set3_early:
        return False, None, None
    
    sets = match.match_score.sets
    margin_total = dominance_breakdown.get('margin_total', 0)
    
    # Проверка TYPE A: 2:0 по сетам + высокий кф (>=1.90)
    if len(sets) >= 2:
        if favorite_side == "P1":
            is_2_0 = (sets[0].p1 > sets[0].p2 and sets[1].p1 > sets[1].p2)
        else:
            is_2_0 = (sets[0].p2 > sets[0].p1 and sets[1].p2 > sets[1].p1)
        
        if is_2_0 and set3_odds >= SET3_HIGH_ODDS:
            signal_info = {
                'reason_type': 'A',
                'dominance': dominance_score,
                'margin_total': margin_total,
                'trigger_reason': f"A:2-0 & dom={dominance_score} & set3_odds>={set3_odds:.2f}"
            }
            return True, "A", signal_info
    
    # Проверка TYPE B: 1:0 по сетам + лидерство во 2-м сете + высокий кф (>=1.90)
    if len(sets) >= 1:
        if favorite_side == "P1":
            is_1_0 = (sets[0].p1 > sets[0].p2)
        else:
            is_1_0 = (sets[0].p2 > sets[0].p1)
        
        if is_1_0 and match.match_score.current_set == 2:
            current = match.match_score.current_set_score
            
            if favorite_side == "P1":
                leader_points = current.p1
                trailer_points = current.p2
            else:
                leader_points = current.p2
                trailer_points = current.p1
            
            lead_margin = leader_points - trailer_points
            
            if (lead_margin >= SET2_MIN_LEAD and
                SET2_MIN_LEADER_POINTS <= leader_points <= SET2_MAX_LEADER_POINTS and
                set3_odds >= SET3_HIGH_ODDS):
                signal_info = {
                    'reason_type': 'B',
                    'dominance': dominance_score,
                    'margin_total': margin_total,
                    'set2_score_on_trigger': f"{current.p1}:{current.p2}",
                    'set2_lead_margin': lead_margin,
                    'trigger_reason': f"B:1-0 & set2 lead>={lead_margin} & dom={dominance_score} & set3_odds>={set3_odds:.2f}"
                }
                return True, "B", signal_info
    
    # Проверка TYPE C: подозрительно равная линия (1.75-2.05) при доминации
    # TYPE C срабатывает если:
    # - (2:0 ИЛИ (1:0 и лидерство во 2-м)) И dominance >= DOMINANCE_MIN
    # - И кф в диапазоне [SET3_FAIR_TOO_EQUAL_MIN, SET3_FAIR_TOO_EQUAL_MAX]
    # - И кф < SET3_HIGH_ODDS (иначе это TYPE A)
    if SET3_FAIR_TOO_EQUAL_MIN <= set3_odds <= SET3_FAIR_TOO_EQUAL_MAX and set3_odds < SET3_HIGH_ODDS:
        is_candidate = False
        set2_lead_margin = None
        set2_score = None
        
        # Проверяем 2:0
        if len(sets) >= 2:
            if favorite_side == "P1":
                is_2_0 = (sets[0].p1 > sets[0].p2 and sets[1].p1 > sets[1].p2)
            else:
                is_2_0 = (sets[0].p2 > sets[0].p1 and sets[1].p2 > sets[1].p1)
            
            if is_2_0:
                is_candidate = True
        
        # Проверяем 1:0 + лидерство во 2-м
        if not is_candidate and len(sets) >= 1 and match.match_score.current_set == 2:
            if favorite_side == "P1":
                is_1_0 = (sets[0].p1 > sets[0].p2)
            else:
                is_1_0 = (sets[0].p2 > sets[0].p1)
            
            if is_1_0:
                current = match.match_score.current_set_score
                if favorite_side == "P1":
                    leader_points = current.p1
                    trailer_points = current.p2
                else:
                    leader_points = current.p2
                    trailer_points = current.p1
                
                lead_margin = leader_points - trailer_points
                
                if (lead_margin >= SET2_MIN_LEAD and
                    SET2_MIN_LEADER_POINTS <= leader_points <= SET2_MAX_LEADER_POINTS):
                    is_candidate = True
                    set2_lead_margin = lead_margin
                    set2_score = f"{current.p1}:{current.p2}"
        
        if is_candidate:
            signal_info = {
                'reason_type': 'C',
                'dominance': dominance_score,
                'margin_total': margin_total,
                'set2_score_on_trigger': set2_score,
                'set2_lead_margin': set2_lead_margin,
                'trigger_reason': f"C:suspicious equal line {set3_odds:.2f} under dom={dominance_score}"
            }
            return True, "C", signal_info
    
    return False, None, None

