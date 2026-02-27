#!/bin/bash
# ─── AutoOrder: Fix corrupted packages after disk-full crash ───
# Run this ONCE on your Wispbyte console to fix the "marshal data too short" error.
#
# What happened:
#   Disk ran out mid-install → telethon .pyc files were truncated/corrupted.
#   Even after freeing space, the broken files remain cached.
#
# This script:
#   1. Removes corrupted package cache
#   2. Clears pip cache (frees disk space)
#   3. Reinstalls packages cleanly

echo "══════════════════════════════════════════════"
echo "  AutoOrder — Cleanup & Reinstall"
echo "══════════════════════════════════════════════"

# Step 1: Remove corrupted site-packages
echo "[1/4] Removing corrupted packages..."
rm -rf .local/lib/python3.11/site-packages/telethon*
rm -rf .local/lib/python3.11/site-packages/pyaes*
rm -rf .local/lib/python3.11/site-packages/rsa*
rm -rf .local/lib/python3.11/site-packages/pyasn1*
rm -rf .local/lib/python3.11/site-packages/python_dotenv*

# Step 2: Clear pip cache to free disk space
echo "[2/4] Clearing pip cache (freeing disk space)..."
pip cache purge 2>/dev/null || rm -rf /home/container/.cache/pip

# Step 3: Remove any __pycache__ dirs (frees disk + avoids stale bytecode)
echo "[3/4] Cleaning __pycache__..."
find /home/container -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null

# Step 4: Reinstall cleanly with no cache
echo "[4/4] Reinstalling packages (no cache)..."
pip install --no-cache-dir --prefix .local -r requirements.txt

echo ""
echo "✅ Done! Now restart the server."
