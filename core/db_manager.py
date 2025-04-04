# core/db_manager.py
import os
import sqlite3
from datetime import datetime
import hashlib
import logging
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

@dataclass
class Patient:
    patient_id: int
    name: str
    gender: str
    birthday: str
    note: str = ""

@dataclass
class EDFFile:
    edf_id: int
    patient_id: int
    file_hash: str
    start_date: str
    eeg_ch: int
    rate: float
    montage: str = ""
    notes: str = ""

@dataclass
class Segment:
    seg_id: int
    patient_id: int
    edf_id: int
    seg_fpath: str
    start_time: float
    end_time: float
    l_marker: str
    r_marker: str
    notes: str = ""

@dataclass
class Diagnosis:
    patient_id: int
    ds_code: str
    ds_descript: str
    notes: str = ""

class DBManager:
    """Database manager for storing and retrieving data."""
    def __init__(self, directory: str = ""):
        """Initialize the database manager."""
        self.directory = os.path.join(directory, "DB") if directory else "DB"
        os.makedirs(self.directory, exist_ok=True)
        self.db_path = os.path.join(self.directory, "eeg_database.db")
        self.segments_dir = os.path.join(self.directory, "segments")
        os.makedirs(self.segments_dir, exist_ok=True)
        self.conn = None
        self._initialize_db()

    def _initialize_db(self):
        """Initialize database connection and create tables if they don't exist."""
        db_dir = os.path.dirname(self.db_path)
        if not os.path.exists(db_dir):
            os.makedirs(db_dir)
            logging.info(f"Created database directory: {db_dir}")

        self.conn = sqlite3.connect(self.db_path)
        self._create_tables()

    def _create_tables(self):
        """Create database tables if they don't exist."""
        cursor = self.conn.cursor()

        # Patients table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS patients (
            patient_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            gender TEXT CHECK(gender IN ('M', 'F', 'N')) DEFAULT 'N',
            birthday TEXT,
            note TEXT DEFAULT ''
        )
        """)

        # EDF files table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS edf_files (
            edf_id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER NOT NULL,
            start_date TEXT NOT NULL,
            eeg_ch INTEGER NOT NULL,
            rate REAL NOT NULL,
            montage TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            file_hash TEXT UNIQUE NOT NULL,
            FOREIGN KEY (patient_id) REFERENCES patients (patient_id)
        )
        """)

        # Segments table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS segments (
            seg_id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER NOT NULL,
            edf_id INTEGER NOT NULL,
            start_time REAL NOT NULL,
            end_time REAL NOT NULL,
            l_marker TEXT NOT NULL,
            r_marker TEXT NOT NULL,
            notes TEXT DEFAULT '',
            seg_fpath TEXT UNIQUE NOT NULL,
            FOREIGN KEY (patient_id) REFERENCES patients (patient_id),
            FOREIGN KEY (edf_id) REFERENCES edf_files (edf_id)
        )
        """)

        # Diagnosis table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS diagnosis (
            patient_id INTEGER NOT NULL,
            ds_code TEXT NOT NULL,
            ds_descript TEXT NOT NULL,
            note TEXT DEFAULT '',
            PRIMARY KEY (patient_id, ds_code),
            FOREIGN KEY (patient_id) REFERENCES patients (patient_id)
        )
        """)
        self.conn.commit()

    def get_last_record(self, table_name: str):
        """Get the last record from a table."""
        cursor = self.conn.cursor()
        cursor.execute(f"SELECT * FROM {table_name} ORDER BY ROWID DESC LIMIT 1")
        return cursor.fetchone()

    def database_size(self) -> int:
        """Get the size of the database in bytes."""
        return os.path.getsize(self.db_path)

    def get_table_names(self):
        """Возвращает список всех таблиц в базе данных."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [table[0] for table in cursor.fetchall()]
        cursor.close()
        return tables

    def get_table_data(self, table_name: str) -> List[Tuple]:
        """Get all data from a table."""
        cursor = self.conn.cursor()
        cursor.execute(f"SELECT * FROM {table_name}")
        return cursor.fetchall()

    def get_table_columns(self, table_name: str) -> List[str]:
        """Get column names from a table."""
        cursor = self.conn.cursor()
        cursor.execute(f"PRAGMA table_info({table_name})")
        return [column[1] for column in cursor.fetchall()]

    def database_exists(self) -> bool:
        """Check if database file exists."""
        return os.path.exists(self.db_path)

    def add_patient(self, name: str, gender: str, birthday: str, note: str = "") -> int:
        """Add a new patient to the database or return existing patient_id if patient already exists."""
        try:
            datetime.strptime(birthday, '%d.%m.%Y')
        except ValueError:
            raise ValueError("Invalid birthday format. Expected 'ДД.ММ.ГГГГ'")

        cursor = self.conn.cursor()
        cursor.execute("SELECT patient_id FROM patients WHERE name = ?", (name,))
        result = cursor.fetchone()
        if result:
            return result[0]

        cursor.execute(
            "INSERT INTO patients (name, gender, birthday, note) VALUES (?, ?, ?, ?)",
            (name, gender, birthday, note)
        )
        self.conn.commit()
        return cursor.lastrowid

    def get_table_data_for_export(self, table_name):
        """Получить данные таблицы в виде списка списков."""
        cursor = self.conn.cursor()
        cursor.execute(f"SELECT * FROM {table_name}")
        return cursor.fetchall()

    def add_edf_file(self, patient_id: int, file_hash: str, start_date: str,
                     eeg_ch: int, rate: float, montage: str = "", notes: str = "") -> int:
        """Add a new EDF file to the database."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT edf_id FROM edf_files WHERE file_hash = ?", (file_hash,))
        result = cursor.fetchone()
        if result:
            raise ValueError(f"EDF file with hash {file_hash} already exists in database (edf_id: {result[0]})")

        try:
            datetime.strptime(start_date, '%d.%m.%Y %H:%M')
        except ValueError:
            raise ValueError("Invalid date format. Expected 'ДД.ММ.ГГГГ ЧЧ:ММ'")

        cursor.execute(
            "INSERT INTO edf_files (patient_id, file_hash, start_date, eeg_ch, rate, montage, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (patient_id, file_hash, start_date, eeg_ch, rate, montage, notes)
        )
        self.conn.commit()
        return cursor.lastrowid

    def add_segment(self, patient_id: int, edf_id: int, seg_fpath: str,
                    start_time: float, end_time: float, l_marker: str,
                    r_marker: str, notes: str = "") -> int:
        """Add a new segment to the database."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT seg_id FROM segments WHERE seg_fpath = ?", (seg_fpath,))
        result = cursor.fetchone()
        if result:
            raise ValueError(f"Segment with path {seg_fpath} already exists in database (seg_id: {result[0]})")
        cursor.execute(
            "INSERT INTO segments (patient_id, edf_id, seg_fpath, start_time, end_time, l_marker, r_marker, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (patient_id, edf_id, seg_fpath, start_time, end_time, l_marker, r_marker, notes)
        )
        self.conn.commit()
        return cursor.lastrowid

    def add_diagnosis(self, patient_id: int, ds_code: str, ds_descript: str, note: str = ""):
        """Add a diagnosis for a patient."""
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT INTO diagnosis (patient_id, ds_code, ds_descript, note) VALUES (?, ?, ?, ?)",
            (patient_id, ds_code, ds_descript, note)
        )
        self.conn.commit()

    def get_patient_by_name(self, name: str) -> Optional[Patient]:
        """Get patient by name."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM patients WHERE name = ?", (name,))
        row = cursor.fetchone()
        return Patient(*row) if row else None

    def get_edf_file_by_hash(self, file_hash: str) -> Optional[EDFFile]:
        """Get EDF file by its hash."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM edf_files WHERE file_hash = ?", (file_hash,))
        row = cursor.fetchone()
        return EDFFile(*row) if row else None

    def get_segments_by_edf(self, edf_id: int) -> List[Segment]:
        """Get all segments for a specific EDF file."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM segments WHERE edf_id = ?", (edf_id,))
        return [Segment(*row) for row in cursor.fetchall()]

    def get_patient_diagnoses(self, patient_id: int) -> List[Diagnosis]:
        """Get all diagnoses for a specific patient."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM diagnosis WHERE patient_id = ?", (patient_id,))
        return [Diagnosis(*row) for row in cursor.fetchall()]

    def get_database_stats(self) -> Dict[str, int]:
        """Get statistics about database records."""
        cursor = self.conn.cursor()
        stats = {}
        cursor.execute("SELECT COUNT(*) FROM patients")
        stats['patients'] = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM edf_files")
        stats['edf_files'] = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM segments")
        stats['segments'] = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM diagnosis")
        stats['diagnoses'] = cursor.fetchone()[0]
        return stats

    def fill_segments_from_dict(self, seg_dict: Dict, edf_file_path: str) -> Tuple[int, int]:
        """Fill database with segments from the segment dictionary."""
        file_hash = self._calculate_file_hash(edf_file_path)
        if self.get_edf_file_by_hash(file_hash):
            raise ValueError("EDF file already exists in database")
        first_seg = next(iter(seg_dict.values()))
        raw = first_seg['data'].info
        subject_info = raw.get('subject_info', {})
        name = " ".join([
            subject_info.get('first_name', ''),
            subject_info.get('middle_name', ''),
            subject_info.get('last_name', '')
        ]).strip()
        gender = subject_info.get('sex', 'N')
        if gender == 1:
            gender = 'M'
        elif gender == 2:
            gender = 'F'
        else:
            gender = 'N'
        birthdate = subject_info.get('birthday')
        if birthdate:
            if hasattr(birthdate, 'strftime'):
                birthdate = birthdate.strftime('%d.%m.%Y')
            elif isinstance(birthdate, str):
                try:
                    try:
                        dt = datetime.strptime(birthdate, '%Y-%m-%d')
                        birthdate = dt.strftime('%d.%m.%Y')
                    except ValueError:
                        datetime.strptime(birthdate, '%d.%m.%Y')
                except ValueError:
                    birthdate = None
        try:
            patient_id = self.add_patient(name, gender, birthdate if birthdate else '01.01.1900')
        except ValueError as e:
            logging.error(f"Failed to add patient: {str(e)}")
            raise
        eeg_ch = len([ch for ch in raw['ch_names'] if 'EEG' in ch])
        rate = raw['sfreq']
        start_date = raw.get('meas_date', datetime.now())
        if isinstance(start_date, (float, int)):
            start_date = datetime.fromtimestamp(start_date)
        start_date_str = start_date.strftime('%d.%m.%Y %H:%M')
        try:
            edf_id = self.add_edf_file(
                patient_id=patient_id,
                file_hash=file_hash,
                start_date=start_date_str,
                eeg_ch=eeg_ch,
                rate=rate
            )
        except ValueError as e:
            logging.error(f"Failed to add EDF file: {str(e)}")
            raise
        base_dir = os.path.join(
            self.segments_dir,
            os.path.splitext(os.path.basename(edf_file_path))[0]
        )
        os.makedirs(base_dir, exist_ok=True)
        for seg_name, seg_data in seg_dict.items():
            clean_seg_name = "".join(c if c.isalnum() else "_" for c in seg_name)
            seg_fname = f"seg_{clean_seg_name}_eeg.fif"
            seg_fpath = os.path.join(base_dir, seg_fname)
            try:
                seg_data['data'].save(seg_fpath, overwrite=True)
                self.add_segment(
                    patient_id=patient_id,
                    edf_id=edf_id,
                    seg_fpath=seg_fpath,
                    start_time=seg_data['start_time'],
                    end_time=seg_data['end_time'],
                    l_marker=seg_data['current_event'],
                    r_marker=seg_data['next_event']
                )
            except Exception as e:
                logging.error(f"Failed to add segment {seg_name}: {str(e)}")
                continue

        return patient_id, edf_id

    @staticmethod
    def parse_date(date_str: str) -> datetime:
        """Parse date string in format 'ДД.ММ.ГГГГ ЧЧ:ММ' to datetime"""
        return datetime.strptime(date_str, '%d.%m.%Y %H:%M')

    @staticmethod
    def format_date(dt: datetime) -> str:
        """Format datetime to string in format 'ДД.ММ.ГГГГ ЧЧ:ММ'"""
        return dt.strftime('%d.%m.%Y %H:%M')

    @staticmethod
    def validate_birthday(birthday: str) -> bool:
        """Validate birthday format (ДД.ММ.ГГГГ)"""
        try:
            datetime.strptime(birthday, '%d.%m.%Y')
            return True
        except ValueError:
            return False

    @staticmethod
    def calculate_age(birthday: str, default_age: int = 0) -> int:
        """Calculate age from birthday (format: 'ДД.ММ.ГГГГ')

        Args:
            birthday: Дата рождения в формате 'ДД.ММ.ГГГГ'
            default_age: Значение, возвращаемое при ошибке (по умолчанию 0)

        Returns:
            Возраст в годах или default_age, если дата некорректна
        """
        if not birthday:
            return default_age

        try:
            birth_date = datetime.strptime(birthday, '%d.%m.%Y')
        except ValueError:
            return default_age

        today = datetime.now()
        age = today.year - birth_date.year
        if (today.month, today.day) < (birth_date.month, birth_date.day):
            age -= 1
        return age

    def get_avg_segment_duration(self):
        """Get average duration of all segments in seconds"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT AVG(duration) FROM segments")
        return cursor.fetchone()[0] or 0

    def get_gender_distribution(self):
        """Get gender distribution statistics"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT gender, COUNT(*) FROM patients GROUP BY gender")
        return dict(cursor.fetchall())

    def get_age_statistics(self):
        """Get age statistics (avg, min, max) calculated from birthday"""
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                SELECT 
                    AVG((julianday('now') - julianday(birthday, '%d.%m.%Y')) / 365.25),
                    MIN((julianday('now') - julianday(birthday, '%d.%m.%Y')) / 365.25),
                    MAX((julianday('now') - julianday(birthday, '%d.%m.%Y')) / 365.25)
                FROM patients
                WHERE birthday IS NOT NULL
            """)
            result = cursor.fetchone()
            if result and result[0] is not None:
                return {
                    'avg': result[0],
                    'min': result[1],
                    'max': result[2]
                }
        except Exception as e:
            print(f"Error getting age stats: {e}")
        return None

    def get_segment_duration_stats(self):
        """Get segment duration statistics (avg, min, max) by calculating duration as end_time - start_time"""
        cursor = self.conn.cursor()
        try:
            cursor.execute("PRAGMA table_info(segments)")
            columns = [info[1] for info in cursor.fetchall()]

            if 'start_time' in columns and 'end_time' in columns:
                cursor.execute("""
                    SELECT 
                        AVG(end_time - start_time) as avg_duration,
                        MIN(end_time - start_time) as min_duration, 
                        MAX(end_time - start_time) as max_duration
                    FROM segments
                    WHERE end_time > start_time  -- Исключаем некорректные записи
                """)
                result = cursor.fetchone()
                if result and result[0] is not None:
                    return {
                        'avg': result[0],
                        'min': result[1],
                        'max': result[2]
                    }
                else:
                    logging.warning("No valid segment duration data found")
            else:
                logging.warning("Required columns (start_time, end_time) not found in segments table")

        except Exception as e:
            logging.error(f"Error calculating segment duration stats: {str(e)}")

        return None

    @staticmethod
    def _calculate_file_hash(file_path: str, algorithm: str = "sha256") -> str:
        """Calculate hash of a file."""
        hash_func = hashlib.new(algorithm)
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_func.update(chunk)
        return hash_func.hexdigest()

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()