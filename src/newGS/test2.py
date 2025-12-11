#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test2.py — Space Channel & Advanced Attack Simulator (With Replay)

Attacks Implemented:
  1. Drop: Probabilistic / Burst Drop
  2. Jamming: Probabilistic / Header Protect / Ratio
  3. Replay: Probabilistic / Replay Delay (sends copy after N seconds)
  
  * Replaces Length Mod with Replay Attack.
"""

import os
import json
import time
import random
import heapq
import threading
import argparse
import socket
import csv
from datetime import datetime
from struct import unpack

from gnuradio import gr, blocks
import pmt


def load_config_json():
    candidates = []
    env_p = os.environ.get("TEST2_CONFIG")
    if env_p: candidates.append(env_p)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    candidates.append(os.path.join(script_dir, "test2_config.json"))

    for p in candidates:
        try:
            if p and os.path.isfile(p):
                with open(p, "r", encoding="utf-8") as f: return json.load(f)
        except: pass
    return None

def apply_config_overrides(args, cfg: dict):
    if not cfg: return args
    def setv(k, dst):
        if k in cfg: setattr(args, dst, cfg[k])
    setv("listen_ip", "listen_ip"); setv("listen_port", "listen_port")
    setv("dst_ip", "dst_ip"); setv("dst_port", "dst_port"); setv("mtu", "mtu")
    setv("base_delay_ms", "base_delay_ms"); setv("jitter_ms", "jitter_ms")
    setv("ber", "ber"); setv("seed", "seed")
    if "mode" in cfg:
        m = str(cfg["mode"]).lower().strip()
        args.full_ber = (m == "full")
        args.payload_only = not args.full_ber
    setv("tlm08a9_len_off", "tlm08a9_len_off")
    setv("tlm08a9_text_off", "tlm08a9_text_off")
    setv("tlm08a9_text_max", "tlm08a9_text_max")
    setv("ctrl_bind_ip", "ctrl_bind_ip"); setv("ctrl_port", "ctrl_port")
    return args

def now_ts(): return datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
def be16(b: bytes): return unpack(">H", b)[0]
def extract_mid(pkt: bytes): return be16(pkt[0:2]) if len(pkt) >= 2 else -1
def extract_seq_count(pkt: bytes):
    if len(pkt) >= 4: return ((pkt[2] & 0x3F) << 8) | pkt[3]
    return -1
def text_region_for_tlm_08a9(pkt: bytes, len_off=12, text_off=14, text_max=128):
    if len(pkt) < text_off: return None
    try: text_len = be16(pkt[len_off:len_off+2])
    except: return None
    text_len = max(0, min(int(text_len), int(text_max)))
    return (int(text_off), min(len(pkt), int(text_off) + text_len))

def flip_bits_inplace(buf: bytearray, ber: float, rng: random.Random, start=0, end=None):
    if ber <= 0.0: return
    L = len(buf); s = max(0, start); e = L if end is None else max(0, min(L, end))
    if s >= e: return
    for i in range(s, e):
        b = buf[i]
        for _ in range(8):
            if rng.random() < ber: b ^= (1 << _)
        buf[i] = b

class PduLogger(gr.basic_block):
    def __init__(self, label="IN"):
        gr.basic_block.__init__(self, name=f"PduLogger({label})", in_sig=None, out_sig=None)
        self.label = label
        self.message_port_register_in(pmt.intern("pdus"))
        self.set_msg_handler(pmt.intern("pdus"), self._handler)
        self.message_port_register_out(pmt.intern("pdus"))
    def _handler(self, msg):
        self.message_port_pub(pmt.intern("pdus"), msg)

class PduSpaceChannel(gr.basic_block):
    HEADER_PROTECT_SIZE = 8

    def __init__(self, base_delay_ms=0.0, jitter_ms=0.0, ber=0.0, seed=0xBEEF,
                 payload_only=True, tlm08a9_len_off=12, tlm08a9_text_off=14, tlm08a9_text_max=128):
        gr.basic_block.__init__(self, name="PduSpaceChannel", in_sig=None, out_sig=None)
        
        self.base_delay_ms = float(base_delay_ms)
        self.jitter_ms = float(jitter_ms)
        self.ber = float(ber)
        self.rng = random.Random(int(seed))
        self.payload_only = bool(payload_only)
        self.len_off = int(tlm08a9_len_off)
        self.text_off = int(tlm08a9_text_off)
        self.text_max = int(tlm08a9_text_max)
        
        # Attack Params
        self.attack_mode = "none"
        self.attack_prob = 100.0
        self.burst_size = 1
        self.burst_remaining = 0
        self.jamming_protect = 8
        self.jamming_ratio = 100.0
        self.replay_delay = 1.0  # [New]

        self.log_path = "attack_log.csv"
        try:
            with open(self.log_path, "w", newline="") as f:
                csv.writer(f).writerow(["Timestamp", "SeqCount", "AttackMode", "Result", "Details"])
            print(f"[TEST2] Log initialized: {self.log_path}")
        except: pass

        self._lock = threading.Lock()
        self.message_port_register_in(pmt.intern("pdus"))
        self.set_msg_handler(pmt.intern("pdus"), self._handler)
        self.message_port_register_out(pmt.intern("pdus"))

        self._send_heap = []
        self._stop = False
        self._tx_thread = threading.Thread(target=self._tx_worker, daemon=True)
        self._tx_thread.start()

    def set_params(self, **kw):
        with self._lock:
            if "base_delay_ms" in kw: self.base_delay_ms = float(kw["base_delay_ms"])
            if "jitter_ms" in kw: self.jitter_ms = float(kw["jitter_ms"])
            if "ber" in kw: self.ber = float(kw["ber"])
            
            if "attack_mode" in kw: 
                self.attack_mode = str(kw["attack_mode"]).lower()
                print(f"[TEST2] Mode: {self.attack_mode}")
            if "attack_prob" in kw: self.attack_prob = float(kw["attack_prob"])
            
            if "burst_size" in kw: self.burst_size = int(kw["burst_size"])
            if "jamming_protect" in kw: self.jamming_protect = int(kw["jamming_protect"])
            if "jamming_ratio" in kw: self.jamming_ratio = float(kw["jamming_ratio"])
            if "replay_delay" in kw: self.replay_delay = float(kw["replay_delay"])

    def _write_log(self, seq, mode, result, details=""):
        try:
            with open(self.log_path, "a", newline="") as f:
                csv.writer(f).writerow([now_ts(), seq, mode, result, details])
        except: pass

    def _now_ns(self): return time.monotonic_ns()
    def _schedule_send(self, meta, data, delay_s):
        t = self._now_ns() + int(max(0, delay_s) * 1e9)
        heapq.heappush(self._send_heap, (t, (meta, data)))

    def _tx_worker(self):
        while not self._stop:
            if not self._send_heap:
                time.sleep(0.0005)
                continue
            t_ns, _ = self._send_heap[0]
            curr = self._now_ns()
            if t_ns > curr:
                time.sleep(min((t_ns - curr)/1e9, 0.001))
                continue
            _, (meta, data) = heapq.heappop(self._send_heap)
            m_pmt = pmt.to_pmt(meta) if meta else pmt.PMT_NIL
            d_pmt = pmt.init_u8vector(len(data), list(data))
            self.message_port_pub(pmt.intern("pdus"), pmt.cons(m_pmt, d_pmt))

    def _handler(self, msg):
        try:
            meta = pmt.to_python(pmt.car(msg))
            vec = pmt.cdr(msg)
            data = bytes(bytearray(pmt.u8vector_elements(vec)))
        except: return

        modified = bytearray(data)
        mode = self.attack_mode
        seq = extract_seq_count(data)
        
        do_attack = False
        if mode == "drop" and self.burst_remaining > 0: do_attack = True
        elif mode != "none":
            if self.rng.random() * 100.0 <= self.attack_prob: do_attack = True

        if do_attack:
            if mode == "drop":
                if self.burst_remaining <= 0: self.burst_remaining = self.burst_size
                self.burst_remaining -= 1
                self._write_log(seq, "Drop", "Dropped", f"BurstRem={self.burst_remaining}")
                return 

            elif mode == "jamming":
                prot = self.jamming_protect
                if len(modified) > prot:
                    payload_len = len(modified) - prot
                    jam_count = int(payload_len * (self.jamming_ratio / 100.0))
                    jam_count = max(0, min(jam_count, payload_len))
                    for i in range(prot, prot + jam_count):
                        modified[i] = self.rng.getrandbits(8)
                self._write_log(seq, "Jamming", "Modified", f"Ratio={self.jamming_ratio}%")

            elif mode == "replay":
                # Replay: Original is sent at end, Schedule duplicate here
                dup_delay = self.replay_delay
                self._schedule_send(meta, bytes(modified), dup_delay) # Duplicate
                self._write_log(seq, "Replay", "Scheduled", f"Delay={dup_delay}s")
                # Original continues to be sent below
        else:
            if mode != "none": self._write_log(seq, mode, "Passed", "Prob check")

        # BER Logic
        cur_ber = self.ber
        if cur_ber > 0.0:
            if self.payload_only:
                mid = extract_mid(modified)
                if mid == 0x08A9:
                    region = text_region_for_tlm_08a9(modified, self.len_off, self.text_off, self.text_max)
                    if region:
                        s, e = region
                        flip_bits_inplace(modified, cur_ber, self.rng, s, e)
            else:
                flip_bits_inplace(modified, cur_ber, self.rng)

        # Normal Send (with jitter)
        base = self.base_delay_ms / 1000.0
        jitter = self.jitter_ms / 1000.0
        delay_s = max(0.0, self.rng.gauss(base, jitter/3.0)) if jitter > 0 else max(0.0, base)
        self._schedule_send(meta, bytes(modified), delay_s)

    def stop(self):
        self._stop = True
        try: self._tx_thread.join(timeout=1.0)
        except: pass
        return super().stop()


class UplinkUdpRelay(gr.top_block):
    def __init__(self, args, cfg):
        super().__init__()
        self.listen_ip = cfg.get("listen_ip", args.listen_ip)
        self.listen_port = int(cfg.get("listen_port", args.listen_port))
        self.dst_ip = cfg.get("dst_ip", args.dst_ip)
        self.dst_port = int(cfg.get("dst_port", args.dst_port))
        
        self.udp_in = blocks.socket_pdu("UDP_SERVER", self.listen_ip, str(self.listen_port), 1472, True)
        self.log_in = PduLogger("IN ")
        self.space = PduSpaceChannel(
            cfg.get("base_delay_ms", 0), cfg.get("jitter_ms", 0), cfg.get("ber", 0), cfg.get("seed", 0xBEEF),
            (not args.full_ber) and args.payload_only,
            args.tlm08a9_len_off, args.tlm08a9_text_off, args.tlm08a9_text_max
        )
        self.log_fwd = PduLogger("FWD")
        self.udp_out = blocks.socket_pdu("UDP_CLIENT", self.dst_ip, str(self.dst_port), 1472, True)
        
        self.msg_connect(self.udp_in, "pdus", self.log_in, "pdus")
        self.msg_connect(self.log_in, "pdus", self.space, "pdus")
        self.msg_connect(self.space, "pdus", self.log_fwd, "pdus")
        self.msg_connect(self.log_fwd, "pdus", self.udp_out, "pdus")
        
        self._start_ctrl_server(cfg.get("ctrl_port", 9696))

    def _start_ctrl_server(self, port):
        def worker():
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.bind(("0.0.0.0", int(port)))
            while True:
                try:
                    data, _ = s.recvfrom(65535)
                    msg = json.loads(data)
                    if msg.get("cmd") == "set": self.space.set_params(**msg["params"])
                except: pass
        threading.Thread(target=worker, daemon=True).start()

    def stop(self):
        self._stop_ctrl = True
        return super().stop()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--listen-port", default=8600)
    ap.add_argument("--dst-port", default=1234)
    ap.add_argument("--dst-ip", default="127.0.0.1")
    ap.add_argument("--listen-ip", default="0.0.0.0")
    ap.add_argument("--payload-only", action="store_true")
    ap.add_argument("--full-ber", action="store_true")
    ap.add_argument("--tlm08a9-len-off", default=12)
    ap.add_argument("--tlm08a9-text-off", default=14)
    ap.add_argument("--tlm08a9-text-max", default=128)
    args = ap.parse_args()
    
    cfg = load_config_json() or {}
    args = apply_config_overrides(args, cfg)
    
    tb = UplinkUdpRelay(args, cfg)
    tb.start()
    try:
        while True: time.sleep(1)
    except: pass
    tb.stop()

if __name__ == "__main__":
    main()
