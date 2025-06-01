#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sample_app_tlm_page.py

“Sample App Telemetry Metrics” 창:
- sample_app_sent.csv: id, timestamp, text, sent_bits
- sample_app_recv.csv: id, timestamp, text, recv_bits

테이블 컬럼:
 [ID, Sent Timestamp, Sent Message, Recv Timestamp, Recv Message, RTT (ms), Status, Bit Error Rate (%)]

“Bit Error Rate”은 전송된 비트열(sent_bits)과 수신된 비트열(recv_bits)을
비트 단위로 비교하여 계산: (불일치 비트 수 / 총 전송 비트 수) × 100 (%)
"""

import sys
import csv
from pathlib import Path
from datetime import datetime

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QApplication, QDialog, QHeaderView, QPushButton,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QLabel, QMessageBox, QHBoxLayout, QWidget
)

class SampleAppTelemetryDialog(QDialog):
    BASE_GUI_DIR = Path(__file__).resolve().parent.parent / "cmdGui"
    SENT_CSV = BASE_GUI_DIR / "sample_app_sent.csv"
    RECV_CSV = BASE_GUI_DIR / "sample_app_recv.csv"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Sample App Telemetry Metrics")
        self.setMinimumSize(950, 550)

        main_layout = QVBoxLayout(self)

        # 1) 설명 라벨
        lbl = QLabel(
            "Sample App 전송·수신 매칭 결과 (ID 기준)\n"
            "- 테이블에 “Bit Error Rate(%)”을 추가했습니다.\n"
            "  (sent_bits vs. recv_bits 비교)"
        )
        main_layout.addWidget(lbl)

        # 2) 테이블 (8개 컬럼)
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "ID",
            "Sent Timestamp", "Sent Message",
            "Recv Timestamp", "Recv Message",
            "RTT (ms)", "Status", "Bit Error Rate (%)"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        main_layout.addWidget(self.table, stretch=1)

        # 3) 초기화 버튼
        btn_widget = QWidget()
        btn_layout = QHBoxLayout(btn_widget)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        self.btn_reset = QPushButton("초기화")
        self.btn_reset.clicked.connect(self.reset_all_data)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_reset)
        main_layout.addWidget(btn_widget)

        # 4) 초기 데이터 로드
        self.refresh_data()

    def refresh_data(self):
        """
        SENT_CSV, RECV_CSV를 읽어서 테이블을 갱신합니다.
        sent_bits vs recv_bits를 비교하여 “Bit Error Rate(%)” 계산 추가
        """
        # ─── 1) 전송 기록 읽기 ["id","timestamp","text","sent_bits"] ───
        sent_ts_dict = {}
        sent_text_dict = {}
        sent_bits_dict = {}
        if self.SENT_CSV.exists():
            with open(self.SENT_CSV, "r", newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        sid = int(row["id"])
                        ts = datetime.fromisoformat(row["timestamp"])
                        text = row.get("text", "")
                        bits = row.get("sent_bits", "")
                        sent_ts_dict[sid] = ts
                        sent_text_dict[sid] = text
                        sent_bits_dict[sid] = bits
                    except Exception:
                        continue

        # ─── 2) 수신 기록 읽기 ["id","timestamp","text","recv_bits"] ───
        recv_ts_dict = {}
        recv_text_dict = {}
        recv_bits_dict = {}
        if self.RECV_CSV.exists():
            with open(self.RECV_CSV, "r", newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        rid = int(row["id"])
                        rts = datetime.fromisoformat(row["timestamp"])
                        text = row.get("text", "")
                        bits = row.get("recv_bits", "")
                        if rid not in recv_ts_dict or rts < recv_ts_dict[rid]:
                            recv_ts_dict[rid] = rts
                            recv_text_dict[rid] = text
                            recv_bits_dict[rid] = bits
                    except Exception:
                        continue

        # ─── 3) 전송된 ID 리스트 기준으로 테이블에 삽입 ───
        all_ids = sorted(sent_ts_dict.keys())
        self.table.setRowCount(len(all_ids))

        for row_idx, sid in enumerate(all_ids):
            sent_ts = sent_ts_dict.get(sid)
            sent_text = sent_text_dict.get(sid, "")
            sent_bits = sent_bits_dict.get(sid, "")
            recv_ts = recv_ts_dict.get(sid, None)
            recv_text = recv_text_dict.get(sid, "")
            recv_bits = recv_bits_dict.get(sid, "")

            # 컬럼 0: ID
            self.table.setItem(row_idx, 0, QTableWidgetItem(str(sid)))

            # 컬럼 1: Sent Timestamp
            item_sent_ts = QTableWidgetItem(sent_ts.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3])
            self.table.setItem(row_idx, 1, item_sent_ts)

            # 컬럼 2: Sent Message
            item_sent_text = QTableWidgetItem(sent_text)
            self.table.setItem(row_idx, 2, item_sent_text)

            # 컬럼 3: Recv Timestamp (없으면 "-")
            if recv_ts:
                item_recv_ts = QTableWidgetItem(recv_ts.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3])
            else:
                item_recv_ts = QTableWidgetItem("-")
            self.table.setItem(row_idx, 3, item_recv_ts)

            # 컬럼 4: Recv Message (없으면 "-")
            if recv_text:
                item_recv_text = QTableWidgetItem(recv_text)
            else:
                item_recv_text = QTableWidgetItem("-")
            self.table.setItem(row_idx, 4, item_recv_text)

            # 컬럼 5: RTT (ms) 계산
            if recv_ts:
                delta_ms = int((recv_ts - sent_ts).total_seconds() * 1000)
                item_rtt = QTableWidgetItem(str(delta_ms))
            else:
                item_rtt = QTableWidgetItem("-")
            self.table.setItem(row_idx, 5, item_rtt)

            # 컬럼 6: Status ("OK" or "TIMEOUT")
            status = "OK" if recv_ts else "TIMEOUT"
            item_status = QTableWidgetItem(status)
            if status == "OK":
                item_status.setForeground(Qt.darkGreen)
            else:
                item_status.setForeground(Qt.red)
            self.table.setItem(row_idx, 6, item_status)

            # 컬럼 7: Bit Error Rate (%) 계산
            if recv_ts and sent_bits:
                total_bits = len(sent_bits)
                # 실제 수신된 recv_bits가 짧으면, 남은 비트는 모두 오류로 간주
                mismatches = 0
                min_len = min(len(sent_bits), len(recv_bits))
                for i in range(min_len):
                    if sent_bits[i] != recv_bits[i]:
                        mismatches += 1
                mismatches += abs(len(sent_bits) - len(recv_bits))
                if total_bits > 0:
                    err_rate = (mismatches / total_bits) * 100
                    item_err = QTableWidgetItem(f"{err_rate:.2f}")
                else:
                    item_err = QTableWidgetItem("-")
            else:
                item_err = QTableWidgetItem("-")
            self.table.setItem(row_idx, 7, item_err)

        self.table.resizeRowsToContents()

    def reset_all_data(self):
        """
        “초기화” 버튼 클릭 시 호출.
        sample_app_sent.csv와 sample_app_recv.csv를 헤더만 남기고 모두 비웁니다.
        """
        reply = QMessageBox.question(
            self,
            "초기화 확인",
            "송신·수신 기록을 모두 삭제하고 초기화하시겠습니까?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        # sample_app_sent.csv 헤더만 남기기 (id,timestamp,text,sent_bits)
        if self.SENT_CSV.exists():
            with open(self.SENT_CSV, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["id", "timestamp", "text", "sent_bits"])

        # sample_app_recv.csv 헤더만 남기기 (id,timestamp,text,recv_bits)
        if self.RECV_CSV.exists():
            with open(self.RECV_CSV, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["id", "timestamp", "text", "recv_bits"])

        # 테이블 갱신
        self.refresh_data()
        QMessageBox.information(self, "초기화 완료", "송수신 기록이 초기화되었습니다.")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    dlg = SampleAppTelemetryDialog()
    dlg.show()
    sys.exit(app.exec_())

