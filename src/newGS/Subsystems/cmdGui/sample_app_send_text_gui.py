#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sample_app_send_text_gui.py (수정본)

: 사용자 입력 텍스트를 보내기 전에 각 메시지에 고유 시퀀스 ID를 붙여서
  SAMPLE_APP으로 전송하고, ID·타임스탬프·원본 텍스트·전송 비트열을 sample_app_sent.csv에 기록합니다.

  - 기존 CSV가 없으면 헤더(id,timestamp,text,sent_bits)를 생성
  - 헤더가 빠졌으면 _ensure_header()에서 자동 삽입
  - sent_bits: raw_text를 UTF-8로 인코딩한 뒤, 각 바이트를 8비트 이진 문자열로 합친 문자열
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

    def _ensure_header(self):
        """
        sample_app_sent.csv가 존재하지만 헤더(id,timestamp,text,sent_bits)가 없는 경우
        파일 최상단에 헤더를 삽입합니다. 기존 행은 보존합니다.
        """
        if not SENT_CSV_PATH.exists():
            return

        with open(SENT_CSV_PATH, "r", newline="", encoding="utf-8") as f:
            first_line = f.readline().strip()

        # 올바른 헤더가 아니면 재작성
        if first_line != "id,timestamp,text,sent_bits":
            with open(SENT_CSV_PATH, "r", newline="", encoding="utf-8") as f:
                existing_rows = f.readlines()
            with open(SENT_CSV_PATH, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["id", "timestamp", "text", "sent_bits"])
                for line in existing_rows:
                    f.write(line)

    def _text_to_bitstring(self, raw_text: str) -> str:
        """
        raw_text(문자열)을 UTF-8로 인코딩한 뒤, 각 바이트를 8비트 이진 문자열로 변환하여 이어 붙인 문자열을 반환
        예: "A" → b'\x41' → "01000001"
        """
        utf8_bytes = raw_text.encode("utf-8", errors="ignore")
        bits = "".join(f"{byte:08b}" for byte in utf8_bytes)
        return bits

    def _append_to_sent_csv(self, seq_id, timestamp, text):
        """
        sample_app_sent.csv에 [seq_id, timestamp, text, sent_bits]를 한 줄 추가.
        파일이 없으면 헤더(id,timestamp,text,sent_bits)부터 생성.
        """
        sent_bits = self._text_to_bitstring(text)

        # 1) 파일이 없으면 헤더부터 생성
        if not SENT_CSV_PATH.exists():
            with open(SENT_CSV_PATH, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["id", "timestamp", "text", "sent_bits"])
                writer.writerow([seq_id, timestamp, text, sent_bits])
            return

        # 2) 파일이 존재하지만 헤더가 올바르지 않을 수 있으므로 보장
        self._ensure_header()

        # 3) 한 줄 추가
        with open(SENT_CSV_PATH, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([seq_id, timestamp, text, sent_bits])

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

            # 5) sample_app_sent.csv에 [id, timestamp, text, sent_bits] 기록
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

