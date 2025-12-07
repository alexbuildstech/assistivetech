#!/bin/bash
echo "🔪 Killing all Python processes..."
pkill -f "main_enhanced.py"
pkill -f "test_interactive.py"
pkill -f "mpv"
echo "✅ Done."
