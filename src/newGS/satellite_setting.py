#!/usr/bin/env python3
# satellite_setting.py

from PyQt5.QtWidgets import (QDialog, QFormLayout, QComboBox, QDoubleSpinBox, 
                             QDialogButtonBox, QGroupBox, QVBoxLayout)

class SatelliteSettingsDialog(QDialog):
    # 위성별 프리셋 데이터베이스 (TLE 이름: {시각화 파라미터})
    # 실제 TLE 데이터를 파싱하는 대신, 대표적인 근사값을 매핑해 둡니다.
    SAT_PRESETS = {
        "ISS": {
            "frequency": 0.437, "antenna_gain": 0.0, "transmit_power": 30.0,
            "sat_size": 15.0, "sat_speed": 0.08, 
            "orbital_radius": 400.0, "inclination": 51.6, "eccentricity": 0.001
        },
        "KITSAT-3": {
            "frequency": 2.2, "antenna_gain": 5.0, "transmit_power": 33.0,
            "sat_size": 8.0, "sat_speed": 0.06, 
            "orbital_radius": 720.0, "inclination": 98.0, "eccentricity": 0.0
        },
        "ANASIS-II": {
            "frequency": 12.0, "antenna_gain": 30.0, "transmit_power": 40.0,
            "sat_size": 20.0, "sat_speed": 0.0,  # 정지궤도는 지구 기준 상대 속도 0에 근접 (시각화용)
            "orbital_radius": 35786.0, "inclination": 0.0, "eccentricity": 0.0
        },
        "NEXTSAT-1": {
            "frequency": 2.4, "antenna_gain": 3.0, "transmit_power": 27.0,
            "sat_size": 5.0, "sat_speed": 0.07, 
            "orbital_radius": 575.0, "inclination": 97.0, "eccentricity": 0.0
        },
        "CAS500-1": {
            "frequency": 8.0, "antenna_gain": 10.0, "transmit_power": 35.0,
            "sat_size": 12.0, "sat_speed": 0.07, 
            "orbital_radius": 500.0, "inclination": 97.0, "eccentricity": 0.0
        }
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("위성 파라미터 설정")
        self.setModal(True)
        self.resize(400, 600)
        
        main_layout = QVBoxLayout(self)
        
        # --- [1] 물리 엔진 설정 ---
        phy_group = QGroupBox("🛰️ 물리 엔진 / 통신 설정 (Physics)")
        phy_layout = QFormLayout()
        
        self.cb_sat_name = QComboBox()
        self.cb_sat_name.addItems(self.SAT_PRESETS.keys())
        # ★ 콤보박스 변경 시 자동 업데이트 연결
        self.cb_sat_name.currentTextChanged.connect(self.on_satellite_changed)
        phy_layout.addRow("위성 선택 (TLE):", self.cb_sat_name)

        self.ds_frequency = QDoubleSpinBox()
        self.ds_frequency.setRange(0.1, 50.0); self.ds_frequency.setDecimals(4); self.ds_frequency.setSuffix(" GHz")
        phy_layout.addRow("업링크 주파수:", self.ds_frequency)
        
        self.ds_antenna_gain = QDoubleSpinBox()
        self.ds_antenna_gain.setRange(0.0, 100.0); self.ds_antenna_gain.setSuffix(" dBi")
        phy_layout.addRow("수신 안테나 이득:", self.ds_antenna_gain)
        
        self.ds_transmit_power = QDoubleSpinBox()
        self.ds_transmit_power.setRange(-30.0, 100.0); self.ds_transmit_power.setSuffix(" dBm")
        phy_layout.addRow("송신 전력:", self.ds_transmit_power)
        
        phy_group.setLayout(phy_layout)
        main_layout.addWidget(phy_group)

        # --- [2] 시각화 설정 ---
        vis_group = QGroupBox("🎨 3D 시각화 설정 (View Only)")
        vis_layout = QFormLayout()
        
        self.ds_sat_size = QDoubleSpinBox()
        self.ds_sat_size.setRange(1.0, 100.0)
        vis_layout.addRow("표시 크기:", self.ds_sat_size)
        
        self.ds_sat_speed = QDoubleSpinBox()
        self.ds_sat_speed.setRange(0.0, 5.0); self.ds_sat_speed.setDecimals(3)
        vis_layout.addRow("회전 속도:", self.ds_sat_speed)
        
        self.ds_orbital_radius = QDoubleSpinBox()
        self.ds_orbital_radius.setRange(100.0, 40000.0); self.ds_orbital_radius.setSuffix(" km")
        vis_layout.addRow("표시 고도:", self.ds_orbital_radius)
        
        self.ds_inclination = QDoubleSpinBox()
        self.ds_inclination.setRange(0.0, 180.0); self.ds_inclination.setSuffix(" °")
        vis_layout.addRow("표시 경사각:", self.ds_inclination)
        
        self.ds_eccentricity = QDoubleSpinBox()
        self.ds_eccentricity.setRange(0.0, 1.0); self.ds_eccentricity.setDecimals(3)
        vis_layout.addRow("이심률:", self.ds_eccentricity)
        
        vis_group.setLayout(vis_layout)
        main_layout.addWidget(vis_group)
        
        # 버튼
        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        main_layout.addWidget(self.buttons)

        # 초기값 로드 (첫 번째 아이템 기준)
        self.on_satellite_changed(self.cb_sat_name.currentText())
    
    def on_satellite_changed(self, sat_name):
        """위성 이름 변경 시, 미리 정의된 값으로 자동 설정"""
        if sat_name in self.SAT_PRESETS:
            p = self.SAT_PRESETS[sat_name]
            # Physics
            self.ds_frequency.setValue(p.get("frequency", 0.437))
            self.ds_antenna_gain.setValue(p.get("antenna_gain", 0.0))
            self.ds_transmit_power.setValue(p.get("transmit_power", 30.0))
            # Visualization
            self.ds_sat_size.setValue(p.get("sat_size", 10.0))
            self.ds_sat_speed.setValue(p.get("sat_speed", 0.05))
            self.ds_orbital_radius.setValue(p.get("orbital_radius", 400.0))
            self.ds_inclination.setValue(p.get("inclination", 45.0))
            self.ds_eccentricity.setValue(p.get("eccentricity", 0.0))

    def getParameters(self):
        return {
            # Physics Parameters
            "sat_name": self.cb_sat_name.currentText(),
            "sat_type": self.cb_sat_name.currentText(), # 호환성 유지
            "frequency": self.ds_frequency.value(),
            "antenna_gain": self.ds_antenna_gain.value(),
            "transmit_power": self.ds_transmit_power.value(),
            
            # Visualization Parameters
            "sat_size": self.ds_sat_size.value(),
            "sat_speed": self.ds_sat_speed.value(),
            "orbital_radius": self.ds_orbital_radius.value(),
            "inclination": self.ds_inclination.value(),
            "eccentricity": self.ds_eccentricity.value()
        }
    
    def setParameters(self, params):
        # 저장된 설정이 있으면 불러오되, 없으면 기본값 유지
        sat_name = params.get("sat_name", "ISS")
        self.cb_sat_name.setCurrentText(sat_name)
        
        # 개별 파라미터가 있으면 덮어씌움 (사용자가 커스텀하게 수정한 경우)
        if "frequency" in params: self.ds_frequency.setValue(params["frequency"])
        if "orbital_radius" in params: self.ds_orbital_radius.setValue(params["orbital_radius"])
        if "inclination" in params: self.ds_inclination.setValue(params["inclination"])
        # 나머지 파라미터들도 필요시 추가 가능
