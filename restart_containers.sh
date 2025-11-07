#!/bin/bash
# ===============================
# Restart script for Docker containers
# Manager & Prometheus Exporter
# ===============================

# --- Restart Manager ---
echo "Stopping manager container..."
docker stop manager

echo "Removing manager container..."
docker rm manager

echo "Building manager image..."
docker build -t game-manager -f docker/Dockerfile_manager .

echo "Starting manager container..."
docker run -d \
  --name manager \
  -v /home/ubuntu/ruby-acorn/data:/app/data \
  -v /home/ubuntu/ruby-acorn/logs:/app/logs \
  game-manager

# --- Restart Prometheus Exporter ---
echo "Stopping exporter container..."
docker stop exporter

echo "Removing exporter container..."
docker rm exporter

echo "Building exporter image..."
docker build -t prometheus-exporter -f docker/Dockerfile_exporter .

echo "Starting exporter container..."
docker run -d \
  --name exporter \
  -p 5000:5000 \
  -v /home/ubuntu/ruby-acorn/data:/app/data \
  prometheus-exporter


echo "✅ All containers restarted successfully!"
