import logging
import json
from datetime import datetime
from typing import Optional, Dict, Any

class GameEventLogger:
    """
    Professional logging utility for RPG game events.
    Provides structured logging with consistent format across all game events.
    """
    
    def __init__(self, log_file: str = "game_events.log", log_level: int = logging.INFO):
        """
        Initialize the game event logger.
        
        Args:
            log_file: Path to the log file
            log_level: Logging level (default: INFO)
        """
        # Use only the default/root logger configuration; do not attach custom handlers
        self.logger = logging.getLogger("GameEvents")
        self.logger.setLevel(log_level)
        self.logger.propagate = True
    
    def log_event(self, 
                  event_type: str, 
                  player_id: Optional[int] = None, 
                  npc_id: Optional[int] = None, 
                  effects: Optional[Dict[str, Any]] = None,
                  log_level: int = logging.INFO):
        """
        Log a game event with structured format.
        
        Args:
            event_type: Type of event (trade, relationship_change, etc.)
            player_id: ID of the player involved (if any)
            npc_id: ID of the NPC involved (if any)
            effects: Event-specific data as dictionary
            log_level: Logging level for this event
        """
        # Build the structured message
        message_parts = [f"EVENT: {event_type}"]
        
        if player_id is not None:
            message_parts.append(f"PLAYER_ID: {player_id}")
        
        if npc_id is not None:
            message_parts.append(f"NPC_ID: {npc_id}")
        
        # Convert effects to JSON string or None
        if effects is not None:
            effects_str = json.dumps(effects, separators=(',', ':'))
        else:
            effects_str = "None"
        
        message_parts.append(f"EFFECTS: {effects_str}")
        
        # Join all parts with separator
        message = " | ".join(message_parts)
        
        # Log the message
        self.logger.log(log_level, message)
    
    def log_trade_success(self, 
                         player_id: int, 
                         npc_id: int, 
                         trade_type: str, 
                         items_transferred: list):
        """
        Log a successful trade event.
        
        Args:
            player_id: ID of the player
            npc_id: ID of the NPC
            trade_type: "buy" or "sell" from player's perspective
            items_transferred: List of item transfer details
        """
        effects = {
            "trade_type": trade_type,
            "items_transferred": items_transferred,
            "trade_status": "success"
        }
        
        self.log_event("trade", player_id, npc_id, effects)
    
    def log_trade_failure(self, 
                         player_id: int, 
                         npc_id: int, 
                         trade_type: str, 
                         error_message: str):
        """
        Log a failed trade event.
        
        Args:
            player_id: ID of the player
            npc_id: ID of the NPC
            trade_type: "buy" or "sell" from player's perspective
            error_message: Reason for trade failure
        """
        effects = {
            "trade_type": trade_type,
            "error": error_message,
            "trade_status": "failed"
        }
        
        self.log_event("trade", player_id, npc_id, effects, logging.WARNING)
    
    def log_relationship_change(self, 
                               player_id: int, 
                               npc_id: int, 
                               previous_value: float, 
                               new_value: float, 
                               reason: str):
        """
        Log a relationship change event.
        
        Args:
            player_id: ID of the player
            npc_id: ID of the NPC
            previous_value: Previous relationship value
            new_value: New relationship value
            reason: Reason for the change
        """
        effects = {
            "previous_value": previous_value,
            "new_value": new_value,
            "reason": reason
        }
        
        self.log_event("relationship_change", player_id, npc_id, effects)
    
    def log_shop_inquiry(self, player_id: int, npc_id: int):
        """
        Log a shop inquiry event.
        
        Args:
            player_id: ID of the player
            npc_id: ID of the NPC
        """
        self.log_event("shop_inquiry", player_id, npc_id)
    
    def log_inventory_check(self, character_id: int, character_type: str):
        """
        Log an inventory check event.
        
        Args:
            character_id: ID of the character
            character_type: "player" or "npc"
        """
        if character_type == "player":
            self.log_event("inventory_check", player_id=character_id)
        else:
            self.log_event("inventory_check", npc_id=character_id)


# Global logger instance
game_logger = GameEventLogger()
