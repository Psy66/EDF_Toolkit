# core/edf_visualizer.py
import os
from seaborn import countplot, histplot
import matplotlib.pyplot as plt

class EDFVisualizer:
    def __init__(self, output_dir):
        """ Initialize the visualizer with the output directory. """
        self.output_dir = os.path.normpath(output_dir)
        os.makedirs(self.output_dir, exist_ok=True)

    def visualize_statistics(self, df):
        """ Visualize statistics and save plots to the output directory. """
        self._visualize_sex_distribution(df)
        self._visualize_age_distribution(df)
        self._visualize_duration_distribution(df)

    def _visualize_sex_distribution(self, df):
        """ Visualize and save the sex distribution plot. """
        if 'sex' in df.columns:
            fig = plt.figure(figsize=(8, 6))
            countplot(data=df, x='sex')
            plt.title('Sex Distribution')
            save_path = os.path.normpath(os.path.join(self.output_dir, 'sex_distribution.png'))
            plt.savefig(save_path)
            plt.close(fig)
            print(f"Сохранено: {save_path}")

    def _visualize_age_distribution(self, df):
        """ Visualize and save the age distribution plot. """
        if 'age' in df.columns:
            age_data = df[df['age'].apply(lambda x: isinstance(x, (int, float)))]
            if not age_data.empty:
                fig = plt.figure(figsize=(8, 6))
                histplot(data=age_data, x='age', bins=20, kde=True)
                plt.title('Age Distribution')
                save_path = os.path.normpath(os.path.join(self.output_dir, 'age_distribution.png'))
                plt.savefig(save_path)
                plt.close(fig)
                print(f"Сохранено: {save_path}")

    def _visualize_duration_distribution(self, df):
        """ Visualize and save the recording duration distribution plot. """
        if 'duration_minutes' in df.columns:
            fig = plt.figure(figsize=(8, 6))
            histplot(data=df, x='duration_minutes', bins=20, kde=True)
            plt.title('Recording Duration (minutes)')
            save_path = os.path.normpath(os.path.join(self.output_dir, 'duration_distribution.png'))
            plt.savefig(save_path)
            plt.close(fig)
            print(f"Сохранено: {save_path}")