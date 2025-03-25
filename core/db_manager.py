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
    sex: str
    age: int
    note: str = ""

@dataclass
class EDFFile:
    edf_id: int
    patient_id: int
    file_hash: str
    start_date: float
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
    note: str = ""

class DBManager:
    def __init__(self, directory: str = ""):
        """Инициализация менеджера БД с хранением всех файлов в подпапке DB."""
        self.directory = os.path.join(directory, "DB") if directory else "DB"
        os.makedirs(self.directory, exist_ok=True)  # Создаем папку если не существует

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
            sex TEXT CHECK(sex IN ('M', 'F', 'N')) DEFAULT 'N',
            age INTEGER,
            note TEXT DEFAULT ''
        )
        """)

        # EDF files table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS edf_files (
            edf_id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER NOT NULL,
            file_hash TEXT UNIQUE NOT NULL,
            start_date REAL NOT NULL,
            eeg_ch INTEGER NOT NULL,
            rate REAL NOT NULL,
            montage TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            FOREIGN KEY (patient_id) REFERENCES patients (patient_id)
        )
        """)

        # Segments table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS segments (
            seg_id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER NOT NULL,
            edf_id INTEGER NOT NULL,
            seg_fpath TEXT UNIQUE NOT NULL,
            start_time REAL NOT NULL,
            end_time REAL NOT NULL,
            l_marker TEXT NOT NULL,
            r_marker TEXT NOT NULL,
            notes TEXT DEFAULT '',
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
        """Получить последнюю запись из указанной таблицы."""
        cursor = self.conn.cursor()
        cursor.execute(f"SELECT * FROM {table_name} ORDER BY ROWID DESC LIMIT 1")
        return cursor.fetchone()

    def database_size(self) -> int:
        """Получить размер базы данных в байтах."""
        return os.path.getsize(self.db_path)

    def get_table_data(self, table_name: str) -> List[Tuple]:
        """Получить все данные из указанной таблицы."""
        cursor = self.conn.cursor()
        cursor.execute(f"SELECT * FROM {table_name}")
        return cursor.fetchall()

    def get_table_columns(self, table_name: str) -> List[str]:
        """Получить названия колонок таблицы."""
        cursor = self.conn.cursor()
        cursor.execute(f"PRAGMA table_info({table_name})")
        return [column[1] for column in cursor.fetchall()]

    def database_exists(self) -> bool:
        """Check if database file exists."""
        return os.path.exists(self.db_path)

    def add_patient(self, name: str, sex: str, age: int, note: str = "") -> int:
        """
        Add a new patient to the database or return existing patient_id if patient already exists.

        Args:
            name: Full name of the patient
            sex: Patient's sex ('M', 'F' or 'N')
            age: Patient's age
            note: Optional notes

        Returns:
            patient_id of the existing or newly created patient
        """
        # Check if patient already exists
        cursor = self.conn.cursor()
        cursor.execute("SELECT patient_id FROM patients WHERE name = ?", (name,))
        result = cursor.fetchone()

        if result:
            return result[0]

        # Add new patient
        cursor.execute(
            "INSERT INTO patients (name, sex, age, note) VALUES (?, ?, ?, ?)",
            (name, sex, age, note)
        )
        self.conn.commit()
        return cursor.lastrowid

    def get_table_data_for_export(self, table_name):
        """Получить данные таблицы в виде списка списков."""
        cursor = self.conn.cursor()
        cursor.execute(f"SELECT * FROM {table_name}")
        return cursor.fetchall()

    def add_edf_file(self, patient_id: int, file_hash: str, start_date: float,
                     eeg_ch: int, rate: float, montage: str = "", notes: str = "") -> int:
        """
        Add a new EDF file to the database.

        Args:
            patient_id: ID of the patient
            file_hash: Hash of the EDF file content
            start_date: Recording start date (timestamp)
            eeg_ch: Number of EEG channels
            rate: Sampling rate
            montage: Montage information
            notes: Optional notes

        Returns:
            edf_id of the newly created record or existing record if file already exists

        Raises:
            ValueError: If EDF file with this hash already exists
        """
        cursor = self.conn.cursor()

        # Check if EDF file already exists
        cursor.execute("SELECT edf_id FROM edf_files WHERE file_hash = ?", (file_hash,))
        result = cursor.fetchone()

        if result:
            raise ValueError(f"EDF file with hash {file_hash} already exists in database (edf_id: {result[0]})")

        # Add new EDF file
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
        """
        Add a new segment to the database.

        Args:
            patient_id: ID of the patient
            edf_id: ID of the EDF file
            seg_fpath: Path to the segment file
            start_time: Start time of the segment (seconds)
            end_time: End time of the segment (seconds)
            l_marker: Left marker name
            r_marker: Right marker name
            notes: Optional notes

        Returns:
            seg_id of the newly created record

        Raises:
            ValueError: If segment with this path already exists
        """
        cursor = self.conn.cursor()

        # Check if segment already exists
        cursor.execute("SELECT seg_id FROM segments WHERE seg_fpath = ?", (seg_fpath,))
        result = cursor.fetchone()

        if result:
            raise ValueError(f"Segment with path {seg_fpath} already exists in database (seg_id: {result[0]})")

        # Add new segment
        cursor.execute(
            "INSERT INTO segments (patient_id, edf_id, seg_fpath, start_time, end_time, l_marker, r_marker, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (patient_id, edf_id, seg_fpath, start_time, end_time, l_marker, r_marker, notes)
        )
        self.conn.commit()
        return cursor.lastrowid

    def add_diagnosis(self, patient_id: int, ds_code: str, ds_descript: str, note: str = ""):
        """
        Add a diagnosis for a patient.

        Args:
            patient_id: ID of the patient
            ds_code: Diagnosis code (ICD-10)
            ds_descript: Diagnosis description
            note: Optional notes

        Raises:
            sqlite3.IntegrityError: If diagnosis for this patient already exists
        """
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
        """
        Fill database with segments from the segment dictionary.

        Args:
            seg_dict: Dictionary with segment data (from EDFSegmentor)
            edf_file_path: Path to the source EDF file

        Returns:
            Tuple of (patient_id, edf_id) for the added records

        Raises:
            ValueError: If EDF file already exists in database
        """
        # Calculate file hash
        file_hash = self._calculate_file_hash(edf_file_path)

        # Check if EDF file already exists
        if self.get_edf_file_by_hash(file_hash):
            raise ValueError("EDF file already exists in database")

        # Extract patient info from the first segment (assuming all segments belong to same patient)
        first_seg = next(iter(seg_dict.values()))
        raw = first_seg['data'].info

        # Get patient info
        subject_info = raw.get('subject_info', {})
        name = " ".join([
            subject_info.get('first_name', ''),
            subject_info.get('middle_name', ''),
            subject_info.get('last_name', '')
        ]).strip()

        sex = subject_info.get('sex', 'N')
        if sex == 1:
            sex = 'M'
        elif sex == 2:
            sex = 'F'
        else:
            sex = 'N'

        # Calculate age
        birthdate = subject_info.get('birthday')
        recording_date = raw.get('meas_date')
        age = None
        if birthdate and recording_date:
            if isinstance(birthdate, str):
                birthdate = datetime.strptime(birthdate, '%Y-%m-%d')
            age = recording_date.year - birthdate.year
            if (recording_date.month, recording_date.day) < (birthdate.month, birthdate.day):
                age -= 1

        # Add patient
        patient_id = self.add_patient(name, sex, age)

        # Add EDF file
        start_date = raw.get('meas_date', datetime.now()).timestamp()
        eeg_ch = len([ch for ch in raw['ch_names'] if 'EEG' in ch])
        rate = raw['sfreq']

        edf_id = self.add_edf_file(
            patient_id=patient_id,
            file_hash=file_hash,
            start_date=start_date,
            eeg_ch=eeg_ch,
            rate=rate
        )

        # Create base directory for segments
        base_dir = os.path.join(
	        self.segments_dir,
	        os.path.splitext(os.path.basename(edf_file_path))[0]
        )
        os.makedirs(base_dir, exist_ok=True)

        # Add segments
        for seg_name, seg_data in seg_dict.items():
            # Clean segment name to make it filesystem-safe
            clean_seg_name = "".join(c if c.isalnum() else "_" for c in seg_name)

            # Create filename with MNE-recommended suffix
            seg_fname = f"seg_{clean_seg_name}_eeg.fif"
            seg_fpath = os.path.join(base_dir, seg_fname)

            # Save segment as FIF file
            seg_data['data'].save(seg_fpath, overwrite=True)

            # Add segment to database
            self.add_segment(
                patient_id=patient_id,
                edf_id=edf_id,
                seg_fpath=seg_fpath,
                start_time=seg_data['start_time'],
                end_time=seg_data['end_time'],
                l_marker=seg_data['current_event'],
                r_marker=seg_data['next_event']
            )

        return patient_id, edf_id

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