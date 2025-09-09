from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
from datetime import datetime, date
import chromadb
import os
import logging
import time

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