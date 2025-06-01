#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test2.py: GMSK 복조 후 복원된 패킷을
“헤더 안에 명시된 길이”와 실제 길이가 일치하도록 자동 보정한 뒤
그대로 UDP(1234)로 전송합니다.

1) UDP(8888)로 들어온 complex64 GMSK 샘플 복조 → bit_stream
2) shift(0~8비트)로 프리앰블(0xAA, 0xAA) 찾아 비트 보정 → 8비트씩 묶어 restored 바이트열 생성
3) restored 첫 6바이트(Primary Header)에서 Length 필드를 읽어, "payload 길이 = length+1" 계산
4) 실제 payload 길이(restored[6:])와 비교하여,
   - 부족하면 0x00으로 패딩
   - 넘치면 잘라서
   헤더-페이로드 길이가 일치하도록 맞춤
5) 보정된 restored_packet(full_packet)을 UDP(1234)로 전송
"""

import socket
import numpy as np
from gnuradio import gr, blocks, digital
import time

GMSK_UDP_PORT = 8888           # test.py → test2.py 포트
CFS_DEST_IP   = '127.0.0.1'     # cFS 수신 IP
CFS_DEST_PORT = 1234            # cFS 수신 포트

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
    """bit_list에서 0xAA 0xAA 패턴(10101010 10101010)의 시작 인덱스를 반환, 없으면 -1"""
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
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(('0.0.0.0', GMSK_UDP_PORT))
    print(f"[test2.py] Listening on UDP port {GMSK_UDP_PORT} ...")

    while True:
        data, addr = sock.recvfrom(65536)
        print(f"\n[test2.py] Received {len(data)} bytes from {addr}")

        # 1) raw bytes → complex64 배열
        num_complex   = len(data) // 8
        complex_array = np.frombuffer(data, dtype=np.complex64, count=num_complex)
        complex_list  = complex_array.tolist()

        # 2) GMSK 복조 → 비트 스트림
        tb = GMSKDemodulator(complex_list)
        tb.run()
        bit_stream = list(tb.sink.data())
        print(f"[test2.py] Demodulated {len(bit_stream)} bits")

        # 3) shift(0~8)로 프리앰블 위치 찾아 보정
        MAX_SHIFT   = 8
        best_shift  = 0
        best_idx    = -1
        for shift in range(0, MAX_SHIFT + 1):
            shifted = bit_stream[shift:] if shift > 0 else bit_stream
            idx = find_preamble(shifted)
            if idx >= 0:
                best_shift = shift
                best_idx   = idx
                break
        if best_idx < 0:
            print("[test2.py] Preamble not found. Skipping.")
            continue
        print(f"[test2.py] Found at shift={best_shift}, idx={best_idx}")

        final_start = best_idx + best_shift + 16
        restored    = bits_to_bytes(bit_stream, final_start)
        print(f"[test2.py] Restored {len(restored)} bytes")

        # 4) Header와 Payload 길이 보정
        if len(restored) < 6:
            print("[test2.py] Restored packet too short for header. Skipping.")
            continue

        # Primary Header 첫 6바이트에서 Length 필드(바이트 4-5) 읽기
        # CCSDS Length = (실 payload 길이) - 1
        hdr_len_field = (restored[4] << 8) | restored[5]
        expected_payload_len = hdr_len_field + 1
        actual_payload_len   = len(restored) - 6

        print(f"[test2.py] Header says payload={expected_payload_len}, actual={actual_payload_len}")

        if actual_payload_len < expected_payload_len:
            # 부족하면 0x00으로 패딩
            pad_len = expected_payload_len - actual_payload_len
            restored_packet = restored + bytes(pad_len)
            print(f"[test2.py] Padded {pad_len} bytes")
        elif actual_payload_len > expected_payload_len:
            # 초과하면 잘라냄
            cut_len = actual_payload_len - expected_payload_len
            restored_packet = restored[:6 + expected_payload_len]
            print(f"[test2.py] Truncated {cut_len} excess bytes")
        else:
            # 일치하면 그대로
            restored_packet = restored

        # (디버깅) 최종 패킷 정보
        print(f"[test2.py] Final packet length={len(restored_packet)} bytes")
        print("[test2.py] Final packet hex (first 32):", 
              ' '.join(f"0x{b:02X}" for b in restored_packet[:32]))

        # 5) cFS로 전송
        sock_out = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock_out.sendto(restored_packet, (CFS_DEST_IP, CFS_DEST_PORT))
        sock_out.close()
        print(f"[test2.py] Forwarded to cFS at {CFS_DEST_IP}:{CFS_DEST_PORT}")

        time.sleep(0.05)

if __name__ == '__main__':
    main()

