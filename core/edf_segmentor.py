# core/edf_segmentor.py
import time
import tkinter as tk
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from tabulate import tabulate
import mne
from config.settings import settings
from core.edf_metadata import EDFMetadata
from core.event_processor import EventProcessor

class EDFSegmentor:
	"""Class for processing EDF files, including loading metadata and splitting into segments."""

	START_SEGMENT_NAME = "Start"
	END_SEGMENT_NAME = "End"
	UNKNOWN_SEGMENT_NAME = "Unknown"

	def __init__(self, output_widget: tk.Text):
		self.seg_dict: Dict[str, Dict[str, Any]] = {}
		self.output_widget: tk.Text = output_widget
		self.metadata: Optional[EDFMetadata] = None
		self.current_file_path: Optional[str] = None
		self.lock: Lock = Lock()
		self.processing_start_time: float = 0

	def load_metadata(self, file_path: str) -> None:
		"""Loads metadata from an EDF file with improved error handling."""
		self.current_file_path = file_path
		try:
			self.output_widget.delete(1.0, tk.END)
			self.metadata = EDFMetadata(file_path)

			if not isinstance(self.metadata.raw, mne.io.BaseRaw):
				raise TypeError("Invalid raw data format")

			try:
				self.output_widget.insert(tk.END, self.metadata.format_metadata_output(EventProcessor))
			except Exception as format_error:
				self.output_widget.insert(tk.END, f"Warning: Metadata formatting issue: {str(format_error)}\n")
			# Still proceed even if formatting had issues

		except Exception as e:
			error_msg = f"Error: Failed to load metadata: {str(e)}\n"
			self.output_widget.insert(tk.END, error_msg)
			raise Exception(error_msg) from e

	def process(self) -> None:
		"""Processes the EDF file, ignoring excluded markers and merging adjacent segments."""
		self.processing_start_time = time.time()
		self.output_widget.delete(1.0, tk.END)

		if self.metadata is None or not isinstance(self.metadata.raw, mne.io.BaseRaw):
			self.output_widget.insert(tk.END, "Error: Please select an EDF file for processing first.\n")
			raise Exception("Please select an EDF file for processing first.")

		self.output_widget.insert(tk.END, "Starting processing with excluded markers...\n")

		# Фильтрация событий: оставляем только те, которые НЕ в EXCLUDED_NAMES
		valid_events = []
		for event in self.metadata.events:
			evt_code = event[2]
			evt_name = EventProcessor.get_event_name(evt_code, self.metadata.event_id)
			if evt_name is not None:  # None означает, что маркер в EXCLUDED_NAMES
				valid_events.append(event)

		if not valid_events:
			self.output_widget.insert(tk.END, "No valid events found after filtering.\n")
			return

		# Обработка сегментов между валидными маркерами
		self.seg_dict.clear()
		existing_names: Set[str] = set()

		# Первый сегмент (от начала до первого валидного маркера)
		first_event_time = float(valid_events[0][0]) / self.metadata.raw.info['sfreq']
		if first_event_time > settings.MIN_SEGMENT_DURATION:
			seg_name = EventProcessor.generate_segment_name(
				self.START_SEGMENT_NAME, existing_names
			)
			seg_data = self.metadata.raw.copy().crop(tmin=0, tmax=first_event_time)
			self.seg_dict[seg_name] = {
				'start_time': 0,
				'end_time': first_event_time,
				'current_event': self.START_SEGMENT_NAME,
				'next_event': EventProcessor.get_event_name(
					valid_events[0][2], self.metadata.event_id
				),
				'data': seg_data
			}
			existing_names.add(seg_name)

		# Основные сегменты (между валидными маркерами)
		for i in range(len(valid_events)):
			start_idx = valid_events[i]
			end_idx = valid_events[i + 1] if i + 1 < len(valid_events) else None

			start_time = float(start_idx[0]) / self.metadata.raw.info['sfreq']
			end_time = (
				float(end_idx[0]) / self.metadata.raw.info['sfreq']
				if end_idx is not None
				else self.metadata.raw.times[-1]
			)

			if end_time - start_time < settings.MIN_SEGMENT_DURATION:
				continue

			evt_name = EventProcessor.get_event_name(
				start_idx[2], self.metadata.event_id
			)
			next_evt = (
				self.END_SEGMENT_NAME
				if end_idx is None
				else EventProcessor.get_event_name(end_idx[2], self.metadata.event_id)
			)

			seg_name = EventProcessor.generate_segment_name(evt_name, existing_names)
			seg_data = self.metadata.raw.copy().crop(tmin=start_time, tmax=end_time)

			self.seg_dict[seg_name] = {
				'start_time': start_time,
				'end_time': end_time,
				'current_event': evt_name,
				'next_event': next_evt,
				'data': seg_data
			}
			existing_names.add(seg_name)

		self._output_results()
		processing_time = time.time() - self.processing_start_time
		self.output_widget.insert(tk.END, f"\nProcessing completed in {processing_time:.2f} seconds\n")

	def _process_segment(self, s_idx: int, e_idx: Optional[int]) -> Optional[Tuple[str, Dict[str, Any]]]:
		"""Processes a segment and returns the segment name and data."""
		s_t: float = float(self.metadata.events[s_idx, 0]) / float(self.metadata.raw.info['sfreq'])
		e_t: float = (float(self.metadata.events[e_idx, 0]) / float(self.metadata.raw.info['sfreq'])
					  if e_idx is not None else float(self.metadata.raw.times[-1]))

		if e_t - s_t < settings.MIN_SEGMENT_DURATION:
			return None

		evt_code: int = int(self.metadata.events[s_idx, 2])
		evt_name = EventProcessor.get_event_name(evt_code, self.metadata.event_id)
		next_evt = self.END_SEGMENT_NAME if e_idx is None else EventProcessor.get_event_name(
			int(self.metadata.events[e_idx, 2]),
			self.metadata.event_id
		)

		with self.lock:
			existing_names: Set[str] = set(self.seg_dict.keys())
			seg_name = EventProcessor.generate_segment_name(evt_name, existing_names)

		seg_data = self.metadata.raw.copy().crop(tmin=s_t, tmax=e_t)
		return (seg_name, {
			'start_time': s_t,
			'end_time': e_t,
			'current_event': evt_name,
			'next_event': next_evt,
			'data': seg_data
		})

	def _output_results(self) -> None:
		"""Outputs the processing results to the text widget."""
		structure_data = [
			["Key", "Key", "Type", "Example Value"],
			["*seg_name*", "", "", ""],
			["", "", "", ""],
			["", "start_time", "float", "0.60"],
			["", "end_time", "float", "15.00"],
			["", "current_event", "str", "Fon"],
			["", "next_event", "str", "OG"],
			["", "data", "RawEDF", "RawEDF Object"]
		]
		self.output_widget.insert(tk.END, "Segment Dictionary Structure:\n")
		self.output_widget.insert(tk.END,
								  tabulate(structure_data, headers="firstrow", tablefmt=settings.TABLE_FORMAT) + "\n\n")

		table_data: List[List[Union[str, float]]] = []
		valid_segments_count = 0
		for seg_name, t in self.seg_dict.items():
			duration = t['end_time'] - t['start_time']
			if duration >= settings.MIN_SEGMENT_DURATION:
				table_data.append([
					seg_name,
					f"{t['start_time']:.3f}",
					f"{t['end_time']:.3f}",
					t['current_event'],
					t['next_event'],
					float(f"{duration:.3f}")
				])
				valid_segments_count += 1

		headers: List[str] = ["Segment", "Start", "End", "From", "To", "Duration"]
		self.output_widget.insert(tk.END,
								  f"Number of segments with duration >= {settings.MIN_SEGMENT_DURATION} sec: {valid_segments_count}\n")
		self.output_widget.insert(tk.END, "Segment Data:\n")
		self.output_widget.insert(tk.END, tabulate(table_data, headers, tablefmt=settings.TABLE_FORMAT) + "\n")