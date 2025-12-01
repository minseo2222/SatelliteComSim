#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import time
import signal
import argparse
import subprocess
from pathlib import Path
from typing import Optional, Tuple

ROOT = Path(__file__).resolve().parent
LOG_DIR = ROOT / "log"
LOG_DIR.mkdir(parents=True, exist_ok=True)

# 관리할 프로세스 정의 (실행 순서: test4 -> test3 -> test2 -> test1)
# test4: Downlink 수신 (UDP 1235 -> 8890)
# test3: Downlink 파싱 및 CSV 저장
# test2: Uplink 물리 엔진 (GroundSystem과 연동, UDP 8600 -> 1234)
# test1: Uplink 패킷 생성 (test1 -> UDP 8600)
PROCS = [
    ("test4", "test4.py"),
    ("test3", "test3.py"),
    ("test2", "test2.py"),
    ("test1", "test1.py"),
]

# --- [보완] 실행 환경 설정 (PYTHONPATH 자동 추가) ---
def get_run_env():
    """
    gr-leo 및 GNU Radio 라이브러리 경로를 자동으로 포함한 환경 변수를 반환합니다.
    사용자가 터미널에서 export를 안 해도 되게 해줍니다.
    """
    env = os.environ.copy()
    
    # 추가할 후보 경로들 (시스템마다 다를 수 있어 여러 개 지정)
    candidate_paths = [
        "/usr/local/lib/python3.8/dist-packages",
        "/usr/local/lib/python3/dist-packages",
        "/usr/lib/python3/dist-packages",
        str(ROOT)  # 현재 프로젝트 폴더도 포함
    ]
    
    current_pythonpath = env.get("PYTHONPATH", "")
    
    # 경로가 없으면 추가
    for p in candidate_paths:
        if p not in current_pythonpath and os.path.isdir(p):
            if current_pythonpath:
                current_pythonpath = f"{p}:{current_pythonpath}"
            else:
                current_pythonpath = p
    
    env["PYTHONPATH"] = current_pythonpath
    return env

def pid_file(name: str) -> Path:
    return LOG_DIR / f"{name}.pid"

def log_file(name: str) -> Path:
    return LOG_DIR / f"{name}.log"

def abs_script(name: str, rel: str) -> Path:
    return (ROOT / rel).resolve()

def _read_pid(p: Path) -> Optional[int]:
    try:
        s = p.read_text().strip()
        if not s:
            return None
        return int(s)
    except Exception:
        return None

def _proc_cmdline(pid: int) -> str:
    try:
        with open(f"/proc/{pid}/cmdline", "rb") as f:
            data = f.read().replace(b"\x00", b" ").strip()
            return data.decode(errors="ignore")
    except Exception:
        return ""

def _proc_exists(pid: int) -> bool:
    if pid <= 0: return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except Exception:
        return False

def _matches_script(pid: int, script_path: Path) -> bool:
    cmd = _proc_cmdline(pid)
    target = str(script_path)
    # 스크립트 경로가 커맨드라인에 포함되어 있는지 확인
    return (target in cmd)

def is_running(name: str, script_path: Path) -> Tuple[bool, Optional[int]]:
    pf = pid_file(name)
    if not pf.exists():
        return (False, None)
    
    pid = _read_pid(pf)
    if not pid:
        return (False, None)
    
    if not _proc_exists(pid):
        return (False, None)
        
    if not _matches_script(pid, script_path):
        return (False, None)
        
    return (True, pid)

def _popen_detached(cmd, cwd: str, log_fd, env):
    """플랫폼별 백그라운드(detached group) 실행"""
    if os.name == "nt":
        return subprocess.Popen(
            cmd,
            stdout=log_fd,
            stderr=subprocess.STDOUT,
            cwd=cwd,
            env=env,  # [보완] 환경변수 전달
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
        )
    else:
        return subprocess.Popen(
            cmd,
            stdout=log_fd,
            stderr=subprocess.STDOUT,
            cwd=cwd,
            env=env,  # [보완] 환경변수 전달
            preexec_fn=os.setsid
        )

def start_one(name: str, script_rel: str, skip_if_running: bool = True) -> bool:
    spath = abs_script(name, script_rel)
    if not spath.is_file():
        print(f"[ERROR] {name}: 스크립트를 찾을 수 없음 -> {spath}")
        return False

    running, pid = is_running(name, spath)
    if running:
        if skip_if_running:
            print(f"[SKIP] {name}: 이미 실행 중 (pid={pid})")
            return True
        else:
            stop_one(name, script_rel)
            time.sleep(0.5)

    # PID 파일 정리
    pf = pid_file(name)
    if pf.exists():
        try: pf.unlink()
        except: pass

    lf = log_file(name)
    lf.parent.mkdir(parents=True, exist_ok=True)
    log_fd = open(lf, "a", buffering=1, encoding="utf-8", errors="ignore")
    
    # 실행 인자 (버퍼링 없이 실행 -u)
    cmd = [sys.executable, "-u", str(spath)]
    
    # test2.py의 경우 --use-leo 옵션을 기본으로 넣고 싶다면 여기서 분기 처리 가능
    # 하지만 test2.py가 config.json을 읽도록 수정했으므로 인자 없이 실행해도 됨.
    
    run_env = get_run_env() # 환경변수 가져오기

    try:
        p = _popen_detached(cmd, str(ROOT), log_fd, run_env)
        pid_file(name).write_text(str(p.pid))
        print(f"[OK  ] {name}: 시작됨 (pid={p.pid}) -> {lf.name}")
        return True
    except Exception as e:
        print(f"[ERROR] {name}: 시작 실패 -> {e}")
        return False

def stop_one(name: str, script_rel: str) -> bool:
    spath = abs_script(name, script_rel)
    running, pid = is_running(name, spath)
    pf = pid_file(name)
    
    if not running:
        if pf.exists():
            try: pf.unlink()
            except: pass
        print(f"[OK  ] {name}: 이미 중지됨")
        return True

    # 프로세스 종료 시도
    try:
        if os.name == "nt":
            os.kill(pid, signal.SIGTERM)
        else:
            os.killpg(pid, signal.SIGTERM)
    except Exception:
        pass

    # 종료 대기
    for _ in range(30): # 3초 대기
        time.sleep(0.1)
        if not _proc_exists(pid):
            break
    else:
        # 강제 종료
        try:
            print(f"[WARN] {name}: 강제 종료(SIGKILL) 시도...")
            if os.name == "nt":
                os.kill(pid, signal.SIGKILL)
            else:
                os.killpg(pid, signal.SIGKILL)
        except Exception:
            pass

    if pf.exists():
        try: pf.unlink()
        except: pass

    print(f"[OK  ] {name}: 중지됨")
    return True

def status_one(name: str, script_rel: str):
    spath = abs_script(name, script_rel)
    running, pid = is_running(name, spath)
    if running:
        print(f"[RUN ] {name}: pid={pid} log={log_file(name)}")
    else:
        print(f"[STOP] {name}")

def action_start(force: bool = False):
    print(f"==================================================")
    print(f"[INFO] 전체 시뮬레이션 프로세스 시작")
    print(f"[INFO] 경로: {ROOT}")
    print(f"==================================================")
    
    if force:
        action_stop()
        time.sleep(1.0)
        
    for name, rel in PROCS:
        ok = start_one(name, rel, skip_if_running=not force)
        # 순차적 실행 안정성을 위해 약간의 딜레이
        time.sleep(0.5 if ok else 0.0)
    
    print("--------------------------------------------------")
    print("[DONE] 모든 프로세스 시작 완료.")
    print("       로그 확인: tail -f log/*.log")

def action_stop():
    print(f"==================================================")
    print(f"[INFO] 전체 시뮬레이션 프로세스 중지")
    print(f"==================================================")
    # 역순 종료 (test1 -> test2 -> test3 -> test4)
    for name, rel in reversed(PROCS):
        stop_one(name, rel)
        time.sleep(0.2)
    print("[DONE] 모든 프로세스 중지 완료.")

def action_restart():
    action_start(force=True)

def action_status():
    print(f"==================================================")
    print(f"[INFO] 프로세스 상태 확인")
    print(f"==================================================")
    for name, rel in PROCS:
        status_one(name, rel)

def parse_args():
    p = argparse.ArgumentParser(description="Satellite Sim Batch Launcher")
    p.add_argument("action", nargs="?", default="start",
                   choices=["start", "stop", "restart", "status"])
    p.add_argument("--force", action="store_true", help="강제 재시작")
    return p.parse_args()

def main():
    args = parse_args()
    if args.action == "start":
        action_start(force=args.force)
    elif args.action == "stop":
        action_stop()
    elif args.action == "restart":
        action_restart()
    elif args.action == "status":
        action_status()

if __name__ == "__main__":
    main()
