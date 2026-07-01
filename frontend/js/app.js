
const API_URL = '';

const session = {
    saveToken: (token) => localStorage.setItem('db_sentinel_token', token),
    getToken: () => localStorage.getItem('db_sentinel_token'),
    clearToken: () => localStorage.removeItem('db_sentinel_token')
};

let activeRequests = 0;

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
        loadTenants();
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
    
    const overlay = document.getElementById('loading-overlay');
    const loadingText = document.getElementById('loading-text');
    
    const isCritical = (method === 'POST' || endpoint.includes('/exec'));
    if (isCritical) {
        overlay.classList.remove('hidden');
        if (loadingText) loadingText.innerText = "Sincronizando con el Motor de DB...";
    }

    try {
        const response = await fetch(`${API_URL}${endpoint}`, options);
        
        if (!response.ok) {
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
                    errorMessage = err.detail[0].msg || 'Error de validación de datos';
                }
            } catch (e) {
                errorMessage = `Error del servidor (${response.status})`;
            }
            throw new Error(errorMessage);
        }

        const json = await response.json();
        
        if (json && json.result && typeof json.result === 'object') {
            return {
                data: json.result.data,
                message: json.result.message,
                success: json.result.success,
                error_code: json.result.error_code
            };
        }
        
        return json;
    } finally {
        if (isCritical) {
            // Pequeño delay para evitar el parpadeo si hay peticiones seguidas
            setTimeout(() => {
                // Solo ocultamos si no hay otras peticiones críticas activas en la cola de eventos
                // En una implementación simple, simplemente lo ocultamos.
                overlay.classList.add('hidden');
            }, 100);
        }
    }
}

async function handleLogin() {
    const tokenInput = document.getElementById('admin-token');
    const token = tokenInput.value;
    if (!token) return notify('Por favor, ingrese el token', 'error');
    try {
        session.saveToken(token);
        await apiRequest('/api/status'); 
        
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

async function loadTenants() {
    try {
        const res = await apiRequest('/exec?cmd=list_tenants', 'POST', {});
        const list = document.getElementById('entity-list');
        list.innerHTML = '';
        
        if (res && Array.isArray(res.data)) {
            res.data.forEach(tenant => {
                const item = document.createElement('div');
                item.className = 'entity-item tenant-item';
                item.innerHTML = `<span>🏢</span> <span>${tenant.name}</span>`;
                item.onclick = () => selectTenant(tenant.id, item);
                list.appendChild(item);
            });
        }
    } catch (e) {
        notify(`Error cargando tenants: ${e.message}`, 'error');
    }
}

async function selectTenant(tenantId, element) {
    document.querySelectorAll('.entity-item').forEach(i => i.classList.remove('active'));
    element.classList.add('active');

    if (window.innerWidth < 768) {
        document.querySelector('.explorer-sidebar').classList.add('hidden');
    }

    const list = document.getElementById('entity-list');
    list.innerHTML = '<div class="list-header"><button onclick="loadTenants()" class="btn-back">← Volver a Tenants</button></div>';
    
    try {
        const res = await apiRequest('/exec?cmd=list_entities', 'POST', {});
        if (res && Array.isArray(res.data)) {
            res.data.forEach(ent => {
                const item = document.createElement('div');
                item.className = 'entity-item entity-sub-item';
                item.innerHTML = `<span>📦</span> <span>${ent.name}</span>`;
                item.onclick = () => selectEntity(ent.name, tenantId, item);
                list.appendChild(item);
            });
        }
    } catch (e) {
        notify(`Error cargando entidades: ${e.message}`, 'error');
    }
}

async function selectEntity(name, tenantId, element) {
    document.querySelectorAll('.entity-sub-item').forEach(i => i.classList.remove('active'));
    element.classList.add('active');

    document.getElementById('empty-state').classList.add('hidden');
    const viewer = document.getElementById('data-viewer');
    viewer.classList.remove('hidden');
    document.getElementById('current-entity-title').querySelector('span').innerText = name;

    try {
        const res = await apiRequest(`/exec?cmd=query_entity`, 'POST', { 
            entity: name,
            impersonate_tid: tenantId 
        });
        renderTable(res.data, 'table-head', 'table-body');
    } catch (e) {
        notify(`Error al cargar datos de ${name}: ${e.message}`, 'error');
    }
}

async function createEntity() {
    const name = document.getElementById('entity-name').value;
    if (!name) return notify('Escribe el nombre de la plataforma', 'error');
    try {
        await apiRequest(`/exec?cmd=create_entity`, 'POST', { name });
        notify(`Entidad ${name} creada`, 'success');
        document.getElementById('entity-name').value = '';
        loadTenants();
    } catch (e) {
        notify(`Error al crear entidad: ${e.message}`, 'error');
    }
}

function showModule(moduleId) {
    document.querySelectorAll('.module').forEach(m => m.classList.add('hidden'));
    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
    
    document.getElementById(`mod-${moduleId}`).classList.remove('hidden');
    document.getElementById(`nav-${moduleId}`).classList.add('active');
    
    if (moduleId === 'entities') loadTenants();
}

function renderTable(data, headId, bodyId) {
    const head = document.getElementById(headId);
    const body = document.getElementById(bodyId);
    
    if (!head || !body) {
        console.error(`DOM elements not found: ${headId} or ${bodyId}`);
        return;
    }

    head.innerHTML = '';
    body.innerHTML = '';

    if (!data || !Array.isArray(data) || data.length === 0) {
        body.innerHTML = '<tr><td colspan="1" style="text-align:center">No hay datos disponibles</td></tr>';
        return;
    }

    const keys = Object.keys(data[0]);
    keys.forEach(k => {
        const th = document.createElement('th');
        th.innerText = k;
        head.appendChild(th);
    });

    data.forEach(row => {
        const tr = document.createElement('tr');
        keys.forEach(k => {
            const td = document.createElement('td');
            td.innerText = typeof row[k] === 'object' ? JSON.stringify(row[k]) : row[k];
            tr.appendChild(td);
        });
        body.appendChild(tr);
    });
}

function closeViewer() {
    if (window.innerWidth < 768) {
        document.querySelector('.explorer-sidebar').classList.remove('hidden');
    }
    document.getElementById('data-viewer').classList.add('hidden');
    document.getElementById('empty-state').classList.remove('hidden');
}

async function viewData(identifier) {
    try {
        let res;
        let title = identifier;

        if (identifier.startsWith('list_')) {
            // Comando de lista core (tenants, api_keys)
            res = await apiRequest(`/exec?cmd=${identifier}`, 'POST', {});
            title = identifier.replace('list_', '').replace('_', ' ').toUpperCase();
        } else {
            // Consulta a entidad genérica (admins, roles)
            res = await apiRequest(`/exec?cmd=query_entity`, 'POST', { entity: identifier });
            title = identifier.charAt(0).toUpperCase() + identifier.slice(1);
        }

        const viewer = document.getElementById('user-data-viewer');
        if (!viewer) throw new Error("Viewer element not found");
        
        viewer.classList.remove('hidden');
        const titleSpan = document.getElementById('user-entity-title')?.querySelector('span');
        if (titleSpan) titleSpan.innerText = title;
        
        renderTable(res.data, 'user-table-head', 'user-table-body');
    } catch (e) {
        console.error(`ViewData error for ${identifier}:`, e);
        notify(`Error cargando ${identifier}: ${e.message}`, 'error');
    }
}

function closeUserViewer() {
    document.getElementById('user-data-viewer').classList.add('hidden');
}

async function runCmd(cmd) {
    try {
        if (cmd === 'format_all') {
            const list = document.getElementById('entity-list');
            if (list) list.innerHTML = '';
        }

        const res = await apiRequest(`/exec?cmd=${cmd}`, 'POST', {});
        const message = res.message || 'Comando ejecutado';
        notify(message, 'success');
        
        // Solo recargamos los tenants si el sistema ha sido inicializado
        if (cmd === 'init_system') {
            loadTenants();
        }
    } catch (e) {
        notify(`Error: ${e.message}`, 'error');
    }
}

window.onload = () => {
    if (session.getToken()) {
        switchView('admin');
    }
};
