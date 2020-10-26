import argparse
import os
import sys
import re
import time
import pathlib
import getpass
import xml.etree.ElementTree as ET
import zipfile
import requests


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("path", nargs="+", help="Target file/directory to be sent")
    parser.add_argument(
        "-p",
        "--prompt",
        action="store_true",
        default=False,
        help="Use terminal to input auth instead of env variable",
    )
    parser.add_argument(
        "-k",
        "--keep",
        action="store_true",
        default=False,
        help="Keep files which are successfully sent (This option may cause disk space problem)",
    )
    parser.add_argument(
        "-c",
        "--compress",
        action="store_true",
        default=False,
        help="Compress files to zip before sending",
    )

    args = parser.parse_args()
    return args


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
    data["cmd"] = "dataSend"

    r = sess.post(send_file_url, data=data)
    # TODO: check


def get_data_list(sess):
    data_list_url = "https://iss.add.re.kr/data.Data.do"
    data = {
        "DATA_FLAG": "S",
        "M_FLAG": "I",
        "cmd": "showDataList",
        "gubun": "5",
        "netType": "I",
    }

    r = sess.post(data_list_url, data=data)
    xml = r.text

    tree = ET.fromstring(xml)
    status_map = {
        "C": "처리완료",
        "X": "전송중",
        "S": "전송중",
        "M": "전송중",
        "W": "전송대기",
    }

    data_list = []
    for data in tree.findall("DATA_LIST"):
        status = status_map.get(data.find("STATUS").text, data.find("STATUS").text)

        data_list.append(
            {
                "idx": data.find("DATA_IDX").text,
                "no": data.find("DOC_NO").text,
                "title": data.find("DATA_TITLE").text,
                "recv_time": data.find("DATA_RECV_TIME").text,
                "filename": data.find("DATA_NAME").text,
                "status": status,
            }
        )

    return data_list


def check_sent(f, data_list):
    for data in data_list:
        if data["title"] != f.name:
            continue

        status = data["status"]
        if status == "처리완료":
            return True, status
        else:
            return False, status

    # data not found
    raise ValueError("%s not uploaded, please check manually" % f.name)


def delete_sent_file(sess, f, data_list):

    data = None
    for d in data_list:
        if d["title"] == f.name:
            data = d
            break
    else:
        raise ValueError("Matching data not found")

    delete_file_url = "https://iss.add.re.kr/data.Data.do"
    data = {
        "DATA_IDX": data["idx"],
        "cmd": "deleteData",
    }

    r = sess.post(delete_file_url, data=data)
    # TODO: check


def get_disk_space_left(sess):
    disk_space_url = "https://iss.add.re.kr/user.AuthUser.do"
    data = {
        "cmd": "showDiskInfo",
    }

    r = sess.post(disk_space_url, data=data)
    text = r.text
    matches = re.findall("<DATA>.+<USE>(.+)</USE>.+</DATA>", text)
    if not matches:
        raise ValueError("Cannot detect disk space left: " + text)

    space = matches[0][:-2]  # strip "MB" part
    spaces_total = 1024
    return spaces_total - int(space)


def get_files(path):
    p = pathlib.Path(path)
    if p.is_dir():
        return p.glob("*")
    else:
        return [p]


def compress_files(files, zipname=None):
    if not files:
        raise ValueError("No files given")

    if zipname is None:
        zipname = files[0].name + ".zip"

    with zipfile.ZipFile(zipname, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in files:
            zf.write(f)

    return pathlib.Path(zipname)


def main():
    args = parse_args()

    # Login
    if args.prompt:
        username = input("Username: ").strip()
        password = getpass.getpass("Password: ").strip()
    else:
        username = os.environ.get("ADD_USERNAME")
        password = os.environ.get("ADD_PASSWORD")

    if not username or not password:
        print("Set ADD_USERNAME and ADD_PASSWORD for authentication")
        print("If you want to type auth information directly, use `-p` option")
        sys.exit(1)

    session = login(username, password)
    print("[*] Successfully logged in")

    # Send files
    files = []
    for p in args.path:
        files.extend(get_files(p))

    if args.compress:
        files = [compress_files(files)]

    num_files = len(files)
    print("[*] Trying to send %d file(s)..." % num_files)

    for f in files:
        if not f.is_file():
            print("[*] %s is not a file, skipping..." % f.name)

        fd = f.open(mode="rb")

        # check disk space first, if not enough space, stop sending
        space_left = get_disk_space_left(session)
        file_size = os.fstat(fd.fileno()).st_size
        file_size_mb = int(file_size / 1024 / 1024)

        if space_left - file_size_mb < 10:  # safe margin for 10MB
            print("Not enough space left")
            sys.exit(1)

        # upload and send the file
        _dir = upload_file(session, fd)
        send_file(session, fd, _dir)
        time.sleep(
            1
        )  # short interval after sending file to prevent long waiting for small files

        # check whether the file is send to local machine
        check_interval = 10
        data_list = get_data_list(session)
        while True:
            chk, status = check_sent(fd, data_list)
            if chk:
                break

            print("%s Not sent (Status: %s)..." % (fd.name, status))
            time.sleep(check_interval)
            data_list = get_data_list(session)

        print("[*] %s sent!" % fd.name)

        if not args.keep:
            print("[*] Deleting %s..." % fd.name)
            delete_sent_file(session, fd, data_list)


if __name__ == "__main__":
    main()