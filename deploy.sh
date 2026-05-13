#!/bin/bash
set -e

echo "📦 Pulling latest changes..."
git pull origin main

CHANGED=$(git diff HEAD@{1} HEAD --name-only 2>/dev/null || echo "")

FRONTEND_CHANGED=false
BACKEND_CHANGED=false

if echo "$CHANGED" | grep -q "^frontend/"; then
  FRONTEND_CHANGED=true
fi

if echo "$CHANGED" | grep -qE "^backend/|^docker-compose\.yml|^\.env"; then
  BACKEND_CHANGED=true
fi

if [ -z "$CHANGED" ]; then
  echo "✅ Already up to date. Nothing to rebuild."
  exit 0
fi

echo ""
echo "Changed files:"
echo "$CHANGED"
echo ""

if $FRONTEND_CHANGED && $BACKEND_CHANGED; then
  echo "🔄 Rebuilding frontend + backend..."
  docker compose up -d --build
elif $FRONTEND_CHANGED; then
  echo "🔄 Rebuilding frontend only..."
  docker compose up -d --build frontend
elif $BACKEND_CHANGED; then
  echo "🔄 Rebuilding backend only..."
  docker compose up -d --build backend
fi

echo ""
echo "✅ Deploy complete."
