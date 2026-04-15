"""
Svanik Tandon + CC 3/31/2026

Standalone tkinter GUI for generating TPC DAQ configuration files.
Serializes parameters via the PGramsCommCodec (datamon) library and
optionally logs configurations to a MySQL database.
"""

import sys
import os
import json
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from datetime import datetime

# Add parent directory to path so we can import from connections/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from connections.config_manager import ConfigManager
from config_gui.config_db import ConfigDB

# ---------------------------------------------------------------------------
# Field presentation overrides
#
# The set of fields and their types comes from the C++ TpcConfigs class via
# ConfigManager.get_config(). This map is used to improve GUI *presentation* 
# pretty labels, hex display, dropdown enums, etc. Any field not listed here
# falls back to a plain integer entry (or array entry, for sequence values).
# ---------------------------------------------------------------------------

TRIGGER_SOURCE_OPTIONS = {
    "light":    0,
    "software": 1,
    "external": 2,
}
TRIGGER_SOURCE_REVERSE = {v: k for k, v in TRIGGER_SOURCE_OPTIONS.items()}

FIELD_OVERRIDES = {
    "enable_top":      {"widget": "hex",      "label": "Enable Top"},
    "enable_middle":   {"widget": "hex",      "label": "Enable Middle"},
    "enable_bottom":   {"widget": "hex",      "label": "Enable Bottom"},
    "fifo_blocksize":  {"widget": "hex",      "label": "FIFO Blocksize"},
    "tpc_dead_time":   {"widget": "hex",      "label": "TPC Dead Time"},
    "trigger_source":  {"widget": "dropdown", "label": "Trigger Source",
                        "options": TRIGGER_SOURCE_OPTIONS},
}

DEFAULTS_DIR = os.path.join(os.path.dirname(__file__), "defaults")
OUTPUT_DIR   = os.path.join(os.path.dirname(__file__), "output")


def _prettify(key):
    return key.replace("_", " ").title()


def _is_array(value):
    return isinstance(value, (list, tuple)) or (
        hasattr(value, "__len__") and not isinstance(value, (str, bytes))
    )


class ConfigGUI:
    """Main tkinter application for TPC configuration."""

    def __init__(self, root):
        self.root = root
        self.root.title("pGRAMS TPC Configuration GUI")
        self.root.minsize(800, 750)

        self.config_mgr = ConfigManager()

        # Try to connect to database; warn but continue if unavailable
        try:
            self.db = ConfigDB()
            self.db_available = True
        except Exception as e:
            self.db = None
            self.db_available = False
            print(f"[WARNING] Database unavailable: {e}")

        # entries[key] = dict with field state. See _add_*_row for shape.
        self.entries = {}

        self._build_ui()
        self._populate_from_config_manager()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        # Top-level scrollable canvas
        canvas = tk.Canvas(self.root)
        scrollbar = ttk.Scrollbar(self.root, orient="vertical", command=canvas.yview)
        self.scroll_frame = ttk.Frame(canvas)

        self.scroll_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.create_window((0, 0), window=self.scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Mousewheel scrolling
        canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(int(-e.delta / 120), "units"))
        canvas.bind_all("<Button-4>",   lambda e: canvas.yview_scroll(-1, "units"))
        canvas.bind_all("<Button-5>",   lambda e: canvas.yview_scroll(1, "units"))

        row = 0

        # --- Metadata section ---
        row = self._add_section_header("Metadata", row)
        row = self._add_metadata_section(row)

        # --- Parameter sections (introspected from ConfigManager) ---
        cfg = self.config_mgr.get_config()

        scalar_keys = [k for k, v in cfg.items() if not _is_array(v)]
        array_keys  = [k for k, v in cfg.items() if     _is_array(v)]

        row = self._add_section_header("Scalar Parameters", row)
        for key in scalar_keys:
            row = self._add_param_row(key, row)

        row = self._add_section_header("Array Parameters", row)
        for key in array_keys:
            row = self._add_array_row(key, len(cfg[key]), row)

        # --- Action buttons ---
        row = self._add_section_header("Actions", row)
        btn_frame = ttk.Frame(self.scroll_frame)
        btn_frame.grid(row=row, column=0, columnspan=3, pady=10, sticky="ew")

        ttk.Button(btn_frame, text="Load Default",         command=self._load_default).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Load JSON...",         command=self._load_json_file).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Clear All",            command=self._clear_all).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Validate",             command=self._validate).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Generate Config File", command=self._generate_config).pack(side="left", padx=5)

        # --- Status bar ---
        self.status_var = tk.StringVar(value="Ready")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief="sunken", anchor="w")
        status_bar.pack(side="bottom", fill="x")

    def _add_section_header(self, text, row):
        sep = ttk.Separator(self.scroll_frame, orient="horizontal")
        sep.grid(row=row, column=0, columnspan=3, sticky="ew", pady=(10, 2))
        lbl = ttk.Label(self.scroll_frame, text=text, font=("TkDefaultFont", 11, "bold"))
        lbl.grid(row=row + 1, column=0, columnspan=3, sticky="w", padx=5, pady=(0, 5))
        return row + 2

    def _add_metadata_section(self, row):
        ttk.Label(self.scroll_frame, text="Run ID:").grid(row=row, column=0, sticky="e", padx=5)
        self.run_id_var = tk.StringVar(value="(auto)")
        ttk.Label(self.scroll_frame, textvariable=self.run_id_var).grid(row=row, column=1, sticky="w", padx=5)
        row += 1

        ttk.Label(self.scroll_frame, text="Date/Time:").grid(row=row, column=0, sticky="e", padx=5)
        self.datetime_var = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        ttk.Label(self.scroll_frame, textvariable=self.datetime_var).grid(row=row, column=1, sticky="w", padx=5)
        row += 1

        ttk.Label(self.scroll_frame, text="Description:").grid(row=row, column=0, sticky="ne", padx=5)
        self.description_entry = tk.Text(self.scroll_frame, height=3, width=50)
        self.description_entry.grid(row=row, column=1, columnspan=2, sticky="w", padx=5, pady=2)
        row += 1
        return row

    def _add_param_row(self, key, row):
        """Add a scalar field (int / hex / dropdown)."""
        override = FIELD_OVERRIDES.get(key, {})
        label    = override.get("label", _prettify(key))
        kind     = override.get("widget", "int")

        ttk.Label(self.scroll_frame, text=f"{label}:").grid(row=row, column=0, sticky="e", padx=5, pady=2)

        if kind == "dropdown":
            options = override["options"]
            combo = ttk.Combobox(self.scroll_frame, values=list(options.keys()),
                                 state="readonly", width=15)
            combo.grid(row=row, column=1, sticky="w", padx=5, pady=2)
            self.entries[key] = {"kind": "dropdown", "widget": combo, "options": options}
        else:
            entry = ttk.Entry(self.scroll_frame, width=20)
            entry.grid(row=row, column=1, sticky="w", padx=5, pady=2)
            self.entries[key] = {"kind": kind, "widget": entry}  # "int" or "hex"

        return row + 1

    def _add_array_row(self, key, size, row):
        """
        Add an array field. Defaults to scalar (broadcast) mode: a single
        Entry whose value is broadcast to all `size` elements. A toggle button
        switches to array mode (Text widget with comma-separated values).
        """
        override = FIELD_OVERRIDES.get(key, {})
        label    = override.get("label", _prettify(key))

        ttk.Label(self.scroll_frame, text=f"{label}:").grid(row=row, column=0, sticky="ne", padx=5, pady=2)

        # Container frame for the input widget — lets us swap widget on toggle
        container = ttk.Frame(self.scroll_frame)
        container.grid(row=row, column=1, sticky="w", padx=5, pady=2)

        # Start in scalar mode
        scalar_entry = ttk.Entry(container, width=20)
        scalar_entry.pack(side="left")

        size_label = ttk.Label(container, text=f"  (broadcast to {size})", foreground="gray")
        size_label.pack(side="left")

        state = {
            "kind":      "array",
            "mode":      "scalar",   # "scalar" | "array"
            "widget":    scalar_entry,
            "container": container,
            "size_label": size_label,
            "size":      size,
            "label":     label,
        }

        toggle_btn = ttk.Button(self.scroll_frame, text="Expand →",
                                command=lambda k=key: self._toggle_array_mode(k))
        toggle_btn.grid(row=row, column=2, sticky="w", padx=5)
        state["toggle_btn"] = toggle_btn

        self.entries[key] = state
        return row + 1

    def _toggle_array_mode(self, key):
        """Swap an array field between scalar-broadcast and full-array input."""
        st = self.entries[key]
        # Capture current value(s) so we can preserve them across the swap
        if st["mode"] == "scalar":
            current = st["widget"].get().strip()
            try:
                seed = int(current, 0) if current else 0
            except ValueError:
                seed = 0
            values = [seed] * st["size"]
            self._switch_to_array_mode(key, values)
        else:
            current = st["widget"].get("1.0", tk.END).strip()
            parts = [p.strip() for p in current.replace("\n", ",").split(",") if p.strip()]
            try:
                seed = int(parts[0], 0) if parts else 0
            except ValueError:
                seed = 0
            self._switch_to_scalar_mode(key, seed)

    def _switch_to_array_mode(self, key, values):
        st = self.entries[key]
        for child in st["container"].winfo_children():
            child.destroy()
        text = tk.Text(st["container"], height=3, width=50)
        text.pack(side="left")
        text.insert("1.0", ", ".join(str(int(v)) for v in values))
        size_label = ttk.Label(st["container"], text=f"  ({st['size']} values)", foreground="gray")
        size_label.pack(side="left")
        st["widget"]     = text
        st["size_label"] = size_label
        st["mode"]       = "array"
        st["toggle_btn"].config(text="← Collapse")

    def _switch_to_scalar_mode(self, key, value):
        st = self.entries[key]
        for child in st["container"].winfo_children():
            child.destroy()
        entry = ttk.Entry(st["container"], width=20)
        entry.pack(side="left")
        entry.insert(0, str(int(value)))
        size_label = ttk.Label(st["container"], text=f"  (broadcast to {st['size']})", foreground="gray")
        size_label.pack(side="left")
        st["widget"]     = entry
        st["size_label"] = size_label
        st["mode"]       = "scalar"
        st["toggle_btn"].config(text="Expand →")

    # ------------------------------------------------------------------
    # Form <-> data helpers
    # ------------------------------------------------------------------

    def _set_scalar_widget(self, st, val):
        """Write a single integer value into a scalar widget."""
        kind = st["kind"]
        w = st["widget"]
        if kind == "dropdown":
            reverse = {v: k for k, v in st["options"].items()}
            w.set(reverse.get(int(val), next(iter(st["options"]))))
        elif kind == "hex":
            w.delete(0, tk.END)
            w.insert(0, hex(int(val)))
        else:  # "int"
            w.delete(0, tk.END)
            w.insert(0, str(int(val)))

    def _populate_from_config_manager(self):
        """Fill the form from the current ConfigManager state."""
        cfg = self.config_mgr.get_config()
        for key, st in self.entries.items():
            if key not in cfg:
                continue
            val = cfg[key]
            if st["kind"] == "array":
                # If all elements are equal, stay in scalar mode and seed it.
                # Otherwise auto-expand to array mode so the user sees real values.
                vals = [int(v) for v in val]
                all_equal = len(set(vals)) <= 1
                if all_equal:
                    if st["mode"] != "scalar":
                        self._switch_to_scalar_mode(key, vals[0] if vals else 0)
                    st["widget"].delete(0, tk.END)
                    st["widget"].insert(0, str(vals[0] if vals else 0))
                else:
                    if st["mode"] != "array":
                        self._switch_to_array_mode(key, vals)
                    else:
                        st["widget"].delete("1.0", tk.END)
                        st["widget"].insert("1.0", ", ".join(str(v) for v in vals))
            else:
                self._set_scalar_widget(st, val)

    def _read_scalar(self, st):
        """Read a single integer value from a scalar widget."""
        kind = st["kind"]
        w = st["widget"]
        if kind == "dropdown":
            return st["options"][w.get()]
        raw = w.get().strip()
        if kind == "hex":
            return int(raw, 16) if raw.lower().startswith("0x") else int(raw)
        return int(raw)

    def _read_form_to_dict(self):
        """Build {"tpc": {...}} from the form, suitable for ConfigManager.update_from_dict()."""
        tpc = {}
        for key, st in self.entries.items():
            if st["kind"] == "array":
                if st["mode"] == "scalar":
                    raw = st["widget"].get().strip()
                    if not raw:
                        continue
                    tpc[key] = int(raw, 0)  # ConfigManager broadcasts scalar -> array
                else:
                    raw = st["widget"].get("1.0", tk.END).strip()
                    if not raw:
                        continue
                    parts = [p.strip() for p in raw.replace("\n", ",").split(",") if p.strip()]
                    tpc[key] = [int(p, 0) for p in parts]
            else:
                tpc[key] = self._read_scalar(st)
        return {"tpc": tpc}

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _load_default(self):
        if not os.path.isdir(DEFAULTS_DIR):
            messagebox.showwarning("No Defaults", f"Defaults directory not found:\n{DEFAULTS_DIR}")
            return
        files = [f for f in os.listdir(DEFAULTS_DIR) if f.endswith(".json")]
        if not files:
            messagebox.showinfo("No Defaults", "No JSON files found in defaults/ directory.")
            return

        win = tk.Toplevel(self.root)
        win.title("Select Default Config")
        win.geometry("350x250")
        listbox = tk.Listbox(win, selectmode="single")
        for f in sorted(files):
            listbox.insert(tk.END, f)
        listbox.pack(fill="both", expand=True, padx=10, pady=5)

        def on_select():
            sel = listbox.curselection()
            if not sel:
                return
            self._apply_json(os.path.join(DEFAULTS_DIR, files[sel[0]]))
            win.destroy()

        ttk.Button(win, text="Load", command=on_select).pack(pady=5)

    def _load_json_file(self):
        filepath = filedialog.askopenfilename(
            title="Open Config JSON",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if filepath:
            self._apply_json(filepath)

    def _apply_json(self, filepath):
        try:
            self.config_mgr.load_json(filepath)
            self._populate_from_config_manager()
            self.status_var.set(f"Loaded: {os.path.basename(filepath)}")
        except Exception as e:
            messagebox.showerror("Load Error", str(e))

    def _clear_all(self):
        """Reset to the C++-defined cleared state (TpcConfigs::clear)."""
        self.config_mgr.clear()
        self._populate_from_config_manager()
        self.description_entry.delete("1.0", tk.END)
        self.status_var.set("Form cleared")

    def _validate(self):
        """Validate all form values and report errors."""
        errors = []
        for key, st in self.entries.items():
            label = FIELD_OVERRIDES.get(key, {}).get("label", _prettify(key))
            try:
                if st["kind"] == "array":
                    if st["mode"] == "scalar":
                        raw = st["widget"].get().strip()
                        if not raw:
                            errors.append(f"{label}: empty value")
                            continue
                        v = int(raw, 0)
                        if not (0 <= v <= 0xFFFFFFFF):
                            errors.append(f"{label}: out of uint32 range")
                    else:
                        raw = st["widget"].get("1.0", tk.END).strip()
                        parts = [p.strip() for p in raw.replace("\n", ",").split(",") if p.strip()]
                        if len(parts) != st["size"]:
                            errors.append(f"{label}: expected {st['size']} values, got {len(parts)}")
                        for i, p in enumerate(parts):
                            v = int(p, 0)
                            if not (0 <= v <= 0xFFFFFFFF):
                                errors.append(f"{label}[{i}]: out of uint32 range")
                else:
                    v = self._read_scalar(st)
                    if not (0 <= v <= 0xFFFFFFFF):
                        errors.append(f"{label}: out of uint32 range")
            except ValueError as e:
                errors.append(f"{label}: {e}")

        if errors:
            messagebox.showwarning("Validation Errors", "\n".join(errors))
            self.status_var.set(f"Validation failed: {len(errors)} error(s)")
            return False
        messagebox.showinfo("Validation", "All parameters valid.")
        self.status_var.set("Validation passed")
        return True

    def _generate_config(self):
        if not self._validate():
            return

        try:
            form_dict = self._read_form_to_dict()
            self.config_mgr.update_from_dict(form_dict)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to update config:\n{e}")
            return

        serialized = self.config_mgr.serialize()
        os.makedirs(OUTPUT_DIR, exist_ok=True)

        now = datetime.now()
        self.datetime_var.set(now.strftime("%Y-%m-%d %H:%M:%S"))

        description = self.description_entry.get("1.0", tk.END).strip()
        config_json = json.dumps(form_dict, indent=2)

        run_id = None
        if self.db_available:
            try:
                run_id = self.db.get_next_id()
            except Exception as e:
                print(f"[WARNING] Could not get run ID from DB: {e}")
        if run_id is None:
            existing = [f for f in os.listdir(OUTPUT_DIR) if f.startswith("config_")]
            run_id = len(existing) + 1
        self.run_id_var.set(str(run_id))

        timestamp_str = now.strftime("%Y%m%d_%H%M%S")
        filename = f"config_{run_id}_{timestamp_str}.txt"
        filepath = os.path.join(OUTPUT_DIR, filename)

        try:
            with open(filepath, "w") as f:
                for val in serialized:
                    f.write(f"{val}\n")
        except Exception as e:
            messagebox.showerror("File Error", f"Failed to write file:\n{e}")
            return

        if self.db_available:
            try:
                self.db.log_config(
                    timestamp=now,
                    description=description,
                    config_json=config_json,
                    output_filename=filename,
                )
            except Exception as e:
                messagebox.showwarning("DB Warning", f"Config file saved but DB logging failed:\n{e}")

        self.status_var.set(f"Config written: {filename}")
        messagebox.showinfo("Success", f"Configuration file generated:\n{filepath}")


def main():
    root = tk.Tk()
    ConfigGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
