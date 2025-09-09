"""
AI Agent Tools - Simple moved implementation 
"""
from langchain_core.tools import tool
from src.entities.characters import NPC, Player
from typing import List, Dict, Callable
from src.core.event_handler import TradeEvent
from datetime import datetime, date, timedelta
import re
import logging

logger = logging.getLogger(__name__)

def create_npc_tools(npc: NPC, engine) -> List:
    """
    Factory function that creates character-specific tools based on their configuration.
    Only returns tools that are specified in the character's ai_agent_config["tools"] list.
    """
    
    # Define all possible tools as a registry
    def _get_tool_registry(npc: NPC, engine) -> Dict[str, Callable]:
        """
        Registry of all available tools. Each character will only get 
        the tools specified in their configuration.
        """
        
        @tool
        def check_relationship():
            '''Check the relationship between you and the player.'''
            relationship = npc.attributes["relationship"]
            if relationship <= 0.3 and relationship > -0.3:
                return "Neutral(stranger)"
            elif relationship <= 0.8 and relationship > 0.3:
                return "Friendly(acquaintance)"
            elif relationship >= 0.8:
                return "Bestie!"
            elif relationship <= -0.3 and relationship > -0.8:
                return "Not Good(troublesome)"
            elif relationship <= -0.8:
                return "Enemy!"

        @tool
        def check_shop_shelf():
            '''Check goods available in your shop if the player asks.'''
            # Filter inventory for only tradeable items, excluding currency (Gold Coins)
            tradeable_items = [item for item in npc.inventory 
                             if item.tradable and item.quantity > 0 and item.name != "Gold Coin"]
            
            if not tradeable_items:
                return "I'm sorry, but I don't have any items for sale right now."
        
            shop_display = []
            for item in tradeable_items:
                shop_display.append(f"{item.name}")
                shop_display.append(f"Price: {item.price} gold coins")
                shop_display.append(f"Quantity: {item.quantity}")
                shop_display.append(f"Description: {item.description}")
                
                # Add effect information if it exists and is meaningful
                if item.effect and any(v != 0 for v in item.effect.values() if v != "None"):
                    effects = []
                    for effect_type, value in item.effect.items():
                        if effect_type != "None" and value != 0:
                            effects.append(f"{effect_type}: +{value}")
                    if effects:
                        shop_display.append(f"Effects: {', '.join(effects)}")
                
                shop_display.append("")  # Empty line between items
            return "\n".join(shop_display)

        @tool
        def make_trade(trade_type: str, trade_info: List[Dict[str, int]]):
            '''
            Validate a trade with the player.
            Args:
                trade_type: "buy" or "sell" (from the player's perspective)
                trade_info: A list of dictionaries where each item name is the key and quantity is the value. Format: [{"item1_name": quantity}, {"item2_name": quantity}...]
            Returns:
                JSON with trade validation results
            '''
            # Get the first player (for debugging/simple setup)
            player_id = engine.players[0].id
            
            # Create trade event and process it (using keyword arguments to avoid dataclass constructor confusion)
            trade_event = TradeEvent(
                event_type="trade",
                timestamp=datetime.now(),
                data={},
                npc_id=npc.id,
                player_id=player_id,
                trade_type=trade_type,
                trade_info=trade_info
            )
            # Alternative cleaner syntax (both work the same):
            # trade_event = TradeEvent.create(npc.id, player_id, trade_type, trade_info)
            return engine.state_manager.process_trade_event(trade_event, engine)

        @tool
        def check_inventory():
            '''Check your own inventory if necessary.'''
            return npc.show_inventory()

        @tool
        def memory_recall(time: str, query: str):
            '''
            Recall past memories and conversations with the player from a specified time period.
            Args:
                time: Time period to search in format xd/xw/xm/xy (x=number, d=days, w=weeks, m=months, y=years). 
                      Examples: "3d" (retrieve memories in 3 days), "2w" (retrieve memories in 2 weeks), "1m" (retrieve memories 1 month), "1y" (retrieve memories 1 year)
                query: What you want to recall. Like: "What is the name of the player?" "What happened last night?"
            Returns:
                String containing relevant memories with timestamps and content
            '''
            def parse_time_period(time_str: str):
                """Parse time string like '3d', '2w', '1m', '1y' into start_date"""
                match = re.match(r'^(\d+)([dwmy])$', time_str.lower())
                if not match:
                    raise ValueError(f"Invalid time format: {time_str}. Use format like '3d', '2w', '1m', '1y'")
                
                number, unit = match.groups()
                number = int(number)
                today = date.today()
                
                if unit == 'd':  # days
                    start_date = today - timedelta(days=number)
                elif unit == 'w':  # weeks
                    start_date = today - timedelta(weeks=number)
                elif unit == 'm':  # months (approximate as 30 days)
                    start_date = today - timedelta(days=number * 30)
                elif unit == 'y':  # years (approximate as 365 days)
                    start_date = today - timedelta(days=number * 365)
                else:
                    raise ValueError(f"Unknown time unit: {unit}")
                
                return start_date

            try:
                # Get the NPC agent to access memory
                agent = engine.get_agent_by_npc_id(npc.id)
                if not agent or not hasattr(agent, 'long_term_memory'):
                    return "I don't have access to my memory system right now."
                
                # Parse the time period
                start_date = parse_time_period(time)
                end_date = date.today()
                
                # Get the current player ID
                player_id = engine.players[0].id if engine.players else None
                
                # Check if there are ANY memories at all (use concise debug logging)
                try:
                    all_memories = agent.long_term_memory.collection.get()
                    total_memories = len(all_memories['documents']) if all_memories['documents'] else 0
                    if logger.isEnabledFor(logging.DEBUG):
                        logger.debug(f"NPC {npc.id} memory collection: total={total_memories}")
                    
                    # If no memories exist at all
                    if total_memories == 0:
                        return f"I don't have any stored memories yet. This might be our first conversation!"
                        
                    # Query memories within range
                    results = agent.long_term_memory.query_memory(
                        query=query,
                        player_id=player_id,
                        start_date=start_date,
                        end_date=end_date,
                        n_results=5
                    )
                    if logger.isEnabledFor(logging.DEBUG):
                        logger.debug(
                            f"Memory query NPC={npc.id} player={player_id} range={start_date}->{end_date} docs={len(results['documents']) if results.get('documents') else 0}"
                        )
                    
                    # Format results to return only time and content
                    if not results['documents'] or len(results['documents']) == 0:
                        # Try a broader search without date filters as fallback
                        fallback_results = agent.long_term_memory.query_memory(
                            query=query,
                            player_id=player_id,
                            n_results=3
                        )
                        if logger.isEnabledFor(logging.DEBUG):
                            logger.debug(
                                f"Fallback memory query NPC={npc.id} docs={len(fallback_results['documents']) if fallback_results.get('documents') else 0}"
                            )
                        
                        if fallback_results['documents'] and len(fallback_results['documents']) > 0:
                            formatted_memories = []
                            for i, (doc, metadata) in enumerate(zip(fallback_results['documents'], fallback_results['metadatas'])):
                                # Handle metadata safely - it might be None, a dict, a list containing a dict, or other format
                                try:
                                    if isinstance(metadata, dict):
                                        memory_date = metadata.get('timestamp', 'unknown date')
                                    elif isinstance(metadata, list) and len(metadata) > 0 and isinstance(metadata[0], dict):
                                        # Handle case where metadata is a list containing a dictionary
                                        memory_date = metadata[0].get('timestamp', 'unknown date')
                                        logger.debug(f"Fallback - Extracted timestamp from list metadata for NPC {npc.id}, memory {i}: {memory_date}")
                                    elif metadata is None:
                                        memory_date = 'unknown date'
                                    else:
                                        # Log unexpected metadata type for debugging
                                        logger.warning(f"Fallback - Unexpected metadata type for NPC {npc.id}, memory {i}: {type(metadata)} - {metadata}")
                                        memory_date = 'unknown date'
                                except Exception as meta_error:
                                    logger.error(f"Fallback - Error processing metadata for NPC {npc.id}, memory {i}: {meta_error}")
                                    memory_date = 'unknown date'
                                
                                # Clean document content if it's wrapped in quotes or brackets
                                clean_doc = doc
                                if isinstance(doc, str):
                                    # Remove outer quotes and brackets if present
                                    clean_doc = doc.strip()
                                    if clean_doc.startswith('["') and clean_doc.endswith('"]'):
                                        # Remove the outer brackets and quotes
                                        clean_doc = clean_doc[2:-2]
                                    elif clean_doc.startswith('"') and clean_doc.endswith('"'):
                                        # Remove outer quotes
                                        clean_doc = clean_doc[1:-1]
                                
                                formatted_memories.append(f"[{memory_date}] {clean_doc}")
                            
                            return formatted_memories
                        else:
                            return f"I don't recall anything about '{query}' from the past {time}."
                    
                    formatted_memories = []
                    for i, (doc, metadata) in enumerate(zip(results['documents'], results['metadatas'])):
                        # Handle metadata safely - it might be None, a dict, a list containing a dict, or other format
                        try:
                            if isinstance(metadata, dict):
                                memory_date = metadata.get('timestamp', 'unknown date')
                            elif isinstance(metadata, list) and len(metadata) > 0 and isinstance(metadata[0], dict):
                                # Handle case where metadata is a list containing a dictionary
                                memory_date = metadata[0].get('timestamp', 'unknown date')
                                logger.debug(f"Extracted timestamp from list metadata for NPC {npc.id}, memory {i}: {memory_date}")
                            elif metadata is None:
                                memory_date = 'unknown date'
                            else:
                                # Log unexpected metadata type for debugging
                                logger.warning(f"Unexpected metadata type for NPC {npc.id}, memory {i}: {type(metadata)} - {metadata}")
                                memory_date = 'unknown date'
                        except Exception as meta_error:
                            logger.error(f"Error processing metadata for NPC {npc.id}, memory {i}: {meta_error}")
                            memory_date = 'unknown date'
                        
                        # Clean document content if it's wrapped in quotes or brackets
                        clean_doc = doc
                        if isinstance(doc, str):
                            # Remove outer quotes and brackets if present
                            clean_doc = doc.strip()
                            if clean_doc.startswith('["') and clean_doc.endswith('"]'):
                                # Remove the outer brackets and quotes
                                clean_doc = clean_doc[2:-2]
                            elif clean_doc.startswith('"') and clean_doc.endswith('"'):
                                # Remove outer quotes
                                clean_doc = clean_doc[1:-1]
                        
                        formatted_memories.append(f"[{memory_date}] {clean_doc}")
                    
                    if formatted_memories:
                        return formatted_memories
                    else:
                        return f"I don't have any clear memories about '{query}' from the past {time}."
                        
                except Exception as memory_error:
                    return f"Error accessing memories: {str(memory_error)}"
                    
            except ValueError as e:
                return f"Wrong time format. {str(e)}"
            except Exception as e:
                return f"Error: {str(e)}"
        
        # Return the registry mapping tool names to tool functions
        return {
            "check_relationship": check_relationship,
            "check_shop_shelf": check_shop_shelf,
            "check_inventory": check_inventory,
            "make_trade": make_trade,
            "memory_recall": memory_recall,
        }
    
    tool_registry = _get_tool_registry(npc, engine)
    npc_tool_names = npc.ai_agent_config.get("tools", [])
    npc_agent_tools = []
    for tool_name in npc_tool_names:
        if tool_name in tool_registry:
            npc_agent_tools.append(tool_registry[tool_name])
        else:
            logger.warning(f"Tool '{tool_name}' not found in registry for NPC {npc.name}")
    
    return npc_agent_tools