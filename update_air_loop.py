import sys
import os
import datetime

base_dir = os.path.dirname(os.path.abspath(__file__))
today = datetime.datetime.now().strftime("%Y-%m-%d")
log_path = os.path.join(base_dir, f"air_loop_log_{today}.txt")

class Logger:
    def write(self, message):
        with open(log_path, "a", encoding="utf-8") as f:
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


def fetch_and_update():
    now = datetime.datetime.now()
    now_hour = now.hour

    print(f"\n[{now}] 현재 시각: {now_hour}")

    if now_hour < 7 or now_hour > 17:
        print("조회 시간 아님. 대기...")
        return False

    if os.path.exists(air_json_path):
        try:
            with open(air_json_path, "r", encoding="utf-8") as f:
                old_data = json.load(f)

            saved_hour = old_data.get("dataHour")
            saved_station = old_data.get("stationName")

            print("기존 저장 hour:", saved_hour)
            print("기존 저장 측정소:", saved_station)

            if str(saved_hour) == str(now_hour) and saved_station == "고현동":
                print("이미 현재 시간 고현동 데이터 있음")
                return True

            if str(saved_hour) == str(now_hour) and saved_station == "아주동":
                print("현재 시간 아주동 데이터 있음 → 고현동 재확인 진행")

        except Exception as e:
            print("기존 JSON 읽기 실패:", e)

    print("API 호출 시작")

    try:
        latest = None
        used_station = None

        for station in STATIONS:
            print(f"{station} API 호출 시작")

            params = PARAMS.copy()
            params["stationName"] = station

            res = requests.get(URL, params=params, verify=False, timeout=15)
            print(f"{station} 응답코드:", res.status_code)

            data = res.json()
            items = data["response"]["body"].get("items", [])

            valid = [
                i for i in items
                if str(i.get("pm10Value", "")).isdigit()
                and str(i.get("pm25Value", "")).isdigit()
            ]

            print(f"{station} 유효 데이터 개수:", len(valid))

            if not valid:
                print(f"{station} 유효 데이터 없음 → 다음 측정소 확인")
                continue

            candidate = max(
                valid,
                key=lambda x: datetime.datetime.strptime(x["dataTime"], "%Y-%m-%d %H:%M")
            )

            candidate_time = candidate["dataTime"]
            candidate_hour = int(candidate_time.split(" ")[1].split(":")[0])

            print(f"{station} 최신 dataTime:", candidate_time)

            if candidate_hour != now_hour:
                print(f"{station} 현재 시간 데이터 아님 → 다음 측정소 확인")
                continue

            latest = candidate
            used_station = station
            break

        if latest is None:
            print("고현동/아주동 모두 유효 데이터 없음")
            return False

        data_time = latest["dataTime"]
        data_hour = int(data_time.split(" ")[1].split(":")[0])

        print("사용 측정소:", used_station)
        print("API 시간:", data_hour)

        if data_hour != now_hour:
            print("아직 현재 시간 데이터 아님")
            return False

        result = {
            "stationName": used_station,
            "pm10": latest["pm10Value"],
            "pm25": latest["pm25Value"],
            "dataHour": data_hour,
            "dataTime": data_time,
            "labelTime": f"{int(data_time[5:7])}. {int(data_time[8:10])}. {data_hour}시"
        }

        with open(air_json_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False)

        print("air.json 저장 완료")

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
        
        if used_station == "고현동":
            return True
        else:
            print("아주동 임시 저장 완료 → 2분 후 고현동 재확인")
            return False

    except Exception as e:
        print("오류 발생:", e)
        return False


# 🔁 메인 루프
while True:
    updated = fetch_and_update()

    now = datetime.datetime.now()

    if updated:
        # 다음 정각까지 대기
        next_hour = (now + datetime.timedelta(hours=1)).replace(minute=0, second=5, microsecond=0)
        wait_seconds = (next_hour - now).total_seconds()

        print(f"다음 정각까지 대기: {int(wait_seconds)}초")
        time.sleep(wait_seconds)

    else:
        # 2분 후 재시도
        print("2분 후 재시도...")
        time.sleep(120)