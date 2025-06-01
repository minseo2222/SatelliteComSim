#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GroundSystem.py (수정본)

- Sample App 전송·수신 기록을 ID 기반으로 매칭하여 RTT 등 평가 지표를 보여주는 창 추가
- Start Telemetry 버튼을 누르면 별도 스레드가 sample_app_recv.csv를 모니터링
  → 수신 기록이 업데이트될 때마다 GUI도 갱신
"""

import csv
import pickle
import shlex
import subprocess
import sys
import threading
import time
from pathlib import Path
from datetime import datetime

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (
    QApplication, QDialog, QHeaderView, QPushButton,
    QTableWidgetItem, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QTableWidget, QMessageBox, QGroupBox, QTextEdit
)

from MiniCmdUtil import MiniCmdUtil
from UiCommandsystemdialog import UiCommandsystemdialog

ROOTDIR = Path(sys.argv[0]).resolve().parent

# --------------------------------------------------------------------------------
# -- SampleAppTelemetryDialog: 별도 창
# --------------------------------------------------------------------------------
class SampleAppTelemetryDialog(QDialog):
    """
    Sample App 전용 전송·수신 결과 창
    - sample_app_sent.csv: 전송 기록 (id, timestamp, text)
    - sample_app_recv.csv: 수신 기록 (id, timestamp)
    표(table)에 “ID, 전송 시각, 수신 시각, RTT(ms), 상태(OK/Timeout)” 등을 표시
    """
    SENT_CSV = ROOTDIR / "sample_app_sent.csv"
    RECV_CSV = ROOTDIR / "sample_app_recv.csv"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Sample App Telemetry Metrics")
        self.setMinimumSize(700, 400)

        # 레이아웃 구성
        main_layout = QVBoxLayout(self)

        # 1) 설명 라벨
        lbl = QLabel("Sample App 전송·수신 매칭 결과 (ID 기준):\n"
                     "- RTT = (수신 시각 – 전송 시각) [단위: ms]\n"
                     "- 상태: 수신 기록이 있으면 OK, 없으면 TIMEOUT")
        main_layout.addWidget(lbl)

        # 2) 테이블: ID, 전송 시각, 수신 시각, RTT(ms), 상태
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["ID", "Sent Timestamp", "Recv Timestamp", "RTT (ms)", "Status"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        main_layout.addWidget(self.table, stretch=1)

        # 3) 닫기 버튼
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.close)
        main_layout.addWidget(btn_close, alignment=Qt.AlignRight)

        # 데이터 로드 및 초기 갱신
        self.refresh_data()

    def refresh_data(self):
        """
        sample_app_sent.csv 와 sample_app_recv.csv 를 읽어서 ID별 매칭 후 테이블 업데이트
        """
        # 1) 전송 기록 읽기 → dict {id: (sent_ts, text)}
        sent_dict = {}
        if self.SENT_CSV.exists():
            with open(self.SENT_CSV, "r", newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        sid = int(row["id"])
                        ts = datetime.fromisoformat(row["timestamp"])
                        sent_dict[sid] = ts
                    except Exception:
                        continue

        # 2) 수신 기록 읽기 → dict {id: recv_ts}
        recv_dict = {}
        if self.RECV_CSV.exists():
            with open(self.RECV_CSV, "r", newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        rid = int(row["id"])
                        rts = datetime.fromisoformat(row["timestamp"])
                        # 만약 같은 ID가 여러 번 수신되었다면, "가장 빠른(recv_ts)"만 사용
                        if rid not in recv_dict or rts < recv_dict[rid]:
                            recv_dict[rid] = rts
                    except Exception:
                        continue

        # 3) 전체 ID 리스트: 전송 ID 기준으로
        all_ids = sorted(sent_dict.keys())

        # 4) 테이블 초기화
        self.table.setRowCount(len(all_ids))
        for row_idx, sid in enumerate(all_ids):
            sent_ts = sent_dict.get(sid)
            recv_ts = recv_dict.get(sid, None)

            # 컬럼 0: ID
            item_id = QTableWidgetItem(str(sid))
            self.table.setItem(row_idx, 0, item_id)

            # 컬럼 1: Sent Timestamp
            item_sent = QTableWidgetItem(sent_ts.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3])
            self.table.setItem(row_idx, 1, item_sent)

            # 컬럼 2: Recv Timestamp (없으면 "-")
            if recv_ts:
                item_recv = QTableWidgetItem(recv_ts.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3])
            else:
                item_recv = QTableWidgetItem("-")
            self.table.setItem(row_idx, 2, item_recv)

            # 컬럼 3: RTT (ms) 계산
            if recv_ts:
                delta = recv_ts - sent_ts
                rtt_ms = int(delta.total_seconds() * 1000)
                item_rtt = QTableWidgetItem(str(rtt_ms))
            else:
                item_rtt = QTableWidgetItem("-")
            self.table.setItem(row_idx, 3, item_rtt)

            # 컬럼 4: Status ("OK" or "TIMEOUT")
            status = "OK" if recv_ts else "TIMEOUT"
            item_status = QTableWidgetItem(status)
            # 색상 표시: OK는 초록, TIMEOUT은 붉은색
            if status == "OK":
                item_status.setForeground(Qt.darkGreen)
            else:
                item_status.setForeground(Qt.red)
            self.table.setItem(row_idx, 4, item_status)

        self.table.resizeRowsToContents()


# --------------------------------------------------------------------------------
# -- TelemetryListener: 백그라운드에서 sample_app_recv.csv를 폴링하며 갱신
# --------------------------------------------------------------------------------
class TelemetryListener(threading.Thread):
    """
    별도 스레드로 동작하면서 일정 주기(예: 1초)로 sample_app_recv.csv 파일을
    읽어들이고 수정시간이 바뀌었으면, 연결된 GUI(Dialog)에 알림(callback)을 호출
    """
    POLL_INTERVAL = 1.0  # 초 단위

    def __init__(self, on_update_callback):
        super().__init__(daemon=True)
        self.on_update = on_update_callback
        self.last_mtime = None
        self.stop_flag = False

    def run(self):
        recv_csv = SampleAppTelemetryDialog.RECV_CSV
        while not self.stop_flag:
            if recv_csv.exists():
                mtime = recv_csv.stat().st_mtime
                # 파일이 새로 생성되었거나 수정되었으면 콜백
                if self.last_mtime is None or mtime > self.last_mtime:
                    self.last_mtime = mtime
                    # UI 스레드 쪽으로 안전하게 시그널/콜백
                    self.on_update()
            time.sleep(self.POLL_INTERVAL)

    def stop(self):
        self.stop_flag = True


# --------------------------------------------------------------------------------
# -- CommandSystem 클래스 수정본
# --------------------------------------------------------------------------------
class CommandSystem(QDialog, UiCommandsystemdialog):
    def __init__(self):
        super().__init__()
        self.setupUi(self)
        self.move(800, 100)
        self.mcu = None

        # 1) “Sample App Telemetry Metrics” 버튼 추가
        self.btn_sample_metrics = QPushButton("Sample App Metrics")
        # start/stop 버튼 영역 (예: “Start Telemetry” 버튼 옆에 추가)
        # self.grp_control은 UI 파일에서 start/stop이 포함된 QGroupBox라고 가정
        # (실제 UI 구조에 맞게 적절히 레이아웃에 추가하면 됩니다.)
        # 예시: self.grp_control.layout().addWidget(self.btn_sample_metrics)
        self.grp_control.layout().addWidget(self.btn_sample_metrics)

        self.btn_sample_metrics.clicked.connect(self.open_sample_metrics_dialog)
        self.sample_dialog = None

        # 2) Telemetry 결과가 CSV로 기록될 때마다 Dialog를 갱신하기 위한 리스너
        self.telemetry_listener = None

    def process_button_generic(self, idx):
        if cmd_page_is_valid[idx]:
            app_name = self.tbl_cmd_sys.item(idx, 0).text().strip()

            # Sample App 텍스트 GUI 호출
            if app_name in ["Sample App", "Sample App (CPU1)", "Sample App Text Send"]:
                gui_path = ROOTDIR / "sample_app_send_text_gui.py"
                subprocess.Popen(["python3", str(gui_path)])

                # 로그에 기록
                with open(ROOTDIR / "SentCommandLogs.txt", "a", encoding="utf-8") as logf:
                    logf.write(f"[{datetime.now()}] GUI Opened for SAMPLE_APP Text Send (via Display Page)\n")
                return

            # 기본 명령 GUI 로직 (기존 코드 유지)
            pkt_id = self.tbl_cmd_sys.item(idx, 1).text()
            address = self.tbl_cmd_sys.item(idx, 2).text()
            launch_string = (
                f'python3 {ROOTDIR}/{cmdClass[idx]} '
                f'--title="{cmdPageDesc[idx]}" --pktid={pkt_id} '
                f'--file={cmdPageDefFile[idx]} --address="{address}" '
                f'--port={cmdPagePort[idx]} --endian={cmdPageEndian[idx]}'
            )
            cmd_args = shlex.split(launch_string)
            subprocess.Popen(cmd_args)

    @staticmethod
    def check_params(idx):
        pickle_file = f'{ROOTDIR}/ParameterFiles/{quick_param[idx]}'
        try:
            with open(pickle_file, 'rb') as pickle_obj:
                param_names = pickle.load(pickle_obj)[1]
            return len(param_names) > 0
        except IOError:
            return False

    def process_quick_button(self, idx):
        if cmd_page_is_valid[idx] and quick_indices[idx] >= 0:
            q_idx = quick_indices[idx]
            pkt_id = self.tbl_cmd_sys.item(idx, 1).text()
            address = self.tbl_cmd_sys.item(idx, 2).text()

            # Sample App 텍스트 GUI 호출 (Quick Command)
            if subsys[q_idx] in ["Sample App", "Sample App Text Send"] and quick_cmd[q_idx] == "Send Text":
                gui_path = ROOTDIR / "sample_app_send_text_gui.py"
                subprocess.Popen(["python3", str(gui_path)])
                with open(ROOTDIR / "SentCommandLogs.txt", "a", encoding="utf-8") as logf:
                    logf.write(f"[{datetime.now()}] GUI Opened for SAMPLE_APP Text Send (via Quick Command)\n")
                return

            # 파라미터가 필요한 경우
            if self.check_params(q_idx):
                launch_string = (
                    f'python3 {ROOTDIR}/Parameter.py '
                    f'--title="{subsys[q_idx]}" '
                    f'--descrip="{quick_cmd[q_idx]}" '
                    f'--idx={idx} --host="{address}" '
                    f'--port={quick_port[q_idx]} '
                    f'--pktid={pkt_id} --endian={quick_endian[q_idx]} '
                    f'--cmdcode={quick_code[q_idx]} --file={quick_param[q_idx]}'
                )
                cmd_args = shlex.split(launch_string)
                subprocess.Popen(cmd_args)
            else:
                self.mcu = MiniCmdUtil(address, quick_port[q_idx],
                                       quick_endian[q_idx], pkt_id,
                                       quick_code[q_idx])
                send_success = self.mcu.send_packet()
                print("Command sent successfully:", send_success)

    def on_start_telemetry(self):
        """
        “Start Telemetry” 버튼 클릭 시 호출.
        기존 TelemetrySystem을 띄우는 로직 + 별도 listener 스레드 시작
        """
        # (기존의 TelemetrySystem 실행 로직)
        self.start_tlm_system(self.cb_ips.currentText())

        # TelemetryListener 스레드가 이미 실행 중이면 중지
        if self.telemetry_listener:
            self.telemetry_listener.stop()
            self.telemetry_listener = None

        # SampleAppTelemetryDialog가 열려 있으면 먼저 닫고 다시 생성
        if self.sample_dialog and self.sample_dialog.isVisible():
            self.sample_dialog.close()
            self.sample_dialog = None

        # TelemetryListener 생성 → sample_app_recv.csv 감시
        self.telemetry_listener = TelemetryListener(on_update_callback=self._on_recv_csv_update)
        self.telemetry_listener.start()

    def _on_recv_csv_update(self):
        """
        sample_app_recv.csv가 갱신되었을 때 호출되는 콜백
        → GUI가 띄워져 있으면 테이블을 갱신
        """
        if self.sample_dialog and self.sample_dialog.isVisible():
            # 메인 스레드에서 GUI 갱신해야 하므로 QTimer.singleShot 사용
            QTimer.singleShot(0, self.sample_dialog.refresh_data)

    def open_sample_metrics_dialog(self):
        """
        “Sample App Metrics” 버튼 클릭 시 호출.
        전용 창을 열고, TelemetryListener가 있으면 GUI가 자동 갱신되도록 연결
        """
        if not self.sample_dialog:
            self.sample_dialog = SampleAppTelemetryDialog(self)
        self.sample_dialog.refresh_data()
        self.sample_dialog.show()

    def start_tlm_system(self, selected_spacecraft):
        """
        기존 TelemetrySystem 실행 로직 (변경 없음)
        """
        subscription = '--sub=GroundSystem'
        if selected_spacecraft != 'All':
            subscription += f'.{selected_spacecraft}.TelemetryPackets'
        args = shlex.split(
            f'python3 {ROOTDIR}/Subsystems/tlmGUI/TelemetrySystem.py {subscription}'
        )
        subprocess.Popen(args)

        # 메인 로그 창에 메시지
        self.log_output.append(f"<font color='blue'>[시스템] Telemetry System Started</font>")

    def start_cmd_system(self, on_stdout_callback=None):
        """
        기존 CommandSystem 실행 로직 (변경 없음)
        """
        if self.cmd_process and self.cmd_process.poll() is None:
            self.display_error_message("Command System is already running.")
            return
        cmd = ['python3', '-u', f'{ROOTDIR}/Subsystems/cmdGui/CommandSystem.py']
        self.cmd_process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1
        )
        self.cmd_process_reader = CmdProcessReader(self.cmd_process)
        if on_stdout_callback:
            self.cmd_process_reader.line_received.connect(on_stdout_callback)
        self.cmd_process_reader.start()
        self.log_output.append(f"<font color='blue'>[시스템] Command System Started</font>")

    def on_cmd_header_changed(self, txt):
        """
        기존 로직 그대로
        """
        self.gs_logic.set_cmd_offsets(txt)
        self.sb_cmd_pri.setEnabled(txt == "Custom")
        self.sb_cmd_sec.setEnabled(txt == "Custom")
        self.sb_cmd_pri.setValue(self.gs_logic.sb_cmd_offset_pri_value)
        self.sb_cmd_sec.setValue(self.gs_logic.sb_cmd_offset_sec_value)
        self.gs_logic.save_offsets()

    def on_cmd_offset_pri_changed(self, v):
        self.gs_logic.sb_cmd_offset_pri_value = v
        self.gs_logic.save_offsets()

    def on_cmd_offset_sec_changed(self, v):
        self.gs_logic.sb_cmd_offset_sec_value = v
        self.gs_logic.save_offsets()

    def on_tlm_header_changed(self, txt):
        self.gs_logic.set_tlm_offset(txt)
        self.sb_tlm_offset.setEnabled(txt == "Custom")
        self.sb_tlm_offset.setValue(self.gs_logic.sb_tlm_offset_value)
        self.gs_logic.save_offsets()

    def on_tlm_offset_changed(self, v):
        self.gs_logic.sb_tlm_offset_value = v
        self.gs_logic.save_offsets()

    def clear_cmd_log(self):
        """
        기존 로직 그대로
        """
        self.log_output.clear()
        self.log_output.append(f"<font color='blue'>[시스템] 커맨드 로그가 초기화되었습니다.</font>")

    def show_error_message(self, msg):
        QMessageBox.warning(self, "Error", msg)

    def append_terminal_output(self, msg: str):
        """
        기존 로직 그대로
        """
        color = "blue" if msg.startswith("[시스템]") else "red" if msg.startswith("[공격]") else "black"
        self.log_output.append(f"<font color='{color}'>{msg}</font>")

    def on_start_tlm(self):
        """
        UI에서 “Start Telemetry” 버튼과 연결하도록, 이 메소드로 바꿔 줍니다.
        (기존 on_start_tlm_system → on_start_telemetry로 리다이렉션)
        """
        self.on_start_telemetry()

    def closeEvent(self, ev):
        """
        프로그램 종료 시 TelemetryListener를 깨끗이 종료
        """
        if self.mcu:
            self.mcu.mm.close()
        if self.telemetry_listener:
            self.telemetry_listener.stop()
        super().closeEvent(ev)


# Main
if __name__ == "__main__":
    cmd_def_file = "command-pages.txt"

    app = QApplication(sys.argv)
    command = CommandSystem()
    tbl = command.tbl_cmd_sys

    # 기존 CSV 및 동적 테이블 로드 로직 그대로
    cmd_page_is_valid, cmdPageDesc, cmdPageDefFile, cmdPageAppid, \
    cmdPageEndian, cmdClass, cmdPageAddress, cmdPagePort = ([] for _ in range(8))

    i = 0
    with open(f"{ROOTDIR}/{cmd_def_file}") as cmdfile:
        reader = csv.reader(cmdfile, skipinitialspace=True)
        for cmdRow in reader:
            try:
                if not cmdRow[0].startswith('#'):
                    cmd_page_is_valid.append(True)
                    cmdPageDesc.append(cmdRow[0])
                    cmdPageDefFile.append(cmdRow[1])
                    cmdPageAppid.append(int(cmdRow[2], 16))
                    cmdPageEndian.append(cmdRow[3])
                    cmdClass.append(cmdRow[4])
                    cmdPageAddress.append(cmdRow[5])
                    cmdPagePort.append(int(cmdRow[6]))
                    i += 1
            except IndexError as e:
                print("IndexError:", e)
                print("This may be due to a formatting issue in command-pages.txt")

    for _ in range(i, 22):
        cmdPageAppid.append(0)
        cmd_page_is_valid.append(False)

    quick_def_file = 'quick-buttons.txt'
    subsys, subsys_file, quick_cmd, quick_code, quick_pkt_id, \
    quick_endian, quick_address, quick_port, quick_param, \
    quick_indices = ([] for _ in range(10))

    with open(f'{ROOTDIR}/{quick_def_file}') as subFile:
        reader = csv.reader(subFile)
        for fileRow in reader:
            if not fileRow[0].startswith('#'):
                subsys.append(fileRow[0])
                subsys_file.append(fileRow[1])
                quick_cmd.append(fileRow[2].strip())
                quick_code.append(fileRow[3].strip())
                quick_pkt_id.append(fileRow[4].strip())
                quick_endian.append(fileRow[5].strip())
                quick_address.append(fileRow[6].strip())
                quick_port.append(fileRow[7].strip())
                quick_param.append(fileRow[8].strip())

    for k, desc in enumerate(cmdPageDesc):
        if cmd_page_is_valid[k]:
            tbl.insertRow(k)
            for col, text in enumerate((desc, hex(cmdPageAppid[k]), cmdPageAddress[k])):
                tbl_item = QTableWidgetItem(text)
                tbl.setItem(k, col, tbl_item)

            tbl_btn = QPushButton("Display Page")
            tbl_btn.clicked.connect(lambda _, x=k: command.process_button_generic(x))
            tbl.setCellWidget(k, 3, tbl_btn)

            quick_idx = -1
            try:
                quick_idx = subsys.index(desc)
            except ValueError:
                pass
            else:
                quick_btn = QPushButton(quick_cmd[quick_idx])
                quick_btn.clicked.connect(lambda _, x=k: command.process_quick_button(x))
                tbl.setCellWidget(k, 4, quick_btn)

            quick_indices.append(quick_idx)

    tbl.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
    tbl.horizontalHeader().setStretchLastSection(True)

    command.show()
    command.raise_()
    print('Command System started.')
    sys.exit(app.exec_())

