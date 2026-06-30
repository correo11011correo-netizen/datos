const API_URL = '';

const session = {
    saveToken: (token) => localStorage.setItem('db_sentinel_token', token),
    getToken: () => localStorage.getItem('db_sentinel_token'),
    clearToken: () => localStorage.removeItem('db_sentinel_token')
};

// SISTEMA DE NOTIFICACIONES (TOASTS)
function notify(message, type = 'info') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.innerText = message;
    
    container.appendChild(toast);
    
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(100%)';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

function switchView(view) {
    const loginScreen = document.getElementById('login-screen');
    const adminDashboard = document.getElementById('admin-dashboard');
    if (view === 'admin') {
        loginScreen.classList.add('hidden');
        adminDashboard.classList.remove('hidden');
        loadEntities();
    } else {
        loginScreen.classList.remove('hidden');
        adminDashboard.classList.add('hidden');
    }
}

async function apiRequest(endpoint, method = 'GET', body = null) {
    const token = session.getToken();
    const options = {
        method,
        headers: { 'Content-Type': 'application/json', 'x-admin-token': token }
    };
    if (body) options.body = JSON.stringify(body);
    
    const response = await fetch(`${API_URL}${endpoint}`, options);
    
    if (!response.ok) {
        // 403 o 422 (cuando falta el token) se tratan como sesión inválida
        if (response.status === 403 || response.status === 422) {
            handleLogout();
            throw new Error('Sesión expirada o token inválido');
        }
        
        let errorMessage = 'Error en la petición';
        try {
            const err = await response.json();
            if (typeof err.detail === 'string') {
                errorMessage = err.detail;
            } else if (Array.isArray(err.detail) && err.detail.length > 0) {
                // Extraer el mensaje del primer error de validación de FastAPI
                errorMessage = err.detail[0].msg || 'Error de validación de datos';
            }
        } catch (e) {
            errorMessage = `Error del servidor (${response.status})`;
        }
        throw new Error(errorMessage);
    }
    return response.json();
}

async function handleLogin() {
    const tokenInput = document.getElementById('admin-token');
    const token = tokenInput.value;
    if (!token) return notify('Por favor, ingrese el token', 'error');
    try {
        session.saveToken(token);
        switchView('admin');
        tokenInput.value = '';
        notify('Bienvenido al Command Center', 'success');
    } catch (e) {
        session.clearToken();
        notify(`Acceso Denegado: ${e.message}`, 'error');
    }
}

function handleLogout() {
    session.clearToken();
    switchView('login');
    notify('Sesión cerrada correctamente', 'info');
}

function showModule(moduleId) {
    document.querySelectorAll('.module').forEach(m => m.classList.add('hidden'));
    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
    
    document.getElementById(`mod-${moduleId}`).classList.remove('hidden');
    document.getElementById(`nav-${moduleId}`).classList.add('active');
    
    if (moduleId === 'entities') loadEntities();
}

async function loadEntities() {
    try {
        const res = await apiRequest('/exec?cmd=list_entities', 'POST', {});
        const list = document.getElementById('entity-list');
        list.innerHTML = '';
        
        res.forEach(ent => {
            const item = document.createElement('div');
            item.className = 'entity-item';
            item.innerHTML = `<span>📂</span> <span>${ent.name}</span>`;
            item.onclick = () => selectEntity(ent.name, item);
            list.appendChild(item);
        });
    } catch (e) {
        notify(`Error cargando entidades: ${e.message}`, 'error');
    }
}

async function selectEntity(name, element) {
    // UI: Marcar como activo
    document.querySelectorAll('.entity-item').forEach(i => i.classList.remove('active'));
    element.classList.add('active');

    // UI: Drill-down en móvil
    if (window.innerWidth < 768) {
        document.querySelector('.explorer-sidebar').classList.add('hidden');
    }

    // UI: Cambiar vista de vacío a datos
    document.getElementById('empty-state').classList.add('hidden');
    const viewer = document.getElementById('data-viewer');
    viewer.classList.remove('hidden');
    document.getElementById('current-entity-title').querySelector('span').innerText = name;

    try {
        const res = await apiRequest(`/exec?cmd=query_entity`, 'POST', { entity: name });
        renderTable(res, 'table-head', 'table-body');
    } catch (e) {
        notify(`Error al cargar datos de ${name}: ${e.message}`, 'error');
    }
}

async function createEntity() {
    const name = document.getElementById('entity-name').value;
    if (!name) return notify('Escribe el nombre de la plataforma', 'error');
    try {
        await apiRequest(`/exec?cmd=create_entity`, 'POST', { name });
        notify(`Plataforma ${name} creada`, 'success');
        document.getElementById('entity-name').value = '';
        loadEntities();
    } catch (e) {
        notify(`Error al crear entidad: ${e.message}`, 'error');
    }
}

function renderTable(data, headId, bodyId) {
    const head = document.getElementById(headId);
    const body = document.getElementById(bodyId);
    head.innerHTML = '';
    body.innerHTML = '';

    if (!data || data.length === 0) {
        body.innerHTML = '<tr><td colspan="1" style="text-align:center">No hay datos disponibles</td></tr>';
        return;
    }

    const keys = Object.keys(data[0]);
    keys.forEach(k => head.innerHTML += `<th>${k}</th>`);

    data.forEach(row => {
        let tr = '<tr>';
        keys.forEach(k => tr += `<td>${typeof row[k] === 'object' ? JSON.stringify(row[k]) : row[k]}</td>`);
        tr += '</tr>';
        body.innerHTML += tr;
    });
}

function closeViewer() {
    // UI: Volver atrás en drill-down móvil
    if (window.innerWidth < 768) {
        document.querySelector('.explorer-sidebar').classList.remove('hidden');
    }
    document.getElementById('data-viewer').classList.add('hidden');
    document.getElementById('empty-state').classList.remove('hidden');
}

async function viewUserData(entity) {
    try {
        const res = await apiRequest(`/exec?cmd=query_entity`, 'POST', { entity });
        document.getElementById('user-data-viewer').classList.remove('hidden');
        document.getElementById('user-entity-title').querySelector('span').innerText = entity;
        renderTable(res, 'user-table-head', 'user-table-body');
    } catch (e) {
        notify(`Error cargando ${entity}`, 'error');
    }
}

function closeUserViewer() {
    document.getElementById('user-data-viewer').classList.add('hidden');
}

async function runCmd(cmd) {
    try {
        const res = await apiRequest(`/exec?cmd=${cmd}`, 'POST', {});
        notify(res.result, 'success');
        if (cmd === 'init_system' || cmd === 'format_all') loadEntities();
    } catch (e) {
        notify(`Error: ${e.message}`, 'error');
    }
}

window.onload = () => {
    if (session.getToken()) {
        switchView('admin');
    }
};
