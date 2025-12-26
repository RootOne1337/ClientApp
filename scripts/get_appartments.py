import json
import subprocess
from datetime import datetime
from dataclasses import dataclass
from typing import List
import sys
import time

try:
    import requests
except ImportError:
    print("Некоторые библиотеки не установлены. Устанавливаю...", flush=True)
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
except ValueError:
    print("Некорректно установленные библиотеки. Переустанавливаю...", flush=True)
    subprocess.check_call([sys.executable, "-m", "pip", "uninstall", "-r", "requirements.txt"])
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])

server_names = {
    1: "01.Downtown",
    2: "02.Strawberry",
    3: "03.Vinewood",
    4: "04.Blackberry",
    5: "05.Insquad",
    6: "06.Sunrise",
    7: "07.Rainbow",
    8: "08.Richman",
    9: "09.Eclipse",
    10: "10.LaMesa",
    11: "11.Burton",
    12: "12.Rockford",
    13: "13.Alta",
    14: "14.DelPerro",
    15: "15.Davis",
    16: "16.Harmony",
    17: "17.Redwood",
    18: "18.Hawick",
    19: "19.Grapeseed",
    20: "20.Murrieta",
    21: "21.Vespucci",
    22: "22.Milton"
}


@dataclass
class Profile:
    is_online: bool
    name: str
    server: str
    lvl: int
    exp: int
    max_exp: int
    cash: int
    bank: int
    house: bool
    apartment: bool
    vehicles: bool
    hours_played: int
    vip_level: int
    vip_name: str
    vip_expire_at: int


def from_dict(data: dict, server_name: str) -> Profile:
    # Удаляем ненужные поля
    keys_to_remove = ["age", "id", "sex", "fraction", "fraction_rank", "fraction_rank_name", "friends",
                      "skills",
                      "is_vehicle_view_needed", "business"]
    for key in keys_to_remove:
        data.pop(key, None)

    # Делаем house, apartment, vehicles булевыми
    data["house"] = bool(data["house"])
    data["apartment"] = bool(data["apartment"])
    data["vehicles"] = bool(data["vehicles"])  # True, если есть машины, иначе False

    data["server"] = server_name
    return Profile(**data)


def check_int(s):
    if s != "" and s is not None:
        if s[0] in ('-', '+'):
            return s[1:].isdigit()
        return s.isdigit()
    else:
        return False


def get_profiles(login, password):
    # Login
    url = "https://gta5rp.com/api/V2/users/auth/login"
    payload = "{\"login\": \"" + login + "\", \"password\": \"" + password + "\", \"remember\": \"0\"}"
    headers = {
        'content-type': "application/json"
    }
    response = requests.request("POST", url, data=payload, headers=headers)
    account = json.loads(response.text)
    token = account["token"]

    profiles: List[Profile] = []
    # Getting profiles
    for x in range(1, 23):
        url = "https://gta5rp.com/api/V2/users/chars/" + str(x)
        headers = {
            'x-access-token': token
        }
        response = requests.request("GET", url, headers=headers)
        json_data = json.loads(response.text)
        profiles.extend(from_dict(data, server_names.get(x)) for data in json_data)
    return profiles


if __name__ == "__main__":
    if len(sys.argv) == 3:
        login = sys.argv[1]
        password = sys.argv[2]
        profiles = get_profiles(login, password)
        for profile in profiles:
            if profile.is_online:
                if profile.apartment or profile.house:
                    print("1", flush=True)
                    sys.exit(0)
                else:
                    print("0", flush=True)
                    sys.exit(0)
        print("Profile wasn't founded", flush=True)
        sys.exit(0)
    else:
        print("Usage: scripts\\getlvl.py <login> <password>", flush=True)
        sys.exit(0)
