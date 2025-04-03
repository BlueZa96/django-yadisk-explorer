import os
import logging
import requests
import urllib.parse
import zipfile
from io import BytesIO
from django.shortcuts import render
from django.http import JsonResponse, HttpResponse
from django.core.cache import cache
from django.conf import settings
from .yandex_api import get_files_from_public_link

logger = logging.getLogger(__name__)


def index(request):
    return render(request, 'index.html')


# Функции работы с файлами
def get_files(request):
    public_key, path = request.GET.get('public_key'), request.GET.get('path', '')
    if not public_key:
        return JsonResponse({'error': 'No public key provided'}, status=400)

    cache_key = f"yandex_files:{public_key}:{path}"
    if cached_data := cache.get(cache_key):
        logger.info(f"Загрузка из кэша: {cache_key}")
        return JsonResponse(cached_data)

    return fetch_and_cache_files(public_key, path, cache_key)


def fetch_and_cache_files(public_key, path, cache_key):
    files_data = get_files_from_public_link(public_key, path)
    if 'error' in files_data:
        return JsonResponse({'error': files_data['error']})

    response_data = parse_files_data(files_data)
    cache.set(cache_key, response_data, settings.CACHE_TTL)
    return JsonResponse(response_data)


def parse_files_data(files_data):
    available_extensions, file_list, folder_list = set(), [], []
    for item in files_data.get('_embedded', {}).get('items', []):
        process_item(item, file_list, folder_list, available_extensions)

    return {
        'files': file_list,
        'folders': folder_list,
        'current_folder': files_data.get("name"),
        'available_types': list(available_extensions)
    }


def process_item(item, file_list, folder_list, available_extensions):
    file_name, file_ext = item.get('name', 'Unknown'), os.path.splitext(item.get('name', ''))[-1].lower()
    is_folder, full_path = item.get('type') == 'dir', item.get('path', '')

    if is_folder:
        folder_list.append({'name': file_name, 'path': full_path})
    else:
        available_extensions.add(file_ext)
        file_list.append({'name': file_name, 'file': item.get('file'), 'extension': file_ext})


# Функции скачивания файлов
def download_file(request):
    file_url, file_name = request.GET.get('file_url'), request.GET.get('file_name')
    if not file_url or not file_name:
        return JsonResponse({'error': 'File URL and name are required'}, status=400)

    return proxy_file_download(file_url, file_name)


def proxy_file_download(file_url, file_name):
    response = requests.get(urllib.parse.unquote(file_url), stream=True)
    if response.status_code != 200:
        return JsonResponse({'error': 'Failed to download file'}, status=500)

    return create_http_response(response.content, file_name)


def create_http_response(content, file_name):
    resp = HttpResponse(content, content_type='application/octet-stream')
    resp['Content-Disposition'] = f'attachment; filename="{file_name}"'
    return resp


# Функции скачивания нескольких файлов и папок
def download_multiple_files(request):
    file_urls, file_names = request.GET.getlist('file_urls[]'), request.GET.getlist('file_names[]')
    if not validate_file_lists(file_urls, file_names):
        return JsonResponse({'error': 'Invalid file URLs or names'}, status=400)

    return create_zip_response(file_urls, file_names, "downloaded_files.zip")


def download_folders(request):
    public_key, folder_paths, folder_names = request.GET.get('public_key'), request.GET.getlist(
        'folder_paths[]'), request.GET.getlist('folder_names[]')
    file_urls, file_names = request.GET.getlist('file_urls[]'), request.GET.getlist('file_names[]')

    if not public_key:
        return JsonResponse({'error': 'Public key is required'}, status=400)
    if not folder_paths and not file_urls:
        return JsonResponse({'error': 'No folders or files selected'}, status=400)

    return create_zip_response(file_urls, file_names, "downloaded_items.zip", public_key, folder_paths, folder_names)


def validate_file_lists(file_urls, file_names):
    return bool(file_urls and file_names and len(file_urls) == len(file_names))


def create_zip_response(file_urls, file_names, zip_name, public_key=None, folder_paths=None, folder_names=None):
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        add_files_to_zip(zip_file, file_urls, file_names)
        if public_key and folder_paths and folder_names:
            add_folders_to_zip(zip_file, public_key, folder_paths, folder_names)

    zip_buffer.seek(0)
    return create_http_response(zip_buffer.read(), zip_name)


def add_files_to_zip(zip_file, file_urls, file_names):
    for file_url, file_name in zip(file_urls, file_names):
        download_and_write_zip(zip_file, file_url, file_name)


def download_and_write_zip(zip_file, file_url, file_name):
    response = requests.get(urllib.parse.unquote(file_url), stream=True)
    if response.status_code == 200:
        zip_file.writestr(file_name, response.content)


def add_folders_to_zip(zip_file, public_key, folder_paths, folder_names):
    for folder_path, folder_name in zip(folder_paths, folder_names):
        add_folder_to_zip(zip_file, public_key, folder_path, folder_name)


def add_folder_to_zip(zip_file, public_key, folder_path, folder_name):
    folder_data = get_files_from_public_link(public_key, folder_path)
    if 'error' in folder_data:
        return

    add_folder_contents_to_zip(zip_file, public_key, folder_data, folder_name + "/")


def add_folder_contents_to_zip(zip_file, public_key, folder_data, parent_prefix):
    for item in folder_data.get('_embedded', {}).get('items', []):
        process_folder_item(zip_file, public_key, item, parent_prefix)


def process_folder_item(zip_file, public_key, item, parent_prefix):
    if item.get('type') == 'dir':
        add_folder_to_zip(zip_file, public_key, item.get('path', ''), parent_prefix + item.get('name', ''))
    elif 'file' in item:
        download_and_write_zip(zip_file, item.get('file'), parent_prefix + item.get('name', 'unnamed_file'))