"""
Event Handler - Simple event system for game communication
"""
from collections import defaultdict
from typing import Callable, Any, Dict, List, Optional
import asyncio
from dataclasses import dataclass, field
from datetime import datetime
import logging
import json

logger = logging.getLogger(__name__)

@dataclass
class BaseEvent:
    """Base event class for all game events"""
    event_type: str
    timestamp: datetime
    data: Dict[str, Any]
    processed: bool = False
    
    def __post_init__(self):
        if not hasattr(self, 'timestamp') or self.timestamp is None:
            self.timestamp = datetime.now()

@dataclass
class TradeEvent(BaseEvent):
    """Trade event with complex validation and execution logic"""
    npc_id: int = 0
    player_id: int = 0
    trade_type: str = ""  # "buy" or "sell" (from player's perspective)
    trade_info: List[Dict[str, int]] = field(default_factory=list)  # [{"Wood Shield": 1}, {"Health Potion": 2}]
    
    def __post_init__(self):
        super().__post_init__()
        if not self.event_type:
            self.event_type = "trade"
    
    @classmethod
    def create(cls, npc_id: int, player_id: int, trade_type: str, trade_info: List[Dict[str, int]]):
        """
        Create a TradeEvent with proper parameters - cleaner constructor alternative.
        
        Args:
            npc_id: ID of the NPC involved in trade
            player_id: ID of the player involved in trade  
            trade_type: "buy" or "sell" (from player's perspective)
            trade_info: List of item dictionaries [{item_name: quantity}, ...]
        
        Returns:
            TradeEvent: Properly initialized trade event
        """
        return cls(
            event_type="trade",
            timestamp=datetime.now(),
            data={},
            npc_id=npc_id,
            player_id=player_id,
            trade_type=trade_type,
            trade_info=trade_info
        )

    def validate_trade(self, game_system):
        """
        Validate a trade between NPC and player.
        Returns tuple: (is_valid: bool, error_message: str, trade_details: dict)
        """
        try:
            from .game_logger import game_logger
            
            # Get the NPC and player objects
            npc = game_system.get_npc_by_id(self.npc_id)
            player = game_system.get_player_by_id(self.player_id)
            
            if not npc:
                return False, f"NPC with ID {self.npc_id} not found", {}
            
            if not player:
                return False, f"Player with ID {self.player_id} not found", {}
            
            total_cost = 0
            trade_items = []
            items_to_transfer = []  # For actual execution
            
            # Process each item in the trade
            for item_dict in self.trade_info:
                for item_name, quantity in item_dict.items():
                    if quantity <= 0:
                        return False, f"Invalid quantity for {item_name}: {quantity}", {}
                    
                    # Determine which character has the item being traded
                    if self.trade_type == "buy":
                        # Player buying from NPC - check NPC's inventory for item and price
                        source_item = npc.find_item_by_name(item_name)
                        if not source_item:
                            return False, f"The merchant doesn't have {item_name} available", {}
                        
                        # Check if NPC has enough quantity
                        if source_item.quantity < quantity:
                            return False, f"The merchant only has {source_item.quantity} {item_name}(s), but you want {quantity}", {}
                        
                        item_cost = source_item.price * quantity
                        total_cost += item_cost
                        trade_items.append({item_name: quantity})
                        items_to_transfer.append({
                            "item": source_item,
                            "quantity": quantity,
                            "from": "npc",
                            "to": "player"
                        })
                        
                    else:  # trade_type == "sell"
                        # Player selling to NPC - check player's inventory for item
                        source_item = player.find_item_by_name(item_name)
                        if not source_item:
                            return False, f"The player don't have {item_name} to sell", {}
                        
                        # Check if player has enough quantity
                        if source_item.quantity < quantity:
                            return False, f"The player only have {source_item.quantity} {item_name}(s), but trying to sell {quantity}", {}
                        
                        item_cost = source_item.price * quantity
                        total_cost += item_cost
                        trade_items.append({item_name: quantity})
                        items_to_transfer.append({
                            "item": source_item,
                            "quantity": quantity,
                            "from": "player",
                            "to": "npc"
                        })
            
            # Check gold availability
            if self.trade_type == "buy":
                # Player needs to have enough gold to buy
                player_gold_item = player.find_item_by_name("Gold Coin")
                player_gold = player_gold_item.quantity if player_gold_item else 0
                if player_gold < total_cost:
                    return False, f"The player has insufficient funds to purchase your items", {}
            else:  # trade_type == "sell"
                # NPC needs to have enough gold to buy from player
                npc_gold_item = npc.find_item_by_name("Gold Coin")
                npc_gold = npc_gold_item.quantity if npc_gold_item else 0
                if npc_gold < total_cost:
                    return False, "You have insufficient funds to purchase the player's items", {}
            
            # If we reach here, the trade is valid
            trade_details = {
                "npc": npc,
                "player": player,
                "total_cost": total_cost,
                "trade_items": trade_items,
                "items_to_transfer": items_to_transfer
            }
            return True, "", trade_details
            
        except Exception as e:
            return False, f"Trade validation error: {str(e)}", {}

    def execute_trade(self, trade_details):
        """
        Execute the actual trade by moving items and gold between inventories.
        Args:
            trade_details: Dict containing validated trade information
        Returns:
            tuple: (success: bool, items_transferred: list) for logging purposes
        """
        try:
            from .game_logger import game_logger
            
            npc = trade_details["npc"]
            player = trade_details["player"]
            total_cost = trade_details["total_cost"]
            items_to_transfer = trade_details["items_to_transfer"]
            
            # Track all items transferred for logging (including gold)
            logged_transfers = []
            
            # Transfer items
            for transfer in items_to_transfer:
                item = transfer["item"]
                quantity = transfer["quantity"]
                from_char = npc if transfer["from"] == "npc" else player
                to_char = player if transfer["to"] == "player" else npc
                
                # Remove from source inventory (silent during trade operations)
                if not from_char.remove_item(item, quantity, silent=True):
                    game_logger.log_trade_failure(
                        self.player_id, 
                        self.npc_id, 
                        self.trade_type, 
                        f"Failed to remove {quantity} {item.name} from {transfer['from']}"
                    )
                    return False, []
                
                # Add to destination inventory (silent during trade operations)
                to_char.add_item(item, quantity, silent=True)
                
                # Add to logged transfers
                logged_transfers.append({
                    "id": item.id,
                    "name": item.name,
                    "quantity": quantity
                })
            
            # Handle gold transfer
            if total_cost > 0:
                if self.trade_type == "buy":
                    # Player pays NPC
                    player_gold = player.find_item_by_name("Gold Coin")
                    npc_gold = npc.find_item_by_name("Gold Coin")
                    
                    if player_gold and player.remove_item(player_gold, total_cost, silent=True):
                        if npc_gold:
                            npc.add_item(npc_gold, total_cost, silent=True)
                        else:
                            # NPC doesn't have gold coins, create from player's gold
                            npc.add_item(player_gold, total_cost, silent=True)
                        
                        # Log gold transfer
                        logged_transfers.append({
                            "id": player_gold.id,
                            "name": "Gold Coin",
                            "quantity": total_cost
                        })
                    else:
                        game_logger.log_trade_failure(
                            self.player_id, 
                            self.npc_id, 
                            self.trade_type, 
                            f"Failed to transfer {total_cost} gold from player to NPC"
                        )
                        return False, []
                        
                else:  # trade_type == "sell"
                    # NPC pays player
                    npc_gold = npc.find_item_by_name("Gold Coin")
                    player_gold = player.find_item_by_name("Gold Coin")
                    
                    if npc_gold and npc.remove_item(npc_gold, total_cost, silent=True):
                        if player_gold:
                            player.add_item(player_gold, total_cost, silent=True)
                        else:
                            # Player doesn't have gold coins, create from NPC's gold
                            player.add_item(npc_gold, total_cost, silent=True)
                        
                        # Log gold transfer
                        logged_transfers.append({
                            "id": npc_gold.id,
                            "name": "Gold Coin",
                            "quantity": total_cost
                        })
                    else:
                        game_logger.log_trade_failure(
                            self.player_id, 
                            self.npc_id, 
                            self.trade_type, 
                            f"Failed to transfer {total_cost} gold from NPC to player"
                        )
                        return False, []
            
            return True, logged_transfers
            
        except Exception as e:
            from .game_logger import game_logger
            game_logger.log_trade_failure(
                self.player_id, 
                self.npc_id, 
                self.trade_type, 
                f"Trade execution error: {str(e)}"
            )
            return False, []

    def process(self, game_system):
        """
        Main process method: validate first, then execute if valid.
        Returns JSON string with trade results.
        """
        from .game_logger import game_logger
        
        # Step 1: Validate the trade
        is_valid, error_message, trade_details = self.validate_trade(game_system)
        
        if not is_valid:
            # Log validation failure
            game_logger.log_trade_failure(
                self.player_id, 
                self.npc_id, 
                self.trade_type, 
                error_message
            )
            
            return json.dumps({
                "status": "failed",
                "items": [],
                "transaction": 0,
                "error_message": error_message
            })
        
        # Step 2: Execute the trade if validation passed
        success, items_transferred = self.execute_trade(trade_details)
        
        if success:
            # Log successful trade
            game_logger.log_trade_success(
                self.player_id,
                self.npc_id,
                self.trade_type,
                items_transferred
            )
            
            return json.dumps({
                "status": "success",
                "items": trade_details["trade_items"],
                "transaction": trade_details["total_cost"]
            })
        else:
            # Execution failure (already logged in execute_trade)
            return json.dumps({
                "status": "failed",
                "items": [],
                "transaction": 0,
                "error_message": "Trade execution failed"
            })

class EventHandler:
    """Simple event system for decoupled communication between game systems"""
    
    def __init__(self):
        self.listeners: Dict[str, List[Callable]] = defaultdict(list)
        self.async_listeners: Dict[str, List[Callable]] = defaultdict(list)
        self.event_history: List[BaseEvent] = []
        self.max_history = 1000  # Keep last 1000 events for debugging
        
    def subscribe(self, event_type: str, handler: Callable) -> None:
        """Subscribe to an event type with a synchronous handler"""
        self.listeners[event_type].append(handler)
        logger.debug(f"Subscribed handler {handler.__name__} to event type: {event_type}")
        
    def subscribe_async(self, event_type: str, handler: Callable) -> None:
        """Subscribe to an event type with an asynchronous handler"""
        self.async_listeners[event_type].append(handler)
        logger.debug(f"Subscribed async handler {handler.__name__} to event type: {event_type}")
        
    def unsubscribe(self, event_type: str, handler: Callable) -> None:
        """Unsubscribe a handler from an event type"""
        if handler in self.listeners[event_type]:
            self.listeners[event_type].remove(handler)
            logger.debug(f"Unsubscribed handler {handler.__name__} from event type: {event_type}")
            
    def emit(self, event_type: str, data: Dict[str, Any] = None) -> None:
        """Emit an event synchronously"""
        if data is None:
            data = {}
            
        event = BaseEvent(event_type=event_type, timestamp=datetime.now(), data=data)
        
        # Store in history
        self._store_event(event)
        
        # Call synchronous listeners
        for handler in self.listeners[event_type]:
            try:
                handler(event)
            except Exception as e:
                logger.error(f"Error in event handler {handler.__name__} for event {event_type}: {e}")
                
    async def emit_async(self, event_type: str, data: Dict[str, Any] = None) -> None:
        """Emit an event asynchronously"""
        if data is None:
            data = {}
            
        event = BaseEvent(event_type=event_type, timestamp=datetime.now(), data=data)
        
        # Store in history
        self._store_event(event)
        
        # Call synchronous listeners first
        for handler in self.listeners[event_type]:
            try:
                handler(event)
            except Exception as e:
                logger.error(f"Error in sync event handler {handler.__name__} for event {event_type}: {e}")
        
        # Call async listeners
        tasks = []
        for handler in self.async_listeners[event_type]:
            try:
                task = asyncio.create_task(handler(event))
                tasks.append(task)
            except Exception as e:
                logger.error(f"Error creating task for async handler {handler.__name__} for event {event_type}: {e}")
                
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
            
    def _store_event(self, event: BaseEvent) -> None:
        """Store event in history with size limit"""
        self.event_history.append(event)
        if len(self.event_history) > self.max_history:
            self.event_history.pop(0)
            
    def get_event_history(self, event_type: str = None, limit: int = 100) -> List[BaseEvent]:
        """Get event history, optionally filtered by event type"""
        if event_type:
            filtered_events = [e for e in self.event_history if e.event_type == event_type]
            return filtered_events[-limit:]
        return self.event_history[-limit:]
        
    def clear_history(self) -> None:
        """Clear event history"""
        self.event_history.clear()
        logger.info("Event history cleared")
        
    def get_listener_count(self, event_type: str = None) -> Dict[str, int]:
        """Get count of listeners for debugging"""
        if event_type:
            return {
                event_type: {
                    'sync': len(self.listeners[event_type]),
                    'async': len(self.async_listeners[event_type])
                }
            }
        
        counts = {}
        all_event_types = set(self.listeners.keys()) | set(self.async_listeners.keys())
        for et in all_event_types:
            counts[et] = {
                'sync': len(self.listeners[et]),
                'async': len(self.async_listeners[et])
            }
        return counts

# Common game events
class GameEvents:
    """Common event type constants"""
    
    # Character events
    CHARACTER_MOVED = "character_moved"
    CHARACTER_INTERACTION = "character_interaction"
    RELATIONSHIP_CHANGED = "relationship_changed"
    
    # Trade events
    TRADE_INITIATED = "trade_initiated"
    TRADE_COMPLETED = "trade_completed"
    TRADE_FAILED = "trade_failed"
    
    # World events
    TIME_CHANGED = "time_changed"
    
    # AI events
    CONVERSATION_STARTED = "conversation_started"
    CONVERSATION_ENDED = "conversation_ended"
    NPC_BEHAVIOR_CHANGED = "npc_behavior_changed"
