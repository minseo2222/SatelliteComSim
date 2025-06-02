#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sample_app_tlm_page.py (최종 + Status와 BER 계산 분리, 부분 BER 계산, QColor 사용)

- CSV 컬럼명 가정:
  - Sent: id, timestamp, text_representation, core_message_bits, attack_type
  - Recv: id, timestamp, text_representation, core_message_bits
- 이 GUI에서 BER 및 Status를 직접 계산하여 표시.
- 송수신 비트열 길이 불일치 시, 짧은 쪽 기준으로 BER 계산하고 표시.
- Qt.darkOrange 대신 QColor(255, 140, 0) 사용.
"""

import sys
import csv
from pathlib import Path
from datetime import datetime, timezone

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor # QColor 임포트 추가
from PyQt5.QtWidgets import (
    QApplication, QDialog, QHeaderView, QPushButton,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QLabel, QMessageBox, QHBoxLayout, QWidget
)

class SampleAppTelemetryDialog(QDialog):
    BASE_GUI_DIR = Path(__file__).resolve().parent.parent / "cmdGui"
    SENT_CSV = BASE_GUI_DIR / "sample_app_sent.csv"
    RECV_CSV = BASE_GUI_DIR / "sample_app_recv.csv"

    DARK_ORANGE_COLOR = QColor(255, 140, 0) # 사용자 정의 어두운 주황색

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Sample App Telemetry Metrics (BER Calculated, QColor Fix)")
        self.setMinimumSize(1150, 600)

        main_layout = QVBoxLayout(self)
        lbl = QLabel(
            "Sample App 전송·수신 매칭 결과 (ID 기준)\n"
            "- GUI에서 직접 BER(%)을 계산하고, Status 및 Attack Type 상태를 통해 통신 품질 및 보안 진단을 수행합니다.\n"
            "- 송수신 메시지 길이 불일치 시, 짧은 쪽 기준으로 BER을 계산하여 참고용으로 표시합니다."
        )
        main_layout.addWidget(lbl)

        self.table = QTableWidget()
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels([
            "ID", "Sent Timestamp (UTC)", "Sent Message",
            "Recv Timestamp (UTC)", "Recv Message", "RTT (ms)",
            "Status", "BER (%)", "Attack Type"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        for col_idx in [1, 2, 3, 4, 8]: 
            self.table.horizontalHeader().setSectionResizeMode(col_idx, QHeaderView.Interactive)
        
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        main_layout.addWidget(self.table, stretch=1)

        btn_widget = QWidget()
        btn_layout = QHBoxLayout(btn_widget)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        self.btn_refresh = QPushButton("새로고침")
        self.btn_refresh.clicked.connect(self.refresh_data)
        self.btn_reset = QPushButton("기록 초기화")
        self.btn_reset.clicked.connect(self.reset_all_data)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_refresh)
        btn_layout.addWidget(self.btn_reset)
        main_layout.addWidget(btn_widget)

        self.refresh_data()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_data)
        self.timer.start(5000)

    def parse_timestamp(self, ts_str):
        if not ts_str: return None
        try:
            return datetime.fromisoformat(ts_str.replace('Z', '+00:00')).astimezone(timezone.utc)
        except ValueError:
            print(f"[WARN] Could not parse timestamp string: {ts_str}"); return None

    def refresh_data(self):
        print("[INFO] Refreshing telemetry data...")
        sent_data_map = {} 
        if self.SENT_CSV.exists():
            try:
                with open(self.SENT_CSV, "r", newline="", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for row_num, row in enumerate(reader, 1):
                        try:
                            sid_str = row.get("id", "").strip()
                            if not sid_str: continue
                            sent_data_map[sid_str] = {
                                "timestamp": self.parse_timestamp(row.get("timestamp", "")),
                                "text_repr": row.get("text_representation", ""),
                                "core_bits": row.get("core_message_bits", ""),
                                "attack_type": row.get("attack_type", "none")
                            }
                        except (ValueError, KeyError) as e: print(f"[WARN] SENT_CSV: Skipping row {row_num} (ID:'{sid_str}') due to {type(e).__name__}: {row} - {e}")
                        except Exception as e: print(f"[ERROR] SENT_CSV: Unexpected error on row {row_num}: {row} - {e}")
            except Exception as e: print(f"[ERROR] Failed to read SENT_CSV ({self.SENT_CSV}): {e}")

        recv_data_map = {}
        if self.RECV_CSV.exists():
            try:
                with open(self.RECV_CSV, "r", newline="", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for row_num, row in enumerate(reader, 1):
                        try:
                            rid_str = row.get("id", "").strip()
                            if not rid_str: continue
                            recv_data_map[rid_str] = {
                                "timestamp": self.parse_timestamp(row.get("timestamp", "")),
                                "text_repr": row.get("text_representation", ""),
                                "core_bits": row.get("core_message_bits", "")
                            }
                        except (ValueError, KeyError) as e: print(f"[WARN] RECV_CSV: Skipping row {row_num} (ID:'{rid_str}') due to {type(e).__name__}: {row} - {e}")
                        except Exception as e: print(f"[ERROR] RECV_CSV: Unexpected error on row {row_num}: {row} - {e}")
            except Exception as e: print(f"[ERROR] Failed to read RECV_CSV ({self.RECV_CSV}): {e}")

        def sort_key(item_id_str):
            try: return int(item_id_str)
            except ValueError: return float('inf') 
        
        all_sids = sorted(sent_data_map.keys(), key=sort_key)
        self.table.setRowCount(0)
        self.table.setRowCount(len(all_sids))

        for row_idx, sid in enumerate(all_sids):
            sent_entry = sent_data_map.get(sid, {})
            recv_entry = recv_data_map.get(sid, {})

            sent_ts_obj = sent_entry.get("timestamp"); sent_text = sent_entry.get("text_repr", "");
            sent_bits = sent_entry.get("core_bits", ""); attack_type = sent_entry.get("attack_type", "none")
            
            display_ts_format = "%Y-%m-%d %H:%M:%S.%f"
            
            self.table.setItem(row_idx, 0, QTableWidgetItem(str(sid)))
            self.table.setItem(row_idx, 1, QTableWidgetItem(sent_ts_obj.strftime(display_ts_format)[:-3] + " Z" if sent_ts_obj else "-"))
            self.table.setItem(row_idx, 2, QTableWidgetItem(sent_text))

            recv_ts_obj = recv_entry.get("timestamp"); recv_text = recv_entry.get("text_repr", ""); recv_bits = recv_entry.get("core_bits", "")

            self.table.setItem(row_idx, 3, QTableWidgetItem(recv_ts_obj.strftime(display_ts_format)[:-3] + " Z" if recv_ts_obj else "-"))
            self.table.setItem(row_idx, 4, QTableWidgetItem(recv_text if recv_entry else "-"))

            item_rtt = QTableWidgetItem("-")
            if sent_ts_obj and recv_ts_obj:
                try: item_rtt.setText(str(int((recv_ts_obj - sent_ts_obj).total_seconds() * 1000)))
                except Exception: item_rtt.setText("Calc Error")
            self.table.setItem(row_idx, 5, item_rtt)

            calculated_ber_val = -1.0 
            ber_to_display = "-"
            length_mismatch_for_ber = False

            if sent_bits and recv_bits:
                len_sent = len(sent_bits); len_recv = len(recv_bits)
                length_for_ber_calc = 0
                if len_sent == len_recv: length_for_ber_calc = len_sent
                else: 
                    length_for_ber_calc = min(len_sent, len_recv)
                    length_mismatch_for_ber = True
                    print(f"[WARN] BER Calc: Length mismatch for ID {sid}. Sent: {len_sent} bits, Recv: {len_recv} bits. Comparing up to {length_for_ber_calc} bits.")
                
                if length_for_ber_calc > 0:
                    errors = sum(1 for i in range(length_for_ber_calc) if sent_bits[i] != recv_bits[i])
                    calculated_ber_val = errors / length_for_ber_calc
                elif len_sent == 0 and len_recv == 0: calculated_ber_val = 0.0
            
            if calculated_ber_val >= 0.0:
                ber_to_display = f"{calculated_ber_val*100:.2f}"
                if length_mismatch_for_ber: ber_to_display += " (Partial)"

            item_ber = QTableWidgetItem(ber_to_display)
            if ber_to_display != "-":
                try:
                    ber_float_for_color = float(ber_to_display.replace(" (Partial)","")) / 100.0
                    if ber_float_for_color > 0.01 : item_ber.setForeground(Qt.red)
                    elif ber_float_for_color > 0 : item_ber.setForeground(self.DARK_ORANGE_COLOR) # 수정: QColor 사용
                except ValueError: pass
            self.table.setItem(row_idx, 7, item_ber)

            final_status_str = "UNKNOWN"; status_color = Qt.black
            if not recv_entry:
                final_status_str = "LOST"; status_color = Qt.blue
            else: 
                if not (sent_bits and recv_bits) : 
                     final_status_str = "RECEIVED (Partial Data for BER)"; status_color = Qt.darkGray
                elif length_mismatch_for_ber: 
                    final_status_str = "ERROR (Length Mismatch)"; status_color = Qt.magenta
                elif calculated_ber_val == 0.0:
                    final_status_str = "OK"; status_color = Qt.darkGreen
                elif calculated_ber_val > 0.0:
                    final_status_str = "CORRUPTED (BER)"; status_color = self.DARK_ORANGE_COLOR # 수정: QColor 사용
                else: 
                    final_status_str = "ERROR (BER Calc)"; status_color = Qt.red
            
            item_status = QTableWidgetItem(final_status_str)
            item_status.setForeground(status_color)
            self.table.setItem(row_idx, 6, item_status)

            item_attack_type = QTableWidgetItem(attack_type if attack_type and attack_type != "none" else "-")
            if attack_type and attack_type != "none":
                item_attack_type.setForeground(Qt.red) 
                item_attack_type.setToolTip(f"Attack Mode on Sent: {attack_type}")
            self.table.setItem(row_idx, 8, item_attack_type)

        self.table.resizeRowsToContents()
        self.table.scrollToBottom()

    def reset_all_data(self):
        reply = QMessageBox.question(
            self, "초기화 확인",
            "송신·수신 기록(CSV 파일)을 모두 삭제하고 초기화하시겠습니까?\n\n"
            f"송신 파일: {self.SENT_CSV}\n"
            f"수신 파일: {self.RECV_CSV}",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply != QMessageBox.Yes: return

        sent_header = ["id", "timestamp", "text_representation", "core_message_bits", "attack_type"]
        recv_header = ["id", "timestamp", "text_representation", "core_message_bits"] 

        try:
            for csv_path, header in [(self.SENT_CSV, sent_header), (self.RECV_CSV, recv_header)]:
                csv_path.parent.mkdir(parents=True, exist_ok=True)
                with open(csv_path, "w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow(header)
            
            self.refresh_data()
            QMessageBox.information(self, "초기화 완료", "송수신 기록이 초기화되었습니다.")
        except Exception as e:
            QMessageBox.critical(self, "초기화 오류", f"파일 초기화 중 오류 발생:\n{e}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    dlg = SampleAppTelemetryDialog()
    dlg.show()
    sys.exit(app.exec_())
