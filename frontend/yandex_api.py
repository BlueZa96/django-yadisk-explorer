import requests
from typing import Dict, Any, Optional
from app.config_manager import ConfigManager

config = ConfigManager()
YANDEX_API_BASE_URL=config.get('YANDEX_API_BASE_URL')

def get_files_from_public_link(public_key: str, path: Optional[str] = None) -> Dict[str, Any]:
    """Получает список файлов по публичной ссылке Яндекс.Диска."""
    response = requests.get(YANDEX_API_BASE_URL, params={'public_key': public_key, **({'path': path} if path else {})})

    if response.status_code == 200:
        return response.json()

    return {
        "error": f"Ошибка API Яндекс.Диска: {response.status_code} - {response.json().get('message', 'Неизвестная ошибка')}"}