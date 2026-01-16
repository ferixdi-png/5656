"""Playwright-based scanner with network interception"""

import asyncio
import json
import random
import re
from typing import Dict, Optional, Callable, List
from datetime import datetime
from playwright.async_api import async_playwright, Page, Browser, BrowserContext
import logging

from app.config import (
    LIVE_URL, SCAN_INTERVAL_MIN, SCAN_INTERVAL_MAX,
    MAX_TABS, BROWSER_HEADLESS, BROWSER_TIMEOUT
)
from app.models import MatchData, MatchOdds, MatchScore, SetScore, Signal, check_signal_conditions
from app.storage import Storage
from app.notify import notify_signal

logger = logging.getLogger(__name__)


class BetBoomScanner:
    """Scanner for BetBoom live matches"""
    
    def __init__(self):
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.is_running = False
        self.matches: Dict[str, MatchData] = {}
        self.detected_signals: set[str] = set()  # match_ids
        
        # Callbacks
        self.on_match_update: Optional[Callable[[List[MatchData]], None]] = None
        self.on_signal: Optional[Callable[[Signal], None]] = None
        self.on_error: Optional[Callable[[str], None]] = None
        
        self.storage = Storage()
        self.retry_count = 0
    
    async def start(self):
        """Start scanner"""
        if self.is_running:
            return
        
        try:
            await self._init_browser()
            self.is_running = True
            logger.info("Scanner started")
            
            # Start monitoring loop
            asyncio.create_task(self._monitoring_loop())
            
        except Exception as e:
            logger.error(f"Failed to start scanner: {e}")
            if self.on_error:
                self.on_error(str(e))
            raise
    
    async def stop(self):
        """Stop scanner"""
        self.is_running = False
        if self.browser:
            await self.browser.close()
        logger.info("Scanner stopped")
    
    async def _init_browser(self):
        """Initialize browser and context"""
        playwright = await async_playwright().start()
        
        self.browser = await playwright.chromium.launch(
            headless=BROWSER_HEADLESS,
            args=['--disable-blink-features=AutomationControlled']
        )
        
        self.context = await self.browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080}
        )
        
        self.page = await self.context.new_page()
        
        # Setup response interception
        self.page.on("response", self._handle_response)
        
        # Navigate to live page
        await self.page.goto(LIVE_URL, wait_until="networkidle", timeout=BROWSER_TIMEOUT)
        await asyncio.sleep(2)  # Wait for initial load
    
    async def _handle_response(self, response):
        """Handle network responses to extract match data"""
        try:
            url = response.url
            content_type = response.headers.get("content-type", "")
            
            # Look for API responses
            if "application/json" in content_type or "json" in url.lower():
                try:
                    data = await response.json()
                    await self._parse_api_response(data, url)
                except Exception:
                    pass  # Not JSON or parse error
            
        except Exception as e:
            logger.debug(f"Error handling response: {e}")
    
    async def _parse_api_response(self, data: dict, url: str):
        """Parse API response to extract match data"""
        try:
            # Try different response structures
            matches_data = None
            
            if isinstance(data, dict):
                # Try common keys
                for key in ['data', 'matches', 'events', 'results', 'items']:
                    if key in data and isinstance(data[key], list):
                        matches_data = data[key]
                        break
                
                # If no array found, check if data itself is a list
                if matches_data is None and isinstance(data, list):
                    matches_data = data
            
            if matches_data:
                for match_item in matches_data:
                    await self._parse_match_item(match_item)
            
        except Exception as e:
            logger.debug(f"Error parsing API response: {e}")
    
    async def _parse_match_item(self, item: dict):
        """Parse single match item from API response"""
        try:
            # Extract match ID
            match_id = str(item.get('id') or item.get('match_id') or item.get('event_id', ''))
            if not match_id:
                return
            
            # Extract match name and players
            home_obj = item.get('home', {}) if isinstance(item.get('home'), dict) else {'name': item.get('home', 'Team1')}
            away_obj = item.get('away', {}) if isinstance(item.get('away'), dict) else {'name': item.get('away', 'Team2')}
            
            if isinstance(item.get('home'), str):
                home_obj = {'name': item.get('home')}
            if isinstance(item.get('away'), str):
                away_obj = {'name': item.get('away')}
            
            player1 = home_obj.get('name', 'Unknown')
            player2 = away_obj.get('name', 'Unknown')
            
            match_name = (
                item.get('name') or 
                item.get('match_name') or 
                item.get('title') or
                f"{player1} vs {player2}"
            )
            
            # Extract league
            league = None
            for key in ['league', 'tournament', 'competition', 'category']:
                if key in item:
                    league_obj = item[key]
                    if isinstance(league_obj, dict):
                        league = league_obj.get('name') or league_obj.get('title')
                    else:
                        league = str(league_obj)
                    break
            
            # Extract URL
            match_url = item.get('url') or item.get('link') or f"{LIVE_URL}#{match_id}"
            
            # Extract odds
            odds = item.get('odds') or item.get('markets') or {}
            match_odds = self._extract_match_odds(odds)
            set3_odds = self._extract_set3_odds(odds, item)
            
            # Extract score
            score = item.get('score') or item.get('scores') or {}
            match_score = self._extract_match_score(score)
            
            # Update or create match
            if match_id in self.matches:
                match = self.matches[match_id]
                match.match_name = match_name
                match.match_url = match_url
                match.player1 = player1
                match.player2 = player2
                match.league = league
                match.match_odds = match_odds
                match.set3_odds = set3_odds
                match.match_score = match_score
                match.last_update = datetime.now()
            else:
                match = MatchData(
                    match_id=match_id,
                    match_name=match_name,
                    match_url=match_url,
                    player1=player1,
                    player2=player2,
                    league=league,
                    match_odds=match_odds,
                    set3_odds=set3_odds,
                    match_score=match_score
                )
                self.matches[match_id] = match
            
            # Check for signals
            await self._check_signal(match)
            
        except Exception as e:
            logger.debug(f"Error parsing match item: {e}")
    
    def _extract_match_odds(self, odds_data: dict) -> MatchOdds:
        """Extract match odds from odds data"""
        result = MatchOdds()
        
        # Try different structures
        markets = odds_data.get('markets', []) if isinstance(odds_data, dict) else []
        if not markets:
            markets = odds_data if isinstance(odds_data, list) else []
        
        for market in markets:
            market_name = (market.get('name') or market.get('type') or '').lower()
            if 'исход' in market_name or 'match' in market_name or 'winner' in market_name:
                outcomes = market.get('outcomes') or market.get('selections') or []
                for outcome in outcomes:
                    name = (outcome.get('name') or outcome.get('label') or '').lower()
                    odds_val = outcome.get('odds') or outcome.get('price') or outcome.get('value')
                    
                    if odds_val:
                        try:
                            odds_float = float(odds_val)
                            if '1' in name or 'home' in name or 'п1' in name:
                                result.p1 = odds_float
                            elif '2' in name or 'away' in name or 'п2' in name:
                                result.p2 = odds_float
                        except (ValueError, TypeError):
                            pass
        
        return result
    
    def _extract_set3_odds(self, odds_data: dict, match_item: dict) -> MatchOdds:
        """Extract set 3 odds"""
        result = MatchOdds()
        
        # Try to find set 3 market
        markets = odds_data.get('markets', []) if isinstance(odds_data, dict) else []
        if not markets:
            markets = odds_data if isinstance(odds_data, list) else []
        
        for market in markets:
            market_name = (market.get('name') or market.get('type') or '').lower()
            if ('3' in market_name and 'сет' in market_name) or ('set 3' in market_name):
                outcomes = market.get('outcomes') or market.get('selections') or []
                for outcome in outcomes:
                    name = (outcome.get('name') or outcome.get('label') or '').lower()
                    odds_val = outcome.get('odds') or outcome.get('price') or outcome.get('value')
                    
                    if odds_val:
                        try:
                            odds_float = float(odds_val)
                            if '1' in name or 'home' in name or 'п1' in name:
                                result.p1 = odds_float
                            elif '2' in name or 'away' in name or 'п2' in name:
                                result.p2 = odds_float
                        except (ValueError, TypeError):
                            pass
        
        return result
    
    def _extract_match_score(self, score_data: dict) -> MatchScore:
        """Extract match score from score data"""
        result = MatchScore()
        
        # Try different structures
        sets = score_data.get('sets') or score_data.get('periods') or []
        
        if isinstance(sets, list):
            for set_data in sets:
                if isinstance(set_data, dict):
                    p1 = int(set_data.get('home', set_data.get('p1', set_data.get('score1', 0))))
                    p2 = int(set_data.get('away', set_data.get('p2', set_data.get('score2', 0))))
                    result.sets.append(SetScore(p1=p1, p2=p2))
        
        # Extract current set
        current_set = score_data.get('current_set', score_data.get('current_period', 1))
        result.current_set = int(current_set) if current_set else 1
        
        # Extract current set score
        current_score = score_data.get('current_score') or score_data.get('live_score') or {}
        if isinstance(current_score, dict):
            result.current_set_score = SetScore(
                p1=int(current_score.get('home', current_score.get('p1', current_score.get('score1', 0)))),
                p2=int(current_score.get('away', current_score.get('p2', current_score.get('score2', 0))))
            )
        
        return result
    
    async def _check_signal(self, match: MatchData):
        """Check if match meets signal conditions"""
        # Рассчитываем dominance заранее для обновления match.dominance
        from app.models import get_favorite_side, get_favorite_odds, calculate_dominance
        
        favorite_side = get_favorite_side(match.match_odds)
        if favorite_side:
            dominance_score, _ = calculate_dominance(match, favorite_side)
            match.dominance = dominance_score
        
        is_signal, reason_type, signal_info = check_signal_conditions(match)
        
        if not is_signal:
            # Обновляем статус и reason
            if match.set3_odds.p1 is None and match.set3_odds.p2 is None:
                match.status = "NO_MARKET"
                match.reason = ""
            else:
                # Проверяем кандидата (для открытия деталки)
                from app.config import FAV_MATCH_MAX, DOMINANCE_PRE_FILTER, SET2_MIN_LEAD, SET2_MIN_LEADER_POINTS, SET2_MAX_LEADER_POINTS
                
                favorite_odds = get_favorite_odds(match.match_odds)
                if favorite_odds and favorite_odds <= FAV_MATCH_MAX:
                    # Предварительная проверка dominance
                    if match.dominance >= DOMINANCE_PRE_FILTER:
                        favorite_side = get_favorite_side(match.match_odds)
                        if favorite_side:
                            sets = match.match_score.sets
                            is_2_0 = False
                            is_1_0 = False
                            
                            if len(sets) >= 2:
                                if favorite_side == "P1":
                                    is_2_0 = (sets[0].p1 > sets[0].p2 and sets[1].p1 > sets[1].p2)
                                else:
                                    is_2_0 = (sets[0].p2 > sets[0].p1 and sets[1].p2 > sets[1].p1)
                            
                            if not is_2_0 and len(sets) >= 1:
                                if favorite_side == "P1":
                                    is_1_0 = (sets[0].p1 > sets[0].p2)
                                else:
                                    is_1_0 = (sets[0].p2 > sets[0].p1)
                            
                            if is_2_0 or (is_1_0 and match.match_score.current_set == 2):
                                # Для 1:0 проверяем лидерство во 2-м сете
                                if is_2_0 or (is_1_0 and match.match_score.current_set == 2):
                                    if is_1_0 and match.match_score.current_set == 2:
                                        current = match.match_score.current_set_score
                                        leader_points = current.p1 if favorite_side == "P1" else current.p2
                                        trailer_points = current.p2 if favorite_side == "P1" else current.p1
                                        lead_margin = leader_points - trailer_points
                                        if not (lead_margin >= SET2_MIN_LEAD and
                                                SET2_MIN_LEADER_POINTS <= leader_points <= SET2_MAX_LEADER_POINTS):
                                            match.status = "OK"
                                            match.reason = ""
                                            return
                                    match.status = "CANDIDATE"
                                    match.reason = f"Dom:{match.dominance}"
                                    return
                match.status = "OK"
                match.reason = ""
            return
        
        # Prevent duplicate signals (с учётом типа)
        signal_key = f"{match.match_id}_{reason_type}"
        if signal_key in self.detected_signals:
            return
        
        # Generate signal
        favorite_side = get_favorite_side(match.match_odds)
        match_odds = get_favorite_odds(match.match_odds)
        set3_odds = match.set3_odds.p1 if favorite_side == "P1" else match.set3_odds.p2
        
        # Format sets score
        if len(match.match_score.sets) >= 2:
            sets_str = ":".join([f"{s.p1}-{s.p2}" for s in match.match_score.sets[:2]])
        elif len(match.match_score.sets) >= 1:
            sets_str = f"{match.match_score.sets[0].p1}-{match.match_score.sets[0].p2}"
        else:
            sets_str = "0-0"
        
        current_str = f"{match.match_score.current_set_score.p1}:{match.match_score.current_set_score.p2}"
        
        signal = Signal(
            match_id=match.match_id,
            match_name=match.match_name,
            match_url=match.match_url,
            favorite_side=favorite_side,
            match_odds=match_odds,
            set3_odds=set3_odds,
            sets_score=sets_str,
            current_set_score=current_str,
            reason_type=reason_type,
            dominance=signal_info.get('dominance', match.dominance),
            margin_total=signal_info.get('margin_total', 0),
            set2_score_on_trigger=signal_info.get('set2_score_on_trigger'),
            set2_lead_margin=signal_info.get('set2_lead_margin'),
            trigger_reason=signal_info.get('trigger_reason', '')
        )
        
        # Save and notify
        self.storage.save_signal(signal)
        notify_signal(signal)
        self.detected_signals.add(signal_key)
        
        match.status = "SIGNAL"
        match.reason = f"TYPE {reason_type}"
        
        if self.on_signal:
            self.on_signal(signal)
        
        logger.info(f"Signal TYPE {reason_type} detected (dom={signal.dominance}): {match.match_name} - {signal_info.get('trigger_reason', '')}")
    
    async def _monitoring_loop(self):
        """Main monitoring loop with DOM fallback"""
        while self.is_running:
            try:
                # Try to parse from DOM as fallback
                if self.page:
                    await self._parse_dom_fallback()
                
                # Notify about updates
                if self.on_match_update:
                    matches_list = list(self.matches.values())
                    self.on_match_update(matches_list)
                
                # Random delay
                delay = random.uniform(SCAN_INTERVAL_MIN, SCAN_INTERVAL_MAX)
                await asyncio.sleep(delay)
                
                self.retry_count = 0  # Reset on success
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                self.retry_count += 1
                
                if self.retry_count >= 3:
                    logger.warning("Too many errors, reinitializing browser...")
                    try:
                        await self._init_browser()
                    except Exception as init_error:
                        logger.error(f"Failed to reinitialize: {init_error}")
                        if self.on_error:
                            self.on_error(str(init_error))
                
                await asyncio.sleep(5)
    
    async def _parse_dom_fallback(self):
        """Fallback: parse match data from DOM"""
        try:
            # Refresh page periodically to get latest data
            if self.page:
                # Try to find match containers
                selectors = [
                    '[data-match-id]',
                    '[data-event-id]',
                    '.match-card',
                    '.event-card',
                    '.event-item',
                    '[class*="match"]',
                    '[class*="event"]'
                ]
                
                all_elements = []
                for selector in selectors:
                    try:
                        elements = await self.page.query_selector_all(selector)
                        all_elements.extend(elements[:10])  # Limit per selector
                    except Exception:
                        continue
                
                # Parse each element
                for element in all_elements[:30]:  # Limit total
                    try:
                        match_id = (
                            await element.get_attribute('data-match-id') or
                            await element.get_attribute('data-event-id') or
                            await element.get_attribute('id') or
                            f"dom_{hash(str(element))}"
                        )
                        
                        # Try to extract match name and players
                        name_elem = await element.query_selector('.match-name, .event-name, [class*="name"]')
                        match_name = await name_elem.inner_text() if name_elem else f"Match {match_id[:8]}"
                        
                        # Try to extract players from name (format: "Player1 vs Player2")
                        player1, player2 = "Unknown", "Unknown"
                        if " vs " in match_name or " VS " in match_name:
                            parts = match_name.split(" vs ") if " vs " in match_name else match_name.split(" VS ")
                            if len(parts) >= 2:
                                player1 = parts[0].strip()
                                player2 = parts[1].strip()
                        
                        # Try to extract league
                        league = None
                        league_elem = await element.query_selector('[class*="league"], [class*="tournament"], [class*="competition"]')
                        if league_elem:
                            league = await league_elem.inner_text()
                        
                        # Try to extract odds (look for numbers with decimal point)
                        odds_elems = await element.query_selector_all('[class*="odd"], [class*="coef"], [class*="price"]')
                        match_odds = MatchOdds()
                        
                        if len(odds_elems) >= 2:
                            try:
                                p1_text = await odds_elems[0].inner_text()
                                p2_text = await odds_elems[1].inner_text()
                                match_odds.p1 = float(re.search(r'\d+\.?\d*', p1_text).group())
                                match_odds.p2 = float(re.search(r'\d+\.?\d*', p2_text).group())
                            except Exception:
                                pass
                        
                        # Try to extract score
                        score_elem = await element.query_selector('[class*="score"], [class*="sets"]')
                        match_score = MatchScore()
                        
                        if score_elem:
                            score_text = await score_elem.inner_text()
                            # Try to parse score like "2:0, 3:1" or "2-0"
                            score_parts = re.findall(r'(\d+)[:\-](\d+)', score_text)
                            for p1, p2 in score_parts[:2]:
                                match_score.sets.append(SetScore(p1=int(p1), p2=int(p2)))
                        
                        # Update or create match
                        if match_id in self.matches:
                            match = self.matches[match_id]
                            match.match_name = match_name
                            match.player1 = player1
                            match.player2 = player2
                            match.league = league
                            match.match_odds = match_odds
                            match.match_score = match_score
                            match.last_update = datetime.now()
                        else:
                            match = MatchData(
                                match_id=match_id,
                                match_name=match_name,
                                match_url=LIVE_URL + f"#{match_id}",
                                player1=player1,
                                player2=player2,
                                league=league,
                                match_odds=match_odds,
                                match_score=match_score
                            )
                            self.matches[match_id] = match
                        
                        # Check for signals
                        await self._check_signal(match)
                        
                    except Exception as e:
                        logger.debug(f"Error parsing DOM element: {e}")
                        continue
                    
        except Exception as e:
            logger.debug(f"DOM fallback error: {e}")

