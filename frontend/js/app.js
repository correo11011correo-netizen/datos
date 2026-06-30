const API_URL = '';

const session = {
    saveToken: (token) => localStorage.setItem('db_sentinel_token', token),
    getToken: () => localStorage.getItem('db_sentinel_token'),
    clearToken: () => localStorage.removeItem('db_sentinel_token')
};

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
        if (response.status === 403) {
            handleLogout();
            throw new Error('Sesión expirada o token inválido');
        }
        const err = await response.json();
        throw new Error(err.detail || 'Error en la petición');
    }
    return response.json();
}

async function handleLogin() {
    const tokenInput = document.getElementById('admin-token');
    const token = tokenInput.value;
    if (!token) return alert('Por favor, ingrese el token');
    try {
        session.saveToken(token);
        await apiRequest('/exec?cmd=init_system', 'POST', {});
        switchView('admin');
        tokenInput.value = '';
    } catch (e) {
        session.clearToken();
        alert(`Acceso Denegado: ${e.message}`);
    }
}

function handleLogout() {
    session.clearToken();
    switchView('login');
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
        const grid = document.getElementById('entity-grid');
        grid.innerHTML = '';
        
        res.forEach(ent => {
            const card = document.createElement('div');
            card.className = 'entity-card';
            card.innerHTML = `<h4>${ent.name}</h4>`;
            card.onclick = () => viewData(ent.name);
            grid.appendChild(card);
        });
    } catch (e) {
        console.error('Error loading entities:', e);
    }
}

async function createEntity() {
    const name = document.getElementById('entity-name').value;
    if (!name) return alert('Escribe el nombre de la entidad');
    try {
        await apiRequest(`/exec?cmd=create_entity`, 'POST', { name });
        alert('Entidad creada');
        document.getElementById('entity-name').value = '';
        loadEntities();
    } catch (e) {
        alert(`Error: ${e.message}`);
    }
}

async function viewData(entityName) {
    try {
        const res = await apiRequest(`/exec?cmd=query_entity`, 'POST', { entity: entityName });
        
        // Mostrar visor
        const viewer = document.getElementById('data-viewer');
        viewer.classList.remove('hidden');
        document.getElementById('current-entity-title').querySelector('span').innerText = entityName;
        
        renderTable(res, 'table-head', 'table-body');
    } catch (e) {
        alert(`Error: ${e.message}`);
    }
}

function renderTable(data, headId, bodyId) {
    const head = document.getElementById(headId);
    const body = document.getElementById(bodyId);
    head.innerHTML = '';
    body.innerHTML = '';

    if (!data || data.length === 0) {
        body.innerHTML = '<tr><td colspan="1" style="text-align:center">No hay datos</td></tr>';
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
    document.getElementById('data-viewer').classList.add('hidden');
}

// Funciones para el módulo de usuarios
async function viewUserData(entity) {
    try {
        const res = await apiRequest(`/exec?cmd=query_entity`, 'POST', { entity });
        document.getElementById('user-data-viewer').classList.remove('hidden');
        document.getElementById('user-entity-title').querySelector('span').innerText = entity;
        renderTable(res, 'user-table-head', 'user-table-body');
    } catch (e) {
        alert(`Error: ${e.message}`);
    }
}

function closeUserViewer() {
    document.getElementById('user-data-viewer').classList.add('hidden');
}

// Sobrescribir viewData original para manejar el contexto de usuarios si es necesario
const originalViewData = viewData;
window.viewData = (entity) => {
    const activeMod = document.querySelector('.module:not(.hidden)').id;
    if (activeMod === 'mod-users') {
        viewUserData(entity);
    } else {
        originalViewData(entity);
    }
};

async function runCmd(cmd) {
    try {
        const res = await apiRequest(`/exec?cmd=${cmd}`, 'POST', {});
        alert(`Resultado: ${res.result}`);
        if (cmd === 'init_system' || cmd === 'format_all') loadEntities();
    } catch (e) {
        alert(`Error: ${e.message}`);
    }
}

window.onload = () => {
    if (session.getToken()) {
        switchView('admin');
    }
};
