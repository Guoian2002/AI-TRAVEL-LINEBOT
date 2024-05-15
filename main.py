from flask import Flask, request
import os
import math, json, time, requests


# 載入 LINE Message API 相關函式庫
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage, StickerSendMessage, ImageSendMessage, LocationSendMessage

app = Flask(__name__)

def earth_quake():
    result = []
    code = os.getenv('WEATHER_TOKEN')
    try:
        # 小區域 https://opendata.cwa.gov.tw/dataset/earthquake/E-A0016-001
        url = f'https://opendata.cwa.gov.tw/api/v1/rest/datastore/E-A0016-001?Authorization={code}'
        req1 = requests.get(url)  # 爬取資料
        data1 = req1.json()       # 轉換成 json
        eq1 = data1['records']['Earthquake'][0]           # 取得第一筆地震資訊
        t1 = data1['records']['Earthquake'][0]['EarthquakeInfo']['OriginTime']
        # 顯著有感 https://opendata.cwa.gov.tw/dataset/all/E-A0015-001
        url2 = f'https://opendata.cwa.gov.tw/api/v1/rest/datastore/E-A0015-001?Authorization={code}'
        req2 = requests.get(url2)  # 爬取資料
        data2 = req2.json()        # 轉換成 json
        eq2 = data2['records']['Earthquake'][0]           # 取得第一筆地震資訊
        t2 = data2['records']['Earthquake'][0]['EarthquakeInfo']['OriginTime']
        
        result = [eq1['ReportContent'], eq1['ReportImageURI']] # 先使用小區域地震
        if t2>t1:
          result = [eq2['ReportContent'], eq2['ReportImageURI']] # 如果顯著有感地震時間較近，就用顯著有感地震
    except Exception as e:
        print(e)
        result = ['抓取失敗...','']
    return result

def weather(address):
    result = {}
    code = os.getenv('WEATHER_TOKEN')
    # 即時天氣
    try:
        url = [f'https://opendata.cwa.gov.tw/api/v1/rest/datastore/O-A0001-001?Authorization={code}',
            f'https://opendata.cwa.gov.tw/api/v1/rest/datastore/O-A0003-001?Authorization={code}']
        for item in url:
            req = requests.get(item)   # 爬取目前天氣網址的資料
            data = req.json()
            station = data['records']['Station']
            for i in station:
                city = i['GeoInfo']['CountyName']
                area = i['GeoInfo']['TownName']
                if not f'{city}{area}' in result:
                    weather = i['WeatherElement']['Weather']
                    temp = i['WeatherElement']['AirTemperature']
                    humid = i['WeatherElement']['RelativeHumidity']
                    result[f'{city}{area}'] = f'目前天氣狀況「{weather}」，溫度 {temp} 度，相對濕度 {humid}%！'
    except:
        pass


    # 氣象預報
    api_list = {"宜蘭縣":"F-D0047-001","桃園市":"F-D0047-005","新竹縣":"F-D0047-009","苗栗縣":"F-D0047-013",
        "彰化縣":"F-D0047-017","南投縣":"F-D0047-021","雲林縣":"F-D0047-025","嘉義縣":"F-D0047-029",
        "屏東縣":"F-D0047-033","臺東縣":"F-D0047-037","花蓮縣":"F-D0047-041","澎湖縣":"F-D0047-045",
        "基隆市":"F-D0047-049","新竹市":"F-D0047-053","嘉義市":"F-D0047-057","臺北市":"F-D0047-061",
        "高雄市":"F-D0047-065","新北市":"F-D0047-069","臺中市":"F-D0047-073","臺南市":"F-D0047-077",
        "連江縣":"F-D0047-081","金門縣":"F-D0047-085"}
    for name in api_list:
        if name in address:
            city_id = api_list[name]
    t = time.time()
    t1 = time.localtime(t+28800)
    t2 = time.localtime(t+28800+10800)
    now = time.strftime('%Y-%m-%dT%H:%M:%S',t1)
    now2 = time.strftime('%Y-%m-%dT%H:%M:%S',t2)
    url = f'https://opendata.cwa.gov.tw/api/v1/rest/datastore/{city_id}?Authorization={code}&elementName=WeatherDescription&timeFrom={now}&timeTo={now2}'
    req = requests.get(url)   # 取得主要縣市預報資料
    data = req.json()         # json 格式化訊息內容
    location = data['records']['locations'][0]['location']
    city = data['records']['locations'][0]['locationsName']
    for item in location:
        try:
            area = item['locationName']
            note = item['weatherElement'][0]['time'][0]['elementValue'][0]['value']
            if not f'{city}{area}' in result:
                result[f'{city}{area}'] = ''
            else:
                result[f'{city}{area}'] = result[f'{city}{area}'] + '。\n\n'
            result[f'{city}{area}'] = result[f'{city}{area}'] + '未來三小時' + note
        except:
            pass

    # 空氣品質
    try:
        url = 'https://data.moenv.gov.tw/api/v2/aqx_p_432?api_key=e8dd42e6-9b8b-43f8-991e-b3dee723a52d&limit=1000&sort=ImportDate%20desc&format=JSON'
        req = requests.get(url)
        data = req.json()
        records = data['records']
        for item in records:
            county = item['county']      # 縣市
            sitename = item['sitename']  # 區域
            name = f'{county}{sitename}'
            aqi = int(item['aqi'])       # AQI 數值
            aqi_status = ['良好','普通','對敏感族群不健康','對所有族群不健康','非常不健康','危害']
            msg = aqi_status[aqi//50]    # 除以五十之後無條件捨去，取得整數

            for k in result:
                if name in k:
                    result[k] = result[k] + f'\n\nAQI：{aqi}，空氣品質{msg}。'
    except:
        pass

    output = '找不到氣象資訊'
    for i in result:
        if i in address: # 如果地址裡存在 key 的名稱
            output = f'「{address}」{result[i]}'
            break
    return output

def cctv(msg):
    try:
        output = ''
        camera_list = {
            '夢時代':'https://cctv1.kctmc.nat.gov.tw/27e5c086/',
            '鼓山渡輪站':'https://cctv3.kctmc.nat.gov.tw/ddb9fc98/',
            '中正交流道':'https://cctv3.kctmc.nat.gov.tw/166157d9/',
            '五福愛河':'https://cctv4.kctmc.nat.gov.tw/335e2702/'
        }
        for item in camera_list:
            if msg == item:
                output = camera_list[msg]
    except Exception as e:
        print(e)
    return output


access_token = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
channel_secret = os.getenv('LINE_CHANNEL_SECRET')

@app.route("/callback", methods=['POST'])
def linebot():
    body = request.get_data(as_text=True)                    # 取得收到的訊息內容
    try:
        line_bot_api = LineBotApi(access_token)     # 確認 token 是否正確
        handler = WebhookHandler(channel_secret)    # 確認 secret 是否正確
        signature = request.headers['X-Line-Signature']             # 加入回傳的 headers
        handler.handle(body, signature)      # 綁定訊息回傳的相關資訊
        json_data = json.loads(body)         # 轉換內容為 json 格式
        reply_token = json_data['events'][0]['replyToken']    # 取得回傳訊息的 Token ( reply message 使用 )
        user_id = json_data['events'][0]['source']['userId']  # 取得使用者 ID ( push message 使用 )
        print(json_data)                                      # 印出內容
        type = json_data['events'][0]['message']['type']
        if type == 'text':
            text = json_data['events'][0]['message']['text']
            if text == '雷達回波圖' or text == '雷達回波':
                line_bot_api.push_message(user_id, TextSendMessage(text='馬上找給你！抓取資料中....'))
                img_url = f'https://cwaopendata.s3.ap-northeast-1.amazonaws.com/Observation/O-A0058-001.png?{time.time_ns()}'
                img_message = ImageSendMessage(original_content_url=img_url, preview_image_url=img_url)
                line_bot_api.reply_message(reply_token,img_message)
            elif text == '地震':
                line_bot_api.push_message(user_id, TextSendMessage(text='馬上找給你！抓取資料中....'))
                reply = earth_quake()
                text_message = TextSendMessage(text=reply[0])
                line_bot_api.reply_message(reply_token,text_message)
                line_bot_api.push_message(user_id, ImageSendMessage(original_content_url=reply[1], preview_image_url=reply[1]))
            else:
                reply = cctv(text)
                if not reply == '':
                    text_message = TextSendMessage(text=reply)
                    line_bot_api.reply_message(reply_token,text_message)
                    sec = math.ceil(time.time())
                    reply = reply + f'snapshot?t={sec}'
                    line_bot_api.push_message(user_id, ImageSendMessage(original_content_url=reply, preview_image_url=reply))
                else:
                    text_message = TextSendMessage(text=text)
                    line_bot_api.reply_message(reply_token,text_message)
        elif type == 'location':
            line_bot_api.push_message(user_id, TextSendMessage(text='馬上找給你！抓取資料中....'))
            address = json_data['events'][0]['message']['address'].replace('台','臺')  # 取出地址資訊，並將「台」換成「臺」
            reply = weather(address)
            text_message = TextSendMessage(text=reply)
            line_bot_api.reply_message(reply_token,text_message)
    except Exception as e:
        print(e)
    return 'OK'                 # 驗證 Webhook 使用，不能省略

if __name__ == "__main__":
    app.run("0.0.0.0", port=8080)
