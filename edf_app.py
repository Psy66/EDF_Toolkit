# edf_app.py
import tkinter.font as tkfont
import csv
import os
import tkinter as tk
import logging
from tkinter import filedialog, messagebox, scrolledtext, ttk
from config.settings import settings
from core.edf_processor import EDFProcessor
from core.edf_segmentor import EDFSegmentor
from core.db_manager import DBManager
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
        self.db_manager = None
        self._setup_ui()

    def _try_autoload_db(self):
        """Attempt to automatically load existing database"""
        if not self.directory:
            return
        db_path = os.path.join(self.directory, "DB", "eeg_database.db")
        if os.path.exists(db_path):
            try:
                self.db_manager = DBManager(self.directory)
                self._enable_db_buttons()
                self._update_db_status()
                self.text_output.insert(tk.END, "Automatically loaded existing database\n")
                if hasattr(self, 'segmentor') and self.segmentor and hasattr(self.segmentor, 'current_file_path'):
                    for btn in self.button_frame.winfo_children():
                        if isinstance(btn, tk.Button) and btn["text"] == "Fill":
                            btn.config(state=tk.NORMAL)
            except Exception as e:
                self.text_output.insert(tk.END, f"Error loading database: {str(e)}\n")

    def _setup_ui(self):
        """Initialize the user interface with all buttons in one frame."""
        # Main button frame
        self.button_frame = tk.Frame(self.root)
        self.button_frame.pack(pady=10)
        for i in range(12):
            self.button_frame.grid_columnconfigure(i, weight=1)
        tk.Label(self.button_frame, text="Batch Processing:", font=("Arial", 11)) \
            .grid(row=0, column=0, padx=5, pady=5, sticky="w")
        batch_buttons = [
            ("Open", self.select_directory, "Select folder with EDF files"),
            ("Rename", self.rename_files, "Rename EDF files by metadata"),
            ("Check", self.check_corrupted, "Check for corrupted files"),
            ("Dupes", self.find_duplicates, "Find and delete duplicates"),
            ("Similar", self.find_similar_time, "Find files with similar times"),
            ("Stats", self.generate_stats, "Generate statistics"),
            ("Patients", self.generate_patient_table, "Create patient table"),
            ("Random", self.randomize_filenames, "Randomize filenames"),
            ("Anonym", self.remove_patient_info, "Remove patient info"),
            ("Info", self.read_edf_info, "Show EDF file info"),
        ]
        for idx, (text, command, tooltip) in enumerate(batch_buttons):
            btn = tk.Button(self.button_frame, text=text, width=8, command=command,
                            state=tk.DISABLED if idx > 0 else tk.NORMAL)
            btn.grid(row=0, column=idx + 1, padx=2, pady=5, sticky="ew")
            self._create_tooltip(btn, tooltip)
        tk.Label(self.button_frame, text="Segmentation:", font=("Arial", 11)) \
            .grid(row=1, column=0, padx=5, pady=5, sticky="w")
        seg_buttons = [
            ("Load", self.load_edf_file, "Load EDF file"),
            ("Split", self.split_into_segments, "Split into segments"),
        ]
        for idx, (text, command, tooltip) in enumerate(seg_buttons):
            btn = tk.Button(self.button_frame, text=text, width=8, command=command, state=tk.DISABLED)
            btn.grid(row=1, column=idx + 1, padx=2, pady=5, sticky="ew")
            self._create_tooltip(btn, tooltip)
        tk.Label(self.button_frame, text="Min (sec):", font=("Arial", 9)) \
            .grid(row=1, column=3, padx=2, pady=5, sticky="e")
        self.min_duration_entry = tk.Entry(self.button_frame, width=6)
        self.min_duration_entry.insert(0, str(settings.MIN_SEGMENT_DURATION))
        self.min_duration_entry.grid(row=1, column=4, padx=2, pady=5, sticky="w")
        tk.Button(self.button_frame, text="Set", width=4, command=self.apply_min_duration) \
            .grid(row=1, column=5, padx=2, pady=5, sticky="w")
        tk.Label(self.button_frame, text="Database:", font=("Arial", 11)) \
            .grid(row=2, column=0, padx=5, pady=5, sticky="w")
        db_buttons = [
            ("Create", self.create_database, "Create new database"),
            ("Fill", self.fill_segments, "Fill with segments"),
            ("Stats", self.show_db_stats, "Show statistics"),
            ("Edit", self.edit_database, "View/edit tables"),
        ]
        for idx, (text, command, tooltip) in enumerate(db_buttons):
            btn = tk.Button(self.button_frame, text=text, width=8, command=command,
                            state=tk.NORMAL if idx == 0 else tk.DISABLED)
            btn.grid(row=2, column=idx + 1, padx=2, pady=5, sticky="ew")
            self._create_tooltip(btn, tooltip)
        self.db_status_label = tk.Label(self.button_frame, text="[DB Not Created]", fg="red")
        self.db_status_label.grid(row=2, column=6, columnspan=4, padx=5, pady=5, sticky="w")
        tk.Button(self.button_frame, text="Exit", width=8, command=self.root.quit) \
            .grid(row=2, column=10, padx=2, pady=5, sticky="e")
        self.text_output = scrolledtext.ScrolledText(self.root, wrap=tk.WORD, width=210, height=40)
        self.text_output.pack(pady=10)
        self.text_output.bind("<Control-c>", self._copy_text)
        self.text_output.bind("<Control-a>", self._select_all_text)
        self.context_menu = tk.Menu(self.root, tearoff=0)
        self.context_menu.add_command(label="Copy", command=self._copy_text)
        self.text_output.bind("<Button-3>", self._show_context_menu)

    def _display_table(self, parent, table_name):
        """Отобразить содержимое таблицы с возможностью сортировки и контекстного меню."""
        for widget in parent.winfo_children():
            if isinstance(widget, tk.Frame) and widget != parent.winfo_children()[0]:
                widget.destroy()
        try:
            table_container = tk.Frame(parent)
            table_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            toolbar = tk.Frame(table_container)
            toolbar.pack(fill=tk.X, pady=(0, 5))
            refresh_btn = tk.Button(toolbar, text="🔄 Обновить",
                                    command=lambda: self._refresh_table(table_container, table_name),
                                    bd=1, relief=tk.RAISED)
            refresh_btn.pack(side=tk.LEFT, padx=2)
            export_btn = tk.Button(toolbar, text="💾 Экспорт в CSV",
                                   command=lambda: self._export_table(table_name),
                                   bd=1, relief=tk.RAISED)
            export_btn.pack(side=tk.LEFT, padx=2)
            columns = self.db_manager.get_table_columns(table_name)
            data = self.db_manager.get_table_data(table_name)
            table_frame = tk.Frame(table_container)
            table_frame.pack(fill=tk.BOTH, expand=True)
            scroll_y = tk.Scrollbar(table_frame)
            scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
            scroll_x = tk.Scrollbar(table_frame, orient=tk.HORIZONTAL)
            scroll_x.pack(side=tk.BOTTOM, fill=tk.X)
            self.tree = ttk.Treeview(table_frame, columns=columns, show="headings",
                                     yscrollcommand=scroll_y.set,
                                     xscrollcommand=scroll_x.set,
                                     selectmode='extended')
            self.tree.pack(fill=tk.BOTH, expand=True)
            scroll_y.config(command=self.tree.yview)
            scroll_x.config(command=self.tree.xview)
            for col in columns:
                self.tree.heading(col, text=col,
                                  command=lambda c=col: self._sort_treeview(self.tree, c, False))
                self.tree.column(col, width=tkfont.Font().measure(col) + 20,
                                 stretch=tk.YES, anchor=tk.W)
            if len(data) > 1000:
                progress = ttk.Progressbar(table_container, orient=tk.HORIZONTAL,
                                           length=200, mode='determinate')
                progress.pack(pady=5)
                progress["maximum"] = len(data)
                batch_size = 100
                for i in range(0, len(data), batch_size):
                    batch = data[i:i + batch_size]
                    for row in batch:
                        self.tree.insert("", tk.END, values=row)
                    progress["value"] = i + len(batch)
                    table_container.update()
                progress.destroy()
            else:
                for row in data:
                    self.tree.insert("", tk.END, values=row)
            self._auto_resize_columns(self.tree, columns)
            self._setup_table_context_menu(table_name)
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось отобразить таблицу {table_name}:\n{str(e)}")

    def _sort_treeview(self, tree, col, reverse):
        """Сортировка Treeview по колонке."""
        data = [(tree.set(child, col), child) for child in tree.get_children('')]
        data.sort(reverse=reverse)
        for index, (val, child) in enumerate(data):
            tree.move(child, '', index)
        tree.heading(col, command=lambda: self._sort_treeview(tree, col, not reverse))

    def _auto_resize_columns(self, tree, columns):
        """Автоматическая подстройка ширины колонок."""
        for col in columns:
            max_width = tkfont.Font().measure(col)
            for row in tree.get_children():
                cell_value = tree.set(row, col)
                max_width = max(max_width, tkfont.Font().measure(str(cell_value)))
            tree.column(col, width=max_width + 20)

    def _setup_table_context_menu(self, table_name):
        """Настройка контекстного меню для таблицы."""
        menu = tk.Menu(self.tree, tearoff=0)
        menu.add_command(label="Копировать", command=self._copy_table_data)
        menu.add_command(label="Редактировать",
                         command=lambda: self._edit_record(table_name))
        menu.add_command(label="Удалить",
                         command=lambda: self._delete_record(table_name))
        self.tree.bind("<Button-3>", lambda event: menu.post(event.x_root, event.y_root))

    def _refresh_table(self, container, table_name):
        """Обновить содержимое таблицы."""
        self._display_table(container, table_name)

    def _export_table(self, table_name):
        """Экспорт таблицы в CSV файл."""
        try:
            file_path = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV Files", "*.csv")],
                title=f"Export {table_name} to CSV"
            )
            if file_path:
                data = self.db_manager.get_table_data(table_name)
                columns = self.db_manager.get_table_columns(table_name)
                with open(file_path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(columns)
                    writer.writerows(data)
                messagebox.showinfo("Успех", f"Данные экспортированы в:\n{file_path}")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось экспортировать данные:\n{str(e)}")

    def edit_database(self):
        """Open database editor window."""
        if not self.db_manager:
            messagebox.showwarning("Error", "Database not created. Please create database first.")
            return
        editor = tk.Toplevel(self.root)
        editor.title("Database Editor")
        editor.geometry("1200x600")
        notebook = ttk.Notebook(editor)
        self._create_table_viewer_tab(notebook)
        self._create_sql_editor_tab(notebook)
        notebook.pack(fill="both", expand=True)

    def _load_table_data(self, event):
        """Load selected table data"""
        selection = self.table_listbox.curselection()
        if not selection:
            return
        table_name = self.table_listbox.get(selection[0])
        for widget in self.table_data_frame.winfo_children():
            widget.destroy()
        try:
            columns = self.db_manager.get_table_columns(table_name)
            data = self.db_manager.get_table_data(table_name)
            tree = ttk.Treeview(self.table_data_frame, columns=columns, show="headings")
            for col in columns:
                tree.heading(col, text=col)
                tree.column(col, width=100, anchor=tk.W)
            for row in data:
                tree.insert("", tk.END, values=row)
            scroll_y = ttk.Scrollbar(self.table_data_frame, orient="vertical", command=tree.yview)
            scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
            tree.configure(yscrollcommand=scroll_y.set)
            scroll_x = ttk.Scrollbar(self.table_data_frame, orient="horizontal", command=tree.xview)
            scroll_x.pack(side=tk.BOTTOM, fill=tk.X)
            tree.configure(xscrollcommand=scroll_x.set)
            tree.pack(fill=tk.BOTH, expand=True)
            tk.Label(self.table_data_frame,
                     text=f"Loaded {len(data)} rows from table '{table_name}'",
                     font=('Arial', 8)).pack(side=tk.BOTTOM)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load table data: {str(e)}")

    def _execute_sql(self):
        """Execute SQL query from editor"""
        query = self.sql_input.get("1.0", tk.END).strip()
        if not query:
            messagebox.showwarning("Warning", "Please enter a SQL query")
            return
        try:
            cursor = self.db_manager.conn.cursor()
            cursor.execute(query)
            for row in self.sql_results.get_children():
                self.sql_results.delete(row)
            self.sql_results["columns"] = []
            if query.lower().strip().startswith(("select", "pragma", "explain")):
                # For SELECT queries - show results in table
                columns = [desc[0] for desc in cursor.description]
                self.sql_results["columns"] = columns
                for col in columns:
                    self.sql_results.heading(col, text=col)
                    self.sql_results.column(col, width=100)
                for row in cursor.fetchall():
                    self.sql_results.insert("", tk.END, values=row)
                messagebox.showinfo("Success", f"Query executed. Returned {len(self.sql_results.get_children())} rows")
            else:
                self.db_manager.conn.commit()
                messagebox.showinfo("Success", f"Query executed. Rows affected: {cursor.rowcount}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to execute query:\n{str(e)}")

    def _run_quick_query(self, query_template):
        """Run predefined quick query"""
        selection = self.table_listbox.curselection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a table first")
            return

        table_name = self.table_listbox.get(selection[0])
        query = query_template.format(table=table_name)
        self.sql_input.delete("1.0", tk.END)
        self.sql_input.insert("1.0", query)
        if hasattr(self, 'notebook'):
            self.notebook.select(1)  # Switch to SQL tab

    def _clear_sql(self):
        """Clear SQL query editor"""
        self.sql_input.delete("1.0", tk.END)

    def _save_query(self):
        """Save current query to file"""
        query = self.sql_input.get("1.0", tk.END).strip()
        if not query:
            messagebox.showwarning("Warning", "No query to save")
            return
        file_path = filedialog.asksaveasfilename(
            defaultextension=".sql",
            filetypes=[("SQL Files", "*.sql"), ("All Files", "*.*")],
            title="Save SQL Query"
        )
        if file_path:
            try:
                with open(file_path, 'w') as f:
                    f.write(query)
                messagebox.showinfo("Success", "Query saved successfully")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save query: {str(e)}")

    def _load_query(self):
        """Load SQL query from file"""
        file_path = filedialog.askopenfilename(
            filetypes=[("SQL Files", "*.sql"), ("All Files", "*.*")],
            title="Load SQL Query"
        )
        if file_path:
            try:
                with open(file_path, 'r') as f:
                    query = f.read()
                self.sql_input.delete("1.0", tk.END)
                self.sql_input.insert("1.0", query)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load query: {str(e)}")

    def _create_table_viewer_tab(self, notebook):
        """Create tab with table selection and viewing"""
        table_frame = ttk.Frame(notebook)
        notebook.add(table_frame, text="Tables")
        list_frame = ttk.Frame(table_frame, width=200)
        list_frame.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5)
        tk.Label(list_frame, text="Database Tables", font=('Arial', 10, 'bold')).pack()
        self.table_listbox = tk.Listbox(list_frame)
        self.table_listbox.pack(fill=tk.BOTH, expand=True, pady=5)
        for table in ["patients", "edf_files", "segments", "diagnosis"]:
            self.table_listbox.insert(tk.END, table)
        self.table_listbox.bind('<<ListboxSelect>>', self._load_table_data)
        self.table_data_frame = ttk.Frame(table_frame)
        self.table_data_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)

    def _create_sql_editor_tab(self, notebook):
        """Create tab with SQL query editor"""
        sql_frame = ttk.Frame(notebook)
        notebook.add(sql_frame, text="SQL Query")

        # SQL input area
        tk.Label(sql_frame, text="SQL Query:", font=('Arial', 10, 'bold')).pack(anchor=tk.W)

        self.sql_input = scrolledtext.ScrolledText(sql_frame, wrap=tk.WORD, height=8)
        self.sql_input.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Button frame
        btn_frame = ttk.Frame(sql_frame)
        btn_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Button(btn_frame, text="Execute", command=self._execute_sql).pack(side=tk.LEFT)
        ttk.Button(btn_frame, text="Clear", command=self._clear_sql).pack(side=tk.LEFT)
        ttk.Button(btn_frame, text="Save Query", command=self._save_query).pack(side=tk.RIGHT)
        ttk.Button(btn_frame, text="Load Query", command=self._load_query).pack(side=tk.RIGHT)

        # Results area
        tk.Label(sql_frame, text="Results:", font=('Arial', 10, 'bold')).pack(anchor=tk.W)

        self.sql_results = ttk.Treeview(sql_frame)
        self.sql_results.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        scroll_y = ttk.Scrollbar(sql_frame, orient="vertical", command=self.sql_results.yview)
        scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        self.sql_results.configure(yscrollcommand=scroll_y.set)

        scroll_x = ttk.Scrollbar(sql_frame, orient="horizontal", command=self.sql_results.xview)
        scroll_x.pack(side=tk.BOTTOM, fill=tk.X)
        self.sql_results.configure(xscrollcommand=scroll_x.set)

    def create_database(self):
        """Создать новую базу данных в папке DB."""
        try:
            if not self.directory:
                messagebox.showwarning("Ошибка", "Сначала выберите рабочую папку")
                return
            db_folder = os.path.join(self.directory, "DB")
            db_path = os.path.join(db_folder, "eeg_database.db")
            os.makedirs(db_folder, exist_ok=True)
            if os.path.exists(db_path):
                if not messagebox.askyesno("Подтверждение",
                                           "База данных уже существует. Пересоздать?"):
                    self.text_output.insert(tk.END, "Используется существующая БД\n")
                    return
            self.db_manager = DBManager(self.directory)
            if not self.db_manager.database_exists():
                raise RuntimeError("Не удалось создать файл БД")
            self.text_output.insert(tk.END, f"База данных создана в:\n{db_path}\n")
            self._enable_db_buttons()
            self._update_db_status()

        except Exception as e:
            error_msg = f"Error creating database: {str(e)}"
            self.text_output.insert(tk.END, error_msg + "\n")
            messagebox.showerror("Database Error", error_msg)
            if hasattr(self, 'db_manager'):
                del self.db_manager

    def _enable_db_buttons(self):
        """Активировать кнопки работы с базой данных."""
        db_buttons = ["Fill", "Stats", "Edit"]  # Сокращенные названия кнопок из _setup_ui
        for btn in self.button_frame.winfo_children():
            if isinstance(btn, tk.Button) and btn["text"] in db_buttons:
                btn.config(state=tk.NORMAL)

    def _update_db_status(self):
        """Обновить статус базы данных в интерфейсе."""
        if hasattr(self, 'db_manager') and self.db_manager:
            db_name = os.path.basename(self.db_manager.db_path)
            size = os.path.getsize(self.db_manager.db_path) / 1024  # Размер в KB
            self.db_status_label.config(
                text=f"DB: {db_name} ({size:.1f} KB)",
                fg="green",
                font=("Arial", 9, "bold")
            )

    def show_db_stats(self):
        """Показать статистику базы данных с очисткой экрана."""
        self.text_output.delete(1.0, tk.END)  # Очищаем экран
        if not hasattr(self, 'db_manager') or not self.db_manager:
            self.text_output.insert(tk.END, "Database not initialized. Please create database first.\n")
            return
        try:
            stats = self.db_manager.get_database_stats()
            self.text_output.insert(tk.END, "=== DATABASE STATISTICS ===\n")
            self.text_output.insert(tk.END, f"Location: {self.db_manager.db_path}\n\n")
            self.text_output.insert(tk.END, "Records Count:\n")
            self.text_output.insert(tk.END, f"- Patients: {stats['patients']}\n")
            self.text_output.insert(tk.END, f"- EDF Files: {stats['edf_files']}\n")
            self.text_output.insert(tk.END, f"- Segments: {stats['segments']}\n")
            self.text_output.insert(tk.END, f"- Diagnoses: {stats['diagnoses']}\n\n")
            self.text_output.insert(tk.END, "Last Added:\n")
            try:
                last_patient = self.db_manager.get_last_record("patients")
                last_edf = self.db_manager.get_last_record("edf_files")
                self.text_output.insert(tk.END, f"- Last Patient: {last_patient[1]} (ID: {last_patient[0]})\n")
                self.text_output.insert(tk.END, f"- Last EDF File: {last_edf[0]} (Channels: {last_edf[4]})\n")
            except Exception as e:
                self.text_output.insert(tk.END, f"- Additional info unavailable: {str(e)}\n")
        except Exception as e:
            error_msg = f"Error retrieving database stats: {str(e)}"
            self.text_output.insert(tk.END, error_msg + "\n")
            messagebox.showerror("Database Error", error_msg)

    def fill_segments(self):
        """Заполнить базу данных сегментами из текущего словаря."""
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
            self._show_db_stats()
        except ValueError as e:
            self.text_output.insert(tk.END, f"Error adding segments: {e}\n")
            messagebox.showerror("Error", str(e))
        except Exception as e:
            self.text_output.insert(tk.END, f"Unexpected error: {e}\n")
            messagebox.showerror("Error", f"Failed to add segments: {e}")

    def _show_db_stats(self):
        """Показать статистику базы данных."""
        if not self.db_manager:
            self.text_output.insert(tk.END, "Database not initialized.\n")
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
                if isinstance(btn, tk.Button) and btn["text"] != "Open":
                    btn.config(state=tk.NORMAL)
            self._try_autoload_db()

    def load_edf_file(self):
        """Load an EDF file for segmentation."""
        file_path = filedialog.askopenfilename(filetypes=[("EDF files", "*.edf")])
        if file_path:
            self.segmentor = EDFSegmentor(self.text_output)
            self.segmentor.current_file_path = file_path  # Сохраняем путь к файлу
            self.segmentor.load_metadata(file_path)
            for btn in self.button_frame.winfo_children():
                if isinstance(btn, tk.Button) and btn["text"] == "Split into Segments":
                    btn.config(state=tk.NORMAL)
            if self.db_manager:
                for btn in self.button_frame.winfo_children():
                    if isinstance(btn, tk.Button) and btn["text"] == "Fill Segments":
                        btn.config(state=tk.NORMAL)

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