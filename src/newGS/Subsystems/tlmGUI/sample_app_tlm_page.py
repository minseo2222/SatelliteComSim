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
import io
import difflib
from pathlib import Path
from datetime import datetime, timedelta

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QApplication, QDialog, QHeaderView, QPushButton,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QLabel, QMessageBox, QHBoxLayout, QWidget,
    QPlainTextEdit, QDialogButtonBox, QFormLayout
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

def _hex_to_bytes(hex_str: str) -> bytes:
    s = (hex_str or "").strip()
    if not s:
        return b""
    try:
        return bytes.fromhex(s)
    except ValueError:
        return b""

def _bits_str_to_bytes(bits: str) -> bytes:
    s = (bits or "").strip()
    if s.startswith("b:"):
        s = s[2:]
    if not s:
        return b""
    if len(s) % 8 != 0 or any(ch not in "01" for ch in s):
        return b""
    return bytes(int(s[i:i+8], 2) for i in range(0, len(s), 8))

def _payload_bytes_from_row(row: dict) -> bytes:
    data = _hex_to_bytes(row.get("payload_hex", ""))
    if data:
        return data
    data = _hex_to_bytes(row.get("text_hex", ""))
    if data:
        return data
    return _bits_str_to_bytes(row.get("payload_bits") or row.get("bits", ""))

def _bit_error_stats(sent_bytes: bytes, recv_bytes: bytes):
    common = min(len(sent_bytes), len(recv_bytes))
    err_bits = 0
    for i in range(common):
        err_bits += bin(sent_bytes[i] ^ recv_bytes[i]).count("1")
    if len(sent_bytes) > common:
        err_bits += (len(sent_bytes) - common) * 8
    if len(recv_bytes) > common:
        err_bits += (len(recv_bytes) - common) * 8
    total_bits = max(len(sent_bytes), len(recv_bytes)) * 8
    return err_bits, total_bits

def _text_similarity(sent_text: str, recv_text: str) -> float:
    return difflib.SequenceMatcher(None, sent_text or "", recv_text or "").ratio() * 100.0

def _bytes_to_grouped_bits(data: bytes, group=8, line_bytes=8) -> str:
    if not data:
        return "(empty)"
    rows = []
    for offset in range(0, len(data), line_bytes):
        chunk = data[offset:offset + line_bytes]
        bit_groups = ["".join(f"{b:08b}" for b in chunk[i:i+1]) for i in range(len(chunk))]
        hex_groups = " ".join(f"{b:02X}" for b in chunk)
        rows.append(f"{offset:04d}: {' '.join(bit_groups)}    {hex_groups}")
    return "\n".join(rows)

def _mismatch_summary(sent_bytes: bytes, recv_bytes: bytes, limit=64) -> str:
    common = min(len(sent_bytes), len(recv_bytes))
    mismatches = []
    for byte_idx in range(common):
        xorv = sent_bytes[byte_idx] ^ recv_bytes[byte_idx]
        if xorv == 0:
            continue
        for bit_idx in range(8):
            mask = 1 << (7 - bit_idx)
            if xorv & mask:
                mismatches.append(f"byte {byte_idx}, bit {bit_idx}: {sent_bytes[byte_idx]:08b} -> {recv_bytes[byte_idx]:08b}")
                if len(mismatches) >= limit:
                    return "\n".join(mismatches + ["..."])
    if len(sent_bytes) != len(recv_bytes):
        mismatches.append(f"length mismatch: sent={len(sent_bytes)} bytes, recv={len(recv_bytes)} bytes")
    return "\n".join(mismatches) if mismatches else "No mismatches"

def _read_csv_rows(csv_path: Path):
    rows = []
    if not csv_path.exists(): return rows
    try:
        with open(csv_path, "r", encoding="utf-8", newline="") as f:
            content = f.read().replace("\x00", "")
            sample = content[:2048]
            try: dialect = csv.Sniffer().sniff(sample, delimiters=",\t;")
            except: dialect = csv.excel
            reader = csv.DictReader(io.StringIO(content), dialect=dialect)
            for row in reader:
                extras = row.get(None) or []
                if extras:
                    if not row.get("payload_hex") and len(extras) >= 1:
                        row["payload_hex"] = extras[0]
                    if not row.get("payload_bits") and len(extras) >= 2:
                        row["payload_bits"] = extras[1]
                if "text" in row and row["text"]:
                    row["text"] = row["text"].replace("\x00", "")
                rows.append(row)
    except Exception as e:
        print(f"[ERROR] CSV Read Failed {csv_path}: {e}")
    return rows

class PacketDetailDialog(QDialog):
    def __init__(self, sent_info, recv_info, parent=None):
        super().__init__(parent)
        self.setWindowTitle("패킷 상세보기")
        self.resize(1100, 700)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        sent_row = sent_info["row"] if sent_info else {}
        recv_row = recv_info["row"] if recv_info else {}
        sent_payload = sent_info["payload"] if sent_info else b""
        recv_payload = recv_info["payload"] if recv_info else b""
        err_bits, total_bits = _bit_error_stats(sent_payload, recv_payload)
        ber = (err_bits / total_bits) * 100 if total_bits > 0 else 0.0
        similarity = _text_similarity(sent_row.get("text", ""), recv_row.get("text", ""))

        form.addRow("Sent ID", QLabel(sent_row.get("id", "-")))
        form.addRow("Recv ID", QLabel(recv_row.get("id", "-")))
        form.addRow("Sent Text", QLabel(sent_row.get("text", "-")))
        form.addRow("Recv Text", QLabel(recv_row.get("text", "-")))
        form.addRow("Sent MID/APID", QLabel(f"{sent_row.get('mid_hex', '-')} / {sent_row.get('apid_hex', '-')}"))
        form.addRow("Recv MID/APID", QLabel(f"{recv_row.get('mid_hex', '-')} / {recv_row.get('apid_hex', '-')}"))
        form.addRow("Sent Seq", QLabel(sent_row.get("seq", "-")))
        form.addRow("Recv Seq", QLabel(recv_row.get("seq", "-")))
        form.addRow("Sent Len", QLabel(sent_row.get("len", "-")))
        form.addRow("Recv Len", QLabel(recv_row.get("len", "-")))
        form.addRow("Bit Errors", QLabel(str(err_bits)))
        form.addRow("BER(%)", QLabel(f"{ber:.2f}"))
        form.addRow("Similarity(%)", QLabel(f"{similarity:.2f}"))
        layout.addLayout(form)

        panes = QHBoxLayout()

        sent_box = QVBoxLayout()
        sent_box.addWidget(QLabel("송신 Payload Bits / Hex"))
        self.sent_bits = QPlainTextEdit()
        self.sent_bits.setReadOnly(True)
        self.sent_bits.setPlainText(_bytes_to_grouped_bits(sent_payload))
        sent_box.addWidget(self.sent_bits)
        panes.addLayout(sent_box, 1)

        recv_box = QVBoxLayout()
        recv_box.addWidget(QLabel("수신 Payload Bits / Hex"))
        self.recv_bits = QPlainTextEdit()
        self.recv_bits.setReadOnly(True)
        self.recv_bits.setPlainText(_bytes_to_grouped_bits(recv_payload))
        recv_box.addWidget(self.recv_bits)
        panes.addLayout(recv_box, 1)

        diff_box = QVBoxLayout()
        diff_box.addWidget(QLabel("비트 차이 요약"))
        self.diff_bits = QPlainTextEdit()
        self.diff_bits.setReadOnly(True)
        self.diff_bits.setPlainText(_mismatch_summary(sent_payload, recv_payload))
        diff_box.addWidget(self.diff_bits)
        panes.addLayout(diff_box, 1)

        layout.addLayout(panes)

        btns = QDialogButtonBox(QDialogButtonBox.Close)
        btns.rejected.connect(self.reject)
        btns.accepted.connect(self.accept)
        btns.button(QDialogButtonBox.Close).clicked.connect(self.close)
        layout.addWidget(btns)

class SampleAppTelemetryDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Sample App Telemetry (Hybrid Matching)")
        self.setMinimumSize(1200, 650)

        layout = QVBoxLayout(self)
        self.current_results = []

        info_lbl = QLabel(
            "<b>[하이브리드 매칭 및 정량 평가]</b><br>"
            "- <b>1단계(ID):</b> 메시지 ID가 일치하면 매칭<br>"
            "- <b>2단계(시간):</b> ID가 깨졌을 경우(재밍 등), 전송 후 2초 내 도착한 패킷과 매칭<br>"
            "- <b>BER:</b> 송신 데이터와 수신 데이터의 비트 차이를 백분율로 표시"
        )
        layout.addWidget(info_lbl)

        self.table = QTableWidget()
        cols = ["Sent ID", "Sent Time", "Sent Msg", "Recv Time", "Recv Msg", "RTT(ms)", "Status", "BER(%)", "Similarity(%)", "상세"]
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

            sent_list.append({
                "row": row,
                "ts": ts,
                "id": row.get("id", ""),
                "payload": _payload_bytes_from_row(row),
                "matched": False
            })

        recv_list = []
        for row in recv_rows:
            if row.get("direction") != "recv": continue
            mid = (row.get("mid_hex") or row.get("sid_hex") or "").lower()
            if "08a9" not in mid: continue # Telemetry Filter
            ts = self._parse_ts(row.get("ts"))
            if not ts: continue

            recv_list.append({
                "row": row,
                "ts": ts,
                "id": row.get("id", ""),
                "payload": _payload_bytes_from_row(row),
                "matched": False
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
        self.current_results = results

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
            status, color, ber_str, sim_str, rtt_str = "-", Qt.black, "-", "-", "-"

            if s and r:
                rtt_str = f"{(r['ts'] - s['ts']).total_seconds()*1000:.0f}"
                
                sent_payload = s["payload"]
                recv_payload = r["payload"]
                err_bits, total_bits = _bit_error_stats(sent_payload, recv_payload)
                similarity = _text_similarity(s["row"].get("text", ""), r["row"].get("text", ""))
                sim_str = f"{similarity:.2f} %"
                
                if err_bits == 0:
                    status = "OK"
                    color = COLOR_OK
                    ber_str = "0.00 %"
                else:
                    status = "CORRUPTED" # 매칭은 됐지만 내용 다름
                    color = COLOR_CORRUPT
                    ber = (err_bits / total_bits) * 100 if total_bits > 0 else 0
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

            sim_item = QTableWidgetItem(sim_str)
            sim_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(idx, 8, sim_item)

            detail_btn = QPushButton("상세보기")
            detail_btn.clicked.connect(lambda _, row_idx=idx: self.open_detail_dialog(row_idx))
            self.table.setCellWidget(idx, 9, detail_btn)

    def reset_all_data(self):
        reply = QMessageBox.question(self, "초기화", "로그를 초기화하시겠습니까?", QMessageBox.Yes | QMessageBox.No)
        if reply != QMessageBox.Yes: return
        try:
            # Seq 포함된 헤더로 초기화
            header = ["ts","direction","id","text","mid_hex","apid_hex","cc_dec",
                      "seq","len","src_ip","src_port","head_hex16","text_hex","bits",
                      "payload_hex","payload_bits"]
            for p in [SENT_CSV, RECV_CSV]:
                with open(p, "w", newline="", encoding="utf-8") as f:
                    csv.writer(f).writerow(header)
            self.refresh_data()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def open_detail_dialog(self, row_idx: int):
        if row_idx < 0 or row_idx >= len(self.current_results):
            return
        sent_info, recv_info = self.current_results[row_idx]
        dlg = PacketDetailDialog(sent_info, recv_info, self)
        dlg.exec_()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    dlg = SampleAppTelemetryDialog()
    dlg.show()
    sys.exit(app.exec_())
