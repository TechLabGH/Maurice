import tkinter as tk
from tkinter import END, ttk, filedialog, messagebox
from pystray import Icon, Menu, MenuItem
from datetime import datetime
import numpy as np
import threading
import time
import os
import json
import subprocess
import sys
import signal
from PIL import Image, ImageTk

SCHEDULE_FILE = "schedules.json"
LOG_FILE = "log.txt"

tray_icon = None

root = tk.Tk()
root.title("Maurice")
root.geometry("600x345")
root.resizable(False, False)


def minimize_to_tray():
    global tray_icon

    # Don't create multiple tray icons if minimized more than once
    if tray_icon is not None:
        root.withdraw()
        return

    root.withdraw()

    def on_exit(icon, item):
        try:
            if scheduler.running:
                scheduler.shutdown(wait=False)
        except Exception as e:
            with open(LOG_FILE, "a", encoding="utf-8") as log:
                log.write(f"[{datetime.now()}] Scheduler shutdown error: {e}\n")

        try:
            icon.visible = False
            icon.stop()
        except Exception:
            pass

        # Clean shutdown of Tk
        try:
            root.after(0, root.destroy)
        except Exception:
            pass

        # Hard exit to ensure background threads/processes stop
        os._exit(0)

    def show_window(icon, item):
        global tray_icon
        # Restore Tk window on the Tk thread
        root.after(0, root.deiconify)
        root.after(0, root.lift)
        root.after(0, root.focus_force)

        # Remove tray icon
        try:
            icon.visible = False
            icon.stop()
        except Exception:
            pass

        tray_icon = None

    # Build tray image
    image = Image.open("maurice.png").resize((64, 64))

    tray_icon = Icon(
        "Maurice",
        image,
        menu=Menu(
            MenuItem("Open", show_window),
            MenuItem("Exit", on_exit),
        ),
    )

    # More reliable than manually threading tray_icon.run()
    tray_icon.run_detached()

def open_about_window():
    # Prevent multiple About windows
    if hasattr(open_about_window, "window") and open_about_window.window.winfo_exists():
        open_about_window.window.lift()
        return

    about = tk.Toplevel(root)
    open_about_window.window = about

    about.title("About Maurice")
    about.resizable(False, False)
    about.transient(root)
    about.grab_set()  # modal behavior

    # Center the window
    width, height = 420, 300
    x = root.winfo_x() + (root.winfo_width() // 2) - (width // 2)
    y = root.winfo_y() + (root.winfo_height() // 2) - (height // 2)
    about.geometry(f"{width}x{height}+{x}+{y}")

    container = tk.Frame(about, padx=20, pady=20)
    container.pack(fill="both", expand=True)

    # Load graphic
    
    img = Image.open("L_maurice.png").resize((50, 50))
    photo = ImageTk.PhotoImage(img)
    logo = tk.Label(container, image=photo)
    logo.image = photo  # keep reference
    logo.pack(pady=(0, 10))

    # Text content
    tk.Label(
        container,
        text="Maurice",
        font=("Segoe UI", 16, "bold"),
    ).pack()

    tk.Label(
        container,
        text="A lightweight background python task scheduler\nMinimalize to system tray.",
        justify="center",
        wraplength=360,
        pady=10,
    ).pack()

    tk.Label(
        container,
        text="Version 1.0\n© 2026 Maurice Project\nAuthor: David Z",
        font=("Segoe UI", 9),
        fg="gray",
        pady=10,
    ).pack()

    tk.Button(
        container,
        text="Close",
        width=10,
        command=about.destroy,
    ).pack(pady=(10, 0))

def browse_file():
    path = filedialog.askopenfilename(filetypes=[("Script Files", "*.py *.pyw")])
    if path:
        g_44.delete(0, tk.END)
        g_44.insert(0, path)

def open_log():
    #use os default program to open txt file
    os.startfile(LOG_FILE)

def open_readme():
    #use os default program to open txt file
    os.startfile("readme.txt")

def open_config():
    #use os default program to open json file
    os.startfile(SCHEDULE_FILE)

    if os.path.exists(SCHEDULE_FILE):
        try:
            with open(SCHEDULE_FILE, "r") as f:
                data = json.load(f)
            for job in data:
                if all(k in job for k in ("frequency", "datetime", "filepath")):
                    try:
                        datetime.strptime(job["datetime"], "%Y-%m-%d %H:%M")
                        schedule_task(job["frequency"], job["datetime"], job["filepath"])
                    except Exception as e:
                        with open(LOG_FILE, "a") as log_file:
                            log_file.write(f"[{datetime.now()}] Skipped invalid job: {job}, Reason: {e}\n")
        except Exception as e:
            with open(LOG_FILE, "a") as log_file:
                log_file.write(f"[{datetime.now()}] Failed to load jobs: {e}\n")

def add_schedule_to_file():
    # read entry values
    name = g_14.get()
    frequency = g_24.get()
    dt = g_34.get()
    filepath = g_44.get()

    # first run time needs to be in the future
    if dt < datetime.now().strftime("%Y-%m-%d %H:%M"):
        messagebox.showerror("Error", "Start time must be in the future.")
        return

    # all firlds need to be filled
    if not frequency or not dt or not filepath or not name:
        messagebox.showerror("Error", "Please fill in all fields.")
        return

    data = {"name": name, "frequency": frequency, "next_run": dt, "filepath": filepath, "last_run": "1900-01-01 00:00"}
    print(data)

    #read current schedule    
    if os.path.exists(SCHEDULE_FILE):
        with open(SCHEDULE_FILE, "r") as f:
            existing = json.load(f)
    else:
        existing = []

    #add new entry
    existing.append(data)

    #sabe back to file
    with open(SCHEDULE_FILE, "w") as f:
        f.truncate()
        json.dump(existing, f, indent=2)
        f.close()
    
    # clear entries
    g_14.delete(0, END)
    g_14.insert(0, "")
    g_24.delete(0, END)
    g_24.insert(0, "")
    g_34.delete(0, END)
    g_34.insert(0, "YYYY-MM-DD HH:MM")
    g_44.delete(0, END)
    g_44.insert(0, "")

    # refresh combobox with newly added schedule
    load_schedules()

def load_schedules():
    # check if schedule file exists
    if os.path.exists(SCHEDULE_FILE):
        with open(SCHEDULE_FILE, "r") as f:
            sched_json = json.load(f)
            
            # clear current schedule
            schedule.clear()

            # parse json into schedule array
            for tasks in sched_json:
                schedule.append(tasks)
            
            # array is empty - nothing loaded
            if np.shape(schedule)[0] == 0:
                messagebox.showinfo("Info", "Schedule file is empty or has broken structure")
                return
    # schedule fine not found
    else:
        messagebox.showinfo("Error", "Schedule file not found.\nPlease create it manually.\nSee readme for details.")
        return
    
    # at least one task loaded to array - update combobox
    if np.shape(schedule)[0] > 0:
        #clear selected task from combobox
        g_11.set("")
        #delete all current values
        g_11['values'] = ()
        #add new values from schedule array
        g_11['values'] = [task["name"] for task in schedule]

def task_selected(x):
    # convert to numpy array for easier handling
    sched_ar = np.array(schedule)
    sel_task = g_11.get()
    for row in sched_ar:
        if row["name"] == sel_task:
            g_22.config(text=row["frequency"])
            g_32.config(text=row["next_run"])
            g_42.config(text="..." + row["filepath"][-25:])
            g_52.config(text=row["last_run"])
            break
    
def delete_task():
    sel_task = g_11.get()
    if not sel_task:
        messagebox.showerror("Error", "No task selected.")
        return

    # Remove from schedule array
    global schedule
    schedule = [task for task in schedule if task["name"] != sel_task]

    # Save updated schedule to file
    with open(SCHEDULE_FILE, "w") as f:
        f.truncate()
        json.dump(schedule, f, indent=2)
        f.close()

    # Refresh combobox and clear details
    load_schedules()
    g_22.config(text="---")
    g_32.config(text="---")
    g_42.config(text="---")
    g_52.config(text="---")






# --- GUI Layout ---

# Menu Bar
menubar = tk.Menu(root)
file_menu = tk.Menu(menubar, tearoff=0)
file_menu.add_command(label="Open log",         command=open_log)
file_menu.add_command(label="Open config",      command=open_config)
file_menu.add_separator()
file_menu.add_command(label="Minimize to tray", command=minimize_to_tray)
file_menu.add_command(label="Exit",             command=root.destroy)
menubar.add_cascade(label="File", menu=file_menu)
about = tk.Menu(menubar, tearoff=0)
about.add_command(label="Readme",                command=open_readme)
about.add_command(label="About Maurice",         command=open_about_window)
menubar.add_cascade(label="Help", menu=about)
root.config(menu=menubar)

# Main window
g_11 = ttk.Combobox(root, values=[]                            , width=36)
g_11.bind("<<ComboboxSelected>>", task_selected)
g_13 = tk.Label(root, text="Add new:"                          , width=8)
g_14 = tk.Entry(root)
g_21 = tk.Label(root, text="Frequency:"                        , width=8)
g_22 = tk.Label(root, text="---", anchor="w"                   , width=28)
g_23 = tk.Label(root, text="Frequency:"                        , width=8)
g_24 = ttk.Combobox(root, values=["Daily", "Weekly", "Monthly"], width=28)
g_31 = tk.Label(root, text="Start:"                            , width=8)
g_32 = tk.Label(root, text="---", anchor="w"                   , width=28)
g_33 = tk.Label(root, text="Start:"                            , width=8)
g_34 = tk.Entry(root, justify="left")
g_34.insert(0, "YYYY-MM-DD HH:MM")
g_41 = tk.Label(root, text="Path:"                             , width=8)
g_42 = tk.Label(root, text="---", anchor="w"                   , width=28)
g_43 = tk.Label(root, text="Path:"                             , width=8)
g_44 = tk.Entry(root)
g_45 = tk.Button(root, text="..."                              , width=4, command=browse_file)
g_51 = tk.Label(root, text="Last run:"                         , width=8)
g_52 = tk.Label(root, text="---", anchor="w"                   , width=28)
g_61 = tk.Button(root, text="Delete"                           , width=8, command=delete_task)
g_63 = tk.Button(root, text="Save"                             , width=8, command=add_schedule_to_file)
g_71 = tk.Text(root, height=4                                  , width=72)

g_11.grid(row=0, column=0, padx=10, pady=10, sticky="w",  columnspan=2, ipadx=0, ipady=0)
g_13.grid(row=0, column=2, padx=10, pady=10, sticky="w",                ipadx=0, ipady=0)
g_14.grid(row=0, column=3, padx=10, pady=10, sticky="ew", columnspan=2, ipadx=0, ipady=0)
g_21.grid(row=1, column=0, padx=10, pady=10, sticky="w",                ipadx=0, ipady=0)
g_22.grid(row=1, column=1, padx=10, pady=10, sticky="w",                ipadx=0, ipady=0)
g_23.grid(row=1, column=2, padx=10, pady=10, sticky="w",                ipadx=0, ipady=0)
g_24.grid(row=1, column=3, padx=10, pady=10, sticky="ew", columnspan=2, ipadx=0, ipady=0)
g_31.grid(row=2, column=0, padx=10, pady=10, sticky="w",                ipadx=0, ipady=0)
g_32.grid(row=2, column=1, padx=10, pady=10, sticky="w",                ipadx=0, ipady=0)
g_33.grid(row=2, column=2, padx=10, pady=10, sticky="w",                ipadx=0, ipady=0)
g_34.grid(row=2, column=3, padx=10, pady=10, sticky="ew", columnspan=2, ipadx=0, ipady=0)
g_41.grid(row=3, column=0, padx=10, pady=10, sticky="w",                ipadx=0, ipady=0)
g_42.grid(row=3, column=1, padx=10, pady=10, sticky="w",                ipadx=0, ipady=0)
g_43.grid(row=3, column=2, padx=10, pady=10, sticky="w",                ipadx=0, ipady=0)
g_44.grid(row=3, column=3, padx=10, pady=10, sticky="w",                ipadx=0, ipady=0)
g_45.grid(row=3, column=4, padx=10, pady=10, sticky="w",                ipadx=0, ipady=0)
g_51.grid(row=4, column=0, padx=10, pady=10, sticky="e",                ipadx=0, ipady=0)
g_52.grid(row=4, column=1, padx=10, pady=10, sticky="w",                ipadx=0, ipady=0)
g_61.grid(row=5, column=0, padx=10, pady=10, sticky="e",  columnspan=2, ipadx=0, ipady=0)
g_63.grid(row=5, column=2, padx=10, pady=10, sticky="e",  columnspan=3, ipadx=0, ipady=0)
g_71.grid(row=6, column=0, padx=10, pady=10, sticky="ew", columnspan=5, ipadx=0, ipady=0)




# --- Running ---

# Load schedule
schedule = []
sel_task = None
load_schedules()






# Minimize to tray when user clicks the window close (X)
root.protocol("WM_DELETE_WINDOW", minimize_to_tray)

# Optional: Minimize to tray when user hits the minimize button
def on_minimize(event):
    # 'iconic' means minimized
    if root.state() == "iconic":
        minimize_to_tray()

root.bind("<Unmap>", on_minimize)

# --- Start GUI ---
root.mainloop()
