#!/usr/bin/env python3
"""
Process Management Script
Ensures a clean environment by gracefully terminating old instances of the application.
"""

import os
import sys
import time
import signal
import subprocess
import psutil

TARGET_SCRIPT = "main_enhanced.py"

def get_target_processes():
    """Find all processes running the target script."""
    procs = []
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = proc.info['cmdline']
            if cmdline and any(TARGET_SCRIPT in arg for arg in cmdline):
                procs.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    return procs

def kill_processes():
    """Terminate target processes gracefully, then forcefully."""
    procs = get_target_processes()
    
    if not procs:
        print(f"✅ No existing instances of {TARGET_SCRIPT} found.")
        return

    print(f"⚠️ Found {len(procs)} running instances of {TARGET_SCRIPT}. Cleaning up...")

    # 1. Graceful Shutdown (SIGTERM)
    for proc in procs:
        try:
            print(f"   - Sending SIGTERM to PID {proc.pid}...")
            proc.terminate()
        except psutil.NoSuchProcess:
            pass

    # Wait for them to exit
    gone, alive = psutil.wait_procs(procs, timeout=5)

    # 2. Force Kill (SIGKILL)
    if alive:
        print(f"⚠️ {len(alive)} processes did not exit. Force killing...")
        for proc in alive:
            try:
                print(f"   - Sending SIGKILL to PID {proc.pid}...")
                proc.kill()
            except psutil.NoSuchProcess:
                pass
        
        # Wait again to be sure
        psutil.wait_procs(alive, timeout=2)

    print("✅ Cleanup complete.")

if __name__ == "__main__":
    kill_processes()
