#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, sys, csv, time, socket, pathlib, subprocess, shlex, signal, traceback, threading

# ===== 설정 =====
GS_LISTEN_HOST = os.getenv("GS_LISTEN_HOST", "0.0.0.0")
GS_LISTEN_PORT = int(os.getenv("GS_LISTEN_PORT", "50000"))   # GS→test1 수신
UPLINK_DST_HOST = os.getenv("UPLINK_DST_HOST", "127.0.0.1")
UPLINK_DST_PORT = int(os.getenv("UPLINK_DST_PORT", "1234"))  # GNURadio 미사용 → CI_LAB 직결

LOG_DIR = pathlib.Path(os.getenv("LOG_DIR", "log")); LOG_DIR.mkdir(parents=True, exist_ok=True)
CSV_PATH = LOG_DIR / "sample_app_sent.csv"

SETUP_SCRIPT = os.getenv("TOLAB_SETUP_SCRIPT",
    str((pathlib.Path(__file__).parent / "scripts" / "setup_tolab_08a9.sh").resolve()))
SETUP_TIMEOUT_SEC = int(os.getenv("TOLAB_SETUP_TIMEOUT_SEC", "12"))
SKIP_SETUP = os.getenv("TOLAB_SKIP_SETUP", "0") == "1"

# ===== 유틸 =====
def now_ts(): return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

def ensure_csv_header(path: pathlib.Path):
    found = path.exists() and path.stat().st_size > 0
    f = path.open("a", newline="", encoding="utf-8"); w = csv.writer(f)
    if not found:
        w.writerow(["ts","src_ip","src_port","len","apid_hex","mid_hex","cc_dec","head_hex16","ascii_preview"])
    return f, w

def ascii_preview(b: bytes, n: int = 32):
    return "".join(chr(ch) if 32 <= ch < 127 else "." for ch in b[:n])

def parse_ccsds_apid_mid_cc(data: bytes):
    apid = mid = cc = None
    if len(data) >= 2:
        apid = ((data[0] & 0x07) << 8) | data[1]
        mid = apid
    if len(data) > 6: cc = data[6]
    return apid, mid, cc

# ===== 스크립트 비동기 실행 =====
def run_setup_script_async():
    if SKIP_SETUP:
        print(f"[{now_ts()}] [INIT] skip by env TOLAB_SKIP_SETUP=1")
        return
    if not os.path.isfile(SETUP_SCRIPT):
        print(f"[{now_ts()}] [INIT][WARN] setup script not found: {SETUP_SCRIPT}")
        return
    def _run():
        cmd = ["/usr/bin/env", "bash", SETUP_SCRIPT]
        print(f"[{now_ts()}] [INIT] running (async): {' '.join(shlex.quote(c) for c in cmd)}")
        try:
            cp = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                timeout=SETUP_TIMEOUT_SEC, check=False, text=True)
            print(f"[{now_ts()}] [INIT] rc={cp.returncode}")
            if cp.stdout: print(f"[INIT][STDOUT]\n{cp.stdout.strip()}")
            if cp.stderr: print(f"[INIT][STDERR]\n{cp.stderr.strip()}")
        except subprocess.TimeoutExpired:
            print(f"[{now_ts()}] [INIT][ERROR] setup timeout ({SETUP_TIMEOUT_SEC}s)")
        except Exception as e:
            print(f"[{now_ts()}] [INIT][EXCEPTION] {e}\n{traceback.format_exc()}")
    threading.Thread(target=_run, daemon=True).start()

def main():
    print(f"[{now_ts()}] test1 starting…")

    # 1) 먼저 바인딩부터 해서 수신/로깅 가능하게
    try:
        in_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        in_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        in_sock.bind((GS_LISTEN_HOST, GS_LISTEN_PORT))
        print(f"[{now_ts()}] listening on {GS_LISTEN_HOST}:{GS_LISTEN_PORT}")
    except Exception as e:
        print(f"[{now_ts()}] [BIND][ERROR] {e}\n{traceback.format_exc()}"); sys.exit(1)

    out_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    print(f"[{now_ts()}] forwarding to {UPLINK_DST_HOST}:{UPLINK_DST_PORT}")

    f, writer = ensure_csv_header(CSV_PATH)
    last_flush = time.time()

    # 2) 시작 직후 비동기로 초기화(스크립트)
    run_setup_script_async()

    running = True
    def _handle(sig, frame):
        nonlocal running; running = False
    signal.signal(signal.SIGINT, _handle); signal.signal(signal.SIGTERM, _handle)

    while running:
        try:
            data, addr = in_sock.recvfrom(65535)
        except Exception as e:
            print(f"[{now_ts()}] [RECV][ERROR] {e}\n{traceback.format_exc()}"); break

        src_ip, src_port = addr
        apid, mid, cc = parse_ccsds_apid_mid_cc(data)
        head_hex16 = " ".join(f"{b:02X}" for b in data[:16])
        preview = ascii_preview(data)

        # 콘솔 한 줄: 예전처럼 보이게
        print(f"[RECV] {src_ip}:{src_port} len={len(data)} apid=0x{(apid or 0):04X} "
              f"cc={(cc if cc is not None else -1)} head={head_hex16}")
        if cc == 3 and len(data) > 8:
            msg_txt = data[8:].split(b'\x00', 1)[0].decode('utf-8', errors='ignore')
            print(f"[TEXT] {msg_txt}")      
        # CSV 기록
        writer.writerow([now_ts(), src_ip, src_port, len(data),
                         f"0x{(apid or 0):04X}", f"0x{(mid or 0):04X}",
                         (cc if cc is not None else -1), head_hex16, preview])

        try:
            out_sock.sendto(data, (UPLINK_DST_HOST, UPLINK_DST_PORT))
            print(f"[FWD ] -> {UPLINK_DST_HOST}:{UPLINK_DST_PORT} len={len(data)}")
        except Exception as e:
            print(f"[{now_ts()}] [SEND][ERROR] {e}\n{traceback.format_exc()}")

        if time.time() - last_flush >= 1.0:
            try: f.flush()
            except Exception: pass
            last_flush = time.time()

    try: f.flush(); f.close()
    except Exception: pass
    in_sock.close(); out_sock.close()
    print(f"[{now_ts()}] test1 stopped.")

if __name__ == "__main__":
    # python -u 추천 (버퍼링 방지)
    main()

