# -*- coding: utf-8 -*-
import os
from flask import Flask
from flask_socketio import SocketIO

socketio = SocketIO(
    cors_allowed_origins="*",
    async_mode="eventlet",
    logger=False,
    engineio_logger=False,
    ping_timeout=60,
    ping_interval=25,
)


def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder="../templates",
        static_folder="../static",
    )
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "quizbattle-dev-key-please-change")

    socketio.init_app(app)

    from .routes import bp
    app.register_blueprint(bp)

    from . import socket_events

    return app
