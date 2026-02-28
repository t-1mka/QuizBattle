# -*- coding: utf-8 -*-
import time
from flask import Blueprint, render_template, jsonify

bp = Blueprint("main", __name__)


@bp.route("/")
def index():
    return render_template("index.html")


@bp.route("/health")
def health():
    return jsonify({"status": "ok", "ts": time.time()})
