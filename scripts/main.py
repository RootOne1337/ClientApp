import json
import subprocess
from datetime import datetime
from dataclasses import dataclass
from typing import List
import sys
import time
import math

try:
    import gspread
    import requests
    from google.oauth2.service_account import Credentials
except ImportError:
    print("Некоторые библиотеки не установлены. Устанавливаю...", flush=True)
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
    import gspread
    import requests
    from google.oauth2.service_account import Credentials
except ValueError:
    print("Некорректно установленные библиотеки. Переустанавливаю...", flush=True)
    subprocess.check_call([sys.executable, "-m", "pip", "uninstall", "-r", "requirements.txt"])
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
    import gspread
    import requests
    from google.oauth2.service_account import Credentials

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


@dataclass
class User:
    login: str
    email: str
    is_admin: bool
    is_admin_login_available: bool
    last_char_id: int
    last_server: int
    balance: int
    total_donate: int
    pending_donate: str
    has_notifies: bool


def from_dict(data: dict, server_name: str) -> Profile:
    # Удаляем ненужные поля
    keys_to_remove = ["age", "id", "is_online", "sex", "fraction", "fraction_rank", "fraction_rank_name", "friends",
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


def send_to_google_sheet(row_name, value, col, mode):
    # Настройка доступа
    SCOPE = ["https://spreadsheets.google.com/feeds",
             "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_file("credentials.json", scopes=SCOPE)
    client = gspread.authorize(creds)

    # Открываем таблицу и лист "Общая"
    sheet = client.open("Учет виртов").worksheet("Total")

    # Получаем все данные из столбца А и состояния
    column_a = sheet.col_values(1)  # PC NAME
    status_column = sheet.col_values(4)  # Состояние (основа / не основа)

    # Проходим по всем совпадениям
    for row_index, name in enumerate(column_a, start=1):
        # Защита от IndexError: проверяем что status_column достаточно длинный
        status = status_column[row_index - 1] if row_index <= len(status_column) else ""
        
        if name == row_name and status != "Не основа":
            current_time = datetime.now().strftime("%d.%m.%Y %H:%M")

            if mode == "replace":
                sheet.update_cell(row_index, col, value)
                sheet.update_cell(row_index, 12, current_time)
                print(f"{value} placed to row #{row_index}, column #{col}", flush=True)
                return  # После обновления выходим из функции

            elif mode == "plus":
                old_value = sheet.cell(row_index, col).value
                if check_int(old_value):
                    new_value = int(old_value) + value
                else:
                    new_value = value
                sheet.update_cell(row_index, col, new_value)
                sheet.update_cell(row_index, 12, current_time)
                print(f"{value} was added to row #{row_index} (was - {old_value}, now - {new_value}), column #{col}",
                      flush=True)
                return  # После обновления выходим из функции

    print("Account wasn't founded or all matches are 'Не основа'", flush=True)


def get_profiles(login, password):
    # Login
    url = "https://gta5rp.com/api/V2/users/auth/login"
    payload = "{\"login\": \"" + login + "\", \"password\": \"" + password + "\", \"remember\": \"0\"}"
    headers = {
        'content-type': "application/json"
    }
    try:
        response = requests.request("POST", url, data=payload, headers=headers, timeout=10)
        response.raise_for_status()
        account = json.loads(response.text)
        if "token" not in account:
            print("Error: 'token' key missing in API response")
            return []
        token = account["token"]
    except (requests.exceptions.RequestException, json.JSONDecodeError, KeyError) as e:
        print(f"Error in get_profiles API: {e}")
        return []

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


def get_user(login, password):
    url = "https://gta5rp.com/api/V2/users/auth/login"
    payload = "{\"login\": \"" + login + "\", \"password\": \"" + password + "\", \"remember\": \"0\"}"
    headers = {
        'content-type': "application/json"
    }
    try:
        response = requests.request("POST", url, data=payload, headers=headers, timeout=10)
        response.raise_for_status()
        account = json.loads(response.text)
        if "token" not in account:
            print("Error: 'token' key missing in API response")
            return None
        token = account["token"]
    except (requests.exceptions.RequestException, json.JSONDecodeError, KeyError) as e:
        print(f"Error in get_user API: {e}")
        return None
    url = "https://gta5rp.com/api/V2/users/"
    headers = {
        'x-access-token': token
    }
    response = requests.request("GET", url, headers=headers)
    json_data = json.loads(response.text)
    return User(**json_data)


if __name__ == "__main__":
    if len(sys.argv) == 5:
        row_name = sys.argv[1]
        value = int(sys.argv[2])
        col = int(sys.argv[3])
        mode = sys.argv[4]
        send_to_google_sheet(row_name, value, col, mode)

    if len(sys.argv) == 2:
        name = sys.argv[1]
        SCOPE = ["https://spreadsheets.google.com/feeds",
                 "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_file("credentials.json", scopes=SCOPE)
        client = gspread.authorize(creds)

        # Открываем таблицу и лист "Общая"
        sheet = client.open("Учет виртов").worksheet("Total")
        pc_name = sheet.col_values(1)
        block = sheet.col_values(15)
        ban = sheet.col_values(16)
        for row_index, pc in enumerate(pc_name, start = 1):
            if pc == name:
                if (len(block) >= row_index and block[row_index - 1].replace(" ", "").replace("\t", "") != "") or (len(ban) >= row_index and ban[row_index - 1].replace(" ", "").replace("\t", "") != ""):
                    print("|",block[row_index - 1],"|")
                    print("|",ban[row_index - 1],"|")
                    print("1", flush=True)
                else:
                    print("0", flush=True)

    elif len(sys.argv) == 3:
        login = sys.argv[1]
        password = sys.argv[2]
        profiles = get_profiles(login, password)
        print("Profiles:\t", flush=True)
        SCOPE = ["https://spreadsheets.google.com/feeds",
                 "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_file("credentials.json", scopes=SCOPE)
        client = gspread.authorize(creds)

        # Открываем таблицу и лист "Общая"
        sheet = client.open("Учет виртов").worksheet("Total")

        # Получаем все данные из столбца А и состояния
        server = sheet.col_values(2)  # Server
        profile_name = sheet.col_values(3)  # Name
        vipType = sheet.col_values(4)  # Vip type
        vipDuration = sheet.col_values(5)  # Vip duration
        money = sheet.col_values(7)  # Money
        flat = sheet.col_values(11)  # House
        for profile in profiles:
            for row_index, server_name in enumerate(server, start=1):
                # IndexError protection
                if row_index > len(profile_name) or row_index > len(vipType) or row_index > len(vipDuration):
                    continue
                if server_name == profile.server and profile_name[row_index - 1].replace(" ","_") == profile.name:
                    print(f"Found in table, row #{row_index}", flush=True)
                    if vipType[row_index - 1] != "Не основа":
                        if profile.vip_level == 1:
                            sheet.update_cell(row_index, 4, "Standart")
                        elif profile.vip_level == 2:
                            sheet.update_cell(row_index, 4, "Gold")
                        elif profile.vip_level == 3:
                            sheet.update_cell(row_index, 4, "Platinum")
                        sheet.update_cell(row_index, 5, math.ceil((profile.vip_expire_at - time.time()) / 86400))
                    sheet.update_cell(row_index, 7, profile.cash+profile.bank)
                    if profile.house or profile.apartment:
                        sheet.update_cell(row_index, 11, "Квартира")
                    else:
                        sheet.update_cell(row_index, 11, "")
            print("Server:\t\t" + profile.server, flush=True)
            print("Name:\t\t" + profile.name, flush=True)
            print("Lvl:\t\t" + str(profile.lvl), flush=True)
            print("Exp:\t\t" + str(profile.exp), flush=True)
            print("ExpM:\t\t" + str(profile.max_exp), flush=True)
            print("Cash:\t\t" + str(profile.cash), flush=True)
            print("Bank:\t\t" + str(profile.bank), flush=True)
            print("House:\t\tYES" if profile.house else "House:\t\tNO", flush=True)
            print("Apartment:\tYES" if profile.apartment else "Apartment:\tNO", flush=True)
            print("Vehicles:\tYES" if profile.vehicles else "Vehicles:\tNO", flush=True)
            print("Hours played:\t" + str(profile.hours_played), flush=True)
            print("Vip lvl:\t" + str(profile.vip_level), flush=True)
            print("Vip type:\t" + profile.vip_name, flush=True)
            print("Vip duration:\t" + str(round((profile.vip_expire_at - time.time()) / 86400)) + " days\n", flush=True)

    elif len(sys.argv) == 4:
        login = sys.argv[1]
        password = sys.argv[2]
        row_name = sys.argv[3]
        user = get_user(login,password)
        if user is not None and user.balance > 0:
            SCOPE = ["https://spreadsheets.google.com/feeds",
                     "https://www.googleapis.com/auth/drive"]
            creds = Credentials.from_service_account_file("credentials.json", scopes=SCOPE)
            client = gspread.authorize(creds)

            # Открываем таблицу и лист "Общая"
            sheet = client.open("Учет виртов").worksheet("Total")

            # Получаем все данные из столбца А и состояния
            column_a = sheet.col_values(1)  # PCNAME
            status_column = sheet.col_values(10)  # DP

            for row_index, name in enumerate(column_a, start=1):
                if name == row_name:
                    print(f"Found in table, row #{row_index}", flush=True)
                    sheet.update_cell(row_index, 10, user.balance)
                    print(f"{user.balance} placed to row #{row_index}, column #10", flush=True)

        print("Login:\t\t" + user.login, flush=True)
        print("Email:\t\t" + user.email, flush=True)
        print("Last char:\t\t" + str(user.last_char_id), flush=True)
        print("Last server:\t\t" + str(user.last_server), flush=True)
        print("Balance:\t\t" + str(user.balance), flush=True)
        print("Total donate:\t\t" + str(user.total_donate), flush=True)
        print("Pending donate:\t\t" + str(user.pending_donate), flush=True)

    else:
        print("Usage: main.py <row_name> <value> <column_number> <mode>", flush=True)
        sys.exit("Usage: python3 main.py <row_name> <value> <column_number> <mode>")
