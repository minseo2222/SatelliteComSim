#!/usr/bin/env python3
import sys
import os
import shlex
import subprocess
import signal
import pathlib
import json
import socket
from datetime import datetime, timezone
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QSettings
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QMessageBox, QWidget, QHBoxLayout,
    QVBoxLayout, QGroupBox, QFormLayout, QLabel, QPushButton,
    QComboBox, QSpinBox, QTextEdit, QDialog
)

from modeling import EarthSatelliteView
from satellite_setting import SatelliteSettingsDialog
from base_station_setting import BaseStationSettingsDialog
from comm_setting import CommSettingsDialog

class CmdProcessReader(QThread):
    line_received = pyqtSignal(str)
    def __init__(self, process, parent=None):
        super().__init__(parent)
        self.process = process
        self._running = True
    def run(self):
        while self._running:
            if self.process.stdout:
                line = self.process.stdout.readline()
                if not line: break
                self.line_received.emit(line.rstrip("\n"))
    def stop(self): self._running = False

class GroundSystemLogic:
    TLM_HDR_V1_OFFSET = 4
    TLM_HDR_V2_OFFSET = 4
    CMD_HDR_PRI_V1_OFFSET = 0
    CMD_HDR_SEC_V1_OFFSET = 0
    CMD_HDR_PRI_V2_OFFSET = 4
    CMD_HDR_SEC_V2_OFFSET = 4

    def __init__(self, rootdir, display_error_callback=None):
        self.ROOTDIR = rootdir
        self.display_error_callback = display_error_callback
        self.ip_addresses_list = ['All']
        self.spacecraft_names = ['All']
        self.routing_service = None
        self.cmd_process = None
        self.cmd_process_reader = None

    def display_error_message(self, message: str):
        print(f"[GS_LOGIC_ERROR] {message}")
        if self.display_error_callback: self.display_error_callback(message)

    def get_selected_spacecraft_name(self, combo_box_text: str):
        try:
            if combo_box_text in self.ip_addresses_list:
                idx = self.ip_addresses_list.index(combo_box_text)
                if idx < len(self.spacecraft_names): return self.spacecraft_names[idx]
            return combo_box_text
        except ValueError: return "All"

    def start_tlm_system(self, selected_spacecraft: str):
        subscription = '--sub=GroundSystem'
        if selected_spacecraft != 'All' and selected_spacecraft in self.spacecraft_names:
            subscription += f'.{selected_spacecraft}.TelemetryPackets'
        tlm_system_path = self.ROOTDIR / "Subsystems" / "tlmGUI" / "TelemetrySystem.py"
        if not tlm_system_path.is_file():
            self.display_error_message(f"TelemetrySystem.py를 찾을 수 없습니다: {tlm_system_path}")
            return
        args = shlex.split(f'python3 {str(tlm_system_path)} {subscription}')
        try: subprocess.Popen(args)
        except Exception as e: self.display_error_message(f"Telemetry System 시작 실패: {e}")

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
            self.cmd_process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            self.cmd_process_reader = CmdProcessReader(self.cmd_process)
            if on_stdout_callback: self.cmd_process_reader.line_received.connect(on_stdout_callback)
            self.cmd_process_reader.start()
        except Exception as e: self.display_error_message(f"Command System 시작 실패: {e}")

    def stop_cmd_system(self):
        if self.cmd_process and self.cmd_process.poll() is None:
            try: self.cmd_process.terminate()
            except: pass
        if self.cmd_process_reader:
            try: self.cmd_process_reader.stop(); self.cmd_process_reader.quit(); self.cmd_process_reader.wait(1000)
            except: pass

    def update_ip_list(self, ip, name):
        is_new_ip = True
        for i, existing_ip in enumerate(self.ip_addresses_list):
            if existing_ip == ip:
                if i < len(self.spacecraft_names) and self.spacecraft_names[i] != name:
                    self.spacecraft_names[i] = name
                is_new_ip = False
                break
        if is_new_ip:
            self.ip_addresses_list.append(ip); self.spacecraft_names.append(name)

    def init_routing_service(self, routing_service=None):
        try:
            from RoutingService import RoutingService
            self.routing_service = routing_service or RoutingService()
            self.routing_service.signal_update_ip_list.connect(self.update_ip_list)
            self.routing_service.start()
            print("[SYSTEM] RoutingService started.")
        except ImportError: self.display_error_message("RoutingService.py를 찾을 수 없습니다.")
        except Exception as e: self.display_error_message(f"RoutingService 초기화 중 오류: {e}")

class NextGenGroundSystem(QMainWindow):
    DEFAULT_TLM_HDR_VER = "1"
    DEFAULT_CMD_HDR_VER = "1"
    DEFAULT_TLM_OFFSET = GroundSystemLogic.TLM_HDR_V1_OFFSET
    DEFAULT_CMD_OFFSET_PRI = GroundSystemLogic.CMD_HDR_PRI_V1_OFFSET
    DEFAULT_CMD_OFFSET_SEC = GroundSystemLogic.CMD_HDR_SEC_V1_OFFSET

    def __init__(self):
        super().__init__()
        self.setWindowTitle("차세대 위성통신 보안 시뮬레이터 (GroundSystem)")
        self.resize(1250, 850)
        QApplication.setOrganizationName("MySatComProject")
        QApplication.setApplicationName("GroundSystemGUI")
        self.settings = QSettings()
        self.ROOTDIR = pathlib.Path(__file__).resolve().parent
        self.gs_logic = GroundSystemLogic(self.ROOTDIR, self.show_error_message_box)
        self.attack_file_path = self.ROOTDIR / "attack_mode.txt"
        self.test2_process = None
        self.TEST2_CTRL_IP = "127.0.0.1"
        self.TEST2_CTRL_PORT = 9696
        self.udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        self._init_ui()
        self._load_settings()
        self.gs_logic.init_routing_service()
        self._initialize_attack_file()
        self._update_attack_ui_from_file()

    def _init_ui(self):
        main_widget = QWidget(); self.setCentralWidget(main_widget)
        h_layout = QHBoxLayout(main_widget)
        left_panel = QWidget(); left_layout = QVBoxLayout(left_panel)
        earth_model_path = self.ROOTDIR / "textures" / "earth.glb"
        earth_texture_path = self.ROOTDIR / "textures" / "image_0.png"
        bg_image_path = self.ROOTDIR / "textures" / "background.jpg"
        sat_model_path = self.ROOTDIR / "textures" / "satellite.glb"
        self.earth_view = EarthSatelliteView(model_path=str(earth_model_path), texture_path=str(earth_texture_path), bg_image_path=str(bg_image_path), sat_model_path=str(sat_model_path), parent=self)
        left_layout.addWidget(self.earth_view, stretch=4)
        button_layout = QHBoxLayout()
        for name, callback in [("기지국 설정", self.openBaseStationSettings), ("위성 설정", self.openSatelliteSettings), ("통신 설정", self.openCommSettings)]:
            b = QPushButton(name); b.clicked.connect(callback); button_layout.addWidget(b)
        left_layout.addLayout(button_layout)
        h_layout.addWidget(left_panel, stretch=5)
        right_panel = QWidget(); right_layout = QVBoxLayout(right_panel)
        self.log_output = QTextEdit(); self.log_output.setReadOnly(True)
        right_layout.addWidget(self.log_output, stretch=3)
        control_box = QGroupBox("제어 / 공격 시뮬레이션"); control_layout = QVBoxLayout(control_box); form_layout = QFormLayout()
        self.cb_tlm_header = QComboBox(); self.cb_tlm_header.addItems(["1", "2", "Custom"]); self.cb_tlm_header.currentTextChanged.connect(self.on_tlm_header_changed)
        form_layout.addRow("TLM Header Ver:", self.cb_tlm_header)
        self.sb_tlm_offset = QSpinBox(); self.sb_tlm_offset.setRange(0, 64); self.sb_tlm_offset.valueChanged.connect(self.on_tlm_offset_changed)
        form_layout.addRow("TLM Offset:", self.sb_tlm_offset)
        self.cb_cmd_header = QComboBox(); self.cb_cmd_header.addItems(["1", "2", "Custom"]); self.cb_cmd_header.currentTextChanged.connect(self.on_cmd_header_changed)
        form_layout.addRow("CMD Header Ver:", self.cb_cmd_header)
        self.sb_cmd_pri = QSpinBox(); self.sb_cmd_pri.setRange(0, 64); self.sb_cmd_pri.valueChanged.connect(self.on_cmd_offset_pri_changed)
        form_layout.addRow("CMD Offset PRI:", self.sb_cmd_pri)
        self.sb_cmd_sec = QSpinBox(); self.sb_cmd_sec.setRange(0, 64); self.sb_cmd_sec.valueChanged.connect(self.on_cmd_offset_sec_changed)
        form_layout.addRow("CMD Offset SEC:", self.sb_cmd_sec)
        control_layout.addLayout(form_layout)
        control_layout.addWidget(QLabel("대상 IP 선택:"))
        self.cb_ips = QComboBox(); self.cb_ips.addItem("All")
        if len(self.gs_logic.ip_addresses_list) > 1:
            for i, ip_addr in enumerate(self.gs_logic.ip_addresses_list):
                if ip_addr == "All": continue
                name = self.gs_logic.spacecraft_names[i] if i < len(self.gs_logic.spacecraft_names) else ip_addr
                self.cb_ips.addItem(f"{name} ({ip_addr})", ip_addr)
        control_layout.addWidget(self.cb_ips)
        sys_ctrl_btn_layout = QHBoxLayout()
        for label, handler in [("Start Telemetry", self.on_start_tlm), ("Start Command", self.on_start_cmd), ("로그 초기화", self.clear_cmd_log)]:
            b = QPushButton(label); b.clicked.connect(handler); sys_ctrl_btn_layout.addWidget(b)
        control_layout.addLayout(sys_ctrl_btn_layout)
        control_layout.addWidget(QLabel("공격 유형 선택:"))
        self.attack_combo = QComboBox()
        self.attack_modes_kor_to_eng = {"없음": "none", "재밍": "jamming", "변조": "modify", "드랍": "drop", "노이즈": "noise"}
        self.attack_combo.addItems(self.attack_modes_kor_to_eng.keys())
        self.attack_combo.currentTextChanged.connect(self._update_attack_button_state_on_combo_change)
        control_layout.addWidget(self.attack_combo)
        self.attack_button = QPushButton("공격 시작"); self.attack_button.setCheckable(True); self.attack_button.clicked.connect(self.toggle_attack_mode)
        control_layout.addWidget(self.attack_button)
        control_layout.addStretch()
        right_layout.addWidget(control_box, stretch=2)
        h_layout.addWidget(right_panel, stretch=3)

    def send_config_to_physics_engine(self, config_data):
        payload = {"cmd": "set", "params": config_data}
        try:
            msg = json.dumps(payload).encode('utf-8')
            self.udp_sock.sendto(msg, (self.TEST2_CTRL_IP, self.TEST2_CTRL_PORT))
            self.append_terminal_output(f"[시스템] 물리 엔진(test2) 설정 저장 및 전송: {config_data}")
        except Exception as e: self.append_terminal_output(f"[오류] 설정 전송 실패: {e}")

    def _initialize_attack_file(self):
        if not self.attack_file_path.exists():
            try:
                with open(self.attack_file_path, "w", encoding="utf-8") as f: f.write("none")
            except: pass

    def _update_attack_ui_from_file(self):
        current_mode_eng = "none"
        if self.attack_file_path.exists():
            try:
                with open(self.attack_file_path, "r", encoding="utf-8") as f: current_mode_eng = f.read().strip().lower()
            except: pass
        mode_eng_to_kor = {v: k for k, v in self.attack_modes_kor_to_eng.items()}
        current_mode_kor = mode_eng_to_kor.get(current_mode_eng, "없음")
        self.attack_combo.setCurrentText(current_mode_kor)
        is_attacking = (current_mode_eng != "none")
        self.attack_button.setChecked(is_attacking)
        self.attack_button.setText("공격 중지" if is_attacking else "공격 시작")
        self.attack_combo.setEnabled(not is_attacking)

    def _load_settings(self):
        default_sat = getattr(self.earth_view, 'DEFAULT_PARAMS', {})
        sat_params = self.settings.value("satellite/params", defaultValue=default_sat, type=dict)
        if sat_params: 
            # load 시에도 시각화용 파라미터만 전달하도록 필터링
            vis_params = sat_params.copy()
            if 'sat_name' in vis_params: del vis_params['sat_name']
            self.earth_view.updateSatelliteParameters(**vis_params)
            
        default_gs = {"gs_name": "Default GS", "gs_latitude": 36.350413, "gs_longitude": 127.384548, "gs_altitude": 50.0, "min_elevation": 5.0, "gs_antenna_gain": 35.0}
        gs_params = self.settings.value("basestation/params", defaultValue=default_gs, type=dict)
        if gs_params and hasattr(self.earth_view, 'updateBaseStationMarker'):
            self.earth_view.updateBaseStationMarker(gs_params['gs_latitude'], gs_params['gs_longitude'], gs_params['gs_name'])
        self.cb_tlm_header.setCurrentText(self.settings.value("offsets/tlm_ver", self.DEFAULT_TLM_HDR_VER, type=str))
        self.sb_tlm_offset.setValue(self.settings.value("offsets/tlm_offset", self.DEFAULT_TLM_OFFSET, type=int))
        self.cb_cmd_header.setCurrentText(self.settings.value("offsets/cmd_ver", self.DEFAULT_CMD_HDR_VER, type=str))
        self.sb_cmd_pri.setValue(self.settings.value("offsets/cmd_pri", self.DEFAULT_CMD_OFFSET_PRI, type=int))
        self.sb_cmd_sec.setValue(self.settings.value("offsets/cmd_sec", self.DEFAULT_CMD_OFFSET_SEC, type=int))

    def _save_settings(self):
        self.settings.setValue("offsets/tlm_ver", self.cb_tlm_header.currentText())
        self.settings.setValue("offsets/tlm_offset", self.sb_tlm_offset.value())
        self.settings.setValue("offsets/cmd_ver", self.cb_cmd_header.currentText())
        self.settings.setValue("offsets/cmd_pri", self.sb_cmd_pri.value())
        self.settings.setValue("offsets/cmd_sec", self.sb_cmd_sec.value())

    def _update_attack_button_state_on_combo_change(self, selected_text_kor):
        if not self.attack_button.isChecked(): self.attack_button.setEnabled(selected_text_kor != "없음")

    def toggle_attack_mode(self):
        is_checked = self.attack_button.isChecked()
        selected_kor = self.attack_combo.currentText()
        if is_checked and selected_kor == "없음":
            self.append_terminal_output("[공격] 유형을 선택하세요.")
            self.attack_button.setChecked(False)
            return
        selected_mode_eng = self.attack_modes_kor_to_eng.get(selected_kor, "none") if is_checked else "none"
        try:
            with open(self.attack_file_path, "w", encoding="utf-8") as f: f.write(selected_mode_eng)
        except Exception as e:
            self.append_terminal_output(f"[공격] 파일 저장 실패: {e}")
            self.attack_button.setChecked(not is_checked)
            return
        self.attack_button.setText("공격 중지" if is_checked else "공격 시작")
        self.attack_combo.setEnabled(not is_checked)
        self.append_terminal_output(f"[공격] 모드 변경: {selected_mode_eng}")

    def openBaseStationSettings(self):
        dlg = BaseStationSettingsDialog(self)
        default_params = {"gs_name": "Default GS", "gs_latitude": 37.5665, "gs_longitude": 126.9780, "gs_altitude": 30.0, "min_elevation": 5.0, "gs_antenna_gain": 35.0}
        params = self.settings.value("basestation/params", defaultValue=default_params, type=dict)
        dlg.setParameters(params)
        if dlg.exec_() == QDialog.Accepted:
            new_params = dlg.getParameters()
            self.settings.setValue("basestation/params", new_params)
            self.append_terminal_output(f"[시스템] 기지국 '{new_params['gs_name']}' 설정 저장 및 전송.")
            if hasattr(self.earth_view, 'updateBaseStationMarker'):
                self.earth_view.updateBaseStationMarker(new_params['gs_latitude'], new_params['gs_longitude'], new_params['gs_name'])
            self.send_config_to_physics_engine(new_params)

    def openSatelliteSettings(self):
        dlg = SatelliteSettingsDialog(self)
        default_params = getattr(self.earth_view, 'DEFAULT_PARAMS', {})
        params = self.settings.value("satellite/params", defaultValue=default_params, type=dict)
        if hasattr(dlg, 'setParameters'): dlg.setParameters(params)
        
        if dlg.exec_() == QDialog.Accepted:
            new_sat_params = dlg.getParameters()
            
            # [수정] 시각화(modeling.py) 업데이트 시 'sat_name' 제거
            vis_params = new_sat_params.copy()
            if 'sat_name' in vis_params: del vis_params['sat_name']
            
            self.earth_view.updateSatelliteParameters(**vis_params)
            self.settings.setValue("satellite/params", new_sat_params)
            self.append_terminal_output(f"[시스템] 위성 '{new_sat_params.get('sat_name','Unknown')}' 설정 저장 및 전송.")
            
            # Physics 업데이트용 데이터
            phy_params = {
                "sat_name": new_sat_params.get("sat_name", "ISS"),
                "frequency": new_sat_params.get("frequency", 2.4) * 1e9, # GHz -> Hz
                "antenna_gain": new_sat_params.get("antenna_gain", 0.0),
                "transmit_power": new_sat_params.get("transmit_power", 30.0)
            }
            self.send_config_to_physics_engine(phy_params)

    def openCommSettings(self):
        default_comm = {"listen_port":8600, "dst_port":1234, "mtu":1472}
        comm_params = self.settings.value("comm/params", defaultValue=default_comm, type=dict)
        dlg = CommSettingsDialog(self, defaults=comm_params)
        if dlg.exec_() == QDialog.Accepted:
            new_params = dlg.get()
            self.settings.setValue("comm/params", new_params)
            cfg_path = self.ROOTDIR / "test2_config.json"
            try:
                with open(cfg_path, "w", encoding="utf-8") as f: json.dump(new_params, f, ensure_ascii=False, indent=2)
            except: pass
            # 로그 용어 통일
            self.append_terminal_output("[시스템] 통신 설정 저장 및 전송.")
            self.send_config_to_physics_engine(new_params)

    def clear_cmd_log(self): self.log_output.clear()
    def show_error_message_box(self, msg): QMessageBox.critical(self, "오류", msg)
    def append_terminal_output(self, msg: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_output.append(f"[{timestamp}] {msg}")
        self.log_output.ensureCursorVisible()
    def on_start_tlm(self):
        sc = self.cb_ips.currentText()
        if sc != "All": sc = self.gs_logic.get_selected_spacecraft_name(sc)
        self.gs_logic.start_tlm_system(sc)
    def on_start_cmd(self):
        self.gs_logic.start_cmd_system(lambda l: self.append_terminal_output(f"[CMD] {l}"))
    def on_tlm_header_changed(self, txt):
        self.sb_tlm_offset.setEnabled(txt == "Custom")
        self._save_settings()
    def on_tlm_offset_changed(self, v): self._save_settings()
    def on_cmd_header_changed(self, txt):
        en = (txt == "Custom")
        self.sb_cmd_pri.setEnabled(en); self.sb_cmd_sec.setEnabled(en)
        self._save_settings()
    def on_cmd_offset_pri_changed(self, v): self._save_settings()
    def on_cmd_offset_sec_changed(self, v): self._save_settings()
    def on_ip_list_updated(self, ip, name):
        for i in range(self.cb_ips.count()):
            if self.cb_ips.itemData(i) == ip: return
        self.cb_ips.addItem(f"{name} ({ip})", userData=ip)
    def closeEvent(self, event):
        self._save_settings()
        self.gs_logic.stop_cmd_system()
        if self.gs_logic.routing_service: self.gs_logic.routing_service.stop()
        super().closeEvent(event)

def main():
    app = QApplication(sys.argv)
    window = NextGenGroundSystem()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__": main()
