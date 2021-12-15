import pytesseract
import requests
import requests as req
import execjs
from PIL import Image, ImageFilter
import re
from Crypto.Cipher import AES
from binascii import b2a_hex, a2b_hex
import json
from datetime import datetime, timedelta
from apscheduler.schedulers.blocking import BlockingScheduler
from email.mime.multipart import MIMEMultipart
import smtplib
from email.mime.text import MIMEText


class Email:
    """
    def __init__(self, host, user, password, sender):
    def __init__(self, receiver):
    """
    mail_host = 'smtp.163.com'
    mail_user = '************'
    # 邮箱的授权码
    mail_pass = '************'
    # 发送者邮箱
    sender = '************'

    def __init__(self, host, user, password, sender):
        self.mail_host = host
        self.mail_user = user
        self.mail_pass = password
        self.sender = sender

    def __init__(self, receiver=['************']):
        # 传入列表
        self.receivers = receiver

    def send_email(self, subject, text=None, filePath=None):
        message = MIMEMultipart()
        message['Subject'] = subject
        message['From'] = self.sender
        message['To'] = ",".join(self.receivers)
        if text:
            message.attach(MIMEText(text, 'plain', 'utf-8'))
        if filePath:
            with open(filePath, 'rb') as file:
                content = file.read()
            attachment = MIMEText(content, 'base64', 'utf-8')
            attachment['Content-Type'] = 'application/octet-stream'
            attachment['Content-Disposition'] = 'attachment; filename="' + filePath.split('/')[-1] + '"'
            message.attach(attachment)
        try:
            smtp = smtplib.SMTP_SSL(self.mail_host, 465)
            smtp.login(self.mail_user, self.mail_pass)
            smtp.sendmail(self.sender, self.receivers, message.as_string())
            smtp.quit()
            return True
        except Exception as e:
            print(e)
            return False


class AesCbcZeroPadding(object):
    """
    AES CBC zeropadding
    结果呈现 hex， 中途使用 utf-8 编码
    """

    # 如果text不足16位的倍数就用空格补足为16位
    def __init__(self, key, iv):
        self.key = key
        self.iv = iv

    def add_to_16(self, text):
        if len(text.encode('utf-8')) % 16:
            add = 16 - (len(text.encode('utf-8')) % 16)
        else:
            add = 0
        text = text + ('\0' * add)
        return text.encode('utf-8')

    # 加密函数
    def encrypt(self, text):
        key = self.key.encode('utf-8')
        mode = AES.MODE_CBC
        iv = bytes(self.iv.encode('utf-8'))
        text = self.add_to_16(text)
        cryptos = AES.new(key, mode, iv)
        cipher_text = cryptos.encrypt(text)
        # 因为AES加密后的字符串不一定是ascii字符集的，输出保存可能存在问题，所以这里转为16进制字符串
        return b2a_hex(cipher_text)

    # 解密后，去掉补足的空格用strip() 去掉
    def decrypt(self, text):
        key = self.key.encode('utf-8')
        iv = bytes(self.iv.encode('utf-8'))
        mode = AES.MODE_CBC
        cryptos = AES.new(key, mode, iv)
        plain_text = cryptos.decrypt(a2b_hex(text))
        return bytes.decode(plain_text).rstrip('\0')


class OutSchool(object):
    username = '************'
    password = '************'
    head = {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
        'Accept-Encoding': 'gzip, deflate',
        'Accept-Language': "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
        'Connection': 'keep-alive',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.75 Safari/537.36 Edg/86.0.622.38',
    }
    cookie = None
    session = None

    def getHtml(self, url, cookie=None):
        try:
            r = req.get(url, headers=self.head, cookies=cookie)
            r.encoding = r.apparent_encoding
            r.raise_for_status()
            return r
        except req.exceptions as e:
            print(url, "请求出错", e)
            return None

    def postUrl(self, url, data, cookie=None):
        try:
            r = req.post(url, headers=self.head, cookies=cookie, data=data)
            r.encoding = r.apparent_encoding
            r.raise_for_status()
            return r
        except req.exceptions as e:
            print(url, "请求出错", e)
            return None

    # 需要搞定图像识别，得到验证码
    def getCode(self, cookie=None):
        # 需要获取验证码
        codeUrl = "http://pass.hust.edu.cn/cas/code"
        r = self.getHtml(codeUrl, cookie=cookie)
        path = "./image/code.gif"
        with open(path, "wb") as file:
            file.write(r.content)

        image = Image.open(path)
        try:
            while True:
                s = image.tell()
                image.save(path[:-4] + str(s) + '.png')
                image.seek(s + 1)
        except EOFError:
            pass

        # 第一张和第四张
        # 0 17 37 40
        image3 = Image.open(path[:-4] + '3' + '.png').crop((0, 16, 38, 40))
        # w: 37 h: 23
        image0 = Image.open(path[:-4] + '0' + '.png').crop((44, 16, 82, 40))
        image = Image.new("RGB", (image3.size[0] * 2, image3.size[1]))
        image.paste(image3, (0, 0))
        image.paste(image0, (image3.size[0], 0))
        image = image.convert('L')
        image.save(path[:-4] + 'gray.png')
        # 黑色是 0， 白色是 1
        threshold = 200
        table = []
        for i in range(256):
            if i < threshold:
                table.append(0)
            else:
                table.append(1)
        image = image.point(table, '1')
        image.save(path[:-4] + '111.png')
        image = image.filter(ImageFilter.ModeFilter(2))
        image.save(path[:-4] + '111_mode.png')
        code = pytesseract.image_to_string(image, config="--psm 7")
        # 替换非数字部分
        code = re.sub(r'[^\d]', '', code)
        return code

    def login(self, url):
        response = self.getHtml(url)
        assert response is not None
        html = response.text
        curCookie = response.cookies
        username = '************'
        password = '************'

        lt = re.findall('id="lt" name="lt" value="(.*?)"', html)[0]
        execution = re.findall('name="execution" value="(.*?)"', html)[0]
        with open('des.js') as file:
            comp = execjs.compile(file.read())
        s = username + password + lt
        rsa = comp.call('strEnc', s, '1', '2', '3')
        code = self.getCode(curCookie)
        print(code)
        if len(code) != 4:
            return False
        # code = 1234
        loginData = {
            'code': code,
            'rsa': rsa,
            'ul': len(username),
            'pl': len(password),
            'lt': lt,
            'execution': execution,
            '_eventId': 'submit'
        }
        self.session = requests.Session()
        r = self.session.post(url, data=loginData, headers=self.head, cookies=curCookie)
        if re.search(r'连续登录失败5次，账号将被锁定1分钟，剩余次数', r.text) is not None:
            return False
        return True

    def dateOutSchool(self):
        # 预约出校的函数，需要先发一次 get ，得到 cookie，使用 session 保存
        url = 'http://access.hust.edu.cn/IDKJ-P/P/studentApi'
        r = self.session.get(url, headers=self.head)

        # 对如下json加密，加密之后填到上面的data，然后直接post就行
        f_form_data = {"applyUserName": '************', "applyUserId": '************', "schoolArea": '************',
                       "bookingUserIDcard": '************', "deptName": '************', "deptNo": '************',
                       "bookingStartTime": "2021-12-14 23:13:46", "bookingEndTime": "2021-12-15 23:13:46",
                       "visitCase": "11111111"}
        # 修改一下时间，修改为当前时间，和一天之后的时间
        startTime = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        endTime = (datetime.strptime(startTime, '%Y-%m-%d %H:%M:%S') + timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S')
        f_form_data['bookingStartTime'] = startTime
        f_form_data['bookingEndTime'] = endTime

        # 对数据进行加密
        aes = AesCbcZeroPadding('123456789ABCDEFG', '123456789ABCDEFG')
        f_str_data = json.dumps(f_form_data, ensure_ascii=False, separators=(',', ':'))
        # 注意需要转化数据格式
        en_data = aes.encrypt(f_str_data).decode('utf-8')
        data = {
            "parkId": '************',
            "sign": '************',
            "timeStamp": "2019-04-30 10:57:32",
            "data": en_data
        }
        postUrl = 'http://access.hust.edu.cn/IDKJ-P/student/resStudentAPI'

        r = self.session.post(postUrl, json=data, headers=self.head)
        try:
            if r.json()['resCode'] != '0':
                print('预约失败')
                return False
            else:
                print('预约成功')
                return True
        except Exception as e:
            print('返回了err网页')
            return False


def job():
    appCenterUrl = "https://pass.hust.edu.cn/cas/login?service=http://m.hust.edu.cn/wechat/apps_center.jsp"
    outSchool = OutSchool()
    fail_times = 0
    login_flag = False
    with open('log.txt', 'w') as file:
        while True:
            try:
                if outSchool.login(appCenterUrl):
                    file.write('登录成功')
                    login_flag = True
                    fail_times = 0
                    break
                else:
                    file.write('登录失败')
                    fail_times = fail_times + 1
            except Exception as e:
                file.write('登录失败，报错，catch到了')
                fail_times = fail_times + 1

            if fail_times >= 10:
                file.write('登录系统出现问题，需要赶紧处理')
                break
            else:
                continue

        while login_flag:
            try:
                if outSchool.dateOutSchool():
                    file.write('预约成功')
                    fail_times = 0
                else:
                    file.write('预约失败')
                    fail_times = fail_times + 1
            except Exception as e:
                file.write('预约失败，报错，catch到了')
                fail_times = fail_times + 1

            if fail_times >= 10:
                file.write('预约系统出现问题，需要赶紧处理')
                break
            else:
                continue
    # asdasda
    email = Email()
    with open('log.txt', 'r') as file:
        s = file.read()

    sub = datetime.now().strftime('%Y-%m-%d') + '预约出校'
    email.send_email(subject=sub, text=s)


def main():
    scheduler = BlockingScheduler(timezone='Asia/Shanghai')
    scheduler.add_job(job, 'cron', hour=8)
    scheduler.start()


if __name__ == '__main__':
    main()
