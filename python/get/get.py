import argparse
import os
import getpass
import xml.etree.ElementTree as ET
import time
import requests

downloaded = []

def parse_args():
    parser = argparse.ArgumentParser()
    
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
        help="Keep files which are successfully downloaded",
    )

    parser.add_argument(
        "-i",
        "--interval",
        default=0,
        help="Check interval(sec), 0 for no repeat (default: %(default)s)",
        type=int,
    )
    
    parser.add_argument(
        "-o",
        "--output",
        default="C:\\Users\\user\\Downloads",
        help="Download dir (default: %(default)s)",
    )

    args = parser.parse_args()
    return args

def login(username, password):
    url = "https://mail.add.re.kr/user.User.do"
    session = requests.session()
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.97 Safari/537.36",
        }
    )

    r = session.post(
        url,
        data={
            "cmd": "login",
            "DOMAIN": "mail.add",
            "USERS_ID": username,
            "USERS_PASSWD": password,
        },
    )
    if "통합 메일 시스템" not in r.text:
        print(r.text)
        raise ValueError("아이디/비밀번호 오류")

    return session

def delete_data(sess, data):
    url = "https://mail.add.re.kr/data.Data.do"

    r = sess.post(
        url,
        data={
            "cmd": "deleteData",
            "DATA_IDX": data["idx"],
        }
    )
    # TODO: check


def download_data(sess, data, save_dir):
    global downloaded
    url = "https://mail.add.re.kr/data.Data.do"

    dt = data["data"]
    for f in dt:
        if f["path"] in downloaded:
            continue

        print("[*] Downlaoding:", f["name"])
        r = sess.post(
            url,
            params={
                "cmd": "attache",
                "DATA_FLAG": "R",
                "DOC_NO": data["no"],
                "fPath": f["path"],
                "fName": f["name"],
            },
            data={
                "DATA_FLAG": "R",
                "DOC_NO": data["no"],
            }
        )

        with open(os.path.join(save_dir, f["name"]), "wb") as fp:
            fp.write(r.content)

        downloaded.append(f["path"])
        print("[*] Done:", f["name"])


def get_not_read_files(sess):
    url = "https://mail.add.re.kr/data.Data.do"
    r = sess.post(
        url,
        data={
            "cmd": "showDataList",
            "gubun": "5",
            "M_FLAG": "I",
            "DATA_FLAG": "R",
            "netType": "S",
        }
    )

    xml = r.text

    tree = ET.fromstring(xml)
    data_list = []
    for data in tree.findall("DATA_LIST"):
        is_read = data.find("READ_YN").text
        
        if is_read == "Y":
            continue

        data_list.append(
            {
                "idx": data.find("DATA_IDX").text,
                "no": data.find("DOC_NO").text,
                "title": data.find("DATA_TITLE").text,
                "recv_time": data.find("DATA_RECV_TIME").text,
                "status": data.find("STATUS").text,
            }
        )

        names = data.find("DATA_NAME").text.split(":")
        paths = data.find("DATA_PATH").text.split(":")
        files = [{"name": n, "path": p} for n, p in zip(names, paths)]
        data_list[-1]["data"] = files

    
    return data_list
    

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
        exit(1)

    sess = login(username, password)
    print("[*] Successfully logged in")

    while True:

        data_list = get_not_read_files(sess)
        for data in data_list:
            download_data(sess, data, args.output)
            if not args.keep:
                delete_data(sess, data)
        
        if args.interval == 0:
            break

        time.sleep(args.interval)
 


if __name__ == "__main__":
    main()