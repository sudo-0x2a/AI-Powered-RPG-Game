"""
AI Agents - Simple moved implementation without extra features
"""
from pydantic import BaseModel, Field
from typing import Annotated, List, Any, Dict, Optional
from langgraph.graph.message import add_messages
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver
from src.entities.characters import NPC
from .tools import create_npc_tools 
from .npc_memory import NPCMemory, GraphMemory
from datetime import datetime, date
import os
import re
import logging

logger = logging.getLogger(__name__)

def check_llm_connection(model_name: str = None) -> bool:
    """
    Check if the LLM is reachable and responding.
    """
    if not model_name:
        model_name = os.getenv("MODEL_NAME")
        if not model_name:
            logger.error("❌ MODEL_NAME environment variable is not set")
            return False

    try:
        logger.info(f"Checking connection to LLM: {model_name}...")
        # Use configured base_url if available in env
        base_url = os.getenv("OPENAI_BASE_URL")
        api_key = os.getenv("OPENAI_API_KEY")
        
        llm = ChatOpenAI(model=model_name, max_retries=1, base_url=base_url, api_key=api_key)

        # Simple ping
        llm.invoke([HumanMessage(content="Hello")])
        logger.info(f"✅ Successfully connected to LLM: {model_name}")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to connect to LLM: {e}")
        return False

# --- Pydantic Models for Knowledge Graph Extraction ---
class ExtractedNode(BaseModel):
    name: str = Field(..., description="The canonical name of the entity or event (e.g. 'Iron Sword', 'TradeEvent_01')")
    type: str = Field(..., description="The type: 'character', 'item', 'location', 'event'")
    quantity: Optional[int] = Field(None, description="Quantity if applicable (integer)")
    properties: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Other attributes (e.g. event details like trade_type, cost, or chat summary)")

class ExtractedEdge(BaseModel):
    source: str = Field(..., description="Name of source entity/event")
    target: str = Field(..., description="Name of target entity/event")

class KnowledgeGraphData(BaseModel):
    nodes: List[ExtractedNode] = Field(description="List of entities and events found in the text")
    edges: List[ExtractedEdge] = Field(description="List of connections between entities and events")
# -------------------------------------------------------

class NPCAgent:
    def __init__(self, npc: NPC, engine, thread_id: int):
        self.npc = npc
        self.engine = engine
        model_name = os.getenv("MODEL_NAME")
        if not model_name:
            raise ValueError("MODEL_NAME environment variable is not set")
        
        base_url = os.getenv("OPENAI_BASE_URL")
        api_key = os.getenv("OPENAI_API_KEY")
        
        if base_url:
            # If using custom base_url, pass the api_key from env
            self.llm = ChatOpenAI(model=model_name, base_url=base_url, api_key=api_key)
        else:
            self.llm = ChatOpenAI(model=model_name)

        sys_path = self.npc.ai_agent_config["system_message_path"]
        if not os.path.isabs(sys_path):
            sys_path = os.path.join(self.npc.config_dir, sys_path)
        self.system_message = open(sys_path, "r").read()
        self.tools = create_npc_tools(self.npc, self.engine)
        self.agent = self.llm.bind_tools(self.tools)
        self.memory = InMemorySaver()
        self.config = {"configurable": {"thread_id": thread_id}}
        
        # Initialize long-term memory storage
        memory_type = self.npc.ai_agent_config.get("memory_type", "embedding")
        
        if memory_type == "graph":
            logger.info(f"Initializing Graph Memory for NPC {self.npc.id}")
            self.long_term_memory = GraphMemory(self.npc.config_dir, self.npc.id)
        else:
            logger.info(f"Initializing Embedding Memory (VectorDB) for NPC {self.npc.id}")
            self.long_term_memory = NPCMemory(self.npc.config_dir, self.npc.id)
        
        self.npc_workflow = self.build_graph()

    def build_graph(self):
        class NPCState(BaseModel):
            messages: Annotated[List, add_messages] = Field(default_factory=list)

        def agent_node(state: NPCState) -> NPCState:
            current_messages = state.messages
            response = self.agent.invoke(current_messages)
            return {"messages": [response]}
        
        # Create tool node using LangGraph's ToolNode
        tool_node = ToolNode(self.tools)
        
        # Routing function to decide next step
        def should_continue(state: NPCState):
            last_message = state.messages[-1]
            # If the last message has tool calls, go to tools
            if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
                return "tools"
            # Otherwise, end the conversation
            return END
        
        graph_builder = StateGraph(NPCState)
        graph_builder.add_node("agent_node", agent_node)
        graph_builder.add_node("tools", tool_node)

        graph_builder.add_edge(START, "agent_node")
        graph_builder.add_conditional_edges(
            "agent_node",
            should_continue,
            {
                "tools": "tools",
                END: END
            }
        )
        graph_builder.add_edge("tools", "agent_node")
        npc_workflow = graph_builder.compile(checkpointer=self.memory)
        return npc_workflow

    def print_graph(self, filename=None):
        try:
            png_data = self.npc_workflow.get_graph().draw_mermaid_png()
            if filename is None:
                filename = f"graph_{self.npc.name.replace(' ', '_')}_id_{self.npc.id}.png"
            if not filename.endswith('.png'):
                filename += '.png'
            with open(filename, 'wb') as f:
                f.write(png_data)
            
            logger.info(f"Graph saved successfully as: {os.path.abspath(filename)}")
            return filename
            
        except Exception as e:
            logger.error(f"Error saving graph: {e}")
            return None

    def chat(self, message: str):
        current_state = self.npc_workflow.get_state(self.config)
        system_prompt = self.system_message + "\n\nNow the time is " + datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if not current_state.values.get("messages"):
            input_payload = {
                "messages": [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=message)
                ]
            }
        else:
            input_payload = {"messages": [HumanMessage(content=message)]}
        result = self.npc_workflow.invoke(input_payload, config=self.config)
        return result["messages"][-1].content

    def reset_memory(self):
        thread_id = self.config["configurable"]["thread_id"]
        if thread_id in self.memory.storage:
            del self.memory.storage[thread_id]
            logger.info(f"Memory for thread_id '{thread_id}' has been forcibly reset.")
        else:
            logger.info(f"No memory found to reset for thread_id '{thread_id}'.")
    
    def _extract_graph_data(self, summary: str, known_entities: Dict[str, Any]) -> KnowledgeGraphData:
        """
        Use the Agent's LLM to extract structured graph data from the summary.
        This logic is moved here from GraphMemory to keep LLM calls within the Agent.
        """
        # Extract entity names for the prompt context
        known_names = list(known_entities.keys()) if known_entities else []
        known_context = f"Known entities in the world (use these names if applicable): {', '.join(known_names)}" if known_names else ""

        # Configure Structured Output
        structured_llm = self.llm.with_structured_output(KnowledgeGraphData)
        
        prompt = f"""
        You are a Knowledge Graph Builder.
        Task: Extract entities, events, and connections from the conversation summary.
        
        Text:
        "{summary}"
        
        {known_context}

        Instructions:
        1. Identify Characters, Items, and Locations.
        2. Create 'Event' nodes for interactions (e.g., 'TradeEvent_01', 'ChatEvent_01').
           - Event properties:
             - For Trade: type='trade', trade_type='buy'/'sell', cost, timestamp.
             - For Chat: type='chat', summary, timestamp.
        3. Connect participants (Characters) and objects (Items) to the Event node using Edges.
        4. STRICTLY map Character/Item entities to the Known Entities list. 
           - If an entity is "Player", "Self", "Me", or the user's name, map it to "Player" (ID 100).
        5. For Items, separate the quantity from the name.
           - Example: "14 gold" -> Name: "Gold Coin", Quantity: 14
        6. Do NOT add 'relation' labels to edges; just connect the source and target.
        """
        
        logger.info(f"Extracting graph entities for NPC {self.npc.id} using Agent's LLM...")
        return structured_llm.invoke(prompt)

    def save_conversation_memory(self, summary: str, player_id: int, memory_date=None):
        """
        Save a conversation summary as a long-term memory.
        """
        from datetime import date
        if memory_date is None:
            memory_date = date.today()
        
        try:
            logger.info(f"Saving memory for NPC {self.npc.id} (player {player_id}): '{summary[:50]}...'")
            
            # Case 1: Graph Memory (Needs LLM extraction first)
            if isinstance(self.long_term_memory, GraphMemory):
                # 1. Build known entities lookup
                known_entities = {}
                for char in self.engine.all_characters:
                    known_entities[char.name.lower()] = {
                        "id": char.id,
                        "type": "character"
                    }
                    # Also add player as "player" if name is different
                    if isinstance(char, type(self.engine.players[0])) and char.name.lower() != "player":
                         known_entities["player"] = {
                            "id": char.id,
                            "type": "character"
                        }

                if hasattr(self.engine, "items_by_name"):
                    for name, item in self.engine.items_by_name.items():
                        known_entities[name] = {
                            "id": item.id,
                            "type": "item"
                        }
                
                # 2. Use AGENT'S LLM to extract data
                graph_data = self._extract_graph_data(summary, known_entities)
                
                if not graph_data:
                    logger.warning("Structured extraction failed or returned empty.")
                    return "error_extraction_failed"

                # 3. Pass PRE-COMPUTED data to memory for storage
                # We convert Pydantic model to dict/JSON compatible format or pass object if GraphMemory supports it
                # GraphMemory.add_memory will be updated to accept 'graph_data' instead of 'summary' + 'llm'
                
                # Convert to dict format for compatibility with existing memory system interface logic or just pass the object
                # Let's update GraphMemory.add_graph_data(graph_data, ...)
                memory_id = self.long_term_memory.add_graph_data(graph_data, player_id, memory_date, known_entities)
                
            # Case 2: Vector Memory (Standard text storage)
            else:
                memory_id = self.long_term_memory.add_memory(summary, player_id, memory_date)
            
            # Verify save
            try:
                if hasattr(self.long_term_memory, 'graph_data'):
                    total_memories = len(self.long_term_memory.graph_data.get("nodes", []))
                    logger.info(f"Memory saved. Total graph nodes: {total_memories}")
                else:
                    total_memories = len(self.long_term_memory.collection.get()['documents'] or [])
                    logger.info(f"Memory saved. Total memories: {total_memories}")
            except Exception as count_error:
                logger.warning(f"Could not verify memory count: {count_error}")
            
            return memory_id
            
        except Exception as e:
            logger.error(f"Failed to save memory for NPC {self.npc.id}: {e}")
            raise
    
    def cleanup(self):
        """
        Clean up resources used by the NPCAgent.
        Should be called when the agent is no longer needed.
        """
        try:
            # Clean up long-term memory
            if hasattr(self, 'long_term_memory') and self.long_term_memory:
                self.long_term_memory.close()
                logger.info(f"Cleaned up memory for NPC {self.npc.name}")
        except Exception as e:
            logger.warning(f"Error cleaning up NPC agent for {self.npc.name}: {e}")
        finally:
            self.long_term_memory = None
    
    def __del__(self):
        """Destructor to ensure resources are cleaned up"""
        try:
            self.cleanup()
        except Exception:
            pass  # Ignore errors in destructor

class SummaryAgent:
    """
    A minimal agent that only performs conversation summarization.
    """

    def __init__(self, model: str = None):
        if not model:
            model = os.getenv("MODEL_NAME")
            if not model:
                raise ValueError("MODEL_NAME environment variable is not set")
        
        base_url = os.getenv("OPENAI_BASE_URL")
        api_key = os.getenv("OPENAI_API_KEY")

        if base_url:
            self.llm = ChatOpenAI(model=model, base_url=base_url, api_key=api_key)
        else:
            self.llm = ChatOpenAI(model=model)

    def summarize(self, messages: List[Any], npc_name: str = "NPC", npc_role: str = "NPC") -> str:
        """
        Create a concise summary from a conversation message list.

        Args:
            messages: List of LangChain message objects (HumanMessage/AIMessage/SystemMessage/etc.)
            npc_name: Name of the NPC speaker
            npc_role: Role of the NPC speaker

        Returns:
            Cleaned summary string with any <think>...</think> content removed.
        """
        def clean_thinking_tags(text: str) -> str:
            """Remove <think>...</think> content from text"""
            if not text:
                return text
            # Remove thinking tags and their content
            cleaned = re.sub(r"<think>[\s\S]*?</think>", "", text, flags=re.IGNORECASE)
            # Clean up extra whitespace
            cleaned = re.sub(r'\s+', ' ', cleaned).strip()
            return cleaned
        
        transcript_lines: List[str] = []
        
        for msg in messages or []:
            # Get message type and content
            msg_type = getattr(msg, "type", None)
            content = getattr(msg, "content", None)
            
            # Skip empty messages
            if not content or not isinstance(content, str):
                continue
            
            # Only include human (player) and ai (assistant) messages
            # Explicitly exclude system, tool, function, and any other message types
            if msg_type == "human":
                # Clean player message and add to transcript
                cleaned_content = clean_thinking_tags(content)
                if cleaned_content:  # Only add if there's content after cleaning
                    transcript_lines.append(f"Player: {cleaned_content}")
                    
            elif msg_type == "ai":
                # Clean AI message (remove thinking tags) and add to transcript
                cleaned_content = clean_thinking_tags(content)
                if cleaned_content:  # Only add if there's content after cleaning
                    transcript_lines.append(f"{npc_name}: {cleaned_content}")
            
            # Skip all other message types: system, tool, function, etc.

        if not transcript_lines:
            logger.warning("No conversation content found to summarize")
            return "No conversation content found to summarize."

        transcript = "\n".join(transcript_lines)
        logger.info(f"Summarizing conversation with {len(transcript_lines)} message lines")

        prompt = f"""You are a conversation summarizer.
Your job is to summarize a conversation between an NPC and a player in an RPG game.
The summary will function as a piece of memory for future interactions.

<conversation>
{transcript}
</conversation>

Create a concise summary that captures:
- What was discussed or accomplished
- Any items traded or services provided
- The general tone/mood of the interaction
- Important details the NPC should remember

Return only the summary text, no additional formatting."""

        response = self.llm.invoke([HumanMessage(content=prompt)])
        content = getattr(response, "content", str(response))

        # Final cleanup of any remaining thinking tags in the summary response
        if isinstance(content, str):
            content = clean_thinking_tags(content)

        logger.info(f"Generated summary: '{content[:100]}...'")
        return content
