import os
import sys
import json
import threading
import subprocess
from pathlib import Path
from datetime import datetime, timedelta

import tkinter as tk
from tkinter import END, ttk, filedialog, messagebox

from pystray import Icon, Menu, MenuItem
from PIL import Image, ImageTk

import ctypes

# ----------------------------
# Constants / Files
# ----------------------------
APP_TITLE = "Maurice"
SCHEDULE_FILE = Path("schedules.json")
LOG_FILE = Path("log.txt")

DT_FORMAT = "%Y-%m-%d %H:%M"

tray_icon = None
_tray_img_small = None
_tray_img_large = None


# ----------------------------
# Helpers
# ----------------------------
def log_line(msg: str) -> None:
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
            g_71.insert(tk.END, f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
            g_71.see(tk.END)
    except Exception:
        pass


def parse_dt(s: str) -> datetime:
    return datetime.strptime(s.strip(), DT_FORMAT)


def fmt_dt(dt: datetime) -> str:
    return dt.strftime(DT_FORMAT)


def atomic_write_json(path: Path, data) -> None:
    path = Path(path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp.replace(path)


def read_json_list(path: Path) -> list[dict]:
    if not path.exists():
        return []
    raw = path.read_text(encoding="utf-8")
    if not raw.strip():
        return []
    data = json.loads(raw)
    return data if isinstance(data, list) else []


def short_path(p: str, max_len: int = 35) -> str:
    p = p or ""
    if len(p) <= max_len:
        return p
    base = os.path.basename(p)
    if len(base) >= max_len:
        return base[: max_len - 1] + "…"
    tail_len = max_len - len(base) - 1
    return f"{base}…{p[-tail_len:]}"


def add_month(dt: datetime) -> datetime:
    y, m = dt.year, dt.month
    m += 1
    if m == 13:
        y += 1
        m = 1

    # last day of new month
    if m == 12:
        first_next = datetime(y + 1, 1, 1)
    else:
        first_next = datetime(y, m + 1, 1)
    last_day = (first_next - timedelta(days=1)).day

    day = min(dt.day, last_day)
    return dt.replace(year=y, month=m, day=day)


def compute_next_run(prev_scheduled: datetime, frequency: str) -> datetime:
    """
    IMPORTANT: advance based on the scheduled time (prev_scheduled), not now,
    so cadence stays the same even if runs were delayed/missed.
    """
    f = (frequency or "").strip().lower()
    if f == "daily":
        return prev_scheduled + timedelta(days=1)
    if f == "weekly":
        return prev_scheduled + timedelta(days=7)
    if f == "monthly":
        return add_month(prev_scheduled)
    # default fallback
    return prev_scheduled + timedelta(days=1)


def run_script(filepath: str) -> None:
    try:
        subprocess.Popen(
            [sys.executable, filepath],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        log_line(f"Started: {filepath}")
    except Exception as e:
        log_line(f"Failed to start {filepath}: {e}")

# ----------------------------
# Anti-lock: move mouse a tiny bit every minute
# ----------------------------
def _get_mouse_pos() -> tuple[int, int]:
    class POINT(ctypes.Structure):
        _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

    pt = POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
    return int(pt.x), int(pt.y)


def _set_mouse_pos(x: int, y: int) -> None:
    ctypes.windll.user32.SetCursorPos(int(x), int(y))


def start_mouse_jiggler(interval_seconds: int = 60) -> threading.Event:
    """
    Moves the mouse cursor by 1px and back every `interval_seconds`.
    Returns a stop Event you can set() when exiting.
    Windows only (uses user32).
    """
    stop_evt = threading.Event()

    def _loop():
        while not stop_evt.is_set():
            try:
                x, y = _get_mouse_pos()
                _set_mouse_pos(x + 1, y)
                _set_mouse_pos(x, y)
            except Exception as e:
                log_line(f"Mouse jiggler error: {e}")

            stop_evt.wait(interval_seconds)

    t = threading.Thread(target=_loop, daemon=True)
    t.start()
    return stop_evt

# ----------------------------
# Catch-up missed tasks (ON OPEN)
# ----------------------------
def catch_up_missed_tasks(schedules: list[dict]) -> tuple[list[dict], bool]:
    """
    If next_run < now:
      - run the task ONCE immediately
      - set last_run to now
      - advance next_run forward in steps from the original next_run until it's in the future
        (cadence behaves as if runs were never missed)
    """
    now = datetime.now()
    changed = False

    for job in schedules:
        if not isinstance(job, dict):
            continue

        name = str(job.get("name", "")).strip()
        frequency = str(job.get("frequency", "")).strip()
        next_run_s = str(job.get("next_run", "")).strip()
        filepath = str(job.get("filepath", "")).strip()

        if not (name and frequency and next_run_s and filepath):
            continue
        if not Path(filepath).exists():
            continue

        try:
            scheduled = parse_dt(next_run_s)
        except Exception:
            continue

        if scheduled < now:
            # Run ONCE now because it was missed
            run_script(filepath)
            job["last_run"] = fmt_dt(now)

            # Advance next_run as if it kept running on schedule:
            # step from the scheduled time until next_run is in the future.
            nxt = scheduled
            while nxt <= now:
                nxt = compute_next_run(nxt, frequency)

            job["next_run"] = fmt_dt(nxt)
            changed = True

    return schedules, changed


# ----------------------------
# Scheduler Thread
# ----------------------------
class SimpleScheduler:
    def __init__(self):
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._thread = threading.Thread(target=self._loop, daemon=True)

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop.set()

    def _loop(self):
        while not self._stop.is_set():
            try:
                self.tick()
            except Exception as e:
                log_line(f"Scheduler tick error: {e}")
            self._stop.wait(1.0)

    def tick(self):
        with self._lock:
            schedules = read_json_list(SCHEDULE_FILE)

        now = datetime.now()
        changed = False

        for job in schedules:
            if not isinstance(job, dict):
                continue

            name = str(job.get("name", "")).strip()
            frequency = str(job.get("frequency", "")).strip()
            next_run_s = str(job.get("next_run", "")).strip()
            filepath = str(job.get("filepath", "")).strip()

            if not (name and frequency and next_run_s and filepath):
                continue
            if not Path(filepath).exists():
                continue

            try:
                next_run = parse_dt(next_run_s)
            except Exception:
                continue

            # Due now
            if next_run <= now:
                run_script(filepath)
                job["last_run"] = fmt_dt(now)

                # Keep cadence based on scheduled time
                nxt = compute_next_run(next_run, frequency)
                # If we were behind a while, advance until in the future (but only run once)
                while nxt <= now:
                    nxt = compute_next_run(nxt, frequency)

                job["next_run"] = fmt_dt(nxt)
                changed = True

        if changed:
            with self._lock:
                atomic_write_json(SCHEDULE_FILE, schedules)


scheduler = SimpleScheduler()


# ----------------------------
# GUI
# ----------------------------
root = tk.Tk()
root.title(APP_TITLE)
root.geometry("600x345")
root.resizable(False, False)

schedule: list[dict] = []


def load_images_once():
    global _tray_img_small, _tray_img_large
    try:
        if _tray_img_small is None:
            _tray_img_small = Image.open("maurice.png").resize((64, 64))
        if _tray_img_large is None:
            _tray_img_large = Image.open("L_maurice.png").resize((50, 50))
    except Exception as e:
        log_line(f"Image load error: {e}")


def minimize_to_tray():
    global tray_icon

    if tray_icon is not None:
        root.withdraw()
        return

    load_images_once()
    root.withdraw()

    def on_exit(icon, item):
        try:
            scheduler.stop()
        except Exception as e:
            log_line(f"Scheduler stop error: {e}")

        try:
            icon.visible = False
            icon.stop()
        except Exception:
            pass

        try:
            root.after(0, root.destroy)
        except Exception:
            pass

        try:
            mouse_jiggler_stop.set()
        except Exception:
            pass

        os._exit(0)

    def show_window(icon, item):
        global tray_icon
        root.after(0, root.deiconify)
        root.after(0, root.lift)
        root.after(0, root.focus_force)
        try:
            icon.visible = False
            icon.stop()
        except Exception:
            pass
        tray_icon = None

    image = _tray_img_small if _tray_img_small is not None else Image.new("RGBA", (64, 64), (0, 0, 0, 0))

    tray_icon = Icon(
        "Maurice",
        image,
        menu=Menu(
            MenuItem("Open", show_window),
            MenuItem("Exit", on_exit),
        ),
    )
    tray_icon.run_detached()


def open_about_window():
    if hasattr(open_about_window, "window") and open_about_window.window.winfo_exists():
        open_about_window.window.lift()
        return

    load_images_once()

    about = tk.Toplevel(root)
    open_about_window.window = about
    about.title("About Maurice")
    about.resizable(False, False)
    about.transient(root)
    about.grab_set()

    width, height = 420, 300
    x = root.winfo_x() + (root.winfo_width() // 2) - (width // 2)
    y = root.winfo_y() + (root.winfo_height() // 2) - (height // 2)
    about.geometry(f"{width}x{height}+{x}+{y}")

    container = tk.Frame(about, padx=20, pady=20)
    container.pack(fill="both", expand=True)

    if _tray_img_large is not None:
        photo = ImageTk.PhotoImage(_tray_img_large)
        logo = tk.Label(container, image=photo)
        logo.image = photo
        logo.pack(pady=(0, 10))

    tk.Label(container, text="Maurice", font=("Segoe UI", 16, "bold")).pack()
    tk.Label(
        container,
        text="A lightweight background python task scheduler\nMinimize to system tray.",
        justify="center",
        wraplength=360,
        pady=10,
    ).pack()
    tk.Label(
        container,
        text="Version 2.1\n© 2026 Maurice Project\nAuthor: David Z",
        font=("Segoe UI", 9),
        fg="gray",
        pady=10,
    ).pack()
    tk.Button(container, text="Close", width=10, command=about.destroy).pack(pady=(10, 0))


def browse_file():
    path = filedialog.askopenfilename(filetypes=[("Script Files", "*.py *.pyw")])
    if path:
        g_44.delete(0, tk.END)
        g_44.insert(0, path)


def open_log():
    try:
        os.startfile(str(LOG_FILE))
    except Exception as e:
        messagebox.showerror("Error", f"Could not open log file:\n{e}")


def open_readme():
    try:
        os.startfile("readme.txt")
    except Exception as e:
        messagebox.showerror("Error", f"Could not open readme.txt:\n{e}")


def open_config():
    try:
        if not SCHEDULE_FILE.exists():
            atomic_write_json(SCHEDULE_FILE, [])
        os.startfile(str(SCHEDULE_FILE))
    except Exception as e:
        messagebox.showerror("Error", f"Could not open config:\n{e}")
        return

    load_schedules()


def load_schedules():
    """Loads schedules into `schedule` and refreshes combobox. Shows popups if invalid."""
    global schedule
    try:
        data = read_json_list(SCHEDULE_FILE)
    except Exception:
        messagebox.showerror("Error", "schedules.json is invalid JSON.\nFix it or recreate it.")
        schedule = []
        g_11.set("")
        g_11["values"] = ()
        return

    normalized: list[dict] = []
    for job in data:
        if not isinstance(job, dict):
            continue
        if not all(k in job for k in ("name", "frequency", "next_run", "filepath", "last_run")):
            continue
        try:
            parse_dt(str(job["next_run"]))
        except Exception:
            continue
        try:
            parse_dt(str(job["last_run"]))
        except Exception:
            job["last_run"] = "1900-01-01 00:00"
        normalized.append(job)

    schedule = normalized
    g_11["values"] = tuple(task["name"] for task in schedule)


def load_schedules_silent():
    """Like load_schedules(), but no popups (safe to call repeatedly)."""
    global schedule
    try:
        data = read_json_list(SCHEDULE_FILE)
    except Exception:
        schedule = []
        g_11["values"] = ()
        return

    normalized: list[dict] = []
    for job in data:
        if not isinstance(job, dict):
            continue
        if not all(k in job for k in ("name", "frequency", "next_run", "filepath", "last_run")):
            continue
        try:
            parse_dt(str(job["next_run"]))
        except Exception:
            continue
        try:
            parse_dt(str(job["last_run"]))
        except Exception:
            job["last_run"] = "1900-01-01 00:00"
        normalized.append(job)

    schedule = normalized
    g_11["values"] = tuple(task["name"] for task in schedule)


def add_schedule_to_file():
    name = g_14.get().strip()
    frequency = g_24.get().strip()
    dt_str = g_34.get().strip()
    filepath = g_44.get().strip()

    if not name or not frequency or not dt_str or not filepath:
        messagebox.showerror("Error", "Please fill in all fields.")
        return

    try:
        next_run_dt = parse_dt(dt_str)
    except ValueError:
        messagebox.showerror("Error", f"Start time must match: {DT_FORMAT}")
        return

    if next_run_dt <= datetime.now():
        messagebox.showerror("Error", "Start time must be in the future.")
        return

    if not Path(filepath).exists():
        messagebox.showerror("Error", "Selected script path does not exist.")
        return

    new_task = {
        "name": name,
        "frequency": frequency,
        "next_run": fmt_dt(next_run_dt),
        "filepath": filepath,
        "last_run": "1900-01-01 00:00",
    }

    try:
        existing = read_json_list(SCHEDULE_FILE)
    except Exception:
        existing = []

    if any(isinstance(t, dict) and t.get("name") == name for t in existing):
        messagebox.showerror("Error", "A task with that name already exists.")
        return

    existing.append(new_task)

    try:
        atomic_write_json(SCHEDULE_FILE, existing)
    except Exception as e:
        messagebox.showerror("Error", f"Failed to save schedules.json:\n{e}")
        return

    g_14.delete(0, END)
    g_24.set("")
    g_34.delete(0, END)
    g_34.insert(0, "YYYY-MM-DD HH:MM")
    g_44.delete(0, END)

    load_schedules()


def task_selected(_event=None):
    sel = g_11.get().strip()
    if not sel:
        return
    for row in schedule:
        if row.get("name") == sel:
            g_22.config(text=row.get("frequency", "---"))
            g_32.config(text=row.get("next_run", "---"))
            g_42.config(text=short_path(row.get("filepath", "---")))
            g_52.config(text=row.get("last_run", "---"))
            return


def delete_task():
    sel = g_11.get().strip()
    if not sel:
        messagebox.showerror("Error", "No task selected.")
        return

    new_list = [t for t in schedule if t.get("name") != sel]

    try:
        atomic_write_json(SCHEDULE_FILE, new_list)
    except Exception as e:
        messagebox.showerror("Error", f"Failed to update schedules.json:\n{e}")
        return

    load_schedules()
    g_22.config(text="---")
    g_32.config(text="---")
    g_42.config(text="---")
    g_52.config(text="---")


def refresh_selected_task_ui():
    """Periodic UI refresh so g_32/g_52 reflect latest run times."""
    sel = g_11.get().strip()

    load_schedules_silent()

    if sel:
        for row in schedule:
            if row.get("name") == sel:
                g_22.config(text=row.get("frequency", "---"))
                g_32.config(text=row.get("next_run", "---"))
                g_42.config(text=short_path(row.get("filepath", "---")))
                g_52.config(text=row.get("last_run", "---"))
                break

    root.after(1000, refresh_selected_task_ui)


# ----------------------------
# Menu + Layout
# ----------------------------
menubar = tk.Menu(root)
file_menu = tk.Menu(menubar, tearoff=0)
file_menu.add_command(label="Open log", command=open_log)
file_menu.add_command(label="Open config", command=open_config)
file_menu.add_separator()
file_menu.add_command(label="Minimize to tray", command=minimize_to_tray)
file_menu.add_command(label="Exit", command=root.destroy)
menubar.add_cascade(label="File", menu=file_menu)

help_menu = tk.Menu(menubar, tearoff=0)
help_menu.add_command(label="Readme", command=open_readme)
help_menu.add_command(label="About Maurice", command=open_about_window)
menubar.add_cascade(label="Help", menu=help_menu)

root.config(menu=menubar)

g_11 = ttk.Combobox(root, values=[], width=36)
g_11.bind("<<ComboboxSelected>>", task_selected)

g_13 = tk.Label(root, text="Add new:", width=8)
g_14 = tk.Entry(root)

g_21 = tk.Label(root, text="Frequency:", width=8)
g_22 = tk.Label(root, text="---", anchor="w", width=28)

g_23 = tk.Label(root, text="Frequency:", width=8)
g_24 = ttk.Combobox(root, values=["Daily", "Weekly", "Monthly"], width=28)

g_31 = tk.Label(root, text="Start:", width=8)
g_32 = tk.Label(root, text="---", anchor="w", width=28)

g_33 = tk.Label(root, text="Start:", width=8)
g_34 = tk.Entry(root, justify="left")
g_34.insert(0, "YYYY-MM-DD HH:MM")

g_41 = tk.Label(root, text="Path:", width=8)
g_42 = tk.Label(root, text="---", anchor="w", width=28)

g_43 = tk.Label(root, text="Path:", width=8)
g_44 = tk.Entry(root)
g_45 = tk.Button(root, text="...", width=4, command=browse_file)

g_51 = tk.Label(root, text="Last run:", width=8)
g_52 = tk.Label(root, text="---", anchor="w", width=28)

g_61 = tk.Button(root, text="Delete", width=8, command=delete_task)
g_63 = tk.Button(root, text="Save", width=8, command=add_schedule_to_file)

g_71 = tk.Text(root, height=4, width=72)

g_11.grid(row=0, column=0, padx=10, pady=10, sticky="w", columnspan=2)
g_13.grid(row=0, column=2, padx=10, pady=10, sticky="w")
g_14.grid(row=0, column=3, padx=10, pady=10, sticky="ew", columnspan=2)

g_21.grid(row=1, column=0, padx=10, pady=10, sticky="w")
g_22.grid(row=1, column=1, padx=10, pady=10, sticky="w")

g_23.grid(row=1, column=2, padx=10, pady=10, sticky="w")
g_24.grid(row=1, column=3, padx=10, pady=10, sticky="ew", columnspan=2)

g_31.grid(row=2, column=0, padx=10, pady=10, sticky="w")
g_32.grid(row=2, column=1, padx=10, pady=10, sticky="w")

g_33.grid(row=2, column=2, padx=10, pady=10, sticky="w")
g_34.grid(row=2, column=3, padx=10, pady=10, sticky="ew", columnspan=2)

g_41.grid(row=3, column=0, padx=10, pady=10, sticky="w")
g_42.grid(row=3, column=1, padx=10, pady=10, sticky="w")

g_43.grid(row=3, column=2, padx=10, pady=10, sticky="w")
g_44.grid(row=3, column=3, padx=10, pady=10, sticky="w")
g_45.grid(row=3, column=4, padx=10, pady=10, sticky="w")

g_51.grid(row=4, column=0, padx=10, pady=10, sticky="e")
g_52.grid(row=4, column=1, padx=10, pady=10, sticky="w")

g_61.grid(row=5, column=0, padx=10, pady=10, sticky="e", columnspan=2)
g_63.grid(row=5, column=2, padx=10, pady=10, sticky="e", columnspan=3)

g_71.grid(row=6, column=0, padx=10, pady=10, sticky="ew", columnspan=5)


# ----------------------------
# Start-up behavior:
# 1) Load schedules
# 2) Catch up missed tasks ON OPEN
# 3) Start UI auto-refresh
# 4) Start scheduler loop
# ----------------------------
def startup_catch_up():
    try:
        schedules = read_json_list(SCHEDULE_FILE)
    except Exception:
        return

    schedules, changed = catch_up_missed_tasks(schedules)
    if changed:
        try:
            atomic_write_json(SCHEDULE_FILE, schedules)
        except Exception as e:
            log_line(f"Failed to write catch-up updates: {e}")


load_schedules()
startup_catch_up()          # <-- runs missed tasks once, advances next_run as if never missed
load_schedules()            # reload list after catch-up changes
refresh_selected_task_ui()  # keeps g_32/g_52 current
mouse_jiggler_stop = start_mouse_jiggler(60) # moves mouse every minute to prevent lock/sleep
scheduler.start()

root.protocol("WM_DELETE_WINDOW", minimize_to_tray)

def on_minimize(_event):
    if root.state() == "iconic":
        minimize_to_tray()

root.bind("<Unmap>", on_minimize)

root.mainloop()
