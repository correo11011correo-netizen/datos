const API_URL = 'http://localhost:8000';
const ADMIN_TOKEN = 'super-secret-admin-token';

async function apiRequest(endpoint, method = 'GET', body = null) {
    const options = {
        method,
        headers: {
            'Content-Type': 'application/json',
            'x-admin-token': ADMIN_TOKEN
        }
    };
    if (body) options.body = JSON.stringify(body);
    
    const response = await fetch(`${API_URL}${endpoint}`, options);
    if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail || 'Error en la petición');
    }
    return response.json();
}

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
        body.innerHTML = '<tr><td colspan="1">No hay datos</td></tr>';
        return;
    }

    // Extract keys from first item for headers
    const keys = Object.keys(data[0]);
    keys.forEach(k => head.innerHTML += `<th>${k}</th>`);

    data.forEach(row => {
        let tr = '<tr>';
        keys.forEach(k => tr += `<td>${row[k] || ''}</td>`);
        tr += '</tr>';
        body.innerHTML += tr;
    });
}
