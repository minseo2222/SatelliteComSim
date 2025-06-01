#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test.py: UDP로 들어오는 평문 앞에 프리앰블(0xAA, 0xAA)을 붙여 GMSK 변조 후
complex64 샘플 형태로 UDP(8888)로 전송하는 예시입니다.

1) UDP(50000) 수신: GS GUI에서 보낸 평문 바이트
2) 바이트 앞에 [0xAA, 0xAA] 프리앰블 추가
3) GMSK 변조 → complex64 샘플 → UDP(8888) 전송
"""

import socket
import time
import numpy as np
from gnuradio import gr, blocks, digital

UDP_IP       = "127.0.0.1"   # test2.py(복조기) IP
UDP_PORT     = 8888          # test2.py(복조기) 포트
LISTEN_IP    = "0.0.0.0"     # GS GUI가 보내는 IP
LISTEN_PORT  = 50000         # GS GUI가 보내는 포트

class GMSKModulator(gr.top_block):
    """
    GMSKModulator: byte(uchar) 리스트를 받아 GMSK 변조 후
    complex64 샘플을 vector_sink_c에 저장한다.
    """
    def __init__(self, data_bytes):
        super().__init__()
        # 1) byte(uchar) 소스 → GMSK 변조 (output: complex64)
        self.src = blocks.vector_source_b(data_bytes, False)
        self.mod = digital.gmsk_mod(samples_per_symbol=2)
        # 2) 변조된 complex64 샘플을 저장할 sink
        self.sink = blocks.vector_sink_c()
        # 블록 연결: src(u8) → gmsk_mod(complex) → sink(complex)
        self.connect(self.src, self.mod)
        self.connect(self.mod, self.sink)

    def get_modulated_data(self):
        return self.sink.data()  # complex64 리스트 반환


def main():
    # 1) UDP(50000) 수신 소켓
    sock_recv = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock_recv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock_recv.bind((LISTEN_IP, LISTEN_PORT))

    # 2) UDP(8888) 전송 소켓
    sock_send = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    print(f"[test.py] Listening on {LISTEN_IP}:{LISTEN_PORT} ...")

    while True:
        # GS GUI로부터 평문 바이트 수신
        data, addr = sock_recv.recvfrom(4096)
        print(f"[test.py] Received {len(data)} bytes from {addr}")

        # 3) 프리앰블(0xAA, 0xAA) 추가
        preamble = [0xAA, 0xAA]
        orig_bytes = list(data)
        packet_bytes = preamble + orig_bytes  # [0xAA,0xAA] + 원본

        # 4) GMSK 변조
        tb = GMSKModulator(packet_bytes)
        tb.start()
        time.sleep(0.1)   # 충분히 샘플 생성할 시간 대기
        tb.stop()
        tb.wait()

        # 5) complex64 샘플 리스트 → numpy array → raw bytes
        complex_samples = tb.get_modulated_data()
        complex_array = np.array(complex_samples, dtype=np.complex64)
        mod_bytes = complex_array.tobytes()

        # 6) UDP(8888)으로 전송
        sock_send.sendto(mod_bytes, (UDP_IP, UDP_PORT))
        print(f"[test.py] Sent {len(mod_bytes)} bytes (complex64 GMSK) to {UDP_IP}:{UDP_PORT}")


if __name__ == "__main__":
    main()

