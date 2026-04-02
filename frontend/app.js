// === State ===
let token = localStorage.getItem('ats_token');
let currentUser = JSON.parse(localStorage.getItem('ats_user') || 'null');
let candidates = [];
let currentCandidateId = null;
let calendarWeekStart = getMonday(new Date());

const STATUSES = ['Новый', 'Резюме рассмотрено', 'Запрос информации', 'Тестовое задание', 'Интервью', 'Оффер', 'Принят', 'Отказ'];
const STATUS_CLASSES = {
    'Новый': 'status-new', 'Резюме рассмотрено': 'status-reviewed',
    'Запрос информации': 'status-test',
    'Тестовое задание': 'status-test', 'Интервью': 'status-interview',
    'Оффер': 'status-offer', 'Принят': 'status-hired', 'Отказ': 'status-rejected'
};
const WEEKDAYS = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'];

// === API ===
async function api(path, opts = {}) {
    const headers = { ...(opts.headers || {}) };
    if (token) headers['Authorization'] = `Bearer ${token}`;
    if (opts.body && !(opts.body instanceof FormData)) {
        headers['Content-Type'] = 'application/json';
        opts.body = JSON.stringify(opts.body);
    }
    const res = await fetch(path, { ...opts, headers });
    if (res.status === 401) { logout(); throw new Error('Unauthorized'); }
    if (!res.ok) { const e = await res.json().catch(() => ({})); throw new Error(e.detail || 'Error'); }
    return res.json();
}

// === Auth ===
document.getElementById('login-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const username = document.getElementById('login-username').value;
    const password = document.getElementById('login-password').value;
    try {
        const data = await api('/api/auth/login', { method: 'POST', body: { username, password } });
        token = data.access_token;
        currentUser = data.user;
        localStorage.setItem('ats_token', token);
        localStorage.setItem('ats_user', JSON.stringify(currentUser));
        showApp();
    } catch (err) {
        document.getElementById('login-error').textContent = err.message;
    }
});

function logout() {
    token = null; currentUser = null;
    localStorage.removeItem('ats_token');
    localStorage.removeItem('ats_user');
    document.getElementById('login-page').classList.add('active');
    document.getElementById('main-app').classList.remove('active');
}

document.getElementById('logout-btn').addEventListener('click', logout);

function showApp() {
    document.getElementById('login-page').classList.remove('active');
    document.getElementById('main-app').classList.add('active');
    document.getElementById('current-user').textContent = currentUser.display_name;
    loadCandidates();
}

// === Theme ===
const savedTheme = localStorage.getItem('ats_theme') || 'light';
document.documentElement.setAttribute('data-theme', savedTheme);
updateThemeBtn();

document.getElementById('theme-toggle').addEventListener('click', () => {
    const current = document.documentElement.getAttribute('data-theme');
    const next = current === 'light' ? 'dark' : 'light';
    document.documentElement.setAttribute('data-theme', next);
    localStorage.setItem('ats_theme', next);
    updateThemeBtn();
});

function updateThemeBtn() {
    const theme = document.documentElement.getAttribute('data-theme');
    document.getElementById('theme-toggle').textContent = theme === 'light' ? '🌙' : '☀️';
}

// === Navigation ===
document.querySelectorAll('.nav-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
        document.getElementById(`${btn.dataset.view}-view`).classList.add('active');
        if (btn.dataset.view === 'calendar') renderCalendar();
    });
});

// === Load Candidates ===
async function loadCandidates() {
    try {
        candidates = await api('/api/candidates');
        renderKanban();
        renderTable();
        updatePositionFilter();
        loadTodayMeetings();
        loadInfoRequests();
    } catch (err) { console.error(err); }
}

// === Today Meetings Widget ===
async function loadTodayMeetings() {
    const widget = document.getElementById('today-meetings-widget');
    try {
        const today = new Date().toISOString().split('T')[0];
        const meetings = await api(`/api/meetings?date_from=${today}&date_to=${today}`);
        if (meetings.length === 0) {
            widget.innerHTML = '';
            return;
        }
        widget.innerHTML = `
            <div class="today-widget">
                <div class="today-widget-title">Встречи сегодня (${meetings.length})</div>
                ${meetings.map(m => `
                    <div class="today-widget-item" onclick="openCandidateDetail(${m.candidate_id})">
                        <span class="tw-time">${esc(m.meeting_time || '—')}</span>
                        <span class="tw-name">${esc(m.candidate_name)}</span>
                        <span class="tw-pos">${esc(m.candidate_position || '')}</span>
                        <span class="tw-format">${esc(m.format)}</span>
                    </div>
                `).join('')}
            </div>
        `;
    } catch (err) {
        widget.innerHTML = '';
    }
}

// === Info Requests Widget ===
async function loadInfoRequests() {
    const container = document.getElementById('today-meetings-widget');
    try {
        const requests = await api('/api/info-requests');
        if (requests.length === 0) return;
        // Append after today meetings
        const widget = document.createElement('div');
        widget.className = 'today-widget';
        widget.style.borderLeftColor = 'var(--warning)';
        widget.innerHTML = `
            <div class="today-widget-title" style="color:var(--warning)">Запросы информации (${requests.length})</div>
            ${requests.map(r => {
                const text = (r.request_text || '').replace('**Запрос информации:**\n', '').substring(0, 80);
                return `
                <div class="today-widget-item" onclick="openCandidateDetail(${r.id})">
                    <span class="tw-name">${esc(r.full_name)}</span>
                    <span class="tw-pos">${esc(r.position || '')}</span>
                    <span style="font-size:0.8rem;color:var(--text-secondary);flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(text)}</span>
                </div>`;
            }).join('')}
        `;
        container.appendChild(widget);
    } catch (err) { /* silent */ }
}

// === Kanban ===
function renderKanban() {
    const board = document.getElementById('kanban-board');
    board.innerHTML = '';
    STATUSES.forEach(status => {
        const items = candidates.filter(c => c.status === status);
        const col = document.createElement('div');
        col.className = 'kanban-column';
        col.innerHTML = `
            <div class="kanban-column-header">
                <span>${status}</span>
                <span class="count">${items.length}</span>
            </div>
            <div class="kanban-cards" data-status="${status}"></div>
        `;
        const cards = col.querySelector('.kanban-cards');

        cards.addEventListener('dragover', e => { e.preventDefault(); cards.classList.add('drag-over'); });
        cards.addEventListener('dragleave', () => cards.classList.remove('drag-over'));
        cards.addEventListener('drop', async (e) => {
            e.preventDefault();
            cards.classList.remove('drag-over');
            const cid = e.dataTransfer.getData('text/plain');
            if (cid) {
                try {
                    await api(`/api/candidates/${cid}/status`, { method: 'PATCH', body: { status } });
                    loadCandidates();
                } catch (err) { console.error(err); }
            }
        });

        items.forEach(c => {
            const card = document.createElement('div');
            card.className = 'kanban-card';
            card.draggable = true;
            card.addEventListener('dragstart', (e) => {
                e.dataTransfer.setData('text/plain', c.id);
                card.classList.add('dragging');
            });
            card.addEventListener('dragend', () => card.classList.remove('dragging'));
            card.addEventListener('click', () => openCandidateDetail(c.id));
            const us = c.user_scores || {};
            const ut = c.user_trends || {};
            const trendIcon = t => t === 'up' ? '↑' : t === 'down' ? '↓' : '→';
            const trendColor = t => t === 'up' ? 'var(--success)' : t === 'down' ? 'var(--danger)' : 'var(--text-secondary)';
            const miniStars = (score) => score ? '<span style="color:var(--warning)">' + '★'.repeat(score) + '☆'.repeat(5-score) + '</span>' : '<span style="color:var(--border)">☆☆☆☆☆</span>';
            const divergent = c.score_divergence > 2;
            card.innerHTML = `
                <div style="display:flex;justify-content:space-between;align-items:start">
                    <div class="card-name">${esc(c.full_name)}</div>
                    <div style="display:flex;gap:0.15rem">
                        <button class="btn btn-ghost btn-sm card-rate-btn" style="padding:0.1rem 0.3rem;font-size:0.75rem;line-height:1" data-cid="${c.id}" title="Оценить">★</button>
                        <button class="btn btn-ghost btn-sm card-menu-btn" style="padding:0.1rem 0.3rem;font-size:0.9rem;line-height:1" data-cid="${c.id}">⋮</button>
                    </div>
                </div>
                <div class="card-position">${esc(c.position || '—')}</div>
                <div style="font-size:0.7rem;margin-top:0.35rem;line-height:1.4">
                    ${us.venera ? `<div>V: ${miniStars(us.venera)} <span style="color:${trendColor(ut.venera)};font-weight:600">${trendIcon(ut.venera)}</span></div>` : ''}
                    ${us.dmitry ? `<div>D: ${miniStars(us.dmitry)} <span style="color:${trendColor(ut.dmitry)};font-weight:600">${trendIcon(ut.dmitry)}</span></div>` : ''}
                    ${!us.venera && !us.dmitry ? '<div style="color:var(--border)">Нет оценок</div>' : ''}
                </div>
                <div class="card-meta">
                    <span>${formatDate(c.last_activity)}</span>
                    ${c.stage_avg ? `<span style="font-weight:600">${c.stage_avg}</span>` : ''}
                </div>
            `;
            if (divergent) card.style.borderColor = 'var(--warning)';
            card.querySelector('.card-menu-btn').addEventListener('click', (e) => {
                e.stopPropagation();
                showCardContextMenu(e, c.id, c.full_name, c.status);
            });
            card.querySelector('.card-rate-btn').addEventListener('click', (e) => {
                e.stopPropagation();
                showQuickRate(e, c.id, c.status);
            });
            cards.appendChild(card);
        });
        board.appendChild(col);
    });
}

// === Context Menu & Quick Actions ===
function showCardContextMenu(e, cid, name, currentStatus) {
    // Remove any existing menu
    document.querySelectorAll('.card-context-menu').forEach(m => m.remove());
    const menu = document.createElement('div');
    menu.className = 'card-context-menu';
    const actions = [
        { label: 'Резюме рассмотрено', status: 'Резюме рассмотрено' },
        { label: 'Запросить информацию', status: 'Запрос информации', needsNote: true },
        { label: 'Отправить тестовое', status: 'Тестовое задание', needsNote: true },
        { label: 'Назначить интервью', status: 'Интервью', openMeeting: true },
        { label: 'Оффер', status: 'Оффер' },
        { label: 'Отказ', status: 'Отказ' },
    ].filter(a => a.status !== currentStatus);

    menu.innerHTML = actions.map(a =>
        `<div class="ctx-item" data-status="${a.status}" data-needs-note="${a.needsNote||''}" data-open-meeting="${a.openMeeting||''}">${a.label}</div>`
    ).join('');
    menu.style.position = 'fixed';
    menu.style.left = e.clientX + 'px';
    menu.style.top = e.clientY + 'px';
    document.body.appendChild(menu);

    menu.querySelectorAll('.ctx-item').forEach(item => {
        item.addEventListener('click', async () => {
            menu.remove();
            const status = item.dataset.status;
            const needsNote = item.dataset.needsNote === 'true';
            const openMeeting = item.dataset.openMeeting === 'true';
            await quickStatusChange(cid, status, needsNote, openMeeting);
        });
    });

    const closeMenu = (ev) => { if (!menu.contains(ev.target)) { menu.remove(); document.removeEventListener('click', closeMenu); }};
    setTimeout(() => document.addEventListener('click', closeMenu), 0);
}

async function quickStatusChange(cid, status, needsNote, openMeeting) {
    let note = '';
    if (needsNote) {
        const prompts = {
            'Запрос информации': 'Что запросить у кандидата?',
            'Тестовое задание': 'Описание тестового задания:',
        };
        note = prompt(prompts[status] || 'Комментарий:');
        if (note === null) return; // cancelled
    }
    await api(`/api/candidates/${cid}/status`, { method: 'PATCH', body: { status, note } });
    loadCandidates();
    if (openMeeting) {
        openCandidateDetail(cid);
        // Wait for modal to render, then switch to meetings tab and open form
        setTimeout(() => {
            const meetTab = document.querySelector('[data-tab="meetings"]');
            if (meetTab) meetTab.click();
            setTimeout(() => {
                const section = document.getElementById('meeting-form-section');
                if (section) section.open = true;
            }, 200);
        }, 500);
    }
}

// === Quick Rate Popup ===
function statusToStage(status) {
    const map = {'Резюме рассмотрено': 'resume', 'Запрос информации': 'resume', 'Тестовое задание': 'test', 'Интервью': 'interview', 'Оффер': 'offer', 'Принят': 'offer'};
    return map[status] || 'resume';
}

function showQuickRate(e, cid, status) {
    document.querySelectorAll('.quick-rate-popup').forEach(m => m.remove());
    const stage = statusToStage(status);
    const stageLabels = {resume:'Резюме', test:'Тестовое', interview:'Интервью', offer:'Итоговая'};
    const popup = document.createElement('div');
    popup.className = 'quick-rate-popup';
    popup.style.cssText = `position:fixed;left:${e.clientX}px;top:${e.clientY}px;z-index:1001;background:var(--bg-card);border:1px solid var(--border);border-radius:var(--radius);box-shadow:var(--shadow-lg);padding:0.75rem;min-width:220px`;
    popup.innerHTML = `
        <div style="font-size:0.8rem;color:var(--text-secondary);margin-bottom:0.35rem">${stageLabels[stage] || stage}</div>
        <div class="stars qr-stars" style="font-size:1.5rem;cursor:pointer">
            ${[1,2,3,4,5].map(i => `<span class="star" data-s="${i}">☆</span>`).join('')}
        </div>
        <input type="text" class="qr-comment" placeholder="Комментарий (необязательно)" style="margin-top:0.5rem;font-size:0.8rem">
        <button class="btn btn-primary btn-sm qr-save" style="margin-top:0.5rem;width:100%" disabled>Сохранить</button>
    `;
    document.body.appendChild(popup);
    let score = 0;
    popup.querySelectorAll('.qr-stars .star').forEach(star => {
        star.addEventListener('click', () => {
            score = parseInt(star.dataset.s);
            popup.querySelectorAll('.qr-stars .star').forEach((s, i) => {
                s.textContent = i < score ? '★' : '☆';
                s.style.color = i < score ? 'var(--warning)' : '';
            });
            popup.querySelector('.qr-save').disabled = false;
        });
    });
    popup.querySelector('.qr-save').addEventListener('click', async () => {
        const comment = popup.querySelector('.qr-comment').value;
        await api(`/api/candidates/${cid}/ratings/stages`, { method: 'POST', body: { stage, score, comment } });
        popup.remove();
        loadCandidates();
    });
    const closePopup = (ev) => { if (!popup.contains(ev.target)) { popup.remove(); document.removeEventListener('click', closePopup); }};
    setTimeout(() => document.addEventListener('click', closePopup), 0);
}

// === Calendar ===
function getMonday(d) {
    const date = new Date(d);
    const day = date.getDay();
    const diff = date.getDate() - day + (day === 0 ? -6 : 1);
    date.setDate(diff);
    date.setHours(0, 0, 0, 0);
    return date;
}

function formatISODate(d) {
    return d.toISOString().split('T')[0];
}

async function renderCalendar() {
    const grid = document.getElementById('calendar-grid');
    const label = document.getElementById('cal-week-label');

    const weekEnd = new Date(calendarWeekStart);
    weekEnd.setDate(weekEnd.getDate() + 6);

    const monthNames = ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня',
                        'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря'];
    label.textContent = `${calendarWeekStart.getDate()} ${monthNames[calendarWeekStart.getMonth()]} — ${weekEnd.getDate()} ${monthNames[weekEnd.getMonth()]} ${weekEnd.getFullYear()}`;

    const dateFrom = formatISODate(calendarWeekStart);
    const dateTo = formatISODate(weekEnd);

    let meetings = [];
    try {
        meetings = await api(`/api/meetings?date_from=${dateFrom}&date_to=${dateTo}`);
    } catch (err) { console.error(err); }

    const today = formatISODate(new Date());

    grid.innerHTML = '';
    for (let i = 0; i < 7; i++) {
        const date = new Date(calendarWeekStart);
        date.setDate(date.getDate() + i);
        const dateStr = formatISODate(date);
        const dayMeetings = meetings.filter(m => m.meeting_date === dateStr);
        const isToday = dateStr === today;

        const col = document.createElement('div');
        col.className = `cal-day${isToday ? ' cal-today' : ''}`;
        col.innerHTML = `
            <div class="cal-day-header">
                <span class="cal-weekday">${WEEKDAYS[i]}</span>
                <span class="cal-day-num">${date.getDate()}</span>
            </div>
            ${dayMeetings.map(m => `
                <div class="cal-event" onclick="openCandidateDetail(${m.candidate_id})" title="${esc(m.candidate_name)} — ${esc(m.meeting_time || '')} ${esc(m.format)}">
                    ${esc(m.meeting_time || '—')} ${esc(m.candidate_name)}
                </div>
            `).join('')}
        `;
        grid.appendChild(col);
    }
}

document.getElementById('cal-prev').addEventListener('click', () => {
    calendarWeekStart.setDate(calendarWeekStart.getDate() - 7);
    renderCalendar();
});
document.getElementById('cal-next').addEventListener('click', () => {
    calendarWeekStart.setDate(calendarWeekStart.getDate() + 7);
    renderCalendar();
});
document.getElementById('cal-today').addEventListener('click', () => {
    calendarWeekStart = getMonday(new Date());
    renderCalendar();
});

// === Table ===
function renderTable() {
    const tbody = document.getElementById('candidates-tbody');
    const search = document.getElementById('search-input').value.toLowerCase();
    const statusFilter = document.getElementById('filter-status').value;
    const posFilter = document.getElementById('filter-position').value;

    let filtered = candidates.filter(c => {
        if (search && !c.full_name.toLowerCase().includes(search) && !c.position.toLowerCase().includes(search) && !(c.email||'').toLowerCase().includes(search)) return false;
        if (statusFilter && c.status !== statusFilter) return false;
        if (posFilter && c.position !== posFilter) return false;
        return true;
    });

    tbody.innerHTML = filtered.map(c => {
        const us = c.user_scores || {};
        const sv = us.venera || 0, sd = us.dmitry || 0;
        const delta = sv && sd ? Math.abs(sv - sd) : 0;
        const deltaStyle = delta > 2 ? 'color:var(--warning);font-weight:700' : 'color:var(--text-secondary)';
        const miniS = s => s ? '<span style="color:var(--warning)">' + '★'.repeat(s) + '</span>' + '<span style="color:var(--border)">' + '☆'.repeat(5-s) + '</span>' : '—';
        return `<tr data-id="${c.id}" ${delta > 2 ? 'style="background:rgba(245,158,11,0.08)"' : ''}>
            <td><strong>${esc(c.full_name)}</strong></td>
            <td>${esc(c.position || '—')}</td>
            <td><span class="status-badge ${STATUS_CLASSES[c.status]}">${c.status}</span></td>
            <td style="font-size:0.8rem">${miniS(sv)}</td>
            <td style="font-size:0.8rem">${miniS(sd)}</td>
            <td style="${deltaStyle};font-size:0.85rem;text-align:center">${delta || '—'}</td>
            <td>${formatDate(c.created_at)}</td>
            <td>${formatDate(c.last_activity)}</td>
        </tr>`;
    }).join('');

    tbody.querySelectorAll('tr').forEach(tr => {
        tr.addEventListener('click', () => openCandidateDetail(parseInt(tr.dataset.id)));
    });
}

document.getElementById('search-input').addEventListener('input', renderTable);
document.getElementById('filter-status').addEventListener('change', renderTable);
document.getElementById('filter-position').addEventListener('change', renderTable);

function updatePositionFilter() {
    const sel = document.getElementById('filter-position');
    const positions = [...new Set(candidates.map(c => c.position).filter(Boolean))];
    const current = sel.value;
    sel.innerHTML = '<option value="">Все позиции</option>' + positions.map(p => `<option value="${esc(p)}">${esc(p)}</option>`).join('');
    sel.value = current;
}

document.querySelectorAll('th[data-sort]').forEach(th => {
    th.addEventListener('click', () => {
        const col = th.dataset.sort;
        const dir = th.classList.contains('sort-asc') ? -1 : 1;
        document.querySelectorAll('th').forEach(t => t.classList.remove('sort-asc', 'sort-desc'));
        th.classList.add(dir === 1 ? 'sort-asc' : 'sort-desc');
        candidates.sort((a, b) => {
            const va = a[col] || '', vb = b[col] || '';
            return va < vb ? -dir : va > vb ? dir : 0;
        });
        renderTable();
    });
});

// === Add/Edit Candidate Modal ===
const editModal = document.getElementById('edit-modal');
document.getElementById('add-candidate-btn').addEventListener('click', () => {
    document.getElementById('edit-modal-title').textContent = 'Новый кандидат';
    document.getElementById('candidate-form').reset();
    document.getElementById('cf-id').value = '';
    editModal.classList.add('active');
});

editModal.querySelectorAll('.modal-close, .modal-cancel').forEach(el => {
    el.addEventListener('click', () => editModal.classList.remove('active'));
});

document.getElementById('candidate-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const id = document.getElementById('cf-id').value;
    const data = {
        full_name: document.getElementById('cf-name').value,
        position: document.getElementById('cf-position').value,
        email: document.getElementById('cf-email').value,
        phone: document.getElementById('cf-phone').value,
        telegram: document.getElementById('cf-telegram').value,
        portfolio_url: document.getElementById('cf-portfolio').value,
        source: document.getElementById('cf-source').value,
        status: document.getElementById('cf-status').value,
    };
    try {
        if (id) {
            await api(`/api/candidates/${id}`, { method: 'PUT', body: data });
        } else {
            await api('/api/candidates', { method: 'POST', body: data });
        }
        editModal.classList.remove('active');
        loadCandidates();
    } catch (err) { alert(err.message); }
});

// === Candidate Detail ===
async function openCandidateDetail(id) {
    currentCandidateId = id;
    const modal = document.getElementById('candidate-modal');
    const detail = document.getElementById('candidate-detail');
    detail.innerHTML = '<p style="text-align:center;padding:2rem;color:var(--text-secondary)">Загрузка...</p>';
    modal.classList.add('active');

    try {
        const [candidate, notes, meetings, tasks, files, timeline, ratings] = await Promise.all([
            api(`/api/candidates/${id}`),
            api(`/api/candidates/${id}/notes`),
            api(`/api/candidates/${id}/meetings`),
            api(`/api/candidates/${id}/tasks`),
            api(`/api/candidates/${id}/files`),
            api(`/api/candidates/${id}/timeline`),
            api(`/api/candidates/${id}/ratings`),
        ]);

        document.getElementById('modal-candidate-name').textContent = candidate.full_name;
        const myRating = ratings.find(r => r.user_id === currentUser.id);

        detail.innerHTML = `
            <!-- Profile & Quick Actions -->
            <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:0.5rem;margin-bottom:0.75rem">
                <span class="status-badge ${STATUS_CLASSES[candidate.status]}" style="font-size:0.85rem;padding:0.25rem 0.75rem">${candidate.status}</span>
                <div style="display:flex;gap:0.5rem">
                    <button class="btn btn-ghost btn-sm" onclick="editCandidate(${id})">Редактировать</button>
                    <button class="btn btn-danger btn-sm" onclick="deleteCandidate(${id})">Удалить</button>
                </div>
            </div>
            <div style="display:flex;gap:0.35rem;flex-wrap:wrap;margin-bottom:1rem" class="quick-actions">
                ${candidate.status !== 'Резюме рассмотрено' ? `<button class="btn btn-ghost btn-sm" onclick="quickStatusChange(${id},'Резюме рассмотрено')">Резюме рассмотрено</button>` : ''}
                ${candidate.status !== 'Запрос информации' ? `<button class="btn btn-ghost btn-sm" onclick="quickStatusChange(${id},'Запрос информации',true)">Запросить информацию</button>` : ''}
                ${candidate.status !== 'Тестовое задание' ? `<button class="btn btn-ghost btn-sm" onclick="quickStatusChange(${id},'Тестовое задание',true)">Отправить тестовое</button>` : ''}
                ${candidate.status !== 'Интервью' ? `<button class="btn btn-ghost btn-sm" onclick="quickStatusChange(${id},'Интервью',false,true)">Назначить интервью</button>` : ''}
                ${candidate.status !== 'Оффер' ? `<button class="btn btn-ghost btn-sm" style="color:var(--success)" onclick="quickStatusChange(${id},'Оффер')">Оффер</button>` : ''}
                ${candidate.status !== 'Отказ' ? `<button class="btn btn-ghost btn-sm" style="color:var(--danger)" onclick="quickStatusChange(${id},'Отказ')">Отказ</button>` : ''}
            </div>

            <div class="candidate-profile">
                ${profileField('Позиция', candidate.position)}
                ${profileField('Email', candidate.email ? `<a href="mailto:${esc(candidate.email)}">${esc(candidate.email)}</a>` : '—', true)}
                ${profileField('Телефон', candidate.phone || '—')}
                ${profileField('Telegram', candidate.telegram || '—')}
                ${profileField('Портфолио', candidate.portfolio_url ? `<a href="${esc(candidate.portfolio_url)}" target="_blank">${esc(candidate.portfolio_url)}</a>` : '—', true)}
                ${profileField('Источник', candidate.source || '—')}
                ${profileField('Добавлен', formatDate(candidate.created_at))}
            </div>

            <!-- Star Track -->
            <div id="star-track" class="star-track"></div>

            <!-- Tabs -->
            <div class="detail-tabs">
                <button class="detail-tab active" data-tab="timeline">Активность</button>
                <button class="detail-tab" data-tab="notes">Заметки (${notes.length})</button>
                <button class="detail-tab" data-tab="tasks">Тестовое (${tasks.length})</button>
                <button class="detail-tab" data-tab="meetings">Встречи (${meetings.length})</button>
                <button class="detail-tab" data-tab="files">Файлы (${files.length})</button>
            </div>

            <!-- Timeline Tab -->
            <div class="tab-content active" id="tab-timeline">
                <div class="timeline">
                    ${timeline.map(t => `
                        <div class="timeline-item">
                            <div class="tl-header">
                                <span class="tl-author">${esc(t.author_name)}</span>
                                <span class="tl-action">${esc(t.action)}</span>
                                <span>${formatDateTime(t.created_at)}</span>
                            </div>
                            ${t.details ? `<div class="tl-details">${esc(t.details)}</div>` : ''}
                        </div>
                    `).join('') || '<p style="color:var(--text-secondary);font-size:0.85rem">Нет активности</p>'}
                </div>
            </div>

            <!-- Notes Tab -->
            <div class="tab-content" id="tab-notes">
                ${notes.map(n => `
                    <div class="note-item">
                        <div class="note-header">
                            <span><span class="note-author">${esc(n.author_name)}</span> · ${formatDateTime(n.created_at)}</span>
                            <button class="btn btn-ghost btn-sm" onclick="deleteNote(${id}, ${n.id})">✕</button>
                        </div>
                        <div class="note-content">${renderMarkdown(n.content)}</div>
                    </div>
                `).join('') || '<p style="color:var(--text-secondary);font-size:0.85rem">Нет заметок</p>'}
                <details class="add-section">
                    <summary>Добавить заметку</summary>
                    <div class="add-form">
                        <textarea id="new-note" placeholder="Markdown поддерживается..." rows="3"></textarea>
                        <button class="btn btn-primary btn-sm" style="margin-top:0.5rem" onclick="addNote(${id})">Добавить</button>
                    </div>
                </details>
            </div>

            <!-- Tasks Tab -->
            <div class="tab-content" id="tab-tasks">
                ${tasks.map(t => `
                    <div class="item-card">
                        <div class="item-header">
                            <span class="status-badge ${t.status === 'Выдано' ? 'status-test' : t.status === 'Получено' ? 'status-interview' : 'status-hired'}">${t.status}</span>
                            <span class="item-meta">${formatDateTime(t.assigned_at)}</span>
                        </div>
                        <div class="item-body">
                            ${t.description ? `<p>${esc(t.description)}</p>` : ''}
                            ${t.rating ? `<p>Оценка: ${'★'.repeat(t.rating)}${'☆'.repeat(5 - t.rating)}</p>` : ''}
                            ${t.comment ? `<p style="color:var(--text-secondary)">${esc(t.comment)}</p>` : ''}
                        </div>
                        <div style="display:flex;gap:0.5rem;margin-top:0.5rem;flex-wrap:wrap">
                            ${t.status === 'Выдано' ? `<button class="btn btn-sm btn-ghost" onclick="updateTask(${id},${t.id},'Получено')">Получено</button>` : ''}
                            ${t.status === 'Получено' ? `<button class="btn btn-sm btn-ghost" onclick="updateTask(${id},${t.id},'Проверено')">Проверено</button>` : ''}
                            <button class="btn btn-sm btn-ghost" onclick="rateTask(${id},${t.id})">Оценить</button>
                            <button class="btn btn-sm btn-ghost" onclick="deleteTask(${id},${t.id})">✕</button>
                        </div>
                    </div>
                `).join('') || '<p style="color:var(--text-secondary);font-size:0.85rem">Нет тестовых заданий</p>'}
                <details class="add-section">
                    <summary>Добавить тестовое задание</summary>
                    <div class="add-form">
                        <textarea id="new-task-desc" placeholder="Описание задания..." rows="3"></textarea>
                        <button class="btn btn-primary btn-sm" style="margin-top:0.5rem" onclick="addTask(${id})">Добавить</button>
                    </div>
                </details>
            </div>

            <!-- Meetings Tab -->
            <div class="tab-content" id="tab-meetings">
                ${meetings.map(m => `
                    <div class="item-card">
                        <div class="item-header">
                            <span class="item-title">${formatDate(m.meeting_date)}${m.meeting_time ? ' ' + esc(m.meeting_time) : ''} · ${esc(m.format)}${m.duration ? ' · ' + m.duration + ' мин' : ''}</span>
                            <div style="display:flex;gap:0.25rem">
                                <button class="btn btn-ghost btn-sm" onclick="editMeeting(${id},${m.id})">&#9998;</button>
                                <button class="btn btn-ghost btn-sm" onclick="deleteMeeting(${id},${m.id})">✕</button>
                            </div>
                        </div>
                        <div class="item-body">
                            ${m.attendees && m.attendees !== 'all' ? `<p style="font-size:0.8rem;color:var(--text-secondary)">Участники: ${esc(m.attendees)}</p>` : ''}
                            ${m.zoom_url ? `<p><a href="${esc(m.zoom_url)}" target="_blank">Zoom</a></p>` : ''}
                            ${m.recording_url ? `<p><a href="${esc(m.recording_url)}" target="_blank">Запись</a></p>` : ''}
                            ${m.summary ? `<p>${esc(m.summary)}</p>` : ''}
                        </div>
                        <div class="item-meta">Создал: ${esc(m.creator_name)}</div>
                    </div>
                `).join('') || '<p style="color:var(--text-secondary);font-size:0.85rem">Нет встреч</p>'}
                <details class="add-section" id="meeting-form-section">
                    <summary>Добавить встречу</summary>
                    <div class="add-form">
                        <input type="hidden" id="edit-meeting-id">
                        <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:0.5rem">
                            <div><label>Дата *</label><input type="date" id="new-meeting-date"></div>
                            <div><label>Время</label><input type="time" id="new-meeting-time" value="10:00"></div>
                            <div><label>Длительность</label><select id="new-meeting-duration" class="select">
                                <option value="30">30 мин</option>
                                <option value="60" selected>60 мин</option>
                                <option value="90">90 мин</option>
                                <option value="120">2 часа</option>
                            </select></div>
                        </div>
                        <label>Формат</label>
                        <select id="new-meeting-format" class="select">
                            <option value="zoom">Zoom</option>
                            <option value="очно">Очно</option>
                            <option value="телефон">Телефон</option>
                        </select>
                        <label>Участники</label>
                        <select id="new-meeting-attendees" class="select">
                            <option value="all">Все (Venera + Dmitry)</option>
                            <option value="venera">Только Venera</option>
                            <option value="dmitry">Только Dmitry</option>
                        </select>
                        <label>Ссылка на Zoom</label>
                        <input type="url" id="new-meeting-zoom" placeholder="https://zoom.us/j/...">
                        <label>Ссылка на запись (после встречи)</label>
                        <input type="url" id="new-meeting-recording" placeholder="https://...">
                        <label>Итоги / резюме встречи</label>
                        <textarea id="new-meeting-summary" rows="2" placeholder="Краткие итоги..."></textarea>
                        <div style="display:flex;gap:0.5rem;margin-top:0.5rem">
                            <button class="btn btn-primary btn-sm" onclick="saveMeeting(${id})">Сохранить</button>
                            <button class="btn btn-ghost btn-sm" onclick="cancelEditMeeting()">Отмена</button>
                        </div>
                    </div>
                </details>
            </div>

            <!-- Files Tab -->
            <div class="tab-content" id="tab-files">
                ${files.map(f => `
                    <div class="file-item">
                        <div class="file-info">
                            <span class="file-icon">${f.file_type === 'resume' ? '📄' : '📎'}</span>
                            <a href="/api/candidates/${id}/files/${f.id}/download?token=${encodeURIComponent(token)}" target="_blank">${esc(f.original_filename)}</a>
                            <span style="color:var(--text-secondary);font-size:0.75rem">${esc(f.uploader_name)} · ${formatDate(f.created_at)}</span>
                        </div>
                        <button class="btn btn-ghost btn-sm" onclick="deleteFile(${id},${f.id})">✕</button>
                    </div>
                `).join('') || '<p style="color:var(--text-secondary);font-size:0.85rem">Нет файлов</p>'}
                <details class="add-section">
                    <summary>Загрузить файл</summary>
                    <div class="add-form">
                        <input type="file" id="new-file">
                        <button class="btn btn-primary btn-sm" style="margin-top:0.5rem" onclick="uploadFile(${id})">Загрузить</button>
                    </div>
                </details>
            </div>
        `;

        // Tab switching
        detail.querySelectorAll('.detail-tab').forEach(tab => {
            tab.addEventListener('click', () => {
                detail.querySelectorAll('.detail-tab').forEach(t => t.classList.remove('active'));
                detail.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
                tab.classList.add('active');
                document.getElementById(`tab-${tab.dataset.tab}`).classList.add('active');
            });
        });

        // Star Track
        renderStarTrack(id, candidate);

    } catch (err) {
        detail.innerHTML = `<p class="error">Ошибка: ${err.message}</p>`;
    }
}

// === Star Track ===
async function renderStarTrack(candidateId, candidate) {
    const track = document.getElementById('star-track');
    if (!track) return;
    let stageRatings = [];
    try { stageRatings = await api(`/api/candidates/${candidateId}/ratings/stages`); } catch(e) {}

    const stages = [
        { key: 'resume', label: 'Резюме' },
        { key: 'test', label: 'Тестовое' },
        { key: 'interview', label: 'Интервью' },
        { key: 'offer', label: 'Итоговая' },
    ];
    const users = [
        { username: 'venera', label: 'V', color: '#22c55e' },
        { username: 'dmitry', label: 'D', color: '#6366f1' },
    ];
    const myUsername = currentUser ? currentUser.username : '';

    const byStageUser = {};
    for (const r of stageRatings) {
        byStageUser[`${r.stage}_${r.username}`] = r;
    }

    const allScores = stageRatings.map(r => r.score);
    const avgScore = allScores.length ? (allScores.reduce((a,b)=>a+b,0) / allScores.length).toFixed(1) : '—';
    let trendHtml = '';
    if (allScores.length >= 2) {
        const last = allScores[allScores.length-1], prev = allScores[allScores.length-2];
        trendHtml = last > prev ? `<span style="color:var(--success);font-weight:700">↑</span>`
            : last < prev ? `<span style="color:var(--danger);font-weight:700">↓</span>`
            : `<span style="color:var(--text-secondary)">→</span>`;
    }

    const starsHtml = (score, color) => {
        return [1,2,3,4,5].map(i =>
            `<span style="color:${score && i <= score ? color : 'var(--border)'};font-size:0.85rem">${score && i <= score ? '★' : '☆'}</span>`
        ).join('');
    };

    track.innerHTML = `
        <div style="display:flex;align-items:center;gap:0.75rem;margin-bottom:0.5rem">
            <span style="font-size:0.85rem;font-weight:600">Средний балл: ${avgScore}</span>
            ${trendHtml}
        </div>
        <div class="star-track-grid">
            ${stages.map(s => {
                const formId = `sr-form-${s.key}`;
                return `<div class="star-track-stage">
                    <div class="star-track-label">${s.label}</div>
                    ${users.map(u => {
                        const r = byStageUser[`${s.key}_${u.username}`];
                        const score = r ? r.score : 0;
                        const comment = r && r.comment ? r.comment : '';
                        const isMine = u.username === myUsername;
                        const clickable = isMine ? `style="cursor:pointer" onclick="openStageRateForm('${s.key}',${candidateId},${score},'${esc(comment).replace(/'/g, "\\'")}','${formId}')"` : '';
                        return `<div class="star-track-user-block">
                            <div class="star-track-row" ${clickable} title="${isMine ? 'Нажмите для редактирования' : ''}">
                                <span style="font-size:0.7rem;font-weight:600;color:${u.color};width:1rem">${u.label}</span>
                                <span>${starsHtml(score, u.color)}</span>
                            </div>
                            ${comment ? `<div style="font-size:0.7rem;color:var(--text-secondary);padding-left:1.2rem;line-height:1.3;margin-top:0.1rem">${esc(comment)}</div>` : ''}
                        </div>`;
                    }).join('')}
                    <div id="${formId}"></div>
                    <button class="btn btn-ghost btn-sm" style="font-size:0.7rem;padding:0.1rem 0.3rem;margin-top:0.15rem" onclick="openStageRateForm('${s.key}',${candidateId},0,'','${formId}')">Оценить</button>
                </div>`;
            }).join('')}
        </div>
    `;
}

window.openStageRateForm = function(stage, cid, existingScore, existingComment, formContainerId) {
    // Close any other open forms
    document.querySelectorAll('.sr-inline-form').forEach(f => f.remove());

    const container = document.getElementById(formContainerId);
    if (!container) return;

    const form = document.createElement('div');
    form.className = 'sr-inline-form';
    form.style.cssText = 'margin-top:0.35rem;padding:0.5rem;background:var(--bg);border-radius:var(--radius);border:1px solid var(--border)';

    let selectedScore = existingScore || 0;

    const renderFormStars = () => {
        return [1,2,3,4,5].map(i =>
            `<span class="sr-star" data-v="${i}" style="cursor:pointer;font-size:1.1rem;color:${i <= selectedScore ? 'var(--warning)' : 'var(--border)'}">${i <= selectedScore ? '★' : '☆'}</span>`
        ).join('');
    };

    form.innerHTML = `
        <div class="sr-stars-row" style="display:flex;gap:0.1rem;margin-bottom:0.35rem">${renderFormStars()}</div>
        <input type="text" class="sr-comment-input" value="${esc(existingComment)}" placeholder="Комментарий..." style="font-size:0.75rem;padding:0.3rem 0.5rem;width:100%">
        <div style="display:flex;gap:0.3rem;margin-top:0.35rem">
            <button class="btn btn-primary btn-sm sr-save" style="font-size:0.7rem;padding:0.15rem 0.4rem" ${selectedScore ? '' : 'disabled'}>Сохранить</button>
            <button class="btn btn-ghost btn-sm sr-cancel" style="font-size:0.7rem;padding:0.15rem 0.4rem">Отмена</button>
        </div>
    `;
    container.innerHTML = '';
    container.appendChild(form);

    // Star click via event delegation on the row
    const starsRow = form.querySelector('.sr-stars-row');
    starsRow.addEventListener('click', (e) => {
        const star = e.target.closest('.sr-star');
        if (!star) return;
        selectedScore = parseInt(star.dataset.v);
        starsRow.innerHTML = [1,2,3,4,5].map(i =>
            `<span class="sr-star" data-v="${i}" style="cursor:pointer;font-size:1.1rem;color:${i <= selectedScore ? 'var(--warning)' : 'var(--border)'}">${i <= selectedScore ? '★' : '☆'}</span>`
        ).join('');
        form.querySelector('.sr-save').disabled = false;
    });

    form.querySelector('.sr-save').addEventListener('click', async () => {
        const comment = form.querySelector('.sr-comment-input').value;
        await api(`/api/candidates/${cid}/ratings/stages`, { method: 'POST', body: { stage, score: selectedScore, comment } });
        openCandidateDetail(cid);
        loadCandidates();
    });

    form.querySelector('.sr-cancel').addEventListener('click', () => {
        form.remove();
    });

    form.querySelector('.sr-comment-input').focus();
};

// === Candidate Actions ===
window.editCandidate = async function(id) {
    const c = await api(`/api/candidates/${id}`);
    document.getElementById('edit-modal-title').textContent = 'Редактировать кандидата';
    document.getElementById('cf-id').value = c.id;
    document.getElementById('cf-name').value = c.full_name;
    document.getElementById('cf-position').value = c.position;
    document.getElementById('cf-email').value = c.email;
    document.getElementById('cf-phone').value = c.phone;
    document.getElementById('cf-telegram').value = c.telegram;
    document.getElementById('cf-portfolio').value = c.portfolio_url;
    document.getElementById('cf-source').value = c.source;
    document.getElementById('cf-status').value = c.status;
    document.getElementById('candidate-modal').classList.remove('active');
    document.getElementById('edit-modal').classList.add('active');
};

window.deleteCandidate = async function(id) {
    if (!confirm('Удалить кандидата?')) return;
    await api(`/api/candidates/${id}`, { method: 'DELETE' });
    document.getElementById('candidate-modal').classList.remove('active');
    loadCandidates();
};

// === Notes ===
window.addNote = async function(cid) {
    const content = document.getElementById('new-note').value.trim();
    if (!content) return;
    await api(`/api/candidates/${cid}/notes`, { method: 'POST', body: { content } });
    openCandidateDetail(cid);
};

window.deleteNote = async function(cid, nid) {
    await api(`/api/candidates/${cid}/notes/${nid}`, { method: 'DELETE' });
    openCandidateDetail(cid);
};

// === Tasks ===
window.addTask = async function(cid) {
    const desc = document.getElementById('new-task-desc').value.trim();
    await api(`/api/candidates/${cid}/tasks`, { method: 'POST', body: { description: desc } });
    openCandidateDetail(cid);
};

window.updateTask = async function(cid, tid, status) {
    await api(`/api/candidates/${cid}/tasks/${tid}`, { method: 'PUT', body: { status } });
    openCandidateDetail(cid);
};

window.rateTask = async function(cid, tid) {
    const rating = prompt('Оценка от 1 до 5:');
    if (!rating) return;
    const comment = prompt('Комментарий (необязательно):') || '';
    await api(`/api/candidates/${cid}/tasks/${tid}`, { method: 'PUT', body: { rating: parseInt(rating), comment } });
    openCandidateDetail(cid);
};

window.deleteTask = async function(cid, tid) {
    await api(`/api/candidates/${cid}/tasks/${tid}`, { method: 'DELETE' });
    openCandidateDetail(cid);
};

// === Meetings ===
window.saveMeeting = async function(cid) {
    const editId = document.getElementById('edit-meeting-id').value;
    const data = {
        meeting_date: document.getElementById('new-meeting-date').value,
        meeting_time: document.getElementById('new-meeting-time').value,
        format: document.getElementById('new-meeting-format').value,
        attendees: document.getElementById('new-meeting-attendees').value,
        zoom_url: document.getElementById('new-meeting-zoom').value,
        recording_url: document.getElementById('new-meeting-recording').value,
        summary: document.getElementById('new-meeting-summary').value,
        duration: parseInt(document.getElementById('new-meeting-duration').value) || 60,
    };
    if (!data.meeting_date) { alert('Укажите дату'); return; }
    if (editId) {
        await api(`/api/candidates/${cid}/meetings/${editId}`, { method: 'PUT', body: data });
    } else {
        await api(`/api/candidates/${cid}/meetings`, { method: 'POST', body: data });
    }
    openCandidateDetail(cid);
};

window.editMeeting = async function(cid, mid) {
    const meetings = await api(`/api/candidates/${cid}/meetings`);
    const m = meetings.find(x => x.id === mid);
    if (!m) return;
    document.getElementById('edit-meeting-id').value = m.id;
    document.getElementById('new-meeting-date').value = m.meeting_date || '';
    document.getElementById('new-meeting-time').value = m.meeting_time || '10:00';
    document.getElementById('new-meeting-format').value = m.format || 'zoom';
    document.getElementById('new-meeting-attendees').value = m.attendees || 'all';
    document.getElementById('new-meeting-zoom').value = m.zoom_url || '';
    document.getElementById('new-meeting-recording').value = m.recording_url || '';
    document.getElementById('new-meeting-summary').value = m.summary || '';
    const durSel = document.getElementById('new-meeting-duration');
    if (durSel) durSel.value = String(m.duration || 60);
    const section = document.getElementById('meeting-form-section');
    if (section) {
        section.open = true;
        section.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
};

window.cancelEditMeeting = function() {
    document.getElementById('edit-meeting-id').value = '';
    document.getElementById('new-meeting-date').value = '';
    document.getElementById('new-meeting-time').value = '10:00';
    document.getElementById('new-meeting-format').value = 'zoom';
    document.getElementById('new-meeting-attendees').value = 'all';
    document.getElementById('new-meeting-zoom').value = '';
    document.getElementById('new-meeting-recording').value = '';
    document.getElementById('new-meeting-summary').value = '';
    const durSel = document.getElementById('new-meeting-duration');
    if (durSel) durSel.value = '60';
    const section = document.getElementById('meeting-form-section');
    if (section) section.open = false;
};

window.deleteMeeting = async function(cid, mid) {
    if (!confirm('Отменить встречу? Участники получат уведомление.')) return;
    await api(`/api/candidates/${cid}/meetings/${mid}`, { method: 'DELETE' });
    openCandidateDetail(cid);
};

// === Files ===
window.uploadFile = async function(cid) {
    const input = document.getElementById('new-file');
    if (!input.files.length) return;
    const formData = new FormData();
    formData.append('file', input.files[0]);
    await api(`/api/candidates/${cid}/files`, { method: 'POST', body: formData });
    openCandidateDetail(cid);
};

window.deleteFile = async function(cid, fid) {
    await api(`/api/candidates/${cid}/files/${fid}`, { method: 'DELETE' });
    openCandidateDetail(cid);
};

// === Modals ===
document.querySelectorAll('.modal').forEach(modal => {
    modal.addEventListener('click', (e) => {
        if (e.target === modal) modal.classList.remove('active');
    });
    modal.querySelectorAll('.modal-close').forEach(btn => {
        btn.addEventListener('click', () => modal.classList.remove('active'));
    });
});

document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        document.querySelectorAll('.modal.active').forEach(m => m.classList.remove('active'));
    }
});

// === Helpers ===
function esc(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function renderMarkdown(text) {
    if (typeof marked !== 'undefined' && typeof DOMPurify !== 'undefined') {
        return DOMPurify.sanitize(marked.parse(text || ''));
    }
    return esc(text).replace(/\n/g, '<br>');
}

function formatDate(dt) {
    if (!dt) return '—';
    try {
        const d = new Date(dt.replace(' ', 'T'));
        return d.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short', year: 'numeric' });
    } catch { return dt; }
}

function formatDateTime(dt) {
    if (!dt) return '—';
    try {
        const d = new Date(dt.replace(' ', 'T'));
        return d.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
    } catch { return dt; }
}

function profileField(label, value, isHtml = false) {
    return `<div class="profile-field"><div class="label">${label}</div><div class="value">${isHtml ? value : esc(value || '—')}</div></div>`;
}

// === Init ===
if (token && currentUser) {
    showApp();
}
