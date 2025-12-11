#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sample_app_tlm_page.py (Hybrid Matching Version)

기능:
  1. 1차 매칭: 텍스트 ID (id 컬럼) 일치 여부
  2. 2차 매칭: ID가 깨진 경우, 전송 시간(ts) 기준 2초 내 응답 패킷 매칭
  3. BER 계산: 비트 단위 비교
  4. 상태 판정: OK / CORRUPTED / LOST
"""

import sys
import csv
from pathlib import Path
from datetime import datetime, timedelta

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QApplication, QDialog, QHeaderView, QPushButton,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QLabel, QMessageBox, QHBoxLayout, QWidget
)

# 파일 경로 설정
CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parents[1]  # newGS 폴더
LOG_DIR = PROJECT_ROOT / "log"
SENT_CSV = LOG_DIR / "sample_app_sent.csv"
RECV_CSV = LOG_DIR / "sample_app_recv.csv"

# 색상 정의
COLOR_LOST = QColor(255, 80, 80)       # 빨강 (분실)
COLOR_OK = QColor(50, 205, 50)         # 녹색 (정상)
COLOR_CORRUPT = QColor(255, 140, 0)    # 주황 (내용 깨짐)
COLOR_GRAY = Qt.darkGray

DISPLAY_TS_FMT = "%H:%M:%S"

def _read_csv_rows(csv_path: Path):
    rows = []
    if not csv_path.exists(): return rows
    try:
        with open(csv_path, "r", encoding="utf-8", newline="") as f:
            sample = f.read(2048); f.seek(0)
            try: dialect = csv.Sniffer().sniff(sample, delimiters=",\t;")
            except: dialect = csv.excel
            reader = csv.DictReader(f, dialect=dialect)
            for row in reader: rows.append(row)
    except Exception as e:
        print(f"[ERROR] CSV Read Failed {csv_path}: {e}")
    return rows

class SampleAppTelemetryDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Sample App Telemetry (Hybrid Matching)")
        self.setMinimumSize(1200, 650)

        layout = QVBoxLayout(self)

        info_lbl = QLabel(
            "<b>[하이브리드 매칭 및 정량 평가]</b><br>"
            "- <b>1단계(ID):</b> 메시지 ID가 일치하면 매칭<br>"
            "- <b>2단계(시간):</b> ID가 깨졌을 경우(재밍 등), 전송 후 2초 내 도착한 패킷과 매칭<br>"
            "- <b>BER:</b> 송신 데이터와 수신 데이터의 비트 차이를 백분율로 표시"
        )
        layout.addWidget(info_lbl)

        self.table = QTableWidget()
        cols = ["Sent ID", "Sent Time", "Sent Msg", "Recv Time", "Recv Msg", "RTT(ms)", "Status", "BER(%)"]
        self.table.setColumnCount(len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(4, QHeaderView.Stretch)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.table)

        btn_box = QHBoxLayout()
        self.btn_refresh = QPushButton("새로고침")
        self.btn_refresh.clicked.connect(self.refresh_data)
        self.btn_reset = QPushButton("로그 초기화")
        self.btn_reset.clicked.connect(self.reset_all_data)
        self.btn_reset.setStyleSheet("background-color: #ffdddd;")
        btn_box.addStretch()
        btn_box.addWidget(self.btn_refresh)
        btn_box.addWidget(self.btn_reset)
        layout.addLayout(btn_box)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_data)
        self.timer.start(2000)

        self.refresh_data()

    def _parse_ts(self, s: str):
        if not s: return None
        try: return datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
        except: return None

    def refresh_data(self):
        sent_rows = _read_csv_rows(SENT_CSV)
        recv_rows = _read_csv_rows(RECV_CSV)

        # 1. 데이터 전처리 (리스트 변환)
        sent_list = []
        for row in sent_rows:
            if row.get("direction") != "sent": continue
            if "1882" not in row.get("mid_hex", "").lower(): continue # Command Filter
            ts = self._parse_ts(row.get("ts"))
            if not ts: continue
            
            bits = row.get("bits", "")
            if bits.startswith("b:"): bits = bits[2:]
            
            sent_list.append({
                "row": row, "ts": ts, "id": row.get("id", ""), "bits": bits, "matched": False
            })

        recv_list = []
        for row in recv_rows:
            if row.get("direction") != "recv": continue
            mid = (row.get("mid_hex") or row.get("sid_hex") or "").lower()
            if "08a9" not in mid: continue # Telemetry Filter
            ts = self._parse_ts(row.get("ts"))
            if not ts: continue
            
            bits = row.get("bits", "")
            if bits.startswith("b:"): bits = bits[2:]

            recv_list.append({
                "row": row, "ts": ts, "id": row.get("id", ""), "bits": bits, "matched": False
            })

        # 2. 매칭 로직 (Hybrid)
        results = [] # 최종 출력용 리스트

        # Step A: ID 기반 매칭 (신뢰도 높음)
        for s in sent_list:
            if s["matched"]: continue
            if not s["id"]: continue # ID가 없으면 패스

            for r in recv_list:
                if r["matched"]: continue
                # ID가 일치하고, 시간이 같거나 늦은 경우
                if r["id"] == s["id"] and r["ts"] >= s["ts"]:
                    s["matched"] = True
                    r["matched"] = True
                    results.append((s, r))
                    break
        
        # Step B: 시간 기반 매칭 (ID가 깨진 경우, RTT 윈도우 2초)
        for s in sent_list:
            if s["matched"]: continue
            
            best_r = None
            min_diff = 999999
            
            for r in recv_list:
                if r["matched"]: continue
                
                # 송신 시간 이후, 2초 이내 도착
                diff = (r["ts"] - s["ts"]).total_seconds()
                if 0 <= diff <= 2.0:
                    if diff < min_diff:
                        min_diff = diff
                        best_r = r
            
            if best_r:
                s["matched"] = True
                best_r["matched"] = True
                results.append((s, best_r))
            else:
                # 매칭 실패 -> Lost
                results.append((s, None))

        # (옵션) 매칭되지 않은 수신 패킷 (Recv Only) 처리
        # for r in recv_list:
        #     if not r["matched"]: results.append((None, r))

        # 3. 정렬 (Sent Time 기준)
        results.sort(key=lambda x: x[0]["ts"] if x[0] else x[1]["ts"])

        # 4. 테이블 출력
        self.table.setRowCount(len(results))
        for idx, (s, r) in enumerate(results):
            # Sent Info
            if s:
                self.table.setItem(idx, 0, QTableWidgetItem(s["id"]))
                self.table.setItem(idx, 1, QTableWidgetItem(s["ts"].strftime(DISPLAY_TS_FMT)))
                self.table.setItem(idx, 2, QTableWidgetItem(s["row"].get("text", "")))
            else:
                self.table.setItem(idx, 0, QTableWidgetItem("-")) # Recv Only

            # Recv Info
            if r:
                self.table.setItem(idx, 3, QTableWidgetItem(r["ts"].strftime(DISPLAY_TS_FMT)))
                self.table.setItem(idx, 4, QTableWidgetItem(r["row"].get("text", "")))
            else:
                self.table.setItem(idx, 3, QTableWidgetItem("-"))
                self.table.setItem(idx, 4, QTableWidgetItem("-"))

            # RTT & Status
            status, color, ber_str, rtt_str = "-", Qt.black, "-", "-"

            if s and r:
                rtt_str = f"{(r['ts'] - s['ts']).total_seconds()*1000:.0f}"
                
                # BER Calc
                sb, rb = s["bits"], r["bits"]
                min_len = min(len(sb), len(rb))
                # 비트 차이 계산
                err_bits = sum(1 for i in range(min_len) if sb[i] != rb[i])
                # 길이 차이도 에러로 포함
                err_bits += abs(len(sb) - len(rb))
                total_len = max(len(sb), len(rb))
                
                if err_bits == 0:
                    status = "OK"
                    color = COLOR_OK
                    ber_str = "0.00 %"
                else:
                    status = "CORRUPTED" # 매칭은 됐지만 내용 다름
                    color = COLOR_CORRUPT
                    ber = (err_bits / total_len) * 100 if total_len > 0 else 0
                    ber_str = f"{ber:.2f} %"
            
            elif s and not r:
                status = "LOST"
                color = COLOR_LOST
            elif not s and r:
                status = "RECV ONLY"
                color = COLOR_GRAY

            self.table.setItem(idx, 5, QTableWidgetItem(rtt_str))
            
            st_item = QTableWidgetItem(status)
            st_item.setForeground(color); st_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(idx, 6, st_item)
            
            ber_item = QTableWidgetItem(ber_str)
            ber_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(idx, 7, ber_item)

    def reset_all_data(self):
        reply = QMessageBox.question(self, "초기화", "로그를 초기화하시겠습니까?", QMessageBox.Yes | QMessageBox.No)
        if reply != QMessageBox.Yes: return
        try:
            # Seq 포함된 헤더로 초기화
            header = ["ts","direction","id","text","mid_hex","apid_hex","cc_dec",
                      "seq","len","src_ip","src_port","head_hex16","text_hex","bits"]
            for p in [SENT_CSV, RECV_CSV]:
                with open(p, "w", newline="", encoding="utf-8") as f:
                    csv.writer(f).writerow(header)
            self.refresh_data()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

if __name__ == "__main__":
    app = QApplication(sys.argv)
    dlg = SampleAppTelemetryDialog()
    dlg.show()
    sys.exit(app.exec_())
