#!/usr/bin/env python3
"""
ActivityX v2 Configuration — Multi-Tenant
Before distributing to a client, fill in their LAW_FIRM_ID from Supabase.
"""

# ── Supabase credentials ───────────────────────────────────────────────────────
SUPABASE_URL = "https://mwctncfrjjgxbusdlfqt.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im13Y3RuY2ZyampneGJ1c2RsZnF0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzE0MjA2NzcsImV4cCI6MjA4Njk5NjY3N30.FWydfEXukHE_vrss8fvs3J3s-kdxwSVjFx02Dl5hRjA"

# ── Client identifier ─────────────────────────────────────────────────────────
# Only change this per client — copy the UUID from the law_firms table in Supabase.
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
