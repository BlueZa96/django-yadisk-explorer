import environ
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath((__file__))))

env = environ.Env()
environ.Env.read_env(os.path.join(BASE_DIR, '.env'))

class ConfigManager:
    def __init__(self):
        self.env = env
        self.config = {}

    def get(self, key, default=None, cast_type=str):
        """
        Получаем переменную окружения с автоматическим преобразованием типа.
        Если переменная не найдена, возвращаем значение по умолчанию.
        """
        if key not in self.config:
            if cast_type == bool:
                self.config[key] = self.env.bool(key, default=default)
            elif cast_type == int:
                self.config[key] = self.env.int(key, default=default)
            elif cast_type == float:
                self.config[key] = self.env.float(key, default=default)
            elif cast_type == list:
                self.config[key] = self.env.list(key, default=default)
            else:
                self.config[key] = self.env.str(key, default=default)
        return self.config[key]
