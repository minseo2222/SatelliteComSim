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
GNURADIO_TX_PORT= 8602                 # GNURadio가 받는 포트(필요 시 변경)

# SAMPLE_APP 텍스트 텔레메트리 MID (sample_app_msgids.h 에서 정의)
SAMPLE_APP_TEXT_TLM_MID = 0x08A9

# 로그 파일 경로 (newGS/log/ 아래)
ROOTDIR = Path(__file__).resolve().parent
LOG_DIR = ROOTDIR / "log"
RECV_CSV = LOG_DIR / "sample_app_recv.csv"

# -----------------------------
# 도우미: CCSDS 기본 헤더 파싱
# -----------------------------
def parse_ccsds_header(pkt):
    """
    CCSDS 기본 헤더(빅엔디안 6바이트):
      0-1: Stream ID (MID)
      2-3: Sequence (flags + count)
      4-5: Length (헤더 제외 길이)
    """
    if len(pkt) < 6:
        return None
    (stream_id, seq, length) = struct.unpack(">HHH", pkt[:6])
    apid = stream_id & 0x07FF
    return {
        "mid": stream_id,
        "apid": apid,
        "seq": seq,
        "len": length,              # 헤더 제외 길이
        "total_len": length + 7     # CCSDS 전체 길이(= len + 7)
    }

# -----------------------------
# 도우미: SAMPLE_APP 텍스트 TLM 파싱
#  - sample_app_msg.h 기준:
#    typedef struct {
#       CFE_SB_TlmHdr_t TlmHeader;   // 기본 + 2차 헤더 (총 12바이트로 가정)
#       uint16          TextLen;     // 2바이트
#       char            Text[128];   // 128바이트
#    } SAMPLE_TextTlm_t;
# -----------------------------
def parse_sample_text_tlm(pkt):
    """
    pkt 전체에서 CCSDS 헤더 이후의 페이로드를 해석:
      [0:6]   : CCSDS 기본 헤더
      [6:12]  : CFE SB 2차 TLM 헤더(일반적으로 6바이트로 취급)
      [12:14] : TextLen (uint16, big-endian)
      [14:142]: Text[128]
    """
    if len(pkt) < 14:
        return None
    text_len = struct.unpack(">H", pkt[12:14])[0]
    text_raw = pkt[14:14+128]
    text = text_raw.split(b"\x00", 1)[0].decode("utf-8", errors="ignore")
    if text_len > len(text):
        text_len = len(text)
    return text_len, text

# -----------------------------
# CSV 초기화
# -----------------------------
def ensure_csv_header(path, header):
    path.parent.mkdir(parents=True, exist_ok=True)
    if (not path.exists()) or path.stat().st_size == 0:
        with open(path, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(header)

# -----------------------------
# GNURadio로 패킷 패스스루(옵션)
# -----------------------------
def forward_to_gnuradio(sock_tx, data):
    try:
        sock_tx.sendto(data, (GNURADIO_TX_IP, GNURADIO_TX_PORT))
    except Exception:
        # GNURadio 미실행 등 예외는 조용히 무시
        pass

# -----------------------------
# 메인
# -----------------------------
def main():
    ensure_csv_header(RECV_CSV, ["ts", "mid_hex", "apid_hex", "text_len", "text"])

    # 소켓 준비 (cFS 수신)
    sock_rx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock_rx.bind((CFS_LISTEN_IP, CFS_LISTEN_PORT))
    sock_rx.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4 * 1024 * 1024)

    # GNURadio TX 소켓
    sock_tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    print(f"[test3.py] Listening cFS on {CFS_LISTEN_IP}:{CFS_LISTEN_PORT} ...")
    print(f"[test3.py] Forwarding raw CCSDS to GNURadio TX at {GNURADIO_TX_IP}:{GNURADIO_TX_PORT}")
    print(f"[test3.py] Only printing SAMPLE_APP_TEXT_TLM (MID=0x{SAMPLE_APP_TEXT_TLM_MID:04X})")

    while True:
        data, addr = sock_rx.recvfrom(2048)
        hdr = parse_ccsds_header(data)
        if not hdr:
            continue

        # GNURadio로는 모든 패킷을 그대로 전달(필요 시 주석 처리)
        forward_to_gnuradio(sock_tx, data)

        # SAMPLE_APP_TEXT_TLM만 콘솔 출력 + CSV 로깅
        if hdr["mid"] == SAMPLE_APP_TEXT_TLM_MID:
            parsed = parse_sample_text_tlm(data)
            if not parsed:
                continue
            text_len, text = parsed

            ts = datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]
            print(f"[test3.py] SAMPLE_APP_TEXT_TLM 0x{hdr['mid']:04X} APID=0x{hdr['apid']:03X} len={hdr['total_len']} | TextLen={text_len} Text={text!r}")

            with open(RECV_CSV, "a", newline="", encoding="utf-8") as f:
                csv.writer(f).writerow([
                    ts,
                    "0x%04X" % hdr["mid"],
                    "0x%03X" % hdr["apid"],
                    text_len,
                    text
                ])

if __name__ == "__main__":
    main()

