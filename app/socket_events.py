# -*- coding: utf-8 -*-
"""Socket.IO события BrainStorm"""
import time, logging, eventlet
from flask import request
from flask_socketio import emit, join_room, leave_room
from . import socketio
from .game_logic import rooms, Room, gen_code, get_room_by_sid, cache_get, cache_set
from .ai_client import generate_questions

logger = logging.getLogger(__name__)
TIME_PER_Q = 30


def _emit_question(room: Room):
    q = room.current_question
    if not q:
        return
    payload = {
        "question":        {"question": q["question"], "options": q["options"]},
        "question_number": room.current_q + 1,
        "total_questions": room.total_questions,
        "time_limit":      TIME_PER_Q,
        "mode":            room.mode,
    }
    if room.mode == "team":
        payload["turn_team"]   = room.turn_team
        payload["team_scores"] = room.team_scores()
    socketio.emit("new_question", payload, room=room.code)
    eventlet.spawn_after(TIME_PER_Q + 1, _timeout_question, room.code, room.current_q)


def _timeout_question(code, q_idx):
    room = rooms.get(code)
    if not room or room.state != "playing" or room.current_q != q_idx:
        return
    for p in room.players.values():
        if not p.answered:
            p.answered = True
            p.answer_index = -1
            p.answer_time = time.time()
            room.reset_streak(p.sid)
    _resolve_question(room)


def _resolve_question(room: Room):
    q = room.current_question
    if not q:
        return
    ci = q["correct"]
    correct_text = q["options"][ci] if 0 <= ci < len(q["options"]) else "?"

    player_answers = {
        sid: {"answer": p.answer_index, "correct": (p.answer_index == ci), "streak": p.streak}
        for sid, p in room.players.items()
    }
    socketio.emit("question_result", {
        "correct_index":  ci,
        "correct_answer": correct_text,
        "player_answers": player_answers,
        "scores":         {sid: p.score for sid, p in room.players.items()},
        "team_scores":    room.team_scores() if room.mode == "team" else None,
        "mode":           room.mode,
    }, room=room.code)

    has_next = room.advance_question()
    eventlet.sleep(3)

    if has_next:
        if room.current_q % 5 == 0 and room.current_q < room.total_questions:
            socketio.emit("interim_results", {
                "players":       [p.to_dict() for p in room.players.values()],
                "next_question": room.current_q + 1,
            }, room=room.code)
            eventlet.sleep(5)
        _emit_question(room)
    else:
        socketio.emit("game_over", room.final_results(), room=room.code)


def _player_left(sid):
    room = get_room_by_sid(sid)
    if not room:
        return
    room.remove_player(sid)
    leave_room(room.code)
    if not room.players:
        rooms.pop(room.code, None)
        return
    if room.host_sid == sid:
        room.host_sid = room.human_players[0].sid
    socketio.emit("players_update", {"players": room.players_list()}, room=room.code)
    socketio.emit("host_changed",   {"host": room.players[room.host_sid].name}, room=room.code)
    if room.state == "playing" and room.all_answered():
        eventlet.spawn(_resolve_question, room)


@socketio.on("connect")
def on_connect():
    logger.debug("connect: %s", request.sid)

@socketio.on("disconnect")
def on_disconnect():
    _player_left(request.sid)

@socketio.on("leave_room")
def on_leave_room():
    _player_left(request.sid)


@socketio.on("create_room")
def on_create_room(data):
    name = (data.get("player_name") or "Игрок").strip() or "Игрок"
    code = gen_code()
    room = Room(code=code, host_sid=request.sid)
    room.add_player(request.sid, name)
    rooms[code] = room
    join_room(code)
    emit("room_created", {"room_code": code, "is_host": True, "players": room.players_list()})


@socketio.on("join_room")
def on_join_room(data):
    code = (data.get("room_code") or "").strip().upper()
    name = (data.get("player_name") or "Игрок").strip() or "Игрок"
    if code not in rooms:
        emit("error", {"message": "Комната не найдена. Проверь код."})
        return
    room = rooms[code]
    if room.state != "waiting":
        emit("error", {"message": "Игра уже началась, войти нельзя."})
        return
    room.add_player(request.sid, name)
    join_room(code)
    emit("room_joined", {"room_code": code, "is_host": False,
                         "players": room.players_list(), "settings": room.settings})
    emit("player_joined", {"players": room.players_list()}, room=code, include_self=False)


@socketio.on("update_settings")
def on_update_settings(data):
    room = get_room_by_sid(request.sid)
    if not room or room.host_sid != request.sid:
        return
    for k in ("topic", "question_count", "difficulty", "num_options", "game_mode"):
        if k in data:
            room.settings[k] = data[k]
    emit("settings_updated", {"settings": room.settings}, room=room.code)


@socketio.on("start_game")
def on_start_game(_):
    room = get_room_by_sid(request.sid)
    if not room or room.host_sid != request.sid or room.state != "waiting":
        return
    if len(room.players) < 2:
        emit("error", {"message": "Нужно минимум 2 игрока."})
        return

    s           = room.settings
    topic       = s.get("topic", "Общие знания")
    count       = max(1, min(50, int(s.get("question_count", 10))))
    difficulty  = s.get("difficulty", "medium")
    num_options = max(2, min(6, int(s.get("num_options", 4))))

    emit("game_loading", {"message": "🤖 GigaChat генерирует вопросы..."}, room=room.code)

    def _start():
        key = (topic, count, difficulty, num_options)
        questions = cache_get(key)
        if questions:
            logger.info("📦 Кэш: тема '%s'", topic)
        else:
            try:
                questions = generate_questions(topic, count, difficulty, num_options)
                cache_set(key, questions)
            except Exception as exc:
                logger.error("generate_questions: %s", exc)
                socketio.emit("error", {"message": "Ошибка AI. Попробуй ещё раз."}, room=room.code)
                return

        if room.mode == "team":
            room.assign_teams()

        room.questions    = questions
        room.state        = "playing"
        room.current_q    = 0
        room.q_start_time = time.time()
        room.reset_answers()

        for sid, p in room.players.items():
            socketio.emit("game_started", {"your_team": p.team, "mode": room.mode}, room=sid)

        _emit_question(room)

    eventlet.spawn(_start)


@socketio.on("submit_answer")
def on_submit_answer(data):
    room   = get_room_by_sid(request.sid)
    player = room.players.get(request.sid) if room else None
    if not room or room.state != "playing" or not player or player.answered:
        return
    q = room.current_question
    if not q:
        return

    ans        = int(data.get("answer_index", -1))
    is_correct = (ans == q["correct"])

    player.answered     = True
    player.answer_index = ans
    player.answer_time  = time.time()

    pts = room.award_point(request.sid) if is_correct else 0
    if not is_correct:
        room.reset_streak(request.sid)

    if room.mode == "ffa":
        if is_correct and room.ffa_first is None:
            room.ffa_first = request.sid
            socketio.emit("ffa_correct", {"player_name": player.name, "points": pts}, room=room.code)
        if room.ffa_first is not None or room.all_answered():
            eventlet.spawn(_resolve_question, room)
        return

    emit("answer_ack", {"correct": is_correct, "points": pts, "streak": player.streak})
    if room.all_answered():
        eventlet.spawn(_resolve_question, room)
