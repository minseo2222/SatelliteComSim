#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test2.py — Uplink GNURadio PDU UDP relay with LEO Satellite Channel Physics
"""

import os
import json
import time
import random
import heapq
import threading
import argparse
import socket
import math
from datetime import datetime, timedelta
from struct import unpack
from typing import Tuple, Optional  # <--- ★ [수정됨] 이 부분이 추가되었습니다.

from gnuradio import gr, blocks
import pmt

# --- gr-leo 라이브러리 임포트 시도 ---
try:
    from gnuradio import leo
    LEO_AVAILABLE = True
except ImportError:
    try:
        import leo
        LEO_AVAILABLE = True
    except ImportError:
        LEO_AVAILABLE = False
        print("[WARNING] 'leo' module not found. Physics simulation with gr-leo will be disabled.")

# ---------------------- 기본 설정 ----------------------
DEFAULT_TLE_1 = "1 25544U 98067A   18268.52547184  .00016717  00000-0  10270-3 0  9019"
DEFAULT_TLE_2 = "2 25544  51.6373 238.6885 0003885 206.9748 153.1203 15.53729445 14114"
SPEED_OF_LIGHT = 299792458.0

# ---------------------- 패킷 처리 유틸 ----------------------
def now_ts(): return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
def extract_mid(pkt: bytes) -> int: return unpack(">H", pkt[0:2])[0] if len(pkt) >= 2 else -1

def text_region_for_tlm_08a9(pkt: bytes, len_off=12, text_off=14, text_max=128):
    if len(pkt) < text_off: return None
    try:
        text_len = unpack(">H", pkt[len_off:len_off+2])[0]
    except: return None
    text_len = max(0, min(int(text_len), int(text_max)))
    start = int(text_off); end = min(len(pkt), start + text_len)
    return (start, end) if end > start else None

def flip_bits_inplace(buf: bytearray, ber: float, rng: random.Random, start: int = 0, end: Optional[int] = None):
    if ber <= 0.0: return
    L = len(buf); s = max(0, start); e = L if end is None else max(0, min(L, end))
    if s >= e: return
    for i in range(s, e):
        b = buf[i]
        for bit in range(8):
            if rng.random() < ber: b ^= (1 << bit)
        buf[i] = b

# ---------------------- 로거 블록 ----------------------
class PduLogger(gr.basic_block):
    def __init__(self, label="IN"):
        gr.basic_block.__init__(self, name=f"PduLogger({label})", in_sig=None, out_sig=None)
        self.label = label
        self.message_port_register_in(pmt.intern("pdus"))
        self.set_msg_handler(pmt.intern("pdus"), self._handler)
        self.message_port_register_out(pmt.intern("pdus"))

    def _handler(self, msg):
        try:
            vec = pmt.cdr(msg)
            data = bytes(bytearray(pmt.u8vector_elements(vec)))
            print(f"[{self.label}] {now_ts()} len={len(data)} MID=0x{extract_mid(data):04X}")
        except: pass
        self.message_port_pub(pmt.intern("pdus"), msg)

# ---------------------- 우주환경 블록 (물리 엔진) ----------------------
class PduSpaceChannel(gr.basic_block):
    def __init__(self, cfg):
        gr.basic_block.__init__(self, name="PduSpaceChannel", in_sig=None, out_sig=None)
        
        # 설정 로드
        self.base_delay_ms = float(cfg.get("base_delay_ms", 0.0))
        self.jitter_ms = float(cfg.get("jitter_ms", 0.0))
        self.ber = float(cfg.get("ber", 0.0))
        self.rng = random.Random(int(cfg.get("seed", 0xBEEF)))
        self.payload_only = bool(cfg.get("payload_only", True))
        
        # 통신/물리 파라미터 (초기값)
        self.use_leo = cfg.get("use_leo", False) and LEO_AVAILABLE
        self.sat_name = cfg.get("sat_name", "ISS")
        
        # [위성 파라미터]
        self.sat_tx_power_dbm = 30.0  # 기본 30dBm (1W)
        self.sat_ant_gain_dbi = 0.0   # 등방성
        self.uplink_freq = 437e6      # 437 MHz

        # [지상국 파라미터]
        self.gs_lat = 36.350413
        self.gs_lon = 127.384548
        self.gs_alt = 50.0
        self.gs_ant_gain_dbi = 0.0
        self.gs_min_elev = 5.0        # 최소 앙각 5도

        # gr-leo 객체
        self.tracker = None
        self.satellite = None
        
        if self.use_leo: self._init_leo_physics()

        # 스레드 설정
        self._lock = threading.Lock()
        self.message_port_register_in(pmt.intern("pdus"))
        self.set_msg_handler(pmt.intern("pdus"), self._handler)
        self.message_port_register_out(pmt.intern("pdus"))
        self._send_heap = []
        self._stop = False
        self._tx_thread = threading.Thread(target=self._tx_worker, daemon=True)
        self._tx_thread.start()

    def _init_leo_physics(self):
        print(f"[PduSpaceChannel] Init Physics for {self.sat_name} (Freq:{self.uplink_freq/1e6}MHz, Pwr:{self.sat_tx_power_dbm}dBm)...")
        try:
            # 안테나 패턴 생성 (기본 Dipole 사용, 이득은 수식에서 별도 계산)
            if hasattr(leo, 'antenna'):
                ant = leo.antenna.dipole_antenna.make(0, self.uplink_freq, 0, 0)
            else:
                ant = leo.dipole_antenna.make(0, self.uplink_freq, 0, 0)

            # 위성 생성
            self.satellite = leo.satellite.make(
                self.sat_name, DEFAULT_TLE_1, DEFAULT_TLE_2,
                self.uplink_freq, 145e6, self.sat_tx_power_dbm, ant, ant, 12, 190, 1200
            )

            # 트래커 생성
            start_t = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.0000000Z")
            end_t = (datetime.utcnow() + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%S.0000000Z")
            
            if hasattr(leo, 'tracker'):
                self.tracker = leo.tracker.make(
                    self.satellite, self.gs_lat, self.gs_lon, self.gs_alt,
                    start_t, end_t, 1000, self.uplink_freq, 145e6, 300.0, ant, ant, 1, 210, 19200
                )
            else:
                 self.tracker = leo.tracker_make(
                    self.satellite, self.gs_lat, self.gs_lon, self.gs_alt,
                    start_t, end_t, 1000, self.uplink_freq, 145e6, 300.0, ant, ant, 1, 210, 19200
                )
            print("[PduSpaceChannel] Physics initialized.")
        except Exception as e:
            print(f"[PduSpaceChannel] ERROR: {e}")
            self.use_leo = False

    def set_params(self, **kw):
        with self._lock:
            # 기본 통신 설정
            if "base_delay_ms" in kw: self.base_delay_ms = float(kw["base_delay_ms"])
            if "jitter_ms" in kw: self.jitter_ms = float(kw["jitter_ms"])
            if "ber" in kw: self.ber = float(kw["ber"])
            
            need_reinit = False
            # 지상국 설정 반영
            if "gs_lat" in kw: self.gs_lat = float(kw["gs_lat"]); need_reinit = True
            if "gs_lon" in kw: self.gs_lon = float(kw["gs_lon"]); need_reinit = True
            if "gs_alt" in kw: self.gs_alt = float(kw["gs_alt"]); need_reinit = True
            if "min_elevation" in kw: self.gs_min_elev = float(kw["min_elevation"])
            if "gs_antenna_gain" in kw: self.gs_ant_gain_dbi = float(kw["gs_antenna_gain"])

            # 위성 설정 반영
            if "sat_name" in kw: self.sat_name = str(kw["sat_name"]); need_reinit = True
            if "frequency" in kw: self.uplink_freq = float(kw["frequency"]); need_reinit = True
            if "transmit_power" in kw: self.sat_tx_power_dbm = float(kw["transmit_power"])
            if "antenna_gain" in kw: self.sat_ant_gain_dbi = float(kw["antenna_gain"])

            if "use_leo" in kw and LEO_AVAILABLE:
                new_use = bool(kw["use_leo"])
                if new_use and not self.use_leo: need_reinit = True
                self.use_leo = new_use

            if need_reinit and self.use_leo:
                self._init_leo_physics()

    def _calculate_physics(self) -> Tuple[float, float]:
        """ 궤도 역학 및 링크 버젯 계산 """
        if not self.tracker: return (0.0, 0.0)
        try:
            # 1. 거리 및 앙각 계산
            dist_km = 400.0
            elev_deg = 90.0
            if hasattr(self.tracker, "get_range"): dist_km = self.tracker.get_range()
            if hasattr(self.tracker, "get_elevation"): elev_deg = self.tracker.get_elevation()

            dist_m = dist_km * 1000.0
            delay_s = dist_m / SPEED_OF_LIGHT
            if dist_m < 1.0: dist_m = 1.0

            # [가시성 체크] 최소 앙각보다 낮으면 통신 두절 (BER=0.5)
            if elev_deg < self.gs_min_elev:
                return delay_s, 0.5 # Link Lost

            # 2. 경로 손실 (Free Space Path Loss)
            # FSPL(dB) = 20log10(d) + 20log10(f) - 147.55
            path_loss_db = 20 * math.log10(dist_m) + 20 * math.log10(self.uplink_freq) - 147.55
            
            # 3. 도플러 효과 페널티
            doppler_hz = 0.0
            if hasattr(self.tracker, "get_range_rate"):
                rr = self.tracker.get_range_rate()
                doppler_hz = - (rr / SPEED_OF_LIGHT) * self.uplink_freq
            
            # 3kHz 이상 벗어나면 추가 손실 (예시 모델)
            doppler_loss_db = 0.0
            if abs(doppler_hz) > 3000.0:
                doppler_loss_db = (abs(doppler_hz) - 3000.0) / 1000.0 * 1.0 # 1kHz당 1dB 감쇄

            # 4. Link Budget (수신 전력 계산)
            # Rx_Power = Tx_Power + Tx_Gain + Rx_Gain - Path_Loss - Doppler_Loss
            rx_power_dbm = self.sat_tx_power_dbm + self.sat_ant_gain_dbi + self.gs_ant_gain_dbi \
                           - path_loss_db - doppler_loss_db
            
            # SNR 계산 (Noise Floor는 -110dBm 가정)
            noise_floor_dbm = -110.0
            snr_db = rx_power_dbm - noise_floor_dbm
            snr_linear = 10 ** (snr_db / 10.0)
            
            # BER 계산 (BPSK 근사)
            if snr_linear <= 0: ber = 0.5
            else:
                ber = 0.5 * math.erfc(math.sqrt(snr_linear))
                if ber < 1e-9: ber = 0.0

            return delay_s, ber

        except Exception:
            return (0.001, 0.0)

    def _handler(self, msg):
        # (기존 패킷 처리 로직과 동일)
        try:
            meta = pmt.to_python(pmt.car(msg))
            vec = pmt.cdr(msg)
            data = bytes(bytearray(pmt.u8vector_elements(vec)))
        except: meta = {}; data = b""

        if self.use_leo:
            d_s, ber_val = self._calculate_physics()
            cur_delay = d_s; cur_ber = ber_val
        else:
            cur_delay = self.base_delay_ms / 1000.0; cur_ber = self.ber

        modified = bytearray(data)
        if cur_ber > 0.0:
            if self.payload_only:
                mid = extract_mid(modified)
                if mid == 0x08A9:
                    r = text_region_for_tlm_08a9(modified, self.len_off, self.text_off, self.text_max)
                    if r: flip_bits_inplace(modified, cur_ber, self.rng, r[0], r[1])
            else:
                flip_bits_inplace(modified, cur_ber, self.rng)

        base = cur_delay
        jitter = self.jitter_ms / 1000.0
        delay_s = max(0.0, self.rng.gauss(base, jitter/3.0)) if jitter > 0 else base
        self._schedule_send(meta, bytes(modified), delay_s)

    def _now_ns(self): return time.monotonic_ns()
    def _sleep_until_ns(self, t_ns):
        while True:
            diff = t_ns - self._now_ns()
            if diff <= 0: break
            time.sleep(min(diff/1e9, 0.001))
    def _schedule_send(self, meta, data, delay_s):
        t = self._now_ns() + int(max(0.0, delay_s)*1e9)
        heapq.heappush(self._send_heap, (t, (meta, data)))
    def _tx_worker(self):
        while not self._stop:
            if not self._send_heap: time.sleep(0.0005); continue
            t_ns, _ = self._send_heap[0]
            self._sleep_until_ns(t_ns)
            while self._send_heap and self._send_heap[0][0] <= self._now_ns():
                _, (m, d) = heapq.heappop(self._send_heap)
                out = pmt.cons(pmt.to_pmt(m), pmt.init_u8vector(len(d), list(d)))
                self.message_port_pub(pmt.intern("pdus"), out)
    def stop(self):
        self._stop = True
        try: self._tx_thread.join(1.0)
        except: pass
        return True

# ---------------------- 메인 ----------------------
class UplinkUdpRelay(gr.top_block):
    def __init__(self, **kwargs):
        super().__init__()
        self.cfg = kwargs
        self.udp_in = blocks.socket_pdu("UDP_SERVER", self.cfg.get("listen_ip"), str(self.cfg.get("listen_port")), int(self.cfg.get("mtu")), True)
        self.log_in = PduLogger("IN ")
        self.space = PduSpaceChannel(self.cfg)
        self.log_fwd = PduLogger("FWD")
        self.udp_out = blocks.socket_pdu("UDP_CLIENT", self.cfg.get("dst_ip"), str(self.cfg.get("dst_port")), int(self.cfg.get("mtu")), True)
        self.msg_connect(self.udp_in, "pdus", self.log_in, "pdus")
        self.msg_connect(self.log_in, "pdus", self.space, "pdus")
        self.msg_connect(self.space, "pdus", self.log_fwd, "pdus")
        self.msg_connect(self.log_fwd, "pdus", self.udp_out, "pdus")
        self._start_ctrl_server()

    def _start_ctrl_server(self):
        self._stop_ctrl = False
        self._ctrl_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._ctrl_sock.bind((self.cfg.get("ctrl_bind_ip","127.0.0.1"), int(self.cfg.get("ctrl_port",9696))))
        def worker():
            while not self._stop_ctrl:
                self._ctrl_sock.settimeout(0.5)
                try: data, addr = self._ctrl_sock.recvfrom(65535)
                except: continue
                try:
                    msg = json.loads(data)
                    if msg.get("cmd") == "set":
                        self.space.set_params(**msg.get("params", {}))
                        self._ctrl_sock.sendto(b'{"ok":true}', addr)
                except: pass
        self._ctrl_thr = threading.Thread(target=worker, daemon=True)
        self._ctrl_thr.start()
    def stop(self):
        self._stop_ctrl = True
        try: self._ctrl_sock.close()
        except: pass
        return super().stop()

def main():
    # 설정 파일 로드
    cfg = {}
    cfg_path = os.environ.get("TEST2_CONFIG", os.path.join(os.path.dirname(os.path.abspath(__file__)), "test2_config.json"))
    try:
        with open(cfg_path, "r") as f: cfg = json.load(f)
    except: pass
    
    # CLI 인자 파싱 (설정 파일보다 우선)
    ap = argparse.ArgumentParser()
    ap.add_argument("--listen-ip", default="0.0.0.0"); ap.add_argument("--listen-port", type=int, default=8600)
    ap.add_argument("--dst-ip", default="127.0.0.1"); ap.add_argument("--dst-port", type=int, default=1234)
    ap.add_argument("--mtu", type=int, default=1472)
    ap.add_argument("--use-leo", action="store_true"); ap.add_argument("--sat-name", default="ISS")
    args = ap.parse_args()
    
    # 병합
    for k,v in vars(args).items():
        if v: cfg[k] = v # CLI 값이 있으면 덮어씀
    if "listen_ip" not in cfg: cfg["listen_ip"] = "0.0.0.0"
    if "listen_port" not in cfg: cfg["listen_port"] = 8600
    if "dst_ip" not in cfg: cfg["dst_ip"] = "127.0.0.1"
    if "dst_port" not in cfg: cfg["dst_port"] = 1234
    if "mtu" not in cfg: cfg["mtu"] = 1472

    tb = UplinkUdpRelay(**cfg)
    tb.start()
    print(f"[test2] Started. Physics: {'ON' if tb.space.use_leo else 'OFF'}")
    try:
        while True: time.sleep(1)
    except KeyboardInterrupt: pass
    tb.stop()
    tb.wait()

if __name__ == "__main__":
    main()
