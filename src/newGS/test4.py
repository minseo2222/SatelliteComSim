#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test4.py: UDP(8890)로 들어오는 GMSK complex64 바이트를 수신하여
1) GMSK 복조 → 비트 스트림
2) shift(0~8비트)로 프리앰블(0xAA, 0xAA) 위치 찾기
3) 8비트씩 묶어 원본 바이트 restored 생성
4) restored 전체를 순회하며 “(숫자열):(ASCII 메시지)” 구조를 찾아 파싱
5) sample_app_recv.csv 에 [ID, timestamp, text, recv_bits] 한 줄을 추가
6) 메시지 본문만 UDP(50001)로 GS GUI에 전달
"""

import socket
import csv
import time
import numpy as np
from gnuradio import gr, blocks, digital
from pathlib import Path
from datetime import datetime

# ------------------------------------------------------------------------------
# 1) UDP 포트 설정
# ------------------------------------------------------------------------------
GMSK_LISTEN_PORT = 8890      # test3 → test4 GMSK 수신 포트
GS_SEND_IP       = '127.0.0.1'
GS_SEND_PORT     = 50001     # test4 → GS GUI 전송 포트

# ------------------------------------------------------------------------------
# 2) sample_app_recv.csv 파일 경로 설정
# ------------------------------------------------------------------------------
BASE_DIR     = Path(__file__).resolve().parent            # newGS
RECV_CSV_DIR = BASE_DIR / "Subsystems" / "cmdGui"          # newGS/Subsystems/cmdGui
RECV_CSV     = RECV_CSV_DIR / "sample_app_recv.csv"

# ------------------------------------------------------------------------------
# 3) 비트 → 바이트 / 프리앰블 감지 함수들
# ------------------------------------------------------------------------------
def bits_to_bytes(bit_list, start_bit):
    out = bytearray()
    n = len(bit_list)
    for i in range(start_bit, n, 8):
        if i + 8 > n:
            break
        byte = 0
        for b in range(8):
            byte = (byte << 1) | (bit_list[i + b] & 0x1)
        out.append(byte)
    return bytes(out)

def find_preamble(bit_list):
    target = [1,0,1,0,1,0,1,0] * 2  # 0xAA 0xAA
    L = len(bit_list)
    for i in range(0, L - 16 + 1):
        if bit_list[i:i+16] == target:
            return i
    return -1

# ------------------------------------------------------------------------------
# 4) GMSK 복조용 클래스
# ------------------------------------------------------------------------------
class GMSKDemodulator(gr.top_block):
    def __init__(self, input_samples):
        super().__init__()
        self.src   = blocks.vector_source_c(input_samples, False)
        self.demod = digital.gmsk_demod(samples_per_symbol=2)
        self.sink  = blocks.vector_sink_b()
        self.connect(self.src, self.demod)
        self.connect(self.demod, self.sink)

# ------------------------------------------------------------------------------
# 5) “ID:메시지” 파싱 보조 함수
# ------------------------------------------------------------------------------
def parse_id_and_body(restored_bytes: bytes):
    """
    restored_bytes 내부에서 “(숫자열):(ASCII 텍스트)” 구조를 찾아 반환.
    반환: (parsed_id: int or None, parsed_body: str)
    """
    n = len(restored_bytes)
    for sep_idx in range(n):
        if restored_bytes[sep_idx] == 0x3A:  # ':' 바이트 (0x3A)
            # 콜론 바로 앞부터 역순으로 숫자(ASCII) 추출
            i = sep_idx - 1
            id_bytes = bytearray()
            while i >= 0 and 0x30 <= restored_bytes[i] <= 0x39:
                id_bytes.insert(0, restored_bytes[i])
                i -= 1

            if len(id_bytes) == 0:
                continue

            try:
                id_str = id_bytes.decode('ascii')
                parsed_id = int(id_str)
            except:
                continue

            # 메시지 본문: 콜론 뒤(restored_bytes[sep_idx+1:])를 UTF-8로 디코딩
            body_bytes = restored_bytes[sep_idx+1:]
            try:
                parsed_body = body_bytes.decode('utf-8', errors='ignore')
            except:
                parsed_body = ""
            return (parsed_id, parsed_body)

    return (None, "")

# ------------------------------------------------------------------------------
# 6) 문자를 이진 문자열로 바꾸는 헬퍼
# ------------------------------------------------------------------------------
def text_to_bitstring(text: str) -> str:
    """
    text(문자열)를 UTF-8 인코딩한 뒤, 각 바이트를 8비트 이진 문자열로 합쳐서 반환
    예: "A" → b'\x41' → "01000001"
    """
    b = text.encode("utf-8", errors="ignore")
    return "".join(f"{byte:08b}" for byte in b)

# ------------------------------------------------------------------------------
# 7) main 루프
# ------------------------------------------------------------------------------
def main():
    # 7.1) UDP 바인딩 (GMSK 바이트 수신)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(('0.0.0.0', GMSK_LISTEN_PORT))
    print(f"[test4.py] Listening on UDP port {GMSK_LISTEN_PORT} ...")

    # 7.2) CSV 디렉토리/파일 준비
    if not RECV_CSV_DIR.exists():
        RECV_CSV_DIR.mkdir(parents=True, exist_ok=True)

    # 헤더 보장: 없으면 만들어 둔다
    if not RECV_CSV.exists():
        with open(RECV_CSV, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["id", "timestamp", "text", "recv_bits"])
        print(f"[test4.py] Created new CSV file: {RECV_CSV}")

    while True:
        data, addr = sock.recvfrom(65536)
        print(f"\n[test4.py] Received {len(data)} GMSK bytes from {addr}")

        # 바이트→complex64 배열로 변환
        num_complex   = len(data) // 8
        complex_array = np.frombuffer(data, dtype=np.complex64, count=num_complex)
        complex_list  = complex_array.tolist()

        # GMSK 복조
        tb = GMSKDemodulator(complex_list)
        tb.run()
        bit_stream = list(tb.sink.data())
        print(f"[test4.py] Demodulated {len(bit_stream)} bits")

        # 프리앰블 찾기 (shift 0~8)
        MAX_SHIFT  = 8
        best_shift = 0
        best_idx   = -1
        for shift in range(0, MAX_SHIFT + 1):
            shifted_bits = bit_stream[shift:] if shift > 0 else bit_stream
            idx = find_preamble(shifted_bits)
            if idx >= 0:
                best_shift = shift
                best_idx   = idx
                break

        if best_idx < 0:
            print("[test4.py] Preamble not found. Skipping.")
            continue

        print(f"[test4.py] Found preamble at shift={best_shift}, idx={best_idx}")

        # 복원된 바이트 생성
        final_start = best_idx + best_shift + 16
        restored    = bits_to_bytes(bit_stream, final_start)
        print(f"[test4.py] Restored {len(restored)} bytes")
        print("[test4.py] Restored Hex (first 32):",
              ' '.join(f"0x{b:02X}" for b in restored[:32]))

        # “ID:메시지” 파싱
        parsed_id, parsed_body = parse_id_and_body(restored)
        print(f"[test4.py] Parsed ID: {parsed_id}, Text: {parsed_body!r}")

        # 널바이트(\x00) 제거: trailing nulls가 있으면 모두 strip
        if parsed_body:
            parsed_body = parsed_body.rstrip('\x00')

        # CSV에 [id, timestamp, text, recv_bits] 기록
        if parsed_id is not None:
            timestamp_str = datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]
            recv_bits = text_to_bitstring(parsed_body)
            with open(RECV_CSV, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([parsed_id, timestamp_str, parsed_body, recv_bits])
            print(f"[test4.py] Logged to {RECV_CSV.name}: "
                  f"ID={parsed_id}, Time={timestamp_str}, Text={parsed_body!r}, recv_bits_len={len(recv_bits)}")
        else:
            print("[test4.py] ID parsing failed; not logged to CSV.")

        # GS GUI로 메시지 본문만 전송
        to_send = parsed_body.encode('utf-8', errors='ignore')
        sock_out = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock_out.sendto(to_send, (GS_SEND_IP, GS_SEND_PORT))
        sock_out.close()
        print(f"[test4.py] Forwarded {len(to_send)} text bytes to GS at {GS_SEND_IP}:{GS_SEND_PORT}")

        time.sleep(0.05)

if __name__ == '__main__':
    main()

