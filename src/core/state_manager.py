"""
State Manager - Manages global game state and world systems
"""
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import logging

from .event_handler import EventHandler, GameEvents, TradeEvent

logger = logging.getLogger(__name__)

# Weather system removed - will be implemented separately per user's design

@dataclass 
class TimeState:
    """Current time state"""
    hour: int = 12           # 0-23
    minute: int = 0          # 0-59
    day: int = 1             # Day counter
    time_scale: float = 1.0  # Time multiplier (1.0 = real time)
    
    def get_time_string(self) -> str:
        """Get formatted time string"""
        return f"Day {self.day}, {self.hour:02d}:{self.minute:02d}"
        
    def is_day_time(self) -> bool:
        """Check if it's day time (6 AM to 6 PM)"""
        return 6 <= self.hour < 18
        
    def get_time_period(self) -> str:
        """Get current time period"""
        if 5 <= self.hour < 12:
            return "morning"
        elif 12 <= self.hour < 17:
            return "afternoon"
        elif 17 <= self.hour < 21:
            return "evening"
        else:
            return "night"

@dataclass
class NPCState:
    """State for individual NPCs"""
    current_mood: float = 0.0      # -1.0 to 1.0
    current_activity: str = "idle"  # idle, patrolling, following, etc.
    last_interaction: Optional[datetime] = None
    interaction_count: int = 0
    behavior_data: Dict[str, Any] = field(default_factory=dict)

class StateManager:
    """Manages global game state and world systems"""
    
    def __init__(self, event_handler: EventHandler):
        self.event_handler = event_handler
        
        # World state
        self.time = TimeState()
        
        # Character states
        self.npc_states: Dict[int, NPCState] = {}
        self.active_players: Dict[int, Dict[str, Any]] = {}
        
        # Game metadata
        self.game_start_time = datetime.now()
        self.last_update = datetime.now()
        
        # Time system settings
        self.time_update_interval = timedelta(seconds=60)      # Update time every minute
        
        logger.info("State Manager initialized")
        
    def update(self, delta_time: float) -> None:
        """Update world systems"""
        current_time = datetime.now()
        
        # Update time system
        self._update_time_system(delta_time)
        
        # Update NPC states
        self._update_npc_states()
        
        self.last_update = current_time
        
    def _update_time_system(self, delta_time: float) -> None:
        """Update game time"""
        # Convert delta_time (seconds) to game minutes
        game_minutes = (delta_time * self.time.time_scale) / 60
        
        old_hour = self.time.hour
        old_day = self.time.day
        
        self.time.minute += int(game_minutes)
        
        # Handle minute overflow
        if self.time.minute >= 60:
            hours_to_add = self.time.minute // 60
            self.time.minute = self.time.minute % 60
            self.time.hour += hours_to_add
            
        # Handle hour overflow
        if self.time.hour >= 24:
            days_to_add = self.time.hour // 24
            self.time.hour = self.time.hour % 24
            self.time.day += days_to_add
            
        # Emit events for significant time changes
        if self.time.hour != old_hour or self.time.day != old_day:
            self.event_handler.emit(GameEvents.TIME_CHANGED, {
                'old_hour': old_hour,
                'new_hour': self.time.hour,
                'old_day': old_day,
                'new_day': self.time.day,
                'time_period': self.time.get_time_period(),
                'is_day_time': self.time.is_day_time()
            })
            
# Weather system methods removed - will be implemented separately
        
    def _update_npc_states(self) -> None:
        """Update NPC states based on world conditions"""
        time_modifier = 0.1 if self.time.is_day_time() else -0.1
        
        for npc_id, npc_state in self.npc_states.items():
            # Apply time-based mood modifiers
            base_mood = npc_state.current_mood
            npc_state.current_mood = max(-1.0, min(1.0, base_mood + time_modifier))
            
    def get_npc_state(self, npc_id: int) -> NPCState:
        """Get or create NPC state"""
        if npc_id not in self.npc_states:
            self.npc_states[npc_id] = NPCState()
        return self.npc_states[npc_id]
        
    def update_npc_activity(self, npc_id: int, activity: str, behavior_data: Dict[str, Any] = None) -> None:
        """Update NPC activity state"""
        npc_state = self.get_npc_state(npc_id)
        old_activity = npc_state.current_activity
        
        npc_state.current_activity = activity
        if behavior_data:
            npc_state.behavior_data.update(behavior_data)
            
        if old_activity != activity:
            self.event_handler.emit(GameEvents.NPC_BEHAVIOR_CHANGED, {
                'npc_id': npc_id,
                'old_activity': old_activity,
                'new_activity': activity,
                'behavior_data': behavior_data
            })
            
    def update_relationship(self, npc_id: int, player_id: int, change: float) -> None:
        """Update relationship between NPC and player"""
        # This will be integrated with character entities later
        self.event_handler.emit(GameEvents.RELATIONSHIP_CHANGED, {
            'npc_id': npc_id,
            'player_id': player_id,
            'change': change
        })
        
    def record_interaction(self, npc_id: int, player_id: int) -> None:
        """Record an interaction between NPC and player"""
        npc_state = self.get_npc_state(npc_id)
        npc_state.last_interaction = datetime.now()
        npc_state.interaction_count += 1
        
        self.event_handler.emit(GameEvents.CHARACTER_INTERACTION, {
            'npc_id': npc_id,
            'player_id': player_id,
            'interaction_count': npc_state.interaction_count,
            'timestamp': npc_state.last_interaction
        })
        
    def process_trade_event(self, trade_event: TradeEvent, game_system) -> str:
        """Process a trade event and return the result"""
        logger.info(f"Processing trade event: {trade_event.trade_type} between NPC {trade_event.npc_id} and Player {trade_event.player_id}")
        
        # Process the trade using the event's built-in logic
        result = trade_event.process(game_system)
        trade_event.processed = True
        
        # Emit trade events based on result
        try:
            import json
            result_data = json.loads(result)
            
            if result_data["status"] == "success":
                self.event_handler.emit(GameEvents.TRADE_COMPLETED, {
                    'npc_id': trade_event.npc_id,
                    'player_id': trade_event.player_id,
                    'trade_type': trade_event.trade_type,
                    'items': result_data["items"],
                    'transaction': result_data["transaction"]
                })
                logger.info(f"Trade completed successfully: {result_data['transaction']} gold, {len(result_data['items'])} item types")
            else:
                self.event_handler.emit(GameEvents.TRADE_FAILED, {
                    'npc_id': trade_event.npc_id,
                    'player_id': trade_event.player_id,
                    'trade_type': trade_event.trade_type,
                    'error': result_data.get("error_message", "Unknown error")
                })
                logger.warning(f"Trade failed: {result_data.get('error_message', 'Unknown error')}")
                
        except Exception as e:
            logger.error(f"Error processing trade event result: {e}")
            self.event_handler.emit(GameEvents.TRADE_FAILED, {
                'npc_id': trade_event.npc_id,
                'player_id': trade_event.player_id,
                'trade_type': trade_event.trade_type,
                'error': f"Processing error: {str(e)}"
            })
        
        return result
        
    def get_world_context(self) -> Dict[str, Any]:
        """Get current world context for AI agents"""
        return {
            'time': {
                'hour': self.time.hour,
                'minute': self.time.minute,
                'day': self.time.day,
                'time_period': self.time.get_time_period(),
                'is_day_time': self.time.is_day_time()
            }
        }
        
    def get_state_summary(self) -> Dict[str, Any]:
        """Get summary of current game state for API"""
        return {
            'time': self.time.get_time_string(),
            'active_npcs': len(self.npc_states),
            'active_players': len(self.active_players),
            'uptime': str(datetime.now() - self.game_start_time)
        }
