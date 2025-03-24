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
        """Formats event information into a table, excluding all stimFlash events regardless of ID."""
        if self.events is None:
            return "No events available in annotations.\n"

        main_events = []
        stim_count = 0

        for event in self.events:
            event_id = event[2]
            raw_name = EventProcessor.get_event_name(event_id, self.event_id)

            if 'stimflash' in raw_name.lower():
                stim_count += 1
                continue

            time_sec = event[0] / self.raw.info['sfreq']
            simplified_name = self._simplify_segment_name(raw_name)
            main_events.append({
                'time': time_sec,
                'id': event_id,
                'name': simplified_name
            })

        output = [
            f"\nEvent Markers ({len(main_events)} main events, {stim_count} stimFlash hidden)",
            tabulate(
                [[f"{e['time']:.2f}", e['id'], e['name']] for e in sorted(main_events, key=lambda x: x['time'])],
                headers=["Time (s)", "ID", "Event Type"],
                tablefmt=settings.TABLE_FORMAT
            )
        ]

        if main_events:
            stats = {}
            for e in main_events:
                stats[e['name']] = stats.get(e['name'], 0) + 1

            output.extend([
                "\n\nEvent Statistics:",
                tabulate(
                    sorted(stats.items(), key=lambda x: (-x[1], x[0])),
                    headers=["Event Type", "Count"],
                    tablefmt=settings.TABLE_FORMAT
                )
            ])
        else:
            output.append("\nNo significant events found")

        return "\n".join(output)

    def _simplify_segment_name(self, original_name):
        """Simplifies and translates segment names, removing content in both () and [] brackets."""
        name = original_name.split('(')[0].split('[')[0].strip()
        name_mapping = {
            "Фоновая запись": "Background",
            "Открывание глаз": "Eyes Open",
            "Закрывание глаз": "Eyes Closed",
            "Фотостимуляция": "Photic Stim",
            "После фотостимуляции": "Post-Photic",
            "Без стимуляции": "Rest",
            "Встроенный фотостимулятор оба, 50 мс, 1 Гц": "Photic 1Hz",
            "Встроенный фотостимулятор оба, 50 мс, 2 Гц": "Photic 2Hz",
            "Встроенный фотостимулятор оба, 50 мс, 4 Гц": "Photic 4Hz",
            "Встроенный фотостимулятор оба, 50 мс, 6 Гц": "Photic 6Hz",
            "Встроенный фотостимулятор оба, 50 мс, 8 Гц": "Photic 8Hz",
            "Встроенный фотостимулятор оба, 50 мс, 10 Гц": "Photic 10Hz",
            "Встроенный фотостимулятор оба, 50 мс, 12 Гц": "Photic 12Hz",
            "Встроенный фотостимулятор оба, 50 мс, 14 Гц": "Photic 14Hz",
            "Встроенный фотостимулятор оба, 30 мс, 16 Гц": "Photic 16Hz",
            "Встроенный фотостимулятор оба, 30 мс, 18 Гц": "Photic 18Hz",
            "Встроенный фотостимулятор оба, 30 мс, 20 Гц": "Photic 20Hz",
            "Встроенный фотостимулятор оба, 15 мс, 50 Гц": "Photic 50Hz",
            "Встроенный фотостимулятор оба, 10 мс, 60 Гц": "Photic 60Hz",
            "Встроенный слуховой стимулятор оба, 110 дБ, 10 мс, Тон 1000 Гц, Сжатие, 1 Гц": "Auditory 1KHz",
            "Остановка стимуляции": "Stim End",
            "Гипервентиляция": "Hyperventilation",
            "Гипервентиляция 1 мин.": "Hypervent 1min",
            "Гипервентиляция 2 мин.": "Hypervent 2min",
            "Гипервентиляция 3 мин.": "Hypervent 3min",
            "После гипервентиляции": "Post-Hypervent",
            "Окончание После гипервентиляции": "Post-Hypervent End",
            "Разрыв записи": "Recording Gap"
        }
        return name_mapping.get(name, name.split('(')[0].split('[')[0].strip())

    def process(self):
        """Processes the EDF file, splitting it into segments with proper event grouping."""
        self.output_widget.delete(1.0, tk.END)
        if self.raw is None:
            self.output_widget.insert(tk.END, "Error: Please select an EDF file for processing first.\n")
            raise Exception("Please select an EDF file for processing first.")
        self.output_widget.insert(tk.END, "Starting processing...\n")
        if len(self.events) < 2:
            self.output_widget.insert(tk.END, "Insufficient events to extract segments.\n")
            return
        filtered_events = []
        for event in self.events:
            if event[2] == 1:  # skip stimFlash
                continue
            evt_name = EventProcessor.get_event_name(event[2], self.event_id)
            filtered_events.append((event[0], event[2], evt_name))
        if len(filtered_events) < 2:
            self.output_widget.insert(tk.END, "No valid events after filtering.\n")
            return
        grouped_events = []
        i = 0
        while i < len(filtered_events):
            current_time, current_id, current_name = filtered_events[i]
            if "Фотостимуляция" in current_name and i + 1 < len(filtered_events):
                next_time, next_id, next_name = filtered_events[i + 1]
                if "Встроенный фотостимулятор" in next_name:
                    grouped_events.append((current_time, next_id, next_name))
                    i += 2
                    continue
            grouped_events.append((current_time, current_id, current_name))
            i += 1
        for i in range(len(grouped_events) - 1):
            start_time = grouped_events[i][0] / self.raw.info['sfreq']
            end_time = grouped_events[i + 1][0] / self.raw.info['sfreq']
            if end_time - start_time < settings.MIN_SEGMENT_DURATION:
                continue
            original_name = grouped_events[i][2]
            simplified_name = self._simplify_segment_name(original_name)
            next_event = self._simplify_segment_name(grouped_events[i + 1][2])
            seg_name = EventProcessor.generate_segment_name(simplified_name, self.seg_dict.keys())
            seg_data = self.raw.copy().crop(tmin=start_time, tmax=end_time)
            self.seg_dict[seg_name] = {
                'start_time': start_time,
                'end_time': end_time,
                'current_event': simplified_name,
                'next_event': next_event,
                'data': seg_data
            }
        if len(grouped_events) > 0:
            last_time = grouped_events[-1][0] / self.raw.info['sfreq']
            original_name = grouped_events[-1][2]
            simplified_name = self._simplify_segment_name(original_name)
            seg_name = EventProcessor.generate_segment_name(simplified_name, self.seg_dict.keys())
            seg_data = self.raw.copy().crop(tmin=last_time)
            self.seg_dict[seg_name] = {
                'start_time': last_time,
                'end_time': self.raw.times[-1],
                'current_event': simplified_name,
                'next_event': "End",
                'data': seg_data
            }
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