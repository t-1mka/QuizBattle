// BrainStorm — game.js
const socket = io();
let timerInterval = null;

// ── DOM helper ───────────────────────────────────────────────
const $ = id => document.getElementById(id);

// ── Вид ─────────────────────────────────────────────────────
function showView(id) {
    document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
    $(`view-${id}`)?.classList.add('active');
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

// ── Тосты ───────────────────────────────────────────────────
function toast(msg, type = 'info', ms = 3000) {
    const t = Object.assign(document.createElement('div'), {
        className: `toast toast-${type}`, innerHTML: msg
    });
    $('toasts').appendChild(t);
    setTimeout(() => {
        t.style.cssText = 'opacity:0;transform:translateX(100%)';
        setTimeout(() => t.remove(), 300);
    }, ms);
}

// ── Таймер ───────────────────────────────────────────────────
function startTimer(sec) {
    clearInterval(timerInterval);
    let left = sec;
    const el = $('g-timer');
    const tick = () => {
        if (!el) return;
        el.textContent = left;
        el.style.color      = left <= 5  ? '#ff4444' : left <= 10 ? '#ff9f1c' : '#4a90e2';
        el.style.textShadow = `0 0 20px ${left <= 5 ? '#ff4444' : left <= 10 ? '#ff9f1c' : '#4a90e2'}`;
        el.style.animation  = left <= 5 ? 'pulse 0.5s ease-in-out infinite' : '';
        if (--left < 0) clearInterval(timerInterval);
    };
    tick();
    timerInterval = setInterval(tick, 1000);
}

function stopTimer() {
    clearInterval(timerInterval);
    timerInterval = null;
    const el = $('g-timer');
    if (el) el.style.animation = '';
}

// ── Игроки ───────────────────────────────────────────────────
function renderPlayers(players) {
    const list = $('players-list');
    if (!list) return;
    list.innerHTML = players.map(p => `
        <li class="${p.is_host ? 'host-player' : ''}">
            <span class="player-avatar">${p.name[0].toUpperCase()}</span>
            <span class="player-name">${p.name}</span>
            ${p.is_host ? '<span class="badge-host">👑 Хост</span>' : ''}
            ${p.team  ? `<span class="badge-team team-${p.team}">Команда ${p.team}</span>` : ''}
        </li>`).join('');
    $('players-count').textContent = `(${players.length})`;
}

// ── Настройки гостя ──────────────────────────────────────────
const DIFF  = { easy:'😊 Лёгкая', medium:'🧠 Средняя', hard:'🔥 Сложная' };
const MODES = { classic:'🏆 Классика', ffa:'⚡ Все против всех', team:'🤝 Командный' };

function renderGuestSettings(s) {
    if (!s) return;
    const vals = {
        'gs-topic': s.topic || 'Общие знания',
        'gs-count': s.question_count ? s.question_count + ' шт.' : '—',
        'gs-diff':  DIFF[s.difficulty]  || '—',
        'gs-mode':  MODES[s.game_mode]  || '—',
    };
    for (const [id, val] of Object.entries(vals)) {
        const el = $(id);
        if (!el) continue;
        const changed = el.textContent !== '—' && el.textContent !== val;
        el.textContent = val;
        if (changed) {
            const card = el.closest('.gs-item');
            card?.classList.add('updated');
            setTimeout(() => card?.classList.remove('updated'), 1500);
        }
    }
}

// ── Описание режима (для хоста) ───────────────────────────────
function updateModeDesc() {
    const descs = {
        classic: '🏆 <b>Классика</b> — все отвечают одновременно, очки за скорость.',
        ffa:     '⚡ <b>Все против всех</b> — только первый правильный ответ приносит очки.',
        team:    '🤝 <b>Командный бой</b> — команды ходят по очереди.',
    };
    const el = $('mode-desc');
    if (el) el.innerHTML = descs[$('s-mode')?.value] || '';
}

// ── Подсветка ответов ─────────────────────────────────────────
function highlightAnswers(correctIdx, playerAnswers) {
    const myAns = playerAnswers[socket.id]?.answer ?? -1;
    document.querySelectorAll('.option-btn').forEach((btn, i) => {
        btn.classList.remove('selected-pending');
        btn.classList.add('disabled');
        if (i === correctIdx) btn.classList.add('selected-correct');
        else if (i === myAns) btn.classList.add('selected-wrong');
    });
}

// ── Вкладки ───────────────────────────────────────────────────
document.querySelectorAll('.tab-btn').forEach(btn => btn.addEventListener('click', () => {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-panel').forEach(p => p.style.display = 'none');
    btn.classList.add('active');
    $(`tab-${btn.dataset.tab}`)?.setAttribute('style', 'display:block');
    $({ create: 'create-name', join: 'join-name' }[btn.dataset.tab])?.focus();
}));

// ── Создать лобби ─────────────────────────────────────────────
function doCreate() {
    const el  = $('create-name');
    const err = $('create-name-error');
    const name = el?.value.trim();
    if (!name) { err.style.display = 'block'; el?.classList.add('inp-error'); return; }
    err.style.display = 'none'; el.classList.remove('inp-error');
    socket.emit('create_room', { player_name: name });
}
$('btn-create')?.addEventListener('click', doCreate);
$('create-name')?.addEventListener('keydown', e => {
    $('create-name-error').style.display = 'none';
    $('create-name')?.classList.remove('inp-error');
    if (e.key === 'Enter') doCreate();
});

// ── Войти в игру ──────────────────────────────────────────────
function doJoin() {
    const nameEl = $('join-name'), codeEl = $('join-code'), err = $('join-error');
    const name   = nameEl?.value.trim();
    const code   = codeEl?.value.trim().toUpperCase();
    if (!name || !code) { err.style.display = 'block'; return; }
    err.style.display = 'none';
    socket.emit('join_room', { player_name: name, room_code: code });
}
$('btn-join')?.addEventListener('click', doJoin);
['join-name','join-code'].forEach(id =>
    $(id)?.addEventListener('keydown', e => {
        $('join-error').style.display = 'none';
        if (e.key === 'Enter') doJoin();
    })
);
$('join-code')?.addEventListener('input', function() { this.value = this.value.toUpperCase(); });

// ── Лобби ─────────────────────────────────────────────────────
$('btn-apply')?.addEventListener('click', () => {
    socket.emit('update_settings', {
        topic:          $('s-topic')?.value || 'Общие знания',
        question_count: parseInt($('s-count')?.value) || 10,
        difficulty:     $('s-diff')?.value  || 'medium',
        num_options:    parseInt($('s-options')?.value) || 4,
        game_mode:      $('s-mode')?.value  || 'classic',
    });
    toast('✅ Настройки применены', 'success');
});
$('btn-start')?.addEventListener('click', () => socket.emit('start_game', {}));
$('btn-copy')?.addEventListener('click', () => {
    navigator.clipboard.writeText($('lobby-code')?.textContent || '');
    toast('📋 Код скопирован!', 'success', 1500);
});
$('s-mode')?.addEventListener('change', updateModeDesc);

function doLeave() { socket.emit('leave_room'); showView('main'); }
$('btn-leave-lobby')?.addEventListener('click', doLeave);
$('btn-leave-game')?.addEventListener('click', () => confirm('Выйти из игры?') && doLeave());
$('btn-again')?.addEventListener('click',      () => showView('main'));

// ── Socket события ────────────────────────────────────────────

socket.on('room_created', data => {
    showView('lobby');
    $('lobby-code').textContent = data.room_code;
    renderPlayers(data.players);
    $('btn-leave-lobby').style.display = 'inline-block';
    $('host-settings').style.display   = 'block';
    $('guest-settings').style.display  = 'none';
    $('btn-start').style.display       = 'inline-block';
    updateModeDesc();
    $('btn-apply')?.click();
});

socket.on('room_joined', data => {
    showView('lobby');
    $('lobby-code').textContent = data.room_code;
    renderPlayers(data.players);
    $('btn-leave-lobby').style.display = 'inline-block';
    $('host-settings').style.display   = 'none';
    $('guest-settings').style.display  = 'block';
    $('btn-start').style.display       = 'none';
    renderGuestSettings(data.settings);
});

socket.on('player_joined',   data => { renderPlayers(data.players); toast('👋 Новый игрок!', 'success'); });
socket.on('players_update',  data => renderPlayers(data.players));
socket.on('host_changed',    data => toast(`👑 Новый хост: ${data.host}`, 'info'));

socket.on('settings_updated', data => {
    if (!data.settings) return;
    updateModeDesc();
    renderGuestSettings(data.settings);
    if ($('guest-settings')?.style.display !== 'none')
        toast('📋 Хост обновил настройки', 'info', 2000);
});

socket.on('game_loading', data => {
    showView('loading');
    $('loading-msg').textContent = data.message;
});

socket.on('game_started', data => {
    showView('game');
    $('g-score').textContent    = '0';
    $('g-mode-badge').textContent = { classic:'🏆 Классика', ffa:'⚡ FFA', team:`🤝 Команда ${data.your_team}` }[data.mode] || '';
    const teamEl = $('g-team');
    if (data.your_team && teamEl) { teamEl.textContent = `Команда ${data.your_team}`; teamEl.style.display = 'inline-block'; }
});

socket.on('new_question', data => {
    $('question-result-panel').style.display = 'none';
    $('g-qnum').textContent    = `Вопрос ${data.question_number} / ${data.total_questions}`;
    $('g-progress').style.width = `${data.question_number / data.total_questions * 100}%`;
    $('g-question').textContent = data.question.question;

    const grid    = $('options-grid');
    grid.innerHTML = '';
    const LETTERS  = ['A','B','C','D','E','F'];
    data.question.options.forEach((opt, i) => {
        const btn = document.createElement('button');
        btn.className = 'option-btn';
        btn.innerHTML = `<span class="opt-letter">${LETTERS[i]}</span><span class="opt-text">${opt}</span>`;
        btn.onclick = () => {
            if (btn.classList.contains('disabled')) return;
            document.querySelectorAll('.option-btn').forEach(b => b.classList.add('disabled'));
            btn.classList.add('selected-pending');
            socket.emit('submit_answer', { answer_index: i });
        };
        grid.appendChild(btn);
    });

    startTimer(data.time_limit);
    $('g-status').textContent = '';

    const isTeam = data.mode === 'team';
    $('team-board').style.display = isTeam ? 'flex' : 'none';
    $('turn-bar').style.display   = isTeam ? 'block' : 'none';
    if (isTeam) {
        $('tb-s1').textContent = data.team_scores?.[1] ?? 0;
        $('tb-s2').textContent = data.team_scores?.[2] ?? 0;
        $('turn-bar').textContent = `Ход Команды ${data.turn_team}`;
    }
});

socket.on('answer_ack', data => {
    if (data.correct) {
        if (data.streak >= 2) toast({ 2:'🔥 Серия ×2!', 3:'🔥🔥 Серия ×3!', 4:'⚡ Серия ×4!', 5:'💥 ×5!!' }[Math.min(data.streak,5)] || `🔥 ×${data.streak}!`, 'streak', 2000);
        if (data.points) toast(`+${data.points} очков`, 'success', 1500);
    }
});

socket.on('question_result', data => {
    stopTimer();
    highlightAnswers(data.correct_index, data.player_answers);
    $('g-score').textContent = data.scores[socket.id] || 0;

    const myAns  = data.player_answers[socket.id];
    const panel  = $('question-result-panel');
    const title  = $('result-title');
    title.textContent = myAns?.correct ? '✅ Правильно!' : '❌ Неверно!';
    title.style.color = myAns?.correct ? '#28a745' : '#dc3545';

    $('qr-scores').innerHTML = Object.entries(data.scores)
        .sort((a, b) => b[1] - a[1])
        .map(([sid, score]) => {
            const icon = data.player_answers[sid]?.correct ? '✅' : '❌';
            const self = sid === socket.id ? ' <b>(вы)</b>' : '';
            return `<div class="score-row-item">${icon} ${score} очков${self}</div>`;
        }).join('');

    panel.style.display = 'block';
    setTimeout(() => panel.style.display = 'none', 3000);
});

socket.on('interim_results', data => {
    const panel = $('question-result-panel');
    $('result-title').innerHTML = '📊 Промежуточные результаты';
    $('result-title').style.color = '#ffd700';
    $('qr-scores').innerHTML =
        [...data.players].sort((a,b) => b.score - a.score)
        .map((p,i) => `<div class="score-row-item">${i+1}. ${p.name} — ${p.score} очков</div>`)
        .join('');
    panel.style.display = 'block';
    setTimeout(() => panel.style.display = 'none', 5000);
});

socket.on('ffa_correct', data => {
    const f = $('ffa-flash');
    if (!f) return;
    f.innerHTML = `⚡ ${data.player_name} первый! <b>+${data.points}</b>`;
    f.style.display = 'block';
    setTimeout(() => f.style.display = 'none', 2500);
});

socket.on('game_over', data => {
    stopTimer();
    showView('results');
    const MEDALS = {1:'🥇', 2:'🥈', 3:'🥉'};
    $('leaderboard').innerHTML = data.players.map(p => `
        <div class="leaderboard-item rank-${p.rank}">
            <span class="rank">${MEDALS[p.rank] || '#'+p.rank}</span>
            <span class="name">${p.name}${p.team ? `<small class="team-${p.team}-color"> Команда ${p.team}</small>` : ''}</span>
            <div class="score-info">
                <span class="score">${p.score}</span>
                <small style="color:#a0a8c0;display:block">✅ ${p.total_correct ?? 0} верных</small>
            </div>
        </div>`).join('');

    const banner = $('result-banner');
    if (data.mode === 'team' && data.winner) {
        banner.style.display = 'block';
        banner.innerHTML = data.winner === 'draw' ? '🤝 Ничья!' : `🏆 Победила Команда ${data.winner === 'team1' ? 1 : 2}!`;
    } else {
        banner.style.display = 'none';
    }
});

socket.on('error',      data => { toast(`❌ ${data.message}`, 'error', 4000); showView('main'); });
socket.on('disconnect', ()   => toast('⚠️ Соединение потеряно. Обновите страницу.', 'error', 10000));

window.addEventListener('load', () => { updateModeDesc(); $('create-name')?.focus(); });
