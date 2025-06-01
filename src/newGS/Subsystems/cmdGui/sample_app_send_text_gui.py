#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sample_app_send_text_gui.py (수정본)

: 사용자 입력 텍스트를 보내기 전에 각 메시지에 고유 시퀀스 ID를 붙여서
  SAMPLE_APP으로 전송하고, ID·타임스탬프·원본 텍스트를 sample_app_sent.csv에 기록합니다.

1) sample_app_sent.csv:
     파일이 없으면 새로 생성. 헤더: id,timestamp,text
     각 행: 시퀀스ID(정수), 전송 시각(ISO 8601), 원본 텍스트 (CSV escape 처리됨)
2) 실제 전송할 때는 "<ID>:<원본문자열>" 포맷을 사용
3) 기존 SentCommandLogs.txt에도 간단 로그 남김
"""

import sys
import subprocess
import csv
from pathlib import Path
from datetime import datetime

from PyQt5.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QLabel,
    QTextEdit, QPushButton, QMessageBox
)

ROOTDIR       = Path(__file__).resolve().parent
CMDUTIL_PATH  = (ROOTDIR / "../cmdUtil/cmdUtil").resolve()
SENT_CSV_PATH = ROOTDIR / "sample_app_sent.csv"
LOG_PATH      = ROOTDIR / "SentCommandLogs.txt"

class SendTextDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Send Text to Sample App")
        self.setGeometry(100, 100, 400, 200)

        layout = QVBoxLayout()
        self.label       = QLabel("Enter message to send to SAMPLE_APP:")
        self.text_edit   = QTextEdit()
        self.send_button = QPushButton("Send")

        layout.addWidget(self.label)
        layout.addWidget(self.text_edit)
        layout.addWidget(self.send_button)
        self.setLayout(layout)

        self.send_button.clicked.connect(self.send_command)

    def _get_next_id(self):
        """
        sample_app_sent.csv 파일을 읽어서, 'id' 열의 마지막 값을 찾아
        그 값 + 1 을 반환. (파일이 없거나 비어 있으면 1 반환)
        """
        if not SENT_CSV_PATH.exists():
            return 1
        try:
            with open(SENT_CSV_PATH, "r", newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                last_id = 0
                for row in reader:
                    try:
                        rid = int(row.get("id", "0"))
                        if rid > last_id:
                            last_id = rid
                    except ValueError:
                        continue
                return last_id + 1
        except Exception:
            # CSV 파일 읽기 오류가 발생하면, 일단 1부터 시작
            return 1

    def _append_to_sent_csv(self, seq_id, timestamp, text):
        """
        sample_app_sent.csv에 [seq_id, timestamp, text]를 한 줄 추가.
        CSV 파일이 없으면 헤더(id,timestamp,text)부터 생성.
        """
        write_header = not SENT_CSV_PATH.exists()
        with open(SENT_CSV_PATH, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if write_header:
                writer.writerow(["id", "timestamp", "text"])
            writer.writerow([seq_id, timestamp, text])

    def send_command(self):
        raw_text = self.text_edit.toPlainText().strip()
        if not raw_text:
            QMessageBox.warning(self, "Input Error", "Please enter text before sending.")
            return

        # 1) 새로운 시퀀스 ID 생성
        seq_id = self._get_next_id()
        # 2) 현재 시각(ISO 8601)
        timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]
        # 3) 실제 보낼 문자열: "<ID>:<원본문자열>"
        text_to_send = f"{seq_id}:{raw_text}"

        # UdpCommands 실행 커맨드
        cmd = [
            str(CMDUTIL_PATH),
            "--host=127.0.0.1",
            "--port=50000",
            "--pktid=0x18A8",       # SAMPLE_APP_CMD_MID
            "--cmdcode=10",         # SAMPLE_APP_SEND_TEXT_CC
            f"--string=128:{text_to_send}"
        ]

        try:
            # 4) 실제 전송
            subprocess.run(cmd, check=True)

            # 5) sample_app_sent.csv에 [id, timestamp, 원본:raw_text] 기록
            self._append_to_sent_csv(seq_id, timestamp, raw_text)

            # 6) SentCommandLogs.txt에도 간단 로그 기록
            log_msg = f"[{timestamp}] SAMPLE_APP SEND_TEXT (ID={seq_id}): \"{raw_text}\""
            with open(LOG_PATH, "a", encoding="utf-8") as log_file:
                log_file.write(log_msg + "\n")

            # 7) GroundSystem 콘솔에도 출력
            print(f"[CMD] {log_msg}")

            QMessageBox.information(self, "Success", f"Message sent successfully! (ID={seq_id})")
            self.text_edit.clear()

        except subprocess.CalledProcessError as e:
            err_msg = f"[CMD] Error sending message: {e}"
            print(err_msg)
            QMessageBox.critical(self, "Error", f"Failed to send:\n{e}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SendTextDialog()
    window.show()
    sys.exit(app.exec_())

