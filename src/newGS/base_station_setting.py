#!/usr/bin/env python3
from PyQt5.QtWidgets import QDialog, QFormLayout, QDoubleSpinBox, QDialogButtonBox, QLineEdit

class BaseStationSettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("기지국 파라미터 설정")
        layout = QFormLayout(self)
        
        self.le_gs_name = QLineEdit("Default GS")
        layout.addRow("기지국 이름:", self.le_gs_name)

        self.ds_gs_latitude = QDoubleSpinBox()
        self.ds_gs_latitude.setRange(-90.0, 90.0); self.ds_gs_latitude.setDecimals(6); self.ds_gs_latitude.setValue(36.350413)
        layout.addRow("위도 (deg):", self.ds_gs_latitude)
        
        self.ds_gs_longitude = QDoubleSpinBox()
        self.ds_gs_longitude.setRange(-180.0, 180.0); self.ds_gs_longitude.setDecimals(6); self.ds_gs_longitude.setValue(127.384548)
        layout.addRow("경도 (deg):", self.ds_gs_longitude)

        self.ds_gs_altitude = QDoubleSpinBox()
        self.ds_gs_altitude.setRange(0.0, 5000.0); self.ds_gs_altitude.setValue(50.0)
        layout.addRow("고도 (m):", self.ds_gs_altitude)
        
        self.ds_min_elevation = QDoubleSpinBox()
        self.ds_min_elevation.setRange(0.0, 90.0); self.ds_min_elevation.setValue(5.0)
        layout.addRow("통신 최소 앙각 (deg):", self.ds_min_elevation)

        self.ds_gs_antenna_gain = QDoubleSpinBox()
        self.ds_gs_antenna_gain.setRange(0.0, 60.0); self.ds_gs_antenna_gain.setValue(35.0)
        layout.addRow("안테나 이득 (dBi):", self.ds_gs_antenna_gain)
        
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept); btns.rejected.connect(self.reject)
        layout.addWidget(btns)
    
    def getParameters(self):
        return {
            "gs_name": self.le_gs_name.text(),
            "gs_lat": self.ds_gs_latitude.value(),
            "gs_lon": self.ds_gs_longitude.value(),
            "gs_alt": self.ds_gs_altitude.value(),
            "min_elevation": self.ds_min_elevation.value(),
            "gs_antenna_gain": self.ds_gs_antenna_gain.value()
        }

    def setParameters(self, params):
        self.le_gs_name.setText(params.get("gs_name", "Default GS"))
        self.ds_gs_latitude.setValue(params.get("gs_lat", 36.350413))
        self.ds_gs_longitude.setValue(params.get("gs_lon", 127.384548))
        self.ds_gs_altitude.setValue(params.get("gs_alt", 50.0))
        self.ds_min_elevation.setValue(params.get("min_elevation", 5.0))
        self.ds_gs_antenna_gain.setValue(params.get("gs_antenna_gain", 35.0))
