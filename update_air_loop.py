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


def fetch_and_update():
    now = datetime.datetime.now()
    now_hour = now.hour

    print(f"\n[{now}] 현재 시각: {now_hour}")

    if now_hour < 7 or now_hour > 17:
        print("조회 시간 아님. 대기...")
        return False

    print("API 호출 시작")

    try:
        station_data = {}

        for station in STATIONS:
            print(f"{station} API 호출 시작")

            params = PARAMS.copy()
            params["stationName"] = station

            res = requests.get(URL, params=params, verify=False, timeout=15)
            print(f"{station} 응답코드:", res.status_code)

            if res.status_code != 200:
                print(f"{station} API 오류({res.status_code}) → 다음 측정소 확인")
                continue

            data = res.json()
            items = data["response"]["body"].get("items", [])

            valid_items = [
                i for i in items
                if is_valid_value(i.get("pm10Value")) or is_valid_value(i.get("pm25Value"))
            ]

            if not valid_items:
                print(f"{station} 사용 가능한 pm10/pm25 데이터 없음 → 다음 측정소 확인")
                continue

            candidate = max(
                valid_items,
                key=lambda x: parse_data_time(x["dataTime"])
            )

            candidate_dt = parse_data_time(candidate["dataTime"])

            if candidate_dt.hour != now_hour:
                print(f"{station} 현재 시간 데이터 아님({candidate['dataTime']}) → 다음 측정소 확인")
                continue

            station_data[station] = candidate

            print(f"{station} 현재 시간 dataTime:", candidate["dataTime"])
            print(f"{station} pm10:", candidate.get("pm10Value"))
            print(f"{station} pm25:", candidate.get("pm25Value"))

        gohyeon = station_data.get("고현동")
        aju = station_data.get("아주동")

        if not gohyeon and not aju:
            print("고현동/아주동 모두 현재 시간 데이터 없음")
            return False

        pm10 = None
        pm25 = None
        pm10_station = None
        pm25_station = None
        data_time = None

        if gohyeon:
            data_time = gohyeon["dataTime"]

            if is_valid_value(gohyeon.get("pm10Value")):
                pm10 = gohyeon["pm10Value"]
                pm10_station = "고현동"

            if is_valid_value(gohyeon.get("pm25Value")):
                pm25 = gohyeon["pm25Value"]
                pm25_station = "고현동"

        if aju:
            if data_time is None:
                data_time = aju["dataTime"]

            if pm10 is None and is_valid_value(aju.get("pm10Value")):
                pm10 = aju["pm10Value"]
                pm10_station = "아주동"

            if pm25 is None and is_valid_value(aju.get("pm25Value")):
                pm25 = aju["pm25Value"]
                pm25_station = "아주동"

        if pm10 is None and pm25 is None:
            print("pm10/pm25 모두 유효값 없음")
            return False

        data_dt = parse_data_time(data_time)
        data_hour = data_dt.hour
        used_station = f"미세먼지:{pm10_station}, 초미세먼지:{pm25_station}"

        result = {
            "stationName": used_station,
            "pm10": pm10,
            "pm25": pm25,
            "pm10Station": pm10_station,
            "pm25Station": pm25_station,
            "dataHour": data_hour,
            "dataTime": data_time,
            "labelTime": f"{data_dt.month}. {data_dt.day}. {data_hour}시"
        }

        with open(air_json_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False)

        print("air.json 저장 완료")
        print("사용 값:", used_station)

        subprocess.run(["git", "add", "air.json"], cwd=base_dir)

        diff_check = subprocess.run(
            ["git", "diff", "--cached", "--quiet"],
            cwd=base_dir
        )

        if diff_check.returncode == 0:
            print("변경사항 없음 → commit 안 함")
        else:
            subprocess.run(["git", "commit", "-m", "update air"], cwd=base_dir)
            subprocess.run(["git", "push"], cwd=base_dir)
            print("GitHub 업데이트 완료")

        return pm10_station == "고현동" and pm25_station == "고현동"

    except Exception as e:
        print("오류 발생:", e)
        return False

try:
    # 🔁 메인 루프
    while True:
        try:
            updated = fetch_and_update()

            now = datetime.datetime.now()

            if updated:
                next_hour = (now + datetime.timedelta(hours=1)).replace(
                    minute=10,
                    second=5,
                    microsecond=0
                )

                wait_seconds = (next_hour - now).total_seconds()

                print(f"다음 시간 10분까지 대기: {int(wait_seconds)}초")
                time.sleep(wait_seconds)

            else:
                minute = now.minute

                # 10분~30분까지는 2분마다 재조회
                if 10 <= minute < 30:
                    wait_seconds = 120

                # 그 외 시간은 다음 시간 10분까지 대기
                else:
                    next_try = (now + datetime.timedelta(hours=1)).replace(
                        minute=10,
                        second=5,
                        microsecond=0
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