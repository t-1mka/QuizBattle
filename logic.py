import os
import random
import string
from flask import Flask, render_template, request, send_file
from flask_socketio import SocketIO, emit, join_room
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__, template_folder='template')
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'quiz-battle-secret-' + os.urandom(16).hex())
socketio = SocketIO(app, cors_allowed_origins='*')

ROOMS = {}


def gen_room_code():
    chars = string.ascii_uppercase + string.digits
    while True:
        code = ''.join(random.choices(chars, k=6))
        if code not in ROOMS:
            return code



def create_questions(count, topic, difficulty):
    questions = []
    for i in range(count):
        options = ['Вариант A', 'Вариант B', 'Вариант C', 'Вариант D']
        correct_index = random.randint(0, 3)
        correct_answer = options[correct_index]
        random.shuffle(options)
        correct_index = options.index(correct_answer)
        questions.append({
            'text': f'Вопрос {i + 1}',
            'options': options,
            'correct_index': correct_index,
        })
    return questions


def get_room_by_code(code):
    return ROOMS.get(code.upper() if code else '')

def get_players_list(room):
    return [{'sid': p['sid'], 'name': p['name'], 'team': p['team']} for p in room['players']]

@socketio.on('create_room')
def handle_create_room(data):
    name = (data.get('player_name') or '').strip() or 'Игрок'
    questions_count = min(50, max(1, int(data.get('questions_count', 5))))
    difficulty = data.get('difficulty', 'normal')
    try:
        topic = (data.get('topic') or '').strip()
        if topic == '':
            return emit('error', {'message': "Тема не задана"})

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
    
    if not room['questions']:
        emit('error', {'message': 'Не удалось сгенерировать вопросы. Попробуйте еще раз.'})
        return
    
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
        players_to_remove = []
        for i, p in enumerate(room['players']):
            if p['sid'] == request.sid:
                players_to_remove.append(i)
        for i in reversed(players_to_remove):
            room['players'].pop(i)
        
        if players_to_remove:
            emit('player_joined', {'players': get_players_list(room)}, room=code)
        if not room['players']:
            del ROOMS[code]
        elif room.get('host_sid') == request.sid and room['players']:
            room['host_sid'] = room['players'][0]['sid']

@app.route('/')
def index():
    return render_template('sheet.html')

@app.route('/static/<path:filename>')
def serve_static(filename):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    static_dir = os.path.join(base_dir, 'static')
    return send_file(os.path.join(static_dir, filename))

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
