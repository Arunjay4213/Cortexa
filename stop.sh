#!/bin/bash
# Stop CortexOS
lsof -ti:8000 2>/dev/null | xargs kill 2>/dev/null
sleep 1
# Force kill if still running
lsof -ti:8000 2>/dev/null | xargs kill -9 2>/dev/null || true
echo "CortexOS stopped"
