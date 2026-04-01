import subprocess
import time
import os
import sys
import json
import logging
from pathlib import Path

# ── Logging ───────────────────────────────────────────────────────────────────
def _setup_controller_logging():
    if sys.platform == 'win32':
        base = Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData' / 'Local'))
    elif sys.platform == 'darwin':
        base = Path.home() / 'Library' / 'Application Support'
    else:
        base = Path.home() / '.local' / 'share'
    log_dir = base / 'ActivityX'
    log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=str(log_dir / 'controller.log'),
        level=logging.INFO,
        format='%(asctime)s %(levelname)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    )

_setup_controller_logging()

# ── Single-instance guard ─────────────────────────────────────────────────────
if sys.platform == 'win32':
    import ctypes
    _mutex = ctypes.windll.kernel32.CreateMutexW(None, True, "Global\\ActivityXController")
    if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        sys.exit(0)
elif sys.platform == 'darwin':
    import fcntl
    _lock_file = open('/tmp/activityx_controller.lock', 'w')
    try:
        fcntl.flock(_lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except IOError:
        sys.exit(0)

# Supabase import
try:
    from supabase import create_client
except ImportError:
    print("Warning: Supabase client not available. Install with: pip install supabase")
    create_client = None

def _load_config():
    """Load config.py from the same directory as the executable."""
    import importlib.util
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    spec = importlib.util.spec_from_file_location("config", os.path.join(base_dir, 'config.py'))
    cfg = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cfg)
    return cfg


try:
    _cfg = _load_config()
    SUPABASE_URL = _cfg.SUPABASE_URL
    SUPABASE_KEY = _cfg.SUPABASE_KEY
    LAW_FIRM_ID = getattr(_cfg, 'LAW_FIRM_ID', None) or None  # empty string → None
except Exception:
    SUPABASE_URL = os.getenv('SUPABASE_URL', '')
    SUPABASE_KEY = os.getenv('SUPABASE_KEY', '')
    LAW_FIRM_ID = os.getenv('LAW_FIRM_ID', None) or None


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
    if sys.platform == 'win32':
        base = Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData' / 'Local'))
    elif sys.platform == 'darwin':
        base = Path.home() / 'Library' / 'Application Support'
    else:
        base = Path.home() / '.local' / 'share'
    documents_path = base / 'ActivityX' / 'keytrk_data'

    if not documents_path.exists():
        return

    batch_files = list(documents_path.glob("optimized_batch_*.json"))
    if not batch_files:
        return

    supabase_client = init_supabase_client()
    if not supabase_client:
        print("Cannot upload batches: Supabase client not available")
        return

    law_firm_id = LAW_FIRM_ID
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

        date_str = data.get('d')
        start_str = data.get('s')
        end_str = data.get('e')
        if date_str and start_str and 'T' not in str(start_str):
            start_str = f"{date_str}T{start_str}"
        if date_str and end_str and 'T' not in str(end_str):
            end_str = f"{date_str}T{end_str}"

        insert_data = {
            'batch_id': file_path.stem,
            'user_id': data.get('u'),
            'law_firm_id': law_firm_id,
            'date_tracked': date_str,
            'batch_start_time': start_str,
            'batch_end_time': end_str,
            'total_time_seconds': data.get('tt', 0),
            'active_time_seconds': data.get('at', 0),
            'inactive_time_seconds': data.get('it', 0),
            'network_name': data.get('nn'),
            'ip_address': data.get('ip'),
            'local_ips': data.get('li'),
            'batch_data': data
        }

        response = supabase_client.table("activity_summary").upsert(insert_data, on_conflict="batch_id,user_id").execute()

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
    if sys.platform == 'win32':
        base = Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData' / 'Local'))
        tracker_path = base / 'ActivityX' / 'activity_tracker.exe'
    elif sys.platform == 'darwin':
        base = Path.home() / 'Library' / 'Application Support'
        tracker_path = base / 'ActivityX' / 'activity_tracker'
    else:
        base = Path.home() / '.local' / 'share'
        tracker_path = base / 'ActivityX' / 'activity_tracker'
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




STALE_THRESHOLD_SECONDS = 600  # 10 minutes
GITHUB_REPO = "Orceus/activityx-tracker-v2"
UPDATE_CHECK_INTERVAL = 3600  # 1 hour
MAX_CRASH_COUNT = 3


def _get_log_dir_for_update():
    if sys.platform == 'win32':
        base = Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData' / 'Local'))
    elif sys.platform == 'darwin':
        base = Path.home() / 'Library' / 'Application Support'
    else:
        base = Path.home() / '.local' / 'share'
    d = base / 'ActivityX'
    d.mkdir(parents=True, exist_ok=True)
    return d


_UPDATE_DIR = _get_log_dir_for_update()


def get_local_version():
    for base in [_UPDATE_DIR, Path(os.path.dirname(sys.executable if getattr(sys, 'frozen', False) else os.path.abspath(__file__)))]:
        version_path = base / 'version.txt'
        try:
            if version_path.exists():
                return version_path.read_text().strip()
        except Exception:
            pass
    return "v0.0.0"


def _get_ssl_context():
    """Get an SSL context that works in PyInstaller builds."""
    import ssl
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except (ImportError, Exception):
        pass
    if sys.platform == 'win32':
        try:
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            ctx.load_default_certs(purpose=ssl.Purpose.SERVER_AUTH)
            return ctx
        except Exception:
            pass
    try:
        return ssl.create_default_context()
    except Exception:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx


def check_and_update():
    try:
        import urllib.request
        import urllib.error
        import shutil

        local_version = get_local_version()
        logging.info("Checking for updates... current: %s", local_version)

        ssl_ctx = _get_ssl_context()
        url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
        req = urllib.request.Request(url, headers={"Accept": "application/vnd.github.v3+json"})
        with urllib.request.urlopen(req, timeout=15, context=ssl_ctx) as resp:
            release = json.loads(resp.read().decode())

        remote_version = release.get("tag_name", "")
        if not remote_version or remote_version <= local_version:
            logging.info("Already up to date (%s)", local_version)
            return False

        logging.info("New version available: %s → %s", local_version, remote_version)

        tracker_asset = None
        for asset in release.get("assets", []):
            if asset["name"] == "activity_tracker.exe":
                tracker_asset = asset

        if not tracker_asset:
            logging.warning("No activity_tracker.exe in release %s", remote_version)
            return False

        tracker_path = _UPDATE_DIR / 'activity_tracker.exe'
        backup_path = _UPDATE_DIR / 'activity_tracker.exe.backup'
        if tracker_path.exists():
            try:
                shutil.copy2(str(tracker_path), str(backup_path))
            except Exception:
                pass

        kill_process('activity_tracker.exe')
        time.sleep(3)

        temp_path = _UPDATE_DIR / 'activity_tracker.exe.tmp'
        download_req = urllib.request.Request(tracker_asset["browser_download_url"])
        with urllib.request.urlopen(download_req, context=ssl_ctx) as dl_resp:
            with open(str(temp_path), 'wb') as dl_file:
                dl_file.write(dl_resp.read())

        if temp_path.stat().st_size < 1_000_000:
            logging.error("Downloaded file too small, aborting")
            temp_path.unlink()
            start_activity_tracker()
            return False

        if tracker_path.exists():
            tracker_path.unlink()
        temp_path.rename(tracker_path)

        version_path = _UPDATE_DIR / 'version.txt'
        version_path.write_text(remote_version)

        start_activity_tracker()
        logging.info("Updated tracker to %s", remote_version)

        # Also download new controller for next restart
        controller_asset = None
        for asset in release.get("assets", []):
            if asset["name"] == "activity_tracker_controller.exe":
                controller_asset = asset
        if controller_asset:
            try:
                controller_new = _UPDATE_DIR / 'activity_tracker_controller.exe.new'
                ctrl_req = urllib.request.Request(controller_asset["browser_download_url"])
                with urllib.request.urlopen(ctrl_req, context=ssl_ctx) as ctrl_resp:
                    with open(str(controller_new), 'wb') as ctrl_file:
                        ctrl_file.write(ctrl_resp.read())
                logging.info("Downloaded new controller, will apply on next restart")
            except Exception as e:
                logging.warning("Failed to download new controller: %s", e)

        return True

    except Exception as e:
        logging.error("Update check error: %s", e, exc_info=True)
        return False


def record_crash():
    crash_path = _UPDATE_DIR / 'crash_count.txt'
    try:
        with open(crash_path, 'a') as f:
            f.write(f"{time.time()}\n")
    except Exception:
        pass


def check_crash_and_rollback():
    backup_path = _UPDATE_DIR / 'activity_tracker.exe.backup'
    tracker_path = _UPDATE_DIR / 'activity_tracker.exe'
    crash_path = _UPDATE_DIR / 'crash_count.txt'
    if not backup_path.exists():
        return
    try:
        if crash_path.exists():
            content = crash_path.read_text().strip().split('\n')
            recent = [float(t) for t in content if time.time() - float(t) < 300]
            if len(recent) >= MAX_CRASH_COUNT:
                logging.critical("Tracker crashed %d times! Rolling back...", len(recent))
                kill_process('activity_tracker.exe')
                time.sleep(2)
                import shutil
                shutil.copy2(str(backup_path), str(tracker_path))
                crash_path.unlink(missing_ok=True)
                start_activity_tracker()
    except Exception as e:
        logging.error("Rollback error: %s", e)


def kill_process(process_name):
    """Force-kill a process by name"""
    try:
        subprocess.call(
            ['taskkill', '/F', '/IM', process_name],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        logging.info("Force-killed %s", process_name)
        return True
    except Exception as e:
        logging.error("Failed to kill %s: %s", process_name, e)
        return False


def check_last_alive():
    """Check if tracker is actually producing data (not zombie)."""
    if sys.platform == 'win32':
        base = Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData' / 'Local'))
    elif sys.platform == 'darwin':
        base = Path.home() / 'Library' / 'Application Support'
    else:
        base = Path.home() / '.local' / 'share'
    alive_path = base / 'ActivityX' / 'last_alive.txt'

    if not alive_path.exists():
        return False
    try:
        from datetime import datetime
        content = alive_path.read_text().strip()
        last_alive = datetime.fromisoformat(content)
        age_seconds = (datetime.now() - last_alive).total_seconds()
        if age_seconds > STALE_THRESHOLD_SECONDS:
            logging.warning("last_alive.txt is %.0f seconds old (threshold: %d)", age_seconds, STALE_THRESHOLD_SECONDS)
            return False
        return True
    except Exception as e:
        logging.error("Error reading last_alive.txt: %s", e)
        return False


def _get_pc_name():
    try:
        cfg = _load_config()
        return cfg.get_user_id()
    except Exception:
        import platform
        return f"{os.environ.get('USERNAME', os.environ.get('USER', 'user'))}@{platform.node()}"


def _read_last_lines(file_path, n=100):
    try:
        if not file_path.exists():
            return ""
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
        return "".join(lines[-n:])
    except Exception:
        return ""


def _get_log_dir():
    if sys.platform == 'win32':
        base = Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData' / 'Local'))
    elif sys.platform == 'darwin':
        base = Path.home() / 'Library' / 'Application Support'
    else:
        base = Path.home() / '.local' / 'share'
    return base / 'ActivityX'


def upload_logs_to_supabase():
    supabase_client = init_supabase_client()
    # Update tracker version on employee record
    try:
        if supabase_client:
            pc_name_for_version = _get_pc_name()
            supabase_client.table("employees").update({
                "tracker_version": get_local_version()
            }).eq("pc_name", pc_name_for_version).execute()
    except Exception:
        pass
    if not supabase_client:
        return
    log_dir = _get_log_dir()
    pc_name = _get_pc_name()
    tracker_running = is_process_running('activity_tracker.exe')
    last_alive = None
    try:
        alive_path = log_dir / 'last_alive.txt'
        if alive_path.exists():
            last_alive = alive_path.read_text().strip()
    except Exception:
        pass

    law_firm_id = LAW_FIRM_ID

    for log_type, filename, lines in [('tracker', 'tracker.log', 100), ('controller', 'controller.log', 50)]:
        content = _read_last_lines(log_dir / filename, lines)
        if content:
            try:
                supabase_client.table("tracker_logs").insert({
                    'law_firm_id': law_firm_id,
                    'pc_name': pc_name,
                    'log_type': log_type,
                    'log_content': content,
                    'last_alive': last_alive,
                    'tracker_running': tracker_running,
                }).execute()
                logging.info("Uploaded %s log to Supabase", log_type)
            except Exception as e:
                logging.error("Failed to upload %s log: %s", log_type, e)


def _ensure_scheduled_tasks():
    """Always register Windows Scheduled Tasks pointing to current exe."""
    if sys.platform != 'win32':
        return
    try:
        exe_path = sys.executable if getattr(sys, 'frozen', False) else os.path.abspath(__file__)
        subprocess.call(
            ['schtasks', '/Create', '/TN', 'ActivityX Controller',
             '/TR', f'"{exe_path}"', '/SC', 'MINUTE', '/MO', '5', '/F'],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        subprocess.call(
            ['schtasks', '/Create', '/TN', 'ActivityX Controller Startup',
             '/TR', f'"{exe_path}"', '/SC', 'ONLOGON', '/F'],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        logging.info("Registered Windows Scheduled Tasks → %s", exe_path)
    except Exception as e:
        logging.error("Failed to register scheduled tasks: %s", e)


def main():
    if sys.platform == 'win32':
        import ctypes
        ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)

    logging.info("Controller started")
    _ensure_scheduled_tasks()
    # Check if a new controller was downloaded — swap and restart
    if sys.platform == 'win32':
        new_controller = _UPDATE_DIR / 'activity_tracker_controller.exe.new'
        if new_controller.exists() and new_controller.stat().st_size > 1_000_000:
            try:
                current_exe = Path(sys.executable)
                import shutil
                shutil.copy2(str(new_controller), str(current_exe))
                new_controller.unlink()
                logging.info("Controller updated, restarting...")
                os.execv(str(current_exe), [str(current_exe)])
            except Exception as e:
                logging.error("Controller self-update failed: %s", e)
    # Report version immediately on startup
    try:
        _sb = init_supabase_client()
        if _sb:
            _sb.table("employees").update({
                "tracker_version": get_local_version()
            }).eq("pc_name", _get_pc_name()).execute()
    except Exception:
        pass
    time.sleep(60)

    last_batch_upload = time.time()
    last_log_upload = time.time()
    last_update_check = 0
    last_tracker_start = time.time()  # Grace period for stale check
    batch_upload_interval = 180
    log_upload_interval = 1800

    while True:
        try:
            current_time = time.time()

            process_running = is_process_running('activity_tracker.exe')
            # Only check staleness after tracker has had time to sync (10 min grace)
            tracker_healthy = check_last_alive() if (current_time - last_tracker_start > STALE_THRESHOLD_SECONDS) else True

            if not process_running:
                logging.warning("activity_tracker.exe not running, restarting...")
                record_crash()
                check_crash_and_rollback()
                start_activity_tracker()
                last_tracker_start = time.time()
            elif process_running and not tracker_healthy:
                logging.warning("Tracker process alive but stale. Force-killing...")
                kill_process('activity_tracker.exe')
                time.sleep(5)
                start_activity_tracker()
                last_tracker_start = time.time()

            # Auto-update check every hour
            if current_time - last_update_check >= UPDATE_CHECK_INTERVAL:
                try:
                    check_and_update()
                except Exception:
                    pass
                last_update_check = current_time

            if current_time - last_batch_upload >= batch_upload_interval:
                try:
                    upload_optimized_batches()
                except Exception:
                    pass
                last_batch_upload = current_time

            if current_time - last_log_upload >= log_upload_interval:
                try:
                    upload_logs_to_supabase()
                except Exception:
                    pass
                last_log_upload = current_time

            time.sleep(30)

        except Exception as e:
            logging.error("Error in controller main loop: %s", e, exc_info=True)
            time.sleep(30)
            continue


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        logging.critical("Controller fatal error: %s", e, exc_info=True)
        while True:
            time.sleep(60)
