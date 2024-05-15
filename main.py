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


# 載入 LINE Message API 相關函式庫
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage, StickerSendMessage, ImageSendMessage, LocationSendMessage

# from google.cloud import storage
# from google.oauth2 import service_account
# import json
# credentials_dict = json.loads(os.environ['GOOGLE_APPLICATION_CREDENTIALS'])
# credentials = service_account.Credentials.from_service_account_info(credentials_dict)
# storage_client = storage.Client(credentials=credentials)

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
load_dotenv('.env')
line_bot_api = LineBotApi(os.getenv('LINE_CHANNEL_ACCESS_TOKEN'))
handler = WebhookHandler(os.getenv('LINE_CHANNEL_SECRET'))
storage = None
youtube = Youtube(step=4)
website = Website()

memory = Memory(system_message=os.getenv(
    'SYSTEM_MESSAGE'), memory_message_count=3)
model_management = {}
api_keys = {}
# chat = True
place_array = ["士林區", "大同區", "信義區", "北投區", "文山區", "大安區", "中正區", "內湖區", "松山區", "中山區"]
user_states = {}
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
def get_data_from_db( dis ):
    try:
        # 使用 urlparse 解析連接 URI
        params = urlparse(unquote(DATABASE_URL))

        # 建立連接
        conn = psycopg2.connect(
            dbname=params.path[1:],
            user=params.username,
            password=params.password,
            host=params.hostname,
            port=params.port
        )

        # 執行 SQL 查詢並獲取資料
        cur = conn.cursor()
        cur.execute("   SELECT name,address,phone FROM heart WHERE district = '"+ dis +"';")
        rows = cur.fetchall()

        # 檢查查詢結果是否為空
        if rows:
            message = str(rows) 
            result = message.replace("[", "").replace("]", "").replace("(", "🧡").replace(")", " \n").replace(",", " \n").replace("'", "")
            
            if len(message) <= 2000:  # 檢查消息長度
                return result
            else:
                return 'The message is too long!'
        else:
            return 'The query result is empty!'

        cur.close()
        conn.close()
    except Exception as e:
        return 'An error occurred except'

    return rows


user_states = {}
user_relations = {}
#將使用將使用者資料寫入到friend資料庫
def insert_into_db(user_id, relation, phone_number):
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
    cur.execute("SELECT COUNT(*) FROM friend WHERE user_id = %s", (user_id,))
    count = cur.fetchone()[0]

    if count == 0:
        # user_id 不存在，插入新記錄
        cur.execute("INSERT INTO friend (user_id, relation, phone_number) VALUES (%s, %s, %s)", (user_id, relation, phone_number))
    else:
        # user_id 已存在，刪除該使用者的所有欄位資料再插入新記錄
        cur.execute("DELETE FROM friend WHERE user_id = %s", (user_id,))
        cur.execute("INSERT INTO friend (user_id, relation, phone_number) VALUES (%s, %s, %s)", (user_id, relation, phone_number))

    # 提交事務
    conn.commit()

    # 關閉連接
    cur.close()
    conn.close()

def get_trusted_person(user_id):
    params = urlparse(unquote(DATABASE_URL))
    conn = psycopg2.connect(
        dbname=params.path[1:],
        user=params.username,
        password=params.password,
        host=params.hostname,
        port=params.port
    )
    cur = conn.cursor()
    cur.execute("SELECT relation, phone_number FROM friend WHERE user_id = %s", (user_id,))
    result = cur.fetchone()

    cur.close()
    conn.close()

    return result

def split_bullet_points(text):
    # 透過正規表示式將列點的部分分開
    title = re.match(r'[\u4e00-\u9fff]+[。]', text)
    try:
        title = title.group(0)
    except:
        title = "前面取不到"
    points = re.findall(r'\S*\d+\. \S*', text)
    # 去除第一個元素，因為在第一個列點之前的部分會是空字串
    return title, points[1:]

# 控制輸出的字數
def generate_reply_messages(response, user_id):
    messages = []

    # 檢查文字是否為列點式的格式
    title, parts = split_bullet_points(response)
    if(len(parts) != 0):
        messages.append(TextSendMessage(text=title, quick_reply=QuickReply(
                items=[QuickReplyButton(action=MessageAction(label="繼續", text="繼續"))])))
        for part in parts:
            messages.append(TextSendMessage(text=part, quick_reply=QuickReply(
                items=[QuickReplyButton(action=MessageAction(label="繼續", text="繼續"))])))
    else:
        messages.append(TextSendMessage(text=response, quick_reply=QuickReply(
                items=[QuickReplyButton(action=MessageAction(label="繼續", text="繼續"))])))
    # else:
    #     response_len = len(response)
    #     remaining_response = response

    #     while response_len > MAX_CHARS:
    #         split_index = remaining_response.rfind(' ', 0, MAX_CHARS)
    #         current_message = remaining_response[:split_index]
    #         remaining_response = remaining_response[split_index + 1:]
    #         response_len = len(remaining_response)
    #         messages.append(TextSendMessage(text=current_message, quick_reply=QuickReply(
    #             items=[QuickReplyButton(action=MessageAction(label="繼續", text="繼續"))])))

    #     messages.append(TextSendMessage(text=remaining_response))

    user_next_indices[user_id] = len(user_messages[user_id])
    return messages

# 天氣
def linebot():
    body = request.get_data(as_text=True)                    # 取得收到的訊息內容
    try:
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

""" #登入歡迎
@handler.add(FollowEvent)
def handle_follow(event):
    line_bot_api.reply_message(
        event.reply_token,
        [
            TextSendMessage(text="您好！🎊\n我是你的心情小助手 Emo ~\n在這裡，您可以放心的跟我聊天\n我可以提供您免費的AI心理諮商服務🥰\n點開底下選單\n我可以提供心理院所的資料給您參考\n有需要時，我可以給您專業人員的電話撥打☎️\n我也將不定時的給您更多有趣的心理測驗玩玩🖋\n接下來您可以自由的跟我聊聊囉😀"),
            TextSendMessage(text="您是否願意留下最信任的親朋好友聯絡方式給emo，讓emo在您需要幫助的時候可以盡快的給予您幫助～",
                            quick_reply=QuickReply(
                                items=[
                                    QuickReplyButton(
                                        action=MessageAction(label="是我願意相信emo", text="是我願意相信emo")
                                    ),
                                    QuickReplyButton(
                                        action=MessageAction(label="我再想想", text="我再想想")
                                    )
                                ]
                            ))
        ]
    )

def generate_summary(conversation):
    
    return "請幫我將以下對話做100字左右的總結"+" ".join(conversation[:10])
 """
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
    logger.info(f'{user_id}: {text}')
    api_key = os.getenv("CHATGPT_API_KEY")
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
        if text == '是我願意相信emo':
            user_states[user_id] = 'awaiting_relation'
            msg = TextSendMessage(text="請輸入您信任的親朋好友關係")
        elif user_id in user_states and user_states[user_id] == 'awaiting_relation':
            user_relations[user_id] = text  # store the relation
            user_states[user_id] = 'awaiting_phone'  # change state to awaiting_phone
            msg = TextSendMessage(text="請輸入親朋好友的電話號碼")
        elif user_id in user_states and user_states[user_id] == 'awaiting_phone':
            insert_into_db(user_id, user_relations[user_id], text)  # insert both relation and phone into DB
            user_states[user_id] = None  # reset state
            user_relations[user_id] = None  # clear stored relation
            msg = TextSendMessage(text="您的親朋好友關係及電話已經成功記錄。現在可以跟emo聊天了。")


        elif text == '我需要求助':
            trusted_person = get_trusted_person(user_id)
            if trusted_person is not None:
                relation, phone_number = trusted_person
                msg = TextSendMessage(text=f"或是你可以尋找你信任的 {relation}，電話號碼是 {phone_number}，他會給與妳很大的協助。")
                line_bot_api.reply_message(event.reply_token, msg)

        elif text == '相信emo':
            msg=TextSendMessage(text="您是否願意留下最信任的親朋好友聯絡方式給emo，讓emo在您需要幫助的時候可以盡快的給予您幫助～",
                            quick_reply=QuickReply(
                                items=[
                                    QuickReplyButton(
                                        action=MessageAction(label="是我願意相信emo", text="是我願意相信emo")
                                    ),
                                    QuickReplyButton(
                                        action=MessageAction(label="我再想想", text="我再想想")
                                    )
                                ]
                            ))


        elif text=="我再想想":
            msg = TextSendMessage(text="現在可以跟emo聊天了~")

        elif text == 'emo你在嗎':
            msg = TextSendMessage(
                text="我在，有甚麼可以幫您的嗎，以下是您可以使用的指令\n\n指令：\n\n忘記\n👉 Emo會忘記上下文關係，接下來的回答不再跟上文有關係~\n\n請畫\n👉 請畫+你想畫的東西 Emo會在短時間畫給你~\n\n語音輸入\n👉 使用line語音輸入Emo可以直接回覆喔~\n\n其他文字輸入\n👉 Emo直接以文字回覆~  \n\n相信emo\n👉 Emo會更新你提供的資訊~",
                quick_reply=QuickReply(
                    items=[
                        QuickReplyButton(
                            action=MessageAction(label="忘記", text="忘記")
                        ),
                        QuickReplyButton(
                            action=MessageAction(label="請畫", text="請畫")
                        ),
                        QuickReplyButton(
                            action=MessageAction(label="總結", text="總結")
                        ),
                        QuickReplyButton(
                            action=MessageAction(label="語音輸入", text="語音輸入")
                        ),
                        QuickReplyButton(
                            action=MessageAction(label="相信emo", text="相信emo")
                        ),
                    ]
                )
            )


        elif text == '忘記':
            memory.remove(user_id)
            user_messages[user_id]=[]
            assistant_messages[user_id]=[]
            msg = TextSendMessage(text='歷史訊息清除成功')
  
        elif text == '總結':
            memory.chats[user_id] = True
            conversation = user_messages[user_id] + assistant_messages[user_id]
            if len(conversation) == 0:
                msg = TextSendMessage(text='目前您沒有跟emo聊天，請先聊聊再來~')
            else:
                text=generate_summary(conversation)

        elif text == '請畫':
            user_states[user_id] = 'drawing'
            msg = TextSendMessage(text='請輸入你想畫的東西')

        elif user_states.get(user_id) == 'drawing':
            prompt = text.strip()
            memory.append(user_id, 'user', prompt)
            is_successful, response, error_message = model_management[user_id].image_generations(
                prompt)
            if not is_successful:
                raise Exception(error_message)
            url = response['data'][0]['url']
            msg = ImageSendMessage(
                original_content_url=url,
                preview_image_url=url
            )
            memory.append(user_id, 'assistant', url)

            user_states[user_id] = None

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
        elif text == "文字":
            msg = TextSendMessage(text="可以用語音跟emo聊天嘍~")

        elif text == "語音":
            msg = TextSendMessage(text="近期即將推出，敬請期待")
        
        elif text in place_array:
            tmp=get_data_from_db( text )
            msg = TextSendMessage(text=tmp)
        
        elif text == "我想要做心理測驗":
            msg = TextSendMessage(text="請選擇想做的類型",
                quick_reply=QuickReply(
                    items=[
                        QuickReplyButton(
                            action=MessageAction(label="~壓力~", text="~壓力~")
                        ),
                        QuickReplyButton(
                            action=MessageAction(label="~趣味~", text="~趣味~")
                        ),
                    ]
                )              
            )

        # 不用傳進gpt的文字
        elif text == "~壓力~":
            pass

        elif text == "~趣味~":
            pass

        elif text == "雷達回波":
            msg=TextSendMessage(text="雷達回波")
            pass

        elif text == "地震":
            pass

        

        else:
            if text == '開啟聊天':
                memory.chats[user_id] = True
                msg = TextSendMessage(text="已開啟聊天")

            elif text == '關閉聊天':
                memory.chats[user_id] = False
                msg = TextSendMessage(text="已關閉聊天")

            elif text == '我想要查詢心理醫療機構':
                msg = TextSendMessage(
                    text="請點選想查詢的地區",
                    quick_reply=QuickReply(
                        items=[
                            QuickReplyButton(
                                action=MessageAction(label="士林區", text="士林區")
                            ),
                            QuickReplyButton(
                                action=MessageAction(label="大同區", text="大同區")
                            ),
                            QuickReplyButton(
                                action=MessageAction(label="信義區", text="信義區")
                            ),
                            QuickReplyButton(
                                action=MessageAction(label="北投區", text="北投區")
                            ),
                            QuickReplyButton(
                                action=MessageAction(label="文山區", text="文山區")
                            ),
                            QuickReplyButton(
                                action=MessageAction(label="大安區", text="大安區")
                            ),
                            QuickReplyButton(
                                action=MessageAction(label="中正區", text="中正區")
                            ),
                            QuickReplyButton(
                                action=MessageAction(label="內湖區", text="內湖區")
                            ),
                            QuickReplyButton(
                                action=MessageAction(label="松山區", text="松山區")
                            ),
                            QuickReplyButton(
                                action=MessageAction(label="中山區", text="中山區")
                            )

                        ]
                    )
                )

        if memory.chats[user_id] and msg == "":
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
                        user_model, os.getenv('OPENAI_MODEL_ENGINE'))
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
                        user_model, os.getenv('OPENAI_MODEL_ENGINE'))
                    is_successful, response, error_message = website_reader.summarize(
                        chunks)
                    if not is_successful:
                        raise Exception(error_message)
                    role, response = get_role_and_content(response)
                    msg = TextSendMessage(text=response)
            else:
                is_successful, response, error_message = user_model.chat_completions(
                    memory.get(user_id), os.getenv('OPENAI_MODEL_ENGINE'))
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
        msg = TextSendMessage(text='Token 無效，請重新註冊，格式為 /註冊 sk-xxxxx')
    except KeyError:
        msg = TextSendMessage(text='錯誤')
    except Exception as e:
        memory.remove(user_id)
        if str(e).startswith('Incorrect API key provided'):
            msg = TextSendMessage(text='OpenAI API Token 有誤，請重新註冊。')
        elif str(e).startswith('That model is currently overloaded with other requests.'):
            msg = TextSendMessage(text='已超過負荷，請稍後再試')
        else:
            msg = TextSendMessage(text=str(e))
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
        msg = TextSendMessage(text='請先註冊 Token，格式為 /註冊 sk-xxxxx')
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
