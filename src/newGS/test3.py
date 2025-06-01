#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test3.py: cFS에서 들어오는 sample_app 메시지(MID=0x08A9)만 필터링하여
프리앰블(0xAA, 0xAA)을 붙인 뒤 GMSK 변조하여
UDP(8890)로 송신합니다.

- cFS → test3: UDP 1235번 포트
- test3 → test4: UDP 8890번 포트
"""

import socket
import time
import struct
import numpy as np
from gnuradio import gr, blocks, digital

# cFS → test3 수신 포트 (1235번)
CFS_LISTEN_IP    = "0.0.0.0"
CFS_LISTEN_PORT  = 1235

# test3 → test4 GMSK 전송 포트 (8890번)
GMSK_SEND_IP     = "127.0.0.1"
GMSK_SEND_PORT   = 8890

# **원래대로 되돌린 부분: sample_app 텍스트 텔레메트리 MID**
# cFS에서 들어오는 패킷의 첫 2바이트가 0x08A9으로 나왔으므로, 이 값을 필터링합니다.
SAMPLE_APP_MID = 0x08A9

class GMSKModulator(gr.top_block):
    """
    byte(uchar) 리스트를 받아 GMSK 변조 후
    complex64 샘플을 vector_sink_c에 저장합니다.
    """
    def __init__(self, data_bytes):
        super().__init__()
        self.src = blocks.vector_source_b(data_bytes, False)
        self.mod = digital.gmsk_mod(samples_per_symbol=2)
        self.sink = blocks.vector_sink_c()
        self.connect(self.src, self.mod)
        self.connect(self.mod, self.sink)

    def get_modulated_data(self):
        return self.sink.data()

def get_msg_id(data):
    """
    데이터 바이트열의 첫 2바이트를 big-endian 형식으로 읽어 MID를 반환합니다.
    """
    if len(data) < 2:
        return None
    return struct.unpack_from(">H", data, 0)[0]

def main():
    # 1) cFS → test3 수신용 UDP 소켓 (포트 1235)
    sock_recv = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock_recv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock_recv.bind((CFS_LISTEN_IP, CFS_LISTEN_PORT))

    # 2) test3 → test4 전송용 UDP 소켓 (포트 8890)
    sock_send = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    print(f"[test3.py] Listening for cFS on {CFS_LISTEN_IP}:{CFS_LISTEN_PORT} ...")

    while True:
        data, addr = sock_recv.recvfrom(4096)
        msg_id = get_msg_id(data)

        # ───────────────────────────────────────────────────────────────────────
        # 디버깅용: cFS에서 들어온 패킷의 첫 2바이트와 msg_id를 출력
        print(f"[test3.py DEBUG] Raw first 2 bytes: {data[:2].hex().upper()}, msg_id = 0x{msg_id:04X}")
        # ───────────────────────────────────────────────────────────────────────

        # sample_app 텍스트(MID=0x08A9)인 경우에만 처리
        if msg_id != SAMPLE_APP_MID:
            continue

        print(f"[test3.py] Received sample_app packet ({len(data)} bytes) from {addr}")

        # 3) 프리앰블(0xAA, 0xAA) 추가
        preamble = [0xAA, 0xAA]
        orig_bytes = list(data)
        packet_bytes = preamble + orig_bytes

        # 4) GMSK 변조
        tb = GMSKModulator(packet_bytes)
        tb.start()
        time.sleep(0.1)   # 충분히 샘플 생성할 시간 대기
        tb.stop()
        tb.wait()

        complex_samples = tb.get_modulated_data()
        complex_array   = np.array(complex_samples, dtype=np.complex64)
        mod_bytes       = complex_array.tobytes()

        # 5) UDP(8890)로 전송
        sock_send.sendto(mod_bytes, (GMSK_SEND_IP, GMSK_SEND_PORT))
        print(f"[test3.py] Sent {len(mod_bytes)} bytes to {GMSK_SEND_IP}:{GMSK_SEND_PORT}")

if __name__ == "__main__":
    main()

