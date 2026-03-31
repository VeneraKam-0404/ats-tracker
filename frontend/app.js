// === State ===
let token = localStorage.getItem('ats_token');
let currentUser = JSON.parse(localStorage.getItem('ats_user') || 'null');
let candidates = [];
let currentCandidateId = null;

const STATUSES = ['Новый', 'Резюме рассмотрено', 'Тестовое задание', 'Интервью', 'Оффер', 'Принят', 'Отказ'];
const STATUS_CLASSES = {
    'Новый': 'status-new', 'Резюме рассмотрено': 'status-reviewed',
    'Тестовое задание': 'status-test', 'Интервью': 'status-interview',
    'Оффер': 'status-offer', 'Принят': 'status-hired', 'Отказ': 'status-rejected'
};

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
    });
});

// === Load Candidates ===
async function loadCandidates() {
    try {
        candidates = await api('/api/candidates');
        renderKanban();
        renderTable();
        updatePositionFilter();
    } catch (err) { console.error(err); }
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

        // Drag & drop
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
            const stars = c.avg_rating ? '★'.repeat(Math.round(c.avg_rating)) + '☆'.repeat(5 - Math.round(c.avg_rating)) : '';
            card.innerHTML = `
                <div class="card-name">${esc(c.full_name)}</div>
                <div class="card-position">${esc(c.position || '—')}</div>
                <div class="card-meta">
                    <span>${formatDate(c.last_activity)}</span>
                    <span class="card-rating">${stars}</span>
                </div>
            `;
            cards.appendChild(card);
        });
        board.appendChild(col);
    });
}

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
        const stars = c.avg_rating ? '★'.repeat(Math.round(c.avg_rating)) + '☆'.repeat(5 - Math.round(c.avg_rating)) : '—';
        return `<tr data-id="${c.id}">
            <td><strong>${esc(c.full_name)}</strong></td>
            <td>${esc(c.position || '—')}</td>
            <td><span class="status-badge ${STATUS_CLASSES[c.status]}">${c.status}</span></td>
            <td style="color:var(--warning)">${stars}</td>
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

// Table sorting
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
            <!-- Profile -->
            <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:0.5rem;margin-bottom:1rem">
                <span class="status-badge ${STATUS_CLASSES[candidate.status]}" style="font-size:0.85rem;padding:0.25rem 0.75rem">${candidate.status}</span>
                <div style="display:flex;gap:0.5rem">
                    <button class="btn btn-ghost btn-sm" onclick="editCandidate(${id})">Редактировать</button>
                    <button class="btn btn-danger btn-sm" onclick="deleteCandidate(${id})">Удалить</button>
                </div>
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

            <!-- Rating -->
            <div class="rating-section">
                <span class="rating-label">Моя оценка:</span>
                <div class="stars" id="my-rating">
                    ${[1,2,3,4,5].map(i => `<span class="star ${myRating && myRating.score >= i ? 'filled' : ''}" data-score="${i}">★</span>`).join('')}
                </div>
                <span class="rating-label" style="margin-left:auto">Средняя: <strong>${candidate.avg_rating || '—'}</strong></span>
            </div>

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
                            <span class="item-title">${formatDate(m.meeting_date)} · ${esc(m.format)}</span>
                            <button class="btn btn-ghost btn-sm" onclick="deleteMeeting(${id},${m.id})">✕</button>
                        </div>
                        <div class="item-body">
                            ${m.recording_url ? `<p><a href="${esc(m.recording_url)}" target="_blank">Запись</a></p>` : ''}
                            ${m.summary ? `<p>${esc(m.summary)}</p>` : ''}
                        </div>
                        <div class="item-meta">Создал: ${esc(m.creator_name)}</div>
                    </div>
                `).join('') || '<p style="color:var(--text-secondary);font-size:0.85rem">Нет встреч</p>'}
                <details class="add-section">
                    <summary>Добавить встречу</summary>
                    <div class="add-form">
                        <label>Дата</label><input type="date" id="new-meeting-date">
                        <label>Формат</label>
                        <select id="new-meeting-format" class="select">
                            <option value="zoom">Zoom</option>
                            <option value="очно">Очно</option>
                            <option value="телефон">Телефон</option>
                        </select>
                        <label>Ссылка на запись</label><input type="url" id="new-meeting-url" placeholder="https://...">
                        <label>Резюме встречи</label><textarea id="new-meeting-summary" rows="2"></textarea>
                        <button class="btn btn-primary btn-sm" style="margin-top:0.5rem" onclick="addMeeting(${id})">Добавить</button>
                    </div>
                </details>
            </div>

            <!-- Files Tab -->
            <div class="tab-content" id="tab-files">
                ${files.map(f => `
                    <div class="file-item">
                        <div class="file-info">
                            <span class="file-icon">${f.file_type === 'resume' ? '📄' : '📎'}</span>
                            <a href="/api/candidates/${id}/files/${f.id}/download" target="_blank">${esc(f.original_filename)}</a>
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

        // Star rating
        detail.querySelectorAll('#my-rating .star').forEach(star => {
            star.addEventListener('click', async () => {
                const score = parseInt(star.dataset.score);
                await api(`/api/candidates/${id}/ratings`, { method: 'POST', body: { score } });
                openCandidateDetail(id);
                loadCandidates();
            });
        });

    } catch (err) {
        detail.innerHTML = `<p class="error">Ошибка: ${err.message}</p>`;
    }
}

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
window.addMeeting = async function(cid) {
    const data = {
        meeting_date: document.getElementById('new-meeting-date').value,
        format: document.getElementById('new-meeting-format').value,
        recording_url: document.getElementById('new-meeting-url').value,
        summary: document.getElementById('new-meeting-summary').value,
    };
    if (!data.meeting_date) { alert('Укажите дату'); return; }
    await api(`/api/candidates/${cid}/meetings`, { method: 'POST', body: data });
    openCandidateDetail(cid);
};

window.deleteMeeting = async function(cid, mid) {
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
