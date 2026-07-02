
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
        const res = await apiRequest('/exec?cmd=list_tenants', 'POST', {});
        const body = document.getElementById('tenants-body');
        if (!body) return;
        body.innerHTML = '';

        if (res.result && Array.isArray(res.result)) {
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

    // 1. Cargar Blueprint
    try {
        const bpRes = await apiRequest('/exec?cmd=dev.blueprint.list', 'POST', {});
        const bp = bpRes.result.find(b => b.id === 'some_id'); // Simplified for this demo
        document.getElementById('detail-blueprint-content').innerText = JSON.stringify(bp || {info: 'No BP found'}, null, 2);
    } catch (e) { document.getElementById('detail-blueprint-content').innerText = 'Error loading BP'; }

    // 2. Cargar Reportes del Tenant
    try {
        const repRes = await apiRequest('/exec?cmd=system.report.list', 'POST', {});
        const filtered = repRes.result.filter(r => r.tenant_id === tid);
        const repDiv = document.getElementById('detail-reports-content');
        repDiv.innerHTML = filtered.map(r => `
            <div class="report-item ${r.category.toLowerCase()}">
                <strong>${r.category}</strong>: ${r.title} <br/>
                <small>${r.description}</small>
            </div>
        `).join('') || 'Sin reportes';
    } catch (e) { document.getElementById('detail-reports-content').innerText = 'Error loading reports'; }

    // 3. Métricas de almacenamiento (Simuladas)
    document.getElementById('detail-storage-content').innerText = (Math.random() * 100).toFixed(2) + " MB used";
}

function closeTenantDetail() {
    document.getElementById('tenant-detail-view').classList.add('hidden');
    document.getElementById('tenants-main-view').classList.remove('hidden');
}

// --- MÓDULO SOPORTE (REPORTES) ---
async function loadGlobalReports() {
    try {
        const res = await apiRequest('/exec?cmd=system.report.list', 'POST', {});
        const body = document.getElementById('global-reports-body');
        if (!body) return;
        body.innerHTML = '';

        if (res.result && Array.isArray(res.result)) {
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
        // Simulación de métricas ya que no hay endpoint de sistema avanzado aún
        document.getElementById('met-total-tenants').innerText = '12';
        document.getElementById('met-total-storage').innerText = '1.4 GB';
        document.getElementById('met-events-rate').innerText = '45 req/s';
        document.getElementById('met-uptime').innerText = '99.9%';
    } catch (e) { notify(e.message, 'error'); }
}

// --- INFRAESTRUCTURA ---
async function runCmd(cmd) {
    try {
        const res = await apiRequest(`/exec?cmd=${cmd}`, 'POST', {});
        notify(res.message || 'Ejecutado', 'success');
        if (cmd === 'init_system') loadTenants();
    } catch (e) { notify(e.message, 'error'); }
}

window.onload = () => {
    if (session.getToken()) {
        document.getElementById('login-screen').classList.add('hidden');
        document.getElementById('admin-dashboard').classList.remove('hidden');
        showModule('infra');
    }
};
