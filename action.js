const roomCodeInput = document.getElementById('room-code-input');
const joinPlayerNameInput = document.getElementById('join-player-name');
const createBtn = document.getElementById('create-room-button');
const joinBtn = document.getElementById('join-room-button');
const modal = document.getElementById('create-room-modal');
const modalClose = document.getElementById('modal-close');
const createRoomForm = document.getElementById('create-room-form');
const viewMain = document.getElementById('view-main');
const viewWaiting = document.getElementById('view-waiting');
const viewGame = document.getElementById('view-game');
const displayRoomCode = document.getElementById('display-room-code');
const playersList = document.getElementById('players-list');
const startGameBtn = document.getElementById('start-game-button');
const team1NameInput = document.getElementById('team1-name-input');
const team2NameInput = document.getElementById('team2-name-input');
const scoreTeam1LabelEl = document.getElementById('score-team1-label');
const scoreTeam2LabelEl = document.getElementById('score-team2-label');
const scoreTeam1El = document.getElementById('score-team1');
const scoreTeam2El = document.getElementById('score-team2');
const gameTurnEl = document.getElementById('game-turn');
const gameQuestionNumEl = document.getElementById('game-question-num');
const gameQuestionTextEl = document.getElementById('game-question-text');
const gameOptionsEl = document.getElementById('game-options');
const gameWaitEl = document.getElementById('game-wait');
const gameOverEl = document.getElementById('game-over');
const gameOverResultEl = document.getElementById('game-over-result');
const backToMainBtn = document.getElementById('back-to-main');

let socket = null;
let roomCode = '';
let isHost = false;
let myTeam = null;
let teamNames = { team1: 'Команда 1', team2: 'Команда 2' };

function applyTeamNamesToUI() {
    const t1 = teamNames.team1 || 'Команда 1';
    const t2 = teamNames.team2 || 'Команда 2';

    if (team1NameInput) team1NameInput.value = t1;
    if (team2NameInput) team2NameInput.value = t2;

    if (scoreTeam1LabelEl) scoreTeam1LabelEl.textContent = t1;
    if (scoreTeam2LabelEl) scoreTeam2LabelEl.textContent = t2;
}

function emitTeamNameUpdate(team, value) {
    if (!socket || !roomCode || !isHost) return;
    const trimmed = (value || '').trim();
    if (!trimmed) return;
    socket.emit('update_team_name', {
        room_code: roomCode,
        team,
        name: trimmed,
    });
}

function connect() {
    socket = io(window.location.origin);
    socket.on('error', (data) => {
        alert(data.message || "Ошибка");
    });
    socket.on('room_created', onRoomCreated);
    socket.on('room_joined', onRoomJoined);
    socket.on('player_joined', onPlayerJoined);
    socket.on('game_started', onGameStarted);
    socket.on("answer_result", onAnswerResult);
    socket.on('team_name_updated', onTeamNameUpdated);
}
connect();

function showView(id) {
    [viewMain, viewWaiting, viewGame].forEach((v) => {
        v.classList.add('view-hidden');
    });
    const el = document.getElementById(id);
    if (el) el.classList.remove('view-hidden');
}

function openCreateModal() {
    if (modal) {
        modal.classList.add('is-open');
        modal.setAttribute('aria-hidden', 'false');
    }
}

function closeCreateModal() {
    if (modal) {
        modal.classList.remove('is-open');
        modal.setAttribute('aria-hidden', 'true');
    }
}

createBtn.addEventListener('click', openCreateModal);
modalClose.addEventListener('click', closeCreateModal);
modal.addEventListener('click', (i) => {
    if (i.target === modal) closeCreateModal();
});
document.addEventListener('keydown', (i) => {
    if (i.key === 'Escape' && modal && modal.classList.contains('is-open')) closeCreateModal();
});

createRoomForm.addEventListener('submit', (e) => {
    e.preventDefault();
    const playerName = document.getElementById('player-name').value.trim() || 'Игрок';
    const questionsCount = parseInt(document.getElementById('questions-count').value, 10) || 5;
    const difficulty = document.getElementById('difficulty').value;
    const topic = document.getElementById('topic').value.trim() || 'Школьная программа';
    if (!socket || !socket.connected) {
        alert('Ошибка при присоединении');
        return;
    }
    socket.emit('create_room', {
        player_name: playerName,
        questions_count: Math.min(50, Math.max(1, questionsCount)),
        difficulty,
        topic,
    });
    closeCreateModal();
    createRoomForm.reset();
    document.getElementById('questions-count').value = 5;
    document.getElementById('difficulty').value = 'normal';
});

if (team1NameInput) {
    team1NameInput.addEventListener('change', () => {
        emitTeamNameUpdate('team1', team1NameInput.value);
    });
}

if (team2NameInput) {
    team2NameInput.addEventListener('change', () => {
        emitTeamNameUpdate('team2', team2NameInput.value);
    });
}

joinBtn.addEventListener('click', () => {
    const code = roomCodeInput ? roomCodeInput.value.trim().toUpperCase() : '';
    const playerName = joinPlayerNameInput ? joinPlayerNameInput.value.trim() || 'Игрок' : 'Игрок';
    if (!code) {
        alert('Введите код комнаты');
        return;
    }
    if (!socket || !socket.connected) {
        alert('Нет соединения с сервером');
        return;
    }
    socket.emit('join_room', { room_code: code, player_name: playerName });
});

function onRoomCreated(data) {
    roomCode = data.room_code;
    isHost = data.is_host;
    myTeam = data.your_team || null;
    if (data.team_names) {
        teamNames = data.team_names;
    }
    displayRoomCode.textContent = roomCode;
    renderPlayers(data.players);
    applyTeamNamesToUI();
    if (startGameBtn) startGameBtn.style.display = isHost ? 'block' : 'none';
    if (team1NameInput) team1NameInput.disabled = !isHost;
    if (team2NameInput) team2NameInput.disabled = !isHost;
    showView('view-waiting');
}

function onRoomJoined(data) {
    roomCode = data.room_code;
    isHost = data.is_host;
    myTeam = data.your_team || null;
    if (data.team_names) {
        teamNames = data.team_names;
    }
    displayRoomCode.textContent = roomCode;
    renderPlayers(data.players);
    applyTeamNamesToUI();
    if (startGameBtn) startGameBtn.style.display = isHost ? 'block' : 'none';
    if (team1NameInput) team1NameInput.disabled = !isHost;
    if (team2NameInput) team2NameInput.disabled = !isHost;
    showView('view-waiting');
}

function onPlayerJoined(data) {
    renderPlayers(data.players);
}

function renderPlayers(players) {
    if (!playersList) return;

    const list = Array.isArray(players) ? players : [];
    const html = list
        .map((p) => {
            const teamKey = p.team;
            const label = teamNames[teamKey] || teamKey;
            return `<li>${p.name} <span class="team-badge">${label}</span></li>`;
        })
        .join('');

    playersList.innerHTML = html;
}

startGameBtn.addEventListener('click', () => {
    if (!socket || !roomCode) return;
    socket.emit('start_game', { room_code: roomCode });
});

function onGameStarted(data) {
    if (data.team_names) {
        teamNames = data.team_names;
        applyTeamNamesToUI();
    }
    showView('view-game');
    gameOverEl.classList.remove('visible');
    updateScores(data.scores);
    setTurn(data.turn);
    gameQuestionNumEl.textContent = `Вопрос ${data.question_number} из ${data.total_questions}`;
    gameQuestionTextEl.textContent = data.question.text;
    const canAnswer = myTeam === data.turn;
    renderOptions(data.question.options, canAnswer);
    gameWaitEl.classList.toggle('hidden', canAnswer);
    gameOptionsEl.classList.toggle('disabled', !canAnswer);
}

function updateScores(scores) {
    const s1 = scores && scores.team1 != null ? scores.team1 : 0;
    const s2 = scores && scores.team2 != null ? scores.team2 : 0;
    if (scoreTeam1El) scoreTeam1El.textContent = s1;
    if (scoreTeam2El) scoreTeam2El.textContent = s2;
}

function setTurn(turn) {
    const fallback = turn === 'team1' ? 'Команда 1' : 'Команда 2';
    const t = teamNames[turn] || fallback;
    gameTurnEl.textContent = `Сейчас отвечает: ${t}`;
}

function renderOptions(options, enabled) {
    if (!gameOptionsEl) return;
    gameOptionsEl.innerHTML = '';
    options.forEach((text, index) => {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'game-option';
        btn.textContent = text;
        btn.disabled = !enabled;
        btn.dataset.index = index;
        btn.addEventListener('click', () => submitAnswer(index));
        gameOptionsEl.appendChild(btn);
    });
}

function submitAnswer(index) {
    if (!socket || !roomCode) return;
    socket.emit('submit_answer', { room_code: roomCode, answer_index: index });
    gameOptionsEl.querySelectorAll('.game-option').forEach((b) => (b.disabled = true));
}

function onAnswerResult(data) {
    if (data.team_names) {
        teamNames = data.team_names;
        applyTeamNamesToUI();
    }
    updateScores(data.scores);
    setTurn(data.turn);
    gameQuestionNumEl.textContent = `Вопрос ${data.question_number} из ${data.total_questions}`;

    if (data.game_over) {
        gameQuestionTextEl.textContent = '';
        gameOptionsEl.innerHTML = '';
        gameWaitEl.classList.add('hidden');
        const s1 = data.scores && data.scores.team1 != null ? data.scores.team1 : 0;
        const s2 = data.scores && data.scores.team2 != null ? data.scores.team2 : 0;
        const t1 = teamNames.team1 || 'Команда 1';
        const t2 = teamNames.team2 || 'Команда 2';
        let text = `${t1}: ${s1} — ${t2}: ${s2}. `;
        if (s1 > s2) text += `${t1} побеждает!`;
        else if (s2 > s1) text += `${t2} побеждает!`;
        else text += 'Ничья!';
        gameOverResultEl.textContent = text;
        gameOverEl.classList.add('visible');
        return;
    }

    gameQuestionTextEl.textContent = data.next_question ? data.next_question.text : '';
    const canAnswer = myTeam === data.turn;
    if (data.next_question) {
        renderOptions(data.next_question.options, canAnswer);
    }
    gameWaitEl.classList.toggle('hidden', canAnswer);
    gameOptionsEl.classList.toggle('disabled', !canAnswer);
}

function onTeamNameUpdated(data) {
    if (data.team_names) {
        teamNames = data.team_names;
        applyTeamNamesToUI();
        if (playersList && playersList.children.length > 0) {
        }
    }
}

if (backToMainBtn) {
    backToMainBtn.addEventListener('click', () => {
        roomCode = '';
        isHost = false;
        myTeam = null;
        showView('view-main');
    });
}
