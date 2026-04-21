from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
from datetime import datetime, date
from typing import List, Dict, Any
import chromadb
import os
import logging
import time
import json

logger = logging.getLogger(__name__)

class NPCMemory:
    def __init__(self, npc_config_dir: str, npc_id: int):
        """
        Initialize NPCMemory with path in the NPC's config directory.
        
        Args:
            npc_config_dir: Path to the NPC's configuration directory (e.g., config/characters/NPC_101/)
            npc_id: ID of the NPC
        """
        self.npc_id = npc_id
        self.npc_config_dir = npc_config_dir
        
        # Create memory subdirectory in the NPC's config folder
        self.memory_dir = os.path.join(npc_config_dir, "memory")
        os.makedirs(self.memory_dir, exist_ok=True)
        
        # Initialize ChromaDB in the memory directory
        self.db_path = self.memory_dir
        self.chroma_client = chromadb.PersistentClient(path=self.db_path)
        self.embedding_function = SentenceTransformerEmbeddingFunction(model_name="google/embeddinggemma-300m")
        
        # Get or create collection for this NPC
        try:
            self.collection = self.chroma_client.get_collection(
                name=f"npc_{npc_id}",
                embedding_function=self.embedding_function
            )
            logger.info(f"Loaded existing memory collection for NPC {npc_id}")
        except Exception:
            # Collection doesn't exist, create it
            self.collection = self.chroma_client.create_collection(
                name=f"npc_{npc_id}",
                embedding_function=self.embedding_function,
                metadata={
                    "description": f"Memory for NPC {npc_id}",
                    "created_at": datetime.now().isoformat(),
                },
                configuration={
                    "hnsw": {
                        "space": "cosine",
                    }
                }
            )
            logger.info(f"Created new memory collection for NPC {npc_id}")

    def close(self):
        """
        Properly close ChromaDB client and clean up resources.
        Should be called when the NPCMemory instance is no longer needed.
        """
        try:
            if hasattr(self, 'chroma_client') and self.chroma_client:
                # ChromaDB doesn't have an explicit close method, but we can reset the client
                self.chroma_client.reset()
                logger.info(f"Closed ChromaDB client for NPC {self.npc_id}")
        except Exception as e:
            logger.warning(f"Error closing ChromaDB client for NPC {self.npc_id}: {e}")
        finally:
            # Clear references to help with garbage collection
            self.chroma_client = None
            self.collection = None
            self.embedding_function = None

    def __del__(self):
        """Destructor to ensure resources are cleaned up"""
        try:
            self.close()
        except Exception:
            pass  # Ignore errors in destructor

    def _generate_memory_id(self, player_id: int, memory_date: date) -> str:
        """
        Generate a unique memory ID in format YYYYMMDD_XX where XX is the sequence number.
        
        Args:
            player_id: ID of the player related to this memory
            memory_date: Date when the memory was created
            
        Returns:
            str: Memory ID in format YYYYMMDD_XX
        """
        date_str = memory_date.strftime("%Y%m%d")
        
        # Query existing memories for this date to determine sequence number
        try:
            # Get all existing memories for this date
            existing_memories = self.collection.get(
                where={
                    "$and": [
                        {"timestamp": {"$eq": memory_date.isoformat()}},
                        {"player_id": {"$eq": player_id}}
                    ]
                }
            )
            
            # Find the highest sequence number for this date
            max_sequence = 0
            for memory_id in existing_memories['ids']:
                if memory_id.startswith(f"{date_str}_"):
                    try:
                        sequence = int(memory_id.split('_')[1])
                        max_sequence = max(max_sequence, sequence)
                    except (IndexError, ValueError):
                        continue
            
            # Generate next sequence number
            next_sequence = max_sequence + 1
            return f"{date_str}_{next_sequence:02d}"
            
        except Exception as e:
            logger.warning(f"Error checking existing memories for sequence: {e}")
            # Fallback to sequence 01 if there's an error
            return f"{date_str}_01"

    def add_memory(self, summary: str, player_id: int, memory_date: date = None) -> str:
        """
        Add a new memory to the collection.
        
        Args:
            summary: The summarized conversation content
            player_id: ID of the player related to this memory
            memory_date: Date when the memory was created (defaults to today)
            
        Returns:
            str: The generated memory ID
        """
        if memory_date is None:
            memory_date = date.today()
        
        # Generate unique memory ID
        memory_id = self._generate_memory_id(player_id, memory_date)
        
        # Prepare metadata with both string date and numeric timestamp for queries
        # Convert date to timestamp (midnight of that day)
        timestamp = time.mktime(memory_date.timetuple())
        
        metadata = {
            "player_id": player_id,
            "timestamp": memory_date.isoformat(),  # String date for display
            "timestamp_numeric": timestamp  # Numeric timestamp for queries
        }
        
        try:
            # Add memory to collection
            self.collection.add(
                ids=[memory_id],
                documents=[summary],
                metadatas=[metadata]
            )
            
            logger.info(f"Added memory {memory_id} for NPC {self.npc_id} and player {player_id}")
            return memory_id
            
        except Exception as e:
            logger.error(f"Error adding memory for NPC {self.npc_id}: {e}")
            raise
        
    def query_memory(self, query: str, player_id: int = None, start_date: date = None, 
                    end_date: date = None, n_results: int = 5):
        """
        Query memories with optional filtering.
        
        Args:
            query: Query text for semantic search
            player_id: Filter by specific player (optional)
            start_date: Filter memories from this date onward (optional)
            end_date: Filter memories up to this date (optional)
            n_results: Maximum number of results to return
            
        Returns:
            Dict: Query results from ChromaDB
        """
        # Build where clause for filtering
        where_conditions = []
        
        if player_id is not None:
            where_conditions.append({"player_id": {"$eq": player_id}})
            
        if start_date is not None:
            start_timestamp = time.mktime(start_date.timetuple())
            where_conditions.append({"timestamp_numeric": {"$gte": start_timestamp}})
            
        if end_date is not None:
            # End of day - add 24 hours - 1 second to include the entire end date
            end_timestamp = time.mktime(end_date.timetuple()) + (24 * 60 * 60 - 1)
            where_conditions.append({"timestamp_numeric": {"$lte": end_timestamp}})
        
        # Construct where clause
        where_clause = None
        if where_conditions:
            if len(where_conditions) == 1:
                where_clause = where_conditions[0]
            else:
                where_clause = {"$and": where_conditions}
        
        try:
            return self.collection.query(
                query_texts=[query],
                where=where_clause,
                n_results=n_results
            )
        except Exception as e:
            # If query with date filtering fails (possibly due to old memories without timestamp_numeric),
            # retry without date filtering
            if where_clause and any("timestamp_numeric" in str(condition) for condition in where_conditions):
                logger.warning(f"Date filtering failed for NPC {self.npc_id}, retrying without date filter: {e}")
                try:
                    # Build where clause with only player_id filter
                    fallback_where = None
                    if player_id is not None:
                        fallback_where = {"player_id": {"$eq": player_id}}
                    
                    return self.collection.query(
                        query_texts=[query],
                        where=fallback_where,
                        n_results=n_results
                    )
                except Exception as fallback_error:
                    logger.error(f"Fallback query also failed for NPC {self.npc_id}: {fallback_error}")
                    return {"ids": [], "documents": [], "metadatas": []}
            else:
                logger.error(f"Error querying memory for NPC {self.npc_id}: {e}")
                return {"ids": [], "documents": [], "metadatas": []}

class GraphMemory:
    """
    A lightweight Knowledge Graph implementation for NPC memory.
    Stores data in a local JSON file with Nodes and Edges.
    """
    def __init__(self, npc_config_dir: str, npc_id: int, llm=None):
        # llm argument is kept for backward compatibility but not used, 
        # since extraction happens in the Agent now.
        self.npc_id = npc_id
        self.config_dir = npc_config_dir
        
        # Create memory directory
        self.memory_dir = os.path.join(npc_config_dir, "memory_graph")
        os.makedirs(self.memory_dir, exist_ok=True)
        
        self.graph_file = os.path.join(self.memory_dir, "knowledge_graph.json")
        self.graph_data = self._load_graph()

    def _load_graph(self) -> Dict[str, List]:
        """Load the graph from JSON or initialize empty structure."""
        if os.path.exists(self.graph_file):
            try:
                with open(self.graph_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load graph for NPC {self.npc_id}: {e}")
        
        # Default structure
        return {
            "nodes": [],  # List of {id, type, ...properties}
            "edges": []   # List of {source, target, relation, ...properties}
        }

    def _save_graph(self):
        """Persist the graph to JSON."""
        try:
            with open(self.graph_file, 'w', encoding='utf-8') as f:
                json.dump(self.graph_data, f, indent=2)
            logger.debug(f"Graph saved for NPC {self.npc_id}")
        except Exception as e:
            logger.error(f"Failed to save graph for NPC {self.npc_id}: {e}")
    
    def add_graph_data(self, graph_data: Any, player_id: int, memory_date: date = None, known_entities: Dict[str, Any] = None) -> str:
        """
        Adds structured graph data (extracted by the Agent) to the persistent store.
        
        Args:
            graph_data: The extracted KnowledgeGraphData object (or dict)
            player_id: The player associated with this interaction
            memory_date: The date of the memory
            known_entities: Lookup table for ID resolution (passed from Agent)
        """
        if memory_date is None:
            memory_date = date.today()

        if known_entities is None:
            known_entities = {}

        try:
            new_nodes_count = 0
            new_edges_count = 0
            
            # Track IDs processed in this batch
            name_to_id_map = {}
            
            # Access nodes/edges based on object type (Pydantic or dict)
            # Agent sends Pydantic object, but we handle both for safety
            nodes_list = graph_data.nodes if hasattr(graph_data, 'nodes') else graph_data.get('nodes', [])
            edges_list = graph_data.edges if hasattr(graph_data, 'edges') else graph_data.get('edges', [])

            # 1. Process Nodes
            for node in nodes_list:
                # Normalize access
                if hasattr(node, 'name'):
                    raw_name = node.name.strip()
                    raw_type = node.type.lower()
                    qty = node.quantity
                    props = node.properties
                else:
                    raw_name = node.get('name', '').strip()
                    raw_type = node.get('type', 'entity').lower()
                    qty = node.get('quantity')
                    props = node.get('properties', {})

                if not raw_name:
                    continue
                
                # ID Resolution
                lookup_key = raw_name.lower()
                resolved_id = raw_name  # Default (fallback)
                resolved_type = raw_type
                
                # Normalize known aliases
                if lookup_key in ['player', 'self', 'me', 'you', 'character']: # Common aliases for player
                     # Try to find player in known_entities by type or assume standard player key
                     if 'player' in known_entities:
                         lookup_key = 'player'
                
                # Attempt to find ID in known_entities
                # We also try fuzzy match on keys if exact match fails (e.g. "gold" vs "gold coin")
                entity_info = None
                if lookup_key in known_entities:
                    entity_info = known_entities[lookup_key]
                else:
                    # Simple fuzzy fallback: check if lookup_key is contained in any known key
                    for k, v in known_entities.items():
                        if lookup_key in k or k in lookup_key:
                            entity_info = v
                            break
                
                # IMPORTANT: If it's an EVENT, use raw name (e.g. "TradeEvent_01") as ID
                if "event" in raw_type:
                    resolved_id = raw_name
                    resolved_type = "event"
                elif entity_info:
                    resolved_id = str(entity_info.get("id", raw_name))
                    resolved_type = entity_info.get("type", raw_type)
                else:
                    # If not found and not event, default to raw
                    logger.debug(f"Unknown entity extracted: {raw_name}")

                
                metadata = {
                    "name": raw_name,
                    "created_at": str(memory_date),
                }
                
                if qty is not None:
                    metadata["quantity"] = qty
                
                if props:
                    metadata.update(props)
                
                name_to_id_map[raw_name] = resolved_id

                # Add/Update Node
                existing_node = next((n for n in self.graph_data["nodes"] if str(n["id"]) == resolved_id), None)
                
                if existing_node:
                    existing_node["metadata"].update(metadata)
                else:
                    self.graph_data["nodes"].append({
                        "id": resolved_id,
                        "type": resolved_type,
                        "metadata": metadata
                    })
                    new_nodes_count += 1

            # 2. Process Edges
            for edge in edges_list:
                if hasattr(edge, 'source'):
                    source_name = edge.source.strip()
                    target_name = edge.target.strip()
                    # relation = edge.relation.strip().upper()  <-- Removed relation
                else:
                    source_name = edge.get('source', '').strip()
                    target_name = edge.get('target', '').strip()
                    # relation = edge.get('relation', '').strip().upper()
                
                if not source_name or not target_name:
                    continue
                    
                # Resolve IDs using the map
                source_id = name_to_id_map.get(source_name, source_name)
                target_id = name_to_id_map.get(target_name, target_name)
                
                # Check duplicates
                existing_edges = {
                    (e["source"], e["target"]) 
                    for e in self.graph_data["edges"]
                }
                
                if (source_id, target_id) not in existing_edges:
                    self.graph_data["edges"].append({
                        "source": source_id,
                        "target": target_id,
                        # "relation": relation, <-- Removed
                        "timestamp": str(memory_date),
                        "player_id": player_id,
                        "npc_id": self.npc_id
                    })
                    new_edges_count += 1

            # 3. Save
            self._save_graph()
            logger.info(f"Graph updated: +{new_nodes_count} nodes, +{new_edges_count} edges.")
            return f"graph_{memory_date}_{new_nodes_count}n_{new_edges_count}e"
            
        except Exception as e:
            logger.error(f"Error adding graph data to memory: {e}")
            return "error_unknown"

    def query_memory(self, query: str, player_id: int = None, **kwargs) -> Dict:
        """
        Retrieves context by finding nodes mentioned in the query,
        then finding connected Event nodes, and describing the event.
        Structure: Entity -> [Edge] -> Event -> [Edge] -> Other Entity
        """
        query_lower = query.lower()
        
        # 1. Entity Linking (Find nodes mentioned in query)
        matched_node_ids = set()
        
        for node in self.graph_data["nodes"]:
            # Check ID matches
            node_id_str = str(node["id"]).lower()
            if node_id_str in query_lower:
                matched_node_ids.add(str(node["id"]))
            
            # Check Name in metadata matches
            name = node.get("metadata", {}).get("name", "").lower()
            if name and name in query_lower:
                matched_node_ids.add(str(node["id"]))

        # 2. Traverse Graph (Entity -> Event)
        # We want to find Event Nodes that are connected to our matched entities
        connected_event_ids = set()
        
        for edge in self.graph_data["edges"]:
            # Check if edge involves a matched entity
            if str(edge["source"]) in matched_node_ids:
                neighbor_id = str(edge["target"])
            elif str(edge["target"]) in matched_node_ids:
                neighbor_id = str(edge["source"])
            else:
                continue
                
            # Check if the neighbor is an Event Node
            neighbor_node = next((n for n in self.graph_data["nodes"] if str(n["id"]) == neighbor_id), None)
            if neighbor_node and neighbor_node.get("type") == "event":
                connected_event_ids.add(neighbor_id)

        # 3. Construct Context from Events
        # Returns a separate document for each found event to allow precise recall
        
        found_documents = []
        found_ids = []
        found_metadatas = []
        
        id_to_node_map = {str(n["id"]): n for n in self.graph_data["nodes"]}
        
        for event_id in connected_event_ids:
            event_node = id_to_node_map.get(event_id)
            if not event_node:
                continue
                
            event_meta = event_node.get("metadata", {})
            event_type = event_meta.get("type", "event")
            event_timestamp = event_meta.get("created_at", str(date.today()))
            
            # Find all participants in this event
            participants = []
            for edge in self.graph_data["edges"]:
                if str(edge["source"]) == event_id:
                    participants.append(str(edge["target"]))
                elif str(edge["target"]) == event_id:
                    participants.append(str(edge["source"]))
            
            # Convert participant IDs to Names
            participant_names = []
            for p_id in participants:
                p_node = id_to_node_map.get(p_id)
                p_name = p_node.get("metadata", {}).get("name", p_id) if p_node else p_id
                participant_names.append(p_name)
            
            # Format Sentence based on Event Type
            if event_type == "trade":
                trade_type = event_meta.get("trade_type", "trade") # buy/sell
                sentence = f"Trade Event ({trade_type}) on {event_timestamp}: Involved {', '.join(participant_names)}"
                if "cost" in event_meta:
                    sentence += f", Cost: {event_meta['cost']}"
                
            elif event_type == "chat":
                summary = event_meta.get("summary", "")
                sentence = f"Chat Event on {event_timestamp}: {summary} (Participants: {', '.join(participant_names)})"
                
            else:
                # Generic fallback
                props = ", ".join([f"{k}: {v}" for k, v in event_meta.items() if k not in ["name", "created_at", "type"]])
                sentence = f"Event '{event_meta.get('name')}' on {event_timestamp} with {', '.join(participant_names)}. Details: {props}"
                
            found_documents.append(sentence)
            found_ids.append(event_id)
            found_metadatas.append({
                "source": "knowledge_graph", 
                "timestamp": event_timestamp,
                "type": event_type,
                "event_id": event_id
            })
            
        if not found_documents:
            logger.info(f"Graph query '{query}' found 0 relevant connections.")
        else:
            logger.info(f"Graph query found {len(found_documents)} connections.")

        # Return in ChromaDB-like batch format [[doc1, doc2]]
        return {
            "documents": [found_documents], 
            "ids": [found_ids], 
            "metadatas": [found_metadatas]
        }

    def close(self):
        """Cleanup if necessary."""
        pass
