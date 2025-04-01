# edf_app.py
import logging
import os
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk
from typing import Optional
from tabulate import tabulate
from config.settings import settings
from core.db_manager import DBManager
from core.edf_processor import EDFProcessor
from core.edf_segmentor import EDFSegmentor

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

class EDFApp:
    def __init__(self, master):
        self.master = master
        self.master.title("EDF File Manager")
        self.master.geometry("1700x700")
        self.directory = ""
        self.processor: Optional[EDFProcessor] = None
        self.segmentor: Optional[EDFSegmentor] = None
        self.db_manager: Optional[DBManager] = None
        self.current_edf_file: Optional[str] = None
        self._cancel_processing = False
        self._setup_ui()
        self._try_autoload_db()

    def _setup_ui(self):
        main_container = tk.Frame(self.master)
        main_container.pack(fill=tk.BOTH, expand=True)

        top_container = tk.Frame(main_container)
        top_container.pack(fill=tk.X, padx=5, pady=5)

        self.top_panel = tk.Frame(top_container)
        self.top_panel.pack(side=tk.LEFT, fill=tk.X, expand=True)

        exit_btn = tk.Button(
            top_container,
            text="Exit",
            width=10,
            command=self.master.quit
        )
        exit_btn.pack(side=tk.RIGHT, padx=5)
        self._create_tooltip(exit_btn, "Exit application")

        self.notebook = ttk.Notebook(self.top_panel)
        self.notebook.pack(fill=tk.X, expand=True)

        self._setup_folder_processing_tab()
        self._setup_segmentation_tab()
        self._setup_database_tab()
        self._setup_text_output_area(main_container)

    def _setup_database_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Database")

        frame = tk.Frame(tab)
        frame.pack(fill=tk.X, padx=5, pady=5)

        self.db_buttons = {}
        buttons = [
            ("Create DB", self.create_database, "Create new database"),
            ("Delete DB", self.delete_database, "Delete database"),
            ("Fill DB", self.fill_segments, "Fill with segments from current EDF file"),
            ("All S&F", self.batch_process_edf_files, "Process all EDF files and save segments to DB"),
            ("DB Stats", self.show_db_stats, "Show DB statistics"),
            ("DB Editor", self.edit_database, "View/edit tables"),
        ]

        for text, command, tooltip in buttons:
            btn = tk.Button(
                frame,
                text=text,
                width=10,
                command=command,
                state=tk.NORMAL if text == "Create DB" else tk.DISABLED
            )
            btn.pack(side=tk.LEFT, padx=2, pady=2)
            self._create_tooltip(btn, tooltip)
            self.db_buttons[text] = btn

        self.db_status_label = tk.Label(
            frame,
            text="[DB Not Created]",
            fg="red"
        )
        self.db_status_label.pack(side=tk.LEFT, padx=5, pady=2)

    def _setup_folder_processing_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="EDF Processing")

        frame = tk.Frame(tab)
        frame.pack(fill=tk.X, padx=5, pady=5)

        buttons = [
            ("Open", self.select_directory, "Select folder with EDF files"),
            ("Rename", self.rename_files, "Rename EDF files by metadata"),
            ("Check", self.check_corrupted, "Check for corrupted files"),
            ("Dupes", self.find_duplicates, "Find and delete duplicates"),
            ("Similar", self.find_similar_time, "Find files with similar times"),
            ("Stats", self.generate_stats, "Generate statistics for EDF files"),
            ("Patients", self.generate_patient_table, "Create patient table"),
            ("Random", self.randomize_filenames, "Randomize filenames"),
            ("Anonym", self.remove_patient_info, "Remove patient info"),
            ("Info", self.read_edf_info, "Show first EDF file info"),
        ]

        for text, command, tooltip in buttons:
            btn = tk.Button(
                frame,
                text=text,
                width=10,
                command=command,
                state=tk.DISABLED if text != "Open" else tk.NORMAL
            )
            btn.pack(side=tk.LEFT, padx=2, pady=2)
            self._create_tooltip(btn, tooltip)

    def _setup_segmentation_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Segmentation")

        frame = tk.Frame(tab)
        frame.pack(fill=tk.X, padx=5, pady=5)

        self.btn_load_edf = tk.Button(
            frame,
            text="Load EDF",
            width=10,
            command=self.load_edf_file,
            state=tk.DISABLED
        )
        self.btn_load_edf.pack(side=tk.LEFT, padx=2, pady=2)
        self._create_tooltip(self.btn_load_edf, "Load EDF file for segmentation")

        self.btn_split = tk.Button(
            frame,
            text="Split",
            width=10,
            command=self.split_into_segments,
            state=tk.DISABLED
        )
        self.btn_split.pack(side=tk.LEFT, padx=2, pady=2)
        self._create_tooltip(self.btn_split, "Split EDF file into segments")

        tk.Label(frame, text="Min (sec):").pack(side=tk.LEFT, padx=2, pady=2)

        self.min_duration_entry = tk.Entry(frame, width=6)
        self.min_duration_entry.insert(0, str(settings.MIN_SEGMENT_DURATION))
        self.min_duration_entry.pack(side=tk.LEFT, padx=2, pady=2)

        self.btn_set_duration = tk.Button(
            frame,
            text="Set Duration",
            width=10,
            command=self.apply_min_duration
        )
        self.btn_set_duration.pack(side=tk.LEFT, padx=2, pady=2)
        self._create_tooltip(self.btn_set_duration, "Set minimum segment duration")

        self.current_file_label = tk.Label(
            frame,
            text="No file loaded",
            fg="gray",
            font=("Arial", 8)
        )
        self.current_file_label.pack(side=tk.LEFT, padx=5, pady=2)

    def _setup_text_output_area(self, parent):
        self.text_output = scrolledtext.ScrolledText(
            parent,
            wrap=tk.WORD,
            width=210,
            height=40
        )
        self.text_output.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.text_output.bind("<Control-c>", self._copy_text)
        self.text_output.bind("<Control-a>", self._select_all_text)

        self.context_menu = tk.Menu(self.master, tearoff=0)
        self.context_menu.add_command(label="Copy", command=self._copy_text)
        self.text_output.bind("<Button-3>", self._show_context_menu)

    def _create_tooltip(self, widget, text):
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
        x, y, _, _ = widget.bbox("insert")
        x += widget.winfo_rootx() + 25
        y += widget.winfo_rooty() + 25
        tooltip.wm_geometry(f"+{x}+{y}")
        tooltip.deiconify()

    def _copy_text(self, event=None):
        try:
            selected_text = self.text_output.selection_get()
            self.master.clipboard_clear()
            self.master.clipboard_append(selected_text)
        except tk.TclError:
            pass
        return "break"

    def _select_all_text(self, event=None):
        self.text_output.tag_add(tk.SEL, "1.0", tk.END)
        self.text_output.mark_set(tk.INSERT, "1.0")
        self.text_output.see(tk.INSERT)
        return "break"

    def _show_context_menu(self, event):
        self.context_menu.post(event.x_root, event.y_root)

    def _center_window(self, window):
        window.update_idletasks()
        x = self.master.winfo_x() + (self.master.winfo_width() - window.winfo_width()) // 2
        y = self.master.winfo_y() + (self.master.winfo_height() - window.winfo_height()) // 2
        window.geometry(f"+{x}+{y}")

    def _update_db_status(self):
        if hasattr(self, 'db_manager') and self.db_manager:
            db_name = os.path.basename(self.db_manager.db_path)
            size = os.path.getsize(self.db_manager.db_path) / 1024
            self.db_status_label.config(
                text=f"DB: {db_name} ({size:.1f} KB)",
                fg="green",
                font=("Arial", 9, "bold")
            )
            self._enable_db_buttons()
        else:
            self.db_status_label.config(
                text="[DB Not Created]",
                fg="red",
                font=("Arial", 9)
            )
            self._disable_db_buttons()

    def _enable_db_buttons(self):
        for btn_text, btn in self.db_buttons.items():
            if btn_text != "Create DB":
                btn.config(state=tk.NORMAL if hasattr(self, 'db_manager') and self.db_manager else tk.DISABLED)

    def _disable_db_buttons(self):
        for btn_text, btn in self.db_buttons.items():
            if btn_text != "Create DB":
                btn.config(state=tk.DISABLED)

    def _try_autoload_db(self):
        if not self.directory:
            return
        db_path = os.path.join(self.directory, "DB", "eeg_database.db")
        if os.path.exists(db_path):
            try:
                self.db_manager = DBManager(self.directory)
                self._update_db_status()
                self.text_output.insert(tk.END, "Automatically loaded existing database\n")
            except Exception as e:
                self.text_output.insert(tk.END, f"Error loading database: {str(e)}\n")

    def batch_process_edf_files(self):
        if not self.directory:
            messagebox.showwarning("Error", "Please select a working directory first")
            return
        if not hasattr(self, 'db_manager') or not self.db_manager:
            messagebox.showwarning("Error", "Please create a database first")
            return

        edf_files = [f for f in os.listdir(self.directory) if f.lower().endswith('.edf')]
        if not edf_files:
            messagebox.showinfo("Information", "No EDF files found in the selected directory")
            return

        progress_window, progress_var, status_label = self._create_progress_window(len(edf_files))
        self.text_output.delete(1.0, tk.END)
        self.text_output.insert(tk.END, f"Starting batch processing of {len(edf_files)} files...\n")

        total_segments = 0
        processed_files = 0
        self._cancel_processing = False

        try:
            for i, edf_file in enumerate(edf_files, 1):
                if self._cancel_processing:
                    self.text_output.insert(tk.END, "\nProcessing cancelled by user\n")
                    break

                try:
                    progress_var.set(i)
                    status_label.config(text=f"Processing file {i} of {len(edf_files)}: {edf_file}")
                    progress_window.update()

                    file_path = os.path.join(self.directory, edf_file)
                    self.text_output.insert(tk.END, f"\nProcessing file: {edf_file}\n")
                    self.text_output.update_idletasks()

                    segmentor = EDFSegmentor(self.text_output)
                    segmentor.load_metadata(file_path)
                    segmentor.process()

                    if segmentor.seg_dict:
                        try:
                            patient_id, edf_id = self.db_manager.fill_segments_from_dict(
                                segmentor.seg_dict,
                                file_path
                            )
                            segments_added = len(segmentor.seg_dict)
                            total_segments += segments_added
                            self.text_output.insert(
                                tk.END,
                                f"Added {segments_added} segments to DB (Patient ID: {patient_id}, EDF ID: {edf_id})\n"
                            )
                            processed_files += 1
                        except ValueError as e:
                            self.text_output.insert(tk.END, f"Database insertion error: {str(e)}\n")
                    else:
                        self.text_output.insert(tk.END, "File contains no segments to add\n")

                except Exception as e:
                    self.text_output.insert(tk.END, f"Error processing file {edf_file}: {str(e)}\n")
                    logging.error(f"Error processing {edf_file}: {e}")
                    continue

            completion_msg = "\nBatch processing cancelled\n" if self._cancel_processing else "\nBatch processing completed!\n"
            self.text_output.insert(
                tk.END,
                f"{completion_msg}"
                f"Files processed: {processed_files}/{len(edf_files)}\n"
                f"Total segments added: {total_segments}\n"
            )

        finally:
            progress_window.destroy()
            self._update_db_status()

    def _create_progress_window(self, total_files):
        progress_window = tk.Toplevel(self.master)
        progress_window.title("Batch Processing Progress")
        progress_window.geometry("400x150")
        progress_window.resizable(False, False)
        progress_window.grab_set()

        tk.Label(progress_window, text="Processing EDF files...", font=('Arial', 10)).pack(pady=10)

        progress_var = tk.DoubleVar()
        progress_bar = ttk.Progressbar(
            progress_window,
            variable=progress_var,
            maximum=total_files,
            length=300,
            mode='determinate'
        )
        progress_bar.pack(pady=5)

        status_label = tk.Label(progress_window, text=f"0 of {total_files} files processed")
        status_label.pack(pady=5)

        cancel_button = tk.Button(
            progress_window,
            text="Cancel",
            command=lambda: setattr(self, '_cancel_processing', True)
        )
        cancel_button.pack(pady=5)

        self._center_window(progress_window)
        return progress_window, progress_var, status_label

    def create_database(self):
        try:
            if not self.directory:
                messagebox.showwarning("Error", "Please select a directory.")
                return
            db_folder = os.path.join(self.directory, "DB")
            db_path = os.path.join(db_folder, "eeg_database.db")
            os.makedirs(db_folder, exist_ok=True)
            if os.path.exists(db_path):
                if not messagebox.askyesno("Confirmation", "Database already exists. Recreate?"):
                    self.text_output.insert(tk.END, "Database already exists.\n")
                    return
            self.db_manager = DBManager(self.directory)
            if not self.db_manager.database_exists():
                raise RuntimeError("Failed to create database file")
            self.text_output.insert(tk.END, f"Database created at:\n{db_path}\n")
            self._update_db_status()
            if not any(f.lower().endswith('.edf') for f in os.listdir(self.directory)):
                messagebox.showwarning("Warning", "No EDF files found in the directory.")

        except Exception as e:
            error_msg = f"Error creating database: {str(e)}"
            self.text_output.insert(tk.END, error_msg + "\n")
            messagebox.showerror("Database Error", error_msg)
            if hasattr(self, 'db_manager'):
                del self.db_manager

    def delete_database(self):
        if not hasattr(self, 'db_manager') or not self.db_manager:
            messagebox.showwarning("Error", "No database to delete")
            return

        db_path = self.db_manager.db_path
        db_name = os.path.basename(db_path)

        confirm = messagebox.askyesno(
            "Confirm Deletion",
            f"Are you sure you want to delete database:\n{db_name}?\n\nThis action cannot be undone!",
            icon='warning'
        )
        if not confirm:
            return

        try:
            if hasattr(self.db_manager, 'close_connection'):
                self.db_manager.close_connection()
            elif hasattr(self.db_manager, 'conn') and self.db_manager.conn:
                self.db_manager.conn.close()

            if os.path.exists(db_path):
                os.remove(db_path)
                self.text_output.insert(tk.END, f"Database file '{db_name}' deleted.\n")

            segments_dir = os.path.join(os.path.dirname(db_path), "segments")
            if os.path.exists(segments_dir):
                import shutil
                shutil.rmtree(segments_dir)
                self.text_output.insert(tk.END, f"Segments directory deleted.\n")

            self.db_manager = None
            self._update_db_status()
            self.text_output.insert(tk.END, f"Database '{db_name}' successfully deleted\n")

        except Exception as e:
            error_msg = f"Error deleting database: {str(e)}"
            self.text_output.insert(tk.END, error_msg + "\n")
            messagebox.showerror("Error", error_msg)

    def fill_segments(self):
        if not self.segmentor or not self.segmentor.seg_dict:
            messagebox.showwarning("Error", "No segments available to add to database.")
            return
        if not self.db_manager:
            messagebox.showwarning("Error", "Database not created. Please create database first.")
            return

        try:
            file_path = getattr(self.segmentor, 'current_file_path', None)
            if not file_path:
                file_path = filedialog.askopenfilename(filetypes=[("EDF files", "*.edf")])
                if not file_path:
                    return

            patient_id, edf_id = self.db_manager.fill_segments_from_dict(
                self.segmentor.seg_dict,
                file_path
            )
            self.text_output.insert(tk.END,
                                  f"Successfully added segments to database. Patient ID: {patient_id}, EDF ID: {edf_id}\n")
            self.show_db_stats()
        except Exception as e:
            self.text_output.insert(tk.END, f"Error adding segments: {e}\n")
            messagebox.showerror("Error", f"Failed to add segments: {e}")

    def show_db_stats(self):
        self.text_output.delete(1.0, tk.END)
        if not hasattr(self, 'db_manager') or not self.db_manager:
            self.text_output.insert(tk.END, "Database not initialized. Please create database first.\n")
            return

        try:
            stats = self.db_manager.get_database_stats()
            self.text_output.insert(tk.END, "Database Statistics:\n")
            self.text_output.insert(tk.END, f"Patients: {stats['patients']}\n")
            self.text_output.insert(tk.END, f"EDF Files: {stats['edf_files']}\n")
            self.text_output.insert(tk.END, f"Segments: {stats['segments']}\n")
            self.text_output.insert(tk.END, f"Diagnoses: {stats['diagnoses']}\n")
        except Exception as e:
            self.text_output.insert(tk.END, f"Error getting database stats: {e}\n")

    def edit_database(self):
        if not self.db_manager:
            messagebox.showwarning("Error", "Database not created. Please create database first.")
            return

        editor_window = tk.Toplevel(self.master)
        from core.db_editor import DBEditor
        DBEditor(editor_window, self.db_manager, self.text_output)
        editor_window.wait_visibility()
        editor_window.grab_set()

    def apply_min_duration(self):
        try:
            min_duration = float(self.min_duration_entry.get())
            if min_duration <= 0:
                raise ValueError("Duration must be greater than 0.")
            settings.MIN_SEGMENT_DURATION = min_duration
            messagebox.showinfo("Success", f"Minimum duration set: {min_duration} sec.")
        except ValueError as e:
            messagebox.showerror("Error", str(e))

    def split_into_segments(self):
        if self.segmentor:
            try:
                min_duration = float(self.min_duration_entry.get())
                if min_duration <= 0:
                    raise ValueError("Duration must be greater than 0.")
                settings.MIN_SEGMENT_DURATION = min_duration
                self.segmentor.process()
            except ValueError as e:
                messagebox.showerror("Error", str(e))

    def select_directory(self):
        self.directory = filedialog.askdirectory()
        if self.directory:
            self.text_output.insert(tk.END, f"Selected directory: {self.directory}\n")
            self.processor = EDFProcessor(self.directory)

            for tab in self.notebook.winfo_children():
                for widget in tab.winfo_children():
                    if isinstance(widget, tk.Frame):
                        for btn in widget.winfo_children():
                            if isinstance(btn, tk.Button) and btn["text"] != "Open":
                                btn.config(state=tk.NORMAL)

            self.btn_load_edf.config(state=tk.NORMAL)
            self._try_autoload_db()

    def load_edf_file(self):
        file_path = filedialog.askopenfilename(filetypes=[("EDF files", "*.edf")])
        if file_path:
            self.segmentor = EDFSegmentor(self.text_output)
            self.segmentor.current_file_path = file_path
            self.segmentor.load_metadata(file_path)
            self.btn_split.config(state=tk.NORMAL)
            if self.db_manager:
                self.db_buttons["Fill DB"].config(state=tk.NORMAL)

    def _execute_operation(self, operation_name, operation_func):
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
        self._execute_operation("file renaming process", self.processor.rename_edf_files)

    def find_duplicates(self):
        self._execute_operation("duplicate search process", self._find_and_delete_duplicates)

    def check_corrupted(self):
        self._execute_operation("corrupted file check process", self.processor.find_and_delete_corrupted_edf)

    def generate_stats(self):
        self._execute_operation("statistics generation process", self._generate_statistics_wrapper)

    def find_similar_time(self):
        self._execute_operation("similar time search process", self.processor.find_edf_with_similar_start_time)

    def generate_patient_table(self):
        self._execute_operation("patient table creation process", self.processor.generate_patient_table)

    def randomize_filenames(self):
        self._execute_operation("filename randomization process", self.processor.randomize_filenames)

    def remove_patient_info(self):
        self._execute_operation("patient information removal process", self.processor.remove_patient_info)

    def read_edf_info(self):
        self._execute_operation("EDF file information reading process", self.processor.read_edf_info)

    def _find_and_delete_duplicates(self):
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
        metadata_list = self.processor.analyze_directory()
        df, stats = self.processor.generate_statistics(metadata_list)
        self._display_statistics(stats)
        return "Statistics generated and visualized."

    def _display_statistics(self, stats):
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