# core/db_manager.py
import os
import logging
from sqlalchemy import create_engine, Column, Integer, String, Float, Date, DateTime, Text, Enum, inspect, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.schema import UniqueConstraint, ForeignKey

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

Base = declarative_base()

class Patient(Base):
	__tablename__ = 'patients'
	id = Column(Integer, primary_key=True)
	name = Column(String, nullable=False)
	birthday = Column(Date)
	sex = Column(Enum('M', 'F', 'N', name='sex_types'))
	age = Column(Integer)
	notes = Column(Text)

	__table_args__ = (UniqueConstraint('name', 'birthday', name='_patient_name_birthday_uc'),)

class EDFFile(Base):
	__tablename__ = 'edf_files'
	id = Column(Integer, primary_key=True)
	patient_id = Column(Integer, ForeignKey('patients.id'), nullable=False)
	file_hash = Column(String(64), unique=True)
	start_date = Column(DateTime, nullable=False)
	eeg_channels = Column(Integer)
	sampling_rate = Column(Float)
	montage = Column(String)
	notes = Column(Text)

	patient = relationship("Patient", backref="edf_files")
	__table_args__ = (UniqueConstraint('patient_id', 'start_date', name='_edf_patient_startdate_uc'),)

class Segment(Base):
	__tablename__ = 'segments'
	id = Column(Integer, primary_key=True)
	edf_id = Column(Integer, ForeignKey('edf_files.id'), nullable=False)
	start_time = Column(Float, nullable=False)
	end_time = Column(Float, nullable=False)
	l_marker = Column(String)
	r_marker = Column(String)
	file_path = Column(String)
	notes = Column(Text)

	edf_file = relationship("EDFFile", backref="segments")
	__table_args__ = (UniqueConstraint('edf_id', 'start_time', 'end_time', name='_segment_unique_uc'),)

class Diagnosis(Base):
	__tablename__ = 'diagnosis'
	id = Column(Integer, primary_key=True)
	patient_id = Column(Integer, ForeignKey('patients.id'), nullable=False)
	ds_code = Column(String(10))
	ds_description = Column(Text)
	notes = Column(Text)

	patient = relationship("Patient", backref="diagnoses")

class DBManager:
	def __init__(self, working_dir):
		self.working_dir = working_dir
		self.db_path = os.path.join(working_dir, "DB")
		self.engine = None
		self.Session = None

	def initialize_db(self):
		"""Initialize the database structure."""
		try:
			os.makedirs(self.db_path, exist_ok=True)
			db_file = os.path.join(self.db_path, "eeg_database.db")
			self.engine = create_engine(f'sqlite:///{db_file}')
			Base.metadata.create_all(self.engine)
			self.Session = sessionmaker(bind=self.engine)
			logger.info(f"Database initialized at: {db_file}")
			return True
		except Exception as e:
			logger.error(f"Error initializing database: {str(e)}")
			return False

	def add_patient(self, name, birthday, sex='N', age=None, notes=None):
		"""Add a new patient to the database."""
		session = self.Session()
		try:
			patient = Patient(
				name=name,
				birthday=birthday,
				sex=sex,
				age=age,
				notes=notes
			)
			session.add(patient)
			session.commit()
			logger.info(f"Added patient: {name} (ID: {patient.id})")
			return patient
		except Exception as e:
			session.rollback()
			logger.error(f"Error adding patient: {str(e)}")
			return None
		finally:
			session.close()

	def add_edf_file(self, patient_id, file_hash, start_date, eeg_channels,
	                 sampling_rate, montage=None, notes=None):
		"""Add a new EDF file record to the database."""
		session = self.Session()
		try:
			edf_file = EDFFile(
				patient_id=patient_id,
				file_hash=file_hash,
				start_date=start_date,
				eeg_channels=eeg_channels,
				sampling_rate=sampling_rate,
				montage=montage,
				notes=notes
			)
			session.add(edf_file)
			session.commit()
			logger.info(f"Added EDF file (ID: {edf_file.id}) for patient ID {patient_id}")
			return edf_file
		except Exception as e:
			session.rollback()
			logger.error(f"Error adding EDF file: {str(e)}")
			return None
		finally:
			session.close()

	def add_segments(self, edf_id, segments_data):
		"""Add multiple segments to the database."""
		session = self.Session()
		try:
			# Create segments directory
			segments_dir = os.path.join(self.db_path, "segments", f"edf_{edf_id}")
			os.makedirs(segments_dir, exist_ok=True)

			added_segments = []
			for seg_name, seg_data in segments_data.items():
				# Generate filename according to MNE conventions
				seg_filename = f"seg_{seg_name.lower()}_{seg_data['start_time']:.1f}-{seg_data['end_time']:.1f}_eeg.fif"
				seg_filepath = os.path.join(segments_dir, seg_filename)

				# Save in FIF format with proper suffix
				seg_data['data'].save(seg_filepath, overwrite=True, fmt='single')

				# Create database record
				segment = Segment(
					edf_id=edf_id,
					start_time=seg_data['start_time'],
					end_time=seg_data['end_time'],
					l_marker=seg_data['current_event'],
					r_marker=seg_data['next_event'],
					file_path=seg_filepath,
					notes=f"Segment {seg_name} from {seg_data['start_time']:.1f} to {seg_data['end_time']:.1f}"
				)
				session.add(segment)
				added_segments.append(segment)

			session.commit()
			logger.info(f"Added {len(added_segments)} segments for EDF ID {edf_id}")
			return added_segments
		except Exception as e:
			session.rollback()
			logger.error(f"Error adding segments: {str(e)}")
			return None
		finally:
			session.close()

	def get_tables(self):
		"""Get list of available tables in the database."""
		if not self.engine:
			return []
		inspector = inspect(self.engine)
		return inspector.get_table_names()

	def get_table_data(self, table_name):
		"""Get all data from specified table."""
		session = self.Session()
		try:
			# Явно указываем, что это текстовый SQL-запрос
			result = session.execute(text(f"SELECT * FROM {table_name}"))
			columns = result.keys()
			data = result.fetchall()
			return columns, data
		except Exception as e:
			logger.error(f"Error getting data from table {table_name}: {str(e)}")
			return [], []
		finally:
			session.close()

	def execute_query(self, query):
		"""Execute raw SQL query."""
		session = self.Session()
		try:
			# Явно указываем, что это текстовый SQL-запрос
			result = session.execute(text(query))
			if query.lower().strip().startswith("select"):
				return True, result.keys(), result.fetchall()
			else:
				session.commit()
				return True, None, result.rowcount
		except Exception as e:
			session.rollback()
			return False, str(e), None
		finally:
			session.close()

	def find_patient(self, name, birthday):
		"""Find patient by name and birthday."""
		session = self.Session()
		try:
			patient = session.query(Patient).filter_by(name=name, birthday=birthday).first()
			return patient
		except Exception as e:
			logger.error(f"Error finding patient: {str(e)}")
			return None
		finally:
			session.close()

	def find_edf_by_hash(self, file_hash):
		"""Find EDF file by its hash."""
		session = self.Session()
		try:
			edf_file = session.query(EDFFile).filter_by(file_hash=file_hash).first()
			return edf_file
		except Exception as e:
			logger.error(f"Error finding EDF file: {str(e)}")
			return None
		finally:
			session.close()