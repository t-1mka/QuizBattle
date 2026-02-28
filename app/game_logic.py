import random, string, time
from dataclasses import dataclass, field
from typing import Optional

SCORE_MULT   = {"easy": 1.0, "medium": 1.5, "hard": 2.0}
BASE_SCORE   = 100
TIME_BONUS   = 50
MAX_TIME     = 30.0

_CACHE: dict = {}
CACHE_TTL = 3600

def cache_get(key):
    if key in _CACHE:
        ts, qs = _CACHE[key]
        if time.time() - ts < CACHE_TTL:
            return qs
        del _CACHE[key]
    return None

def cache_set(key, questions):
    _CACHE[key] = (time.time(), questions)

@dataclass
class Player:
    sid: str
    name: str
    score: int = 0
    team: Optional[int] = None
    answered: bool = False
    answer_index: Optional[int] = None
    answer_time: float = 0.0
    streak: int = 0
    total_correct: int = 0

    def reset_answer(self):
        self.answered = False
        self.answer_index = None
        self.answer_time = 0.0

    def to_dict(self, is_host=False):
        return {
            "name": self.name, "score": self.score,
            "team": self.team, "is_host": is_host,
            "total_correct": self.total_correct,
        }

@dataclass
class Room:
    code: str
    host_sid: str
    settings: dict = field(default_factory=dict)
    players:  dict = field(default_factory=dict)
    state: str = "waiting"
    questions: list = field(default_factory=list)
    current_q: int = 0
    q_start_time: float = 0.0
    ffa_first: Optional[str] = None
    turn_team: int = 1

    @property
    def mode(self):        return self.settings.get("game_mode", "classic")
    @property
    def difficulty(self):  return self.settings.get("difficulty", "medium")
    @property
    def total_questions(self): return len(self.questions)
    @property
    def current_question(self):
        return self.questions[self.current_q] if 0 <= self.current_q < len(self.questions) else None
    @property
    def human_players(self):
        return [p for p in self.players.values()]

    def add_player(self, sid, name):
        p = Player(sid=sid, name=name)
        self.players[sid] = p
        return p

    def remove_player(self, sid):
        self.players.pop(sid, None)

    def players_list(self):
        return [p.to_dict(is_host=(p.sid == self.host_sid)) for p in self.players.values()]

    def assign_teams(self):
        sids = list(self.players.keys())
        random.shuffle(sids)
        for i, sid in enumerate(sids):
            self.players[sid].team = 1 if i % 2 == 0 else 2
        self.turn_team = 1

    def team_scores(self):
        s = {1: 0, 2: 0}
        for p in self.players.values():
            if p.team in s:
                s[p.team] += p.score
        return s

    def reset_answers(self):
        for p in self.players.values():
            p.reset_answer()
        self.ffa_first = None

    def all_answered(self):
        if self.mode == "team":
            active = [p for p in self.players.values() if p.team == self.turn_team]
            return all(p.answered for p in active) if active else True
        return all(p.answered for p in self.players.values())

    def advance_question(self):
        if self.mode == "team":
            self.turn_team = 2 if self.turn_team == 1 else 1
        self.current_q += 1
        if self.current_q >= self.total_questions:
            self.state = "finished"
            return False
        self.reset_answers()
        self.q_start_time = time.time()
        return True

    def award_point(self, sid):
        p = self.players.get(sid)
        if not p:
            return 0
        mult   = SCORE_MULT.get(self.difficulty, 1.0)
        points = int(BASE_SCORE * mult)
        elapsed = max(0.0, p.answer_time - self.q_start_time)
        points += max(0, int(TIME_BONUS * (1 - elapsed / MAX_TIME)))
        p.streak += 1
        p.total_correct += 1
        if p.streak >= 3:
            points += min(50, (p.streak - 2) * 10)
        p.score += points
        return points

    def reset_streak(self, sid):
        if p := self.players.get(sid):
            p.streak = 0

    def final_results(self):
        sorted_p = sorted(self.players.values(), key=lambda p: -p.score)
        out = {
            "mode": self.mode,
            "players": [
                {"rank": i+1, "name": p.name, "score": p.score,
                 "team": p.team, "total_correct": p.total_correct}
                for i, p in enumerate(sorted_p)
            ],
        }
        if self.mode == "team":
            ts = self.team_scores()
            out["team_scores"] = ts
            out["winner"] = "team1" if ts[1] > ts[2] else "team2" if ts[2] > ts[1] else "draw"
        return out

rooms: dict[str, Room] = {}

def gen_code():
    while True:
        code = "".join(random.choices(string.ascii_uppercase, k=6))
        if code not in rooms:
            return code

def get_room_by_sid(sid):
    return next((r for r in rooms.values() if sid in r.players), None)
