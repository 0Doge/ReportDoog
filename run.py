from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import *
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore

import sys
import os

app = Flask(__name__)


# 初始化firebase
cred = credentials.Certificate('serviceAccount.json')
firebase_admin.initialize_app(cred)
db = firestore.client()


config = configparser.ConfigParser()
config.read('config.ini')
# Channel Access Token
line_bot_api = LineBotApi(config.get('line-bot', 'channel_access_token'))
# Channel Secret
handler = WebhookHandler(config.get('line-bot', 'channel_secret'))


def get_report_data(groupId):
    doc_ref = db.collection("ReportGroup").document(str(groupId))
    doc = doc_ref.get()
    if doc.exists:
        return doc.to_dict()
    else:
        return {}

def update_report_data(groupId, data):
    doc_ref = db.collection("ReportGroup").document(str(groupId))
    doc_ref.set(data)

# 監聽所有來自 /callback 的 Post Request
@app.route("/callback", methods=['POST'])
def callback():
    # get X-Line-Signature header value
    signature = request.headers['X-Line-Signature']
    # get request body as text
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)
    # handle webhook body
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

# 處理訊息
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    # 各群組的資訊互相獨立
    try:
        groupID = event.source.group_id
    except: # 此機器人設計給群組回報，單兵不可直接一對一回報給機器人
        message = TextSendMessage(text='我只接收群組內訊息，請先把我邀請到群組!')
        line_bot_api.reply_message(event.reply_token, message)
    else:
        reportData[groupID] = get_report_data(groupID)
        # if not reportData.get(groupID): # 如果此群組為新加入，會創立一個新的儲存區
        #     reportData[groupID]={}
        LineMessage = ''
        receivedmsg = event.message.text
        if  '學號' in receivedmsg and '姓名' in receivedmsg and '電話' in receivedmsg:
            try:
                if ( # 檢查資料是否有填，字數注意有換行符
                    len(receivedmsg.split('學號')[-1].split('\n')[0])<4 or
                    len(receivedmsg.split('姓名')[-1].split('\n')[0])<3 or
                    len(receivedmsg.split('電話')[1].split('\n')[0]) <11
                    ):
                    raise Exception
                # 得到學號
                ID = receivedmsg.split('學號')[-1].split('\n')[0][1:]
                # 直接完整save學號 -Garrett, 2021.01.28  
                ID = int(ID)
                
                #無{ 學號: }欄位取得學號方式
                #import re
                #ID =  [float(s) for s in re.findall(r'-?\d+\.?\d*', receivedmsg)]
                #ID = int(ID[0])


                # 學號不再限定只有5碼 -Garrett, 2021.01.28  
                #if len(ID)==6:
                #    ID = int(ID[-4:])
                #elif len(ID)<=4:
                #    ID = int(ID)
            except Exception:
                LineMessage = '學號、姓名，其中一項未填或錯誤。'
            else:
                reportData[groupID][str(ID)] = receivedmsg
                LineMessage = str(ID)+'號弟兄，回報成功。'

        elif '使用說明' in receivedmsg and len(receivedmsg)==4:
            LineMessage = (
                '收到以下正確格式\n'
                '才會正確記錄回報。\n'
                '----------\n'
                '姓名：\n'
                '學號：\n'
                '電話：\n'
                '(下方欄位依回報類型更改)\n'
                '----------\n'
                '\n'
                '指令\n' 
                '----------\n'   
                '•放假格式\n'
                '•假日格式\n'
                '•收假格式\n'
                '->正確格式範例。\n'
                '•回報統計\n'
                '->顯示完成回報的號碼。\n'
                '•輸出回報\n'
                '->貼出所有回報，並清空回報紀錄。\n'
                '•清空\n'
                '->可手動清空Data，除錯用。\n'

            )
        elif '回報統計' in receivedmsg and len(receivedmsg)==4:
            try:
                LineMessage = (
                    '完成回報的號碼有:\n'
                    +str([number for number in sorted(reportData[groupID].keys())]).strip('[]')
                )
            except BaseException as err:
                LineMessage = '錯誤原因: '+str(err)
        elif '輸出回報' in receivedmsg and len(receivedmsg)==4:
            try:
                LineMessage = ''
                for data in [reportData[groupID][number] for number in sorted(reportData[groupID].keys())]:
                    LineMessage = LineMessage + data +'\n\n'
            except BaseException as err:
                LineMessage = '錯誤原因: '+str(err)
            else:
                reportData[groupID].clear()

        elif '放假格式' in receivedmsg and len(receivedmsg)==4:
            LineMessage = '學號：\n姓名：\n電話：\n返家狀況：'
        elif '假日格式' in receivedmsg and len(receivedmsg)==4:
            LineMessage = '學號：\n姓名：\n電話：\n地點：\n做什麼：\n預計返家時間：\n跟誰：'
        elif '收假格式' in receivedmsg and len(receivedmsg)==4:
            LineMessage = '學號：\n姓名：\n電話：\n地點：\n做什麼：\n跟誰：\n收假方式：'

        # for Error Debug, Empty all data -Sophia_Chen, 2021.01.25        
        elif '清空' in receivedmsg and len(receivedmsg)==2:
            reportData[groupID].clear()
            LineMessage = '資料已重置!'
        
        if LineMessage :
            message = TextSendMessage(text=LineMessage)
            line_bot_api.reply_message(event.reply_token, message)
        
        update_report_data(groupID, reportData[groupID])

if __name__ == "__main__":
    global reportData
    reportData = {}
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
