// ===== Supabase Configuration =====
const SUPABASE_URL = 'https://xmpafvuymrrxxnnpncsw.supabase.co';
const SUPABASE_ANON_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InhtcGFmdnV5bXJyeHhubnBuY3N3Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODQ2NDMwMjEsImV4cCI6MjEwMDIxOTAyMX0.3TKhT9SenGxMyNL-m-ObI22HQZidLBy9RHtr-_1Un_0';

// Initialize Supabase client
const supabase = window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY);

// ===== State =====
let state = {
    cases: [],
    selectedCaseId: null,
    statusFilter: '',
    apiUrl: localStorage.getItem('zedshield_api_url') || 'https://zedshield.onrender.com',
    websocket: null,
    connected: false,
    user: null,
    session: null,
};

// ===== DOM Refs =====
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

const authScreen = $('#authScreen');
const dashboardScreen = $('#dashboardScreen');
const caseListEl = $('#caseList');
const detailPanelEl = $('#detailPanel');
const apiUrlInput = $('#apiUrl');
const refreshBtn = $('#refreshBtn');
const connectionBadge = $('#connectionBadge');
const userBadge = $('#userBadge');
const logoutBtn = $('#logoutBtn');

const statFlagged = $('#statFlagged');
const statReview = $('#statReview');
const statEscalated = $('#statEscalated');
const statCleared = $('#statCleared');

// Auth elements
const loginForm = $('#loginForm');
const signupForm = $('#signupForm');
const loginEmail = $('#loginEmail');
const loginPassword = $('#loginPassword');
const loginBtn = $('#loginBtn');
const signupEmail = $('#signupEmail');
const signupPassword = $('#signupPassword');
const signupName = $('#signupName');
const signupBtn = $('#signupBtn');
const showSignup = $('#showSignup');
const showLogin = $('#showLogin');
const authMessage = $('#authMessage');

// ===== Auth =====
function showAuthMessage(msg, isError = true) {
    authMessage.style.display = 'block';
    authMessage.textContent = msg;
    authMessage.style.color = isError ? '#ff6b6b' : '#33ff99';
}

function toggleAuthForms(showLoginForm) {
    loginForm.style.display = showLoginForm ? 'block' : 'none';
    signupForm.style.display = showLoginForm ? 'none' : 'block';
    authMessage.style.display = 'none';
}

// Login
loginBtn.addEventListener('click', async () => {
    const email = loginEmail.value;
    const password = loginPassword.value;
    if (!email || !password) {
        showAuthMessage('Please enter email and password');
        return;
    }
    
    try {
        const { data, error } = await supabase.auth.signInWithPassword({
            email,
            password,
        });
        if (error) throw error;
        state.user = data.user;
        state.session = data.session;
        showAuthMessage('Login successful!', false);
        setTimeout(initDashboard, 500);
    } catch (err) {
        showAuthMessage(err.message);
    }
});

// Signup
signupBtn.addEventListener('click', async () => {
    const email = signupEmail.value;
    const password = signupPassword.value;
    const name = signupName.value;
    if (!email || !password || !name) {
        showAuthMessage('Please fill in all fields');
        return;
    }
    
    try {
        const { data, error } = await supabase.auth.signUp({
            email,
            password,
            options: {
                data: { full_name: name },
            },
        });
        if (error) throw error;
        showAuthMessage('Account created! Please check your email to confirm.', false);
        setTimeout(() => toggleAuthForms(true), 2000);
    } catch (err) {
        showAuthMessage(err.message);
    }
});

// Toggle
showSignup.addEventListener('click', (e) => {
    e.preventDefault();
    toggleAuthForms(false);
});
showLogin.addEventListener('click', (e) => {
    e.preventDefault();
    toggleAuthForms(true);
});

// Logout
logoutBtn.addEventListener('click', async () => {
    await supabase.auth.signOut();
    state.user = null;
    state.session = null;
    showAuthScreen();
});

// ===== Auth Check =====
async function checkAuth() {
    const { data: { session } } = await supabase.auth.getSession();
    if (session) {
        state.session = session;
        state.user = session.user;
        return true;
    }
    return false;
}

function showAuthScreen() {
    authScreen.style.display = 'flex';
    dashboardScreen.style.display = 'none';
    toggleAuthForms(true);
}

function showDashboard() {
    authScreen.style.display = 'none';
    dashboardScreen.style.display = 'block';
    userBadge.textContent = state.user?.email?.split('@')[0] || 'User';
}

// ===== Dashboard Functions =====
function timeAgo(dateStr) {
    const diff = Date.now() - new Date(dateStr).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return 'just now';
    if (mins < 60) return `${mins}m ago`;
    const hours = Math.floor(mins / 60);
    if (hours < 24) return `${hours}h ago`;
    return `${Math.floor(hours / 24)}d ago`;
}

function getStatusLabel(status) {
    const map = {
        'flagged': 'Flagged',
        'under_review': 'Under Review',
        'escalated': 'Escalated',
        'cleared': 'Cleared',
    };
    return map[status] || status;
}

function getStatusClass(status) {
    return status || 'flagged';
}

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str ?? '';
    return div.innerHTML;
}

// ===== API Calls =====
async function apiFetch(path, options = {}) {
    const url = `${state.apiUrl}${path}`;
    const headers = {
        'Content-Type': 'application/json',
        ...(options.headers || {}),
    };
    
    // Add auth token if available
    if (state.session?.access_token) {
        headers['Authorization'] = `Bearer ${state.session.access_token}`;
    }
    
    const res = await fetch(url, {
        ...options,
        headers,
    });
    
    if (res.status === 401) {
        // Auth expired - redirect to login
        await supabase.auth.signOut();
        showAuthScreen();
        throw new Error('Session expired');
    }
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
}

async function loadCases() {
    try {
        const statusParam = state.statusFilter ? `?status=${state.statusFilter}` : '';
        const data = await apiFetch(`/cases${statusParam}`);
        state.cases = data;
        updateUI();
    } catch (err) {
        console.error('Failed to load cases:', err);
        caseListEl.innerHTML = `
            <div class="empty-state">
                <p>⚠️ Failed to load cases. ${err.message}</p>
                <p style="font-size:13px;margin-top:8px;">Make sure the backend is running at ${state.apiUrl}</p>
            </div>
        `;
    }
}

async function takeAction(caseId, action) {
    try {
        const statusMap = { 'escalate': 'escalated', 'review': 'under_review', 'clear': 'cleared' };
        const newStatus = statusMap[action];
        if (newStatus) {
            const c = state.cases.find(c => c.case_id === caseId);
            if (c) c.status = newStatus;
            updateUI();
        }
        await apiFetch(`/cases/${caseId}/action`, {
            method: 'POST',
            body: JSON.stringify({ action }),
        });
    } catch (err) {
        console.error('Action failed:', err);
        await loadCases();
    }
}

// ===== UI Updates =====
function updateUI() {
    renderCaseList();
    renderStats();
    renderDetail();
}

function renderCaseList() {
    if (state.cases.length === 0) {
        caseListEl.innerHTML = `
            <div class="empty-state">
                <p>No cases yet. Events will appear here when flagged.</p>
                <p style="font-size:13px;margin-top:8px;color:var(--text-dim);">
                    Run demo_replay.py to generate test cases
                </p>
            </div>
        `;
        return;
    }

    caseListEl.innerHTML = state.cases.map(c => `
        <div class="case-card ${c.case_id === state.selectedCaseId ? 'active' : ''}"
             data-case-id="${escapeHtml(c.case_id)}">
            <div class="top-row">
                <span class="account-id">${escapeHtml(c.account_id)}</span>
                <div style="display:flex;align-items:center;gap:10px;">
                    <span class="risk-score">${(c.risk_score * 100).toFixed(1)}%</span>
                    <span class="status-badge ${getStatusClass(c.status)}">${escapeHtml(getStatusLabel(c.status))}</span>
                </div>
            </div>
            <div class="bottom-row">
                <div class="reason-codes">
                    ${(c.reason_codes || []).slice(0, 3).map(r => `<span class="reason-tag">${escapeHtml(r)}</span>`).join('')}
                    ${(c.reason_codes || []).length > 3 ? `<span class="reason-tag">+${c.reason_codes.length - 3}</span>` : ''}
                </div>
                <span class="time-ago">${escapeHtml(timeAgo(c.created_at))}</span>
            </div>
        </div>
    `).join('');

    caseListEl.querySelectorAll('.case-card').forEach(el => {
        el.addEventListener('click', () => {
            state.selectedCaseId = el.dataset.caseId;
            updateUI();
        });
    });
}

function renderStats() {
    const flagged = state.cases.filter(c => c.status === 'flagged').length;
    const review = state.cases.filter(c => c.status === 'under_review').length;
    const escalated = state.cases.filter(c => c.status === 'escalated').length;
    const cleared = state.cases.filter(c => c.status === 'cleared').length;
    
    statFlagged.textContent = flagged;
    statReview.textContent = review;
    statEscalated.textContent = escalated;
    statCleared.textContent = cleared;
}

function renderDetail() {
    if (!state.selectedCaseId) {
        detailPanelEl.innerHTML = `
            <div class="empty-detail">
                <p>Select a case to view details</p>
            </div>
        `;
        return;
    }

    const c = state.cases.find(c => c.case_id === state.selectedCaseId);
    if (!c) {
        detailPanelEl.innerHTML = `
            <div class="empty-detail">
                <p>Case not found</p>
            </div>
        `;
        return;
    }

    const event = c.event || {};
    detailPanelEl.innerHTML = `
        <div class="detail-content">
            <div class="detail-header">
                <div>
                    <div class="detail-account">${escapeHtml(c.account_id)}</div>
                    <div class="detail-case-id">Case: ${escapeHtml(c.case_id.slice(0, 12))}...</div>
                    <span class="status-badge ${getStatusClass(c.status)}" style="display:inline-block;margin-top:6px;font-size:12px;">
                        ${escapeHtml(getStatusLabel(c.status))}
                    </span>
                </div>
                <div class="detail-risk">${(c.risk_score * 100).toFixed(1)}%</div>
            </div>

            <div class="detail-reasons">
                <h4>Reason Codes</h4>
                <ul>
                    ${(c.reason_codes || []).map(r => `<li>${escapeHtml(r)}</li>`).join('')}
                    ${(c.reason_codes || []).length === 0 ? '<li style="color:var(--text-dim);border-left-color:var(--text-dim);">No specific reasons</li>' : ''}
                </ul>
            </div>

            <div class="detail-event">
                <h4>Triggering Event</h4>
                <div class="event-row">
                    <span class="event-label">Counterparty</span>
                    <span>${escapeHtml(event.counterparty_id) || 'N/A'}</span>
                </div>
                <div class="event-row">
                    <span class="event-label">Amount</span>
                    <span>K${(event.amount || 0).toFixed(2)}</span>
                </div>
                <div class="event-row">
                    <span class="event-label">Channel</span>
                    <span>${escapeHtml(event.channel) || 'N/A'}</span>
                </div>
                <div class="event-row">
                    <span class="event-label">Time</span>
                    <span>${event.timestamp ? new Date(event.timestamp).toLocaleString() : 'N/A'}</span>
                </div>
            </div>

            <div class="detail-actions">
                <button class="btn btn-action-escalate" data-action="escalate">🚨 Escalate</button>
                <button class="btn btn-action-review" data-action="review">🔍 Under Review</button>
                <button class="btn btn-action-clear" data-action="clear">✓ Clear</button>
            </div>
        </div>
    `;

    detailPanelEl.querySelectorAll('[data-action]').forEach(btn => {
        btn.addEventListener('click', async () => {
            const action = btn.dataset.action;
            await takeAction(c.case_id, action);
        });
    });
}

// ===== WebSocket =====
function connectWebSocket() {
    if (state.websocket) {
        state.websocket.close();
    }

    const wsUrl = state.apiUrl.replace('http://', 'ws://').replace('https://', 'wss://');
    const ws = new WebSocket(`${wsUrl}/ws/dashboard`);
    state.websocket = ws;

    ws.onopen = () => {
        state.connected = true;
        connectionBadge.textContent = '● Live';
        connectionBadge.className = 'connection-badge';
        console.log('WebSocket connected');
    };

    ws.onmessage = (event) => {
        try {
            const msg = JSON.parse(event.data);
            if (msg.type === 'new_case' && msg.case && typeof msg.case === 'object' && msg.case.case_id) {
                const c = msg.case;
                const show = !state.statusFilter || c.status === state.statusFilter;
                if (show) {
                    state.cases = [c, ...state.cases];
                    updateUI();
                } else {
                    state.cases = [c, ...state.cases];
                }
            } else if (msg.type === 'case_updated' && msg.case_id) {
                const c = state.cases.find(c => c.case_id === msg.case_id);
                if (c) {
                    c.status = msg.status;
                    const show = !state.statusFilter || c.status === state.statusFilter;
                    if (!show) {
                        state.cases = state.cases.filter(c => c.case_id !== msg.case_id);
                    }
                    updateUI();
                }
            }
        } catch (err) {
            console.error('WebSocket message error:', err);
        }
    };

    ws.onclose = () => {
        state.connected = false;
        connectionBadge.textContent = '● Offline';
        connectionBadge.className = 'connection-badge offline';
        console.log('WebSocket disconnected, reconnecting in 3s...');
        setTimeout(connectWebSocket, 3000);
    };
    
    ws.onerror = (err) => {
        console.error('WebSocket error:', err);
        ws.close();
    };
}

// ===== Init Dashboard =====
function initDashboard() {
    apiUrlInput.value = state.apiUrl;
    
    // Filters
    document.querySelectorAll('.filter-tab').forEach(tab => {
        tab.addEventListener('click', () => {
            document.querySelectorAll('.filter-tab').forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            state.statusFilter = tab.dataset.status;
            loadCases();
        });
    });
    
    // Refresh
    refreshBtn.addEventListener('click', loadCases);
    
    // API URL
    apiUrlInput.addEventListener('change', () => {
        state.apiUrl = apiUrlInput.value;
        localStorage.setItem('zedshield_api_url', state.apiUrl);
        connectWebSocket();
        loadCases();
    });
    
    connectWebSocket();
    loadCases();
    
    // Periodic refresh fallback
    setInterval(() => {
        if (!state.connected) {
            loadCases();
        }
    }, 30000);
    
    showDashboard();
}

async function initDashboardWithAuth() {
    const hasSession = await checkAuth();
    if (hasSession) {
        initDashboard();
    } else {
        showAuthScreen();
    }
}

// ===== Start =====
document.addEventListener('DOMContentLoaded', () => {
    // Listen for auth state changes
    supabase.auth.onAuthStateChange((event, session) => {
        if (event === 'SIGNED_IN' && session) {
            state.session = session;
            state.user = session.user;
            initDashboard();
        } else if (event === 'SIGNED_OUT') {
            showAuthScreen();
        }
    });
    
    initDashboardWithAuth();
});
