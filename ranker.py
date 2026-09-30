import json
from datetime import date

import requests


class MosSchoolClient:
    BASE_URL = "https://school.mos.ru"
    RANK_URL = "/api/ej/rating/v1/rank/class"
    SUBJECTS_URL = "/api/ej/rating/v1/rank/subjects"
    PROFILE_URL = "/api/family/web/v1/profile"
    PROFILE_BY_ID_URL = "/api/gamification/v1/profiles"

    ROLE_ID = "1"
    SUBSYSTEM = "familyweb"
    PROFILE_TYPE = "student"
    TIMEOUT = 15

    AUTH_FILE = "school-mos-ru.json"
    CACHE_FILE = "users_cache.json"

    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    ORANGE = "\033[38;5;208m"
    RED = "\033[91m"
    RESET = "\033[0m"

    def __init__(self):
        self.today = date.today().isoformat()
        self.my_uuid = None
        self.users_cache = {}
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "ru-US,ru;q=0.9",
            "Connection": "keep-alive",
            "Content-Type": "application/json;charset=UTF-8",
            "Profile-Type": self.PROFILE_TYPE,
            "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Mobile Safari/537.36",
            "X-Mes-RoleId": self.ROLE_ID,
            "X-mes-subsystem": self.SUBSYSTEM
        })

    def _get(self, path, params=None):
        """Выполняет GET-запрос и возвращает разобранный JSON."""
        response = self.session.get(self.BASE_URL + path, params=params, timeout=self.TIMEOUT)
        response.raise_for_status()
        return response.json()

    def load_cached_auth(self):
        """Читает сохранённую авторизацию и возвращает uuid ученика."""
        try:
            with open(self.AUTH_FILE, 'r') as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return None
        self._apply_auth(data["token"], data["Profile-Id"])
        print(f"Данные загружены из {self.AUTH_FILE}")
        return data["contingent_guid"]

    def refresh_auth(self, token):
        """Обновляет авторизацию по токену, сохраняет её и возвращает uuid."""
        self.session.headers["Authorization"] = f"Bearer {token}"
        profile = self._get(self.PROFILE_URL)
        name = profile["profile"]["last_name"] + " " + profile["profile"]["first_name"]
        child = profile["children"][0]
        profile_id = str(child["id"])
        my_uuid = child["contingent_guid"]
        self._apply_auth(token, profile_id)
        data_to_jsonfile = {
            "token": token,
            "Profile-Id": profile_id,
            "name": name,
            "contingent_guid": my_uuid,
        }
        with open(self.AUTH_FILE, 'w') as f:
            json.dump(data_to_jsonfile, f, ensure_ascii=False, indent=4)
        print(f"Успешный вход как \"{name}\", данные сохранены!")
        return my_uuid

    def login(self):
        """Загружает сохранённую авторизацию или запрашивает токен у пользователя."""
        my_uuid = self.load_cached_auth()
        if my_uuid:
            return my_uuid
        token = input("Перейдите на https://school.mos.ru/v2/token/refresh?roleId=1&subsystem=2 и вставьте токен: ")
        return self.refresh_auth(token)

    def _apply_auth(self, token, profile_id):
        self.session.headers["Authorization"] = f"Bearer {token}"
        self.session.headers["Profile-Id"] = profile_id

    def load_cache(self):
        """Загружает кэш имён учеников."""
        try:
            with open(self.CACHE_FILE, 'r') as f:
                cache = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self.users_cache = {}
            return
        self.users_cache = cache["users"] if "users" in cache else cache

    def flush_cache(self):
        """Сохраняет кэш имён учеников на диск."""
        with open(self.CACHE_FILE, 'w') as f:
            json.dump(self.users_cache, f, ensure_ascii=False, indent=4)

    def get_name(self, person_id):
        """Возвращает имя ученика, используя кэш при наличии."""
        if person_id in self.users_cache:
            return self.users_cache[person_id]
        data = self._get(self.PROFILE_BY_ID_URL, params={"personId": person_id})
        name = data["firstName"] + " " + data["lastName"]
        self.users_cache[person_id] = name
        return name

    def get_subjects(self):
        """Возвращает список предметов с оценками ученика."""
        return self._get(self.SUBJECTS_URL, params={"date": self.today, "personId": self.my_uuid})

    def get_rank(self, subject_id=None):
        """Возвращает рейтинг класса, при наличии — по конкретному предмету."""
        params = {"personId": self.my_uuid, "date": self.today}
        if subject_id:
            params["subjectId"] = subject_id
        return self._get(self.RANK_URL, params=params)

    def mark_color(self, mark):
        """Возвращает ANSI-цвет для средней оценки или None, если оценки нет."""
        if mark is None:
            return None
        rounded = round(mark)
        if rounded >= 5:
            return self.GREEN
        if rounded == 4:
            return self.YELLOW
        if rounded == 3:
            return self.ORANGE
        return self.RED

    def choose_subjects(self):
        """Показывает предметы и возвращает список выбранных пар (id, название)."""
        subjects = self.get_subjects()
        subject_ids = [str(subject["subjectId"]) for subject in subjects]
        subject_names = [subject["subjectName"] for subject in subjects]
        print("0. Общий рейтинг")
        for index, subject in enumerate(subjects, start=1):
            mark = subject["rank"]["averageMarkFive"]
            mark_text = "—" if mark is None else mark
            color = self.mark_color(mark)
            if color is None:
                print(f"{index}. {subject['subjectName']} - {mark_text}")
            else:
                print(f"{color}{index}. {subject['subjectName']} - {mark_text}{self.RESET}")
        while True:
            choice = input("Выберите предметы через пробел (0 для общего рейтинга): ").strip()
            if choice == "":
                return [(None, "Общий рейтинг")]
            try:
                numbers = [int(number) for number in choice.split()]
            except ValueError:
                print("Введите числа через пробел.")
                continue
            if any(number < 0 or number > len(subject_ids) for number in numbers):
                print(f"Введите числа от 0 до {len(subject_ids)}.")
                continue
            return [
                (None, "Общий рейтинг") if number == 0 else (subject_ids[number - 1], subject_names[number - 1])
                for number in numbers
            ]

    def print_rank(self, subject_name, rank_data):
        """Печатает рейтинг класса по предмету."""
        print(f"=== {subject_name} ===")
        for place, student in enumerate(rank_data, start=1):
            mark = student["rank"]["averageMarkFive"]
            name = self.get_name(student["personId"])
            print(f"{place}. {name} - {mark}")
        print()

    def run(self):
        """Точка входа: авторизация, выбор предмета и вывод рейтинга."""
        self.my_uuid = self.login()
        self.load_cache()
        try:
            selections = self.choose_subjects()
            for subject_id, subject_name in selections:
                rank_data = self.get_rank(subject_id)
                self.print_rank(subject_name, rank_data)
        except requests.RequestException as error:
            print(f"Ошибка HTTP-запроса: {error}")
        except (KeyError, TypeError, ValueError) as error:
            print(f"Ошибка обработки данных: {error}")
        finally:
            self.flush_cache()


if __name__ == "__main__":
    MosSchoolClient().run()
