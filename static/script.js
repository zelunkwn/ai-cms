// Navigation Logic
function showSection(sectionId) {
    document.querySelectorAll('.section').forEach(el => el.classList.remove('active'));
    document.querySelectorAll('.nav-links li').forEach(el => el.classList.remove('active'));
    
    document.getElementById(sectionId).classList.add('active');
    event.target.classList.add('active');

    if(sectionId === 'dashboard') loadStats();
    if(sectionId === 'list') loadApis();
}

// Load Stats
async function loadStats() {
    const res = await fetch('/api/cms/stats');
    const data = await res.json();
    
    document.getElementById('stat-calls').innerText = data.total_calls;
    document.getElementById('stat-tokens').innerText = data.total_tokens;
    document.getElementById('stat-cost').innerText = '$' + data.total_cost.toFixed(4);
    document.getElementById('stat-apis').innerText = data.active_apis;
}

// Create API
document.getElementById('create-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const payload = {
        route: document.getElementById('api-route').value,
        model: document.getElementById('api-model').value,
        prompt: document.getElementById('api-prompt').value
    };

    const res = await fetch('/api/cms/create', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload)
    });

    if(res.ok) {
        alert('API Created! You can now POST to: http://localhost:5000/user-api/' + payload.route);
        document.getElementById('create-form').reset();
        showSection('list');
    }
});

async function loadLogs() {
    const res = await fetch('/api/cms/logs');
    const logs = await res.json();
    const container = document.getElementById('logs-container');
    
    if (logs.length === 0) {
        container.innerHTML = '<p class="sub-text">No API calls yet</p>';
        return;
    }
    
    let html = '<table style="width:100%; font-size:0.85rem;">';
    html += '<tr><th>Time</th><th>Tokens</th><th>Latency</th><th>Cost</th></tr>';
    
    logs.slice(0, 10).forEach(log => {
        html += `
            <tr>
                <td>${log.timestamp.split(' ')[1]}</td>
                <td>${log.tokens_used}</td>
                <td>${log.latency}s</td>
                <td>$${log.cost}</td>
            </tr>
        `;
    });
    
    html += '</table>';
    container.innerHTML = html;
}

// Update showSection function to load logs
function showSection(sectionId) {
    document.querySelectorAll('.section').forEach(el => el.classList.remove('active'));
    document.querySelectorAll('.nav-links li').forEach(el => el.classList.remove('active'));
    
    document.getElementById(sectionId).classList.add('active');
    event.target.classList.add('active');

    if(sectionId === 'dashboard') {
        loadStats();
        loadLogs();
    }
    if(sectionId === 'list') loadApis();
}

// Load API List
async function loadApis() {
    const res = await fetch('/api/cms/list');
    const apis = await res.json();
    const tbody = document.getElementById('api-table-body');
    
    tbody.innerHTML = '';
    
    apis.forEach(api => {
        const row = `
            <tr>
                <td><span class="endpoint-url">/user-api/${api.route}</span></td>
                <td>${api.model}</td>
                <td>${api.total_calls}</td>
                <td>
                    <button onclick="testApi('${api.route}')" style="padding:5px; cursor:pointer;">Test</button>
                    <button onclick="deleteApi(${api.id})" style="padding:5px; cursor:pointer; color:red;">Delete</button>
                </td>
            </tr>
        `;
        tbody.innerHTML += row;
    });
}

// Add delete function
async function deleteApi(id) {
    if(confirm('Are you sure you want to delete this API?')) {
        await fetch(`/api/cms/delete/${id}`, { method: 'DELETE' });
        loadApis();
        loadStats();
    }
}

// API Keys Functions
async function loadKeys() {
    const res = await fetch('/api/cms/keys');
    const keys = await res.json();
    const tbody = document.getElementById('keys-table-body');
    
    tbody.innerHTML = '';
    
    keys.forEach(key => {
        const row = `
            <tr>
                <td>${key.name}</td>
                <td><code style="background:#eee; padding:2px 6px; font-size:0.75rem;">${key.key}</code></td>
                <td>${key.usage_count}</td>
                <td><span style="color:${key.is_active ? 'green' : 'red'}">● ${key.is_active ? 'Active' : 'Inactive'}</span></td>
                <td>
                    <button onclick="toggleKey(${key.id})" style="padding:5px; cursor:pointer;">${key.is_active ? 'Deactivate' : 'Activate'}</button>
                    <button onclick="deleteKey(${key.id})" style="padding:5px; cursor:pointer; color:red;">Delete</button>
                </td>
            </tr>
        `;
        tbody.innerHTML += row;
    });
}

async function createKey() {
    const name = document.getElementById('key-name').value || 'Unnamed Key';
    
    const res = await fetch('/api/cms/keys', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({name})
    });
    
    const data = await res.json();
    
    if (res.ok) {
        alert('New API Key Generated:\n\n' + data.key + '\n\nSave this key! It won\'t be shown again.');
        document.getElementById('key-name').value = '';
        loadKeys();
    }
}

async function toggleKey(id) {
    await fetch(`/api/cms/keys/${id}/toggle`, {method: 'POST'});
    loadKeys();
}

async function deleteKey(id) {
    if(confirm('Delete this API Key?')) {
        await fetch(`/api/cms/keys/${id}`, {method: 'DELETE'});
        loadKeys();
    }
}

// Export Function
function exportLogs() {
    window.open('/api/cms/export', '_blank');
}

// Update showSection to handle keys
function showSection(sectionId) {
    document.querySelectorAll('.section').forEach(el => el.classList.remove('active'));
    document.querySelectorAll('.nav-links li').forEach(el => el.classList.remove('active'));
    
    document.getElementById(sectionId).classList.add('active');
    event.target.classList.add('active');

    if(sectionId === 'dashboard') {
        loadStats();
        loadLogs();
    }
    if(sectionId === 'list') loadApis();
    if(sectionId === 'keys') loadKeys();
}

// Simple Test Function
async function testApi(route) {
    const res = await fetch(`/user-api/${route}`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({test: "data"})
    });
    const data = await res.json();
    alert("Response:\n" + JSON.stringify(data, null, 2));
}

// Initial Load
loadStats();