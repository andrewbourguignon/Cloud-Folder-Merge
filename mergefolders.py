import os
import os.path
import shutil
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import tkinter.font as tkfont
import threading

def format_bytes(size):
    if size < 1024:
        return f"{size} B"
    for unit in ("KB", "MB", "GB", "TB"):
        size /= 1024
        if size < 1024:
            return f"{size:.1f} {unit}"
    return f"{size:.1f} PB"

def calculate_preview(source_folders):
    total_files = 0
    total_dirs = 0
    total_bytes = 0
    for folder in source_folders:
        for root, dirs, files in os.walk(folder):
            total_dirs += 1
            for name in files:
                total_files += 1
                file_path = os.path.join(root, name)
                try:
                    total_bytes += os.path.getsize(file_path)
                except OSError:
                    continue
    return total_files, total_dirs, total_bytes

def merge_folders(source_folders, dest_folder, logs, cancel_event, on_progress):
    processed = 0
    for folder in source_folders:
        if cancel_event.is_set():
            break
        for root, dirs, files in os.walk(folder):
            if cancel_event.is_set():
                break
            rel_path = os.path.relpath(root, folder)
            dest_root = dest_folder if rel_path == "." else os.path.join(dest_folder, rel_path)
            if not os.path.exists(dest_root):
                os.makedirs(dest_root, exist_ok=True)
                logs.append(f"Created folder: {dest_root}")
            processed += 1
            on_progress("folder", root, folder, processed)

            for name in files:
                if cancel_event.is_set():
                    break
                source_path = os.path.join(root, name)
                destination_path = os.path.join(dest_root, name)
                if not os.path.exists(destination_path):
                    shutil.copy2(source_path, destination_path)
                    logs.append(f"Copied file: {source_path} -> {destination_path}")
                else:
                    base, extension = os.path.splitext(name)
                    i = 1
                    new_name = f"{base}_{i}{extension}"
                    new_destination_path = os.path.join(dest_root, new_name)
                    while os.path.exists(new_destination_path):
                        i += 1
                        new_name = f"{base}_{i}{extension}"
                        new_destination_path = os.path.join(dest_root, new_name)
                    shutil.copy2(source_path, new_destination_path)
                    logs.append(f"Copied file with rename: {source_path} -> {new_destination_path}")
                processed += 1
                on_progress("file", source_path, folder, processed)

def select_folders():
    downloads_path = os.path.expanduser("~/Downloads")
    folder_path = filedialog.askdirectory(title="Select a Folder to Merge", initialdir=downloads_path)
    if folder_path:
        selected_folders.append(folder_path)
        update_folders_label()

def select_destination_folder():
    return filedialog.askdirectory(title="Select Destination Folder")

def start_merge():
    if not selected_folders:
        messagebox.showwarning("Warning", "Please select folders to merge.")
        return
    destination_folder = select_destination_folder()
    if not destination_folder:
        messagebox.showwarning("Warning", "Please select a destination folder.")
        return
    source_folder_name = os.path.basename(selected_folders[0])
    destination_folder = os.path.join(destination_folder, f"{source_folder_name}_merged")

    total_files, total_dirs, total_bytes = calculate_preview(selected_folders)
    if not show_preview_dialog(destination_folder, total_files, total_dirs, total_bytes):
        return

    if not os.path.exists(destination_folder):
        os.makedirs(destination_folder, exist_ok=True)
    logs = []
    logs.append(f"Destination created: {destination_folder}")
    total_items = total_files + total_dirs
    progress_popup, progress_var, status_var, detail_var, cancel_event = show_progress_window(total_items)

    def on_progress(item_type, path, base_folder, processed_count):
        rel_path = os.path.relpath(path, base_folder)
        def _update():
            progress_var.set(min(processed_count, total_items))
            if item_type == "folder":
                status_var.set("Processing folder")
            else:
                status_var.set("Copying file")
            detail_var.set(rel_path)
        root.after(0, _update)

    def _run_merge():
        start_time = time.perf_counter()
        error = None
        try:
            merge_folders(selected_folders, destination_folder, logs, cancel_event, on_progress)
        except Exception as exc:
            error = exc
            logs.append(f"Error: {exc}")
        elapsed_seconds = int(time.perf_counter() - start_time)
        minutes, seconds = divmod(elapsed_seconds, 60)

        def _finish():
            progress_popup.destroy()
            if error:
                messagebox.showerror("Merge Failed", f"An error occurred:\n{error}")
                show_merge_complete(minutes, seconds, logs, canceled=cancel_event.is_set(), failed=True)
            else:
                show_merge_complete(minutes, seconds, logs, canceled=cancel_event.is_set())
        root.after(0, _finish)

    threading.Thread(target=_run_merge, daemon=True).start()

def show_preview_dialog(destination_folder, total_files, total_dirs, total_bytes):
    preview = tk.Toplevel(root)
    preview.title("Review Merge")
    preview.geometry("520x360")
    preview.minsize(420, 300)
    preview.transient(root)
    preview.grab_set()

    container = ttk.Frame(preview, padding=20)
    container.pack(fill=tk.BOTH, expand=True)

    title = ttk.Label(container, text="Review merge details", font=title_font)
    title.pack(anchor="w")

    summary = ttk.Label(container, text="Confirm the size and destination before starting.")
    summary.pack(anchor="w", pady=(6, 16))

    stats_frame = ttk.Frame(container)
    stats_frame.pack(fill=tk.X)

    ttk.Label(stats_frame, text="Total size:", font=label_bold_font).grid(row=0, column=0, sticky="w")
    ttk.Label(stats_frame, text=format_bytes(total_bytes)).grid(row=0, column=1, sticky="w", padx=(8, 0))

    ttk.Label(stats_frame, text="Files:", font=label_bold_font).grid(row=1, column=0, sticky="w", pady=(6, 0))
    ttk.Label(stats_frame, text=str(total_files)).grid(row=1, column=1, sticky="w", padx=(8, 0), pady=(6, 0))

    ttk.Label(stats_frame, text="Folders:", font=label_bold_font).grid(row=2, column=0, sticky="w", pady=(6, 0))
    ttk.Label(stats_frame, text=str(total_dirs)).grid(row=2, column=1, sticky="w", padx=(8, 0), pady=(6, 0))

    ttk.Label(stats_frame, text="Destination:", font=label_bold_font).grid(row=3, column=0, sticky="w", pady=(6, 0))
    ttk.Label(
        stats_frame,
        text=destination_folder,
        wraplength=420,
        justify="left"
    ).grid(row=3, column=1, sticky="w", padx=(8, 0), pady=(6, 0))

    result = {"proceed": False}

    def on_start():
        result["proceed"] = True
        preview.destroy()

    def on_cancel():
        preview.destroy()

    preview.protocol("WM_DELETE_WINDOW", on_cancel)

    button_row = ttk.Frame(container)
    button_row.pack(fill=tk.X, pady=(18, 0))

    start_button = ttk.Button(button_row, text="Start Merge", command=on_start)
    cancel_button = ttk.Button(button_row, text="Cancel", command=on_cancel)
    start_button.pack(side=tk.RIGHT)
    cancel_button.pack(side=tk.RIGHT, padx=(0, 8))

    preview.wait_window()
    return result["proceed"]

def show_progress_window(total_items):
    popup = tk.Toplevel(root)
    popup.title("Merging...")
    popup.geometry("520x220")
    popup.minsize(420, 200)
    popup.transient(root)
    popup.grab_set()

    frame = ttk.Frame(popup, padding=20)
    frame.pack(fill=tk.BOTH, expand=True)

    status_var = tk.StringVar(value="Preparing merge...")
    detail_var = tk.StringVar(value="")
    progress_var = tk.IntVar(value=0)

    ttk.Label(frame, text="Merge in progress", font=title_font).pack(anchor="w")
    ttk.Label(frame, textvariable=status_var).pack(anchor="w", pady=(6, 0))
    ttk.Label(frame, textvariable=detail_var, wraplength=460, justify="left").pack(anchor="w", pady=(4, 12))

    progress = ttk.Progressbar(frame, maximum=max(1, total_items), variable=progress_var)
    progress.pack(fill=tk.X)

    cancel_event = threading.Event()

    def on_cancel():
        cancel_event.set()
        status_var.set("Cancelling...")
        cancel_button.config(state="disabled")

    cancel_button = ttk.Button(frame, text="Cancel", command=on_cancel)
    cancel_button.pack(pady=(12, 0), anchor="e")

    return popup, progress_var, status_var, detail_var, cancel_event

def show_merge_complete(minutes, seconds, logs, canceled=False, failed=False):
    popup = tk.Toplevel(root)
    popup.title("Merge Complete")
    popup.geometry("520x420")
    popup.minsize(420, 300)
    popup.transient(root)
    popup.grab_set()

    frame = ttk.Frame(popup, padding=20)
    frame.pack(fill=tk.BOTH, expand=True)

    if failed:
        title_text = "Merge failed"
    elif canceled:
        title_text = "Merge canceled"
    else:
        title_text = "Merged successfully!"

    title = ttk.Label(frame, text=title_text, font=title_font)
    title.pack(anchor="w")

    summary = ttk.Label(
        frame,
        text=f"Elapsed Time: {minutes} min {seconds} sec"
    )
    summary.pack(anchor="w", pady=(6, 12))

    dropdown_row = ttk.Frame(frame)
    dropdown_row.pack(fill=tk.X)

    details_label = ttk.Label(dropdown_row, text="Logs:", font=label_bold_font)
    details_label.pack(side=tk.LEFT)

    details_var = tk.StringVar(value="Hide logs")
    details_combo = ttk.Combobox(
        dropdown_row,
        textvariable=details_var,
        values=["Hide logs", "Show logs"],
        state="readonly",
        width=14
    )
    details_combo.pack(side=tk.LEFT, padx=(8, 0))

    log_frame = ttk.Frame(frame)
    log_scroll = ttk.Scrollbar(log_frame, orient=tk.VERTICAL)
    log_text = tk.Text(
        log_frame,
        height=10,
        wrap="word",
        yscrollcommand=log_scroll.set,
        relief="solid",
        borderwidth=1,
        font=text_font
    )
    log_scroll.config(command=log_text.yview)
    log_scroll.pack(side=tk.RIGHT, fill=tk.Y)
    log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    if logs:
        log_text.insert("1.0", "\n".join(logs))
    else:
        log_text.insert("1.0", "No log entries were recorded.")
    log_text.config(state="disabled")

    def update_log_visibility(_event=None):
        if details_var.get() == "Show logs":
            log_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
        else:
            log_frame.pack_forget()

    details_combo.bind("<<ComboboxSelected>>", update_log_visibility)
    update_log_visibility()

    button_row = ttk.Frame(frame)
    button_row.pack(pady=(15, 0), fill=tk.X)

    def export_logs():
        if not logs:
            messagebox.showinfo("Export Logs", "There are no logs to export.")
            return
        file_path = filedialog.asksaveasfilename(
            title="Export Merge Logs",
            defaultextension=".txt",
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")]
        )
        if not file_path:
            return
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write("\n".join(logs))
        except OSError as exc:
            messagebox.showerror("Export Failed", f"Could not save logs:\n{exc}")

    export_button = ttk.Button(button_row, text="Export Logs", command=export_logs)
    close_button = ttk.Button(button_row, text="Close", command=popup.destroy)
    close_button.pack(side=tk.RIGHT)
    export_button.pack(side=tk.RIGHT, padx=(0, 8))

def update_folders_label():
    if selected_folders:
        folders_text = "\n".join(selected_folders)
        folders_label.config(text=folders_text)
    else:
        folders_label.config(text="No folders selected.")

def reset_folders():
    global selected_folders
    selected_folders = []
    update_folders_label()

selected_folders = []

root = tk.Tk()
root.title("Folder Merger")
root.geometry("400x500")

style = ttk.Style(root)
available_themes = style.theme_names()
if "aqua" in available_themes:
    style.theme_use("aqua")
elif "vista" in available_themes:
    style.theme_use("vista")
elif "xpnative" in available_themes:
    style.theme_use("xpnative")

default_font = tkfont.nametofont("TkDefaultFont")
title_font = default_font.copy()
title_font.configure(size=16, weight="bold")
label_bold_font = default_font.copy()
label_bold_font.configure(weight="bold")
text_font = tkfont.nametofont("TkTextFont")

main_frame = ttk.Frame(root, padding=(24, 20))
main_frame.pack(expand=True, fill=tk.BOTH)

heading = ttk.Label(main_frame, text="Folder Merger", font=title_font)
heading.pack(pady=20)

select_button = ttk.Button(main_frame, text="Add Folders to Merge", command=select_folders)
select_button.pack(pady=10, fill=tk.X)

folders_label = ttk.Label(main_frame, text="No folders selected.", justify="left", wraplength=350)
folders_label.pack(pady=10)

merge_button = ttk.Button(main_frame, text="Start Merge", command=start_merge)
merge_button.pack(pady=10, fill=tk.X)

reset_button = ttk.Button(main_frame, text="Reset Folders", command=reset_folders)
reset_button.pack(pady=10, fill=tk.X)

root.mainloop()
