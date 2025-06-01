#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_com.py

SatelliteComSim/src/newGS 디렉토리에 있는 GroundSystem.py와
test1.py~test4.py를 한 번에 실행하도록 하는 런처 스크립트입니다.

- 실행 위치: newGS 폴더 내부에서 `./run_com.py` 로 실행
- 각 프로세스의 stdout을 터미널에 prefix와 함께 출력해 줍니다.
"""

import subprocess
import threading
import os
import sys
import time

# =========================
# 1) newGS 내부 스크립트 경로들
# =========================

# GroundSystem.py는 이제 newGS 폴더 안에 있습니다.
GS_CMD    = ["python3", "GroundSystem.py"]   # GS 실행 커맨드
TEST1_CMD = ["python3", "test1.py"]
TEST2_CMD = ["python3", "test2.py"]
TEST3_CMD = ["python3", "test3.py"]
TEST4_CMD = ["python3", "test4.py"]

# =========================
# 2) 프로세스 출력 포워딩 함수
# =========================

def forward_output(proc, name):
    """
    proc.stdout에서 한 줄씩 읽어와 '[name] ...' 형식으로 터미널에 출력합니다.
    """
    if proc.stdout is None:
        return
    for raw_line in proc.stdout:
        try:
            line = raw_line.decode('utf-8', errors='ignore').rstrip("\n")
        except:
            line = str(raw_line)
        print(f"[{name}] {line}")
    proc.stdout.close()

# =========================
# 3) 프로세스 실행 후 상태를 확인하는 헬퍼
# =========================

def check_process_started(proc, name, delay=0.5):
    """
    Popen한 proc가 delay 초 뒤에도 살아 있는지(poll() is None) 확인합니다.
    만약 종료되었다면 stderr/stdout 버퍼에 남은 내용을 읽어와 에러로 출력합니다.
    """
    time.sleep(delay)
    if proc.poll() is not None:
        # 이미 종료되어 있다면
        print(f"[run_com.py] ERROR: '{name}' 프로세스가 바로 종료되었습니다.  exit code={proc.poll()}")
        try:
            # stdout에 에러 로그가 남아 있을 수 있으므로 읽어서 보여준다
            out = proc.stdout.read().decode('utf-8', errors='ignore')
            if out:
                print(f"[{name}] stdout/stderr 로그:\n{out}")
        except Exception:
            pass


# =========================
# 4) 메인 실행 로직
# =========================

def main():
    # 1) 현재 작업 디렉토리를 run_com.py가 있는 newGS 폴더로 맞춥니다.
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    print(f"[run_com.py] Working directory: {script_dir}\n")

    procs = []

    # -------------------------
    # 2) GroundSystem.py 실행
    # -------------------------
    print("[run_com.py] ▶ GS(GroundSystem.py) 실행 중…")
    try:
        p_gs = subprocess.Popen(
            GS_CMD,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT
        )
        procs.append(("GS", p_gs))
        # GS가 초기화될 충분한 시간 대기
        check_process_started(p_gs, "GS")
    except FileNotFoundError:
        print(f"[run_com.py] ERROR: GS_CMD({GS_CMD}) 실행 파일을 찾을 수 없습니다.")
        print("             newGS 폴더 내부에 GroundSystem.py가 있는지 확인하세요.\n")
    except Exception as e:
        print(f"[run_com.py] GS 실행 중 오류: {e}\n")

    # -------------------------
    # 3) test1.py 실행
    # -------------------------
    print("[run_com.py] ▶ test1.py 실행 중…")
    p1 = subprocess.Popen(
        TEST1_CMD,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT
    )
    procs.append(("test1", p1))
    check_process_started(p1, "test1")

    # -------------------------
    # 4) test2.py 실행
    # -------------------------
    print("[run_com.py] ▶ test2.py 실행 중…")
    p2 = subprocess.Popen(
        TEST2_CMD,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT
    )
    procs.append(("test2", p2))
    check_process_started(p2, "test2")

    # -------------------------
    # 5) test3.py 실행
    # -------------------------
    print("[run_com.py] ▶ test3.py 실행 중…")
    p3 = subprocess.Popen(
        TEST3_CMD,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT
    )
    procs.append(("test3", p3))
    check_process_started(p3, "test3")

    # -------------------------
    # 6) test4.py 실행
    # -------------------------
    print("[run_com.py] ▶ test4.py 실행 중…")
    p4 = subprocess.Popen(
        TEST4_CMD,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT
    )
    procs.append(("test4", p4))
    check_process_started(p4, "test4")

    # -------------------------
    # 7) 각 프로세스 stdout을 별도 스레드에서 읽어와서 출력
    # -------------------------
    threads = []
    for name, proc in procs:
        if proc.stdout is None:
            continue
        t = threading.Thread(target=forward_output, args=(proc, name), daemon=True)
        t.start()
        threads.append(t)

    # -------------------------
    # 8) Ctrl+C 입력 시 모든 프로세스 종료
    # -------------------------
    try:
        for name, proc in procs:
            proc.wait()
    except KeyboardInterrupt:
        print("\n[run_com.py] Ctrl+C 감지: 모든 서브프로세스를 종료합니다...")
        for _, proc in procs:
            proc.terminate()
        sys.exit(0)

if __name__ == "__main__":
    main()

