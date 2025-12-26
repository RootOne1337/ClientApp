import subprocess
import sys

try:
    import gspread
    import requests
    from google.oauth2.service_account import Credentials  # Пример библиотеки
except ImportError:
    print("Некоторые библиотеки не установлены. Устанавливаю...", flush=True)
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
except ValueError:
    print("Некорректно установленные библиотеки. Переустанавливаю...", flush=True)
    subprocess.check_call([sys.executable, "-m", "pip", "uninstall", "-r", "requirements.txt"])
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])


def main(pc_name):
    # Авторизация
    name = sys.argv[1]
    SCOPE = ["https://spreadsheets.google.com/feeds",
             "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_file("credentials.json", scopes=SCOPE)
    client = gspread.authorize(creds)

    # Открываем таблицу и лист "Общая"
    sheet = client.open("Учет виртов").worksheet("Total")

    # Получаем все значения из колонки A
    column_a = sheet.col_values(1)

    # Ищем индекс строки с pc_name
    try:
        row_index = column_a.index(pc_name) + 1  # +1 потому что индексы начинаются с 0
        value_b = sheet.cell(row_index, 20).value  # Колонка B — это вторая колонка
        if value_b is None:
            print("5", flush=True)
        else:
            print(value_b, flush=True)
    except ValueError:
        print("")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Использование: script.py PcName")
    else:
        main(sys.argv[1])
