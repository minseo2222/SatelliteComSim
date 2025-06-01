#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sample_app_tlm_page.py (Cyber-Aware 및 개선된 최종 버전 + Attack Type 표시)

- CSV 컬럼명 가정 (test1.py, test4.py와 일치 필요):
  - Sent: id, timestamp, text_representation, core_message_bits, attack_type
  - Recv: id, timestamp, text_representation, core_message_bits
- 이 GUI에서 BER 및 Status를 직접 계산하여 표시.
- 타임스탬프는 UTC ISO8601 형식("Z" 접미사 포함)으로 가정하고 파싱.
- "Attack Type" 컬럼 추가.
"""

import sys
import csv
from pathlib import Path
from datetime import datetime, timezone

from PyQt5.QtCore import Qt, QTimer
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
        self.setWindowTitle("Sample App Telemetry Metrics (Cyber-Aware & BER Calculated)")
        self.setMinimumSize(1150, 600) # 창 크기 약간 더 늘림 (Attack Type 컬럼 위해)

        main_layout = QVBoxLayout(self)

        lbl = QLabel(
            "Sample App 전송·수신 매칭 결과 (ID 기준)\n"
            "- GUI에서 직접 BER(%)을 계산하고, Status 및 Attack Type 상태를 통해 통신 품질 및 보안 진단을 수행합니다."
        )
        main_layout.addWidget(lbl)

        self.table = QTableWidget()
        self.table.setColumnCount(9) # 수정: 컬럼 수 9개로 변경
        self.table.setHorizontalHeaderLabels([
            "ID",
            "Sent Timestamp (UTC)", "Sent Message",
            "Recv Timestamp (UTC)", "Recv Message",
            "RTT (ms)", "Status", "BER (%)",
            "Attack Type" # 새로운 컬럼 추가
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch) # 기본 스트레치
        # 특정 컬럼들은 내용에 따라 크기 조절 가능하도록 Interactive 설정
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Interactive) # Sent Timestamp
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Interactive) # Sent Message
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Interactive) # Recv Timestamp
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Interactive) # Recv Message
        self.table.horizontalHeader().setSectionResizeMode(8, QHeaderView.Interactive) # Attack Type
        
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
        if not ts_str:
            return None
        try:
            if ts_str.endswith('Z'):
                ts_obj = datetime.fromisoformat(ts_str[:-1] + '+00:00')
            else:
                ts_obj = datetime.fromisoformat(ts_str)
            return ts_obj.astimezone(timezone.utc)
        except ValueError:
            print(f"[WARN] Could not parse timestamp string: {ts_str}")
            return None

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
                            sid = sid_str
                            
                            ts_obj = self.parse_timestamp(row.get("timestamp", ""))
                            text_repr = row.get("text_representation", "")
                            core_bits = row.get("core_message_bits", "")
                            attack_type = row.get("attack_type", "none") # attack_type 읽기

                            sent_data_map[sid] = {
                                "timestamp": ts_obj, "text_repr": text_repr,
                                "core_bits": core_bits, "attack_type": attack_type # 맵에 저장
                            }
                        except (ValueError, KeyError) as e:
                            print(f"[WARN] SENT_CSV: Skipping row {row_num} (ID:'{sid_str}') due to {type(e).__name__}: {row} - {e}")
                        except Exception as e:
                            print(f"[ERROR] SENT_CSV: Unexpected error on row {row_num}: {row} - {e}")
            except Exception as e:
                print(f"[ERROR] Failed to read SENT_CSV ({self.SENT_CSV}): {e}")

        recv_data_map = {}
        if self.RECV_CSV.exists():
            try:
                with open(self.RECV_CSV, "r", newline="", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for row_num, row in enumerate(reader, 1):
                        try:
                            rid_str = row.get("id", "").strip()
                            if not rid_str: continue
                            rid = rid_str

                            ts_obj = self.parse_timestamp(row.get("timestamp", ""))
                            text_repr = row.get("text_representation", "")
                            core_bits = row.get("core_message_bits", "")

                            recv_data_map[rid] = {
                                "timestamp": ts_obj, "text_repr": text_repr,
                                "core_bits": core_bits
                            }
                        except (ValueError, KeyError) as e:
                            print(f"[WARN] RECV_CSV: Skipping row {row_num} (ID:'{rid_str}') due to {type(e).__name__}: {row} - {e}")
                        except Exception as e:
                            print(f"[ERROR] RECV_CSV: Unexpected error on row {row_num}: {row} - {e}")
            except Exception as e:
                 print(f"[ERROR] Failed to read RECV_CSV ({self.RECV_CSV}): {e}")

        def sort_key(item_id_str):
            try: return int(item_id_str)
            except ValueError: return float('inf') 
        
        all_sids = sorted(sent_data_map.keys(), key=sort_key)
        self.table.setRowCount(0)
        self.table.setRowCount(len(all_sids))

        for row_idx, sid in enumerate(all_sids):
            sent_entry = sent_data_map.get(sid)
            recv_entry = recv_data_map.get(sid)

            sent_ts_obj = sent_entry.get("timestamp")
            sent_text = sent_entry.get("text_repr", "")
            sent_bits = sent_entry.get("core_bits", "")
            attack_type = sent_entry.get("attack_type", "none") # attack_type 가져오기

            display_ts_format = "%Y-%m-%d %H:%M:%S.%f"
            
            item_sid = QTableWidgetItem(str(sid))
            item_sent_ts_str = sent_ts_obj.strftime(display_ts_format)[:-3] + " Z" if sent_ts_obj else "-"
            item_sent_ts = QTableWidgetItem(item_sent_ts_str)
            item_sent_text = QTableWidgetItem(sent_text)
            
            self.table.setItem(row_idx, 0, item_sid)
            self.table.setItem(row_idx, 1, item_sent_ts)
            self.table.setItem(row_idx, 2, item_sent_text)

            recv_ts_obj = None; recv_text = ""; recv_bits = "";

            if recv_entry:
                recv_ts_obj = recv_entry.get("timestamp")
                recv_text = recv_entry.get("text_repr", "")
                recv_bits = recv_entry.get("core_bits", "")

            item_recv_ts_str = recv_ts_obj.strftime(display_ts_format)[:-3] + " Z" if recv_ts_obj else "-"
            item_recv_ts = QTableWidgetItem(item_recv_ts_str)
            item_recv_text = QTableWidgetItem(recv_text if recv_entry else "-")
            self.table.setItem(row_idx, 3, item_recv_ts)
            self.table.setItem(row_idx, 4, item_recv_text)

            if sent_ts_obj and recv_ts_obj:
                try:
                    delta = recv_ts_obj - sent_ts_obj
                    delta_ms = int(delta.total_seconds() * 1000)
                    item_rtt = QTableWidgetItem(str(delta_ms))
                except Exception: item_rtt = QTableWidgetItem("Calc Error")
            else: item_rtt = QTableWidgetItem("-")
            self.table.setItem(row_idx, 5, item_rtt)

            final_status_str = "UNKNOWN"; status_color = Qt.black; calculated_ber_val = -1.0
            ber_to_display = "-"

            if not recv_entry:
                final_status_str = "LOST"; status_color = Qt.blue
            else:
                if sent_bits and recv_bits:
                    if len(sent_bits) == len(recv_bits):
                        errors = sum(1 for s_bit, r_bit in zip(sent_bits, recv_bits) if s_bit != r_bit)
                        if len(sent_bits) > 0: calculated_ber_val = errors / len(sent_bits)
                        else: calculated_ber_val = 0.0 if errors == 0 else -1.0 

                        if calculated_ber_val == 0.0:
                            final_status_str = "OK"; status_color = Qt.darkGreen
                        elif calculated_ber_val > 0.0:
                            final_status_str = f"CORRUPTED (BER)"; status_color = Qt.darkOrange
                    else: 
                        final_status_str = "ERROR (Length Mismatch)"; status_color = Qt.magenta
                else: 
                    final_status_str = "RECEIVED (No BER Data)"; status_color = Qt.darkGray

            item_status = QTableWidgetItem(final_status_str)
            item_status.setForeground(status_color)
            self.table.setItem(row_idx, 6, item_status)

            if calculated_ber_val >= 0.0: 
                ber_to_display = f"{calculated_ber_val*100:.2f}"
            
            item_ber = QTableWidgetItem(ber_to_display)
            if ber_to_display != "-":
                try:
                    ber_float_for_color = float(ber_to_display) / 100.0
                    if ber_float_for_color > 0.01 : item_ber.setForeground(Qt.red)
                    elif ber_float_for_color > 0 : item_ber.setForeground(Qt.darkOrange)
                except ValueError: pass
            self.table.setItem(row_idx, 7, item_ber)

            # Attack Type 컬럼 채우기
            item_attack_type = QTableWidgetItem(attack_type if attack_type and attack_type != "none" else "-")
            if attack_type and attack_type != "none":
                item_attack_type.setForeground(Qt.red) 
                item_attack_type.setToolTip(f"Attack Mode: {attack_type}")
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
