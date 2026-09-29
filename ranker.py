import requests
import json
from datetime import date

today = date.today().isoformat()

headers = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Accept-Language": "ru-US,ru;q=0.9",
    "Connection": "keep-alive",
    "Content-Type": "application/json;charset=UTF-8",
    "Profile-Type": "student",
    "Sec-Fetch-Dest": "empty",
    "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Mobile Safari/537.36",
    "X-Mes-RoleId": "1",
    "X-mes-subsystem": "familyweb",
    "Sec-Fetch-Site": "same-origin",
    "sec-ch-ua": "\"Chromium\";v=\"147\", \"Not.A/Brand\";v=\"8\"",
    "sec-ch-ua-mobile": "?1",
    "sec-ch-ua-platform": "\"Android\""
}

CACHE_FILE = "users_cache.json"

GREEN = "\033[92m"
YELLOW = "\033[93m"
ORANGE = "\033[38;5;208m"
RED = "\033[91m"
RESET = "\033[0m"

def load_cache():
    try:
        with open(CACHE_FILE, 'r') as f:
            cache = json.load(f)
    except FileNotFoundError:
        return {}
    if "users" in cache:
        return cache["users"]
    return cache

def save_cache(cache):
    with open(CACHE_FILE, 'w') as f:
        json.dump(cache, f, ensure_ascii=False, indent=4)

def get_and_parse_rank(my_uuid, subject=None):
    subject_param = f"&subjectId={subject}" if subject else ""
    response = requests.get(f'https://school.mos.ru/api/ej/rating/v1/rank/class?personId={my_uuid}{subject_param}&date={today}',
    headers = headers)
    return response.json()

def get_subjects(my_uuid, headers):
    response = requests.get(f'https://school.mos.ru/api/ej/rating/v1/rank/subjects?date={today}&personId={my_uuid}', headers=headers).json()
    return response

def mark_color(mark):
    rounded = round(mark) if mark is not None else 2
    if rounded >= 5:
        return GREEN
    if rounded == 4:
        return YELLOW
    if rounded == 3:
        return ORANGE
    return RED

def name_by_id(id, headers):
    cache = load_cache()
    if id in cache:
        return cache[id]
    response = requests.get(f'https://school.mos.ru/api/gamification/v1/profiles?personId={id}', headers=headers).json()
    name = response["firstName"] + " " + response["lastName"]
    cache[id] = name
    save_cache(cache)
    return name

def get_profile():
    response = requests.get('https://school.mos.ru/api/family/web/v1/profile', headers=headers)
    profile_data = response.json()
    return profile_data["profile"]["last_name"] + " " + profile_data["profile"]["first_name"], str(profile_data["children"][0]["id"]), profile_data["children"][0]["contingent_guid"]
    

def login():
    try:
        with open('school-mos-ru.json', 'r') as f:
            data = json.load(f)
            token = data["token"]
            profile_id = data["Profile-Id"]
            name = data["name"]
            my_uuid = data["contingent_guid"]
            headers["Authorization"] = f"Bearer {token}"
            headers["Profile-Id"] = profile_id
        print("Successfully loaded data from school-mos-ru.json!")
        return my_uuid
            
    except FileNotFoundError:
        token = input("Please go to https://school.mos.ru/v2/token/refresh?roleId=1&subsystem=2 and paste the token: ")
        headers["Authorization"] = f"Bearer {token}"
        name, profile_id, my_uuid = get_profile()
        headers["Profile-Id"] = profile_id
        data_to_jsonfile = {
            "token": token,
            "Profile-Id": profile_id,
            "name": name,
            "contingent_guid": my_uuid
        }
        with open("school-mos-ru.json", 'w') as f:
            json.dump(data_to_jsonfile, f, ensure_ascii=False, indent=4)
        print(f"Successfully registered as \"{name}\" and saved data!")
        return my_uuid

def choose_subject(my_uuid, headers):
    subjects = get_subjects(my_uuid, headers)
    subject_ids = [str(subject["subjectId"]) for subject in subjects]
    print("0. Общий рейтинг")
    for i, subject in enumerate(subjects, start=1):
        mark = subject["rank"]["averageMarkFive"]
        color = mark_color(mark)
        print(f"{color}{i}. {subject['subjectName']} - {mark}{RESET}")
    choice = input("Выберите предмет (0 для общего рейтинга): ")
    if choice == "0" or choice == "":
        return None
    return subject_ids[int(choice) - 1]

def main():
    my_uuid = login()
    subject = choose_subject(my_uuid, headers)
    rank_data = get_and_parse_rank(my_uuid, subject)
    p = 0
    try:
        for student in rank_data:
            stud_mark = rank_data[p]["rank"]["averageMarkFive"]
            p+=1
            stud_id = student["personId"]
            stud_name = name_by_id(stud_id, headers)
            print(f"{p}. {stud_name} - {stud_mark}")
    except KeyError:
        print("ERROR!!!", rank_data)
if __name__ == "__main__":
    main()
