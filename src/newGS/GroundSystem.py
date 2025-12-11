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
    QComboBox, QSpinBox, QTextEdit, QDialog, QDoubleSpinBox, QDialogButtonBox,
    QRadioButton, QButtonGroup
)

from modeling import EarthSatelliteView
from satellite_setting import SatelliteSettingsDialog
from base_station_setting import BaseStationSettingsDialog
from comm_setting import CommSettingsDialog


# ──────────────────────────────────────────────────────────────────────────────
# [Updated] 공격 설정 다이얼로그 (Replay 추가)
# ──────────────────────────────────────────────────────────────────────────────
class AttackConfigDialog(QDialog):
    def __init__(self, mode_kor, current_config, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"{mode_kor} 상세 설정")
        self.mode_kor = mode_kor
        self.config = current_config.copy()
        self._init_ui()

    def _init_ui(self):
        layout = QFormLayout(self)
        
        # 1. 공통: 확률
        self.sb_prob = QDoubleSpinBox()
        self.sb_prob.setRange(0.0, 100.0)
        self.sb_prob.setSuffix(" %")
        self.sb_prob.setDecimals(1)
        self.sb_prob.setValue(float(self.config.get("prob", 100.0)))
        layout.addRow("공격 발동 확률:", self.sb_prob)

        # 2. 공격별 특수 파라미터
        if "드랍" in self.mode_kor:
            self.sb_burst = QSpinBox()
            self.sb_burst.setRange(1, 1000)
            self.sb_burst.setValue(int(self.config.get("burst_size", 1)))
            self.sb_burst.setToolTip("한 번 발동 시 연속으로 드랍할 패킷 수")
            layout.addRow("연속 드랍 (Burst):", self.sb_burst)

        elif "재밍" in self.mode_kor:
            self.sb_protect = QSpinBox()
            self.sb_protect.setRange(0, 1024)
            self.sb_protect.setValue(int(self.config.get("jamming_protect", 8)))
            layout.addRow("헤더 보호 (Bytes):", self.sb_protect)
            
            self.sb_ratio = QDoubleSpinBox()
            self.sb_ratio.setRange(0.0, 100.0)
            self.sb_ratio.setValue(float(self.config.get("jamming_ratio", 100.0)))
            self.sb_ratio.setSuffix(" %")
            layout.addRow("훼손 비율 (Ratio):", self.sb_ratio)

        elif "리플레이" in self.mode_kor:
            self.sb_delay = QDoubleSpinBox()
            self.sb_delay.setRange(0.1, 60.0)
            self.sb_delay.setValue(float(self.config.get("replay_delay", 1.0)))
            self.sb_delay.setSuffix(" sec")
            self.sb_delay.setToolTip("복제된 패킷을 얼마나 늦게 보낼지 설정")
            layout.addRow("재전송 지연 (Delay):", self.sb_delay)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._on_accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _on_accept(self):
        self.config["prob"] = self.sb_prob.value()
        
        if "드랍" in self.mode_kor:
            self.config["burst_size"] = self.sb_burst.value()
        elif "재밍" in self.mode_kor:
            self.config["jamming_protect"] = self.sb_protect.value()
            self.config["jamming_ratio"] = self.sb_ratio.value()
        elif "리플레이" in self.mode_kor:
            self.config["replay_delay"] = self.sb_delay.value()
            
        self.accept()

    def get_config(self):
        return self.config


# ──────────────────────────────────────────────────────────────────────────────
# CmdProcessReader
# ──────────────────────────────────────────────────────────────────────────────
class CmdProcessReader(QThread):
    line_received = pyqtSignal(str)
    def __init__(self, process, parent=None):
        super().__init__(parent)
        self.process = process
        self._running = True
    def run(self):
        while self._running:
            if self.process.stdout is None: break
            line = self.process.stdout.readline()
            if not line: break
            self.line_received.emit(line.rstrip("\n"))
    def stop(self): self._running = False


# ──────────────────────────────────────────────────────────────────────────────
# GroundSystemLogic
# ──────────────────────────────────────────────────────────────────────────────
class GroundSystemLogic:
    TLM_HDR_V1_OFFSET = 4; TLM_HDR_V2_OFFSET = 4
    CMD_HDR_PRI_V1_OFFSET = 0; CMD_HDR_SEC_V1_OFFSET = 0
    CMD_HDR_PRI_V2_OFFSET = 4; CMD_HDR_SEC_V2_OFFSET = 4

    def __init__(self, rootdir, display_error_callback=None):
        self.ROOTDIR = rootdir
        self.display_error_callback = display_error_callback
        self.ip_addresses_list = ['All']; self.spacecraft_names = ['All']
        self.routing_service = None; self.cmd_process = None; self.cmd_process_reader = None

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
            self.display_error_message(f"File Not Found: {tlm_system_path}")
            return
        args = shlex.split(f'python3 {str(tlm_system_path)} {subscription}')
        try: subprocess.Popen(args)
        except Exception as e: self.display_error_message(f"TLM Start Fail: {e}")

    def start_cmd_system(self, on_stdout_callback=None):
        if self.cmd_process and self.cmd_process.poll() is None: return
        cmd_system_path = self.ROOTDIR / "Subsystems" / "cmdGui" / "CommandSystem.py"
        if not cmd_system_path.is_file(): return
        cmd = ['python3', '-u', str(cmd_system_path)]
        try:
            self.cmd_process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
            self.cmd_process_reader = CmdProcessReader(self.cmd_process)
            if on_stdout_callback: self.cmd_process_reader.line_received.connect(on_stdout_callback)
            self.cmd_process_reader.start()
        except Exception as e: self.display_error_message(f"CMD Start Fail: {e}")

    def stop_cmd_system(self):
        if self.cmd_process:
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
        except: pass


# ──────────────────────────────────────────────────────────────────────────────
# NextGenGroundSystem
# ──────────────────────────────────────────────────────────────────────────────
class NextGenGroundSystem(QMainWindow):
    DEFAULT_TLM_HDR_VER = "1"; DEFAULT_CMD_HDR_VER = "1"
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
        self.test2_process = None

        # [Updated] Replay 포함 기본값
        self.attack_configs = {
            "drop": {"prob": 100.0, "burst_size": 1},
            "jamming": {"prob": 100.0, "jamming_protect": 8, "jamming_ratio": 100.0},
            "replay": {"prob": 100.0, "replay_delay": 1.0},
            "none": {}
        }

        self._init_ui()
        self._load_settings()
        self.gs_logic.init_routing_service()

    def _init_ui(self):
        main_widget = QWidget(); self.setCentralWidget(main_widget)
        h_layout = QHBoxLayout(main_widget)

        # Left
        left_panel = QWidget(); left_layout = QVBoxLayout(left_panel)
        self.earth_view = EarthSatelliteView(
            model_path=str(self.ROOTDIR/"textures"/"earth.glb"), 
            texture_path=str(self.ROOTDIR/"textures"/"image_0.png"),
            bg_image_path=str(self.ROOTDIR/"textures"/"background.jpg"), 
            sat_model_path=str(self.ROOTDIR/"textures"/"satellite.glb"), parent=self
        )
        left_layout.addWidget(self.earth_view, stretch=4)
        
        btn_layout = QHBoxLayout()
        for name, cb in [("기지국 설정", self.openBaseStationSettings), ("위성 설정", self.openSatelliteSettings), ("통신 설정", self.openCommSettings)]:
            b = QPushButton(name); b.clicked.connect(cb); btn_layout.addWidget(b)
        left_layout.addLayout(btn_layout)
        h_layout.addWidget(left_panel, stretch=5)

        # Right
        right_panel = QWidget(); right_layout = QVBoxLayout(right_panel)
        self.log_output = QTextEdit(); self.log_output.setReadOnly(True)
        right_layout.addWidget(self.log_output, stretch=3)

        ctrl_box = QGroupBox("제어 / 공격 시뮬레이션")
        ctrl_layout = QVBoxLayout(ctrl_box)
        form = QFormLayout()
        
        self.cb_tlm_header = QComboBox(); self.cb_tlm_header.addItems(["1","2","Custom"])
        self.cb_tlm_header.currentTextChanged.connect(self.on_tlm_header_changed)
        form.addRow("TLM Ver:", self.cb_tlm_header)
        self.sb_tlm_offset = QSpinBox(); self.sb_tlm_offset.setRange(0,64); self.sb_tlm_offset.valueChanged.connect(self.on_tlm_offset_changed)
        form.addRow("TLM Offset:", self.sb_tlm_offset)
        
        self.cb_cmd_header = QComboBox(); self.cb_cmd_header.addItems(["1","2","Custom"])
        self.cb_cmd_header.currentTextChanged.connect(self.on_cmd_header_changed)
        form.addRow("CMD Ver:", self.cb_cmd_header)
        self.sb_cmd_pri = QSpinBox(); self.sb_cmd_pri.setRange(0,64); self.sb_cmd_pri.valueChanged.connect(self.on_cmd_offset_pri_changed)
        form.addRow("CMD Pri:", self.sb_cmd_pri)
        self.sb_cmd_sec = QSpinBox(); self.sb_cmd_sec.setRange(0,64); self.sb_cmd_sec.valueChanged.connect(self.on_cmd_offset_sec_changed)
        form.addRow("CMD Sec:", self.sb_cmd_sec)
        ctrl_layout.addLayout(form)

        self.cb_ips = QComboBox(); self.cb_ips.addItem("All")
        ctrl_layout.addWidget(QLabel("Target IP:")); ctrl_layout.addWidget(self.cb_ips)

        sys_btn_layout = QHBoxLayout()
        for l, h in [("Start Telemetry", self.on_start_tlm), ("Start Command", self.on_start_cmd), ("Clear Log", self.clear_cmd_log)]:
            b = QPushButton(l); b.clicked.connect(h); sys_btn_layout.addWidget(b)
        ctrl_layout.addLayout(sys_btn_layout)

        # [공격 설정]
        att_grp = QGroupBox("공격 시나리오")
        att_layout = QVBoxLayout(att_grp)
        
        self.attack_combo = QComboBox()
        self.attack_modes_kor_to_eng = {
            "없음": "none",
            "드랍 (Drop)": "drop",
            "재밍 (Jamming)": "jamming",
            "리플레이 (Replay)": "replay"
        }
        self.attack_combo.addItems(self.attack_modes_kor_to_eng.keys())
        self.attack_combo.currentTextChanged.connect(self._on_attack_combo_changed)
        att_layout.addWidget(QLabel("공격 유형:"))
        att_layout.addWidget(self.attack_combo)

        att_ctrl_layout = QHBoxLayout()
        self.btn_attack_setting = QPushButton("설정")
        self.btn_attack_setting.clicked.connect(self.open_attack_settings)
        self.btn_attack_setting.setEnabled(False)
        
        self.btn_attack_start = QPushButton("공격 시작")
        self.btn_attack_start.setCheckable(True)
        self.btn_attack_start.clicked.connect(self.toggle_attack_mode)
        self.btn_attack_start.setMinimumHeight(40)
        
        att_ctrl_layout.addWidget(self.btn_attack_setting, 1)
        att_ctrl_layout.addWidget(self.btn_attack_start, 3)
        att_layout.addLayout(att_ctrl_layout)
        
        ctrl_layout.addWidget(att_grp)
        ctrl_layout.addStretch()
        right_layout.addWidget(ctrl_box, stretch=2)
        h_layout.addWidget(right_panel, stretch=3)

    def _on_attack_combo_changed(self, text):
        is_none = (text == "없음")
        self.btn_attack_setting.setEnabled(not is_none)
        if not self.btn_attack_start.isChecked():
            self.btn_attack_start.setEnabled(not is_none)

    def open_attack_settings(self):
        selected_kor = self.attack_combo.currentText()
        if selected_kor == "없음": return
        mode_eng = self.attack_modes_kor_to_eng[selected_kor]
        current_cfg = self.attack_configs.get(mode_eng, {})
        
        dlg = AttackConfigDialog(selected_kor, current_cfg, self)
        if dlg.exec_() == QDialog.Accepted:
            new_cfg = dlg.get_config()
            self.attack_configs[mode_eng] = new_cfg
            self.append_terminal_output(f"[설정] {selected_kor} 파라미터 업데이트: {new_cfg}")
            if self.btn_attack_start.isChecked():
                self._send_attack_config(mode_eng, new_cfg)

    def toggle_attack_mode(self):
        is_started = self.btn_attack_start.isChecked()
        selected_kor = self.attack_combo.currentText()
        if is_started and selected_kor == "없음":
            self.append_terminal_output("[공격] '없음'은 공격 유형이 아닙니다.")
            self.btn_attack_start.setChecked(False)
            return

        mode_eng = self.attack_modes_kor_to_eng.get(selected_kor, "none") if is_started else "none"
        config = self.attack_configs.get(mode_eng, {})
        self._send_attack_config(mode_eng, config)

        self.btn_attack_start.setText("공격 중지" if is_started else "공격 시작")
        self.attack_combo.setEnabled(not is_started)
        if is_started:
            self.append_terminal_output(f"[공격] {selected_kor} 시작. 설정: {config}")
        else:
            self.append_terminal_output("[공격] 공격 중지.")

    def _send_attack_config(self, mode, config):
        comm_params = self.settings.value("comm/params", defaultValue={}, type=dict)
        ctrl_ip = comm_params.get("ctrl_bind_ip", "127.0.0.1")
        ctrl_port = int(comm_params.get("ctrl_port", 9696))
        
        params = {"attack_mode": mode}
        params.update(config)
        if "prob" in params: params["attack_prob"] = params.pop("prob")
            
        msg = {"cmd": "set", "params": params}
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(0.2)
            sock.sendto(json.dumps(msg).encode("utf-8"), (ctrl_ip, ctrl_port))
            sock.close()
        except Exception as e:
            self.append_terminal_output(f"[오류] 공격 명령 전송 실패: {e}")

    # (이하 설정 로드/저장/다이얼로그 메서드는 기존과 동일)
    def _load_settings(self):
        default_sat = getattr(self.earth_view, 'DEFAULT_PARAMS', {})
        sat = self.settings.value("satellite/params", default_sat, type=dict)
        valid = {"sat_type","sat_size","sat_speed","orbital_radius","inclination","eccentricity","frequency","antenna_gain","transmit_power"}
        if sat: self.earth_view.updateSatelliteParameters(**{k:v for k,v in sat.items() if k in valid})
        self.cb_tlm_header.setCurrentText(self.settings.value("offsets/tlm_ver", self.DEFAULT_TLM_HDR_VER, str))
        self.sb_tlm_offset.setValue(self.settings.value("offsets/tlm_offset", self.DEFAULT_TLM_OFFSET, int))
        self.cb_cmd_header.setCurrentText(self.settings.value("offsets/cmd_ver", self.DEFAULT_CMD_HDR_VER, str))
        self.sb_cmd_pri.setValue(self.settings.value("offsets/cmd_pri", self.DEFAULT_CMD_OFFSET_PRI, int))
        self.sb_cmd_sec.setValue(self.settings.value("offsets/cmd_sec", self.DEFAULT_CMD_OFFSET_SEC, int))
        self.append_terminal_output("[시스템] 설정 로드 완료.")

    def _save_settings(self):
        self.settings.setValue("offsets/tlm_ver", self.cb_tlm_header.currentText())
        self.settings.setValue("offsets/tlm_offset", self.sb_tlm_offset.value())
        self.settings.setValue("offsets/cmd_ver", self.cb_cmd_header.currentText())
        self.settings.setValue("offsets/cmd_pri", self.sb_cmd_pri.value())
        self.settings.setValue("offsets/cmd_sec", self.sb_cmd_sec.value())

    def openBaseStationSettings(self):
        dlg = BaseStationSettingsDialog(self)
        dlg.setParameters(self.settings.value("basestation/params", {}, dict))
        if dlg.exec_() == QDialog.Accepted:
            self.settings.setValue("basestation/params", dlg.getParameters())
            self.append_terminal_output("[시스템] 기지국 설정 저장.")

    def openSatelliteSettings(self):
        dlg = SatelliteSettingsDialog(self)
        dlg.setParameters(self.settings.value("satellite/params", {}, dict))
        if dlg.exec_() == QDialog.Accepted:
            self.settings.setValue("satellite/params", dlg.getParameters())
            self.earth_view.updateSatelliteParameters(**dlg.getParameters())
            self.append_terminal_output("[시스템] 위성 설정 저장.")

    def openCommSettings(self):
        dlg = CommSettingsDialog(self, defaults=self.settings.value("comm/params", {}, dict))
        if dlg.exec_() != QDialog.Accepted: return
        self.settings.setValue("comm/params", dlg.get())
        with open(self.ROOTDIR/"test2_config.json", "w") as f: json.dump(dlg.get(), f, indent=2)
        if not self._is_test2_running():
            self._start_test2(self.ROOTDIR/"test2_config.json")
        else:
            self._send_attack_config("none", {})
            self.append_terminal_output("[시스템] 통신 설정 업데이트.")

    def _is_test2_running(self):
        return self.test2_process is not None and self.test2_process.poll() is None

    def _start_test2(self, cfg_path):
        env = os.environ.copy(); env["TEST2_CONFIG"] = str(cfg_path)
        try:
            self.test2_process = subprocess.Popen(["python3", "-u", "test2.py"], cwd=str(self.ROOTDIR), env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
            self.append_terminal_output("[시스템] test2 실행.")
        except Exception as e: self.append_terminal_output(f"[오류] test2 실행불가: {e}")

    def clear_cmd_log(self): self.log_output.clear()
    def show_error_message_box(self, msg): QMessageBox.critical(self, "Error", msg)
    def append_terminal_output(self, msg):
        self.log_output.append(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")
    
    def on_start_tlm(self): self.gs_logic.start_tlm_system("All")
    def on_start_cmd(self): self.gs_logic.start_cmd_system(lambda l: self.append_terminal_output(f"[CMD] {l}"))
    def on_tlm_header_changed(self, t): self.sb_tlm_offset.setEnabled(t=="Custom"); self._save_settings()
    def on_tlm_offset_changed(self, v): self._save_settings()
    def on_cmd_header_changed(self, t): self.sb_cmd_pri.setEnabled(t=="Custom"); self.sb_cmd_sec.setEnabled(t=="Custom"); self._save_settings()
    def on_cmd_offset_pri_changed(self, v): self._save_settings()
    def on_cmd_offset_sec_changed(self, v): self._save_settings()
    def on_ip_list_updated(self, ip, name): self.cb_ips.addItem(f"{name} ({ip})")
    def closeEvent(self, e):
        if self.test2_process: self.test2_process.terminate()
        self.gs_logic.stop_cmd_system()
        super().closeEvent(e)

def main():
    app = QApplication(sys.argv)
    w = NextGenGroundSystem()
    w.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
