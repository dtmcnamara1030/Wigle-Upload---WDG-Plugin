import json
import logging
import threading
import time
from pathlib import Path
import requests

from plugins.plugin_base import PluginBase, PluginMenuItem
from watchdogs.config import WIGLE_API_NAME, WIGLE_API_TOKEN, WIGLE_API_URL

log = logging.getLogger(__name__)


class WigleUpload(PluginBase):
    NAME = "Watch Dogs Go WiGLE Sync"
    VERSION = "1.0"
    AUTHOR = "Antigravity"

    def __init__(self):
        super().__init__()
        self.has_overlay = True
        self._uploading = False
        self._log: list[tuple[str, int]] = []
        self.overlay_active = False
        self._menu_sel = 0
        self._uploaded_sessions: set[str] = set()
        self._load_state()

    def menu_items(self) -> list[PluginMenuItem]:
        return [
            PluginMenuItem("i", "WiGLE Sync", "open_overlay"),
        ]

    def open_overlay(self):
        self.overlay_active = True
        self._menu_sel = 0
        if not WIGLE_API_NAME or not WIGLE_API_TOKEN:
            self._log_add("WiGLE credentials missing!", 8)
            self._log_add("Add WDG_WIGLE_NAME and WDG_WIGLE_TOKEN to secrets.conf", 13)
        else:
            self._log_add("WiGLE Sync plugin active", 11)
            # Auto-test connection on open
            self._test_api()
        
        n = len(self._pending_sessions())
        self._log_add(f"{n} session(s) pending upload", 13)

    def on_update(self) -> None:
        if not self.overlay_active:
            return
        import pyxel

        if pyxel.btnp(pyxel.KEY_ESCAPE):
            self.overlay_active = False
            if self.app:
                self.app._esc_consumed_frame = pyxel.frame_count
            return

        items = self._overlay_items()
        if pyxel.btnp(pyxel.KEY_UP) and self._menu_sel > 0:
            self._menu_sel -= 1
        if pyxel.btnp(pyxel.KEY_DOWN):
            self._menu_sel = min(self._menu_sel + 1, len(items) - 1)
        if pyxel.btnp(pyxel.KEY_RETURN) and items:
            action = items[min(self._menu_sel, len(items) - 1)][0]
            self._exec(action)

    def _overlay_items(self) -> list[tuple[str, str]]:
        n = len(self._pending_sessions())
        return [
            ("upload_all", f"Upload All ({n} pending)"),
            ("upload_latest", "Upload Latest Session"),
            ("test_api", "Test WiGLE Credentials"),
            ("show_pending", "Show Pending Sessions"),
            ("reset", "Reset Upload History"),
        ]

    def _exec(self, action: str):
        if action == "upload_all":
            self._start_upload(all_sessions=True)
        elif action == "upload_latest":
            self._start_upload(all_sessions=False)
        elif action == "test_api":
            self._test_api()
        elif action == "show_pending":
            sessions = self._pending_sessions()
            if not sessions:
                self._log_add("No pending sessions.", 13)
            for s in sessions:
                self._log_add(f"  {s.name}", 13)
        elif action == "reset":
            self._uploaded_sessions.clear()
            self._save_state()
            self._log_add("Upload history reset", 10)

    def draw(self, x: int, y: int, w: int, h: int) -> None:
        if not self.overlay_active:
            return
        import pyxel

        # Draw black background
        pyxel.rect(0, 0, w, h, 0)

        # Title bar
        pyxel.rect(0, 0, w, 12, 1)
        pyxel.text(4, 3, "WATCH DOGS GO — WiGLE SYNC", 11)
        creds_ok = bool(WIGLE_API_NAME and WIGLE_API_TOKEN)
        status_txt = "READY" if creds_ok else "NO CREDS"
        status_col = 11 if creds_ok else 8
        pyxel.text(w - 60, 3, status_txt, status_col)

        # Left Menu panel
        items = self._overlay_items()
        cy = 20
        for i, (action, label) in enumerate(items):
            sel = i == self._menu_sel
            c = 7 if sel else 13
            prefix = "\x10" if sel else " "
            pyxel.text(4, cy, f"{prefix} {label}", c)
            cy += 12

        # Right Log panel
        lx = 180
        pyxel.line(lx - 4, 14, lx - 4, h - 16, 1)
        pyxel.text(lx, 16, "-- Sync Log --", 3)
        ly = 28
        max_lines = (h - 44) // 8
        for text, color in self._log[-max_lines:]:
            pyxel.text(lx, ly, text[:26], color) # fit text in narrow right column
            ly += 8

        # Footer
        pyxel.text(4, h - 22, f"Total Uploaded: {len(self._uploaded_sessions)} sessions", 13)
        pyxel.text(4, h - 12, "[ENTER] Execute  [ESC] Back", 13)

    # ------------------------------------------------------------------
    # Data Detection
    # ------------------------------------------------------------------
    def _pending_sessions(self) -> list[Path]:
        if not self.app or not self.app.loot:
            return []
        base = Path(self.app.loot._base)
        pending = []
        if not base.is_dir():
            return []
        for d in sorted(base.iterdir()):
            if not d.is_dir():
                continue
            # Session must have a wardriving.csv
            csv_file = d / "wardriving.csv"
            if csv_file.is_file() and d.name not in self._uploaded_sessions:
                pending.append(d)
        return pending

    def _active_session_name(self) -> str:
        try:
            return Path(self.app.loot.session_path).name
        except Exception:
            return ""

    def _mark_uploaded(self, session_dir: Path) -> bool:
        if session_dir.name == self._active_session_name():
            return False
        self._uploaded_sessions.add(session_dir.name)
        self._save_state()
        return True

    # ------------------------------------------------------------------
    # WiGLE API Operations
    # ------------------------------------------------------------------
    def _test_api(self):
        if not WIGLE_API_NAME or not WIGLE_API_TOKEN:
            self._log_add("Credentials missing", 8)
            return
        self._log_add("Testing connection...", 3)
        threading.Thread(target=self._test_worker, daemon=True).start()

    def _test_worker(self):
        url = "https://api.wigle.net/api/v2/profile/user"
        auth = (WIGLE_API_NAME, WIGLE_API_TOKEN)
        headers = {"User-Agent": "WatchDogsGo-WiGLE-Sync"}
        try:
            resp = requests.get(url, auth=auth, headers=headers, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("success"):
                    username = data.get("userid") or data.get("userName") or "Unknown"
                    self._log_add(f"API OK: {username}", 11)
                else:
                    self._log_add(f"API Err: {data.get('error', 'unknown')}", 8)
            elif resp.status_code == 401:
                self._log_add("API Err: 401 Unauthorized", 8)
                self._log_add("Check API Name (starts AID) & Token in secrets.conf", 8)
            else:
                self._log_add(f"API Err: HTTP {resp.status_code}", 8)
        except Exception as e:
            self._log_add(f"Conn Failed: {str(e)[:20]}", 8)

    def _start_upload(self, all_sessions: bool = True):
        if not WIGLE_API_NAME or not WIGLE_API_TOKEN:
            self._log_add("Credentials missing!", 8)
            return
        if self._uploading:
            self._log_add("Upload in progress...", 10)
            return
        sessions = self._pending_sessions()
        if not all_sessions and sessions:
            sessions = sessions[-1:]
        if not sessions:
            self._log_add("No pending files", 10)
            return
        self._uploading = True
        threading.Thread(target=self._upload_worker, args=(sessions,), daemon=True).start()

    def _upload_worker(self, sessions: list[Path]):
        total = len(sessions)
        success_count = 0
        
        for i, session_dir in enumerate(sessions):
            csv_path = session_dir / "wardriving.csv"
            self._log_add(f"[{i+1}/{total}] Uploading...", 3)
            
            url = WIGLE_API_URL or "https://api.wigle.net/api/v2/file/upload"
            auth = (WIGLE_API_NAME, WIGLE_API_TOKEN)
            headers = {"User-Agent": "WatchDogsGo-WiGLE-Sync"}
            
            try:
                custom_filename = f"WDG_{session_dir.name}_Wigle.csv"
                with open(csv_path, "rb") as f:
                    files = {"file": (custom_filename, f, "text/csv")}
                    resp = requests.post(url, files=files, auth=auth, headers=headers, timeout=60)
                
                if resp.status_code == 200:
                    try:
                        data = resp.json()
                        if data.get("success"):
                            # Parse transId from the nested results structure
                            transid = "N/A"
                            try:
                                results = data.get("results", {})
                                transids = results.get("transids", [])
                                if transids and isinstance(transids, list):
                                    transid = transids[0].get("transId", "N/A")
                            except Exception:
                                pass
                            
                            self._log_add(f"  OK: ID {transid[:8]}", 11)
                            
                            # Check for anonymous upload warning
                            if data.get("observer") == "anonymous":
                                self._log_add("  Warning: Anonymous upload!", 8)
                                self._log_add("  Check secrets.conf credentials", 8)
                                
                            success_count += 1
                            if not self._mark_uploaded(session_dir):
                                self._log_add("  (active: kept open)", 13)
                        else:
                            self._log_add(f"  Err: {data.get('error', 'unknown')}", 8)
                    except Exception:
                        self._log_add(f"  OK (status 200)", 11)
                        success_count += 1
                        self._mark_uploaded(session_dir)
                elif resp.status_code == 401:
                    self._log_add("  Err: 401 Unauthorized", 8)
                    break # Credentials failed, stop uploads
                else:
                    self._log_add(f"  Err: HTTP {resp.status_code}", 8)
            except Exception as e:
                self._log_add(f"  Failed: {str(e)[:20]}", 8)
            
            if i < total - 1:
                time.sleep(1) # simple rate limit buffer

        self._log_add(f"Finished: {success_count}/{total} files", 11 if success_count == total else 10)
        self._uploading = False

    # ------------------------------------------------------------------
    # State Persistence
    # ------------------------------------------------------------------
    def _state_file(self) -> Path:
        return Path(__file__).parent / ".wigle_upload_state.json"

    def _load_state(self):
        p = self._state_file()
        if p.is_file():
            try:
                data = json.loads(p.read_text())
                self._uploaded_sessions = set(data.get("uploaded", []))
            except Exception:
                pass

    def _save_state(self):
        try:
            self._state_file().write_text(json.dumps({
                "uploaded": sorted(self._uploaded_sessions),
            }))
        except Exception:
            pass

    def _log_add(self, text: str, color: int = 13):
        self._log.append((text, color))
        if len(self._log) > 100:
            self._log = self._log[-100:]
        self.term(text)
        # Mirror to main game log file
        if color in (8, 10):
            log.warning(f"WiGLE: {text}")
        else:
            log.info(f"WiGLE: {text}")
