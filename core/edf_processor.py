# core/edf_processor.py
import os
import hashlib
import random
import csv
from collections import defaultdict
from datetime import timedelta
from dateutil.parser import parse
from tqdm import tqdm
from mne.io import read_raw_edf
from mne import find_events
from pandas import DataFrame
import logging
from transliterate import translit

from config.settings import settings
from core.edf_visualizer import EDFVisualizer
from concurrent.futures import ThreadPoolExecutor, as_completed

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

class EDFProcessor:
    def __init__(self, directory_path):
        self.directory = directory_path
        self.output_dir = os.path.join(self.directory, "output")
        os.makedirs(self.output_dir, exist_ok=True)
        self.visualizer = EDFVisualizer(self.output_dir)

    def check_directory(self):
        """Check if the directory exists."""
        if not os.path.exists(self.directory):
            raise FileNotFoundError(f"Directory {self.directory} does not exist.")
        return True

    @staticmethod
    def get_edf_metadata(file_path, detailed=False):
        """ Extract metadata from an EDF file. """
        try:
            raw = read_raw_edf(file_path, preload=False)
            info = raw.info
            subject_info = info.get('subject_info', {})
            metadata = {
                'file_name': os.path.basename(file_path),
                'subject_info': subject_info,
                'duration': raw.times[-1],
                'channels': info['ch_names'],
                'sfreq': info['sfreq'],
                'meas_date': info.get('meas_date', None)
            }
            if detailed:
                metadata['events'] = find_events(raw) if 'stim' in info['ch_names'] else None

            return metadata
        except Exception as e:
            logging.error(f"Error reading file {file_path}: {e}")
            return None

    @staticmethod
    def format_filename(filename):
        """Format the filename: remove extra underscores and capitalize first and middle names."""
        filename = filename.strip('_')
        parts = filename.split('_')
        formatted_parts = [part.capitalize() if part.isalpha() else part for part in parts]
        return '_'.join(formatted_parts)

    def rename_edf_files(self):
        """Rename EDF files in the directory."""
        edf_files = [f for f in os.listdir(self.directory) if f.endswith('.edf')]
        renamed_count = 0

        with ThreadPoolExecutor(max_workers=settings.MAX_WORKERS) as executor:
            futures = {executor.submit(self.get_edf_metadata, os.path.join(self.directory, file)): file for file in
                       edf_files}
            for future in tqdm(as_completed(futures), total=len(futures), desc="Renaming files", unit="file"):
                file = futures[future]
                try:
                    metadata = future.result()
                    if metadata:
                        subject_info = metadata['subject_info']
                        first_name = subject_info.get('first_name', '').strip().capitalize()
                        middle_name = subject_info.get('middle_name', '').strip().capitalize()
                        last_name = subject_info.get('last_name', '').strip().capitalize()
                        patient_name = f"{first_name}_{middle_name}_{last_name}".strip()
                        if not patient_name:
                            patient_name = 'Unknown'

                        recording_date = metadata.get('meas_date', 'Unknown_Date')
                        if recording_date:
                            recording_date = recording_date.strftime('%Y-%m-%d_%H-%M-%S')

                        formatted_patient_name = self.format_filename(patient_name)
                        new_name = f"{formatted_patient_name}_{recording_date}.edf"
                        new_file_path = os.path.join(self.directory, new_name)

                        counter = 1
                        while os.path.exists(new_file_path):
                            new_name = f"{formatted_patient_name}_{recording_date}_{counter}.edf"
                            new_file_path = os.path.join(self.directory, new_name)
                            counter += 1

                        os.rename(os.path.join(self.directory, file), new_file_path)
                        renamed_count += 1
                    else:
                        logging.warning(f"Failed to extract metadata for file {file}")
                except Exception as e:
                    logging.error(f"Error renaming file {file}: {e}")

        return renamed_count

    def analyze_directory(self):
        """Analyze all EDF files in the specified directory."""
        metadata_list = []
        files = [os.path.join(self.directory, f) for f in os.listdir(self.directory) if f.endswith('.edf')]

        with ThreadPoolExecutor(max_workers=settings.MAX_WORKERS) as executor:
            futures = {executor.submit(self.get_edf_metadata, file): file for file in files}
            for future in tqdm(as_completed(futures), total=len(futures), desc="Analyzing files", unit="file"):
                file = futures[future]
                try:
                    metadata = future.result()
                    if metadata:
                        metadata_list.append(metadata)
                except Exception as e:
                    logging.error(f"Error analyzing file {file}: {e}")
                    continue  # Продолжаем обработку остальных файлов

        return metadata_list

    @staticmethod
    def is_edf_corrupted(file_path):
        """Check if an EDF file is corrupted."""
        try:
            read_raw_edf(file_path, verbose=False)
            return False
        except Exception as e:
            logging.error(f"Error reading file {file_path}: {e}")
            return True

    def find_and_delete_corrupted_edf(self):
        """Find and delete corrupted EDF files in the specified folder."""
        deleted_files = 0
        edf_files = [os.path.join(root, file) for root, _, files in os.walk(self.directory) for file in files if
                     file.endswith(".edf")]

        with ThreadPoolExecutor(max_workers=settings.MAX_WORKERS) as executor:
            futures = {executor.submit(self.is_edf_corrupted, file): file for file in edf_files}
            for future in tqdm(as_completed(futures), total=len(futures), desc="Checking files", unit="file"):
                file = futures[future]
                try:
                    if future.result():
                        logging.warning(f"Corrupted file: {file}")
                        os.remove(file)
                        logging.info(f"File deleted: {file}")
                        deleted_files += 1
                except Exception as e:
                    logging.error(f"Error deleting file {file}: {e}")

        return deleted_files

    @staticmethod
    def get_edf_start_time(file_path):
        """Extract the recording start time from an EDF file."""
        try:
            raw = read_raw_edf(file_path, verbose=False)
            start_datetime = raw.info['meas_date']
            if start_datetime:
                return start_datetime
            return None
        except Exception as e:
            logging.error(f"Error reading file {file_path}: {e}")
            return None

    def find_edf_with_similar_start_time(self, time_delta=timedelta(minutes=10)):
        """Find EDF files with similar start times."""
        time_dict = defaultdict(list)
        edf_files = [os.path.join(root, file) for root, _, files in os.walk(self.directory) for file in files if
                     file.lower().endswith('.edf')]

        with ThreadPoolExecutor(max_workers=settings.MAX_WORKERS) as executor:
            futures = {executor.submit(self.get_edf_start_time, file): file for file in edf_files}
            for future in tqdm(as_completed(futures), total=len(futures), desc="Processing files", unit="file"):
                file = futures[future]
                try:
                    start_datetime = future.result()
                    if start_datetime:
                        rounded_time = start_datetime - timedelta(minutes=start_datetime.minute % 10)
                        time_dict[rounded_time].append((start_datetime, file))
                except Exception as e:
                    logging.error(f"Error processing file {file}: {e}")

        similar_time_groups = []
        for rounded_time, files in time_dict.items():
            if len(files) > 1:
                files.sort()
                for i in range(1, len(files)):
                    if files[i][0] - files[i - 1][0] <= time_delta:
                        similar_time_groups.append(files)
                        break

        return similar_time_groups

    @staticmethod
    def calculate_file_hash(file_path, hash_algorithm="md5", chunk_size=8192):
        """Calculate the file hash for content verification."""
        hash_func = hashlib.new(hash_algorithm)
        with open(file_path, "rb") as f:
            while chunk := f.read(chunk_size):
                hash_func.update(chunk)
        return hash_func.hexdigest()

    def find_duplicate_files(self):
        """Find duplicate files in the specified directory."""
        file_paths = []
        for root, _, files in os.walk(self.directory):
            for file in files:
                file_path = os.path.join(root, file)
                file_paths.append(file_path)
        size_dict = defaultdict(list)
        for path in tqdm(file_paths, desc="Collecting file sizes", unit="file"):
            try:
                size = os.path.getsize(path)
                size_dict[size].append(path)
            except OSError as e:
                logging.warning(f"Could not get size for {path}: {e}")
        hash_dict = defaultdict(list)
        with tqdm(total=sum(len(paths) for paths in size_dict.values() if len(paths) > 1),
                  desc="Checking duplicates", unit="file") as pbar:
            for size, paths in size_dict.items():
                if len(paths) > 1:  # Только файлы с одинаковым размером
                    for path in paths:
                        try:
                            file_hash = self.calculate_file_hash(path)
                            hash_dict[file_hash].append(path)
                            pbar.update(1)
                        except OSError as e:
                            logging.warning(f"Could not hash {path}: {e}")
                            pbar.update(1)
        duplicates = {hash_val: paths for hash_val, paths in hash_dict.items() if len(paths) > 1}
        total_duplicates = sum(len(paths) - 1 for paths in duplicates.values())
        logging.info(f"Found {len(duplicates)} duplicate groups ({total_duplicates} redundant files)")
        return duplicates

    @staticmethod
    def delete_duplicates(duplicates):
        """Delete all duplicates except one, with confirmation and backup option."""
        total_saved = 0
        total_failed = 0

        for hash_val, paths in tqdm(duplicates.items(), desc="Deleting duplicates", unit="group"):
            # Оставляем первый файл, удаляем остальные
            for path in paths[1:]:
                try:
                    # Можно добавить резервное копирование перед удалением
                    os.remove(path)
                    total_saved += 1
                    logging.info(f"Deleted duplicate: {path}")
                except OSError as e:
                    total_failed += 1
                    logging.error(f"Failed to delete {path}: {e}")

        return {
            'total_saved': total_saved,
            'total_failed': total_failed,
            'space_saved': total_saved * os.path.getsize(next(iter(duplicates.values()))[0])
            if total_saved > 0 else 0
        }

    @staticmethod
    def calculate_age(birthdate, recording_date):
        """Calculate the age at the time of recording."""
        try:
            if isinstance(birthdate, str):
                birthdate = parse(birthdate)
            if isinstance(recording_date, str):
                recording_date = parse(recording_date)
            if hasattr(recording_date, 'tzinfo') and recording_date.tzinfo is not None:
                recording_date = recording_date.replace(tzinfo=None)
            age = recording_date.year - birthdate.year
            if (recording_date.month, recording_date.day) < (birthdate.month, birthdate.day):
                age -= 1
            return age
        except Exception as e:
            logging.error(f"Error calculating age: {e}")
            return None

    def generate_statistics(self, metadata_list):
        """Generate descriptive statistics from metadata and save results."""
        stats = defaultdict(list)
        for metadata in metadata_list:
            subject_info = metadata.get('subject_info', {})
            stats['file_name'].append(metadata['file_name'])
            stats['sex'].append(
                'Male' if subject_info.get('sex') == 1 else 'Female' if subject_info.get('sex') == 2 else 'Unknown')

            birthdate = subject_info.get('birthday')
            recording_date = metadata.get('meas_date')
            if birthdate and recording_date:
                age = self.calculate_age(birthdate, recording_date)
                if age is not None:
                    stats['age'].append(min(age, 60))  # Limit age to 60 years

            stats['duration_minutes'].append(metadata['duration'] / 60)

        df = DataFrame(stats)
        descriptive_stats = {
            'sex_distribution': df['sex'].value_counts(),
            'age_distribution': df['age'].describe() if 'age' in df.columns else None,
            'duration_stats': df['duration_minutes'].describe()
        }
        if self.visualizer is None:
            raise ValueError("Visualizer is not initialized.")
        self.visualizer.visualize_statistics(df)
        output_csv_path = os.path.join(self.output_dir, 'edf_metadata_stats.csv')
        df.to_csv(output_csv_path, index=False)
        with open(os.path.join(self.output_dir, 'descriptive_stats.txt'), 'w') as f:
            f.write("Descriptive Statistics:\n")
            f.write(f"Sex Distribution:\n{descriptive_stats['sex_distribution']}\n")
            f.write(f"Age Distribution:\n{descriptive_stats['age_distribution']}\n")
            f.write(f"Duration Statistics:\n{descriptive_stats['duration_stats']}\n")

        return df, descriptive_stats

    def generate_patient_table(self):
        """Generate a CSV table with unique patient names, sex, and age at recording."""
        files = [f for f in os.listdir(self.directory) if f.endswith(".edf")]
        patient_data = set()

        def process_single_file(file_path):
            """Process a single file to extract patient data."""
            try:
                patient_name = self._extract_patient_name(file_path)
                translated_name = translit(patient_name, 'ru', reversed=True)

                metadata = self.get_edf_metadata(os.path.join(self.directory, file_path))
                if not metadata:
                    return None

                subject_info = metadata.get('subject_info', {})
                gender = 'M' if subject_info.get('sex') == 1 else 'F' if subject_info.get('sex') == 2 else 'Unknown'

                birth_date = subject_info.get('birthday')
                record_date = metadata.get('meas_date')
                patient_age = None
                if birth_date and record_date:
                    patient_age = self.calculate_age(birth_date, record_date)

                return translated_name, gender, patient_age
            except Exception as err:
                logging.error(f"Error processing file {file_path}: {err}")
                return None

        with ThreadPoolExecutor(max_workers=settings.MAX_WORKERS) as executor:
            futures = {executor.submit(process_single_file, file): file for file in files}
            for future in tqdm(as_completed(futures), total=len(futures), desc="Processing files", unit="file"):
                try:
                    result = future.result()
                    if result:
                        patient_data.add(result)
                except Exception as err:
                    logging.error(f"Error processing file: {err}")

        sorted_data = sorted(patient_data, key=lambda x: x[0])

        os.makedirs(self.output_dir, exist_ok=True)
        output_path = os.path.join(self.output_dir, "patient_table.csv")
        with open(output_path, mode='w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(["Patient Name", "Sex", "Age at Recording (years)"])
            for name, sex, age in sorted_data:
                writer.writerow([name, sex, age if age is not None else "Unknown"])

        return f"Patient table saved to {output_path}"
    @staticmethod
    def _extract_patient_name(filename):
        """Extract patient name from the filename."""
        parts = filename.replace(".edf", "").split("_")
        if len(parts) >= 3:
            return " ".join(parts[:3])
        raise ValueError(f"Invalid file name: {filename}")

    def randomize_filenames(self):
        """Randomize file names in the directory."""
        files = [f for f in os.listdir(self.directory) if os.path.isfile(os.path.join(self.directory, f))]
        used_codes = set()
        name_mapping = []

        for old_name in files:
            new_name = self._generate_unique_code(used_codes) + os.path.splitext(old_name)[1]
            os.rename(os.path.join(self.directory, old_name), os.path.join(self.directory, new_name))
            name_mapping.append((old_name, new_name))

        output_csv_path = os.path.join(self.directory, "name_mapping.csv")
        with open(output_csv_path, mode='w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['Old Name', 'New Name'])
            writer.writerows(name_mapping)

        return f"File names randomized. Correspondence table saved to {output_csv_path}"

    @staticmethod
    def _generate_unique_code(used_codes):
        """Generate a unique 6-digit numeric code."""
        while True:
            code = ''.join(random.choices('0123456789', k=6))
            if code not in used_codes:
                used_codes.add(code)
                return code

    def remove_patient_info(self):
        """Remove patient information from EDF files."""
        files = [f for f in os.listdir(self.directory) if f.endswith(".edf")]
        for file in tqdm(files, desc="Processing files", unit="file"):
            try:
                self._remove_patient_info(file)
                logging.info(f"Patient information removed from file {file}")
            except Exception as e:
                logging.error(f"Error removing patient information from file {file}: {e}")

    def _remove_patient_info(self, file):
        """Remove patient information from an EDF file, preserving UUID, sex, and birthdate."""
        file_path = os.path.join(self.directory, file)
        try:
            with open(file_path, 'r+b') as f:
                header = f.read(88).decode('ascii')
                parts = header.split()
                if len(parts) >= 5:
                    uuid, sex, birthdate = parts[1], parts[2], parts[3]
                    new_patient_info = f"{uuid} {sex} {birthdate} {'_' * 80}"
                    new_patient_info = new_patient_info[:80]
                    f.seek(8)
                    f.write(new_patient_info.encode('ascii'))
                else:
                    logging.warning(f"Invalid EDF header in file {file}. Cannot remove patient info.")
        except Exception as e:
            logging.error(f"Error processing file {file}: {e}")

    def read_edf_info(self):
        """Read and display information from the first EDF file."""
        files = [f for f in os.listdir(self.directory) if f.endswith(".edf")]
        if not files:
            return "No EDF files found in the directory."

        first_file = files[0]
        try:
            metadata = self.get_edf_metadata(os.path.join(self.directory, first_file), detailed=True)
            if metadata:
                formatted_info = self._format_edf_info(metadata)
                formatted_info += "\nФайл читается и доступен для дальнейшей обработки."
                return formatted_info
            else:
                return "Failed to extract metadata from the file."
        except Exception as e:
            logging.error(f"Error reading information from file {first_file}: {e}")
            return f"Ошибка при чтении файла {first_file}: {e}"

    @staticmethod
    def _format_edf_info(metadata):
        """Format EDF file information for human-readable output."""
        subject_info = metadata.get('subject_info', {})
        formatted_info = (
            f"Информация о файле: {metadata['file_name']}\n"
            f"Имя пациента: {subject_info.get('first_name', 'Не указано')} "
            f"{subject_info.get('middle_name', '')} "
            f"{subject_info.get('last_name', '')}\n"
            f"Пол: {'Мужской' if subject_info.get('sex') == 1 else 'Женский' if subject_info.get('sex') == 2 else 'Не указан'}\n"
            f"Дата рождения: {subject_info.get('birthday', 'Не указана')}\n"
            f"Дата записи: {metadata.get('meas_date', 'Не указана')}\n"
            f"Длительность записи: {metadata['duration'] / 60:.2f} минут\n"
            f"Частота дискретизации: {metadata['sfreq']} Гц\n"
            f"Каналы: {', '.join(metadata['channels'])}\n"
        )
        return formatted_info

    def run(self):
        """Run the EDF processing pipeline."""
        self.check_directory()
        metadata_list = self.analyze_directory()
        df, descriptive_stats = self.generate_statistics(metadata_list)
        self.visualizer.visualize_statistics(df)
        # Удаляем лишний вызов export_statistics, так как данные уже сохранены в generate_statistics
        logging.info("EDF processing completed.")

if __name__ == "__main__":
    directory = input("Enter the path to the directory containing EDF files: ").strip()
    processor = EDFProcessor(directory)
    processor.run()