// ============================================
// 1. SUPABASE CONFIGURATION (Declared ONCE)
// ============================================
const SUPABASE_URL = 'https://xmpafvuymrrxxnnpncsw.supabase.co';
const SUPABASE_ANON_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InhtcGFmdnV5bXJyeHhubnBuY3N3Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODQ2NDMwMjEsImV4cCI6MjEwMDIxOTAyMX0.3TKhT9SenGxMyNL-m-ObI22HQZidLBy9RHtr-_1Un_0';

// ============================================
// 2. SUPABASE CLIENT (Initialized ONCE - never redeclare)
// ============================================
const supabase = window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY);

// ============================================
// 3. APPLICATION STATE
// ============================================
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

// ============================================
// 4. DOM REFS
// ============================================
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

// ============================================
// 5. AUTH FUNCTIONS (Use the SINGLE supabase instance)
// ============================================
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

// ============================================
// 6. AUTH CHECK (Uses the SINGLE supabase instance)
// ============================================
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

// ============================================
// 7. DASHBOARD FUNCTIONS
// ============================================
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

// ============================================
// 8. API CALLS (Uses state.session for auth)
// ============================================
async function apiFetch(path, options = {}) {
    const url = `${state.apiUrl}${path}`;
    const headers = {
        'Content-Type': 'application/json',
        ...(options.headers || {}),
    };
    
    if (state.session?.access_token) {
        headers['Authorization'] = `Bearer ${state.session.access_token}`;
    }
    
    const res = await fetch(url, {
        ...options,
        headers,
    });
    
    if (res.status === 401) {
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

// ============================================
// 9. UI RENDER FUNCTIONS (Using textContent - SAFE)
// ============================================
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

    caseListEl.innerHTML = ''; // Clear

    state.cases.forEach(c => {
        const card = document.createElement('div');
        card.className = `case-card ${c.case_id === state.selectedCaseId ? 'active' : ''}`;
        card.dataset.caseId = c.case_id;
        card.addEventListener('click', () => {
            state.selectedCaseId = c.case_id;
            updateUI();
        });

        // Top row
        const topRow = document.createElement('div');
        topRow.className = 'top-row';

        const account = document.createElement('span');
        account.className = 'account-id';
        account.textContent = c.account_id;
        topRow.appendChild(account);

        const rightSide = document.createElement('div');
        rightSide.style.cssText = 'display:flex;align-items:center;gap:10px;';

        const risk = document.createElement('span');
        risk.className = 'risk-score';
        risk.textContent = `${(c.risk_score * 100).toFixed(1)}%`;
        rightSide.appendChild(risk);

        const status = document.createElement('span');
        status.className = `status-badge ${getStatusClass(c.status)}`;
        status.textContent = getStatusLabel(c.status);
        rightSide.appendChild(status);

        topRow.appendChild(rightSide);
        card.appendChild(topRow);

        // Bottom row
        const bottomRow = document.createElement('div');
        bottomRow.className = 'bottom-row';

        const reasonsDiv = document.createElement('div');
        reasonsDiv.className = 'reason-codes';
        
        const reasons = c.reason_codes || [];
        reasons.slice(0, 3).forEach(r => {
            const tag = document.createElement('span');
            tag.className = 'reason-tag';
            tag.textContent = r;
            reasonsDiv.appendChild(tag);
        });
        
        if (reasons.length > 3) {
            const tag = document.createElement('span');
            tag.className = 'reason-tag';
            tag.textContent = `+${reasons.length - 3}`;
            reasonsDiv.appendChild(tag);
        }
        
        bottomRow.appendChild(reasonsDiv);

        const time = document.createElement('span');
        time.className = 'time-ago';
        time.textContent = timeAgo(c.created_at);
        bottomRow.appendChild(time);

        card.appendChild(bottomRow);
        caseListEl.appendChild(card);
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

    detailPanelEl.innerHTML = '';
    
    const content = document.createElement('div');
    content.className = 'detail-content';

    // Header
    const header = document.createElement('div');
    header.className = 'detail-header';

    const headerLeft = document.createElement('div');
    
    const account = document.createElement('div');
    account.className = 'detail-account';
    account.textContent = c.account_id;
    headerLeft.appendChild(account);
    
    const caseId = document.createElement('div');
    caseId.className = 'detail-case-id';
    caseId.textContent = `Case: ${c.case_id.slice(0, 12)}...`;
    headerLeft.appendChild(caseId);
    
    const status = document.createElement('span');
    status.className = `status-badge ${getStatusClass(c.status)}`;
    status.style.cssText = 'display:inline-block;margin-top:6px;font-size:12px;';
    status.textContent = getStatusLabel(c.status);
    headerLeft.appendChild(status);
    
    header.appendChild(headerLeft);

    const risk = document.createElement('div');
    risk.className = 'detail-risk';
    risk.textContent = `${(c.risk_score * 100).toFixed(1)}%`;
    header.appendChild(risk);

    content.appendChild(header);

    // Reasons
    const reasonsSection = document.createElement('div');
    reasonsSection.className = 'detail-reasons';
    
    const reasonsTitle = document.createElement('h4');
    reasonsTitle.textContent = 'Reason Codes';
    reasonsSection.appendChild(reasonsTitle);
    
    const reasonsList = document.createElement('ul');
    const reasons = c.reason_codes || [];
    if (reasons.length === 0) {
        const li = document.createElement('li');
        li.textContent = 'No specific reasons';
        li.style.cssText = 'color:var(--text-dim);border-left-color:var(--text-dim);';
        reasonsList.appendChild(li);
    } else {
        reasons.forEach(r => {
            const li = document.createElement('li');
            li.textContent = r;
            reasonsList.appendChild(li);
        });
    }
    reasonsSection.appendChild(reasonsList);
    content.appendChild(reasonsSection);

    // Event details
    const event = c.event || {};
    const eventSection = document.createElement('div');
    eventSection.className = 'detail-event';
    
    const eventTitle = document.createElement('h4');
    eventTitle.textContent = 'Triggering Event';
    eventSection.appendChild(eventTitle);
    
    const fields = [
        ['Counterparty', event.counterparty_id || 'N/A'],
        ['Amount', `K${(event.amount || 0).toFixed(2)}`],
        ['Channel', event.channel || 'N/A'],
        ['Time', event.timestamp ? new Date(event.timestamp).toLocaleString() : 'N/A']
    ];
    
    fields.forEach(([label, value]) => {
        const row = document.createElement('div');
        row.className = 'event-row';
        
        const labelSpan = document.createElement('span');
        labelSpan.className = 'event-label';
        labelSpan.textContent = label;
        row.appendChild(labelSpan);
        
        const valueSpan = document.createElement('span');
        valueSpan.textContent = value;
        row.appendChild(valueSpan);
        
        eventSection.appendChild(row);
    });
    
    content.appendChild(eventSection);

    // Actions
    const actions = document.createElement('div');
    actions.className = 'detail-actions';
    
    const actionsList = [
        ['escalate', '🚨 Escalate', 'btn-action-escalate'],
        ['review', '🔍 Under Review', 'btn-action-review'],
        ['clear', '✓ Clear', 'btn-action-clear']
    ];
    
    actionsList.forEach(([action, label, className]) => {
        const btn = document.createElement('button');
        btn.className = `btn ${className}`;
        btn.textContent = label;
        btn.dataset.action = action;
        btn.addEventListener('click', async () => {
            await takeAction(c.case_id, action);
        });
        actions.appendChild(btn);
    });
    
    content.appendChild(actions);
    detailPanelEl.appendChild(content);
}

// ============================================
// 10. WEBSOCKET
// ============================================
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
            if (msg.type === 'new_case') {
                const c = msg.case;
                const show = !state.statusFilter || c.status === state.statusFilter;
                if (show) {
                    state.cases = [c, ...state.cases];
                    updateUI();
                } else {
                    state.cases = [c, ...state.cases];
                }
            } else if (msg.type === 'case_updated') {
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

// ============================================
// 11. INITIALIZATION (Only ONCE)
// ============================================
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
    
    refreshBtn.addEventListener('click', loadCases);
    
    apiUrlInput.addEventListener('change', () => {
        state.apiUrl = apiUrlInput.value;
        localStorage.setItem('zedshield_api_url', state.apiUrl);
        connectWebSocket();
        loadCases();
    });
    
    connectWebSocket();
    loadCases();
    
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

// ============================================
// 12. START (Uses the SINGLE supabase instance)
// ============================================
document.addEventListener('DOMContentLoaded', () => {
    // ✅ Uses the existing supabase instance - NO redeclaration
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
