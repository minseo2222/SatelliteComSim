#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import socket
import struct
import csv
from pathlib import Path
from datetime import datetime

# -----------------------------
# 환경 설정
# -----------------------------
CFS_LISTEN_IP   = "0.0.0.0"
CFS_LISTEN_PORT = 1235                 # cFS TO_LAB가 내보내는 UDP 포트
GNURADIO_TX_IP  = "127.0.0.1"
GNURADIO_TX_PORT= 8602                 # GNURadio가 받는 포트(옵션)

# SAMPLE_APP 텍스트 텔레메트리 MID
SAMPLE_APP_TEXT_TLM_MID = 0x08A9

# 로그 파일 경로 (newGS/log/ 아래)
ROOTDIR = Path(__file__).resolve().parent
LOG_DIR = ROOTDIR / "log"
RECV_CSV = LOG_DIR / "sample_app_recv.csv"

# -----------------------------
# 공통 유틸
# -----------------------------
def now_ts():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def ensure_csv_header(path, header):
    path.parent.mkdir(parents=True, exist_ok=True)
    if (not path.exists()) or path.stat().st_size == 0:
        with open(path, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(header)

def to_hex(b: bytes) -> str:
    return "".join(f"{x:02X}" for x in b)

def bytes_to_bits(b: bytes) -> str:
    return "".join(f"{x:08b}" for x in b)

# -----------------------------
# CCSDS 기본 헤더 파싱
# -----------------------------
def parse_ccsds_header(pkt):
    if len(pkt) < 6:
        return None
    (stream_id, seq, length) = struct.unpack(">HHH", pkt[:6])
    apid = stream_id & 0x07FF
    return {
        "mid": stream_id,
        "apid": apid,
        "seq": seq,
        "len": length,
        "total_len": length + 7
    }

# -----------------------------
# SAMPLE_APP 텍스트 TLM 파싱
# -----------------------------
def parse_sample_text_tlm(pkt):
    if len(pkt) < 14:
        return None
    # [12:14] TextLen, [14:142] Text[128]
    text_len = struct.unpack(">H", pkt[12:14])[0]
    text_raw = pkt[14:14+128]
    text = text_raw.split(b"\x00", 1)[0].decode("utf-8", errors="ignore")
    if text_len > len(text):
        text_len = len(text)
    return text_len, text

# -----------------------------
# GNURadio로 패킷 패스스루(옵션)
# -----------------------------
def forward_to_gnuradio(sock_tx, data):
    try:
        sock_tx.sendto(data, (GNURADIO_TX_IP, GNURADIO_TX_PORT))
    except Exception:
        pass

# -----------------------------
# 메인
# -----------------------------
def main():
    ensure_csv_header(RECV_CSV, [
        "ts","direction","id","text","mid_hex","apid_hex","cc_dec","len",
        "src_ip","src_port","head_hex16","text_hex","bits"
    ])

    # 소켓 준비 (cFS 수신)
    sock_rx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock_rx.bind((CFS_LISTEN_IP, CFS_LISTEN_PORT))
    sock_rx.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4 * 1024 * 1024)

    # GNURadio TX 소켓
    sock_tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    print(f"[test3.py] Listening cFS on {CFS_LISTEN_IP}:{CFS_LISTEN_PORT} ...")
    print(f"[test3.py] Forwarding raw CCSDS to GNURadio TX at {GNURADIO_TX_IP}:{GNURADIO_TX_PORT}")
    print(f"[test3.py] Filtering SAMPLE_APP_TEXT_TLM (MID=0x{SAMPLE_APP_TEXT_TLM_MID:04X})")

    while True:
        data, addr = sock_rx.recvfrom(2048)
        src_ip, src_port = addr
        hdr = parse_ccsds_header(data)
        if not hdr:
            continue

        # GNURadio로는 모든 패킷을 그대로 전달(필요 시 주석 처리)
        forward_to_gnuradio(sock_tx, data)

        # SAMPLE_APP_TEXT_TLM만 처리/로깅
        if hdr["mid"] != SAMPLE_APP_TEXT_TLM_MID:
            continue

        parsed = parse_sample_text_tlm(data)
        if not parsed:
            continue
        text_len, text = parsed

        # ID 추출
        sid = None
        text_body = text
        p = text.split(":", 1)
        if len(p) == 2 and p[0].isdigit():
            try:
                sid = int(p[0])
                text_body = p[1]
            except Exception:
                text_body = text

        # 부가 필드
        head_hex16 = " ".join(f"{b:02X}" for b in data[:16])
        text_bytes = text_body.encode("utf-8", errors="ignore")
        text_hex = to_hex(text_bytes)
        bits = bytes_to_bits(text_bytes)
        if bits:
            bits = "b:" + bits  # 엑셀 숫자 인식 방지

        ts = now_ts()
        print(f"[test3.py] SAMPLE_APP_TEXT_TLM mid=0x{hdr['mid']:04X} apid=0x{hdr['apid']:04X} "
              f"len={hdr['total_len']} TextLen={text_len} Text={text!r}")

        with open(RECV_CSV, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow([
                ts,                         # ts
                "recv",                     # direction
                (sid if sid is not None else ""),  # id
                text_body,                  # text
                f"0x{hdr['mid']:04X}",      # mid_hex
                f"0x{hdr['apid']:04X}",     # apid_hex
                "",                         # cc_dec (수신 텔레메트리는 공란)
                len(data),                  # len
                src_ip, src_port,           # src_ip, src_port
                head_hex16,                 # head_hex16
                text_hex,                   # text_hex
                bits                        # bits
            ])

if __name__ == "__main__":
    main()

