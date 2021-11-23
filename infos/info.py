# 整合水电燃气的API

import time
from datetime import datetime

import requests
from requests import *
import configparser
import json
import paho.mqtt.client
import threading

import string,random
import re
from lxml import etree

mqtt = paho.mqtt.client

WaterHeaders = {
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 12_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 MicroMessenger/7.0.5(0x17000523) NetType/WIFI Language/zh_CN',
    'Referer': 'http://www.jlwater.com/waterFee/waterWx',
    'Accept-Language': 'zh-cn',
    'Accept-Encoding': 'gzip, deflate'
}

ElectricityHeaders = {
    'Host': 'weixin.js.sgcc.com.cn',
    'Connection': 'keep-alive',
    'Content-Length': '0',
    'content-type': 'application/json',
    'Accept-Encoding': 'gzip,compress,br,deflate',
    'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 MicroMessenger/8.0.0(0x18000026) NetType/WIFI Language/zh_CN',
    'Referer': 'https://servicewechat.com/wx203b37ad2ad5d2a6/32/page-frame.html'
}

GasHeaders = {
    'content-type': 'application/x-www-form-urlencoded'
}

Water_API_URL = "http://www.jlwater.com/waterFee/getConsWaterFeeSummary"
Electricity_API_URL = "https://weixin.js.sgcc.com.cn/wxapp_dlsh/wx/oauth_executeNewMini.do"

cfg = configparser.ConfigParser()
cfg.read('/home/ubuntu/infos/param.ini')


def on_connect(client, userdata, flags, rc):
    print("Connected with result code "+str(rc))


def on_message(client, userdata, msg):
    print(msg.topic+" " + ":" + str(msg.payload))


client_id = time.strftime('%Y%m%d%H%M%S', time.localtime(time.time()))
client = mqtt.Client(client_id)  # ClientId不能重复，所以使用当前时间
client.username_pw_set("freefitter", "wxy311???")  # 必须设置，否则会返回「Connected with result code 4」
client.on_connect = on_connect
client.on_message = on_message
#client.connect("www.freefitter.com", 18883, 60)
# client.loop_forever()

def getWaterFee():
    custno = cfg.get('NJSWParam', 'consNo')
    cookies = cfg.get('NJSWParam', 'cookie')
    query_dict = {'consNo': custno, }
    WaterHeaders["Cookie"] = cookies
    try:
        response = requests.get(Water_API_URL, params=query_dict, headers=WaterHeaders)
    except ReadTimeout:
        print("Connection timeout....")
    except ConnectionError:
        print("Connection Error....")
    except RequestException:
        print("Unknown Error")
    client.publish("homefee/water", payload=json.dumps(response.text), qos=0)  # 发送消息
    return response.text
    pass


def getElectricityFee():
    timestamp1 = cfg.get('GJDWParam', 'timestamp')
    noncestr = cfg.get('GJDWParam', 'noncestr')
    sign = cfg.get('GJDWParam', 'sign')
    url = Electricity_API_URL + "?openid=olmSdjpBtXIxbgh9V-r1lPe3d2vg&timestamp=" + timestamp1 + "&noncestr=" + noncestr + "&sign=" + sign + "&unionid=oEa171FLnZ7T8snBJsPBiONGRUHw&userInfo=null"
    try:
        response = requests.post(url, headers=ElectricityHeaders)
    except ReadTimeout:
        print("Connection timeout....")
    except ConnectionError:
        print("Connection Error....")
    except RequestException:
        print("Unknown Error")
    res = response.content.decode('utf-8')
    if res.find("html") >= 0:
        print("参数存在问题,请重新抓包填写")
        return
    ret = json.loads(res)
    if ret["errcode"] == "0000":
        cfg.set("GJDWParam", "timestamp", ret["timestamp"])
        cfg.set("GJDWParam", "noncestr", ret["noncestr"])
        cfg.set("GJDWParam", "sign", ret["sign"])
        cfg.write(open('/home/ubuntu/infos/param.ini', 'w'))
    else:
        print("业务错误.....")
    if "yeModel" in ret:
        client.publish("homefee/electricity", payload=ret["yeModel"], qos=0)  # 发送消息
        return ret["yeModel"]
    else:
        return json.loads("{'yeModel':{}}")
    pass


def getGasFee():
    url = "https://zrds.zrhsh.com/controller/payfee/getcustomerMoneyListForMp.do"
    data = "custCode=1101342079&envir=2&startTime=202109&endTime=202109"
    try:
        response = requests.post(url, data=data, headers=GasHeaders)
    except ReadTimeout:
        print("Connection timeout....")
    except ConnectionError:
        print("Connection Error....")
    except RequestException:
        print("Unknown Error")
    ret = json.loads(response.text)
    if "1" == ret["status"]:
        dataRet = {
            "balance": ret["data"]["balance"]
        }
    else:
        dataRet = {
            "balance": "-"
        }
    client.publish("homefee/gas", payload=json.dumps(dataRet), qos=0)  # 发送消息
    return dataRet
    pass


def getPiInfo():
    try:
        response = requests.get("http://www.freefitter.com:8001/pi-dashboard/?ajax=true")
    except ReadTimeout:
        print("Connection timeout....")
    except ConnectionError:
        print("Connection Error....")
    except RequestException:
        print("Unknown Error")
    client.publish("pi/info", payload=response.text, qos=0)  # 发送消息
    return response.text
    pass

def getWeatherInfo():
    try:
        response = requests.get("https://api.weatherat.com/frontend/realtime/brief/1379")
    except ReadTimeout:
        print("Connection timeout....")
    except ConnectionError:
        print("Connection Error....")
    except RequestException:
        print("Unknown Error")
    client.publish("weather/now", payload=response.text, qos=0)  # 发送消息
    return response.text
    pass

baidu_access_token = '121.ee494fb5783120086b90b01dc8f6a7fa.YHS3F60wAT82TX4MptOEBbL3nFUE1XYiLAcF9Pw.GUnJfQ'

def getBaiduInfo():
    nowDate = time.strftime("%Y%m%d", time.localtime())
    url = "https://openapi.baidu.com/rest/2.0/tongji/report/getData?access_token=" + baidu_access_token + "&site_id=16652070&start_date=" + nowDate + "&end_date=" + nowDate + "&metrics=pv_count&method=overview%2FgetCommonTrackRpt";
    print(url)
    try:
        response = requests.get(url)
    except ReadTimeout:
        print("Connection timeout....")
    except ConnectionError:
        print("Connection Error....")
    except RequestException:
        print("Unknown Error")
    ret = json.loads(response.content)
    totalNum = 0
    for item in ret["result"]["sourceSite"]["items"]:
        totalNum = totalNum + item[1]

    dataRet = {
        "totalNum": totalNum,
        "newVisitor": ret["result"]["visitType"]["newVisitor"]["pv_count"],
        "oldVisitor": ret["result"]["visitType"]["oldVisitor"]["pv_count"]
    }
    client.publish("website/info", payload=json.dumps(dataRet), qos=0)  # 发送消息
    return dataRet

def getDateDiff():
    time_1 = str(datetime.now().year) + '-11-18 00:00:00.000'
    time_2 = str(datetime.now())
    time_1_struct = datetime.strptime(time_1, "%Y-%m-%d %H:%M:%S.%f")
    time_2_struct = datetime.strptime(time_2, "%Y-%m-%d %H:%M:%S.%f")
    days = (time_2_struct - time_1_struct).days
    dataRet = {
        "days": days,
    }
    client.publish("birthday/info", payload=json.dumps(dataRet), qos=0)  # 发送消息
    return dataRet


def getRouterInfo():
    goal = ''.join(random.sample(string.digits, 8))
    url = "https://www.freefitter.com:8443/_api/"
    payload = json.dumps({
        "id": int(goal),
        "method": "rog_status.sh",
        "params": [
            2
        ],
        "fields": ""
    })
    headers = {
        'Content-Type': 'application/json'
    }
    try:
        response = requests.request("POST", url, headers=headers, data=payload)
    except ReadTimeout:
        print("Connection timeout....")
    except ConnectionError:
        print("Connection Error....")
    except RequestException:
        print("Unknown Error")
    ret = json.loads(response.content)
    result = ret["result"]
    resultList = re.split('@@|&nbsp;|<br />|\||：', result)
    new_list = [i for i in resultList if i != '']
    dataRet = {
        "CPU": new_list[1].strip(),
        "W2_4G": new_list[3].strip(),
        "W5G_1": new_list[5].strip(),
        "W5G_1": new_list[7].strip(),
        "MEM": new_list[14].strip()
    }
    return dataRet

def getOilFee():
    url = "http://www.qiyoujiage.com/jiangsu.shtml";
    try:
        response = requests.get(url)
    except ReadTimeout:
        print("Connection timeout....")
    except ConnectionError:
        print("Connection Error....")
    except RequestException:
        print("Unknown Error")
    retStr = response.content.decode('utf-8')
    tree = etree.HTML(retStr)
    items = tree.xpath('//*[@id="youjia"]/dl/dd')
    dataRet = {
        "O92": items[0].text,
        "O95": items[1].text,
        "O98": items[2].text
    }
    return dataRet

def pushToBF():
    dataRet = {
        "router": getRouterInfo(),
        "oil": getOilFee()
    }
    print(dataRet)
pushToBF();
#print(getElectricityFee())
#t1 = threading.Thread(target=getRouterInfo)
#t2 = threading.Thread(target=getPiInfo)
#t1.start()
#t2.start()

#print(getPiInfo())
