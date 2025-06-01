#!/usr/bin/env python3
import sys
import os
import shlex
import subprocess
import signal
import pathlib # pathlib 임포트 유지
from datetime import datetime, timezone
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QSettings
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QMessageBox, QWidget, QHBoxLayout,
    QVBoxLayout, QGroupBox, QFormLayout, QLabel, QPushButton,
    QComboBox, QSpinBox, QTextEdit, QDialog
)
# OpenGL 직접 사용부는 EarthSatelliteView로 이동했을 가능성이 높음
# from OpenGL.GL import *
# from OpenGL.GLU import *

# 가정: modeling.py, satellite_setting.py, base_station_setting.py 파일이
# GroundSystem.py와 같은 디렉토리에 있거나, Python 경로에 올바르게 설정되어 있음.
from modeling import EarthSatelliteView
from satellite_setting import SatelliteSettingsDialog
from base_station_setting import BaseStationSettingsDialog # 기지국 설정 다이얼로그


# ──────────────────────────────────────────────────────────────────────────────
# CmdProcessReader: subprocess stdout을 QThread로 읽어 와 시그널로 전달
# ──────────────────────────────────────────────────────────────────────────────
class CmdProcessReader(QThread):
    line_received = pyqtSignal(str)

    def __init__(self, process, parent=None):
        super().__init__(parent)
        self.process = process
        self._running = True

    def run(self):
        while self._running:
            line = self.process.stdout.readline()
            if not line:
                break
            self.line_received.emit(line.rstrip("\n"))

    def stop(self):
        self._running = False


# ──────────────────────────────────────────────────────────────────────────────
# GroundSystemLogic: GS 내부 로직
# ──────────────────────────────────────────────────────────────────────────────
class GroundSystemLogic:
    # ★★★ 클래스 변수로 오프셋 상수들 다시 정의 ★★★
    TLM_HDR_V1_OFFSET = 4
    TLM_HDR_V2_OFFSET = 4     # TODO: 실제 V2 오프셋 값으로 확인/수정 필요
    CMD_HDR_PRI_V1_OFFSET = 0
    CMD_HDR_SEC_V1_OFFSET = 0
    CMD_HDR_PRI_V2_OFFSET = 4 # TODO: 실제 V2 오프셋 값으로 확인/수정 필요
    CMD_HDR_SEC_V2_OFFSET = 4 # TODO: 실제 V2 오프셋 값으로 확인/수정 필요

    def __init__(self, rootdir, display_error_callback=None):
        self.ROOTDIR = rootdir # pathlib.Path 객체
        self.display_error_callback = display_error_callback
        
        # 이 인스턴스 변수들은 QSettings와 GUI 위젯에서 주로 관리되므로,
        # 여기서는 초기값 설정이 필수는 아니지만, GroundSystemLogic 내부에서 필요하다면 유지.
        # self.sb_tlm_offset_value = self.TLM_HDR_V1_OFFSET
        # self.sb_cmd_offset_pri_value = self.CMD_HDR_PRI_V1_OFFSET
        # self.sb_cmd_offset_sec_value = self.CMD_HDR_SEC_V1_OFFSET
        
        self.ip_addresses_list = ['All']
        self.spacecraft_names = ['All'] # IP 주소에 매칭되는 위성 이름 (선택적)
        
        self.routing_service = None
        self.cmd_process = None
        self.cmd_process_reader = None
        self.test4_process = None
        self.test4_reader = None

    def display_error_message(self, message: str):
        print(f"[GS_LOGIC_ERROR] {message}")
        if self.display_error_callback:
            self.display_error_callback(message)

    def get_selected_spacecraft_name(self, combo_box_text: str):
        # "이름 (IP)" 형식에서 이름을 추출하거나, IP 주소만 있다면 IP 주소 반환
        # 현재는 ip_addresses_list와 spacecraft_names가 동기화된다고 가정
        try:
            # cb_ips에는 "이름 (IP)" 또는 "IP"가 들어갈 수 있음
            # 단순화를 위해, cb_ips의 텍스트가 ip_addresses_list에 있으면 해당 이름 반환
            if combo_box_text in self.ip_addresses_list:
                 idx = self.ip_addresses_list.index(combo_box_text)
                 # spacecraft_names가 ip_addresses_list와 길이가 같고 순서가 맞다고 가정
                 if idx < len(self.spacecraft_names):
                     return self.spacecraft_names[idx]
            return combo_box_text # 매칭되는 이름 없으면 그냥 텍스트 반환 (All 포함)
        except ValueError:
            return "All" 

    def start_tlm_system(self, selected_spacecraft: str):
        subscription = '--sub=GroundSystem'
        # selected_spacecraft가 'All'이 아니고, 실제 존재하는 이름인지 확인
        if selected_spacecraft != 'All' and selected_spacecraft in self.spacecraft_names:
            subscription += f'.{selected_spacecraft}.TelemetryPackets'
        
        tlm_system_path = self.ROOTDIR / "Subsystems" / "tlmGUI" / "TelemetrySystem.py"
        if not tlm_system_path.is_file():
            self.display_error_message(f"TelemetrySystem.py를 찾을 수 없습니다: {tlm_system_path}")
            return
        args = shlex.split(f'python3 {str(tlm_system_path)} {subscription}')
        try:
            subprocess.Popen(args)
        except Exception as e:
            self.display_error_message(f"Telemetry System 시작 실패: {e}")


    def start_cmd_system(self, on_stdout_callback=None):
        if self.cmd_process and self.cmd_process.poll() is None:
            self.display_error_message("Command System이 이미 실행 중입니다.")
            return
        
        cmd_system_path = self.ROOTDIR / "Subsystems" / "cmdGui" / "CommandSystem.py"
        if not cmd_system_path.is_file():
            self.display_error_message(f"CommandSystem.py를 찾을 수 없습니다: {cmd_system_path}")
            return

        cmd = ['python3', '-u', str(cmd_system_path)]
        try:
            self.cmd_process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            self.cmd_process_reader = CmdProcessReader(self.cmd_process)
            if on_stdout_callback:
                self.cmd_process_reader.line_received.connect(on_stdout_callback)
            self.cmd_process_reader.start()
        except Exception as e:
            self.display_error_message(f"Command System 시작 실패: {e}")


    def stop_cmd_system(self):
        if self.cmd_process and self.cmd_process.poll() is None:
            try: self.cmd_process.terminate()
            except Exception as e: print(f"[ERROR] Terminating cmd_process: {e}")
        if self.cmd_process_reader:
            try:
                self.cmd_process_reader.stop()
                self.cmd_process_reader.quit()
                self.cmd_process_reader.wait(1000) # 1초 타임아웃
            except Exception as e: print(f"[ERROR] Stopping cmd_process_reader: {e}")

    def start_test4(self, on_stdout_callback=None):
        if self.test4_process and self.test4_process.poll() is None:
            return # 이미 실행 중

        test4_path = self.ROOTDIR / "test4.py" # test4.py가 ROOTDIR (newGS)에 있다고 가정
        if not test4_path.is_file():
            self.display_error_message(f"test4.py를 찾을 수 없습니다: {test4_path}")
            return
        
        cmd = ['python3', '-u', str(test4_path)]
        try:
            self.test4_process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            self.test4_reader = CmdProcessReader(self.test4_process)
            if on_stdout_callback:
                self.test4_reader.line_received.connect(on_stdout_callback)
            self.test4_reader.start()
        except Exception as e:
            self.display_error_message(f"test4.py 시작 실패: {e}")

    def stop_test4(self):
        if self.test4_process and self.test4_process.poll() is None:
            try: self.test4_process.terminate()
            except Exception as e: print(f"[ERROR] Terminating test4_process: {e}")
        if self.test4_reader:
            try:
                self.test4_reader.stop()
                self.test4_reader.quit()
                self.test4_reader.wait(1000) # 1초 타임아웃
            except Exception as e: print(f"[ERROR] Stopping test4_reader: {e}")
            
    def update_ip_list(self, ip, name):
        # 중복 방지하며 리스트 업데이트
        is_new_ip = True
        for i, existing_ip in enumerate(self.ip_addresses_list):
            if existing_ip == ip: # 이미 있는 IP면 이름만 업데이트 고려
                if i < len(self.spacecraft_names) and self.spacecraft_names[i] != name:
                    self.spacecraft_names[i] = name # 이름 업데이트
                is_new_ip = False
                break
        if is_new_ip:
            self.ip_addresses_list.append(ip)
            self.spacecraft_names.append(name)


    def init_routing_service(self, routing_service=None):
        try:
            from RoutingService import RoutingService # 동적 임포트
            self.routing_service = routing_service or RoutingService()
            self.routing_service.signal_update_ip_list.connect(self.update_ip_list) # GUI의 메소드 대신 Logic의 메소드 연결
            self.routing_service.start()
            print("[SYSTEM] RoutingService started.")
        except ImportError:
            self.display_error_message("RoutingService.py를 찾을 수 없습니다. IP 목록이 동적으로 업데이트되지 않습니다.")
        except Exception as e:
            self.display_error_message(f"RoutingService 초기화 중 오류: {e}")


# ──────────────────────────────────────────────────────────────────────────────
# NextGenGroundSystem: 메인 윈도우
# ──────────────────────────────────────────────────────────────────────────────
class NextGenGroundSystem(QMainWindow):
    DEFAULT_TLM_HDR_VER = "1" # QSettings 기본값용
    DEFAULT_CMD_HDR_VER = "1" # QSettings 기본값용
    
    # GroundSystemLogic에 정의된 클래스 변수를 사용하여 기본 오프셋 값 설정
    DEFAULT_TLM_OFFSET = GroundSystemLogic.TLM_HDR_V1_OFFSET 
    DEFAULT_CMD_OFFSET_PRI = GroundSystemLogic.CMD_HDR_PRI_V1_OFFSET
    DEFAULT_CMD_OFFSET_SEC = GroundSystemLogic.CMD_HDR_SEC_V1_OFFSET

    def __init__(self):
        super().__init__()
        self.setWindowTitle("차세대 위성통신 보안 시뮬레이터 (GroundSystem)")
        self.resize(1250, 850) # 창 크기 조정

        # QSettings: 회사명, 애플리케이션명으로 설정 저장 경로 결정
        QApplication.setOrganizationName("MySatComProject")
        QApplication.setApplicationName("GroundSystemGUI")
        self.settings = QSettings() # 기본 생성자로 사용 가능

        # ROOTDIR: 이 GUI 파일이 있는 디렉토리
        # 리소스 파일(3D 모델, 텍스처 등) 및 다른 스크립트(test4.py 등) 경로의 기준점.
        # 만약 이 파일이 프로젝트 루트의 하위 폴더(예: newGS/)에 있다면,
        # self.ROOTDIR = pathlib.Path(__file__).resolve().parent 와 같이 사용합니다.
        # 현재는 GroundSystem.py가 newGS 폴더에 있다고 가정.
        self.ROOTDIR  = pathlib.Path(__file__).resolve().parent 
        self.gs_logic = GroundSystemLogic(self.ROOTDIR, self.show_error_message_box) # 에러 메시지 콜백 전달
        self.attack_file_path = self.ROOTDIR / "attack_mode.txt"

        self._init_ui()      # UI 요소 생성 및 배치
        self._load_settings()  # 저장된 설정 로드 (UI 요소 값 설정 포함)
        
        self.gs_logic.init_routing_service() # RoutingService 시작 (gs_logic 통해)
        self.gs_logic.start_test4(on_stdout_callback=self.append_terminal_output) # test4 자동 시작
        
        self._initialize_attack_file() # attack_mode.txt 파일 초기화
        self._update_attack_ui_from_file() # 파일 내용으로 공격 UI 초기 상태 설정

    def _init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        h_layout = QHBoxLayout(main_widget)

        # --- Left Panel (3D View and Settings Buttons) ---
        left_panel  = QWidget(); left_layout = QVBoxLayout(left_panel)
        # 3D 모델 및 텍스처 경로: self.ROOTDIR 기준으로 설정
        # 실제 파일 위치에 맞게 경로 확인 및 수정 필요
        earth_model_path = self.ROOTDIR / "textures" / "earth.glb" 
        earth_texture_path = self.ROOTDIR / "textures" / "image_0.png"
        bg_image_path = self.ROOTDIR / "textures" / "background.jpg"
        sat_model_path = self.ROOTDIR / "textures" / "satellite.glb"
        
        # EarthSatelliteView가 해당 파일들을 찾을 수 있도록 경로 확인 필요
        self.earth_view = EarthSatelliteView(
            model_path=str(earth_model_path), texture_path=str(earth_texture_path),
            bg_image_path=str(bg_image_path), sat_model_path=str(sat_model_path), parent=self
        )
        left_layout.addWidget(self.earth_view, stretch=4)

        button_layout = QHBoxLayout()
        buttons_to_add = [
            ("기지국 설정", self.openBaseStationSettings),
            ("위성 설정", self.openSatelliteSettings),
            ("통신 설정", self.openCommSettings) 
        ]
        for name, callback in buttons_to_add:
            b = QPushButton(name); b.clicked.connect(callback); button_layout.addWidget(b)
        left_layout.addLayout(button_layout)
        h_layout.addWidget(left_panel, stretch=5)

        # --- Right Panel (Log Output and Control Box) ---
        right_panel = QWidget(); right_layout = QVBoxLayout(right_panel)
        self.log_output = QTextEdit(); self.log_output.setReadOnly(True)
        right_layout.addWidget(self.log_output, stretch=3)

        control_box = QGroupBox("제어 / 공격 시뮬레이션"); control_layout = QVBoxLayout(control_box)
        form_layout = QFormLayout()
        # TLM Header
        self.cb_tlm_header = QComboBox(); self.cb_tlm_header.addItems(["1", "2", "Custom"])
        self.cb_tlm_header.currentTextChanged.connect(self.on_tlm_header_changed)
        form_layout.addRow("TLM Header Ver:", self.cb_tlm_header)
        self.sb_tlm_offset = QSpinBox(); self.sb_tlm_offset.setRange(0, 64)
        self.sb_tlm_offset.valueChanged.connect(self.on_tlm_offset_changed)
        form_layout.addRow("TLM Offset:", self.sb_tlm_offset)
        # CMD Header
        self.cb_cmd_header = QComboBox(); self.cb_cmd_header.addItems(["1", "2", "Custom"])
        self.cb_cmd_header.currentTextChanged.connect(self.on_cmd_header_changed)
        form_layout.addRow("CMD Header Ver:", self.cb_cmd_header)
        self.sb_cmd_pri = QSpinBox(); self.sb_cmd_pri.setRange(0, 64)
        self.sb_cmd_pri.valueChanged.connect(self.on_cmd_offset_pri_changed)
        form_layout.addRow("CMD Offset PRI:", self.sb_cmd_pri)
        self.sb_cmd_sec = QSpinBox(); self.sb_cmd_sec.setRange(0, 64)
        self.sb_cmd_sec.valueChanged.connect(self.on_cmd_offset_sec_changed)
        form_layout.addRow("CMD Offset SEC:", self.sb_cmd_sec)
        control_layout.addLayout(form_layout)

        control_layout.addWidget(QLabel("대상 IP 선택:"))
        self.cb_ips = QComboBox(); self.cb_ips.addItem("All")
        # RoutingService에서 업데이트된 IP 목록을 gs_logic을 통해 가져와 채우기
        if len(self.gs_logic.ip_addresses_list) > 1: # "All" 외에 다른 IP가 있다면
            for i, ip_addr in enumerate(self.gs_logic.ip_addresses_list):
                if ip_addr == "All": continue # 중복 방지
                name = self.gs_logic.spacecraft_names[i] if i < len(self.gs_logic.spacecraft_names) else ip_addr
                self.cb_ips.addItem(f"{name} ({ip_addr})", ip_addr) # 표시 텍스트와 데이터 분리

        control_layout.addWidget(self.cb_ips)

        sys_ctrl_btn_layout = QHBoxLayout()
        for label, handler in [("Start Telemetry", self.on_start_tlm), ("Start Command", self.on_start_cmd), ("로그 초기화", self.clear_cmd_log)]:
            b = QPushButton(label); b.clicked.connect(handler); sys_ctrl_btn_layout.addWidget(b)
        control_layout.addLayout(sys_ctrl_btn_layout)
        
        control_layout.addWidget(QLabel("공격 유형 선택:"))
        self.attack_combo = QComboBox()
        self.attack_modes_kor_to_eng = {"없음": "none", "재밍": "jamming", "변조": "modify", "드랍": "drop", "노이즈": "noise"}
        self.attack_combo.addItems(self.attack_modes_kor_to_eng.keys())
        self.attack_combo.currentTextChanged.connect(self._update_attack_button_state_on_combo_change) # 핸들러 이름 변경
        control_layout.addWidget(self.attack_combo)

        self.attack_button = QPushButton("공격 시작"); self.attack_button.setCheckable(True)
        self.attack_button.clicked.connect(self.toggle_attack_mode)
        control_layout.addWidget(self.attack_button)
        
        control_layout.addStretch()
        right_layout.addWidget(control_box, stretch=2)
        h_layout.addWidget(right_panel, stretch=3)

    def _initialize_attack_file(self):
        if not self.attack_file_path.exists():
            try:
                with open(self.attack_file_path, "w", encoding="utf-8") as f:
                    f.write("none")
                self.append_terminal_output(f"[시스템] '{self.attack_file_path}' 생성 및 'none'으로 초기화.")
            except Exception as e:
                self.append_terminal_output(f"[오류] attack_mode.txt 생성 실패: {e}")

    def _update_attack_ui_from_file(self):
        """ attack_mode.txt 파일 내용을 읽어 UI 상태를 업데이트합니다. """
        current_mode_eng = "none"
        if self.attack_file_path.exists():
            try:
                with open(self.attack_file_path, "r", encoding="utf-8") as f:
                    current_mode_eng = f.read().strip().lower()
            except Exception as e:
                self.append_terminal_output(f"[오류] attack_mode.txt 읽기 실패: {e}")
        
        mode_eng_to_kor = {v: k for k, v in self.attack_modes_kor_to_eng.items()}
        current_mode_kor = mode_eng_to_kor.get(current_mode_eng, "없음")
        
        self.attack_combo.setCurrentText(current_mode_kor) # 파일 내용에 따라 콤보박스 설정
        
        is_attacking = (current_mode_eng != "none")
        self.attack_button.setChecked(is_attacking) # 버튼 체크 상태 설정
        self.attack_button.setText("공격 중지" if is_attacking else "공격 시작")
        self.attack_combo.setEnabled(not is_attacking) # 콤보박스 활성화/비활성화
        self.attack_button.setEnabled(current_mode_kor != "없음" or is_attacking) # "없음"일때 시작 못하게, 중지는 가능하게


    def _load_settings(self):
        self.append_terminal_output("[시스템] 저장된 설정 로드 시도...")
        # 위성 파라미터
        default_sat_params = getattr(self.earth_view, 'DEFAULT_PARAMS', {
            "sat_type": "소형 위성", "sat_size": 10.0, "sat_speed": 0.05, 
            "orbital_radius": 300.0, "inclination": 45.0, "eccentricity": 0.0,
            "frequency": 2.4, "antenna_gain": 10.0, "transmit_power": 0.0
        })
        sat_params = self.settings.value("satellite/params", defaultValue=default_sat_params, type=dict)
        if sat_params: self.earth_view.updateSatelliteParameters(**sat_params)
        
        # 기지국 파라미터 (BaseStationSettingsDialog의 기본값과 유사하게)
        default_gs_params = {
            "gs_name": "Default GS", "gs_latitude": 36.350413, "gs_longitude": 127.384548, 
            "gs_altitude": 50.0, "min_elevation": 5.0, "gs_antenna_gain": 35.0
        }
        gs_params = self.settings.value("basestation/params", defaultValue=default_gs_params, type=dict)
        if gs_params and hasattr(self.earth_view, 'updateBaseStationMarker'):
             self.earth_view.updateBaseStationMarker(gs_params['gs_latitude'], gs_params['gs_longitude'], gs_params['gs_name'])

        # 헤더/오프셋
        self.cb_tlm_header.setCurrentText(self.settings.value("offsets/tlm_ver", self.DEFAULT_TLM_HDR_VER, type=str))
        self.sb_tlm_offset.setValue(self.settings.value("offsets/tlm_offset", self.DEFAULT_TLM_OFFSET, type=int))
        self.cb_cmd_header.setCurrentText(self.settings.value("offsets/cmd_ver", self.DEFAULT_CMD_HDR_VER, type=str))
        self.sb_cmd_pri.setValue(self.settings.value("offsets/cmd_pri", self.DEFAULT_CMD_OFFSET_PRI, type=int))
        self.sb_cmd_sec.setValue(self.settings.value("offsets/cmd_sec", self.DEFAULT_CMD_OFFSET_SEC, type=int))
        self.on_tlm_header_changed(self.cb_tlm_header.currentText()) # 스핀박스 활성화 상태 반영
        self.on_cmd_header_changed(self.cb_cmd_header.currentText()) # 스핀박스 활성화 상태 반영
        self.append_terminal_output("[시스템] 설정 로드 완료.")


    def _save_settings(self):
        self.settings.setValue("offsets/tlm_ver", self.cb_tlm_header.currentText())
        self.settings.setValue("offsets/tlm_offset", self.sb_tlm_offset.value())
        self.settings.setValue("offsets/cmd_ver", self.cb_cmd_header.currentText())
        self.settings.setValue("offsets/cmd_pri", self.sb_cmd_pri.value())
        self.settings.setValue("offsets/cmd_sec", self.sb_cmd_sec.value())
        # 위성/기지국 파라미터는 각 다이얼로그에서 OK 시 저장됨
        self.append_terminal_output("[시스템] 현재 설정 저장됨.")

    def _update_attack_button_state_on_combo_change(self, selected_text_kor): # 콤보 변경 시 호출
        """공격 콤보박스 선택 변경 시 버튼 상태 업데이트 (공격이 토글된 상태가 아닐 때만)"""
        if not self.attack_button.isChecked(): # 공격이 "시작"된 상태가 아닐 때만
            self.attack_button.setEnabled(selected_text_kor != "없음")

    def toggle_attack_mode(self): # 버튼 클릭 시 호출
        is_checked_for_attack_start = self.attack_button.isChecked() # 현재 버튼이 눌려서 체크된 상태인지
        selected_kor = self.attack_combo.currentText()

        if is_checked_for_attack_start and selected_kor == "없음":
            self.append_terminal_output("[공격] '없음'은 공격 유형이 아닙니다. 다른 유형을 선택 후 시작하세요.")
            self.attack_button.setChecked(False) # 강제 해제
            return

        selected_mode_eng = self.attack_modes_kor_to_eng.get(selected_kor, "none") if is_checked_for_attack_start else "none"

        try:
            with open(self.attack_file_path, "w", encoding="utf-8") as f:
                f.write(selected_mode_eng)
            self.append_terminal_output(f"[공격] attack_mode.txt에 '{selected_mode_eng}' 모드 저장됨.")
        except Exception as e:
            self.append_terminal_output(f"[공격] attack_mode.txt 저장 실패: {e}")
            self.attack_button.setChecked(not is_checked_for_attack_start) # 실패 시 버튼 상태 원복
            return

        self.attack_button.setText("공격 중지" if is_checked_for_attack_start else "공격 시작")
        self.attack_combo.setEnabled(not is_checked_for_attack_start) # 공격 중이면 콤보박스 비활성화
        
        log_msg = f"[공격] {selected_kor} ({selected_mode_eng}) 모드 적용됨." if selected_mode_eng != "none" \
                  else "[공격] 모든 공격 중지됨 (none 모드)."
        self.append_terminal_output(log_msg)

    def openBaseStationSettings(self):
        dlg = BaseStationSettingsDialog(self)
        default_params = {"gs_name": "Default GS", "gs_latitude": 37.5665, "gs_longitude": 126.9780, 
                          "gs_altitude": 30.0, "min_elevation": 5.0, "gs_antenna_gain": 35.0}
        params = self.settings.value("basestation/params", defaultValue=default_params, type=dict)
        dlg.setParameters(params)

        if dlg.exec_() == QDialog.Accepted:
            new_params = dlg.getParameters()
            self.settings.setValue("basestation/params", new_params)
            self.append_terminal_output(f"[시스템] 기지국 '{new_params['gs_name']}' 파라미터 저장됨.")
            if hasattr(self.earth_view, 'updateBaseStationMarker'):
                 self.earth_view.updateBaseStationMarker(new_params['gs_latitude'], new_params['gs_longitude'], new_params['gs_name'])
            # TODO: 변경된 기지국 파라미터를 시뮬레이션 로직에 반영하는 부분 추가 필요

    def openSatelliteSettings(self):
        dlg = SatelliteSettingsDialog(self)
        default_params = getattr(self.earth_view, 'DEFAULT_PARAMS', {
            "sat_type": "소형 위성", "sat_size": 10.0, "sat_speed": 0.05, 
            "orbital_radius": 300.0, "inclination": 45.0, "eccentricity": 0.0,
            "frequency": 2.4, "antenna_gain": 10.0, "transmit_power": 0.0
        })
        params = self.settings.value("satellite/params", defaultValue=default_params, type=dict)
        
        # SatelliteSettingsDialog에 setParameters 와 같은 메소드가 있다고 가정
        if hasattr(dlg, 'setParameters'):
            dlg.setParameters(params) 
        else: # 없다면 개별적으로 설정
            dlg.cb_sat_type.setCurrentText(params.get('sat_type', default_params['sat_type']))
            dlg.ds_sat_size.setValue(params.get('sat_size', default_params['sat_size']))
            # ... (나머지 파라미터들도 위와 같이 params.get()으로 설정) ...
            dlg.ds_sat_speed.setValue(params.get('sat_speed', default_params['sat_speed']))
            dlg.ds_orbital_radius.setValue(params.get('orbital_radius', default_params['orbital_radius']))
            dlg.ds_inclination.setValue(params.get('inclination', default_params['inclination']))
            dlg.ds_eccentricity.setValue(params.get('eccentricity', default_params['eccentricity']))
            dlg.ds_frequency.setValue(params.get('frequency', default_params['frequency']))
            dlg.ds_antenna_gain.setValue(params.get('antenna_gain', default_params['antenna_gain']))
            dlg.ds_transmit_power.setValue(params.get('transmit_power', default_params['transmit_power']))


        if dlg.exec_() == QDialog.Accepted:
            new_sat_params = dlg.getParameters()
            self.earth_view.updateSatelliteParameters(**new_sat_params)
            self.settings.setValue("satellite/params", new_sat_params)
            self.append_terminal_output(f"[시스템] 위성 '{new_sat_params['sat_type']}' 파라미터 저장됨.")
            # TODO: 변경된 위성 파라미터를 시뮬레이션 로직에 반영하는 부분 추가 필요

    def openCommSettings(self):
        QMessageBox.information(self, "통신 설정", "이곳에서 향후 채널 모델 (경로 손실, SNR 등) 및 링크 파라미터를 설정할 수 있습니다.")

    def clear_cmd_log(self): 
        self.log_output.clear(); self.append_terminal_output("[시스템] 로그가 초기화되었습니다.")

    def show_error_message_box(self, msg): # GroundSystemLogic 콜백용
        QMessageBox.critical(self, "오류 발생", msg)

    def append_terminal_output(self, msg: str):
        prefix_color_map = {"[시스템]": "blue", "[공격]": "red", "[CMD]": "green", 
                            "[INFO]": "gray", "[WARN]": "orange", "[ERROR]": "magenta",
                            "[GS_LOGIC_ERROR]": "purple"} # 추가된 에러 타입
        chosen_color = "black"
        for prefix, color in prefix_color_map.items():
            if msg.startswith(prefix): chosen_color = color; break
        
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        self.log_output.append(f"<font color='{chosen_color}'>[{timestamp}] {msg}</font>")
        self.log_output.ensureCursorVisible() # 새 로그 추가 시 자동 스크롤


    def on_start_tlm(self):
        # cb_ips에서 선택된 아이템의 사용자 데이터(IP 주소)를 가져오거나, 텍스트 파싱
        # current_ip_data = self.cb_ips.currentData() # addItem 시 userData를 IP로 저장했다면
        current_ip_text = self.cb_ips.currentText() # "이름 (IP)" 또는 "All"
        selected_sc_name = "All" # 기본값
        if current_ip_text != "All":
            # "이름 (IP)" 형식에서 이름을 추출하거나, IP를 이름으로 사용
            # 여기서는 gs_logic에 등록된 spacecraft_names를 사용하도록 함
            # 실제로는 cb_ips.currentData()에 IP를 저장하고, 표시 텍스트와 분리하는 것이 좋음
            selected_sc_name = self.gs_logic.get_selected_spacecraft_name(current_ip_text)


        self.gs_logic.start_tlm_system(selected_sc_name) # gs_logic의 메소드는 이름만 받음
        self.append_terminal_output(f"[시스템] Telemetry System ({selected_sc_name}) 시작 요청됨.")

    def on_start_cmd(self):
        def handler(line): self.append_terminal_output(f"[CMD] {line}")
        self.gs_logic.start_cmd_system(on_stdout_callback=handler)
        self.append_terminal_output("[시스템] Command System 시작 요청됨.")

    def on_tlm_header_changed(self, txt):
        val = self.DEFAULT_TLM_OFFSET # 기본값은 V1 오프셋
        if txt == '1': val = GroundSystemLogic.TLM_HDR_V1_OFFSET
        elif txt == '2': val = GroundSystemLogic.TLM_HDR_V2_OFFSET
        else: # Custom
            val = self.sb_tlm_offset.value() # Custom이면 현재 스핀박스 값 유지 또는 사용자가 직접 입력
        
        self.sb_tlm_offset.setValue(val) # 스핀박스 값 업데이트
        self.sb_tlm_offset.setEnabled(txt == "Custom")
        self._save_settings() 

    def on_tlm_offset_changed(self, v): # 스핀박스 직접 조작 시
        if self.cb_tlm_header.currentText() == "Custom": self._save_settings()

    def on_cmd_header_changed(self, txt):
        pri_val = self.DEFAULT_CMD_OFFSET_PRI; sec_val = self.DEFAULT_CMD_OFFSET_SEC
        if txt == '1':
            pri_val = GroundSystemLogic.CMD_HDR_PRI_V1_OFFSET
            sec_val = GroundSystemLogic.CMD_HDR_SEC_V1_OFFSET
        elif txt == '2':
            pri_val = GroundSystemLogic.CMD_HDR_PRI_V2_OFFSET
            sec_val = GroundSystemLogic.CMD_HDR_SEC_V2_OFFSET
        else: # Custom
            pri_val = self.sb_cmd_pri.value()
            sec_val = self.sb_cmd_sec.value()
            
        self.sb_cmd_pri.setValue(pri_val)
        self.sb_cmd_sec.setValue(sec_val)
        self.sb_cmd_pri.setEnabled(txt == "Custom")
        self.sb_cmd_sec.setEnabled(txt == "Custom")
        self._save_settings()

    def on_cmd_offset_pri_changed(self, v):
        if self.cb_cmd_header.currentText() == "Custom": self._save_settings()

    def on_cmd_offset_sec_changed(self, v):
        if self.cb_cmd_header.currentText() == "Custom": self._save_settings()

    def on_ip_list_updated(self, ip, name):
        # RoutingService로부터 받은 IP와 이름을 cb_ips 콤보박스에 추가
        # gs_logic.update_ip_list는 이미 호출되었다고 가정 (시그널 연결로)
        # UI 업데이트: 중복 방지 및 표시 형식
        # cb_ips의 아이템 형식: "이름 (IP)" , userData: IP
        found = False
        for i in range(self.cb_ips.count()):
            if self.cb_ips.itemData(i) == ip: # userData로 IP 비교
                # 이미 있으면 이름만 업데이트 필요 시 (선택적)
                # self.cb_ips.setItemText(i, f"{name} ({ip})")
                found = True; break
        if not found:
            self.cb_ips.addItem(f"{name} ({ip})", userData=ip) # userData에 IP 저장
        self.append_terminal_output(f"[시스템] IP 목록 업데이트: {name} ({ip})")


    def init_routing_service(self): # gs_logic을 통해 호출
        self.gs_logic.init_routing_service()
        if self.gs_logic.routing_service:
             self.gs_logic.routing_service.signal_update_ip_list.connect(self.on_ip_list_updated)


    def closeEvent(self, event):
        self.append_terminal_output("[시스템] 종료 중... 모든 설정을 저장합니다.")
        self._save_settings() 
        
        self.gs_logic.stop_cmd_system()
        self.gs_logic.stop_test4()
        if self.gs_logic.routing_service and hasattr(self.gs_logic.routing_service, 'stop'):
            self.gs_logic.routing_service.stop()
        
        print("[시스템] 모든 관련 프로세스 종료 시도 완료. GUI를 닫습니다.")
        super().closeEvent(event)
        
    # on_attack_combo_changed는 _update_attack_button_state_on_combo_change로 대체됨

def main():
    # _version.py 파일이 프로젝트 내에 존재하고, __version__, _version_string 변수를 정의해야 함.
    try:
        from _version import __version__, _version_string
        print(_version_string)
    except ImportError:
        print("Version information (_version.py) not found.")
    
    app = QApplication(sys.argv)
    window = NextGenGroundSystem()
    window.show()
    window.raise_()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
