from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
import os
import json
from pathlib import Path
from pydantic import BaseModel
from typing import Optional
from dotenv import load_dotenv
from fastapi.responses import Response
import atexit

load_dotenv()
# Reduce tokenizer multiprocessing/semaphore usage to avoid resource tracker warnings
import os as _os_env
_os_env.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
try:
    import torch as _torch
    try:
        _torch.multiprocessing.set_sharing_strategy("file_system")
    except Exception:
        pass
except Exception:
    pass
# Import your existing game system
from ..core.game_engine import GameEngine
from ..entities.characters import Player
from ..core.game_logger import game_logger
from ..ai_agents.agents import SummaryAgent
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="RPG LLM API",
    description="Backend API for the LLM-powered RPG game",
    version="1.0.0"
)

# Add CORS middleware to allow frontend to communicate with backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize core game engine
engine = GameEngine()
if not engine.initialize():
    raise RuntimeError("Failed to initialize game engine")

# Initialize SummaryAgent (singleton for server)
summary_agent = SummaryAgent()

# Flag to prevent multiple shutdown calls
_shutdown_called = False

def shutdown_handler():
    """Handle graceful shutdown of the game engine"""
    global _shutdown_called
    if _shutdown_called:
        return
    _shutdown_called = True
    
    try:
        logger.info("Shutting down server...")
        engine.shutdown()
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")

# Register only atexit handler - let uvicorn handle signals properly
atexit.register(shutdown_handler)

# FastAPI shutdown event
@app.on_event("shutdown")
async def app_shutdown():
    """FastAPI shutdown event handler"""
    shutdown_handler()

# Serve static assets (images, maps, etc.) with proper MIME types
project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
assets_path = os.path.join(project_root, "assets")
phaser_path = os.path.join(project_root, "phaser_JS")
frontend_path = os.path.join(project_root, "src", "frontend")

app.mount("/assets", StaticFiles(directory=assets_path, html=True), name="assets")
app.mount("/phaser_JS", StaticFiles(directory=phaser_path), name="phaser_js")
app.mount("/src/frontend", StaticFiles(directory=frontend_path), name="frontend")

# Serve TMX file explicitly with correct MIME type
@app.get("/assets/map/world_map.tmx")
async def serve_tmx():
    """Serve the TMX file with proper XML MIME type"""
    tmx_path = os.path.join(project_root, "assets", "map", "world_map.tmx")
    return FileResponse(tmx_path, media_type="application/xml")

# Serve the game.js file
@app.get("/game.js")
async def serve_game_js():
    """Serve the main game JavaScript file"""
    game_js_path = os.path.join(os.path.dirname(__file__), "..", "frontend", "game.js")
    return FileResponse(
        game_js_path,
        media_type="application/javascript",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
    )

@app.get("/favicon.ico")
async def favicon():
    # Small 16x16 transparent PNG (1x1) as favicon placeholder
    png_bytes = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\x0cIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\n\x0b\x0c\x02\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    return Response(content=png_bytes, media_type="image/png")

@app.get("/", response_class=HTMLResponse)
async def serve_game():
    """Serve the main game HTML page"""
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>RPG LLM Game</title>
        <style>
            body {
                margin: 0;
                padding: 0;
                background: #000;
                display: flex;
                justify-content: center;
                align-items: center;
                min-height: 100vh;
                font-family: Arial, sans-serif;
            }
            #game-container {
                border: 2px solid #333;
                border-radius: 8px;
            }
        </style>
        <link rel="icon" href="/favicon.ico" />
    </head>
    <body>
        <div id="game-container"></div>
        <script src="/phaser_JS/node_modules/phaser/dist/phaser.min.js"></script>
        <script src="/game.js?v=dev"></script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.get("/api/map")
async def get_map_data():
    """Get map data for the frontend"""
    map_path = os.path.join(project_root, "assets", "map", "world_map.tmx")
    if not os.path.exists(map_path):
        raise HTTPException(status_code=404, detail="Map file not found")
    
    return {
        "map_file": "/assets/map/world_map.tmx",
        "tilesets": [
            "/assets/map/[Base]BaseChip_pipo.png",
            "/assets/map/[A]Grass_pipo.png",
            "/assets/map/[A]Water_pipo.png",
            "/assets/map/[A]Dirt_pipo.png",
            "/assets/map/[A]Flower_pipo.png",
            "/assets/map/[A]Wall-Up_pipo.png",
            "/assets/map/[A]WaterFall_pipo.png"
        ],
        "tile_size": 32,
        "map_size": {"width": 60, "height": 60}
    }

@app.get("/api/player")
async def get_player_data():
    """Get player character data"""
    if not engine.players:
        raise HTTPException(status_code=404, detail="No player found")
    
    player = engine.players[0]  # Get first player
    player_data = player.get_frontend_data()
    
    # Add additional player-specific data
    player_data["inventory"] = player.show_inventory()
    
    return player_data

@app.get("/api/characters")
async def get_all_characters():
    """Get all character data for the frontend"""
    characters_data = {
        "npcs": [],
        "players": []
    }
    
    # Add NPCs using dynamic data from configurations
    for npc in engine.npcs:
        npc_data = npc.get_frontend_data()
        characters_data["npcs"].append(npc_data)
    
    # Add players using dynamic data from configurations
    for player in engine.players:
        player_data = player.get_frontend_data()
        characters_data["players"].append(player_data)
    
    return characters_data

class ChatRequest(BaseModel):
    npc_id: int
    message: str
    player_id: Optional[int] = None

@app.post("/api/chat")
async def chat_with_npc(request: ChatRequest):
    """Chat with an NPC via the AI agent system"""
    if not engine.players:
        raise HTTPException(status_code=400, detail="No player available")

    try:
        player_id = request.player_id if request.player_id is not None else engine.players[0].id
        reply = engine.chat_with_npc(request.npc_id, player_id, request.message)
        return {"reply": reply}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat error: {str(e)}")

class ChatCloseRequest(BaseModel):
    npc_id: int
    player_id: Optional[int] = None

def _summarize_and_persist(npc_id: int, player_id: int):
    try:
        agent = engine.get_agent_by_npc_id(npc_id)
        if not agent:
            logger.error(f"Background summarization: agent not found for NPC {npc_id}")
            return
        try:
            current_state = agent.npc_workflow.get_state(agent.config)
            messages = current_state.values.get("messages") if current_state else []
        except Exception as e:
            logger.error(f"Background summarization: failed to read messages for NPC {npc_id}: {e}")
            messages = []
        summary = summary_agent.summarize(messages, npc_name=agent.npc.name, npc_role=agent.npc.role)
        try:
            memory_id = agent.save_conversation_memory(summary, player_id)
            logger.info(f"Background summarization: saved memory {memory_id} for NPC {npc_id}")
        except Exception as e:
            logger.error(f"Background summarization: failed to save memory for NPC {npc_id}: {e}")
        game_logger.log_event(
            event_type="conversation_summary",
            player_id=player_id,
            npc_id=npc_id,
            effects={"summary": summary}
        )
    except Exception as e:
        logger.exception(f"Background summarization error for NPC {npc_id}: {e}")


@app.post("/api/chat/close")
async def close_chat(request: ChatCloseRequest, background_tasks: BackgroundTasks):
    """Signal that chat UI closed; schedule summarization+memory save in background and return immediately."""
    try:
        player_id = request.player_id if request.player_id is not None else (engine.players[0].id if engine.players else None)
        if player_id is None:
            raise HTTPException(status_code=400, detail="No player available")
        # Schedule background processing to avoid blocking main thread/event loop
        background_tasks.add_task(_summarize_and_persist, request.npc_id, player_id)
        return {"status": "accepted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error scheduling close_chat task: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Close chat error: {str(e)}")

# Health check endpoint
@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "game_engine": "initialized",
        "npcs_loaded": len(engine.npcs),
        "players_loaded": len(engine.players)
    }

if __name__ == "__main__":
    import uvicorn
    print("🚀 Starting RPG LLM Backend...")
    print("📝 Game engine loaded:")
    print(f"   - NPCs: {len(engine.npcs)}")
    print(f"   - Players: {len(engine.players)}")
    print("🎮 Game will be available at: http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
