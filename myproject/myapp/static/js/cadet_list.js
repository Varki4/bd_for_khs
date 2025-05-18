// Глобальные переменные
let currentFile = null;
window.currentDocuments = {};
window.newCadetDocuments = {};

// Глобальные переменные для фильтра классов
let selectedGrades = new Set();
let availableGrades = new Set();

// Функция для получения CSRF токена
function getCSRFToken() {
    return document.querySelector('meta[name="csrf-token"]').getAttribute('content');
}

// Функция загрузки списка кадет
function loadCadetList() {
    fetch('/cadets/', {
        headers: {
            'X-Requested-With': 'XMLHttpRequest',
            'X-CSRFToken': getCSRFToken()
        }
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.text();
    })
    .then(html => {
        const tableBody = document.querySelector('tbody');
        if (tableBody) {
            tableBody.innerHTML = html;
            initializeEventHandlers();
        } else {
            console.error('Table body element not found');
        }
    })
    .catch(error => {
        console.error('Error loading cadet list:', error);
    });
}

// Вызываем загрузку списка при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
    loadCadetList();
    initGradeFilter();
});

// Функция очистки превью
function clearPreviews() {
    const previews = document.querySelectorAll('.preview-content');
    previews.forEach(preview => {
        preview.innerHTML = '';
    });
    currentFile = null;
    window.currentDocuments = {};
    window.newCadetDocuments = {};
}

// Глобальные функции модальных окон
window.openModal = function(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        document.body.style.overflow = 'hidden';
        modal.style.display = 'flex';
        // Даем браузеру время на применение display: flex
        setTimeout(() => {
            modal.classList.add('show');
        }, 10);
    }
};

window.closeModal = function(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        document.body.style.overflow = '';
        modal.classList.remove('show');
        // Ждем окончания анимации перед скрытием модального окна
        setTimeout(() => {
            modal.style.display = 'none';
        }, 300);
    }
};

window.openAddModal = function() {
    window.openModal("addModal");
};

window.closeAddModal = function() {
    window.closeModal("addModal");
    clearPreviews();
};

// Обновляем функцию открытия окна редактирования
function openEditModal(button) {
    console.log('Вызвана функция openEditModal');
    
    if (!button || !button.dataset) {
        console.error('Кнопка или её данные отсутствуют:', button);
        return;
    }
    
    const modal = document.getElementById('editModal');
    const form = document.getElementById('editForm');
    
    if (!modal || !form) {
        console.error('Модальное окно или форма не найдены');
        return;
    }
    
    try {
        // Заполняем поля формы
        const fields = {
            'editFullName': button.dataset.full_name,
            'editGrade': button.dataset.grade || '',
            'editBirthDate': button.dataset.birth_date,
            'editPersonalInfo': button.dataset.personal_info || '',
            'editAchievements': button.dataset.achievements,
            'editReprimands': button.dataset.reprimands
        };
        
        // Заполняем поля формы
        for (const [id, value] of Object.entries(fields)) {
            const element = document.getElementById(id);
            if (element) {
                element.value = value || '';
            }
        }
        
        // Устанавливаем action формы и data-cadet-id
        const cadetId = button.dataset.id;
        if (!cadetId) {
            console.error('ID кадета не найден');
            return;
        }
        
        form.action = `/edit-cadet/${cadetId}/?next=/cadets/`;
        form.setAttribute('data-cadet-id', cadetId);
        
        // Открываем модальное окно
        window.openModal('editModal');
    } catch (error) {
        console.error('Ошибка при открытии модального окна:', error);
    }
}

// Делаем функцию доступной глобально
window.openEditModal = openEditModal;

window.closeEditModal = function() {
    window.closeModal("editModal");
    clearPreviews();
};

window.openDeleteModal = function(button) {
    const id = button.getAttribute('data-id');
    const form = document.getElementById("deleteForm");
    if (form) {
        form.action = `/delete-cadet/${id}/?next=/cadet_list/`;
        window.openModal("deleteModal");
    }
};

window.closeDeleteModal = function() {
    window.closeModal("deleteModal");
};

// Обновляем обработчик загрузки документа
document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM loaded');
    
    const editModal = document.getElementById("editModal");
    const editForm = editModal?.querySelector("#editForm");
    
    if (!editModal || !editForm) {
        console.error('Required elements not found');
    }

    const fileInput = document.getElementById('docUpload');
    if (fileInput) {
        fileInput.addEventListener('change', function(e) {
            if (this.files.length) {
                currentFile = this.files[0];
                window.openModal("docTypeModal"); // Открываем окно выбора типа
            }
        });
    }

    // Добавляем обработчик для крестика закрытия
    const closeButtons = document.querySelectorAll('.close');
    closeButtons.forEach(button => {
        button.addEventListener('click', function() {
            const modal = this.closest('.modal');
            if (modal.id === 'docTypeModal') {
                window.closeDocTypeModal();
            }
        });
    });
});

// Добавляем функцию просмотра документа
function viewDocument(type, isAdd = false) {
    const documents = isAdd ? window.newCadetDocuments : window.currentDocuments;
    const doc = isAdd ? documents[type] : documents[document.getElementById('editForm').getAttribute('data-cadet-id')]?.[type];
    
    if (doc && doc.data) {
        const win = window.open("", "_blank");
        win.document.write(`
            <html>
                <head>
                    <title>${doc.name}</title>
                    <style>
                        body {
                            margin: 0;
                            display: flex;
                            flex-direction: column;
                            align-items: center;
                            min-height: 100vh;
                            background: #1a1a1a;
                        }
                        img {
                            max-width: 90%;
                            max-height: 80vh;
                            object-fit: contain;
                            margin-top: 20px;
                        }
                    </style>
                </head>
                <body>
                    <img src="data:image/jpeg;base64,${doc.data}">
                </body>
            </html>
        `);
    }
}

function liveSearch(input) {
    const searchQuery = input.value.trim();
    
    // Отменяем предыдущий запрос, если он есть
    if (window.searchTimeout) {
        clearTimeout(window.searchTimeout);
    }
    
    // Добавляем небольшую задержку перед отправкой запроса
    window.searchTimeout = setTimeout(() => {
        fetch(`/cadets/?q=${encodeURIComponent(searchQuery)}`, {
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': getCSRFToken()
            }
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.text();
        })
        .then(html => {
            const tableBody = document.querySelector('tbody');
            if (tableBody) {
                tableBody.innerHTML = html;
                // Переинициализируем обработчики событий для новых кнопок
                initializeEventHandlers();
            } else {
                console.error('Table body element not found');
            }
        })
        .catch(error => {
            console.error('Error during search:', error);
        });
    }, 300); // Задержка в 300 мс
}

// Функция для инициализации обработчиков событий
function initializeEventHandlers() {
    // Инициализируем обработчики для кнопок редактирования
    document.querySelectorAll('.edit-btn').forEach(button => {
        button.removeEventListener('click', handleEditClick);
        button.addEventListener('click', handleEditClick);
    });

    // Инициализируем обработчики для кнопок удаления
    document.querySelectorAll('.delete-btn').forEach(button => {
        button.removeEventListener('click', handleDeleteClick);
        button.addEventListener('click', handleDeleteClick);
    });
}

// Выносим обработчики в отдельные функции
function handleEditClick(e) {
    e.preventDefault();
    window.openEditModal(this);
}

function handleDeleteClick(e) {
    e.preventDefault();
    window.openDeleteModal(this);
}

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
    const searchInput = document.querySelector('.search-input');
    if (searchInput) {
        // Удаляем старый обработчик перед добавлением нового
        searchInput.removeEventListener('input', handleSearchInput);
        searchInput.addEventListener('input', handleSearchInput);
    }
    
    // Инициализируем обработчики событий при загрузке страницы
    initializeEventHandlers();
});

// Выносим обработчик поиска в отдельную функцию
function handleSearchInput() {
    liveSearch(this);
}

// Обновляем функцию showDocument
function showDocument(name, base64Data) {
    if (!base64Data) return;
    
    const win = window.open("", "_blank");
    win.document.write(`
        <html>
            <head>
                <title>${name}</title>
                <style>
                    body {
                        margin: 0;
                        display: flex;
                        justify-content: center;
                        align-items: center;
                        min-height: 100vh;
                        background: #1a1a1a;
                    }
                    img {
                        max-width: 100%;
                        max-height: 100vh;
                        object-fit: contain;
                    }
                    .download-btn {
                        position: fixed;
                        top: 20px;
                        right: 20px;
                        padding: 10px 20px;
                        background: #4299e1;
                        color: white;
                        text-decoration: none;
                        border-radius: 4px;
                        font-size: 16px;
                    }
                </style>
            </head>
            <body>
                <img src="data:image/jpeg;base64,${base64Data}">
                <a href="data:image/jpeg;base64,${base64Data}" 
                   download="${name}.jpg" 
                   class="download-btn">
                    Скачать
                </a>
            </body>
        </html>
    `);
}

function handleDragOver(e) {
    e.preventDefault();
    e.stopPropagation();
    e.currentTarget.classList.add('dragover');
}

function handleDragLeave(e) {
    e.preventDefault();
    e.stopPropagation();
    e.currentTarget.classList.remove('dragover');
}

function handleDrop(e) {
    e.preventDefault();
    e.stopPropagation();
    e.currentTarget.classList.remove('dragover');
    
    const files = e.dataTransfer.files;
    if (files.length) {
        const input = e.currentTarget.querySelector('input[type="file"]');
        input.files = files;
        handleFileSelect(input);
    }
}

function handleFileSelect(input) {
    const file = input.files[0];
    if (file) {
        const uploadArea = input.closest('.document-upload-area');
        const message = uploadArea.querySelector('.upload-message');
        message.innerHTML = `<i class="fas fa-check"></i><br>${file.name}`;
    }
}

// Добавляем обработчики событий
document.querySelectorAll('.document-upload-area').forEach(area => {
    area.addEventListener('dragover', handleDragOver);
    area.addEventListener('dragleave', handleDragLeave);
    area.addEventListener('drop', handleDrop);
});

function assignDocument(type) {
    if (!currentFile) {
        console.error('No file selected');
        return;
    }

    const cadetId = document.getElementById('editForm').getAttribute('data-cadet-id');
    if (!window.currentDocuments) {
        window.currentDocuments = {};
    }
    if (!window.currentDocuments[cadetId]) {
        window.currentDocuments[cadetId] = {};
    }

    const formData = new FormData();
    formData.append('file', currentFile);
    formData.append('doc_type', type);
    formData.append('cadet_id', cadetId);

    fetch('/upload-document/', {
        method: 'POST',
        body: formData,
        headers: {
            'X-CSRFToken': getCSRFToken()
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            // Обновляем превью документа
            const preview = document.querySelector(`#${type}Doc .preview-content`);
            if (preview) {
                const reader = new FileReader();
                reader.onload = function(e) {
                    if (currentFile.type.startsWith('image/')) {
                        preview.innerHTML = `<img src="${e.target.result}" alt="${type} preview" class="doc-preview">`;
                    } else {
                        preview.innerHTML = `<div class="doc-info">${currentFile.name}</div>`;
                    }
                };
                reader.readAsDataURL(currentFile);
            }
            
            // Сохраняем информацию о документе
            window.currentDocuments[cadetId][type] = {
                name: currentFile.name,
                type: currentFile.type,
                url: data.document.url
            };

            window.closeModal("docTypeModal");
            currentFile = null;
        } else {
            throw new Error(data.message || 'Ошибка при загрузке документа');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Ошибка при загрузке документа: ' + error.message);
    });
}

// Обработчики для кнопок выбора типа документа
document.addEventListener('DOMContentLoaded', function() {
    const docTypeButtons = document.querySelectorAll('.doc-type-buttons button');
    docTypeButtons.forEach(button => {
        button.onclick = function(e) {
            e.preventDefault();
            const type = this.getAttribute('onclick')?.match(/['"]([^'"]+)['"]/)?.[1];
            if (type) {
                assignDocument(type);
            }
            return false;
        };
    });
});

// Обработка загрузки документа для редактирования
function handleDocumentUpload(input) {
    if (input.files && input.files[0]) {
        currentFile = input.files[0];
        const docTypeModal = document.getElementById('docTypeModal');
        docTypeModal.setAttribute('data-mode', 'edit');
        window.openModal("docTypeModal");
    }
}

// Обработчик формы добавления
document.querySelector('#addModal form')?.addEventListener('submit', function(e) {
    e.preventDefault();
    
    const formData = new FormData(this);
    
    // Добавляем основные поля
    formData.append('full_name', document.getElementById('full_name').value);
    formData.append('birth_date', document.getElementById('birth_date').value);
    formData.append('achievements', document.getElementById('achievements').value);
    formData.append('reprimands', document.getElementById('reprimands').value);
    
    // Добавляем документы в FormData
    if (window.newCadetDocuments) {
        Object.entries(window.newCadetDocuments).forEach(([type, doc]) => {
            if (doc.file) {
                // Добавляем файл напрямую, без преобразования
                formData.append(type, doc.file); // Изменено имя поля
                formData.append(`${type}_metadata`, JSON.stringify({
                    timestamp: new Date().toISOString(),
                    fileType: doc.file.type,
                    fileSize: doc.file.size,
                    filename: doc.file.name,
                    documentType: type
                }));
            }
        });
    }

    // Отправляем запрос
    fetch(this.action, {
        method: 'POST',
        body: formData,
        headers: {
            'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
        }
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.text();
    })
    .then(text => {
        try {
            const data = JSON.parse(text);
            if (data.status === 'success') {
                window.location.reload();
            } else {
                throw new Error(data.message || 'Ошибка при сохранении');
            }
        } catch (e) {
            if (text.includes('<!DOCTYPE html>')) {
                // Успешное добавление
                window.location.reload();
            } else {
                throw new Error('Неверный формат ответа от сервера');
            }
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Ошибка при сохранении: ' + error.message);
    });
});

// Обновляем функцию удаления документа
function removeDocument(type) {
    const form = document.getElementById('editForm');
    const cadetId = form.getAttribute('data-cadet-id');
    
    fetch(`/delete-cadet-document/${cadetId}/${type}/`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
    }})
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            const preview = document.querySelector(`#${type}Doc .preview-content`);
            if (preview) {
                preview.innerHTML = '';
            }
            if (currentDocuments[cadetId] && currentDocuments[cadetId][type]) {
                delete currentDocuments[cadetId][type];
            }
        } else {
            throw new Error(data.message || 'Ошибка при удалении документа');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Ошибка при удалении документа');
    });
}

// Обновляем обработчик отправки формы
document.getElementById('editForm').addEventListener('submit', function(e) {
    e.preventDefault();
    
    const formData = new FormData(this);
    const cadetId = this.getAttribute('data-cadet-id');
    
    // Добавляем базовые поля
    formData.append('full_name', document.getElementById('editFullName').value);
    formData.append('birth_date', document.getElementById('editBirthDate').value);
    formData.append('achievements', document.getElementById('editAchievements').value);
    formData.append('reprimands', document.getElementById('editReprimands').value);
    
    // Добавляем документы в FormData
    if (window.currentDocuments && window.currentDocuments[cadetId]) {
        Object.entries(window.currentDocuments[cadetId]).forEach(([type, doc]) => {
            if (doc.data) {
                const blob = dataURItoBlob(doc.data);
                if (blob) {
                    formData.append(`${type}_file`, blob, `${type}.jpg`);
                    formData.append(`${type}_metadata`, JSON.stringify({
                        timestamp: new Date().toISOString(),
                        fileType: 'image/jpeg',
                        documentType: type
                    }));
                }
            }
        });
    }

    // Отправляем запрос
    fetch(this.action, {
        method: 'POST',
        body: formData,
        headers: {
            'X-CSRFToken': getCSRFToken()
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            window.location.reload();
        } else {
            throw new Error(data.message || 'Ошибка при сохранении');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Ошибка при сохранении: ' + error.message);
    });
});

// Вспомогательная функция для конвертации Data URI в Blob
function dataURItoBlob(dataURI) {
    try {
        if (!dataURI || typeof dataURI !== 'string') {
            console.error('Invalid dataURI:', dataURI);
            return null;
        }

        let byteString;
        let mimeType;

        if (dataURI.startsWith('data:')) {
            const [header, base64Data] = dataURI.split(',');
            byteString = atob(base64Data);
            mimeType = header.split(':')[1].split(';')[0];
        } else {
            byteString = atob(dataURI);
            // Определяем тип файла по расширению или используем application/octet-stream
            mimeType = 'application/octet-stream';
        }

        const ab = new ArrayBuffer(byteString.length);
        const ia = new Uint8Array(ab);
        
        for (let i = 0; i < byteString.length; i++) {
            ia[i] = byteString.charCodeAt(i);
        }
        
        return new Blob([ab], { type: mimeType });
    } catch (error) {
        console.error('Error converting data URI to Blob:', error);
        return null;
    }
}

// Добавляем функцию закрытия модального окна выбора типа
window.closeDocTypeModal = function() {
    window.closeModal("docTypeModal");
    currentFile = null;
};

// Добавляем обработчики событий при загрузке DOM
document.addEventListener('DOMContentLoaded', function() {
    const docTypeButtons = document.querySelectorAll('.doc-type-buttons button');
    docTypeButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            const type = this.getAttribute('onclick').match(/'([^']+)'/)[1];
            assignDocument(type);
        });
    });
});

// Обработчик формы редактирования
document.getElementById('editForm').addEventListener('submit', function(e) {
    e.preventDefault();
    
    const formData = new FormData(this);
    const cadetId = this.getAttribute('data-cadet-id');
    
    // Добавляем документы в FormData
    if (window.currentDocuments && window.currentDocuments[cadetId]) {
        Object.entries(window.currentDocuments[cadetId]).forEach(([type, doc]) => {
            if (doc.data) {
                const blob = dataURItoBlob(doc.data);
                if (blob) {
                    formData.append(`${type}_file`, blob, `${type}.jpg`);
                    formData.append(`${type}_metadata`, JSON.stringify({
                        timestamp: new Date().toISOString(),
                        fileType: 'image/jpeg',
                        documentType: type
                    }));
                }
            }
        });
    }

    // Отправляем запрос
    fetch(this.action, {
        method: 'POST',
        body: formData,
        headers: {
            'X-CSRFToken': getCSRFToken()
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            window.location.reload();
        } else {
            throw new Error(data.message || 'Ошибка при сохранении');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Ошибка при сохранении: ' + error.message);
    });
});

// Функция для загрузки документа при создании
function handleAddDocumentUpload(input) {
    console.log('Handle add document upload called');
    
    if (input.files && input.files[0]) {
        currentFile = input.files[0];
        console.log('File selected:', currentFile.name);
        
        const docTypeModal = document.getElementById('docTypeModal');
        docTypeModal.setAttribute('data-mode', 'add');
        window.openModal("docTypeModal");
    }
}

async function loadDocuments(cadetId) {
    try {
        const response = await fetch(`/get-cadet-documents/${cadetId}/`);
        const documents = await response.json();
        return documents;
    } catch (error) {
        console.error('Error loading documents:', error);
        return {};
    }
}

// Добавляем обработчик события DOMContentLoaded
document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM загружен, инициализация обработчиков...');
    
    // Находим все кнопки редактирования
    const editButtons = document.querySelectorAll('.edit-btn');
    console.log('Найдено кнопок редактирования:', editButtons.length);
    
    // Добавляем обработчики событий для кнопок
    editButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            console.log('Нажата кнопка редактирования');
            openEditModal(this);
        });
    });
});

function loadDocument(cadetId, docType) {
    fetch(`/get-cadet-documents/${cadetId}/`)
        .then(response => response.json())
        .then(data => {
            if (data[docType] && data[docType].url) {
                window.open(data[docType].url, '_blank');
            } else {
                alert('Ошибка при загрузке документа');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('Ошибка при загрузке документа');
        });
}

// Функция инициализации фильтра классов
function initGradeFilter() {
    const filterBtn = document.querySelector('.grade-filter-btn');
    const dropdown = document.querySelector('.grade-filter-dropdown');
    const searchInput = document.querySelector('.grade-search-input');
    const applyBtn = document.querySelector('.apply-filter');
    const clearBtn = document.querySelector('.clear-filter');

    // Получаем все доступные классы
    document.querySelectorAll('tbody tr').forEach(row => {
        const grade = row.children[1].textContent.trim();
        if (grade && grade !== 'Не указан') {
            availableGrades.add(grade);
        }
    });

    // Сортируем классы
    const sortedGrades = Array.from(availableGrades).sort((a, b) => {
        const aNum = parseInt(a);
        const bNum = parseInt(b);
        if (aNum !== bNum) return aNum - bNum;
        return a.localeCompare(b);
    });

    // Создаем чекбоксы для классов
    const gradeList = document.querySelector('.grade-list');
    gradeList.innerHTML = ''; // Очищаем список перед добавлением

    // Простой список для всех классов
    sortedGrades.forEach(grade => {
        const label = document.createElement('label');
        label.className = 'grade-checkbox';
        label.innerHTML = `
            <input type="checkbox" value="${grade}">
            ${grade}
        `;
        gradeList.appendChild(label);

        const checkbox = label.querySelector('input');
        checkbox.addEventListener('change', function() {
            if (this.checked) {
                selectedGrades.add(this.value);
            } else {
                selectedGrades.delete(this.value);
            }
            updateFilterState();
        });
    });

    // Обработчик кнопки фильтра
    filterBtn.addEventListener('click', () => {
        dropdown.style.display = dropdown.style.display === 'none' ? 'block' : 'none';
    });

    // Закрытие дропдауна при клике вне него
    document.addEventListener('click', (e) => {
        if (!dropdown.contains(e.target) && !filterBtn.contains(e.target)) {
            dropdown.style.display = 'none';
        }
    });

    // Поиск по классам
    searchInput.addEventListener('input', (e) => {
        const searchText = e.target.value.toLowerCase();
        document.querySelectorAll('.grade-checkbox').forEach(label => {
            const gradeText = label.textContent.trim().toLowerCase();
            const shouldShow = gradeText.includes(searchText);
            label.style.display = shouldShow ? 'block' : 'none';
        });
    });

    // Применение фильтра
    applyBtn.addEventListener('click', () => {
        applyGradeFilter();
        dropdown.style.display = 'none';
    });

    // Сброс фильтра
    clearBtn.addEventListener('click', () => {
        selectedGrades.clear();
        document.querySelectorAll('.grade-checkbox input').forEach(cb => {
            cb.checked = false;
        });
        updateFilterState();
        applyGradeFilter();
        dropdown.style.display = 'none';
    });
}

// Функция обновления состояния фильтра
function updateFilterState() {
    const filterBtn = document.querySelector('.grade-filter-btn');
    filterBtn.closest('.grade-filter').classList.toggle('grade-filter-active', selectedGrades.size > 0);
}

// Функция применения фильтра
function applyGradeFilter() {
    const rows = document.querySelectorAll('tbody tr');
    rows.forEach(row => {
        const grade = row.children[1].textContent.trim();
        if (selectedGrades.size === 0 || selectedGrades.has(grade)) {
            row.style.display = '';
        } else {
            row.style.display = 'none';
        }
    });
}

