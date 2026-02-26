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
    questions_db = {
        'Математика': [
            {'text': 'Сколько будет 2 + 2?', 'options': ['3', '4', '5', '6'], 'correct_index': 1},
            {'text': 'Сколько сторон у квадрата?', 'options': ['3', '4', '5', '6'], 'correct_index': 1},
            {'text': 'Сколько минут в одном часе?', 'options': ['30', '45', '60', '90'], 'correct_index': 2},
            {'text': 'Чему равно 5 × 5?', 'options': ['20', '25', '30', '35'], 'correct_index': 1},
            {'text': 'Сколько дней в неделе?', 'options': ['5', '6', '7', '8'], 'correct_index': 2},
        ],
        'Русский язык': [
            {'text': 'Сколько букв в слове "кошка"?', 'options': ['4', '5', '6', '7'], 'correct_index': 1},
            {'text': 'Какая часть речи отвечает на вопрос "что делает"?', 'options': ['Существительное', 'Глагол', 'Прилагательное', 'Наречие'], 'correct_index': 1},
            {'text': 'Сколько слогов в слове "машина"?', 'options': ['2', '3', '4', '5'], 'correct_index': 1},
            {'text': 'Какой звук обозначает буква "ё"?', 'options': ['[о]', '[йо]', '[й]', '[е]'], 'correct_index': 1},
            {'text': 'Что такое предложение?', 'options': ['Слово', 'Знак препинания', 'Слова связанные по смыслу', 'Буква'], 'correct_index': 2},
        ],
        'География': [
            {'text': 'Столица России?', 'options': ['Санкт-Петербург', 'Москва', 'Новосибирск', 'Екатеринбург'], 'correct_index': 1},
            {'text': 'Самая длинная река в мире?', 'options': ['Волга', 'Нил', 'Амазонка', 'Енисей'], 'correct_index': 2},
            {'text': 'Сколько океанов на Земле?', 'options': ['3', '4', '5', '6'], 'correct_index': 1},
            {'text': 'Какой материк самый большой?', 'options': ['Африка', 'Азия', 'Америка', 'Европа'], 'correct_index': 1},
            {'text': 'Где находится пустыня Сахара?', 'options': ['Азия', 'Африка', 'Америка', 'Австралия'], 'correct_index': 1},
        ],
        'История': [
            {'text': 'В каком году была Куликовская битва?', 'options': ['1380', '1480', '1580', '1680'], 'correct_index': 0},
            {'text': 'Кто был первым президентом США?', 'options': ['Джордж Вашингтон', 'Томас Джефферсон', 'Авраам Линкольн', 'Бенджамин Франклин'], 'correct_index': 0},
            {'text': 'В каком году пал Константинополь?', 'options': ['1453', '1492', '1517', '1612'], 'correct_index': 0},
            {'text': 'Кто написал "Войну и мир"?', 'options': ['Достоевский', 'Толстой', 'Чехов', 'Пушкин'], 'correct_index': 1},
            {'text': 'Какой империи пала в 476 году?', 'options': ['Римская', 'Византийская', 'Османская', 'Британская'], 'correct_index': 0},
        ],
        'Биология': [
            {'text': 'Сколько костей у взрослого человека?', 'options': ['186', '206', '226', '246'], 'correct_index': 1},
            {'text': 'Какой орган перекачивает кровь?', 'options': ['Лёгкие', 'Печень', 'Сердце', 'Почки'], 'correct_index': 2},
            {'text': 'Что производит хлорофилл?', 'options': ['Корень', 'Стебель', 'Лист', 'Цветок'], 'correct_index': 2},
            {'text': 'Сколько камер в сердце человека?', 'options': ['2', '3', '4', '5'], 'correct_index': 2},
            {'text': 'Какое самое большое млекопитающее?', 'options': ['Слон', 'Кит', 'Жираф', 'Бегемот'], 'correct_index': 1},
        ],
        'Литература': [
            {'text': 'Кто написал "Евгения Онегина"?', 'options': ['Лермонтов', 'Пушкин', 'Тургенев', 'Толстой'], 'correct_index': 1},
            {'text': 'В какой сказке есть Змей Горыныч?', 'options': ['Царевна-лягушка', 'Василиса Прекрасная', 'Илья Муромец', 'Золушка'], 'correct_index': 1},
            {'text': 'Кто автор "Муму"?', 'options': ['Тургенев', 'Достоевский', 'Толстой', 'Чехов'], 'correct_index': 0},
            {'text': 'Как зовут главного героя "Преступления и наказания"?', 'options': ['Раскольников', 'Базаров', 'Обломов', 'Чичиков'], 'correct_index': 0},
            {'text': 'В каком произведении есть персонаж Печорин?', 'options': ['Герой нашего времени', 'Отцы и дети', 'Обломов', 'Мёртвые души'], 'correct_index': 0},
        ],
        'Физика': [
            {'text': 'Скорость света в вакууме?', 'options': ['300000 км/с', '150000 км/с', '100000 км/с', '500000 км/с'], 'correct_index': 0},
            {'text': 'Что измеряется в ньютонах?', 'options': ['Масса', 'Сила', 'Скорость', 'Расстояние'], 'correct_index': 1},
            {'text': 'Сколько планет в Солнечной системе?', 'options': ['7', '8', '9', '10'], 'correct_index': 1},
            {'text': 'Какая температура кипения воды?', 'options': ['90°C', '100°C', '110°C', '120°C'], 'correct_index': 1},
            {'text': 'Что притягивает предметы к Земле?', 'options': ['Магнетизм', 'Гравитация', 'Электричество', 'Трение'], 'correct_index': 1},
        ],
        'Химия': [
            {'text': 'Химический символ воды?', 'options': ['H2O', 'CO2', 'O2', 'N2'], 'correct_index': 0},
            {'text': 'Какой газ вдыхаем?', 'options': ['Углекислый', 'Кислород', 'Азот', 'Водород'], 'correct_index': 1},
            {'text': 'Сколько электронов у водорода?', 'options': ['0', '1', '2', '3'], 'correct_index': 1},
            {'text': 'Что такое HCl?', 'options': ['Соляная кислота', 'Серная кислота', 'Уксусная кислота', 'Азотная кислота'], 'correct_index': 0},
            {'text': 'Какой металл самый лёгкий?', 'options': ['Алюминий', 'Железо', 'Литий', 'Медь'], 'correct_index': 2},
        ]
    }
    
    selected_questions = []
    all_topics = list(questions_db.keys())
    
    for i in range(count):
        if topic in questions_db:
            topic_questions = questions_db[topic]
        else:
            topic_questions = []
            for t in all_topics:
                topic_questions.extend(questions_db[t])
        
        if topic_questions:
            question = random.choice(topic_questions)
            selected_questions.append(question.copy())
    
    return selected_questions[:count]


def get_room_by_code(code):
    return ROOMS.get(code.upper() if code else '')

def get_players_list(room):
    return [{'sid': p['sid'], 'name': p['name'], 'team': p['team']} for p in room['players']]

@socketio.on('create_room')
def handle_create_room(data):
    name = (data.get('player_name') or '').strip() or 'Игрок'
    questions_count = min(50, max(1, int(data.get('questions_count', 5))))
    difficulty = data.get('difficulty', 'normal')
    topic = (data.get('topic') or '').strip() or 'Школьная программа'

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

    room['questions'] = create_questions(
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
        emit('error', {'message': 'Такой комнаты нет'})
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

@app.route('/action.js')
def serve_action_js():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    return send_file(os.path.join(base_dir, 'action.js'), mimetype='application/javascript')

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000)
