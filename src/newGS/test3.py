#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import socket, struct, csv
from pathlib import Path
from datetime import datetime

LISTEN_IP, LISTEN_PORT = "0.0.0.0", 8890

# ---- 필터: SAMPLE_APP 텍스트 텔레메트리 후보 ----
FILTER_SID = {0x08A9, 0x1882}   # Stream ID로 보이는 값들
FILTER_APID = {0x0882, 0x08A9}  # APID로 보이는 값들

ROOTDIR = Path(__file__).resolve().parent
LOG_DIR = ROOTDIR / "log"; LOG_DIR.mkdir(parents=True, exist_ok=True)
RECV_CSV = LOG_DIR / "sample_app_recv.csv"

def now_ts(): return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def ensure_csv_header(p, hdr):
    if (not p.exists()) or p.stat().st_size == 0:
        with open(p, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(hdr)

def to_hex(b): return "".join(f"{x:02X}" for x in b)
def bytes_to_bits(b): return "".join(f"{x:08b}" for x in b)

def parse_ccsds_header(pkt):
    if len(pkt) < 6: return None
    (sid, seq_raw, length) = struct.unpack(">HHH", pkt[:6])
    apid = sid & 0x07FF
    # [수정] Sequence Count 14bit 추출 (상위 2비트 플래그 제외)
    seq_count = seq_raw & 0x3FFF
    return {"sid": sid, "apid": apid, "seq": seq_count, "len": length, "total_len": length + 7}

def is_sample_text(hdr):
    sid = hdr["sid"]; apid = hdr["apid"]
    return (sid in FILTER_SID) or (apid in FILTER_APID)

def extract_text_bytes(pkt: bytes) -> bytes:
    if len(pkt) >= 14:
        try:
            # SAMPLE_TextTlm_t의 TextLen은 현재 런타임에서 little-endian으로 들어온다.
            text_len = pkt[12] | (pkt[13] << 8)
            text_len = max(0, min(text_len, 128, len(pkt) - 14))
            return pkt[14:14 + text_len]
        except Exception:
            pass
    if len(pkt) > 8:
        return pkt[8:].split(b"\x00", 1)[0]
    return b""

def extract_text(pkt: bytes) -> str:
    """SAMPLE_APP Text TLM (포맷 A/B 시도)"""
    raw = extract_text_bytes(pkt)
    if raw:
        try:
            text = raw.split(b"\x00", 1)[0].decode("utf-8", errors="ignore")
            if text:
                return text
        except Exception:
            pass
    return ""

def split_id_text(text: str):
    sid = ""
    body = text
    parts = text.split(":", 1)
    if len(parts) == 2 and parts[0].isdigit():
        sid, body = parts[0], parts[1]
    return sid, body

def main():
    # [수정] CSV 헤더에 'seq' 추가 (test1과 통일)
    ensure_csv_header(RECV_CSV, [
        "ts","direction","id","text","mid_hex","apid_hex","cc_dec",
        "seq", "len", "src_ip","src_port","head_hex16","text_hex","bits",
        "payload_hex","payload_bits"
    ])

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((LISTEN_IP, LISTEN_PORT))
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4*1024*1024)

    print(f"[test3] Listening from test4 on {LISTEN_IP}:{LISTEN_PORT} ...")
    print(f"[test3] Showing only SAMPLE_APP Text TLM (sid in {sorted(FILTER_SID)}, apid in {sorted(FILTER_APID)})")

    while True:
        data, addr = sock.recvfrom(4096)
        src_ip, src_port = addr
        hdr = parse_ccsds_header(data)
        if not hdr: continue

        cc = data[6] if len(data) > 6 else None
        head_hex16 = " ".join(f"{b:02X}" for b in data[:16])

        if not is_sample_text(hdr): continue

        raw_payload = extract_text_bytes(data)
        text = extract_text(data)
        sid_str, text_body = split_id_text(text)

        # 콘솔 출력 (Seq 포함)
        print(f"[test3] [TEXT] {now_ts()} sid=0x{hdr['sid']:04X} seq={hdr['seq']} cc={(cc if cc is not None else -1)} text={text!r}")

        # CSV 기록
        text_bytes = text_body.encode("utf-8", errors="ignore")
        text_hex   = to_hex(text_bytes)
        bits = bytes_to_bits(text_bytes)
        if bits: bits = "b:" + bits
        payload_hex = to_hex(raw_payload)
        payload_bits = bytes_to_bits(raw_payload)
        if payload_bits: payload_bits = "b:" + payload_bits

        with open(RECV_CSV, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow([
                now_ts(), "recv", sid_str, text_body,
                f"0x{hdr['sid']:04X}", f"0x{hdr['apid']:04X}",
                (cc if cc is not None else ""), 
                hdr['seq'], # [수정] Seq 저장
                len(data),
                src_ip, src_port, head_hex16, text_hex, bits,
                payload_hex, payload_bits
            ])

if __name__ == "__main__":
    main()
