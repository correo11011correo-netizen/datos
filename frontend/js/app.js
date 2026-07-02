
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

async function apiRequest(endpoint, method = 'GET', body = null) {
    const token = session.getToken();
    const options = {
        method,
        headers: { 'Content-Type': 'application/json', 'x-admin-token': token }
    };
    if (body) options.body = JSON.stringify(body);
    
    const overlay = document.getElementById('loading-overlay');
    if (overlay) overlay.classList.remove('hidden');

    try {
        const response = await fetch(`${API_URL}${endpoint}`, options);
        if (!response.ok) {
            if (response.status === 403) {
                handleLogout();
                throw new Error('Sesión expirada o token inválido');
            }
            throw new Error(`Error ${response.status}: ${response.statusText}`);
        }
        return await response.json();
    } catch (e) {
        throw e;
    } finally {
        if (overlay) overlay.classList.add('hidden');
    }
}

// --- NAVEGACIÓN ---
function showModule(moduleId) {
    document.querySelectorAll('.module').forEach(m => m.classList.add('hidden'));
    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
    document.querySelectorAll('.nav-item-mobile').forEach(n => n.classList.remove('active'));
    
    const mod = document.getElementById(`mod-${moduleId}`);
    if (mod) mod.classList.remove('hidden');
    
    const nav = document.getElementById(`nav-${moduleId}`);
    if (nav) nav.classList.add('active');
    
    const mobNav = document.getElementById(`mob-nav-${moduleId}`);
    if (mobNav) mobNav.classList.add('active');

    if (moduleId === 'users') loadTenants();
    if (moduleId === 'reports') loadGlobalReports();
    if (moduleId === 'metrics') loadSystemMetrics();
    if (moduleId === 'entities') loadExplorerTenants();
}

// --- LOGIN / LOGOUT ---
async function handleLogin() {
    const tokenInput = document.getElementById('admin-token');
    const token = tokenInput.value;
    if (!token) return notify('Ingrese token', 'error');
    try {
        session.saveToken(token);
        await apiRequest('/api/status');
        document.getElementById('login-screen').classList.add('hidden');
        document.getElementById('admin-dashboard').classList.remove('hidden');
        notify('Acceso concedido', 'success');
        showModule('infra');
    } catch (e) {
        notify(`Error: ${e.message}`, 'error');
    }
}

function handleLogout() {
    session.clearToken();
    document.getElementById('login-screen').classList.remove('hidden');
    document.getElementById('admin-dashboard').classList.add('hidden');
    notify('Sesión cerrada', 'info');
}

// --- MÓDULO USUARIOS (TENANTS) ---
async function loadTenants() {
    try {
        const res = await apiRequest('/exec?cmd=system.tenant.list', 'POST', {});
        const body = document.getElementById('tenants-body');
        if (!body) return;
        body.innerHTML = '';

        if (res.status === 'success' && Array.isArray(res.result)) {
            res.result.forEach(t => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td>${t.id.substring(0, 8)}...</td>
                    <td>${t.name}</td>
                    <td>${t.plan}</td>
                    <td><button onclick="openTenantDetail('${t.id}', '${t.name}')" class="btn btn-outline">Gestionar</button></td>
                `;
                body.appendChild(tr);
            });
        }
    } catch (e) { notify(e.message, 'error'); }
}

async function openTenantDetail(tid, name) {
    document.getElementById('tenants-main-view').classList.add('hidden');
    const detailView = document.getElementById('tenant-detail-view');
    detailView.classList.remove('hidden');
    document.getElementById('detail-tenant-name').innerText = `Tenant: ${name}`;

    try {
        const bpRes = await apiRequest('/exec?cmd=dev.blueprint.list', 'POST', {});
        document.getElementById('detail-blueprint-content').innerText = JSON.stringify(bpRes.result || [], null, 2);
    } catch (e) { document.getElementById('detail-blueprint-content').innerText = 'Error loading BP'; }

    try {
        const repRes = await apiRequest('/exec?cmd=system.report.list', 'POST', {});
        const filtered = (repRes.result || []).filter(r => r.tenant_id === tid);
        const repDiv = document.getElementById('detail-reports-content');
        repDiv.innerHTML = filtered.map(r => `
            <div class="report-item ${r.category.toLowerCase()}">
                <strong>${r.category}</strong>: ${r.title} <br/>
                <small>${r.description}</small>
            </div>
        `).join('') || 'Sin reportes';
    } catch (e) { document.getElementById('detail-reports-content').innerText = 'Error loading reports'; }

    document.getElementById('detail-storage-content').innerText = (Math.random() * 100).toFixed(2) + " MB used";
}

function closeTenantDetail() {
    document.getElementById('tenant-detail-view').classList.add('hidden');
    document.getElementById('tenants-main-view').classList.remove('hidden');
}

// --- EXPLORADOR DE DATOS (ENTIDADES) ---
async function loadExplorerTenants() {
    try {
        const res = await apiRequest('/exec?cmd=system.tenant.list', 'POST', {});
        const list = document.getElementById('entity-list');
        if (!list) return;
        list.innerHTML = '';

        if (res.status === 'success' && Array.isArray(res.result)) {
            res.result.forEach(t => {
                const item = document.createElement('div');
                item.className = 'entity-item';
                item.innerHTML = `<span>🏢</span> <span>${t.name}</span>`;
                item.onclick = () => selectTenant(t.id, t.name, item);
                list.appendChild(item);
            });
        }
    } catch (e) { notify(e.message, 'error'); }
}

async function selectTenant(tenantId, tenantName, element) {
    document.querySelectorAll('.entity-item').forEach(i => i.classList.remove('active'));
    element.classList.add('active');

    const list = document.getElementById('entity-list');
    // We keep the list but we could add a "Back" button. 
    // For now, we just fetch the entities for this tenant.
    
    try {
        const res = await apiRequest('/exec?cmd=system.tenant.entities', 'POST', { tenant_id: tenantId });
        if (res.status === 'success' && Array.isArray(res.result)) {
            // If we want to show entities in the same sidebar, we could replace content.
            // Instead, let's use a simple prompt or just list them in the main viewer as a starting point.
            // To maintain the previous UX, we'll render the entities as a table in the main viewer.
            showEntityList(tenantId, tenantName, res.result);
        }
    } catch (e) { notify(e.message, 'error'); }
}

function showEntityList(tenantId, tenantName, entities) {
    document.getElementById('empty-state').classList.add('hidden');
    const viewer = document.getElementById('data-viewer');
    viewer.classList.remove('hidden');
    document.getElementById('current-entity-title').querySelector('span').innerText = `Tenants: ${tenantName}`;
    
    const data = entities.map(ent => ({ entity: ent }));
    renderTable(data, 'table-head', 'table-body', (row) => {
        const entityName = row.entity;
        selectEntity(entityName, tenantId);
    });
}

async function createEntity() {
    const name = document.getElementById('entity-name').value;
    if (!name) return notify('Escribe el nombre del tenant', 'error');
    try {
        const res = await apiRequest('/exec?cmd=system.tenant.create', 'POST', { name });
        if (res.status === 'success') {
            notify(`Tenant ${name} creado. Key: ${res.result.api_key}`, 'success');
            document.getElementById('entity-name').value = '';
            loadExplorerTenants();
        } else {
            throw new Error(res.message);
        }
    } catch (e) {
        notify(`Error al crear tenant: ${e.message}`, 'error');
    }
}

async function selectEntity(entityName, tenantId) {
    document.getElementById('current-entity-title').querySelector('span').innerText = entityName;
    try {
        const res = await apiRequest('/exec?cmd=data.query', 'POST', { 
            entity: entityName,
            impersonate_tid: tenantId 
        });
        if (res.status === 'success' && Array.isArray(res.result)) {
            renderTable(res.result, 'table-head', 'table-body');
        }
    } catch (e) { notify(e.message, 'error'); }
}

function renderTable(data, headId, bodyId, onRowClick = null) {
    const head = document.getElementById(headId);
    const body = document.getElementById(bodyId);
    if (!head || !body) return;

    head.innerHTML = '';
    body.innerHTML = '';

    if (!data || data.length === 0) {
        body.innerHTML = '<tr><td colspan="10" style="text-align:center">No hay datos disponibles</td></tr>';
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
        tr.style.cursor = onRowClick ? 'pointer' : 'default';
        if (onRowClick) tr.onclick = () => onRowClick(row);
        
        keys.forEach(k => {
            const td = document.createElement('td');
            td.innerText = typeof row[k] === 'object' ? JSON.stringify(row[k]) : row[k];
            tr.appendChild(td);
        });
        body.appendChild(tr);
    });
}

function closeViewer() {
    document.getElementById('data-viewer').classList.add('hidden');
    document.getElementById('empty-state').classList.remove('hidden');
}

// --- MÓDULO SOPORTE (REPORTES) ---
async function loadGlobalReports() {
    try {
        const res = await apiRequest('/exec?cmd=system.report.list', 'POST', {});
        const body = document.getElementById('global-reports-body');
        if (!body) return;
        body.innerHTML = '';

        if (res.status === 'success' && Array.isArray(res.result)) {
            res.result.forEach(r => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td>${r.tenant_id.substring(0, 8)}...</td>
                    <td><span class="badge ${r.category}">${r.category}</span></td>
                    <td>${r.title}</td>
                    <td>${r.status}</td>
                    <td>${new Date(r.created_at).toLocaleDateString()}</td>
                `;
                body.appendChild(tr);
            });
        }
    } catch (e) { notify(e.message, 'error'); }
}

// --- MÓDULO MÉTRICAS ---
async function loadSystemMetrics() {
    try {
        document.getElementById('met-total-tenants').innerText = '12';
        document.getElementById('met-total-storage').innerText = '1.4 GB';
        document.getElementById('met-events-rate').innerText = '45 req/s';
        document.getElementById('met-uptime').innerText = '99.9%';
    } catch (e) { notify(e.message, 'error'); }
}

// --- INFRAESTRUCTURA ---
async function runCmd(cmd) {
    // Map legacy frontend commands to new backend system commands
    const cmdMap = {
        'init_system': 'system.init_infra',
        'format_all': 'system.db.format'
    };
    const finalCmd = cmdMap[cmd] || cmd;

    try {
        const res = await apiRequest(`/exec?cmd=${finalCmd}`, 'POST', {});
        notify(res.message || 'Ejecutado', 'success');
        if (finalCmd === 'system.init_infra') loadTenants();
    } catch (e) { notify(e.message, 'error'); }
}

window.onload = () => {
    if (session.getToken()) {
        document.getElementById('login-screen').classList.add('hidden');
        document.getElementById('admin-dashboard').classList.remove('hidden');
        showModule('infra');
    }
};
