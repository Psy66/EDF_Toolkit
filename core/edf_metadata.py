# core/edf_metadata.py
import mne
import numpy as np
from tabulate import tabulate
from typing import Dict, Optional, Any
from config.settings import settings
from core.montage_manager import MontageManager

class EDFMetadata:
    """Class for handling EDF file metadata extraction and processing."""

    def __init__(self, file_path: Optional[str] = None):
        self.raw: Optional[mne.io.Raw] = None
        self.events: Optional[np.ndarray] = None
        self.event_id: Optional[Dict[str, int]] = None
        self.file_path: Optional[str] = file_path
        if file_path:
            self.load_metadata(file_path)

    def load_metadata(self, file_path: str) -> None:
        """Loads metadata from an EDF file."""
        self.file_path = file_path
        try:
            self.raw = mne.io.read_raw_edf(file_path, preload=False)
            if 'ECG  ECG' in self.raw.ch_names:
                self.raw.drop_channels(['ECG  ECG'])
            self.events, self.event_id = mne.events_from_annotations(self.raw)
        except Exception as e:
            raise Exception(f"Failed to load metadata: {str(e)}")

    def get_subject_info(self) -> Dict[str, Any]:
        """Returns formatted subject information."""
        subject_info = self.raw.info.get('subject_info', {})
        return {
            'full_name': f"{subject_info.get('first_name', 'Not specified')} "
                         f"{subject_info.get('middle_name', '')} "
                         f"{subject_info.get('last_name', '')}",
            'birthday': subject_info.get('birthday', 'Not specified'),
            'sex': {1: 'Male', 0: 'Female'}.get(subject_info.get('sex'), 'Not specified'),
            'meas_date': subject_info.get('meas_date', 'Not specified'),
            'num_channels': len(self.raw.ch_names),
            'sfreq': self.raw.info['sfreq']
        }

    def get_channel_info(self):
        """Returns detailed channel information with safe key access."""
        channels_info = self.raw.info['chs']
        channel_data = []
        for channel in channels_info:
            loc = channel.get('loc', [])
            loc_x, loc_y, loc_z = ('-', '-', '-') if len(loc) < 3 or np.isnan(loc[:3]).any() else loc[:3]
            channel_data.append({
                'name': channel.get('ch_name', 'Unknown'),
                'log_number': channel.get('logno', '-'),
                'scan_number': channel.get('scanno', '-'),
                'cal': channel.get('cal', 1.0),
                'range': channel.get('range', 1.0),
                'unit_mul': channel.get('unit_mul', 0),
                'unit': channel.get('unit', 'unknown'),
                'coord_frame': channel.get('coord_frame', '-'),
                'coil_type': channel.get('coil_type', '-'),
                'kind': channel.get('kind', '-'),
                'loc_x': loc_x,
                'loc_y': loc_y,
                'loc_z': loc_z
            })
        return channel_data

    def get_event_info(self, event_processor):
        """Returns formatted event information using the provided EventProcessor."""
        if self.events is None:
            return []

        event_data = []
        for event in self.events:
            time_index = event[0]
            event_id_value = event[2]
            evt_name = event_processor.get_event_name(event_id_value, self.event_id)
            if evt_name is None:
                continue
            time_seconds = time_index / self.raw.info['sfreq']
            event_data.append({
                'time': time_seconds,
                'event_id': event_id_value,
                'description': evt_name
            })
        return event_data

    def apply_montage(self):
        """Applies appropriate montage to the data."""
        montage = MontageManager.create_montage(len(self.raw.ch_names))
        if montage:
            self.raw.set_montage(montage)
            return True
        return False

    def format_metadata_output(self, event_processor):
        """Formats all metadata into a human-readable string with safe channel info handling."""
        subject_info = self.get_subject_info()
        output_lines = [
            f"Full Name: {subject_info['full_name']}\n",
            f"Date of Birth: {subject_info['birthday']}\n",
            f"Sex: {subject_info['sex']}\n",
            f"Study Date: {subject_info['meas_date']}\n",
            f"Number of channels: {subject_info['num_channels']}\n",
            f"Sampling frequency: {subject_info['sfreq']} Hz\n"
        ]
        if self.apply_montage():
            output_lines.append("Montage successfully applied.\n")
        else:
            output_lines.append("Montage not applied: unsuitable number of channels.\n")
        try:
            channel_data = self.get_channel_info()
            table_data = []
            for ch in channel_data:
                table_data.append([
                    ch['name'],
                    ch['log_number'],
                    ch['scan_number'],
                    ch.get('cal', '-'),
                    ch.get('range', '-'),
                    ch['unit_mul'],
                    ch['unit'],
                    ch['coord_frame'],
                    ch['coil_type'],
                    ch['kind'],
                    ch['loc_x'],
                    ch['loc_y'],
                    ch['loc_z']
                ])
            headers = [
                "Channel Name", "Logical Number", "Scan Number", "Calibration", "Range",
                "Unit Multiplier", "Unit", "Coordinate Frame", "Coil Type", "Channel Type",
                "Loc X", "Loc Y", "Loc Z"
            ]
            output_lines.append(
                f"\nChannel Information:\n{tabulate(table_data, headers, tablefmt=settings.TABLE_FORMAT)}\n")
        except Exception as e:
            output_lines.append(f"\nWarning: Could not get full channel information: {str(e)}\n")
        event_data = self.get_event_info(event_processor)
        if not event_data:
            output_lines.append("No events available in annotations.\n")
        else:
            table_data = [[
                f"{evt['time']:.2f}", evt['event_id'], evt['description']
            ] for evt in event_data]
            headers = ["Time (sec)", "Event ID", "Description"]
            output_lines.append(f"\nNumber of events: {len(self.events)}\nEvent List:\n")
            output_lines.append(tabulate(table_data, headers, tablefmt=settings.TABLE_FORMAT))
        return ''.join(output_lines)