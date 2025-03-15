# core/montage_manager.py
import mne
import numpy as np

class MontageManager:
    """Class for creating montages (electrode arrangements) for EEG."""
    @staticmethod
    def create_montage(num_channels):
        """Creates a montage based on the number of channels."""
        if num_channels in [10, 11]:
            ch_n = ['EEG F3', 'EEG F4', 'EEG C3', 'EEG C4', 'EEG P3', 'EEG P4', 'EEG O1', 'EEG O2', 'EEG A2', 'EEG A1']
            ch_c = np.array([
                [-0.05, 0.0375, 0.06], [0.05, 0.0375, 0.06],
                [-0.05, 0.0, 0.1], [0.05, 0.0, 0.1],
                [-0.05, -0.0375, 0.08], [0.05, -0.0375, 0.08],
                [-0.05, -0.075, 0.05], [0.05, -0.075, 0.05],
                [0.1, 0.0, -0.002], [-0.1, 0.0, -0.002]
            ])
        elif num_channels in [19, 20]:
            ch_n = [
                'EEG FP1-A1', 'EEG FP2-A2', 'EEG F3-A1', 'EEG F4-A2',
                'EEG C3-A1', 'EEG C4-A2', 'EEG P3-A1', 'EEG P4-A2',
                'EEG O1-A1', 'EEG O2-A2', 'EEG F7-A1', 'EEG F8-A2',
                'EEG T3-A1', 'EEG T4-A2', 'EEG T5-A1', 'EEG T6-A2',
                'EEG FZ-A2', 'EEG CZ-A1', 'EEG PZ-A2'
            ]
            ch_c = np.array([
                [-0.05, 0.075, 0.05], [0.05, 0.075, 0.05],
                [-0.05, 0.0375, 0.06], [0.05, 0.0375, 0.06],
                [-0.05, 0.0, 0.1], [0.05, 0.0, 0.1],
                [-0.05, -0.0375, 0.08], [0.05, -0.0375, 0.08],
                [-0.05, -0.075, 0.05], [0.05, -0.075, 0.05],
                [-0.075, 0.0375, 0.06], [0.075, 0.0375, 0.06],
                [-0.075, 0.0, 0.1], [0.075, 0.0, 0.1],
                [-0.075, -0.0375, 0.08], [0.075, -0.0375, 0.08],
                [0.0, 0.0375, 0.06], [0.0, 0.0, 0.1], [0.0, -0.0375, 0.08]
            ])
        else:
            return None
        dig_pts = [
            dict(ident=i + 1, ch_name=name, r=coord,
                 kind=mne.io.constants.FIFF.FIFFV_POINT_EEG,
                 coord_frame=mne.io.constants.FIFF.FIFFV_COORD_HEAD)
            for i, (name, coord) in enumerate(zip(ch_n, ch_c))
        ]
        return mne.channels.DigMontage(dig=dig_pts, ch_names=ch_n)