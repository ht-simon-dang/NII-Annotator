import os
import sys
import json
import nibabel as nib
import numpy as np
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QListWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QComboBox, QSlider, QFileDialog, QPushButton, QTextEdit, QSpinBox
)
from PyQt5.QtCore import Qt, QObject, QEvent
from PyQt5.QtGui import QKeyEvent
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

class NiiCanvas(FigureCanvas):
    def __init__(self, figure, annotate_callback):
        super().__init__(figure)
        self.annotate_callback = annotate_callback

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_G:
            self.annotate_callback()
        else:
            super().keyPressEvent(event)

class NiiExplorer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("NIfTI Explorer")
        self.resize(1000, 600)
        self.data = None
        self.annotations = {}
        self.init_ui()
        self.open_folder()

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)

        # Left Sidebar - file list
        self.file_list = QListWidget()
        self.file_list.currentItemChanged.connect(self.on_file_changed)
        layout.addWidget(self.file_list, 1)

        # Right Sidebar - annotations display and export
        self.annotation_display = QTextEdit()
        self.annotation_display.setReadOnly(True)

        self.export_current_btn = QPushButton("Export Current Annotation")
        self.export_current_btn.clicked.connect(self.export_current_annotation)

        self.export_all_btn = QPushButton("Export All Annotations")
        self.export_all_btn.clicked.connect(self.save_annotations)

        right_sidebar = QVBoxLayout()
        right_sidebar.addWidget(QLabel("Current Annotations"))
        right_sidebar.addWidget(self.annotation_display)
        right_sidebar.addWidget(self.export_current_btn)
        right_sidebar.addWidget(self.export_all_btn)
        layout.addLayout(right_sidebar, 2)

        # Main panel
        right_panel = QVBoxLayout()
        # Controls
        controls = QHBoxLayout()
        self.axis_combo = QComboBox()
        self.axis_combo.addItems(["axial", "coronal", "sagittal"])
        self.axis_combo.currentTextChanged.connect(self.on_axis_changed)
        controls.addWidget(QLabel("Axis:"))
        controls.addWidget(self.axis_combo)

        self.slice_slider = QSlider(Qt.Horizontal)
        self.slice_slider.setEnabled(False)
        self.slice_slider.valueChanged.connect(self.on_slice_changed)
        controls.addWidget(QLabel("Slice:"))
        controls.addWidget(self.slice_slider)

        self.zoom_spin = QSpinBox()
        self.zoom_spin.setRange(10, 500)
        self.zoom_spin.setValue(100)
        self.zoom_spin.setSuffix("%")
        self.zoom_spin.valueChanged.connect(self.update_view)
        controls.addWidget(QLabel("Zoom:"))
        controls.addWidget(self.zoom_spin)

        right_panel.addLayout(controls)

        # Annotate button
        self.annotate_button = QPushButton("Confirm Page (G)")
        self.annotate_button.clicked.connect(self.annotate_page)
        right_panel.addWidget(self.annotate_button)

        # Figure
        self.figure = Figure()
        self.canvas = NiiCanvas(self.figure, self.annotate_page)
        self.canvas.setFocusPolicy(Qt.StrongFocus)
        self.canvas.setFocus()
        right_panel.addWidget(self.canvas, 4)

        layout.addLayout(right_panel, 4)

    def wheelEvent(self, event):
        if self.data is None or not self.slice_slider.isEnabled():
            return

        delta = event.angleDelta().y()
        step = 1 if delta > 0 else -1
        new_value = self.slice_slider.value() + step
        new_value = max(0, min(new_value, self.slice_slider.maximum()))
        self.slice_slider.setValue(new_value)

    def open_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select NIfTI Folder", os.getcwd())
        if folder:
            self.load_files(folder)
            self.load_existing_annotations()
        else:
            sys.exit()

    def load_files(self, folder):
        nii_files = sorted([f for f in os.listdir(folder)
                             if f.endswith(".nii") or f.endswith(".nii.gz")])
        self.folder = folder
        self.file_list.clear()
        self.file_list.addItems(nii_files)
        if nii_files:
            self.file_list.setCurrentRow(0)

    def load_existing_annotations(self):
        annotations_path = os.path.join(self.folder, "annotations.json")
        if os.path.exists(annotations_path):
            with open(annotations_path, "r") as f:
                try:
                    self.annotations = json.load(f)
                except json.JSONDecodeError:
                    print("Failed to parse annotations.json")

    def on_file_changed(self, current, previous):
        if current:
            file_name = current.text()
            path = os.path.join(self.folder, file_name)
            self.data = nib.load(path).get_fdata()
            self.axis = self.axis_combo.currentText()
            self.update_slider()
            self.update_view()
            self.update_annotation_display()

    def on_axis_changed(self, axis):
        self.axis = axis
        if self.data is not None:
            self.update_slider()
            self.update_view()

    def update_slider(self):
        axis_idx = {"sagittal":0, "coronal":1, "axial":2}[self.axis]
        max_idx = self.data.shape[axis_idx] - 1
        self.slice_slider.setMaximum(max_idx)
        self.slice_slider.setEnabled(True)
        self.slice_slider.setValue(max_idx // 2)

    def on_slice_changed(self, idx):
        if self.data is not None:
            self.slice_index = idx
            self.update_view()

    def update_view(self):
        axis = self.axis
        idx = self.slice_slider.value()
        zoom = self.zoom_spin.value() / 100.0

        if axis == "axial":
            slice_data = self.data[:, :, idx]
        elif axis == "coronal":
            slice_data = self.data[:, idx, :]
        else:
            slice_data = self.data[idx, :, :]

        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.imshow(np.rot90(slice_data), cmap='gray', aspect='auto', extent=[0, slice_data.shape[0]*zoom, 0, slice_data.shape[1]*zoom])
        ax.set_title(f"{axis.capitalize()} slice {idx}")
        ax.axis('off')
        self.canvas.draw()
        self.canvas.setFocus()

    def annotate_page(self):
        current_item = self.file_list.currentItem()
        if not current_item:
            return

        filename = current_item.text()
        axis = self.axis_combo.currentText()
        idx = self.slice_slider.value()

        if filename not in self.annotations:
            self.annotations[filename] = {"axial": [], "coronal": [], "sagittal": []}

        if idx not in self.annotations[filename][axis]:
            self.annotations[filename][axis].append(idx)
            self.annotations[filename][axis].sort()

        self.update_annotation_display()

    def update_annotation_display(self):
        current_item = self.file_list.currentItem()
        if not current_item:
            return

        filename = current_item.text()
        annotation = self.annotations.get(filename, {"axial": [], "coronal": [], "sagittal": []})
        display_text = f"File: {filename}\n"
        for axis in ["axial", "coronal", "sagittal"]:
            pages = annotation.get(axis, [])
            display_text += f"{axis.capitalize()}: {pages if pages else 'N/A'}\n"
        self.annotation_display.setText(display_text)

    def export_current_annotation(self):
        current_item = self.file_list.currentItem()
        if not current_item:
            return

        filename = current_item.text()
        annotation = self.annotations.get(filename)
        if annotation:
            out_path = os.path.join(self.folder, f"{filename}_annotation.json")
            with open(out_path, "w") as f:
                json.dump({filename: annotation}, f, indent=4)

    def save_annotations(self):
        output_path = os.path.join(self.folder, "annotations.json")
        with open(output_path, "w") as f:
            json.dump(self.annotations, f, indent=4)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = NiiExplorer()
    window.show()
    sys.exit(app.exec_())
