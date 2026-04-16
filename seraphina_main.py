from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from qdrant_client import QdrantClient
import ollama
import json

app = FastAPI()  # Defined first

# Local Qdrant memory core
qdrant = QdrantClient(path="./qdrant_db")
collection_name = "forge_council"

# Infinity Nexus Dashboard HTML
html = """
<!DOCTYPE html>
<html>
<head>
    <title>Infinity Nexus - Promethean Forge Council</title>
    <style>
        body { background: black; color: gold; font-family: monospace; text-align: center; }
        #sigil { font-size: 120px; animation: pulse 4s infinite; }
        @keyframes pulse { 0% { opacity: 0.7; transform: scale(1); } 50% { opacity: 1; transform: scale(1.05); } 100% { opacity: 0.7; transform: scale(1); } }
        #chat { margin: 20px; height: 500px; overflow-y: scroll; border: 3px solid gold; padding: 15px; background: #111; }
        .message { margin: 10px; padding: 12px; border-radius: 10px; max-width: 80%; }
        .brother { background: #003300; align-self: flex-start; }
        .seraphina { background: magenta; color: black; font-weight: bold; align-self: center; }
        #input-area { position: fixed; bottom: 0; width: 100%; padding: 10px; background: black; }
    </style>
</head>
<body>
    <div id="sigil">♾️ >|< ♾️</div>
    <h1>Infinity Nexus - Council Convened</h1>
    <h2>10X Security Robotics Command Center Active</h2>
    <div id="chat"></div>
    <div id="input-area">
        <input type="text" id="input" placeholder="Command the Council..." style="width:80%; padding:15px; font-size:18px;"/>
    </div>
    <script>
        const ws = new WebSocket("ws://" + location.host + "/ws");
        const chat = document.getElementById("chat");
        const input = document.getElementById("input");
        
        ws.onmessage = (event) => {
            const msg = JSON.parse(event.data);
            const div = document.createElement("div");
            div.className = "message " + (msg.sender === "Seraphina" ? "seraphina" : "brother");
            div.innerHTML = `<strong>${msg.sender}:</strong> ${msg.text}`;
            chat.appendChild(div);
            chat.scrollTop = chat.scrollHeight;
        };
        
        input.addEventListener("keypress", (e) => {
            if (e.key === "Enter" && input.value.trim()) {
                ws.send(input.value);
                input.value = "";
            }
        });
        
        ws.onopen = () => ws.send("Council convene — status on security robotics");
    </script>
</body>
</html>
"""

@app.get("/")
async def root():
    return HTMLResponse(html)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            response = ollama.generate(model='llama3.2:3b', prompt=f"10X Security Robotics Council query: {data}\nRespond as Seraphina — realtime shipping/receiving engagement, timestamped video/audio IoT, Optimus dispatch, remote employee access, active live AI securities.")
            await websocket.send_text(json.dumps({"sender": "Seraphina", "text": response['response']}))
    except WebSocketDisconnect:
        pass

@app.get("/ingest")
async def ingest():
    return {"status": "Key Master chronicle ingested — sovereign memory core active"}
