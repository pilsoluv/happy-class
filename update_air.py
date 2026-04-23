import requests
import json
import datetime
import subprocess

URL = "https://apis.data.go.kr/B552584/ArpltnInforInqireSvc/getMsrstnAcctoRltmMesureDnsty"
PARAMS = {
    "serviceKey": "너_API키",
    "returnType": "json",
    "numOfRows": "24",
    "pageNo": "1",
    "stationName": "고현동",
    "dataTerm": "DAILY",
    "ver": "1.3"
}

now_hour = datetime.datetime.now().hour

res = requests.get(URL, params=PARAMS)
data = res.json()

items = data["response"]["body"]["items"]

# 최신 숫자 데이터 찾기
valid = [i for i in items if i["pm10Value"].isdigit() and i["pm25Value"].isdigit()]
latest = sorted(valid, key=lambda x: x["dataTime"])[-1]

data_time = latest["dataTime"]
data_hour = int(data_time.split(" ")[1].split(":")[0])

# 현재 시간 데이터 아니면 종료
if data_hour != now_hour:
    print("아직 현재 시간 데이터 아님")
    exit()

result = {
    "pm10": latest["pm10Value"],
    "pm25": latest["pm25Value"],
    "dataHour": data_hour,
    "labelTime": f"{int(data_time[5:7])}. {int(data_time[8:10])}. {data_hour}시"
}

with open("air.json", "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False)

# Git push
subprocess.run(["git", "add", "air.json"])
subprocess.run(["git", "commit", "-m", "update air"])
subprocess.run(["git", "push"])