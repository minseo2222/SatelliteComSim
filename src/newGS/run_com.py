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

def start_process(name, script_rel):
    spath = (ROOT / script_rel).resolve()
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
        for name, script in PROCS:
            p = start_process(name, script)
            if p:
                children.append((name, p))
                time.sleep(1) # 순차 실행 대기
        
        print("\n[RUNNING] 모든 프로세스가 실행되었습니다. 종료하려면 Ctrl+C를 누르세요.")
        while True:
            time.sleep(1)
            # 죽은 프로세스 확인
            for name, p in children:
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
                if os.name != "nt":
                    try: os.killpg(os.getpgid(p.pid), signal.SIGTERM)
                    except: p.terminate()
                else:
                    p.terminate()
                print(f" - {name} 종료됨")

if __name__ == "__main__":
    main()
