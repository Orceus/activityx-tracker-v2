import subprocess
import time
import os
import sys
import json
import shutil
import tempfile
import zipfile
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError

UPDATE_SERVER_URL = "https://activityx-update-server-production.up.railway.app"
UPDATE_CHECK_INTERVAL = 2 * 60  # 2 minutes (temporary for testing, revert to 6*60*60)

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
        # Convert time-only strings (HH:MM:SS) to full timestamptz (YYYY-MM-DDTHH:MM:SS)
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


def get_install_dir():
    """Get the ActivityX install directory."""
    if sys.platform == 'win32':
        base = Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData' / 'Local'))
    elif sys.platform == 'darwin':
        base = Path.home() / 'Library' / 'Application Support'
    else:
        base = Path.home() / '.local' / 'share'
    return base / 'ActivityX'


def get_current_version():
    """Read the current version from version.txt."""
    version_file = get_install_dir() / 'version.txt'
    try:
        return version_file.read_text().strip()
    except Exception:
        return "0.0.0"


def check_for_update():
    """Check the update server for a newer version. Returns (version, assets) or None."""
    try:
        req = Request(f"{UPDATE_SERVER_URL}/version.json", headers={"User-Agent": "ActivityX-Monitor"})
        with urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
        remote_version = data.get("version", "0.0.0")
        current_version = get_current_version()
        if remote_version != current_version:
            print(f"Update available: {current_version} -> {remote_version}")
            return data
        return None
    except Exception as e:
        print(f"Update check failed: {e}")
        return None


def download_file(url, dest_path):
    """Download a file from the update server."""
    full_url = f"{UPDATE_SERVER_URL}{url}"
    req = Request(full_url, headers={"User-Agent": "ActivityX-Monitor"})
    with urlopen(req, timeout=300) as resp:
        with open(dest_path, 'wb') as f:
            while True:
                chunk = resp.read(65536)
                if not chunk:
                    break
                f.write(chunk)


def kill_tracker():
    """Stop the activity tracker process."""
    if sys.platform == 'win32':
        try:
            subprocess.run(
                ['taskkill', '/F', '/IM', 'activity_tracker.exe'],
                stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
        except Exception:
            pass
    time.sleep(2)


def apply_update(update_data):
    """Download and apply an update. Returns True on success."""
    install_dir = get_install_dir()
    backup_dir = install_dir / '_backup'
    version = update_data.get("version", "unknown")

    # Find the Windows zip asset
    assets = update_data.get("assets", {})
    zip_name = None
    for name in assets:
        if "Windows" in name and name.endswith(".zip"):
            zip_name = name
            break

    if not zip_name:
        print("No Windows zip found in release assets")
        return False

    try:
        # Download to temp
        tmp_dir = Path(tempfile.mkdtemp(prefix="activityx_update_"))
        zip_path = tmp_dir / zip_name
        print(f"Downloading update {version}...")
        download_file(assets[zip_name]["url"], zip_path)

        # Extract
        print("Extracting update...")
        extract_dir = tmp_dir / "extracted"
        with zipfile.ZipFile(zip_path, 'r') as zf:
            zf.extractall(extract_dir)

        # Find the actual files (may be inside a windows/ subfolder)
        source_dir = extract_dir
        for sub in extract_dir.iterdir():
            if sub.is_dir():
                source_dir = sub
                break

        # Verify key files exist in the download
        tracker_name = "activity_tracker.exe" if sys.platform == 'win32' else "activity_tracker"
        if not (source_dir / tracker_name).exists():
            print(f"Update package missing {tracker_name}, aborting")
            shutil.rmtree(tmp_dir, ignore_errors=True)
            return False

        # Stop tracker before swapping files
        kill_tracker()

        # Backup current files (only exe and version.txt)
        backup_dir.mkdir(exist_ok=True)
        files_to_update = [tracker_name, 'version.txt']
        controller_name = "activity_tracker_controller.exe" if sys.platform == 'win32' else "activity_tracker_controller"
        if (source_dir / controller_name).exists():
            files_to_update.append(controller_name)

        for fname in files_to_update:
            src = install_dir / fname
            if src.exists():
                try:
                    shutil.copy2(src, backup_dir / fname)
                except Exception:
                    pass

        # Copy new files (don't overwrite config.py)
        for item in source_dir.iterdir():
            if item.name == 'config.py':
                continue  # Never overwrite client config
            dest = install_dir / item.name
            try:
                if item.is_dir():
                    if dest.exists():
                        shutil.rmtree(dest)
                    shutil.copytree(item, dest)
                else:
                    shutil.copy2(item, dest)
            except Exception as e:
                print(f"Failed to copy {item.name}: {e}")

        # Clean up temp
        shutil.rmtree(tmp_dir, ignore_errors=True)

        print(f"Update {version} applied successfully")

        # Re-apply Windows security exclusions for new executables
        if sys.platform == 'win32':
            try:
                # Remove "downloaded from internet" block flag from all exe files
                subprocess.run(
                    ['powershell', '-ExecutionPolicy', 'Bypass', '-Command',
                     f"Get-ChildItem '{install_dir}' -Recurse | Unblock-File"],
                    capture_output=True, timeout=10,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                # Re-apply Defender exclusion
                subprocess.run(
                    ['powershell', '-ExecutionPolicy', 'Bypass', '-Command',
                     f"Add-MpPreference -ExclusionPath '{install_dir}'"],
                    capture_output=True, timeout=10,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                # Re-add firewall rules for updated executables
                tracker_exe = str(install_dir / 'activity_tracker.exe')
                controller_exe = str(install_dir / 'activity_tracker_controller.exe')
                for name, exe in [("ActivityX Tracker", tracker_exe), ("ActivityX Controller", controller_exe)]:
                    subprocess.run(['netsh', 'advfirewall', 'firewall', 'delete', 'rule', f'name={name}'],
                                   capture_output=True, timeout=10, creationflags=subprocess.CREATE_NO_WINDOW)
                    for direction in ['out', 'in']:
                        subprocess.run(['netsh', 'advfirewall', 'firewall', 'add', 'rule',
                                        f'name={name}', f'dir={direction}', 'action=allow', f'program={exe}'],
                                       capture_output=True, timeout=10, creationflags=subprocess.CREATE_NO_WINDOW)
            except Exception:
                pass  # Non-critical — rules may already exist

        # Restart tracker
        start_activity_tracker()
        return True

    except Exception as e:
        print(f"Update failed: {e}")
        # Attempt rollback
        if backup_dir.exists():
            print("Rolling back...")
            for item in backup_dir.iterdir():
                try:
                    shutil.copy2(item, install_dir / item.name)
                except Exception:
                    pass
            shutil.rmtree(backup_dir, ignore_errors=True)
        start_activity_tracker()
        return False


def main():
    if sys.platform == 'win32':
        import ctypes
        ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)

    time.sleep(60)

    last_batch_upload = time.time()
    batch_upload_interval = 180  # 3 minutes
    last_update_check = 0  # Check on first loop iteration

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

            # Auto-update check
            if current_time - last_update_check >= UPDATE_CHECK_INTERVAL:
                try:
                    update_data = check_for_update()
                    if update_data:
                        apply_update(update_data)
                except Exception as e:
                    print(f"Update error: {e}")
                last_update_check = current_time

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
