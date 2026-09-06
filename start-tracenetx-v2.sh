#!/bin/bash
# TraceNetX v2 - One-command startup script
PROJECT_ROOT="$HOME/Tracenetx"
BACKEND_DIR="$PROJECT_ROOT/backend"
FRONTEND_DIR="$PROJECT_ROOT/frontend/tracenetx-ui"

echo "=========================================="
echo " Starting TraceNetX v2.0"
echo "=========================================="

if [ ! -d "$BACKEND_DIR" ]; then echo "ERROR: backend dir not found at $BACKEND_DIR"; exit 1; fi
if [ ! -f "$BACKEND_DIR/venv/bin/activate" ]; then echo "ERROR: venv not found in $BACKEND_DIR"; exit 1; fi
if [ ! -d "$FRONTEND_DIR" ]; then echo "ERROR: frontend dir not found at $FRONTEND_DIR"; exit 1; fi

echo "[1/3] Checking Neo4j..."
if [ "$(docker ps -q -f name=^neo4j$)" ]; then
    echo "      Neo4j container already running."
elif [ "$(docker ps -aq -f name=^neo4j$)" ]; then
    echo "      Starting existing Neo4j container..."
    docker start neo4j
else
    echo "      Creating new Neo4j container..."
    docker run -d --name neo4j -p7474:7474 -p7687:7687 \
        -e NEO4J_AUTH=neo4j/password123 neo4j:latest
fi

echo "      Waiting for Neo4j bolt port to accept connections..."
for i in $(seq 1 30); do
    if (echo > /dev/tcp/127.0.0.1/7687) >/dev/null 2>&1; then
        echo "      Neo4j is ready (after ${i}s)."
        break
    fi
    sleep 1
    if [ "$i" -eq 30 ]; then
        echo "      WARNING: Neo4j did not become ready in 30s. Continuing anyway."
    fi
done
sleep 2  # small grace period for bolt handshake to fully stabilize

echo "[2/3] Checking backend port 8001..."
if curl -s -o /dev/null -w "" --max-time 1 http://localhost:8001/docs; then
    echo "      Backend already responding on :8001 — skipping launch."
else
    echo "      Starting backend (uvicorn on :8001)..."
    ptyxis --new-window -- bash -c "
        cd '$BACKEND_DIR' && \
        source venv/bin/activate && \
        uvicorn main:app --reload --host 0.0.0.0 --port 8001; \
        exec bash
    " &
    echo "      Waiting for backend to become ready..."
    for i in $(seq 1 30); do
        if curl -s -o /dev/null -w "" --max-time 1 http://localhost:8001/docs; then
            echo "      Backend is ready (after ${i}s)."
            break
        fi
        sleep 1
        if [ "$i" -eq 30 ]; then
            echo "      WARNING: Backend did not respond in 30s. Check its terminal window for errors."
        fi
    done
fi

echo "[3/3] Checking frontend port 3002..."
if lsof -i :3002 >/dev/null 2>&1; then
    echo "      Something already on :3002 — skipping frontend launch."
else
    echo "      Starting frontend (npm start on :3002)..."
    ptyxis --new-window -- bash -c "
        cd '$FRONTEND_DIR' && \
        npm start; \
        exec bash
    " &
fi

echo "=========================================="
echo " All services launching!"
echo " Neo4j Browser : http://localhost:7474"
echo " Backend API   : http://localhost:8001"
echo " Frontend UI   : http://localhost:3002"
echo "=========================================="
