import subprocess
import time
import os
import sys
import json
from pathlib import Path

# Supabase import
try:
    from supabase import create_client, Client
except ImportError:
    print("Warning: Supabase client not available. Install with: pip install supabase")
    create_client = None

# Load Supabase credentials from config.py (same as tracker)
try:
    import config
    SUPABASE_URL = config.SUPABASE_URL
    SUPABASE_KEY = config.SUPABASE_KEY
except ImportError:
    SUPABASE_URL = os.getenv('SUPABASE_URL', '')
    SUPABASE_KEY = os.getenv('SUPABASE_KEY', '')


def get_law_firm_id():
    """Read the saved law_firm_id UUID from keytrk_data/law_firm_id.txt"""
    law_firm_file = Path("keytrk_data") / "law_firm_id.txt"
    if law_firm_file.exists():
        value = law_firm_file.read_text(encoding="utf-8").strip()
        return value if value else None
    return None


def init_supabase_client():
    """Initialize Supabase client"""
    if not create_client:
        return None
    try:
        return create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        print(f"Failed to initialize Supabase client: {e}")
        return None


def upload_optimized_batches():
    """Upload optimized batch files from Documents folder to Supabase"""
    documents_path = Path(os.path.expanduser('~')) / 'Documents' / 'ActivityX' / 'keytrk_data'

    if not documents_path.exists():
        return

    batch_files = list(documents_path.glob("optimized_batch_*.json"))
    if not batch_files:
        return

    supabase_client = init_supabase_client()
    if not supabase_client:
        print("Cannot upload batches: Supabase client not available")
        return

    law_firm_id = get_law_firm_id()
    successful_uploads = []

    for batch_file in sorted(batch_files):
        try:
            success = upload_single_batch(supabase_client, batch_file, law_firm_id)
            if success:
                successful_uploads.append(batch_file)
            else:
                break
        except Exception as e:
            print(f"Error uploading {batch_file.name}: {e}")
            break

    for file_path in successful_uploads:
        try:
            file_path.unlink()
            print(f"Deleted uploaded optimized file: {file_path.name}")
        except Exception as e:
            print(f"Failed to delete {file_path.name}: {e}")

    if successful_uploads:
        print(f"SUCCESS: Successfully synced {len(successful_uploads)} optimized batches")
    elif batch_files:
        print(f"{len(batch_files)} optimized batches pending upload (will retry)")


def upload_single_batch(supabase_client, file_path, law_firm_id=None):
    """Upload a single optimized batch file to Supabase"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        insert_data = {
            'batch_id': file_path.stem,
            'user_id': data.get('u'),
            'law_firm_id': law_firm_id,
            'date_tracked': data.get('d'),
            'batch_start_time': data.get('s'),
            'batch_end_time': data.get('e'),
            'total_time_seconds': data.get('tt', 0),
            'active_time_seconds': data.get('at', 0),
            'inactive_time_seconds': data.get('it', 0),
            'batch_data': data
        }

        response = supabase_client.table("activity_summary").insert(insert_data).execute()

        if response.data:
            print(f"SUCCESS: Uploaded optimized file {file_path.name}")
            return True
        else:
            print(f"Upload failed for: {file_path.name}")
            return False

    except Exception as e:
        print(f"Upload error for {file_path.name}: {e}")
        return False


def is_process_running(process_name):
    try:
        output = subprocess.check_output(
            ['tasklist', '/FI', f'IMAGENAME eq {process_name}'],
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        return process_name.encode() in output
    except:
        return False


def start_activity_tracker():
    tracker_path = Path(os.path.expanduser('~')) / 'Documents' / 'ActivityX' / 'activity_tracker.exe'
    try:
        subprocess.Popen(
            [str(tracker_path)],
            creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            cwd=str(tracker_path.parent),
        )
        return True
    except Exception:
        return False


def main():
    if sys.platform == 'win32':
        import ctypes
        ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)

    time.sleep(60)

    last_batch_upload = time.time()
    batch_upload_interval = 180  # 3 minutes

    while True:
        try:
            current_time = time.time()

            if not is_process_running('activity_tracker.exe'):
                start_activity_tracker()

            if current_time - last_batch_upload >= batch_upload_interval:
                try:
                    upload_optimized_batches()
                except Exception:
                    pass
                last_batch_upload = current_time

            time.sleep(30)

        except Exception:
            time.sleep(30)
            continue


if __name__ == '__main__':
    try:
        main()
    except Exception:
        while True:
            time.sleep(60)
