#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test3.py: cFS에서 들어오는 sample_app 메시지(MID=0x08A9)만 필터링하여
프리앰블(0xAA, 0xAA)을 붙인 뒤 GMSK 변조하여
UDP(8890)로 송신합니다. sample_app 본문은 더 이상 자르지 않고 CCSDS 전체 패킷을 전송합니다.
"""

import socket
import time
import struct
import numpy as np
from gnuradio import gr, blocks, digital

CFS_LISTEN_IP    = "0.0.0.0"
CFS_LISTEN_PORT  = 1235
GMSK_SEND_IP     = "127.0.0.1"
GMSK_SEND_PORT   = 8890
SAMPLE_APP_MID   = 0x08A9

class GMSKModulator(gr.top_block):
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
    if len(data) < 2:
        return None
    return struct.unpack_from(">H", data, 0)[0]

def main():
    sock_recv = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock_recv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock_recv.bind((CFS_LISTEN_IP, CFS_LISTEN_PORT))

    sock_send = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    print(f"[test3.py] Listening for cFS on {CFS_LISTEN_IP}:{CFS_LISTEN_PORT} ...")

    while True:
        data, addr = sock_recv.recvfrom(4096)
        msg_id = get_msg_id(data)

        if msg_id != SAMPLE_APP_MID:
            continue

        print(f"[test3.py] Received sample_app packet ({len(data)} bytes) from {addr}")

        # 전체 CCSDS 패킷을 그대로 사용
        preamble = [0xAA, 0xAA]
        orig_bytes = list(data)  # 자르지 않음
        packet_bytes = preamble + orig_bytes

        tb = GMSKModulator(packet_bytes)
        tb.start()
        time.sleep(0.1)
        tb.stop()
        tb.wait()

        complex_samples = tb.get_modulated_data()
        complex_array   = np.array(complex_samples, dtype=np.complex64)
        mod_bytes       = complex_array.tobytes()

        sock_send.sendto(mod_bytes, (GMSK_SEND_IP, GMSK_SEND_PORT))
        print(f"[test3.py] Sent {len(mod_bytes)} bytes to {GMSK_SEND_IP}:{GMSK_SEND_PORT}")

if __name__ == "__main__":
    main()

