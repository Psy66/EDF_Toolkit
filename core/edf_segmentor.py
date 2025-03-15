# core/edf_segmentor.py
import mne
from mne.viz import plot_montage
from core.montage_manager import MontageManager
from config.settings import settings
import numpy as np
from tabulate import tabulate
import tkinter as tk

class EventProcessor:
    """Handler for generating event names and processing events."""
    @staticmethod
    def get_event_name(evt_code, ev_id):
        """Returns the event name based on its code."""
        return next((name for name, code in ev_id.items() if code == evt_code), "Unknown")

    @staticmethod
    def generate_segment_name(base_name, existing_names):
        """Generates a unique name for a segment."""
        seg_name = base_name
        counter = 1
        while seg_name in existing_names:
            seg_name = f"{base_name}_{counter}"
            counter += 1
        return seg_name

class EDFSegmentor:
    """Class for processing EDF files, including loading metadata and splitting into segments."""
    def __init__(self, output_widget):
        self.seg_dict = {}
        self.output_widget = output_widget
        self.raw = None
        self.events = None
        self.event_id = None

    def load_metadata(self, file_path):
        """Loads metadata from an EDF file."""
        try:
            self.output_widget.delete(1.0, tk.END)
            self.raw = mne.io.read_raw_edf(file_path, preload=True)
            if 'ECG  ECG' in self.raw.ch_names:
                self.raw.drop_channels(['ECG  ECG'])
                self.output_widget.insert(tk.END, "ECG channel removed.\n")
            self.events, self.event_id = mne.events_from_annotations(self.raw)
            self.output_widget.insert(tk.END, self._format_output())
        except Exception as e:
            self.output_widget.insert(tk.END, f"Error: Failed to load metadata: {str(e)}\n")
            raise Exception(f"Failed to load metadata: {str(e)}")

    def _format_output(self):
        """Formats output information about the file, channels, and events."""
        subject_info = self.raw.info.get('subject_info', {})
        output_lines = [
            f"Full Name: {subject_info.get('first_name', 'Not specified')} "
            f"{subject_info.get('middle_name', '')} "
            f"{subject_info.get('last_name', '')}\n",
            f"Date of Birth: {subject_info.get('birthday', 'Not specified')}\n",
            f"Sex: { {1: 'Male', 0: 'Female'}.get(subject_info.get('sex'), 'Not specified') }\n",
            f"Study Date: {subject_info.get('meas_date', 'Not specified')}\n",
            f"Number of channels: {len(self.raw.ch_names)}\n",
            f"Sampling frequency: {self.raw.info['sfreq']} Hz\n"
        ]
        montage = MontageManager.create_montage(len(self.raw.ch_names))
        if montage:
            self.raw.set_montage(montage)
            output_lines.append("Montage successfully applied.\n")
            # plot_montage(montage, kind='topomap', show_names=True, sphere='auto', scale=1.2)
        else:
            output_lines.append("Montage not applied: unsuitable number of channels.\n")
        output_lines.append(self._format_channel_info())
        output_lines.append(self._format_event_info())
        return ''.join(output_lines)

    def _format_channel_info(self):
        """Formats channel information into a table."""
        channels_info = self.raw.info['chs']
        data = []
        for channel in channels_info:
            loc = channel['loc']
            loc_x, loc_y, loc_z = ('-', '-', '-') if len(loc) < 3 or np.isnan(loc[:3]).any() else loc[:3]
            data.append([
                channel['ch_name'], channel['logno'], channel['scanno'], channel['cal'],
                channel['range'], channel['unit_mul'], channel['unit'], channel['coord_frame'],
                channel['coil_type'], channel['kind'], loc_x, loc_y, loc_z
            ])
        headers = [
            "Channel Name", "Logical Number", "Scan Number", "Calibration", "Range",
            "Unit Multiplier", "Unit", "Coordinate Frame", "Coil Type", "Channel Type",
            "Loc X", "Loc Y", "Loc Z"
        ]
        return f"\nChannel Information:\n{tabulate(data, headers, tablefmt=settings.TABLE_FORMAT)}\n"

    def _format_event_info(self):
        """Formats event information into a table."""
        if self.events is None:
            return "No events available in annotations.\n"
        table_data = []
        for s_idx in range(len(self.events)):
            time_index = self.events[s_idx, 0]
            event_id_value = self.events[s_idx, 2]
            evt_name = EventProcessor.get_event_name(event_id_value, self.event_id)
            time_seconds = time_index / self.raw.info['sfreq']
            table_data.append([f"{time_seconds:.2f}", event_id_value, evt_name])
        headers = ["Time (sec)", "Event ID", "Description"]
        return f"\nNumber of events: {len(self.events)}\nEvent List:\n{tabulate(table_data, headers, tablefmt=settings.TABLE_FORMAT)}\n"

    def add_seg(self, s_idx, e_idx):
        """Adds a segment to the segment dictionary."""
        s_t = self.events[s_idx, 0] / self.raw.info['sfreq']
        e_t = self.events[e_idx, 0] / self.raw.info['sfreq'] if e_idx is not None else self.raw.times[-1]
        if e_t - s_t < settings.MIN_SEGMENT_DURATION:
            return
        evt_code = self.events[s_idx, 2]
        evt_name = EventProcessor.get_event_name(evt_code, self.event_id)
        next_evt = "End" if e_idx is None else EventProcessor.get_event_name(self.events[e_idx, 2], self.event_id)
        seg_name = EventProcessor.generate_segment_name(evt_name, self.seg_dict.keys())
        seg_data = self.raw.copy().crop(tmin=s_t, tmax=e_t)
        self.seg_dict[seg_name] = {
            'start_time': s_t,
            'end_time': e_t,
            'current_event': evt_name,
            'next_event': next_evt,
            'data': seg_data
        }

    def process(self):
        """Processes the EDF file, splitting it into segments."""
        self.output_widget.delete(1.0, tk.END)
        if self.raw is None:
            self.output_widget.insert(tk.END, "Error: Please select an EDF file for processing first.\n")
            raise Exception("Please select an EDF file for processing first.")
        self.output_widget.insert(tk.END, "Starting processing...\n")
        if len(self.events) < 2:
            self.output_widget.insert(tk.END, "Insufficient events to extract segments.\n")
            return
        for i in range(len(self.events) - 1):
            self.add_seg(i, i + 1)
        self.add_seg(len(self.events) - 1, None)
        self._output_results()

    def _output_results(self):
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
        self.output_widget.insert(tk.END, tabulate(structure_data, headers="firstrow", tablefmt=settings.TABLE_FORMAT) + "\n\n")
        table_data = []
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
                    f"{duration:.3f}"
                ])
                valid_segments_count += 1
        headers = ["Segment", "Start", "End", "From", "To", "Duration"]
        self.output_widget.insert(tk.END, f"Number of segments with duration >= {settings.MIN_SEGMENT_DURATION} sec: {valid_segments_count}\n")
        self.output_widget.insert(tk.END, "Segment Data:\n")
        self.output_widget.insert(tk.END, tabulate(table_data, headers, tablefmt=settings.TABLE_FORMAT) + "\n")