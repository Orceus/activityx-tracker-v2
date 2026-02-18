#!/usr/bin/env python3
"""
ActivityX v2 Configuration — Multi-Tenant
Before distributing to a client, fill in their LAW_FIRM_ID from Supabase.
"""

# ── Supabase credentials ───────────────────────────────────────────────────────
SUPABASE_URL = ""   # e.g. "https://xxxxxxxxxxxx.supabase.co"
SUPABASE_KEY = ""   # anon/public key

# ── Client identifier ─────────────────────────────────────────────────────────
# Copy the UUID from the law_firms table in Supabase and paste it here
# before distributing this build to the client.
LAW_FIRM_ID = ""    # e.g. "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"

# ── Tracking settings ─────────────────────────────────────────────────────────
SILENT_MODE = True
SYNC_INTERVAL = 300

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
