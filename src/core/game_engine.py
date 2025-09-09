"""
Game Engine - Main orchestrator for the RPG LLM game system
"""
import os
import glob
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

from .event_handler import EventHandler, GameEvents
from .state_manager import StateManager
from src.entities.characters import NPC, Player
from src.ai_agents.agents import NPCAgent

logger = logging.getLogger(__name__)

class GameEngine:
    """Main game engine that orchestrates all game systems"""
    
    def __init__(self, config_directory: str = "config"):
        self.config_directory = config_directory
        
        # Core systems
        self.event_handler = EventHandler()
        self.state_manager = StateManager(self.event_handler)
        
        # Game entities and AI
        self.npcs: List[NPC] = []
        self.players: List[Player] = []
        self.all_characters: List = []
        self.characters = {}
        self.items = {}
        self.agents: Dict[int, NPCAgent] = {}
        
        # AI system reference (will be set by AI module)
        self.ai_system = None
        
        # Game state
        self.is_running = False
        self.initialization_time = None
        
        logger.info("Game Engine initialized")
        
    def initialize(self) -> bool:
        """Initialize the game engine and all subsystems"""
        try:
            logger.info("Initializing Game Engine...")
            
            # Load game configurations
            self._load_configurations()
            
            # Set up event subscriptions
            self._setup_event_handlers()
            
            # Initialize core systems
            self._initialize_core_systems()
            
            # Load characters and AI agents
            self._load_all_characters()
            self._load_agents()
            
            self.is_running = True
            self.initialization_time = datetime.now()
            
            logger.info("Game Engine initialization completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize Game Engine: {e}")
            return False
            
    def _load_configurations(self) -> None:
        """Load character and item configurations from config directory"""
        # This will be enhanced when we integrate with the entity system
        logger.info(f"Loading configurations from {self.config_directory}")
        
        # For now, just verify the config directories exist
        chars_path = os.path.join(self.config_directory, "characters")
        items_path = os.path.join(self.config_directory, "items")
        
        if not os.path.exists(chars_path):
            raise FileNotFoundError(f"Characters config directory not found: {chars_path}")
            
        if not os.path.exists(items_path):
            raise FileNotFoundError(f"Items config directory not found: {items_path}")
            
        # Count available configs
        char_files = glob.glob(os.path.join(chars_path, "*.json"))
        item_files = glob.glob(os.path.join(items_path, "*.json"))
        
        logger.info(f"Found {len(char_files)} character configs and {len(item_files)} item configs")
        
    def _setup_event_handlers(self) -> None:
        """Set up event handler subscriptions for core systems"""
        # Subscribe to relevant events
        self.event_handler.subscribe(GameEvents.CHARACTER_INTERACTION, self._on_character_interaction)
        self.event_handler.subscribe(GameEvents.TRADE_COMPLETED, self._on_trade_completed)
        self.event_handler.subscribe(GameEvents.TIME_CHANGED, self._on_time_changed)
        
        logger.info("Event handlers configured")
        
    def _initialize_core_systems(self) -> None:
        """Initialize core game systems"""
        # Initialize world systems
        logger.info("Core systems initialized")
        
        # Emit initialization complete event
        self.event_handler.emit("game_initialized", {
            'timestamp': datetime.now(),
            'config_directory': self.config_directory
        })

    def _load_all_characters(self) -> None:
        """Load character configs from files or per-NPC folders into NPC/Player objects"""
        characters_path = os.path.join(self.config_directory, "characters")
        if not os.path.exists(characters_path):
            raise FileNotFoundError(f"Characters directory not found: {characters_path}")

        # Collect JSON config paths from both top-level JSONs and NPC directories
        candidate_paths: List[str] = []

        for entry in os.listdir(characters_path):
            full_path = os.path.join(characters_path, entry)
            if os.path.isdir(full_path):
                # Look for a JSON config inside the directory
                preferred = os.path.join(full_path, f"{entry}.json")
                if os.path.exists(preferred):
                    candidate_paths.append(preferred)
                else:
                    inner_jsons = glob.glob(os.path.join(full_path, "*.json"))
                    if inner_jsons:
                        candidate_paths.append(inner_jsons[0])
                    else:
                        logger.warning(f"No JSON config found in character folder: {entry}")
            elif entry.endswith(".json"):
                candidate_paths.append(full_path)

        for config_path in candidate_paths:
            filename = os.path.basename(config_path)
            try:
                if filename.startswith("NPC_"):
                    npc = NPC(config_path)
                    self.npcs.append(npc)
                    self.all_characters.append(npc)
                    logger.info(f"Loaded NPC: {npc.name} (ID: {npc.id})")
                elif filename.startswith("Player_"):
                    player = Player(config_path)
                    self.players.append(player)
                    self.all_characters.append(player)
                    logger.info(f"Loaded Player: {player.name} (ID: {player.id})")
                else:
                    logger.warning(f"Skipping config with unknown naming pattern: {filename}")
            except Exception as e:
                logger.error(f"Error loading character from {filename}: {e}")

        logger.info(f"Loaded {len(self.npcs)} NPCs and {len(self.players)} Players")
        self.characters = {char.id: char for char in self.all_characters}

    def _load_agents(self) -> None:
        """Create AI agents for loaded NPCs"""
        if not self.players:
            logger.warning("No player found. Cannot create NPC agents.")
            return
        for npc in self.npcs:
            try:
                agent = NPCAgent(npc, self, npc.id)
                self.agents[npc.id] = agent
                # Initialize NPC state
                self.get_npc_state(npc.id)
                logger.info(f"Created AI agent for {npc.name}")
            except Exception as e:
                logger.error(f"Error creating agent for {npc.name}: {e}")
        logger.info(f"Created {len(self.agents)} AI agents")
        
    def update(self, delta_time: float = 1.0) -> None:
        """Update all game systems"""
        if not self.is_running:
            return
            
        try:
            # Update state manager (handles weather, time, NPC states)
            self.state_manager.update(delta_time)
            
            # Update AI system if available
            if self.ai_system:
                self.ai_system.update(delta_time)
                
        except Exception as e:
            logger.error(f"Error during game update: {e}")
            
    def shutdown(self) -> None:
        """Gracefully shutdown the game engine"""
        logger.info("Shutting down Game Engine...")
        
        self.is_running = False
        
        # Clean up AI agents and their resources
        logger.info("Cleaning up AI agents...")
        agents_cleaned = 0
        for agent_id, agent in self.agents.items():
            try:
                if hasattr(agent, 'cleanup'):
                    agent.cleanup()
                    agents_cleaned += 1
            except Exception as e:
                logger.warning(f"Error cleaning up agent {agent_id}: {e}")
        
        logger.info(f"Cleaned up {agents_cleaned} AI agents")
        
        # Clear agent references
        self.agents.clear()
        
        # Emit shutdown event
        self.event_handler.emit("game_shutdown", {
            'timestamp': datetime.now(),
            'uptime': datetime.now() - self.initialization_time if self.initialization_time else None
        })
        
        # Clear event history
        self.event_handler.clear_history()
        
        logger.info("Game Engine shutdown complete")
        
    # Event handlers for core systems
    def _on_character_interaction(self, event) -> None:
        """Handle character interaction events"""
        logger.debug(f"Character interaction: NPC {event.data['npc_id']} with Player {event.data['player_id']}")
        
    def _on_trade_completed(self, event) -> None:
        """Handle trade completion events"""
        logger.info(f"Trade completed between NPC {event.data.get('npc_id')} and Player {event.data.get('player_id')}")
        

    def _on_time_changed(self, event) -> None:
        """Handle time change events"""
        if event.data['new_day'] != event.data['old_day']:
            logger.info(f"New day started: Day {event.data['new_day']}")
        
    # API methods for external systems
    def register_ai_system(self, ai_system) -> None:
        """Register the AI system with the game engine"""
        self.ai_system = ai_system
        logger.info("AI system registered with Game Engine")
        
    # Character and agent accessors (moved from GameSystem)
    def get_npc_by_id(self, npc_id: int) -> Optional[NPC]:
        for npc in self.npcs:
            if npc.id == npc_id:
                return npc
        return None

    def get_player_by_id(self, player_id: int) -> Optional[Player]:
        for player in self.players:
            if player.id == player_id:
                return player
        return None

    def get_npc_by_name(self, name: str) -> Optional[NPC]:
        for npc in self.npcs:
            if npc.name.lower() == name.lower():
                return npc
        return None

    def get_agent_by_npc_id(self, npc_id: int) -> Optional[NPCAgent]:
        return self.agents.get(npc_id)

    def chat_with_npc(self, npc_id: int, player_id: int, message: str) -> str:
        agent = self.get_agent_by_npc_id(npc_id)
        if not agent:
            return "This character is not available for conversation."
        try:
            self.record_interaction(npc_id, player_id)
            response = agent.chat(message)
            return response
        except Exception as e:
            logger.error(f"Error chatting with NPC {npc_id}: {e}")
            return "I'm having trouble responding right now. Please try again."

    def get_world_context(self) -> Dict[str, Any]:
        """Get current world context for external systems"""
        return self.state_manager.get_world_context()
        
    def get_npc_state(self, npc_id: int):
        """Get NPC state for external systems"""
        return self.state_manager.get_npc_state(npc_id)
        
    def update_npc_activity(self, npc_id: int, activity: str, behavior_data: Dict[str, Any] = None) -> None:
        """Update NPC activity from external systems"""
        self.state_manager.update_npc_activity(npc_id, activity, behavior_data)
        
    def record_interaction(self, npc_id: int, player_id: int) -> None:
        """Record interaction from external systems"""
        self.state_manager.record_interaction(npc_id, player_id)
        
    def emit_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """Allow external systems to emit events"""
        self.event_handler.emit(event_type, data)
        
    def get_game_stats(self) -> Dict[str, Any]:
        """Get current game statistics"""
        stats = {
            'engine': {
                'is_running': self.is_running,
                'uptime': str(datetime.now() - self.initialization_time) if self.initialization_time else "Not started",
                'config_directory': self.config_directory
            },
            'state': self.state_manager.get_state_summary(),
            'events': {
                'total_events': len(self.event_handler.event_history),
                'listener_counts': self.event_handler.get_listener_count()
            },
            'characters': {
                'loaded_npcs': len(self.npcs),
                'loaded_players': len(self.players),
                'active_agents': len(self.agents)
            }
        }
        
        return stats
        
    def get_characters_summary(self) -> Dict[str, Any]:
        """Get summary of loaded characters (placeholder for entity integration)"""
        return {
            'loaded_characters': len(self.characters),
            'loaded_items': len(self.items),
            'active_npcs': len(self.state_manager.npc_states),
            'active_players': len(self.state_manager.active_players)
        }
