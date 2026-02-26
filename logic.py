import os
import random
import string
import json
import requests
from flask import Flask, render_template, request, send_file
from flask_socketio import SocketIO, emit, join_room

app = Flask(__name__, template_folder='template')
app.config['SECRET_KEY'] = 'quiz-battle-secret'
socketio = SocketIO(app, cors_allowed_origins='*')

ROOMS = {}  # room_code -> room state

YANDEX_IAM_TOKEN = os.getenv('YANDEX_GPT_IAM_TOKEN') or os.getenv('IAM_TOKEN')
YANDEX_FOLDER_ID = os.getenv('YANDEX_GPT_FOLDER_ID') or os.getenv('FOLDER_ID')
YANDEX_GPT_MODEL = os.getenv('YANDEX_GPT_MODEL', 'yandexgpt-lite')
YANDEX_GPT_API_URL = 'https://llm.api.cloud.yandex.net/foundationModels/v1/completion'


def gen_room_code():
    chars = string.ascii_uppercase + string.digits
    while True:
        code = ''.join(random.choices(chars, k=6))
        if code not in ROOMS:
            return code


def _generate_questions_fallback(count, topic, difficulty):
    """Локальный генератор вопросов на случай, если YandexGPT недоступен."""
    questions = []
    for i in range(count):
        options = ['Вариант A', 'Вариант B', 'Вариант C', 'Вариант D']
        correct_index = random.randint(0, 3)
        correct_answer = options[correct_index]
        random.shuffle(options)
        correct_index = options.index(correct_answer)
        questions.append({
            'text': f'Вопрос {i + 1}: тема «{topic}» (сложность: {difficulty})?',
            'options': options,
            'correct_index': correct_index,
        })
    return questions


def _generate_questions_via_yandex(count, topic, difficulty):
    """Генерация вопросов через YandexGPT. Возвращает список вопросов или None при ошибке."""
    if not YANDEX_IAM_TOKEN or not YANDEX_FOLDER_ID:
        return None

    system_text = (
        'Ты помощник, который придумывает вопросы для викторины. '
        'Отвечай только валидным JSON без комментариев и форматирования markdown.'
    )
    user_text = (
        f'Сгенерируй {count} вопросов викторины на русском языке по теме "{topic}" '
        f'со сложностью {difficulty}. '
        'Ответ верни в виде JSON-массива объектов: '
        '[{"text": "вопрос", "options": ["вариант1","вариант2","вариант3","вариант4"], "correct_index": 0}, ...]. '
        'Всегда делай ровно 4 варианта ответов и correct_index указывай как номер правильного варианта (0-3). '
        'Не добавляй никакого текста до или после JSON.'
    )

    payload = {
        'modelUri': f'gpt://{YANDEX_FOLDER_ID}/{YANDEX_GPT_MODEL}',
        'completionOptions': {
            'stream': False,
            'temperature': 0.6,
            'maxTokens': '2000',
        },
        'messages': [
            {'role': 'system', 'text': system_text},
            {'role': 'user', 'text': user_text},
        ],
    }

    try:
        resp = requests.post(
            YANDEX_GPT_API_URL,
            headers={
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {YANDEX_IAM_TOKEN}',
                'x-folder-id': YANDEX_FOLDER_ID,
            },
            json=payload,
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()
        text = (
            data.get('result', {})
            .get('alternatives', [{}])[0]
            .get('message', {})
            .get('text', '')
        )
        if not text:
            return None

        raw = json.loads(text)
        questions = []
        for item in raw:
            q_text = str(item.get('text', '')).strip()
            options = item.get('options') or []
            if not q_text or not isinstance(options, list) or len(options) < 2:
                continue
            # берём первые 4 варианта
            options = [str(o) for o in options][:4]
            if len(options) < 2:
                continue
            idx = item.get('correct_index', 0)
            try:
                idx = int(idx)
            except (TypeError, ValueError):
                idx = 0
            if idx < 0 or idx >= len(options):
                idx = 0
            questions.append({
                'text': q_text,
                'options': options,
                'correct_index': idx,
            })
        return questions or None
    except Exception:
        return None


def generate_questions(count, topic, difficulty):
    """Генерация списка вопросов с попыткой использовать YandexGPT."""
    # сначала пытаемся через YandexGPT
    questions = _generate_questions_via_yandex(count, topic, difficulty)
    if questions:
        return questions
    # если не получилось — возвращаем локальные заглушки
    return _generate_questions_fallback(count, topic, difficulty)


def get_room_by_code(code):
    return ROOMS.get(code.upper() if code else '')


def get_players_list(room):
    return [{'sid': p['sid'], 'name': p['name'], 'team': p['team']} for p in room['players']]


@socketio.on('create_room')
def handle_create_room(data):
    name = (data.get('player_name') or '').strip() or 'Игрок'
    questions_count = min(50, max(1, int(data.get('questions_count', 5))))
    difficulty = data.get('difficulty', 'normal')
    topic = (data.get('topic') or '').strip() or 'Общие знания'

    code = gen_room_code()
    room = {
        'code': code,
        'host_sid': None,
        'players': [],
        'topic': topic,
        'difficulty': difficulty,
        'questions_count': questions_count,
        'questions': [],
        'state': 'waiting',
        'current_question_index': 0,
        'scores': {'team1': 0, 'team2': 0},
        'turn': 'team1',
        'team_names': {'team1': 'Команда 1', 'team2': 'Команда 2'},
    }
    ROOMS[code] = room

    join_room(code)
    room['host_sid'] = request.sid
    room['players'].append({'sid': request.sid, 'name': name, 'team': 'team1'})

    emit(
        'room_created',
        {
            'room_code': code,
            'is_host': True,
            'your_team': 'team1',
            'players': get_players_list(room),
            'team_names': room['team_names'],
        },
    )
    emit('player_joined', {'players': get_players_list(room)}, room=code)


@socketio.on('join_room')
def handle_join_room(data):
    code = (data.get('room_code') or '').strip().upper()
    name = (data.get('player_name') or '').strip() or 'Игрок'

    room = get_room_by_code(code)
    if not room:
        emit('error', {'message': 'Комната не найдена'})
        return
    if room['state'] != 'waiting':
        emit('error', {'message': 'Игра уже началась'})
        return
    if any(p['sid'] == request.sid for p in room['players']):
        emit('error', {'message': 'Вы уже в комнате'})
        return

    join_room(code)
    team = 'team2' if len(room['players']) % 2 == 1 else 'team1'
    room['players'].append({'sid': request.sid, 'name': name, 'team': team})

    emit(
        'room_joined',
        {
            'room_code': code,
            'is_host': room['host_sid'] == request.sid,
            'your_team': team,
            'players': get_players_list(room),
            'team_names': room['team_names'],
        },
    )
    emit('player_joined', {'players': get_players_list(room)}, room=code)


@socketio.on('update_team_name')
def handle_update_team_name(data):
    code = (data.get('room_code') or '').strip().upper()
    team = (data.get('team') or '').strip()
    name = (data.get('name') or '').strip()

    room = get_room_by_code(code)
    if not room or team not in ('team1', 'team2') or not name:
        return

    # только ведущий может менять названия команд
    if request.sid != room['host_sid']:
        return

    room['team_names'][team] = name[:50]
    emit('team_name_updated', {'team_names': room['team_names']}, room=code)


@socketio.on('start_game')
def handle_start_game(data):
    code = (data.get('room_code') or '').strip().upper()
    room = get_room_by_code(code)
    if not room:
        emit('error', {'message': 'Комната не найдена'})
        return
    if room['host_sid'] != request.sid:
        emit('error', {'message': 'Только ведущий может начать игру'})
        return
    if room['state'] != 'waiting':
        emit('error', {'message': 'Игра уже идёт'})
        return
    if len(room['players']) < 2:
        emit('error', {'message': 'Нужно минимум 2 игрока'})
        return

    room['questions'] = generate_questions(
        room['questions_count'], room['topic'], room['difficulty']
    )
    room['state'] = 'playing'
    room['current_question_index'] = 0
    room['scores'] = {'team1': 0, 'team2': 0}
    room['turn'] = 'team1'

    q = room['questions'][0]
    q_safe = {'text': q['text'], 'options': q['options']}
    payload = {
        'scores': room['scores'],
        'turn': room['turn'],
        'question': q_safe,
        'question_number': 1,
        'total_questions': len(room['questions']),
        'team_names': room['team_names'],
    }
    emit('game_started', payload, room=code)


@socketio.on('submit_answer')
def handle_submit_answer(data):
    code = (data.get('room_code') or '').strip().upper()
    answer_index = data.get('answer_index', -1)
    room = get_room_by_code(code)
    if not room or room['state'] != 'playing':
        emit('error', {'message': 'Игра не идёт'})
        return

    player = next((p for p in room['players'] if p['sid'] == request.sid), None)
    if not player:
        emit('error', {'message': 'Вы не в этой комнате'})
        return
    if player['team'] != room['turn']:
        emit('error', {'message': 'Сейчас ход другой команды'})
        return

    q = room['questions'][room['current_question_index']]
    correct = answer_index == q['correct_index']
    if correct:
        room['scores'][room['turn']] += 1

    room['current_question_index'] += 1
    next_turn = 'team2' if room['turn'] == 'team1' else 'team1'
    room['turn'] = next_turn

    next_question = None
    if room['current_question_index'] < len(room['questions']):
        nq = room['questions'][room['current_question_index']]
        next_question = {'text': nq['text'], 'options': nq['options']}
        next_q_num = room['current_question_index'] + 1
    else:
        next_q_num = room['current_question_index']

    payload = {
        'correct': correct,
        'scores': room['scores'],
        'turn': room['turn'],
        'next_question': next_question,
        'question_number': next_q_num,
        'total_questions': len(room['questions']),
        'game_over': room['current_question_index'] >= len(room['questions']),
        'team_names': room['team_names'],
    }
    emit('answer_result', payload, room=code)


@socketio.on('disconnect')
def handle_disconnect():
    for code, room in list(ROOMS.items()):
        for i, p in enumerate(room['players']):
            if p['sid'] == request.sid:
                room['players'].pop(i)
                emit('player_joined', {'players': get_players_list(room)}, room=code)
                if not room['players']:
                    del ROOMS[code]
                break


@app.route('/')
def index():
    return render_template('sheet.html')


@app.route('/action.js')
def serve_action_js():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    for filename in ('Action.js', 'action.js'):
        path = os.path.join(base_dir, filename)
        if os.path.exists(path):
            return send_file(path, mimetype='application/javascript')
    return ('Not Found', 404)


if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000)
