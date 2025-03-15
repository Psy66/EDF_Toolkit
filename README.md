
## 🧠 EDF Batch & Segment Toolkit

![EDF Batch & Segment Toolkit](https://img.shields.io/badge/Version-1.0.0-blue)
![License](https://img.shields.io/badge/License-MIT-green)
![Python](https://img.shields.io/badge/Python-3.8%2B-yellow)

*EDF Batch & Segment Toolkit is a powerful application designed for batch processing and segmentation of European Data Format (EDF) files. It provides a comprehensive set of tools for managing, analyzing, and splitting EDF files, making it ideal for researchers and professionals working with EEG data.*

---

## ✨ Features

### Batch Processing of EDF Files
- 📂 **Open Folder with EDF Files**: Select a directory to work with files.
- 🖋️ **Rename EDF Files**: Automatically rename files based on metadata.
- 🚫 **Remove Corrupted Files**: Find and delete corrupted EDF files.
- 🔍 **Remove Duplicates**: Find and delete duplicate EDF files.
- ⏱️ **Find Files with Similar Start Time**: Locate EDF files with similar recording start times.
- 📊 **Generate Statistics**: Collect and visualize statistics for EDF files.
- 📋 **Create Patient Table**: Generate a CSV table with patient names.
- 🎲 **Randomize Filenames**: Randomize filenames in the folder.
- 👤 **Remove Patient Info**: Remove patient information from EDF files.
- 📄 **Read EDF File Info**: Display information about the selected EDF file.

### Segmentation of EDF Files
- 📂 **Load EDF File**: Load an EDF file for segmentation.
- ✂️ **Split EDF File**: Split the EDF file into segments based on events.
- ⏲️ **Set Minimum Segment Duration**: Define the minimum duration for segments.

---

## 🛠️ Installation

Ensure you have Python 3.8 or higher installed.

Install the required dependencies:

```bash
pip install -r requirements.txt
```

Run the application:

```bash
python edf_app.py
```

---

## 🖥️ Usage

1. Launch the application.
2. Select a folder with EDF files using the **"Open Folder"** button.
3. Use the corresponding buttons to perform the desired operations:
   - 🖋️ **Rename EDF**: Renames files based on metadata.
   - 🚫 **Remove Corrupted**: Deletes corrupted files.
   - 🔍 **Remove Duplicates**: Deletes duplicate files.
   - ⏱️ **Find Similar**: Finds files with similar recording start times.
   - 📊 **Generate Statistics**: Generates statistics for the files.
   - 📋 **Create Patient Table**: Creates a CSV table with patient names.
   - 🎲 **Randomize Filenames**: Randomizes filenames.
   - 👤 **Remove Patient Info**: Removes patient information from files.
   - 📄 **Read EDF Info**: Displays information about the selected EDF file.
   - ✂️ **Split EDF File**: Splits the loaded EDF file into segments.

---

## 📜 License

This project is licensed under the MIT License. For details, see the [LICENSE](LICENSE) file.

---

## 👨‍💻 Author

Timur Petrenko  
📧 Email: psy66@narod.ru

---

## 📚 Citation

If you use this tool in your research, please consider citing it as follows:

```
Petrenko, Timur. EDF Batch & Segment Toolkit. 2025. Available on GitHub: https://github.com/Psy66/EEG_Stat.
```

---

## 📢 Important Note

This application is intended for educational and research purposes only. Use it at your own risk. The author does not take any responsibility for potential issues or damages caused by the use of this software.

---

## 🧩 Detailed Feature Descriptions

### Batch Processing of EDF Files
- **Open Folder with EDF Files**: The application allows you to select a folder containing EDF files for further processing. Once a folder is selected, all other features become available.
- **Rename EDF Files**: Files are renamed based on metadata extracted from the EDF files. The filename is generated using the patient's name and recording date.
- **Remove Corrupted Files**: The application checks each EDF file for integrity. If a file is corrupted, it is deleted from the folder.
- **Remove Duplicates**: The application searches for duplicate files by comparing their content (hash values). All duplicates, except one, are deleted.
- **Find Files with Similar Start Time**: The application finds files with recording start times that differ by no more than 10 minutes.
- **Generate Statistics**: The application collects statistics on all EDF files in the folder, including gender distribution, age distribution, and recording duration.
- **Create Patient Table**: A CSV file is generated containing patient information, including name, gender, and age at the time of recording.
- **Randomize Filenames**: Filenames are replaced with random 6-digit numeric codes. A mapping of old to new filenames is saved in a CSV file.
- **Remove Patient Info**: Patient information is removed from the EDF file headers while preserving UUID, gender, and birthdate.
- **Read EDF File Info**: The application displays detailed information about the selected EDF file, including patient name, gender, birthdate, recording date, recording duration, and channel list.

### Segmentation of EDF Files
- **Load EDF File**: Load an EDF file for segmentation.
- **Split EDF File**: Split the EDF file into segments based on events. The minimum segment duration can be configured.
- **Set Minimum Segment Duration**: Define the minimum duration for segments (default is 5 seconds).

---

## 🖥️ Interface

### Output Field
At the bottom of the interface, there is an output field where the results of operations are displayed. You can copy text from this field using:
- **Ctrl+C** — Copy selected text.
- **Ctrl+A** — Select all text.
- **Right-click** — Open a context menu for copying.

---

## 📂 Project Structure

```
EDF_Batch_Segment_Toolkit/
├── config/
│   └── settings.py          # Application settings
├── core/
│   ├── edf_processor.py     # Core logic for processing EDF files
│   ├── edf_segmentor.py     # Logic for segmenting EDF files
│   ├── edf_visualizer.py    # Visualization of statistics
│   └── montage_manager.py   # Montage creation for EEG channels
├── edf_app.py               # Main application module
├── README.md                # Project documentation
└── requirements.txt         # Dependencies
```

---

## 🛠️ Technical Details

### Dependencies:
- **mne**: For reading and analyzing EDF files.
- **pandas**: For working with tables and statistics.
- **seaborn** and **matplotlib**: For data visualization.
- **transliterate**: For transliterating patient names.

### Workflow:
1. The user selects a folder containing EDF files.
2. The application analyzes the files, extracts metadata, and performs the selected operations.
3. Results are saved in the `output` folder and displayed in the interface.

---