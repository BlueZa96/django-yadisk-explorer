

    const state = {
        files: [],
        folders: [],
        currentPath: "",
        currentFolder: "Главная"
    };

    const fileIcons = {
        ".pdf": "📄", ".doc": "📝", ".docx": "📝", ".xls": "📊",
        ".xlsx": "📊", ".ppt": "📑", ".pptx": "📑", ".txt": "📄",
        ".jpg": "🖼️", ".jpeg": "🖼️", ".png": "🖼️", ".gif": "🖼️",
        ".zip": "📦", ".rar": "📦", ".mp3": "🎵", ".mp4": "🎬",
        ".avi": "🎬", ".mov": "🎬", "default": "📄"
    };

    const getFileIcon = (ext) => fileIcons[ext.toLowerCase()] || fileIcons["default"];

    function fetchFiles(path = "") {
        const publicKey = document.getElementById('public_key').value;
        if (!publicKey) return alert("Введите публичную ссылку!");

        fetch(`/get_files/?public_key=${publicKey}&path=${encodeURIComponent(path)}`)
            .then(res => res.json())
            .then(data => {
                if (data.error) return alert(data.error);

                Object.assign(state, {
                    files: data.files,
                    folders: data.folders,
                    currentPath: path,
                    currentFolder: data.current_folder
                });

                updateUI();
            })
            .catch(console.error);
    }

    function updateUI() {
        updateNavigation();
        updateFileExplorer();
        updateFileTypeFilter();
        toggleUIElements(true);
    }

    function updateNavigation() {
        const nav = document.getElementById('current_folder');
        const pathComponents = state.currentPath.split('/').filter(Boolean);
        let accumulatedPath = '';
        
        nav.innerHTML = `<a href="#" onclick="fetchFiles('')">Главная</a>` +
            pathComponents.map((component, index) => {
                accumulatedPath += `/${component}`;
                return `<span>/</span> ${index < pathComponents.length - 1 ? `<a href="#" onclick="fetchFiles('${accumulatedPath}')">${component}</a>` : `<strong>${component}</strong>`}`;
            }).join('');
    }

    function updateFileExplorer() {
        const explorerItems = document.getElementById('explorer-items');
        explorerItems.innerHTML = '';

        if (state.currentPath) addNavigationButtons(explorerItems);
        state.folders.forEach(addFolderItem.bind(null, explorerItems));
        state.files.length ? state.files.forEach(addFileItem.bind(null, explorerItems)) : addEmptyFolderMessage(explorerItems);
    }

    function addNavigationButtons(container) {
        container.innerHTML += `
            <div><a href="#" class="list-group-item d-flex align-items-center flex-grow-1" onclick="fetchFiles('')">⬆ В начало</a></div>
            <div><a href="#" class="list-group-item d-flex align-items-center flex-grow-1" onclick="fetchFiles('${state.currentPath.substring(0, state.currentPath.lastIndexOf('/'))}')">⬅ Назад</a></div>
        `;
    }

    function addFolderItem(container, folder) {
        container.innerHTML += `
            <div class="list-group-item d-flex align-items-center flex-grow-1">
                <input type="checkbox" value="${folder.path}" data-name="${folder.name}" data-type="folder" class="item-checkbox folder-checkbox me-2">
                <a href="#" onclick="fetchFiles('${folder.path}')">📁 ${folder.name}</a>
            </div>
        `;
    }

    function addFileItem(container, file) {
        container.innerHTML += `
            <div class="list-group-item d-flex align-items-center flex-grow-1">
                <input type="checkbox" value="${file.file}" data-name="${file.name}" data-type="file" class="item-checkbox folder-checkbox me-2">
                <span>${getFileIcon(file.extension)} ${file.name}</span>
                ${file.file ? `<a class="ms-2 btn btn-sm btn-outline-primary download-link" 
                    onclick="downloadFile('${file.file}', '${file.name}')">Скачать</a>` : `<span>Нет ссылки</span>`}
            </div>
        `;
    }

    function addEmptyFolderMessage(container) {
        if (!state.folders.length) container.innerHTML += '<div>Папка пуста</div>';
    }

    function updateFileTypeFilter() {
        const typeSelect = document.getElementById('file_type');
        typeSelect.innerHTML = '<option value="">Все</option>' +
            [...new Set(state.files.map(f => f.extension))].filter(Boolean).map(ext => `<option value="${ext}">${ext}</option>`).join('');
    }

    function toggleUIElements(show) {
        ['file-type-filter', 'download-buttons', 'current_folder'].forEach(id => document.getElementById(id).style.display = show ? 'block' : 'none');
    }

    function downloadFile(url, name) {
        if (!url) return alert("Файл не доступен для скачивания!");
        window.location.href = `/download/?file_url=${encodeURIComponent(url)}&file_name=${encodeURIComponent(name)}`;
    }

    function downloadSelectedItems() {
        const selectedFiles = [...document.querySelectorAll('.file-checkbox:checked')].map(cb => ({ url: cb.value, name: cb.dataset.name }));
        const selectedFolders = [...document.querySelectorAll('.folder-checkbox:checked')].map(cb => ({ path: cb.value, name: cb.dataset.name }));
        
        if (!selectedFiles.length && !selectedFolders.length) return alert("Выберите файлы или папки для скачивания!");

        let url = new URL(selectedFolders.length ? '/download_folders/' : '/download_multiple/', window.location.origin);
        url.searchParams.append('public_key', document.getElementById('public_key').value);

        selectedFolders.forEach(({ path, name }) => {
            url.searchParams.append('folder_paths[]', path);
            url.searchParams.append('folder_names[]', name);
        });
        selectedFiles.forEach(({ url: fileUrl, name }) => {
            url.searchParams.append('file_urls[]', fileUrl);
            url.searchParams.append('file_names[]', name);
        });

        window.location.href = url.href;
    }

    function clearSelection() {
        document.querySelectorAll('.item-checkbox').forEach(checkbox => {
            checkbox.checked = false;
        });
    }

    function selectAllItems() {
        document.querySelectorAll('.item-checkbox').forEach(checkbox => {
            checkbox.checked = true;
        });
    }

