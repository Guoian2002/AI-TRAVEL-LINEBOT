from src.mongodb import mongodb
from src.service.website import Website, WebsiteReader
from src.service.youtube import Youtube, YoutubeTranscriptReader
from src.utils import get_role_and_content
from src.storage import Storage, FileStorage, MongoStorage
from src.logger import logger
from src.memory import Memory
from src.models import OpenAIModel
from dotenv import load_dotenv
from flask import Flask, request, abort
from linebot import (
    LineBotApi, WebhookHandler
)
from linebot.exceptions import (
    InvalidSignatureError
)
from linebot.models import *
import os
import uuid
import psycopg2
from urllib.parse import urlparse, unquote
from gtts import gTTS

import re
import time
import requests
import threading

from flask import Flask, request
import os
import math, json, time, requests

from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage, StickerSendMessage, ImageSendMessage, LocationSendMessage, LocationMessage

app = Flask(__name__)

#地震
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

def getWeather(address):
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
load_dotenv('.env')
line_bot_api = LineBotApi(access_token)
handler = WebhookHandler(channel_secret)
storage = None
youtube = Youtube(step=4)
website = Website()

memory = Memory(system_message=os.getenv(
    'SYSTEM_MESSAGE'), memory_message_count=3)
model_management = {}
api_keys = {}
# chat = True
MAX_CHARS = 150
user_next_indices = {} 


@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        print("Invalid signature. Please check your channel access token/channel secret.")
        abort(400)
    return 'OK'

DATABASE_URL = os.environ['DATABASE_URL']
import psycopg2
from urllib.parse import urlparse, unquote

user_state = {}

def add_to_my_love(user_id, new_love):
    params = urlparse(unquote(DATABASE_URL))

    conn = psycopg2.connect(
        dbname=params.path[1:],
        user=params.username,
        password=params.password,
        host=params.hostname,
        port=params.port
    )

    # 建立連接
    cur = conn.cursor()

    # 檢查 user_id 是否已存在
    cur.execute("SELECT my_love FROM Love_place WHERE user_id = %s", (user_id,))
    result = cur.fetchone()

    if result is None:
        # user_id 不存在，插入新記錄
        cur.execute("INSERT INTO Love_place (user_id, my_love) VALUES (%s, %s)", (user_id, new_love))
    else:
        # user_id 已存在，更新 my_love 欄位
        existing_my_love = result[0]
        updated_my_love = existing_my_love + ',' + new_love if existing_my_love else new_love

        cur.execute("UPDATE Love_place SET my_love = %s WHERE user_id = %s", 
                    (updated_my_love, user_id))

    # 提交事務
    conn.commit()

    # 關閉連接
    cur.close()
    conn.close()


def add_to_want(user_id, new_want):
    params = urlparse(unquote(DATABASE_URL))
    conn = psycopg2.connect(
        dbname=params.path[1:],
        user=params.username,
        password=params.password,
        host=params.hostname,
        port=params.port
    )

    # 建立連接
    cur = conn.cursor()

    # 檢查 user_id 是否已存在
    cur.execute("SELECT want FROM my_want WHERE user_id = %s", (user_id,))
    result = cur.fetchone()

    if result is None:
        # user_id 不存在，插入新記錄
        cur.execute("INSERT INTO my_want (user_id, want) VALUES (%s, %s)", (user_id, new_want))
    else:
        # user_id 已存在，更新 want 欄位
        existing_want = result[0]
        updated_want = existing_want + ',' + new_want if existing_want else new_want

        cur.execute("UPDATE my_want SET want = %s WHERE user_id = %s", 
                    (updated_want, user_id))

    # 提交事務
    conn.commit()

    # 關閉連接
    cur.close()
    conn.close()

def add_to_been_to(user_id, new_been_to):
    params = urlparse(unquote(DATABASE_URL))
    conn = psycopg2.connect(
        dbname=params.path[1:],
        user=params.username,
        password=params.password,
        host=params.hostname,
        port=params.port
    )

    # 建立連接
    cur = conn.cursor()

    # 檢查 user_id 是否已存在
    cur.execute("SELECT been_to FROM been_to WHERE user_id = %s", (user_id,))
    result = cur.fetchone()

    if result is None:
        # user_id 不存在，插入新記錄
        cur.execute("INSERT INTO been_to (user_id, been_to) VALUES (%s, %s)", (user_id, new_been_to))
    else:
        # user_id 已存在，更新 been_to 欄位
        existing_been_to = result[0]
        updated_been_to = existing_been_to + ',' + new_been_to if existing_been_to else new_been_to

        cur.execute("UPDATE been_to SET been_to = %s WHERE user_id = %s", 
                    (updated_been_to, user_id))

    # 提交事務
    conn.commit()

    # 關閉連接
    cur.close()
    conn.close()


def view_records(user_id):
    params = urlparse(unquote(DATABASE_URL))
    conn = psycopg2.connect(
        dbname=params.path[1:],
        user=params.username,
        password=params.password,
        host=params.hostname,
        port=params.port
    )

    cur = conn.cursor()

    # 查詢 love_table 中對應 user_id 的資料
    cur.execute("SELECT my_love FROM love_place WHERE user_id = %s", (user_id,))
    love_record = cur.fetchone()
    my_love = love_record[0] if love_record else "無資料"
    my_love = set(my_love.split(" "))

    # 查詢 want_table 中對應 user_id 的資料
    cur.execute("SELECT want FROM my_want WHERE user_id = %s", (user_id,))
    want_record = cur.fetchone()
    want = want_record[0] if want_record else "無資料"
    want = set(want.split(" "))

    # 查詢 been_to_table 中對應 user_id 的資料
    cur.execute("SELECT been_to FROM been_to WHERE user_id = %s", (user_id,))
    been_to_record = cur.fetchone()
    been_to = been_to_record[0] if been_to_record else "無資料"
    been_to = set(been_to.split(" "))

    result_text = f"我的最愛: {my_love}\n 想去的地方: {want}\n 曾經去過的地方: {been_to}\n"

    conn.commit()
    cur.close()
    conn.close()

    return result_text.strip()

# 天氣
def weather(event):
    try:
        user_id = event.source.user_id  # 取得使用者 ID ( push message 使用 )
        logger.info("user_id: " + user_id)                                      # 印出內容
        type = event.message.type.strip()
        if type == 'text':
            text = event.message.text.strip()
            if text == '雷達回波圖' or text == '雷達回波':
                line_bot_api.push_message(user_id, TextSendMessage(text='馬上找給你！抓取資料中....'))
                img_url = f'https://cwaopendata.s3.ap-northeast-1.amazonaws.com/Observation/O-A0058-001.png?{time.time_ns()}'
                img_message = ImageSendMessage(original_content_url=img_url, preview_image_url=img_url)
                return img_message
            elif text == '地震':
                line_bot_api.push_message(user_id, TextSendMessage(text='馬上找給你！抓取資料中....'))
                reply = earth_quake()
                text_message = TextSendMessage(text=reply[0])
                line_bot_api.push_message(user_id,text_message)
                return ImageSendMessage(original_content_url=reply[1], preview_image_url=reply[1])
            else:
                reply = cctv(text)
                if not reply == '':
                    text_message = TextSendMessage(text=reply)
                    line_bot_api.push_message(user_id,text_message)
                    sec = math.ceil(time.time())
                    reply = reply + f'snapshot?t={sec}'
                    return ImageSendMessage(original_content_url=reply, preview_image_url=reply)
                else:
                    text_message = TextSendMessage(text=text)
                    return text_message
        elif type == 'location':
            line_bot_api.push_message(user_id, TextSendMessage(text='馬上找給你！抓取資料中....'))
            address = event.message.address.replace('台','臺')  # 取出地址資訊，並將「台」換成「臺」
            reply = getWeather(address)
            text_message = TextSendMessage(text=reply)
            return text_message
    except Exception as e:
        print(e)
    return 'OK'                 # 驗證 Webhook 使用，不能省略

def generate_summary(conversation):
    
    return "請幫我將以下對話做100字左右的總結"+" ".join(conversation[:10])

#文字輸出
@handler.add(MessageEvent, message=TextMessage)

def handle_text_message(event):
    user_messages = {}
    assistant_messages = {}
    msg = ""
    print("print")
    user_id = event.source.user_id
    chat = memory.chats[user_id]
    if(chat == ""):
        print("沒有chat")
        memory.setChat(user_id, True)
    text = event.message.text.strip()
    type = event.message.type.strip()
    logger.info(f'{user_id}: {text}')
    api_key = os.getenv("TAIDE_API_KEY")
    model = OpenAIModel(api_key=api_key)
    is_successful, _, _ = model.check_token_valid()
    if not is_successful:
        raise ValueError('Invalid API token')
    model_management[user_id] = model
    storage.save({
        user_id: api_key
    })
    if user_id not in user_messages:
        user_messages[user_id] = []

    if user_id not in assistant_messages:
        assistant_messages[user_id] = []

    user_messages[user_id].append(text)

    if user_id not in user_next_indices:
        user_next_indices[user_id] = 0

    

    try:
        if text == '忘記':
            memory.remove(user_id)
            user_messages[user_id]=[]
            assistant_messages[user_id]=[]
            msg = TextSendMessage(text='歷史訊息清除成功')
  
        elif text == '總結':
            memory.chats[user_id] = True
            conversation = user_messages[user_id] + assistant_messages[user_id]
            if len(conversation) == 0:
                msg = TextSendMessage(text='目前您沒有跟小T，請先聊聊再來~')
            else:
                text=generate_summary(conversation)

        elif text == "語音輸入":
            msg = TextSendMessage(
                text="請選擇輸出方式",
                quick_reply=QuickReply(
                    items=[
                        QuickReplyButton(
                            action=MessageAction(label="文字", text="文字")
                        ),
                        QuickReplyButton(
                            action=MessageAction(label="語音", text="語音")
                        ),
                    ]
                )
            )

        elif text == "雷達回波":
            msg = weather(event)

        elif text == "地震":
            msg = weather(event)

        elif text == "我需要推薦網站":
            pass

        elif text == "天氣資訊":
            msg = TextSendMessage(text="請選擇想知道的資訊",
                quick_reply=QuickReply(
                    items=[

                         QuickReplyButton(
                            action=MessageAction(label="詳細天氣", text="詳細天氣")
                        ),

                        QuickReplyButton(
                            action=MessageAction(label="雷達回波", text="雷達回波")
                        ),
                        QuickReplyButton(
                            action=MessageAction(label="地震", text="地震")
                        ),
                    ]
                )              
            )
        
        elif text == "聊天功能":
            msg = TextSendMessage(
                text="請選擇想要的模式",
                quick_reply=QuickReply(
                    items=[
                        QuickReplyButton(
                            action=MessageAction(label="開啟聊天", text="開啟聊天")
                        ),
                        QuickReplyButton(
                            action=MessageAction(label="關閉聊天", text="關閉聊天")
                        ),
                        QuickReplyButton(
                            action=MessageAction(label="忘記", text="忘記")
                        ),
                        QuickReplyButton(
                            action=MessageAction(label="總結", text="總結")
                        ),
                    ]
                )
            )

        elif text == "我的最愛":
            user_state[user_id] = "my_love"
            msg = TextSendMessage(
                text="選擇分類",
                quick_reply=QuickReply(
                    items=[
                        QuickReplyButton(
                            action=MessageAction(label="最愛的地方", text="最愛的地方")
                        ),
                        QuickReplyButton(
                            action=MessageAction(label="想去的地方", text="想去的地方")
                        ),
                        QuickReplyButton(
                            action=MessageAction(label="已去過的地方", text="已去過的地方")
                        ),
                        QuickReplyButton(
                            action=MessageAction(label="查看紀錄", text="查看紀錄")
                        ),
                     
                    ]
                )
            )

        #最愛的地方
        elif text == '最愛的地方':
            user_state[user_id] = 'input_my_love'
            msg = TextSendMessage(text="現在可以隨意輸入")
            # 回傳訊息
            line_bot_api.reply_message(event.reply_token, msg)
        elif user_state.get(user_id) == 'input_my_love':
            add_to_my_love(user_id, text)
            user_state[user_id] = None
            msg = TextSendMessage(text="已經將你的最愛的地方加入了！")
            # 回傳訊息
            line_bot_api.reply_message(event.reply_token, msg)

        #想去的地方
        elif text == '想去的地方':
            user_state[user_id] = 'input_want'
            msg = TextSendMessage(text="現在可以隨意輸入")
            # 回傳訊息
            line_bot_api.reply_message(event.reply_token, msg)
        elif user_state.get(user_id) == 'input_want':
            add_to_want(user_id, text)
            user_state[user_id] = None
            msg = TextSendMessage(text="已經將你想去的地方加入了！")
            # 回傳訊息
            line_bot_api.reply_message(event.reply_token, msg)


        #已去過的地方
        elif text == '已去過的地方':
            user_state[user_id] = 'input_been_to'
            msg = TextSendMessage(text="現在可以隨意輸入")
            # 回傳訊息
            line_bot_api.reply_message(event.reply_token, msg)
        elif user_state.get(user_id) == 'input_been_to':
            add_to_been_to(user_id, text)
            user_state[user_id] = None
            msg = TextSendMessage(text="已經將你已去過的地方加入了！")
            # 回傳訊息
            line_bot_api.reply_message(event.reply_token, msg)

        elif text == '查看紀錄':
            records = view_records(user_id)
            msg = TextSendMessage(text=records)
            line_bot_api.reply_message(event.reply_token, msg)

        elif text == "詳細天氣":
            msg = TextSendMessage(
                text="請傳送您的位置",
                quick_reply=QuickReply(
                    items=[
                        QuickReplyButton(
                            action=LocationAction(label="傳送位置")
                        )
                    ]
                )
            )
            line_bot_api.reply_message(event.reply_token, msg)

        else:
            if text == '開啟聊天':
                memory.chats[user_id] = True
                msg = TextSendMessage(text="已開啟聊天")

            elif text == '關閉聊天':
                memory.chats[user_id] = False
                msg = TextSendMessage(text="已關閉聊天")

            else:
                user_model = model_management[user_id]
                memory.append(user_id, 'user', text)
                url = website.get_url_from_text(text)
                if url:
                    if youtube.retrieve_video_id(text):
                        is_successful, chunks, error_message = youtube.get_transcript_chunks(
                            youtube.retrieve_video_id(text))
                        if not is_successful:
                            raise Exception(error_message)
                        youtube_transcript_reader = YoutubeTranscriptReader(
                            user_model, os.getenv('MODEL'))
                        is_successful, response, error_message = youtube_transcript_reader.summarize(
                            chunks)
                        if not is_successful:
                            raise Exception(error_message)
                        role, response = get_role_and_content(response)
                        msg = TextSendMessage(text=response)
                    else:
                        chunks = website.get_content_from_url(url)
                        if len(chunks) == 0:
                            raise Exception('無法撈取此網站文字')
                        website_reader = WebsiteReader(
                            user_model, os.getenv('MODEL'))
                        is_successful, response, error_message = website_reader.summarize(
                            chunks)
                        if not is_successful:
                            raise Exception(error_message)
                        role, response = get_role_and_content(response)
                        msg = TextSendMessage(text=response)
                else:
                    is_successful, response, error_message = user_model.chat_completions(
                        memory.get(user_id), os.getenv('MODEL'))
                    logger.info(response)
                    if not is_successful:
                        raise Exception(error_message)
                    role, response = get_role_and_content(response)
                    # if len(response) > MAX_CHARS:
                    #     messages = generate_reply_messages(response, user_id)
                    #     line_bot_api.reply_message(event.reply_token, messages)
                    #     return 'OK'
                memory.append(user_id, role, response)
                msg = TextSendMessage(text=response)



    except ValueError:
        msg = TextSendMessage(text='TAIDE ValueError')
    except KeyError as e:
        logger.info(e)
        msg = TextSendMessage(text='TAIDE 休息中~')
    except Exception as e:
        memory.remove(user_id)
        if str(e).startswith('Incorrect API key provided'):
            msg = TextSendMessage(text='OpenAI API Token 有誤，請重新註冊。')
        elif str(e).startswith('That model is currently overloaded with other requests.'):
            msg = TextSendMessage(text='已超過負荷，請稍後再試')
        else:
            msg = TextSendMessage(text=str(e))
    if msg != "":
        line_bot_api.reply_message(event.reply_token, msg)


#位置訊息輸入
@handler.add(MessageEvent, message=LocationMessage)
def handle_location_message(event):
    msg = weather(event)
    line_bot_api.reply_message(event.reply_token, msg)

#語音輸入
@handler.add(MessageEvent, message=AudioMessage)
def handle_audio_message(event):
    user_id = event.source.user_id
    audio_content = line_bot_api.get_message_content(event.message.id)
    input_audio_path = f'{str(uuid.uuid4())}.m4a'
    with open(input_audio_path, 'wb') as fd:
        for chunk in audio_content.iter_content():
            fd.write(chunk)

    try:
        if not model_management.get(user_id):
            raise ValueError('Invalid API token')
        else:
            is_successful, response, error_message = model_management[user_id].audio_transcriptions(input_audio_path, 'whisper-1')
            if not is_successful:
                raise Exception(error_message)
            memory.append(user_id, 'user', response['text'])
            is_successful, response, error_message = model_management[user_id].chat_completions(memory.get(user_id), 'gpt-3.5-turbo')
            if not is_successful:
                raise Exception(error_message)
            role, response = get_role_and_content(response)
            memory.append(user_id, role, response)
            msg = TextSendMessage(text=response)
    except ValueError:
        msg = TextSendMessage(text='請先註冊你的 API Token，格式為 /註冊 [API TOKEN]')
    except KeyError:
        msg = TextSendMessage(text='TAIDE 不支援語音歐~')
    except Exception as e:
        memory.remove(user_id)
        if str(e).startswith('Incorrect API key provided'):
            msg = TextSendMessage(text='OpenAI API Token 有誤，請重新註冊。')
        else:
            msg = TextSendMessage(text=str(e))
    os.remove(input_audio_path)
    line_bot_api.reply_message(event.reply_token, msg)


@app.route("/", methods=['GET'])
def home():
    return 'Hello World'


if __name__ == "__main__":
    if os.getenv('USE_MONGO'):
        mongodb.connect_to_database()
        storage = Storage(MongoStorage(mongodb.db))
    else:
        storage = Storage(FileStorage('db.json'))
    try:
        data = storage.load()
        for user_id in data.keys():
            model_management[user_id] = OpenAIModel(api_key=data[user_id])
    except FileNotFoundError:
        pass
    app.run(host='0.0.0.0', port=8080)
