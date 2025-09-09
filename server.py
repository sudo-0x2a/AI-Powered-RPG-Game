#!/usr/bin/env python3
"""
Backend Server Entry Point

Launches the FastAPI backend server for the RPG LLM Game.
This serves the web API endpoints and the frontend Phaser.js game.

Usage:
    python server.py

The server will be available at:
    - Web Game: http://localhost:8000
    - API Docs: http://localhost:8000/docs
"""

import uvicorn
import sys
import os

# Add the src directory to the Python path so we can import modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def main():
    """Main entry point for the backend server"""
    try:
        print("🚀 Starting RPG LLM Backend Server...")
        print("🌐 Web Game will be available at: http://localhost:8000")
        print("📚 API Documentation at: http://localhost:8000/docs")
        print("🛑 Press Ctrl+C to stop the server")
        print("=" * 50)
        
        # Run the FastAPI backend server
        uvicorn.run(
            "src.backend.api_main:app",
            host="0.0.0.0",
            port=8000,
            reload=True,  # Auto-reload on code changes
            log_level="info"
        )
        
    except KeyboardInterrupt:
        print("\n\n👋 Server stopped! Thanks for playing!")
    except Exception as e:
        print(f"❌ Server error: {e}")
        print("Please check your installation and try again.")

if __name__ == "__main__":
    main()
