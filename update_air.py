print("스크립트 시작")

import requests
import urllib3
import json
import datetime
import subprocess
import sys
import os

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

now = datetime.datetime.now()
now_hour = now.hour
print("현재 시각:", now_hour)

# 7시~17시만 실행
if now_hour < 7 or now_hour > 17:
    print("조회 시간 아님. 종료")
    sys.exit()

base_dir = os.path.dirname(os.path.abspath(__file__))
air_json_path = os.path.join(base_dir, "air.json")

# 이미 현재 시간 데이터가 저장돼 있으면 종료
if os.path.exists(air_json_path):
    try:
        with open(air_json_path, "r", encoding="utf-8") as f:
            old_data = json.load(f)
        saved_hour = old_data.get("dataHour")
        print("기존 저장 hour:", saved_hour)

        if str(saved_hour) == str(now_hour):
            print("이미 현재 시간 데이터가 저장되어 있으므로 종료")
            sys.exit()
    except Exception as e:
        print("기존 air.json 읽기 실패:", e)

print("API 호출 시작")

try:
    res = requests.get(URL, params=PARAMS, verify=False, timeout=15)
    print("응답코드:", res.status_code)
    print("응답 앞부분:", res.text[:300])

    try:
        data = res.json()
    except Exception:
        print("JSON 아님. 응답 내용 확인 필요")
        sys.exit()

    if "response" not in data or "body" not in data["response"]:
        print("응답 구조 이상")
        print(data)
        sys.exit()

    items = data["response"]["body"].get("items", [])
    print("items 개수:", len(items))

    valid = [
        i for i in items
        if str(i.get("pm10Value", "")).isdigit() and str(i.get("pm25Value", "")).isdigit()
    ]

    print("숫자 데이터 개수:", len(valid))

    if not valid:
        print("숫자 데이터 없음. 종료")
        sys.exit()

    latest = sorted(valid, key=lambda x: x["dataTime"])[-1]

    data_time = latest["dataTime"]
    data_hour = int(data_time.split(" ")[1].split(":")[0])

    print("API 시간:", data_hour)
    print("API 최신 dataTime:", data_time)

    # 아직 현재 시간 데이터가 아니면 종료
    if data_hour != now_hour:
        print("아직 현재 시간 데이터 아님")
        sys.exit()

    result = {
        "pm10": latest["pm10Value"],
        "pm25": latest["pm25Value"],
        "dataHour": data_hour,
        "dataTime": data_time,
        "labelTime": f"{int(data_time[5:7])}. {int(data_time[8:10])}. {data_hour}시"
    }

    with open(air_json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False)

    print("air.json 저장 완료")

    subprocess.run(["git", "add", "air.json"], cwd=base_dir, check=False)
    subprocess.run(["git", "commit", "-m", "update air"], cwd=base_dir, check=False)
    subprocess.run(["git", "push"], cwd=base_dir, check=False)

    print("작업 완료")

except Exception as e:
    print("오류 발생:", e)
    sys.exit()