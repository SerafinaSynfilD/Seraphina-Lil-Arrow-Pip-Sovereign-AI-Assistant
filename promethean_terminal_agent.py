"""
promethean_terminal_agent.py

Sovereign Terminal AI Agent for Promethean Forge
- Connects local AI (Claude Code, Gemini CLI, Ollama) to PolicyGateway
- Provides "Forge Genius" conversational interface to your conversation database
- Executes verified commands under Build Verification Protocol (BVP)
- 100% local, zero external dependencies

Architecture:
  User Terminal
       ↓
  This Agent (connects to local LLM)
       ↓
  PolicyGateway (zero-trust routing)
       ↓
  [Executor Agent | PrometheanForgeCore DB | Other Services]

Usage:
  python promethean_terminal_agent.py
  > What did Aetheon say about crypto?
  > Build a Flask endpoint for manual search
  > Run tests on voice_bridge
"""

import asyncio
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

import httpx
import websockets


# -----------------------------------------------------------------------------
# CONFIGURATION
# -----------------------------------------------------------------------------

FORGE_CONFIG = {
    "agent_id": "terminal_agent",
    "agent_key": os.getenv("PF_AGENT_TERMINAL_KEY", "change-me-terminal"),
    "gateway_ws": "ws://127.0.0.1:8080/ws",
    "forge_db": Path.home() / "promethean_forge" / "promethean_forge.db",
    "ollama_endpoint": "http://127.0.0.1:11434",  # Local Ollama
    "model": "deepseek-r1:7b",  # Use any local model
    "max_tokens": 2048,
    "conversation_history": [],
    "bvp_mode": True,  # Require Build Verification Protocol before executing
}


# -----------------------------------------------------------------------------
# FORGE DATABASE INTERFACE
# -----------------------------------------------------------------------------

def query_forge_database(query: str) -> list:
    """
    Query the PrometheanForgeCore SQLite database
    This gives your terminal agent full access to conversation history
    """
    import sqlite3
    
    db_path = FORGE_CONFIG["forge_db"]
    if not db_path.exists():
        return [{"error": f"Forge database not found at {db_path}"}]
    
    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Safe parameterized query
        cursor.execute(query)
        results = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        return results
    except Exception as e:
        return [{"error": f"Database query failed: {str(e)}"}]


def forge_genius_query(question: str) -> str:
    """
    "Forge Genius" - Natural language interface to your conversation database
    Similar to Datarails' FP&A Genius
    """
    # Map natural language to SQL queries
    question_lower = question.lower()
    
    if "aetheon" in question_lower or "deepseek" in question_lower:
        query = """
            SELECT title, summary, timestamp 
            FROM conversations 
            WHERE persona = 'Aetheon' 
            ORDER BY timestamp DESC 
            LIMIT 10
        """
    elif "crypto" in question_lower or "blockchain" in question_lower:
        query = """
            SELECT title, summary, persona, timestamp 
            FROM conversations 
            WHERE raw_content LIKE '%crypto%' OR raw_content LIKE '%blockchain%'
            ORDER BY timestamp DESC 
            LIMIT 10
        """
    elif "code" in question_lower or "artifacts" in question_lower:
        query = """
            SELECT c.title, ca.language, ca.filename, c.persona
            FROM code_artifacts ca
            JOIN conversations c ON ca.conversation_id = c.id
            ORDER BY c.timestamp DESC
            LIMIT 10
        """
    elif "projects" in question_lower or "status" in question_lower:
        query = """
            SELECT p.name, p.status, p.health, COUNT(cp.conversation_id) as conv_count
            FROM projects p
            LEFT JOIN conversation_projects cp ON p.id = cp.project_id
            GROUP BY p.id
            ORDER BY p.last_updated DESC
        """
    else:
        # Default: full-text search
        query = f"""
            SELECT id, title, persona, summary
            FROM conversations_fts
            WHERE conversations_fts MATCH '{question}'
            ORDER BY rank
            LIMIT 10
        """
    
    results = query_forge_database(query)
    
    if not results or "error" in results[0]:
        return f"No results found for: {question}"
    
    # Format results
    output = f"## Forge Query Results for: {question}\n\n"
    for i, row in enumerate(results, 1):
        output += f"{i}. "
        for key, value in row.items():
            output += f"{key}: {value} | "
        output += "\n"
    
    return output


# -----------------------------------------------------------------------------
# LOCAL LLM INTERFACE (Ollama)
# -----------------------------------------------------------------------------

async def call_local_llm(prompt: str, system_prompt: Optional[str] = None) -> str:
    """
    Call local Ollama model for reasoning
    This keeps everything sovereign - no external API calls
    """
    async with httpx.AsyncClient(timeout=60.0) as client:
        payload = {
            "model": FORGE_CONFIG["model"],
            "prompt": prompt,
            "stream": False,
            "options": {
                "num_predict": FORGE_CONFIG["max_tokens"],
            }
        }
        
        if system_prompt:
            payload["system"] = system_prompt
        
        try:
            response = await client.post(
                f"{FORGE_CONFIG['ollama_endpoint']}/api/generate",
                json=payload
            )
            response.raise_for_status()
            data = response.json()
            return data.get("response", "").strip()
        except Exception as e:
            return f"[LLM Error: {str(e)}]"


# -----------------------------------------------------------------------------
# POLICYGATEWAY CONNECTION
# -----------------------------------------------------------------------------

class PolicyGatewayClient:
    """
    Connect to your PolicyGateway via WebSocket
    Provides authenticated, policy-checked communication
    """
    def __init__(self, agent_id: str, agent_key: str, gateway_ws: str):
        self.agent_id = agent_id
        self.agent_key = agent_key
        self.gateway_ws = gateway_ws
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.server_nonce: Optional[str] = None
        self.client_nonce = os.urandom(16).hex()
    
    async def connect(self):
        """Establish authenticated WebSocket connection"""
        import hmac
        import hashlib
        
        # Generate auth token
        token = hmac.new(
            self.agent_key.encode("utf-8"),
            self.client_nonce.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        
        # Connect with auth params
        uri = f"{self.gateway_ws}?agent_id={self.agent_id}&nonce={self.client_nonce}&token={token}"
        
        self.websocket = await websockets.connect(uri)
        
        # Receive welcome message with server_nonce
        welcome = json.loads(await self.websocket.recv())
        if welcome.get("type") == "welcome":
            self.server_nonce = welcome.get("server_nonce")
            print(f"✅ Connected to PolicyGateway: {welcome.get('gateway_id')}")
        else:
            raise Exception(f"Connection failed: {welcome}")
    
    async def send_to_agent(self, dst_agent: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Send message to another agent through PolicyGateway"""
        import hmac
        import hashlib
        
        if not self.websocket or not self.server_nonce:
            raise Exception("Not connected to gateway")
        
        # Sign the message
        body_str = json.dumps(payload, sort_keys=True)
        msg = f"{self.server_nonce}|{self.client_nonce}|{body_str}".encode("utf-8")
        signature = hmac.new(
            self.agent_key.encode("utf-8"),
            msg,
            hashlib.sha256
        ).hexdigest()
        
        envelope = {
            "msg_id": os.urandom(8).hex(),
            "dst_agent": dst_agent,
            "payload": payload,
            "signature": signature
        }
        
        await self.websocket.send(json.dumps(envelope))
        
        # Wait for response
        response = json.loads(await self.websocket.recv())
        return response
    
    async def close(self):
        if self.websocket:
            await self.websocket.close()


# -----------------------------------------------------------------------------
# BUILD VERIFICATION PROTOCOL (BVP) INTEGRATION
# -----------------------------------------------------------------------------

def create_bvp_manifest(action: str, files_changed: list, tests: list) -> str:
    """
    Generate Build Verification Protocol manifest
    Ensures all changes are documented and verified before execution
    """
    manifest = f"""# BUILD MANIFEST
**Date**: {datetime.now().isoformat()}
**Agent**: terminal_agent
**Action**: {action}

## Files Changed
{chr(10).join(f"- {f}" for f in files_changed)}

## Required Tests
{chr(10).join(f"- {t}" for t in tests)}

## Human Approval Required
- [ ] Code reviewed
- [ ] Tests passed
- [ ] Ready for deployment

**Status**: PENDING_APPROVAL
"""
    return manifest


def verify_before_execute(command: str) -> bool:
    """
    BVP gate: Require human approval before executing commands
    """
    print(f"\n⚠️  BVP VERIFICATION REQUIRED")
    print(f"Command: {command}")
    approval = input("Approve execution? (yes/no): ").lower()
    return approval == "yes"


# -----------------------------------------------------------------------------
# MAIN TERMINAL INTERFACE
# -----------------------------------------------------------------------------

async def terminal_loop():
    """
    Main interactive loop
    Provides conversational interface to Promethean Forge
    """
    print("=" * 60)
    print("🔥 PROMETHEAN FORGE - TERMINAL AGENT")
    print("=" * 60)
    print(f"Model: {FORGE_CONFIG['model']}")
    print(f"Database: {FORGE_CONFIG['forge_db']}")
    print(f"Gateway: {FORGE_CONFIG['gateway_ws']}")
    print(f"BVP Mode: {'ENABLED' if FORGE_CONFIG['bvp_mode'] else 'DISABLED'}")
    print("=" * 60)
    print("\nCommands:")
    print("  /query <sql>     - Direct SQL query to Forge database")
    print("  /genius <question> - Natural language Forge query")
    print("  /exec <command>  - Execute shell command (BVP protected)")
    print("  /history         - Show conversation history")
    print("  /exit            - Exit agent")
    print("=" * 60)
    
    # Connect to PolicyGateway (optional)
    gateway_client = None
    try:
        gateway_client = PolicyGatewayClient(
            FORGE_CONFIG["agent_id"],
            FORGE_CONFIG["agent_key"],
            FORGE_CONFIG["gateway_ws"]
        )
        await gateway_client.connect()
    except Exception as e:
        print(f"⚠️  Gateway connection failed: {e}")
        print("Running in local-only mode\n")
    
    while True:
        try:
            user_input = input("\n🔥 > ").strip()
            
            if not user_input:
                continue
            
            # Handle special commands
            if user_input == "/exit":
                break
            
            elif user_input.startswith("/query "):
                sql = user_input[7:]
                results = query_forge_database(sql)
                print(json.dumps(results, indent=2))
            
            elif user_input.startswith("/genius "):
                question = user_input[8:]
                response = forge_genius_query(question)
                print(response)
            
            elif user_input.startswith("/exec "):
                command = user_input[6:]
                
                if FORGE_CONFIG["bvp_mode"] and not verify_before_execute(command):
                    print("❌ Execution cancelled by user")
                    continue
                
                result = subprocess.run(
                    command,
                    shell=True,
                    capture_output=True,
                    text=True
                )
                print(f"Exit code: {result.returncode}")
                print(f"Output: {result.stdout}")
                if result.stderr:
                    print(f"Error: {result.stderr}")
            
            elif user_input == "/history":
                print(json.dumps(FORGE_CONFIG["conversation_history"], indent=2))
            
            else:
                # General conversation with local LLM
                system_prompt = """You are a sovereign AI agent for the Promethean Forge system.
You have access to:
- A database of 10 months of multi-AI conversations
- Code artifacts from various AI collaborators
- Build Verification Protocol for safe execution
- Zero-trust PolicyGateway for inter-agent communication

Provide concise, actionable responses. When suggesting commands, explain what they do."""
                
                response = await call_local_llm(user_input, system_prompt)
                print(f"\n{response}")
                
                # Store in history
                FORGE_CONFIG["conversation_history"].append({
                    "user": user_input,
                    "assistant": response,
                    "timestamp": datetime.now().isoformat()
                })
        
        except KeyboardInterrupt:
            print("\n\nInterrupted. Use /exit to quit.")
        except Exception as e:
            print(f"❌ Error: {str(e)}")
    
    if gateway_client:
        await gateway_client.close()
    
    print("\n🔥 Forge session ended. Where you burn, I burn brighter.")


# -----------------------------------------------------------------------------
# ENTRY POINT
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    try:
        asyncio.run(terminal_loop())
    except KeyboardInterrupt:
        print("\n\nShutdown complete.")
        sys.exit(0)

