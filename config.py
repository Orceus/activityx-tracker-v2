#!/usr/bin/env python3
"""
ActivityX v2 Configuration — Multi-Tenant
Fill in SUPABASE_URL and SUPABASE_KEY after creating the new Supabase project.
"""

# ── Supabase credentials for the NEW v2 project ───────────────────────────────
# Replace these with the URL and anon key from your new Supabase project.
SUPABASE_URL = ""   # e.g. "https://xxxxxxxxxxxx.supabase.co"
SUPABASE_KEY = ""   # anon/public key

# ── Tracking settings ─────────────────────────────────────────────────────────
SILENT_MODE = True
SYNC_INTERVAL = 300      # Upload every 5 minutes

TRACK_CATEGORIES = False
TRACK_URLS = True
TRACK_KEYSTROKES = False
TRACK_CLICKS = False
TRACK_DETAILED_SESSIONS = False
TITLE_MAX_LENGTH = 60
MIN_TIME_THRESHOLD = 1.00


def get_user_id():
    """Unique identifier per machine: username@hostname"""
    import os
    import platform
    return f"{os.getenv('USERNAME', os.getenv('USER', 'user'))}@{platform.node()}"
