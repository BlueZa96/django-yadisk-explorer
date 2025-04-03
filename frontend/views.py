import os
import logging
import requests
import urllib.parse
from django.shortcuts import render
from django.http import JsonResponse, HttpResponse
from django.core.cache import cache
from django.conf import settings
from .yandex_api import get_files_from_public_link
import zipfile
from io import BytesIO

logger = logging.getLogger(__name__)


def index(request):
    """
    Главная страница, где будет запрашиваться публичная ссылка для файлов.
    """
    return render(request, 'index.html')


def get_files(request):
    """
    Получение файлов и папок с Яндекс.Диска по публичной ссылке.
    """
    public_key = request.GET.get('public_key')
    path = request.GET.get('path', '')  # Путь к папке
    if not public_key:
        return JsonResponse({'error': 'No public key provided'}, status=400)

    cache_key = f"yandex_files:{public_key}:{path}"
    cached_data = cache.get(cache_key)
    if cached_data:
        logger.info(f"Загрузка из кэша: {cache_key}")
        return JsonResponse(cached_data)

    files_data = get_files_from_public_link(public_key, path)
    if 'error' in files_data:
        return JsonResponse({'error': files_data['error']})

    available_extensions = set()
    file_list = []
    folder_list = []
    current_folder = files_data["name"]

    if '_embedded' in files_data and 'items' in files_data['_embedded']:
        for item in files_data['_embedded']['items']:
            file_name = item.get('name', 'Unknown')
            file_ext = os.path.splitext(file_name)[-1].lower()
            is_folder = item.get('type') == 'dir'
            full_path = item.get('path', '')

            if is_folder:
                folder_list.append({'name': file_name, 'path': full_path})
            else:
                if file_ext:
                    available_extensions.add(file_ext)
                file_list.append({
                    'name': file_name,
                    'file': item.get('file', None),
                    'extension': file_ext
                })

    response_data = {
        'files': file_list,
        'folders': folder_list,
        'current_folder': current_folder,
        'available_types': list(available_extensions)
    }

    cache.set(cache_key, response_data, settings.CACHE_TTL)
    return JsonResponse(response_data)


def download_file(request):
    """
    Проксирование скачивания файла с Яндекс.Диска напрямую в браузер.
    """
    file_url = request.GET.get('file_url')
    file_name = request.GET.get('file_name')

    if not file_url or not file_name:
        return JsonResponse({'error': 'File URL and name are required'}, status=400)

    decoded_url = urllib.parse.unquote(file_url)
    response = requests.get(decoded_url, stream=True)

    if response.status_code != 200:
        return JsonResponse({'error': 'Failed to download file'}, status=500)

    # Проксируем скачивание файла в браузер
    resp = HttpResponse(response.content, content_type=response.headers.get('Content-Type', 'application/octet-stream'))
    resp['Content-Disposition'] = f'attachment; filename="{file_name}"'
    return resp


def download_multiple_files(request):
    """
    Скачивание нескольких файлов в формате ZIP.
    """
    file_urls = request.GET.getlist('file_urls[]')
    file_names = request.GET.getlist('file_names[]')

    if not file_urls or not file_names or len(file_urls) != len(file_names):
        return JsonResponse({'error': 'Invalid file URLs or names'}, status=400)

    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for file_url, file_name in zip(file_urls, file_names):
            decoded_url = urllib.parse.unquote(file_url)
            response = requests.get(decoded_url, stream=True)
            if response.status_code == 200:
                file_data = response.content
                zip_file.writestr(file_name, file_data)

    zip_buffer.seek(0)
    response = HttpResponse(zip_buffer.read(), content_type='application/zip')
    response['Content-Disposition'] = 'attachment; filename="downloaded_files.zip"'
    return response


def download_folders(request):
    """
    Скачивание папок и файлов в формате ZIP.
    """
    public_key = request.GET.get('public_key')
    folder_paths = request.GET.getlist('folder_paths[]')
    folder_names = request.GET.getlist('folder_names[]')
    file_urls = request.GET.getlist('file_urls[]')
    file_names = request.GET.getlist('file_names[]')

    if not public_key:
        return JsonResponse({'error': 'Public key is required'}, status=400)

    if not folder_paths and not file_urls:
        return JsonResponse({'error': 'No folders or files selected'}, status=400)

    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        # Добавление отдельных файлов
        if file_urls and file_names:
            for file_url, file_name in zip(file_urls, file_names):
                decoded_url = urllib.parse.unquote(file_url)
                response = requests.get(decoded_url, stream=True)
                if response.status_code == 200:
                    file_data = response.content
                    zip_file.writestr(file_name, file_data)

        # Добавление папок
        if folder_paths and folder_names:
            for folder_path, folder_name in zip(folder_paths, folder_names):
                # Получаем содержимое папки
                folder_data = get_files_from_public_link(public_key, folder_path)

                if 'error' in folder_data:
                    continue

                if '_embedded' in folder_data and 'items' in folder_data['_embedded']:
                    folder_prefix = folder_name + "/"

                    # Добавляем файлы из этой папки
                    for item in folder_data['_embedded']['items']:
                        if item.get('type') != 'dir' and 'file' in item:
                            file_url = item.get('file')
                            file_name = item.get('name', 'unnamed_file')
                            file_path = folder_prefix + file_name

                            response = requests.get(file_url, stream=True)
                            if response.status_code == 200:
                                file_data = response.content
                                zip_file.writestr(file_path, file_data)

                    # Рекурсивно добавляем подпапки
                    _add_subfolders_to_zip(zip_file, public_key, folder_data, folder_prefix)

    zip_buffer.seek(0)
    response = HttpResponse(zip_buffer.read(), content_type='application/zip')
    response['Content-Disposition'] = 'attachment; filename="downloaded_items.zip"'
    return response


def _add_subfolders_to_zip(zip_file, public_key, parent_folder_data, parent_prefix):
    """
    Рекурсивно добавляет подпапки и их содержимое в ZIP-архив.
    """
    if '_embedded' in parent_folder_data and 'items' in parent_folder_data['_embedded']:
        for item in parent_folder_data['_embedded']['items']:
            if item.get('type') == 'dir':
                subfolder_path = item.get('path', '')
                subfolder_name = item.get('name', 'unnamed_folder')
                subfolder_prefix = parent_prefix + subfolder_name + "/"

                # Получаем содержимое подпапки
                subfolder_data = get_files_from_public_link(public_key, subfolder_path)

                if 'error' in subfolder_data:
                    continue

                if '_embedded' in subfolder_data and 'items' in subfolder_data['_embedded']:
                    # Добавляем файлы из подпапки
                    for subitem in subfolder_data['_embedded']['items']:
                        if subitem.get('type') != 'dir' and 'file' in subitem:
                            file_url = subitem.get('file')
                            file_name = subitem.get('name', 'unnamed_file')
                            file_path = subfolder_prefix + file_name

                            response = requests.get(file_url, stream=True)
                            if response.status_code == 200:
                                file_data = response.content
                                zip_file.writestr(file_path, file_data)

                    # Рекурсивно добавляем подпапки подпапок
                    _add_subfolders_to_zip(zip_file, public_key, subfolder_data, subfolder_prefix)