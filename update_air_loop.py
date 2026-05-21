import os
import sys
import datetime

base_dir = os.path.dirname(os.path.abspath(__file__))

LOCK_FILE = os.path.join(base_dir, "air_loop.lock")

# 이전 실행 중 남은 lock 파일 제거
if os.path.exists(LOCK_FILE):
    try:
        os.remove(LOCK_FILE)
    except:
        pass

# 새 lock 파일 생성
with open(LOCK_FILE, "w", encoding="utf-8") as f:
    f.write(str(os.getpid()))

today = datetime.datetime.now().strftime("%Y-%m-%d")
log_path = os.path.join(base_dir, f"air_loop_log_{today}.txt")

class Logger:
    def write(self, message):
        with open(log_path, "a", encoding="utf-8-sig", errors="ignore") as f:
            f.write(message)

    def flush(self):
        pass

sys.stdout = Logger()
sys.stderr = Logger()

print("\n==============================")
print("루프 시작:", datetime.datetime.now())

import requests
import urllib3
import json
import datetime
import subprocess
import sys
import os
import time

CREATE_NO_WINDOW = 0x08000000

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

URL = "https://apis.data.go.kr/B552584/ArpltnInforInqireSvc/getMsrstnAcctoRltmMesureDnsty"

PARAMS = {
    "serviceKey": "587751fffeb679c7184b091460e67cf605d7dfaa01e1c1c8d709aa03b79d4226",
    "returnType": "json",
    "numOfRows": "24",
    "pageNo": "1",
    "stationName": "고현동",
    "dataTerm": "DAILY",
    "ver": "1.3"
}

STATIONS = ["고현동", "아주동"]

base_dir = os.path.dirname(os.path.abspath(__file__))
air_json_path = os.path.join(base_dir, "air.json")

def parse_data_time(value):
    date_part, time_part = value.split(" ")
    hour, minute = map(int, time_part.split(":"))

    if hour == 24:
        base_date = datetime.datetime.strptime(date_part, "%Y-%m-%d")
        next_date = base_date + datetime.timedelta(days=1)
        return next_date.replace(hour=0, minute=minute)

    return datetime.datetime.strptime(value, "%Y-%m-%d %H:%M")


def is_valid_value(value):
    return str(value).isdigit()


def is_valid_item(item):
    return (
        is_valid_value(item.get("pm10Value"))
        and is_valid_value(item.get("pm25Value"))
    )


def get_latest_valid_item(station):
    print(f"{station} API 호출 시작")

    params = PARAMS.copy()
    params["stationName"] = station

    res = requests.get(URL, params=params, verify=False, timeout=15)
    print(f"{station} 응답코드:", res.status_code)

    if res.status_code != 200:
        print(f"{station} API 오류({res.status_code})")
        return None

    data = res.json()
    items = data["response"]["body"].get("items", [])

    valid_items = [i for i in items if is_valid_item(i)]

    if not valid_items:
        print(f"{station} 유효 데이터 없음")
        return None

    latest = max(valid_items, key=lambda x: parse_data_time(x["dataTime"]))

    print(f"{station} 최신 dataTime:", latest["dataTime"])
    print(f"{station} pm10:", latest.get("pm10Value"))
    print(f"{station} pm25:", latest.get("pm25Value"))

    return latest


def fetch_and_update():
    now = datetime.datetime.now()
    now_hour = now.hour

    print(f"\n[{now}] 현재 시각: {now_hour}")

    if now_hour < 7 or now_hour > 17:
        print("조회 시간 아님. 대기...")
        return False

    print("API 호출 시작")

    try:
        gohyeon = get_latest_valid_item("고현동")
        aju = None

        selected = None
        used_station = None
        source_note = None

        if gohyeon:
            gohyeon_dt = parse_data_time(gohyeon["dataTime"])
            diff_hours = (now - gohyeon_dt).total_seconds() / 3600

            if gohyeon_dt.hour == now_hour:
                selected = gohyeon
                used_station = "고현동"
                source_note = "고현동 현재 시간 데이터"

            elif diff_hours < 3:
                selected = gohyeon
                used_station = "고현동"
                source_note = "고현동 최신 데이터"

            else:
                print("고현동 데이터 3시간 이상 지연 → 아주동 확인")
                aju = get_latest_valid_item("아주동")

        if selected is None and aju:
            selected = aju
            used_station = "아주동"
            source_note = "고현동 데이터 지연으로 아주동 데이터 사용"

        if selected is None:
            print("고현동/아주동 모두 유효 데이터 없음")
            return False

        data_time = selected["dataTime"]
        data_dt = parse_data_time(data_time)
        data_hour = data_dt.hour

        result = {
            "stationName": used_station,
            "sourceNote": source_note,
            "pm10": selected["pm10Value"],
            "pm25": selected["pm25Value"],
            "dataHour": data_hour,
            "dataTime": data_time,
            "labelTime": f"{data_dt.month}. {data_dt.day}. {data_hour}시"
        }

        subprocess.run(
            ["git", "pull", "--rebase", "origin", "main"],
            cwd=base_dir,
            creationflags=CREATE_NO_WINDOW
        )

        with open(air_json_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False)

        print("air.json 저장 완료")
        print("사용 측정소:", used_station)
        print("사용 기준:", source_note)
 
        subprocess.run(
            ["git", "add", "air.json"],
            cwd=base_dir,
            creationflags=CREATE_NO_WINDOW
        )

        diff_check = subprocess.run(
            ["git", "diff", "--cached", "--quiet"],
            cwd=base_dir,
            creationflags=CREATE_NO_WINDOW
        )

        if diff_check.returncode == 0:
            print("변경사항 없음 → commit 안 함")
        else:
            subprocess.run(
                ["git", "commit", "-m", "update air"],
                cwd=base_dir,
                creationflags=CREATE_NO_WINDOW
            )

            subprocess.run(
                ["git", "push"],
                cwd=base_dir,
                creationflags=CREATE_NO_WINDOW
            )
            print("GitHub 업데이트 완료")

        return used_station == "고현동" and data_hour == now_hour

    except Exception as e:
        print("오류 발생:", e)
        return False

try:
    # 🔁 메인 루프
    while True:
        try:
            updated = fetch_and_update()

            now = datetime.datetime.now()
            minute = now.minute

# 00~09분 → 10분까지 대기
            if minute < 10:
                next_try = now.replace(
                    minute=10,
                    second=0,
                    microsecond=0
                )

                wait_seconds = (next_try - now).total_seconds()

# 10~29분 → 2분마다 재조회
            elif minute < 30:
                wait_seconds = 120

# 30분 이후 → 다음 시간 10분까지 대기
            else:
                next_try = (
                    now.replace(
                        minute=10,
                        second=0,
                        microsecond=0
                    )
                    + datetime.timedelta(hours=1)
                )

                wait_seconds = (next_try - now).total_seconds()

            print(f"다음 조회까지 대기: {int(wait_seconds)}초")
            time.sleep(wait_seconds)

        except Exception as e:
            print("루프 오류:", e)
            time.sleep(60)

finally:
    if os.path.exists(LOCK_FILE):
        os.remove(LOCK_FILE)