# core/db_editor.py
import csv
import logging
import os
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Any, Optional
from tabulate import tabulate

class DBEditor:
    def __init__(self, master: tk.Toplevel, db_manager: Any, text_output: Optional[tk.Text] = None):
        self.master = master
        self.db_manager = db_manager
        self.text_output = text_output
        self.current_table = None
        self._setup_ui()
        self._load_tables()

    def _setup_ui(self):
        self.master.title("Database Editor")
        self.master.geometry("1600x600")

        self.notebook = ttk.Notebook(self.master)
        self.notebook.pack(fill="both", expand=True)

        self._create_table_viewer_tab()
        self._create_sql_editor_tab()
        self._create_stats_tab()

    def _load_tables(self):
        self.table_listbox.delete(0, tk.END)
        tables = self.db_manager.get_table_names()
        for table in tables:
            self.table_listbox.insert(tk.END, table)

    def _create_table_viewer_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Tables")

        main_frame = tk.Frame(tab)
        main_frame.pack(fill="both", expand=True, padx=5, pady=5)

        list_frame = tk.Frame(main_frame, width=200)
        list_frame.pack(side="left", fill="y", padx=5, pady=5)

        tk.Label(list_frame, text="Database Tables", font=('Arial', 10, 'bold')).pack()

        self.table_listbox = tk.Listbox(list_frame)
        self.table_listbox.pack(fill="both", expand=True, pady=5)
        self.table_listbox.bind('<<ListboxSelect>>', self._on_table_select)

        self.table_data_frame = tk.Frame(main_frame)
        self.table_data_frame.pack(side="right", fill="both", expand=True, padx=5, pady=5)

        toolbar = tk.Frame(tab)
        toolbar.pack(fill="x", padx=5, pady=5)

        tk.Button(toolbar, text="Export to CSV",
                command=self._export_current_table).pack(side="left", padx=2)
        tk.Button(toolbar, text="Refresh",
                command=self._refresh_tables).pack(side="left", padx=2)

    def _create_sql_editor_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="SQL Query")

        tk.Label(tab, text="SQL Query:", font=('Arial', 10, 'bold')).pack(anchor="w")
        self.sql_input = tk.Text(tab, wrap=tk.WORD, height=8)
        self.sql_input.pack(fill="x", padx=5, pady=5)

        btn_frame = tk.Frame(tab)
        btn_frame.pack(fill="x", padx=5, pady=5)

        tk.Button(btn_frame, text="Execute",
                command=self._execute_sql).pack(side="left", padx=2)
        tk.Button(btn_frame, text="Clear",
                command=self._clear_sql).pack(side="left", padx=2)
        tk.Button(btn_frame, text="Save Query",
                command=self._save_query).pack(side="right", padx=2)
        tk.Button(btn_frame, text="Load Query",
                command=self._load_query).pack(side="right", padx=2)

        tk.Label(tab, text="Results:", font=('Arial', 10, 'bold')).pack(anchor="w")

        self.sql_results = ttk.Treeview(tab)
        self.sql_results.pack(fill="both", expand=True, padx=5, pady=5)

        scroll_y = ttk.Scrollbar(tab, orient="vertical", command=self.sql_results.yview)
        scroll_y.pack(side="right", fill="y")
        self.sql_results.configure(yscrollcommand=scroll_y.set)

        scroll_x = ttk.Scrollbar(tab, orient="horizontal", command=self.sql_results.xview)
        scroll_x.pack(side="bottom", fill="x")
        self.sql_results.configure(xscrollcommand=scroll_x.set)

    def _create_stats_tab(self):
        """Создание вкладки для статистики."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Statistics")
        self.stats_text = tk.Text(tab, wrap=tk.WORD)
        self.stats_text.pack(fill="both", expand=True, padx=5, pady=5)
        tk.Button(tab, text="Refresh Statistics",
                  command=self._show_db_stats).pack(pady=5)
        self._show_db_stats()

    def _on_table_select(self, event):
        """Обработчик выбора таблицы."""
        selection = self.table_listbox.curselection()
        if not selection:
            return

        table_name = self.table_listbox.get(selection[0])
        self.current_table = table_name
        self._display_table(table_name)

    def _display_table(self, table_name: str):
        """Отображение содержимого таблицы."""

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
            scroll_y.pack(side="right", fill="y")
            tree.configure(yscrollcommand=scroll_y.set)
            scroll_x = ttk.Scrollbar(self.table_data_frame, orient="horizontal", command=tree.xview)
            scroll_x.pack(side="bottom", fill="x")
            tree.configure(xscrollcommand=scroll_x.set)
            tree.pack(fill="both", expand=True)
            self._setup_table_context_menu(tree, table_name)
            tk.Label(self.table_data_frame,
                     text=f"Loaded {len(data)} rows from table '{table_name}'",
                     font=('Arial', 8)).pack(side="bottom")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load table data: {str(e)}")
            logging.error(f"Error displaying table {table_name}: {e}")

    def _setup_table_context_menu(self, tree: ttk.Treeview, table_name: str):
        """Настройка контекстного меню для таблицы.

        Args:
            tree: Виджет Treeview
            table_name: Имя таблицы
        """
        menu = tk.Menu(self.master, tearoff=0)
        menu.add_command(label="Copy", command=lambda: self._copy_table_data(tree))
        menu.add_command(label="Refresh", command=lambda: self._display_table(table_name))
        menu.add_command(label="Export to CSV", command=lambda: self._export_table(table_name))

        def show_menu(event):
            try:
                menu.tk_popup(event.x_root, event.y_root)
            finally:
                menu.grab_release()

        tree.bind("<Button-3>", show_menu)

    def _copy_table_data(self, tree: ttk.Treeview):
        """Копирование данных из таблицы в буфер обмена.

        Args:
            tree: Виджет Treeview с данными
        """
        try:
            selected_items = tree.selection()
            if not selected_items:
                return

            data = []
            for item in selected_items:
                values = tree.item(item, 'values')
                data.append('\t'.join(str(v) for v in values))

            self.master.clipboard_clear()
            self.master.clipboard_append('\n'.join(data))
        except Exception as e:
            messagebox.showerror("Error", f"Failed to copy data: {str(e)}")
            logging.error(f"Error copying table data: {e}")

    def _export_table(self, table_name: str):
        """Экспорт таблицы в CSV-файл.

        Args:
            table_name: Имя таблицы для экспорта
        """
        try:
            file_path = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV Files", "*.csv")],
                title=f"Export {table_name} to CSV"
            )
            if not file_path:
                return

            data = self.db_manager.get_table_data(table_name)
            columns = self.db_manager.get_table_columns(table_name)

            with open(file_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(columns)
                writer.writerows(data)

            messagebox.showinfo("Success", f"Data exported to:\n{file_path}")
            if self.text_output:
                self.text_output.insert(tk.END, f"Exported table '{table_name}' to {file_path}\n")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to export data:\n{str(e)}")
            logging.error(f"Error exporting table {table_name}: {e}")

    def _export_current_table(self):
        """Экспорт текущей выбранной таблицы."""
        if not self.current_table:
            messagebox.showwarning("Warning", "No table selected")
            return
        self._export_table(self.current_table)

    def _refresh_tables(self):
        """Обновление списка таблиц."""
        try:
            self.table_listbox.delete(0, tk.END)
            tables = self.db_manager.get_table_names()
            for table in tables:
                self.table_listbox.insert(tk.END, table)

            if self.current_table and self.current_table in tables:
                idx = tables.index(self.current_table)
                self.table_listbox.selection_set(idx)
                self._display_table(self.current_table)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to refresh tables: {str(e)}")
            logging.error(f"Error refreshing tables: {e}")

    def _execute_sql(self):
        """Выполнение SQL-запроса."""
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
                columns = [desc[0] for desc in cursor.description]
                self.sql_results["columns"] = columns
                for col in columns:
                    self.sql_results.heading(col, text=col)
                    self.sql_results.column(col, width=100)
                for row in cursor.fetchall():
                    self.sql_results.insert("", tk.END, values=row)
                messagebox.showinfo("Success",
                                    f"Query executed. Returned {len(self.sql_results.get_children())} rows")
            else:
                self.db_manager.conn.commit()
                messagebox.showinfo("Success",
                                    f"Query executed. Rows affected: {cursor.rowcount}")
            if not query.lower().strip().startswith(("select", "pragma", "explain")):
                self._refresh_tables()
                self._show_db_stats()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to execute query:\n{str(e)}")
            logging.error(f"Error executing SQL query: {e}")

    def _clear_sql(self):
        """Очистка редактора SQL."""
        self.sql_input.delete("1.0", tk.END)

    def _save_query(self):
        """Сохранение SQL-запроса в файл."""
        query = self.sql_input.get("1.0", tk.END).strip()
        if not query:
            messagebox.showwarning("Warning", "No query to save")
            return

        file_path = filedialog.asksaveasfilename(
            defaultextension=".sql",
            filetypes=[("SQL Files", "*.sql"), ("All Files", "*.*")],
            title="Save SQL Query"
        )
        if not file_path:
            return

        try:
            with open(file_path, 'w') as f:
                f.write(query)
            messagebox.showinfo("Success", "Query saved successfully")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save query: {str(e)}")
            logging.error(f"Error saving SQL query: {e}")

    def _load_query(self):
        """Загрузка SQL-запроса из файла."""
        file_path = filedialog.askopenfilename(
            filetypes=[("SQL Files", "*.sql"), ("All Files", "*.*")],
            title="Load SQL Query"
        )
        if not file_path:
            return

        try:
            with open(file_path, 'r') as f:
                query = f.read()

            self.sql_input.delete("1.0", tk.END)
            self.sql_input.insert("1.0", query)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load query: {str(e)}")
            logging.error(f"Error loading SQL query: {e}")

    def _show_db_stats(self):
        """Отображение статистики базы данных."""
        if not hasattr(self, 'stats_text'):
            return
        self.stats_text.delete(1.0, tk.END)
        try:
            self.stats_text.insert(tk.END, "=== DATABASE STATISTICS ===\n\n")
            db_size = os.path.getsize(self.db_manager.db_path) / (1024 * 1024)
            self.stats_text.insert(tk.END, f"Database file: {self.db_manager.db_path}\n")
            self.stats_text.insert(tk.END, f"Size: {db_size:.2f} MB\n\n")
            stats = self.db_manager.get_database_stats()
            self.stats_text.insert(tk.END, "=== RECORD COUNTS ===\n")
            self.stats_text.insert(tk.END, tabulate([
                ["Patients", stats['patients']],
                ["EDF Files", stats['edf_files']],
                ["Segments", stats['segments']],
                ["Diagnoses", stats['diagnoses']]
            ], headers=["Table", "Records"], tablefmt="pretty") + "\n\n")
            seg_stats = self.db_manager.get_segment_duration_stats()
            if seg_stats:
                self.stats_text.insert(tk.END, "=== SEGMENT DURATION STATISTICS ===\n")
                self.stats_text.insert(tk.END, "Duration calculated as (end_time - start_time)\n")
                self.stats_text.insert(tk.END, tabulate([
                    ["Average duration", f"{seg_stats['avg']:.2f} sec"],
                    ["Shortest segment", f"{seg_stats['min']:.2f} sec"],
                    ["Longest segment", f"{seg_stats['max']:.2f} sec"]
                ], tablefmt="pretty") + "\n\n")
            else:
                self.stats_text.insert(tk.END, "Segment duration statistics not available\n\n")
            self.stats_text.insert(tk.END, "=== ADDITIONAL STATISTICS ===\n")
            gender_stats = self.db_manager.get_gender_distribution()
            if gender_stats:
                self.stats_text.insert(tk.END, "\nGender Distribution:\n")
                self.stats_text.insert(tk.END, tabulate(
                    gender_stats.items(),
                    headers=["Gender", "Count"],
                    tablefmt="pretty") + "\n")
            age_stats = self.db_manager.get_age_statistics()
            if age_stats:
                self.stats_text.insert(tk.END, "\nPatient Age Statistics:\n")
                self.stats_text.insert(tk.END, tabulate([
                    ["Average age", f"{age_stats['avg']:.1f} years"],
                    ["Youngest patient", f"{age_stats['min']} years"],
                    ["Oldest patient", f"{age_stats['max']} years"]
                ], tablefmt="pretty") + "\n")
            self.stats_text.insert(tk.END, f"\nReport generated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        except Exception as e:
            error_msg = f"Error retrieving database stats: {str(e)}"
            self.stats_text.insert(tk.END, error_msg + "\n")
            logging.error(f"Error showing DB stats: {e}")