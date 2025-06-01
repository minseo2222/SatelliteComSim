#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test4.py: UDP(8890)로 들어오는 GMSK complex64 바이트를 수신하여
1) GMSK 복조 → 비트 스트림
2) shift(0~8비트)로 프리앰블(0xAA,0xAA) 위치 찾기
3) 8비트씩 묶어 원본 바이트 restored 생성
4) restored에서 “: ” 뒤에 나오는 텍스트(원하는 메시지)만 추출하여
   UDP(50001)로 GS GUI에 전달
"""

import socket
import numpy as np
from gnuradio import gr, blocks, digital
import time

# test3 → test4 GMSK 수신 포트
GMSK_LISTEN_PORT = 8890

# test4 → GS GUI 전송 포트
GS_SEND_IP       = '127.0.0.1'
GS_SEND_PORT     = 50001

def bits_to_bytes(bit_list, start_bit):
    """bit_list[start_bit:]를 8비트씩 묶어 bytes로 반환"""
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
    """bit_list에서 0xAA 0xAA(10101010 10101010) 패턴의 시작 인덱스를 반환"""
    target = [1,0,1,0,1,0,1,0] * 2
    L = len(bit_list)
    for i in range(0, L - 16 + 1):
        if bit_list[i:i+16] == target:
            return i
    return -1

class GMSKDemodulator(gr.top_block):
    """complex64 입력 → GMSK 복조 → uchar 비트 출력"""
    def __init__(self, input_samples):
        super().__init__()
        self.src   = blocks.vector_source_c(input_samples, False)
        self.demod = digital.gmsk_demod(samples_per_symbol=2)
        self.sink  = blocks.vector_sink_b()
        self.connect(self.src, self.demod)
        self.connect(self.demod, self.sink)

def main():
    # 1) GMSK complex64 bytes 수신용 UDP 소켓 (포트 8890)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(('0.0.0.0', GMSK_LISTEN_PORT))
    print(f"[test4.py] Listening on UDP port {GMSK_LISTEN_PORT} ...")

    while True:
        data, addr = sock.recvfrom(65536)
        print(f"\n[test4.py] Received {len(data)} GMSK bytes from {addr}")

        # 2) raw bytes → complex64 배열로 복원
        num_complex   = len(data) // 8
        complex_array = np.frombuffer(data, dtype=np.complex64, count=num_complex)
        complex_list  = complex_array.tolist()

        # 3) GMSK 복조 → 비트 스트림
        tb = GMSKDemodulator(complex_list)
        tb.run()
        bit_stream = list(tb.sink.data())
        print(f"[test4.py] Demodulated {len(bit_stream)} bits")

        # 4) shift(0~8)로 프리앰블 위치 찾기
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

        final_start = best_idx + best_shift + 16
        restored    = bits_to_bytes(bit_stream, final_start)
        print(f"[test4.py] Restored {len(restored)} bytes")

        # (디버깅) 헥사 일부 출력
        print("[test4.py] Restored Hex (first 32):", 
              ' '.join(f"0x{b:02X}" for b in restored[:32]))

        # 5) restored를 UTF-8로 디코딩하여 “: ” 뒤의 텍스트만 추출
        try:
            text_all = restored.decode('utf-8', errors='ignore')
        except:
            text_all = ""
        # “: ” 구분자가 있으면 뒤쪽만 취함
        if ": " in text_all:
            _, msg_body = text_all.split(": ", 1)
        else:
            msg_body = text_all  # 구분자가 없으면 전체

        # (디버깅) 추출된 메시지
        print("[test4.py] Extracted Text:", msg_body)

        # 6) GS GUI(127.0.0.1:50001)로 메시지 부분만 전송
        to_send = msg_body.encode('utf-8', errors='ignore')
        sock_out = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock_out.sendto(to_send, (GS_SEND_IP, GS_SEND_PORT))
        sock_out.close()
        print(f"[test4.py] Forwarded {len(to_send)} text bytes to GS at {GS_SEND_IP}:{GS_SEND_PORT}")

        time.sleep(0.05)

if __name__ == '__main__':
    main()

