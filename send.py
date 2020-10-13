import os
import re
import time
import time
import xml.etree.ElementTree as ET
import requests


def login(username, password):
    login_url = "https://iss.add.re.kr/user.User.do"
    session = requests.session()
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.75 Safari/537.36",
        }
    )

    r = session.post(
        login_url,
        data={
            "DOMAIN": "add.re.kr",
            "USERS_ID": username,
            "USERS_PASSWD": password,
            "cmd": "login",
        },
    )

    if "통합 메일 시스템" not in r.text:
        print(r.text)
        raise ValueError("아이디/비밀번호 오류")

    return session


def upload_file(sess, f):
    upload_file_url = "https://iss.add.re.kr/bigmail.BigMailFile.do"
    _dir = str(time.time() * 10000)
    params = {
        "cmd": "webmailAttacheFile",
        "DOMAIN": "add.re.kr",
        "USERS_ID": "webmaster",
        "MAX_FILE_SIZE": "10485760",
        "sendType": "data",
        "dir": _dir,
    }

    files = {
        _dir: f,
    }

    r = sess.post(upload_file_url, params=params, files=files)
    if "<result_message>200</result_message>" not in r.text:
        print(r.text)
        raise ValueError("Something is wrong while uploading the file")

    return _dir

def send_file(sess, f, _dir):
    auth_url = "https://iss.add.re.kr/webmail.AuthWebMail.do"
    send_file_url = "https://iss.add.re.kr/data.Data.do"

    # Step 1: authenticate mail
    data = {
        "APRV_YN": "Y",
        "DATA_TITLE": f.name,
        "attache_file": _dir + "/" + f.name,
        "cmd": "privacyFilter",
        "gubun": "5",
    }

    r = sess.post(auth_url, data=data)
    if "<RESULT>SUCCESS</RESULT>" not in r.text:
        print(r.text)
        raise ValueError("Something is wrong while authenticating web mail")

    # Step 2: send file
    data["cmd"] =  "dataSend"

    r = sess.post(send_file_url, data=data)
    # TODO: check


def check_sent(sess, f):
    check_sent_url = "https://iss.add.re.kr/data.Data.do"
    data = {
        "DATA_FLAG": "S",
        "M_FLAG": "I",
        "cmd": "showDataList",
        "gubun": "5",
        "netType": "I",
    }

    r = sess.post(check_sent_url, data=data)
    xml = r.text
    matches = re.findall("<DATA_TITLE>(.+)</DATA_TITLE>", xml)

    if f.name not in matches:
        raise ValueError("%s not uploaded, please check manually" % f.name)

    tree = ET.fromstring(xml)
    status_map = {
        "C": "처리완료",
        "X": "전송중",
        "S": "전송중",
        "M": "전송중",
        "W": "전송대기",
    }
    for data in tree.findall("DATA_LIST"):
        fname = data.find("DATA_TITLE").text
        if fname != f.name:
            continue
        
        status = data.find("STATUS").text
        status_str = status_map.get(status)

        if status_str is None:
            raise KeyError("Unknown status `%s`" % status)

        if status_str == "처리완료":
            return True
        else:
            return False

    # should not come here
    return False


def delete_sent_file(file):
    pass


def check_disk_space(sess):
    check_disk_space_url = "https://iss.add.re.kr/user.AuthUser.do"
    data = {
        "cmd": "showDiskInfo",
    }

    r = sess.post(check_disk_space_url, data=data)
    text = r.text
    matches = re.findall("<DATA>.+<USE>(.+)</USE>.+</DATA>", text)
    if not matches:
        raise ValueError("Cannot detect disk space left: " + text)

    space = matches[0][:-2]  # strip "MB" part
    spaces_total = 1024
    return spaces_total - int(space)


def main():
    username = os.environ.get("ADD_USERNAME")
    password = os.environ.get("ADD_PASSWORD")

    if not username or not password:
        print("Set ADD_USERNAME and ADD_PASSWORD")
        exit(1)

    session = login(username, password)
    space_left = check_disk_space(session)
    
    f = open("testfile.txt", "rb")
    file_size = os.fstat(f.fileno()).st_size
    file_size_mb = int(file_size / 1024 / 1024)

    # safe margin for 10MB
    if space_left - file_size_mb < 10:
        print("Not enough space left")
        exit(1)

    _dir = upload_file(session, f)
    send_file(session, f, _dir)

    check_interval = 10
    while not check_sent(session, f):
        print("%s Not sent..." % f.name)
        time.sleep(check_interval)

    print("sent!")
    
    
if __name__ == "__main__":
    main()