const API_URL = '';

// Gestión de Sesión
const session = {
    saveToken: (token) => localStorage.setItem('db_sentinel_token', token),
    getToken: () => localStorage.getItem('db_sentinel_token'),
    clearToken: () => localStorage.removeItem('db_sentinel_token')
};

// Cambio de vistas
function switchView(view) {
    const loginScreen = document.getElementById('login-screen');
    const adminDashboard = document.getElementById('admin-dashboard');
    
    if (view === 'admin') {
        loginScreen.classList.add('hidden');
        adminDashboard.classList.remove('hidden');
    } else {
        loginScreen.classList.remove('hidden');
        adminDashboard.classList.add('hidden');
    }
}

async function apiRequest(endpoint, method = 'GET', body = null) {
    const token = session.getToken();
    const options = {
        method,
        headers: {
            'Content-Type': 'application/json',
            'x-admin-token': token
        }
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
        // 1. Guardar el token PRIMERO para que apiRequest pueda leerlo
        session.saveToken(token);
        
        // 2. Ahora validar contra la API
        await apiRequest('/exec?cmd=init_system', 'POST', {});
        
        // 3. Si la API respondió OK, entrar al dashboard
        switchView('admin');
        tokenInput.value = '';
    } catch (e) {
        // Si falló, limpiar el token erróneo
        session.clearToken();
        alert(`Acceso Denegado: ${e.message}`);
    }
}

function handleLogout() {
    session.clearToken();
    switchView('login');
}

// Comandos del Panel
async function runCmd(cmd) {
    try {
        const res = await apiRequest(`/exec?cmd=${cmd}`, 'POST');
        alert(`Resultado: ${res.result}`);
    } catch (e) {
        alert(`Error: ${e.message}`);
    }
}

async function createEntity() {
    const name = document.getElementById('entity-name').value;
    if (!name) return alert('Escribe el nombre de la entidad');
    try {
        const res = await apiRequest(`/exec?cmd=create_entity`, 'POST', { name });
        alert(res.result);
        document.getElementById('entity-name').value = '';
    } catch (e) {
        alert(`Error: ${e.message}`);
    }
}

async function viewData() {
    const entity = document.getElementById('view-entity').value;
    if (!entity) return alert('Escribe la entidad a visualizar');
    try {
        const res = await apiRequest(`/exec?cmd=query_entity`, 'POST', { entity });
        renderTable(res.result);
    } catch (e) {
        alert(`Error: ${e.message}`);
    }
}

function renderTable(data) {
    const head = document.getElementById('table-head');
    const body = document.getElementById('table-body');
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
        keys.forEach(k => tr += `<td>${row[k] || ''}</td>`);
        tr += '</tr>';
        body.innerHTML += tr;
    });
}

// Inicialización al cargar la página
window.onload = () => {
    if (session.getToken()) {
        switchView('admin');
    }
};
