#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GUI interface to camera runner.
"""

"""
TODOs:
    * Add video streaming code
    * Set up child runners for single / multi cam operation
    * Set up threading to update video display
"""

import sys
import textwrap
from PyQt5.QtGui import *
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
from FlyCaptureUtils import (Camera, img2array, getAvailableCameras,
                             imgSize_from_vidMode, VIDEO_MODES, FRAMERATES,
                             GRAB_MODES, PIXEL_FORMATS)

import imageio; TEST_IMAGE = imageio.imread('imageio:chelsea.png')  # TODO

# Assorted default parameters
DEFAULTS = {'cam_mode':'Multi',
            'video_mode':'VM_640x480RGB',
            'framerate':'FR_30',
            'grab_mode':'BUFFER_FRAMES',
            'preview':Qt.Unchecked,
            'pixel_format':'RGB',
            'save_output':Qt.Checked,
            'output_encoder':'Auto',
            'output_format':'Auto',
            'overwrite':Qt.Unchecked,
            'save_timestamps':Qt.Checked,
            'mjpg_quality':75,
            'h264_bitrate':1e6,
            'h264_size':'Auto',
            'embedded_info':{'timestamp':Qt.Checked,
                             'gain':Qt.Unchecked,
                             'shutter':Qt.Unchecked,
                             'brightness':Qt.Unchecked,
                             'exposure':Qt.Unchecked,
                             'whiteBalance':Qt.Unchecked,
                             'frameCounter':Qt.Unchecked,
                             'strobePattern':Qt.Unchecked,
                             'ROIPosition':Qt.Unchecked} }


def error_dlg(parent, msg, title='Error', icon=QMessageBox.Critical):
    "Return error dialog"
    dlg = QMessageBox(parent)
    dlg.setWindowTitle(title)
    dlg.setIcon(icon)
    dlg.setText(msg)
    return dlg

def format_tooltip(text, *args, **kwargs):
    "Wrapper around textwrap.fill that preserves newline characters"
    return '\n'.join(textwrap.fill(t, *args, **kwargs) \
                     for t in text.splitlines())

def BoldQLabel(text):
    "Return QLabel formatted in bold"
    font = QFont()
    font.setBold(True)
    label = QLabel(text)
    label.setFont(font)
    return label


class MainWindow(QMainWindow):
    "Main window for selecting camera and output settings."
    def __init__(self):
        super().__init__()
        self.findCameras()
        self.initUI()
        self.show()
        if not self.camList:
            error_dlg(self, 'No cameras found!', 'Warning',
                      QMessageBox.Warning).exec_()

    def findCameras(self):
        self.camList = getAvailableCameras()

    def initUI(self):
        # Init central widget
        self.centralWidget = QWidget()
        self.setCentralWidget(self.centralWidget)

        # Init window
        self.resize(600, 700)
        self.setWindowTitle('Camera Runner')

        # Init main grid layout
        grid = QGridLayout()
        self.centralWidget.setLayout(grid)

        # Add selectCamsGroup
        self.initSelectCamsGroup()
        grid.addWidget(self.selectCamsGroup, 0, 0)

        # Add optsGroup
        self.initOptsGroup()
        grid.addWidget(self.optsGroup, 0, 1)

        # Add outputGroup
        self.initOutputGroup()
        grid.addWidget(self.outputGroup, 1, 0, 1, 2)

        # Add statusGroup
        self.initStatusGroup()
        grid.addWidget(self.statusGroup, 2, 0, 1, 2)

        # Add buttons
        hbox = QHBoxLayout()
        hbox.addStretch(1)

        self.connectBtn = QPushButton('Connect')
        self.connectBtn.clicked.connect(self.on_connect)
        self.connectBtn.setToolTip('Connect to camera(s)')
        hbox.addWidget(self.connectBtn)

        self.startBtn = QPushButton('Start Capture')
        self.startBtn.clicked.connect(self.on_start)
        self.startBtn.setToolTip('Start video capture')
        self.startBtn.setEnabled(False)
        hbox.addWidget(self.startBtn)

        self.stopBtn = QPushButton('Stop Capture')
        self.stopBtn.clicked.connect(self.on_stop)
        self.stopBtn.setToolTip('Stop video capture')
        self.stopBtn.setEnabled(False)
        hbox.addWidget(self.stopBtn)

        self.exitBtn = QPushButton('Exit')
        self.exitBtn.clicked.connect(self.on_exit)
        self.exitBtn.setToolTip('Exit application')
        hbox.addWidget(self.exitBtn)

        grid.addLayout(hbox, 3, 0, 1, 2)

    def initSelectCamsGroup(self):
        # Init group and vbox
        self.selectCamsGroup = QGroupBox('Select Cameras')
        group_vbox = QVBoxLayout()

        # Add camera mode dropdown
        hbox = QHBoxLayout()
        hbox.addWidget(QLabel('Camera mode'))
        self.camMode = QComboBox()
        self.camMode.addItems(['Single', 'Multi'])
        self.camMode.setCurrentText(DEFAULTS['cam_mode'])
        self.camMode.currentTextChanged.connect(self.on_camera_mode_change)
        self.camMode.setToolTip('Acquire images from one or multiple cameras')
        hbox.addWidget(self.camMode)
        hbox.addStretch(1)
        group_vbox.addLayout(hbox)

        # Add camera select table
        self.cameraTable = QTableWidget(len(self.camList), 3)

        self.cameraTable.setHorizontalHeaderLabels([None,'Camera','Serial'])
        header = self.cameraTable.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        self.cameraTable.verticalHeader().setVisible(False)

        for row, (cam_num, serial) in enumerate(self.camList):
            chk = QTableWidgetItem()
            chk.setCheckState(Qt.Checked)

            txt1 = QTableWidgetItem(str(cam_num))
            txt1.setFlags(Qt.ItemIsEnabled)
            txt2 = QTableWidgetItem(str(serial))
            txt2.setFlags(Qt.ItemIsEnabled)

            self.cameraTable.setItem(row, 0, chk)
            self.cameraTable.setItem(row, 1, txt1)
            self.cameraTable.setItem(row, 2, txt2)

        self.cameraTable.cellClicked.connect(self.on_camera_check)

        self.cameraTable.setToolTip('Select camera(s) to use')

        self.set_camTable_selectivity()

        group_vbox.addWidget(self.cameraTable)

        # Update group
        self.selectCamsGroup.setLayout(group_vbox)

    def initOptsGroup(self):
        # Init group and grid
        self.optsGroup = QGroupBox('Camera Options')
        form = QFormLayout()

        # Add widgets
        self.vidMode = QComboBox()
        self.vidMode.addItems(VIDEO_MODES.keys())
        self.vidMode.setCurrentText(DEFAULTS['video_mode'])
        self.vidMode.setToolTip('Camera resolution and colour mode')
        form.addRow('Video mode', self.vidMode)

        self.framerate = QComboBox()
        self.framerate.addItems(FRAMERATES.keys())
        self.framerate.setCurrentText(DEFAULTS['framerate'])
        self.framerate.setToolTip('Camera frame rate')
        form.addRow('Framerate', self.framerate)

        self.grabMode = QComboBox()
        self.grabMode.addItems(GRAB_MODES.keys())
        self.grabMode.setCurrentText(DEFAULTS['grab_mode'])
        self.grabMode.setToolTip(format_tooltip(
            'If BUFFER_FRAMES, read oldest frame out of buffer. Frames are '
            'not lost, but computer must keep up to avoid buffer overflows.'
            '\n\n'
            'If DROP_FRAMES, read newest frame out of buffer. Older frames '
            'will be lost if computer falls behind.'
            ))
        form.addRow('Grab mode', self.grabMode)

        self.saveOutput = QCheckBox()
        self.saveOutput.stateChanged.connect(self.on_save_output_check)
        self.saveOutput.setCheckState(DEFAULTS['save_output'])
        self.saveOutput.setToolTip('Enable/disable Output Options dialog')
        form.addRow('Save video', self.saveOutput)

        self.preview = QCheckBox()
        self.preview.setCheckState(DEFAULTS['preview'])
        self.preview.setToolTip(
            'Display live video preview.\n'
            'Only available for single-camera operation.'
            )
        form.addRow('Preview', self.preview)

        self.pixelFormat = QComboBox()
        self.pixelFormat.addItems(PIXEL_FORMATS.keys())
        self.pixelFormat.setCurrentText(DEFAULTS['pixel_format'])
        self.pixelFormat.setToolTip(
            'Colour mode for display: must be appropriate for video mode.\n'
            'Only available for single-camera operation.'
            )
        form.addRow('Pixel format', self.pixelFormat)

        if self.camMode.currentText() == 'Multi':
            self.preview.setEnabled(False)
            self.pixelFormat.setEnabled(False)


        # Update group
        self.optsGroup.setLayout(form)

    def initOutputGroup(self):
        # Init group and vbox
        self.outputGroup = QGroupBox('Output Options')
        self.outputGroup.setEnabled(self.saveOutput.isChecked())

        group_vbox = QVBoxLayout()

        ## File select
        vbox = QVBoxLayout()
        vbox.addWidget(BoldQLabel('File select'), Qt.AlignLeft)

        hbox = QHBoxLayout()
        self.outputFile = QLineEdit()
        self.outputFile.setToolTip(format_tooltip(
            'Base filepath to desired output file. If camera mode is Multi '
            'then camera numbers will be appended to filename. File '
            'extension can be added automatically if an output encoder is '
            'specified.'
            ))
        hbox.addWidget(self.outputFile)
        btn = QPushButton('Browse')
        btn.clicked.connect(self.on_fileselect_browse)
        hbox.addWidget(btn)
        vbox.addLayout(hbox)

        group_vbox.addLayout(vbox)
        group_vbox.addSpacing(10)

        ## Opts
        opts_hbox = QHBoxLayout()

        # General Opts
        form = QFormLayout()
        form.addRow(BoldQLabel('General Options'))

        self.outputEncoder = QComboBox()
        self.outputEncoder.addItems(['Auto','AVI','MJPG','H264'])
        self.outputEncoder.setCurrentText(DEFAULTS['output_encoder'])
        self.outputEncoder.setToolTip(format_tooltip(
            'Writer format. If Auto, will attempt to determine from '
            'filename extension, or will error if no extension provided.'
            ))
        form.addRow('Encoder', self.outputEncoder)

        self.outputOverwrite = QCheckBox()
        self.outputOverwrite.setCheckState(DEFAULTS['overwrite'])
        self.outputOverwrite.setToolTip('Overwrite file if it already exists')
        form.addRow('Overwrite', self.outputOverwrite)

        self.outputSaveTimestamps = QCheckBox()
        self.outputSaveTimestamps.setCheckState(DEFAULTS['save_timestamps'])
        self.outputSaveTimestamps.setToolTip(
            'Save timestamps for each frame to a corresponding CSV file'
            )
        form.addRow('Timestamps CSV', self.outputSaveTimestamps)

        opts_hbox.addLayout(form)
        opts_hbox.addStretch(1)

        # MJPG & H264 options
        vbox = QVBoxLayout()

        mjpg_form = QFormLayout()
        lab = BoldQLabel('MJPG Options')
        lab.setToolTip('Options applicable only for MJPG format')
        mjpg_form.addRow(lab)

        self.outputQuality = QSpinBox()
        self.outputQuality.setRange(0, 100)
        self.outputQuality.setValue(DEFAULTS['mjpg_quality'])
        self.outputQuality.setToolTip('Video quality (value between 0 and 100)')
        mjpg_form.addRow('Quality', self.outputQuality)

        h264_form = QFormLayout()
        lab = BoldQLabel('H264 Options')
        lab.setToolTip('Options applicable only for H264 format')
        h264_form.addRow(lab)

        self.outputBitrate = QSpinBox()
        self.outputBitrate.setRange(0, 2**31-1)
        self.outputBitrate.setSingleStep(1000)
        self.outputBitrate.setValue(DEFAULTS['h264_bitrate'])
        self.outputBitrate.setToolTip('Bitrate (in bits per second)')
        h264_form.addRow('Bitrate', self.outputBitrate)

        self.outputSize = QLineEdit()
        self.outputSize.setText(DEFAULTS['h264_size'])
        self.outputSize.setToolTip(format_tooltip(
            'Image width and height in pixels, specified as (W,H) tuple '
            '(including brackets). Must match resolution specified in video '
            'mode. If Auto, will attempt to determine from video mode.'
            ))
        h264_form.addRow('Image Size', self.outputSize)

        vbox.addLayout(mjpg_form)
        vbox.addSpacing(10)
        vbox.addLayout(h264_form)
        vbox.addStretch(1)

        opts_hbox.addLayout(vbox)
        opts_hbox.addStretch(1)

        # Embedded image info options
        form = QFormLayout()
        lab = BoldQLabel('Embed Image Info')
        lab.setToolTip(format_tooltip(
            'Information to be embedded in top-left image pixels. To be '
            'usable, video mode must be set to monochrome.'
            ))
        form.addRow(lab)

        self.outputEmbeddedImageInfo = {}
        for prop, prop_default in DEFAULTS['embedded_info'].items():
            widget = QCheckBox()
            widget.setCheckState(prop_default)
            self.outputEmbeddedImageInfo[prop] = widget
            form.addRow(prop, widget)

        opts_hbox.addLayout(form)

        # Add options to main vbox
        group_vbox.addLayout(opts_hbox)

        # Add stretch below
        group_vbox.addStretch(1)

        # Update group
        self.outputGroup.setLayout(group_vbox)

    def initStatusGroup(self):
        self.statusGroup = QGroupBox('Status')

        self.statusText = QLabel()
        self.statusText.setText('Disconnected')
        font = self.statusText.font()
        font.setPointSize(16)
        self.statusText.setFont(font)
        self.statusText.setStyleSheet('QLabel {color:red}')
        self.statusText.setAlignment(Qt.AlignCenter)

        layout = QHBoxLayout()
        layout.addWidget(self.statusText)

        self.statusGroup.setLayout(layout)

    def parse_settings(self):
        """
        Extract current settings.

        Returns
        -------
        res : dict or None
            Dictionary with settings listed against keys. If error encountered
            will return None instead.
        """
        # Misc values
        cam_mode = self.camMode.currentText()
        preview = self.preview.isEnabled() and self.preview.isChecked()
        pixel_format = self.pixelFormat.currentText()

        # Cam nums
        cam_nums = []
        for rowN in range(self.cameraTable.rowCount()):
            use_cam = self.cameraTable.item(rowN, 0).checkState() == Qt.Checked
            cam_num = int(self.cameraTable.item(rowN, 1).text())
            if use_cam:
                cam_nums.append(cam_num)
        if cam_mode == 'Single':
            assert(len(cam_nums) == 1)
            cam_nums = cam_nums[0]

        # Cam kwargs
        cam_kwargs = {'video_mode':self.vidMode.currentText(),
                      'framerate':self.framerate.currentText(),
                      'grab_mode':self.grabMode.currentText()}

        # Output video and writer kwargs
        if self.saveOutput.isChecked():
            outfile = self.outputFile.text()

            # Error if no outfile provided and return None
            if not outfile:
                error_dlg(self, 'Must specify filename if saving video').exec_()
                return

            writer_kwargs = {
                'file_format':self.outputEncoder.currentText(),
                'file_format':self.outputFormat.currentText(),
                'overwrite':self.outputOverwrite.isChecked(),
                'csv_timestamps':self.outputSaveTimestamps.isChecked(),
                'quality':self.outputQuality.value(),
                'bitrate':self.outputBitrate.value(),
                }

            if self.outputEncoder.currentText() == 'Auto':
                writer_kwargs['encoder'] = None
            else:
                writer_kwargs['encoder'] = self.outputEncoder.currentText()

            if self.outputFormat.currentText() == 'Auto':
                writer_kwargs['file_format'] = None
            else:
                writer_kwargs['file_format'] = self.outputFormat.currentText()

            if self.outputSize.text() == 'Auto':
                writer_kwargs['img_size'] = None
            else:
                writer_kwargs['img_size'] = eval(self.outputSize.text())

            writer_kwargs['embedded_image_info'] = []
            for prop, widget in self.outputEmbeddedImageInfo.items():
                if widget.isChecked():
                    writer_kwargs['embedded_image_info'].append(prop)

        else:  # don't save video
            outfile = None
            writer_kwargs = {}

        # Assign into class
        return {'cam_mode':cam_mode,
                'cam_nums':cam_nums,
                'cam_kwargs':cam_kwargs,
                'outfile':outfile,
                'writer_kwargs':writer_kwargs,
                'preview':preview,
                'pixel_format':pixel_format}

    def set_camTable_selectivity(self, row=0):
        """
        Sets whether one or multiple cameras in table may be selected,
        dependent on camera mode
        """
        if self.camMode.currentText() == 'Single':
            for rowN in range(self.cameraTable.rowCount()):
                chk = QTableWidgetItem()
                if rowN == row:
                    chk.setCheckState(Qt.Checked)
                else:
                    chk.setCheckState(Qt.Unchecked)
                self.cameraTable.setItem(rowN, 0, chk)

    def on_camera_mode_change(self, text):
        """
        On camera mode change: re-select default cameras & disable/enable
        preview options
        """
        for rowN in range(self.cameraTable.rowCount()):
            chk = QTableWidgetItem()
            if text == 'Multi' or (text == 'Single' and rowN == 0):
                chk.setCheckState(Qt.Checked)
            else:
                chk.setCheckState(Qt.Unchecked)
            self.cameraTable.setItem(rowN, 0, chk)

        if text == 'Single':
            self.preview.setEnabled(True)
            self.pixelFormat.setEnabled(True)
        else:
            self.preview.setEnabled(False)
            self.pixelFormat.setEnabled(False)

    def on_camera_check(self, row, col):
        """
        Handle change in camera check status. Specifically, handle single-cam
        mode by ensuring selecting one camera deselects all others
        """
        self.set_camTable_selectivity(row)

    def on_fileselect_browse(self):
        "Open save file dialog"
        dlg = QFileDialog()
        file = dlg.getSaveFileName()[0]
        self.outputFile.setText(file)

    def on_save_output_check(self):
        "Enable/disable 'Output Options' group box"
        # Options-group created BEFORE output-group so would error 1st time
        if hasattr(self, 'outputGroup'):
            self.outputGroup.setEnabled(self.saveOutput.isChecked())

    def on_connect(self):
        "Connect to cameras, hide window, and open runner window"

        # Parse parameter values
        settings = self.parse_settings()
        if not settings:
            return
        print(settings)

        self.statusText.setText('Connected')
        self.statusText.setStyleSheet('QLabel {color:green}')

        self.connectBtn.setEnabled(False)
        self.startBtn.setEnabled(True)

        # Init preview window?
        # NOTE - window instance must be assigned into this class to prevent
        # it getting immediately garbage collected!
        if settings['preview']:
            xPos = self.pos().x() + self.size().width()
            yPos = self.pos().y()
            size = imgSize_from_vidMode(settings['cam_kwargs']['video_mode'])
            self.preview_window = PreviewWindow(self, size, (xPos,yPos))

    def on_start(self):
        print('Start')

        self.statusText.setText('Running')
        self.statusText.setStyleSheet('QLabel {color:green}')

        self.startBtn.setEnabled(False)
        self.stopBtn.setEnabled(True)

        if hasattr(self, 'preview_window'):
            self.preview_window.setImage(TEST_IMAGE)  # XXX

    def on_stop(self):
        print('Stop')

        self.statusText.setText('Disconnected')
        self.statusText.setStyleSheet('QLabel {color:red}')

        self.stopBtn.setEnabled(False)
        self.connectBtn.setEnabled(True)

        if hasattr(self, 'preview_window'):
            self.preview_window.close()

    def on_exit(self):
        print('Exit')

        if hasattr(self, 'preview_window'):
            self.preview_window.close()

        self.close()


class PreviewWindow(QMainWindow):
    "Class for video preview pop-up"
    def __init__(self, parent, winsize=(640,480), pos=(0,0)):
        super().__init__(parent)
        self.parent = parent
        self.winsize = winsize
        self.pos = pos
        self.initUI()
        self.show()

    def initUI(self):
        # Init window
        self.setWindowTitle('Preview')
        self.resize(*self.winsize)
        self.move(*self.pos)

        # Add label for pixmap, allocate as central widget
        self.imgQLabel = QLabel()
        self.imgQLabel.setAlignment(Qt.AlignCenter)
        self.setCentralWidget(self.imgQLabel)

    def setImage(self, im):
        """
        Takes image (as numpy array) and updates QLabel display.

        Parameters
        ----------
        im : numpy array
            Image as 2D (grayscale) or 3D (RGB) numpy array with uint8 dtype
        """
        W, H = im.shape[:2]
        stride = im.strides[0]

        if im.ndim == 3:
            if im.shape[2] == 3:
                fmt = QImage.Format_RGB888
            elif im.shape[2] == 4:
                fmt = QImage.Format_RGBA8888
            else:
                raise TypeError('Unknown colour format')
        elif im.ndim == 2:
            fmt = QImage.Format_Grayscale8
        else:
            raise TypeError('Unknown image format')

        qimg = QImage(im.data, H, W, stride, fmt)
        qpixmap = QPixmap(qimg).scaled(self.imgQLabel.size(), Qt.KeepAspectRatio)
        self.imgQLabel.setPixmap(qpixmap)


### Run application ###
if __name__ == '__main__':
    app = QApplication(sys.argv)
    win = MainWindow()
    sys.exit(app.exec_())
