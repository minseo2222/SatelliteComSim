#!/usr/bin/env python3
# base_station_setting.py

from PyQt5.QtWidgets import QDialog, QFormLayout, QDoubleSpinBox, QDialogButtonBox, QLineEdit

class BaseStationSettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("기지국 파라미터 설정")
        self.setModal(True)
        layout = QFormLayout(self)
        
        # 기지국 이름 (식별용)
        self.le_gs_name = QLineEdit("Default GS")
        layout.addRow("기지국 이름:", self.le_gs_name)

        # 기지국 위치: 위도 (Latitude)
        self.ds_gs_latitude = QDoubleSpinBox()
        self.ds_gs_latitude.setRange(-90.0, 90.0)
        self.ds_gs_latitude.setDecimals(6)
        self.ds_gs_latitude.setValue(36.350413) # 예: 대전 위도
        self.ds_gs_latitude.setSuffix(" °")
        layout.addRow("위도:", self.ds_gs_latitude)
        
        # 기지국 위치: 경도 (Longitude)
        self.ds_gs_longitude = QDoubleSpinBox()
        self.ds_gs_longitude.setRange(-180.0, 180.0)
        self.ds_gs_longitude.setDecimals(6)
        self.ds_gs_longitude.setValue(127.384548) # 예: 대전 경도
        self.ds_gs_longitude.setSuffix(" °")
        layout.addRow("경도:", self.ds_gs_longitude)

        # 기지국 위치: 고도 (Altitude)
        self.ds_gs_altitude = QDoubleSpinBox()
        self.ds_gs_altitude.setRange(0.0, 10000.0) # 미터 단위
        self.ds_gs_altitude.setDecimals(2)
        self.ds_gs_altitude.setValue(50.0) # 예: 50m
        self.ds_gs_altitude.setSuffix(" m")
        layout.addRow("고도:", self.ds_gs_altitude)
        
        # 기지국 안테나 최소 앙각 (Minimum Elevation Angle)
        self.ds_min_elevation = QDoubleSpinBox()
        self.ds_min_elevation.setRange(0.0, 90.0)
        self.ds_min_elevation.setValue(5.0) # 예: 5도
        self.ds_min_elevation.setSuffix(" °")
        layout.addRow("최소 앙각:", self.ds_min_elevation)

        # 기지국 안테나 이득 (dBi) - 위성 설정과 유사하게 추가
        self.ds_gs_antenna_gain = QDoubleSpinBox()
        self.ds_gs_antenna_gain.setRange(0.0, 50.0) # 기지국 안테나는 더 클 수 있음
        self.ds_gs_antenna_gain.setValue(35.0)
        self.ds_gs_antenna_gain.setSuffix(" dBi")
        layout.addRow("안테나 이득 (GS):", self.ds_gs_antenna_gain)
        
        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
    
    def getParameters(self):
        return {
            "gs_name": self.le_gs_name.text(),
            "gs_latitude": self.ds_gs_latitude.value(),
            "gs_longitude": self.ds_gs_longitude.value(),
            "gs_altitude": self.ds_gs_altitude.value(),
            "min_elevation": self.ds_min_elevation.value(),
            "gs_antenna_gain": self.ds_gs_antenna_gain.value(),
        }

    def setParameters(self, params):
        self.le_gs_name.setText(params.get("gs_name", "Default GS"))
        self.ds_gs_latitude.setValue(params.get("gs_latitude", 36.350))
        self.ds_gs_longitude.setValue(params.get("gs_longitude", 127.384))
        self.ds_gs_altitude.setValue(params.get("gs_altitude", 50.0))
        self.ds_min_elevation.setValue(params.get("min_elevation", 5.0))
        self.ds_gs_antenna_gain.setValue(params.get("gs_antenna_gain", 35.0))
