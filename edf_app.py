# edf_app.py
import tkinter as tk
import logging
from tkinter import filedialog, messagebox, scrolledtext
from config.settings import settings
from core.edf_processor import EDFProcessor
from core.edf_segmentor import EDFSegmentor
from tabulate import tabulate

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

class EDFApp:
    def __init__(self, root):
        self.root = root
        self.root.title("EDF File Manager")
        self.root.geometry("1700x700")
        self.directory = ""
        self.processor = None
        self.segmentor = None
        self._setup_ui()

    def _setup_ui(self):
        """Initialize the user interface."""
        self.button_frame = tk.Frame(self.root)
        self.button_frame.pack(pady=10)

        batch_label = tk.Label(self.button_frame, text="Batch Processing of EDF Files", font=("Arial", 11))
        batch_label.grid(row=0, column=0, padx=5, pady=5, sticky="w")

        batch_buttons = [
            ("Open Folder", self.select_directory, "Select a folder containing EDF files"),
            ("Rename EDF", self.rename_files, "Rename EDF files based on metadata"),
            ("Delete Corrupted", self.check_corrupted, "Delete corrupted EDF files"),
            ("Delete Duplicates", self.find_duplicates, "Find and delete duplicate EDF files"),
            ("Find Similar", self.find_similar_time, "Find EDF files with similar start times"),
            ("Generate Statistics", self.generate_stats, "Generate statistics for EDF files"),
            ("Create Patient Table", self.generate_patient_table, "Create a CSV table with patient names"),
            ("Randomize Filenames", self.randomize_filenames, "Randomize file names in the folder"),
            ("Remove Patient Info", self.remove_patient_info, "Remove patient information from EDF files"),
            ("Read EDF Info", self.read_edf_info, "Read and display information from EDF file"),
        ]

        for idx, (text, command, tooltip) in enumerate(batch_buttons):
            btn = tk.Button(self.button_frame, text=text, command=command, state=tk.DISABLED if idx > 0 else tk.NORMAL)
            btn.grid(row=0, column=idx + 1, padx=5, pady=5)
            self._create_tooltip(btn, tooltip)

        segmentation_label = tk.Label(self.button_frame, text="Segmentation of EDF Files", font=("Arial", 11))
        segmentation_label.grid(row=1, column=0, padx=5, pady=5, sticky="w")

        segmentation_buttons = [
            ("Load EDF File", self.load_edf_file, "Load an EDF file for segmentation"),
            ("Split EDF File", self.split_into_segments, "Split the EDF file into segments"),
        ]

        for idx, (text, command, tooltip) in enumerate(segmentation_buttons):
            btn = tk.Button(self.button_frame, text=text, command=command, state=tk.DISABLED)
            btn.grid(row=1, column=idx + 1, padx=5, pady=5)
            self._create_tooltip(btn, tooltip)

        min_duration_label = tk.Label(self.button_frame, text="Min Segment (sec):", font=("Arial", 10))
        min_duration_label.grid(row=1, column=len(segmentation_buttons) + 1, padx=5, pady=5, sticky="w")

        self.min_duration_entry = tk.Entry(self.button_frame, width=10)
        self.min_duration_entry.insert(0, str(settings.MIN_SEGMENT_DURATION))
        self.min_duration_entry.grid(row=1, column=len(segmentation_buttons) + 2, padx=5, pady=5)

        apply_duration_button = tk.Button(self.button_frame, text=" Apply ", command=self.apply_min_duration)
        apply_duration_button.grid(row=1, column=len(segmentation_buttons) + 3, padx=5, pady=5, sticky="w")

        exit_button = tk.Button(self.button_frame, text="Exit", command=self.root.quit)
        exit_button.grid(row=1, column=len(segmentation_buttons) + 8, padx=5, pady=5, sticky="e")

        self.text_output = scrolledtext.ScrolledText(self.root, wrap=tk.WORD, width=210, height=40)
        self.text_output.pack(pady=10)
        self.text_output.bind("<Control-c>", self._copy_text)
        self.text_output.bind("<Control-a>", self._select_all_text)
        self.context_menu = tk.Menu(self.root, tearoff=0)
        self.context_menu.add_command(label="Copy", command=self._copy_text)
        self.text_output.bind("<Button-3>", self._show_context_menu)

    def apply_min_duration(self):
        """Apply the minimum segment duration from the entry field."""
        try:
            min_duration = float(self.min_duration_entry.get())
            if min_duration <= 0:
                raise ValueError("Duration must be greater than 0.")
            settings.MIN_SEGMENT_DURATION = min_duration
            messagebox.showinfo("Success", f"Minimum duration set: {min_duration} sec.")
        except ValueError as e:
            messagebox.showerror("Error", str(e))

    def split_into_segments(self):
        """Split the loaded EDF file into segments using the specified minimum duration."""
        if self.segmentor:
            try:
                min_duration = float(self.min_duration_entry.get())
                if min_duration <= 0:
                    raise ValueError("Duration must be greater than 0.")
                settings.MIN_SEGMENT_DURATION = min_duration
                self.segmentor.process()
            except ValueError as e:
                messagebox.showerror("Error", str(e))

    def _copy_text(self, event=None):
        """Copy selected text to clipboard."""
        try:
            selected_text = self.text_output.selection_get()
            self.root.clipboard_clear()
            self.root.clipboard_append(selected_text)
        except tk.TclError:
            pass
        return "break"

    def _select_all_text(self, event=None):
        """Select all text in the output window."""
        self.text_output.tag_add(tk.SEL, "1.0", tk.END)
        self.text_output.mark_set(tk.INSERT, "1.0")
        self.text_output.see(tk.INSERT)
        return "break"

    def _show_context_menu(self, event):
        """Show the context menu on right-click."""
        self.context_menu.post(event.x_root, event.y_root)

    def _create_tooltip(self, widget, text):
        """Create a tooltip for the widget."""
        tooltip = tk.Toplevel(widget)
        tooltip.wm_overrideredirect(True)
        tooltip.wm_geometry("+0+0")
        tooltip.withdraw()

        label = tk.Label(tooltip, text=text, background="#ffffe0", relief="solid", borderwidth=1)
        label.pack()

        widget.bind("<Enter>", lambda e: self._show_tooltip(tooltip, widget))
        widget.bind("<Leave>", lambda e: tooltip.withdraw())

    @staticmethod
    def _show_tooltip(tooltip, widget):
        """Show the tooltip."""
        x, y, _, _ = widget.bbox("insert")
        x += widget.winfo_rootx() + 25
        y += widget.winfo_rooty() + 25
        tooltip.wm_geometry(f"+{x}+{y}")
        tooltip.deiconify()

    def select_directory(self):
        """Select a directory containing EDF files."""
        self.directory = filedialog.askdirectory()
        if self.directory:
            self.text_output.insert(tk.END, f"Selected directory: {self.directory}\n")
            self.processor = EDFProcessor(self.directory)
            for btn in self.button_frame.winfo_children():
                if isinstance(btn, tk.Button) and btn["text"] != "Open Folder":
                    btn.config(state=tk.NORMAL)

    def load_edf_file(self):
        """Load an EDF file for segmentation."""
        file_path = filedialog.askopenfilename(filetypes=[("EDF files", "*.edf")])
        if file_path:
            self.segmentor = EDFSegmentor(self.text_output)
            self.segmentor.load_metadata(file_path)
            for btn in self.button_frame.winfo_children():
                if isinstance(btn, tk.Button) and btn["text"] == "Split into Segments":
                    btn.config(state=tk.NORMAL)

    def split_into_segments(self):
        """Split the loaded EDF file into segments."""
        if self.segmentor:
            self.segmentor.process()

    def _execute_operation(self, operation_name, operation_func):
        """Execute an operation with error handling."""
        if not self.directory:
            messagebox.showwarning("Error", "Directory not selected.")
            return

        self.text_output.insert(tk.END, f"Started {operation_name}...\n")
        self.text_output.update_idletasks()

        try:
            result = operation_func()
            self.text_output.insert(tk.END, f"{operation_name.capitalize()} completed.\n")
            if result:
                self.text_output.insert(tk.END, f"Result: {result}\n")
        except Exception as e:
            logging.error(f"Error during {operation_name}: {e}")
            self.text_output.insert(tk.END, f"Error: {e}\n")
            messagebox.showerror("Error", f"An error occurred: {e}")

    def rename_files(self):
        """Rename EDF files."""
        self._execute_operation("file renaming process", self.processor.rename_edf_files)

    def find_duplicates(self):
        """Find and delete duplicates."""
        self._execute_operation("duplicate search process", self._find_and_delete_duplicates)

    def check_corrupted(self):
        """Check for corrupted files."""
        self._execute_operation("corrupted file check process", self.processor.find_and_delete_corrupted_edf)

    def generate_stats(self):
        """Generate statistics."""
        self._execute_operation("statistics generation process", self._generate_statistics_wrapper)

    def find_similar_time(self):
        """Find files with similar start times."""
        self._execute_operation("similar time search process", self.processor.find_edf_with_similar_start_time)

    def generate_patient_table(self):
        """Generate patient table."""
        self._execute_operation("patient table creation process", self.processor.generate_patient_table)

    def randomize_filenames(self):
        """Randomize file names."""
        self._execute_operation("filename randomization process", self.processor.randomize_filenames)

    def remove_patient_info(self):
        """Remove patient information."""
        self._execute_operation("patient information removal process", self.processor.remove_patient_info)

    def read_edf_info(self):
        """Read EDF file information."""
        self._execute_operation("EDF file information reading process", self.processor.read_edf_info)

    def _find_and_delete_duplicates(self):
        """Find and delete duplicate files."""
        duplicates = self.processor.find_duplicate_files()
        if duplicates:
            self.text_output.insert(tk.END, "Duplicate files found:\n")
            for hash_val, paths in duplicates.items():
                self.text_output.insert(tk.END, f"Hash: {hash_val}\n")
                for path in paths:
                    self.text_output.insert(tk.END, f"  {path}\n")
            self.processor.delete_duplicates(duplicates)
            return "Duplicates deleted."
        return "No duplicates found."

    def _generate_statistics_wrapper(self):
        """Generate and display statistics."""
        metadata_list = self.processor.analyze_directory()
        df, stats = self.processor.generate_statistics(metadata_list)
        self._display_statistics(stats)
        return "Statistics generated and visualized."

    def _display_statistics(self, stats):
        """Display statistics in the text field."""
        self.text_output.insert(tk.END, "Descriptive statistics:\n")
        if 'sex_distribution' in stats and stats['sex_distribution'] is not None:
            self.text_output.insert(tk.END, "Sex distribution:\n")
            self.text_output.insert(tk.END, tabulate(stats['sex_distribution'].items(), headers=["Sex", "Count"],
                                                     tablefmt="pretty") + "\n")
        if 'age_distribution' in stats and stats['age_distribution'] is not None:
            self.text_output.insert(tk.END, "\nAge distribution:\n")
            age_stats = stats['age_distribution']
            self.text_output.insert(tk.END, tabulate(
                [["Count", int(age_stats['count'])], ["Mean age", f"{age_stats['mean']:.2f} years"],
                 ["Minimum age", f"{age_stats['min']} years"], ["Maximum age", f"{age_stats['max']} years"]],
                headers=["Metric", "Value"], tablefmt="pretty") + "\n")
        if 'duration_stats' in stats and stats['duration_stats'] is not None:
            self.text_output.insert(tk.END, "\nRecording duration statistics (minutes):\n")
            duration_stats = stats['duration_stats']
            self.text_output.insert(tk.END, tabulate([["Mean duration", f"{duration_stats['mean']:.2f} min"],
                                                      ["Minimum duration", f"{duration_stats['min']:.2f} min"],
                                                      ["Maximum duration", f"{duration_stats['max']:.2f} min"]],
                                                     headers=["Metric", "Value"], tablefmt="pretty") + "\n")

if __name__ == "__main__":
    root = tk.Tk()
    app = EDFApp(root)
    root.mainloop()