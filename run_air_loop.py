# run_air_loop.py
# 기존 프로세스 정리 + 안전한 PID Lock + 메인 실행기

import os
import sys
import time
import signal
import psutil
import subprocess

LOCK_FILE = "air_loop.lock"
SCRIPT_NAME = "update_air_loop.py"


def is_process_running(pid):
    try:
        process = psutil.Process(pid)

        cmdline = " ".join(process.cmdline()).lower()

        return (
            process.is_running()
            and SCRIPT_NAME.lower() in cmdline
        )

    except:
        return False


def remove_stale_lock():
    if not os.path.exists(LOCK_FILE):
        return

    try:
        with open(LOCK_FILE, "r") as f:
            pid = int(f.read().strip())

        if is_process_running(pid):
            print(f"이미 실행 중입니다. PID: {pid}")
            sys.exit()

        else:
            print("죽은 프로세스의 lock 발견 → 삭제")
            os.remove(LOCK_FILE)

    except:
        print("lock 파일 손상 → 삭제")
        os.remove(LOCK_FILE)


def kill_existing_processes():
    current_pid = os.getpid()

    for proc in psutil.process_iter(["pid", "name", "cmdline"]):

        try:
            pid = proc.info["pid"]

            if pid == current_pid:
                continue

            cmdline = " ".join(proc.info["cmdline"] or []).lower()

            if SCRIPT_NAME.lower() in cmdline:
                print(f"기존 프로세스 종료: PID {pid}")
                proc.kill()

        except:
            pass


def create_lock():
    with open(LOCK_FILE, "w") as f:
        f.write(str(os.getpid()))


def cleanup(*args):
    print("종료 처리 중...")

    if os.path.exists(LOCK_FILE):
        os.remove(LOCK_FILE)

    sys.exit()


signal.signal(signal.SIGINT, cleanup)
signal.signal(signal.SIGTERM, cleanup)


# 1. 기존 프로세스 종료
kill_existing_processes()

time.sleep(2)

# 2. 오래된 lock 정리
remove_stale_lock()

# 3. 새 lock 생성
create_lock()

print("새 루프 실행")

os.execv(sys.executable, [sys.executable, SCRIPT_NAME])