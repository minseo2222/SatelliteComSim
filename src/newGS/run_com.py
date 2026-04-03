#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
import time
import signal
import argparse
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LOG_DIR = ROOT / "log"
LOG_DIR.mkdir(parents=True, exist_ok=True)

PROCS = [
    ("test4", "test4.py"), # Downlink
    ("test3", "test3.py"), # CSV Log
    ("test2", "test2.py"), # Uplink Physics Engine
    ("test1", "test1.py"), # Traffic Gen
    ("GroundSystem", "GroundSystem.py") # GUI
]

STOP_GRACE_SEC = 2.0
NEWGS_PORTS = {1235, 50000, 50001, 8600, 8890, 9696}

def get_run_env():
    """ PYTHONPATH 자동 설정 """
    env = os.environ.copy()
    paths = [
        "/usr/local/lib/python3.8/dist-packages",
        "/usr/local/lib/python3/dist-packages",
        str(ROOT)
    ]
    curr = env.get("PYTHONPATH", "")
    for p in paths:
        if p not in curr and os.path.isdir(p):
            curr = f"{p}:{curr}" if curr else p
    env["PYTHONPATH"] = curr
    # 버퍼링 비활성화
    env["PYTHONUNBUFFERED"] = "1"
    return env

def abs_script(script_rel: str) -> Path:
    return (ROOT / script_rel).resolve()

def _proc_cmdline(pid: int) -> str:
    try:
        data = Path(f"/proc/{pid}/cmdline").read_bytes()
    except Exception:
        return ""
    return data.replace(b"\x00", b" ").decode(errors="ignore").strip()

def _find_matching_pids(script_path: Path):
    current_pid = os.getpid()
    matches = []
    for proc_dir in Path("/proc").iterdir():
        if not proc_dir.name.isdigit():
            continue
        pid = int(proc_dir.name)
        if pid == current_pid:
            continue
        cmdline = _proc_cmdline(pid)
        if str(script_path) in cmdline:
            matches.append(pid)
    return matches

def _signal_process(pid: int, sig: int):
    if os.name == "nt":
        try:
            os.kill(pid, sig)
            return
        except ProcessLookupError:
            return
    try:
        os.killpg(pid, sig)
    except ProcessLookupError:
        return
    except Exception:
        try:
            os.kill(pid, sig)
        except ProcessLookupError:
            return

def _pid_exists(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except Exception:
        return False

def _terminate_pid(pid: int, grace_sec: float = STOP_GRACE_SEC):
    _signal_process(pid, signal.SIGTERM)
    deadline = time.time() + grace_sec
    while time.time() < deadline:
        if not _pid_exists(pid):
            return True
        time.sleep(0.1)
    _signal_process(pid, signal.SIGKILL)
    deadline = time.time() + 1.0
    while time.time() < deadline:
        if not _pid_exists(pid):
            return True
        time.sleep(0.05)
    return not _pid_exists(pid)

def _socket_inodes_for_ports(ports):
    inodes = set()
    proc_files = [Path("/proc/net/udp"), Path("/proc/net/udp6")]
    for proc_file in proc_files:
        try:
            lines = proc_file.read_text().splitlines()
        except Exception:
            continue
        for line in lines[1:]:
            parts = line.split()
            if len(parts) < 10:
                continue
            try:
                local_addr = parts[1]
                inode = parts[9]
                hex_port = local_addr.split(":")[1]
                port = int(hex_port, 16)
            except Exception:
                continue
            if port in ports:
                inodes.add(inode)
    return inodes

def _pids_for_socket_inodes(inodes):
    if not inodes:
        return set()
    current_pid = os.getpid()
    pids = set()
    for proc_dir in Path("/proc").iterdir():
        if not proc_dir.name.isdigit():
            continue
        pid = int(proc_dir.name)
        if pid == current_pid:
            continue
        fd_dir = proc_dir / "fd"
        try:
            for fd in fd_dir.iterdir():
                try:
                    target = os.readlink(fd)
                except OSError:
                    continue
                if target.startswith("socket:["):
                    inode = target[8:-1]
                    if inode in inodes:
                        pids.add(pid)
                        break
        except Exception:
            continue
    return pids

def cleanup_port_occupants():
    stale_pids = _pids_for_socket_inodes(_socket_inodes_for_ports(NEWGS_PORTS))
    if not stale_pids:
        return

    print("[INFO] newGS 전용 포트 점유 프로세스를 정리합니다...")
    for pid in sorted(stale_pids):
        ok = _terminate_pid(pid)
        status = "정리됨" if ok else "정리 실패"
        print(f" - pid={pid} {status}")
    time.sleep(0.3)

def cleanup_existing_processes():
    stale = []
    for name, script_rel in PROCS:
        script_path = abs_script(script_rel)
        for pid in _find_matching_pids(script_path):
            stale.append((name, script_path, pid))

    if not stale:
        return

    print("[INFO] 기존 실행 잔여 프로세스를 정리합니다...")
    for name, _, pid in stale:
        ok = _terminate_pid(pid)
        status = "정리됨" if ok else "정리 실패"
        print(f" - {name} pid={pid} {status}")
    time.sleep(0.3)

def start_process(name, script_rel):
    spath = abs_script(script_rel)
    if not spath.exists():
        print(f"[ERROR] {name}: 파일 없음 ({spath})")
        return None

    log_path = LOG_DIR / f"{name}.log"
    log_fd = open(log_path, "w", encoding="utf-8") # 덮어쓰기 모드

    print(f"[INFO] {name} 시작... (Log: {log_path.name})")
    
    try:
        # 새 세션으로 실행 (Ctrl+C 전파 방지용 등)
        if os.name == "nt":
            p = subprocess.Popen([sys.executable, "-u", str(spath)], 
                                 cwd=str(ROOT), env=get_run_env(), 
                                 stdout=log_fd, stderr=subprocess.STDOUT,
                                 creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
        else:
            p = subprocess.Popen([sys.executable, "-u", str(spath)], 
                                 cwd=str(ROOT), env=get_run_env(), 
                                 stdout=log_fd, stderr=subprocess.STDOUT,
                                 preexec_fn=os.setsid)
        return p
    except Exception as e:
        print(f"[ERROR] {name} 실행 실패: {e}")
        return None

def main():
    print(f"=== 위성 통신 시뮬레이터 통합 런처 ===")
    print(f"경로: {ROOT}")
    
    children = []
    
    try:
        cleanup_existing_processes()
        cleanup_port_occupants()

        for name, script in PROCS:
            p = start_process(name, script)
            if p:
                children.append((name, p))
                time.sleep(1) # 순차 실행 대기
        
        print("\n[RUNNING] 모든 프로세스가 실행되었습니다. 종료하려면 Ctrl+C를 누르세요.")
        while True:
            time.sleep(1)
            # 죽은 프로세스 확인
            for name, p in list(children):
                if p.poll() is not None:
                    print(f"[WARN] {name} 프로세스가 종료되었습니다 (Code: {p.returncode})")
                    children.remove((name, p))
            if not children:
                break

    except KeyboardInterrupt:
        print("\n[STOP] 종료 요청 감지. 모든 프로세스를 정리합니다...")
    finally:
        for name, p in children:
            if p.poll() is None:
                ok = _terminate_pid(p.pid)
                status = "종료됨" if ok else "종료 실패"
                print(f" - {name} {status}")

if __name__ == "__main__":
    main()
