#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sample_app_send_text_gui.py

사용자 입력 텍스트를 SAMPLE_APP으로 전송합니다.
ID는 sample_app_sent.csv의 마지막 ID 다음 번호로 자동 할당됩니다.
전송 로그(csv 저장)는 test1.py에서 처리합니다.
"""

import sys
import subprocess
from pathlib import Path
from datetime import datetime
import csv

from PyQt5.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QLabel,
    QTextEdit, QPushButton, QMessageBox
)

# 이 스크립트 파일이 위치한 디렉토리
ROOTDIR_GUI = Path(__file__).resolve().parent

# cmdUtil 경로: 이 GUI 스크립트 위치에서 한 단계 상위 디렉토리의 cmdUtil 폴더 안을 가정
CMDUTIL_PATH = (ROOTDIR_GUI / "../cmdUtil/cmdUtil").resolve()

# 이 GUI 앱 자체의 로컬 활동 로그 (test1.py의 SENT_CSV와는 다름)
LOCAL_LOG_PATH = ROOTDIR_GUI / "SentCommandLogs_GUI.txt" 

# test1.py가 생성하고 이 GUI가 참조할 SENT_CSV 파일 경로
# 중요: 이 경로는 test1.py의 SENT_CSV_PATH와 정확히 일치해야 합니다.
# test1.py가 ROOTDIR_test1 / "Subsystems" / "cmdGui" / "sample_app_sent.csv" 에 저장하므로,
# 이 GUI 스크립트의 위치(ROOTDIR_GUI)를 기준으로 해당 경로를 올바르게 지정해야 합니다.
# 예시: 만약 test1.py와 이 GUI 스크립트가 같은 디렉토리(예: src/newGS/)에 있다면,
# SENT_CSV_FILE_PATH = ROOTDIR_GUI / "Subsystems" / "cmdGui" / "sample_app_sent.csv"
# 만약 이 GUI 스크립트가 test1.py의 상위 디렉토리에 있다면 경로 조정 필요.
# 여기서는 test1.py와 같은 프로젝트 루트 (예: src/newGS/)에 이 GUI가 있다고 가정.
# 또는, tlm_page와 유사한 경로 구조를 가정:
# PROJECT_ROOT_ASSUMED = ROOTDIR_GUI.parent.parent # GUI가 .../Subsystems/someGUI/ 에 있다고 가정
# SENT_CSV_FILE_PATH = PROJECT_ROOT_ASSUMED / "Subsystems" / "cmdGui" / "sample_app_sent.csv"
# 가장 일반적인 경우: test1.py와 이 GUI가 같은 폴더에 있을 때
# (test1.py의 ROOTDIR이 test1.py가 있는 폴더를 의미하므로)
SENT_CSV_FILE_PATH = ROOTDIR_GUI / ".." / "cmdGui" / "sample_app_sent.csv"
# 사용자의 실제 파일 구조에 맞게 위 SENT_CSV_FILE_PATH를 반드시 확인하고 조정해주세요.


class SendTextDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Send Text to Sample App (Auto ID from CSV)")
        self.setGeometry(100, 100, 400, 250) # 높이 약간 늘림 (디버그용)

        layout = QVBoxLayout()
        self.label = QLabel("Enter message to send to SAMPLE_APP:")
        self.text_edit = QTextEdit()
        self.send_button = QPushButton("Send")
        self.debug_label = QLabel("Next ID will be: ?") # 다음 ID 표시용 디버그 라벨

        layout.addWidget(self.label)
        layout.addWidget(self.text_edit)
        layout.addWidget(self.send_button)
        layout.addWidget(self.debug_label) # 디버그 라벨 추가
        self.setLayout(layout)

        self.send_button.clicked.connect(self.send_command)

        # CSV 경로 디버깅 출력
        print(f"[INFO] GUI ROOTDIR: {ROOTDIR_GUI}")
        print(f"[INFO] Attempting to use SENT_CSV: {SENT_CSV_FILE_PATH.resolve()}") # 실제 절대 경로 확인

        last_id_from_csv = self._get_last_seq_id_from_csv()
        self.next_seq_id = last_id_from_csv + 1
        
        self.debug_label.setText(f"Next ID will be: {self.next_seq_id}")
        print(f"[INFO] Next sequence ID initialized to: {self.next_seq_id}")


    def _get_last_seq_id_from_csv(self):
        max_id = 0
        resolved_path = SENT_CSV_FILE_PATH.resolve() # 경로 존재 여부 확인 위해 resolve
        print(f"[DEBUG] _get_last_seq_id_from_csv: Checking file at {resolved_path}")

        if SENT_CSV_FILE_PATH.exists() and SENT_CSV_FILE_PATH.is_file():
            if SENT_CSV_FILE_PATH.stat().st_size > 0:
                try:
                    with open(SENT_CSV_FILE_PATH, "r", newline="", encoding="utf-8") as f:
                        reader = csv.DictReader(f)
                        if not reader.fieldnames:
                            print(f"[WARN] CSV file {resolved_path} has no header row.")
                            return 0
                        if "id" not in reader.fieldnames:
                            print(f"[WARN] CSV file {resolved_path} header does not contain 'id' column. Header: {reader.fieldnames}")
                            return 0
                            
                        print(f"[DEBUG] CSV Header: {reader.fieldnames}")
                        row_count = 0
                        for row_num, row in enumerate(reader, 1):
                            row_count += 1
                            try:
                                current_id_str = row.get("id", "0").strip()
                                current_id = int(current_id_str)
                                print(f"[DEBUG] Row {row_num}: Parsed ID '{current_id_str}' -> {current_id}")
                                if current_id > max_id:
                                    max_id = current_id
                            except ValueError:
                                print(f"[DEBUG] Row {row_num}: ID '{current_id_str}' is not a valid integer. Skipping.")
                                continue
                            except Exception as e_row:
                                print(f"[WARN] Error processing row {row_num} in {resolved_path}: {row} - {e_row}")
                        if row_count == 0:
                             print(f"[INFO] CSV file {resolved_path} has a header but no data rows.")
                        print(f"[DEBUG] Max ID found in CSV: {max_id}")

                except FileNotFoundError: # resolve() 후에도 파일을 못 찾는 경우 (거의 발생 안 함)
                    print(f"[INFO] {resolved_path} not found during open. Starting ID from 1.")
                    return 0
                except Exception as e_file:
                    print(f"[ERROR] Failed to read {resolved_path}: {e_file}. Starting ID from 1.")
                    return 0
            else: # 파일은 존재하나 크기가 0 (빈 파일)
                print(f"[INFO] {resolved_path} exists but is empty. Starting ID from 1.")
        else: # 파일 자체가 존재하지 않음
            print(f"[INFO] {resolved_path} does not exist or is not a file. Starting ID from 1.")
        return max_id

    def send_command(self):
        raw_text = self.text_edit.toPlainText().strip()
        if not raw_text:
            QMessageBox.warning(self, "Input Error", "Please enter text before sending.")
            return

        current_id_to_send = self.next_seq_id
        message = f"{current_id_to_send}:{raw_text}"
        
        self.next_seq_id += 1
        self.debug_label.setText(f"Next ID will be: {self.next_seq_id}") # 다음 ID GUI에 업데이트

        full_text_bytes = message.encode("utf-8", errors="ignore")[:128]
        full_text_str   = full_text_bytes.decode("utf-8", errors="ignore")

        print(f"[DEBUG] Final message to send: {full_text_str!r} (ID: {current_id_to_send})")

        timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]

        cmd = [
            str(CMDUTIL_PATH), "--host=127.0.0.1", "--port=50000",
            "--pktid=0x18A8", "--cmdcode=10", f"--string=128:{full_text_str}"
        ]

        try:
            # cmdUtil 경로 존재 확인
            if not CMDUTIL_PATH.is_file():
                QMessageBox.critical(self, "Error", f"cmdUtil not found at specified path:\n{CMDUTIL_PATH}")
                # ID를 다시 이전 값으로 롤백 (선택적)
                self.next_seq_id -=1
                self.debug_label.setText(f"Next ID will be: {self.next_seq_id}")
                return

            process_result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            print(f"[CMDUTIL STDOUT] {process_result.stdout}")
            if process_result.stderr:
                 print(f"[CMDUTIL STDERR] {process_result.stderr}")


            log_msg = f"[{timestamp}] SAMPLE_APP SEND_TEXT: \"{message}\""
            try:
                LOCAL_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
                with open(LOCAL_LOG_PATH, "a", encoding="utf-8") as log_file:
                    log_file.write(log_msg + "\n")
            except Exception as e_log:
                print(f"[ERROR] Failed to write to local GUI log {LOCAL_LOG_PATH}: {e_log}")


            print(f"[CMD] {log_msg}")
            QMessageBox.information(self, "Success", f"Message sent as ID {current_id_to_send}")
            self.text_edit.clear()

        except subprocess.CalledProcessError as e:
            err_msg = f"[CMD] Error sending message: {e}\nStdout: {e.stdout}\nStderr: {e.stderr}"
            print(err_msg)
            QMessageBox.critical(self, "Error", f"Failed to send (CalledProcessError):\n{e}\n{e.stderr}")
            self.next_seq_id -=1 # 전송 실패 시 ID 롤백
            self.debug_label.setText(f"Next ID will be: {self.next_seq_id}")
        except FileNotFoundError:
            err_msg = f"[CMD] Error: cmdUtil not found at {CMDUTIL_PATH}"
            print(err_msg)
            QMessageBox.critical(self, "Error", f"cmdUtil not found.\nPlease check path: {CMDUTIL_PATH}")
            self.next_seq_id -=1 # 전송 실패 시 ID 롤백
            self.debug_label.setText(f"Next ID will be: {self.next_seq_id}")
        except Exception as e_generic: # 그 외 예외
            err_msg = f"[CMD] Generic error sending message: {e_generic}"
            print(err_msg)
            QMessageBox.critical(self, "Error", f"Failed to send (Generic Error):\n{e_generic}")
            self.next_seq_id -=1 # 전송 실패 시 ID 롤백
            self.debug_label.setText(f"Next ID will be: {self.next_seq_id}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SendTextDialog()
    window.show()
    sys.exit(app.exec_())
