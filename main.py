"""Flask WSGI приложение для получения статистики по хостам в сетевых
сегментах."""

__author__ = "ZHEZLYAEV Aleksandr  <zhezlyaev@gmail.com>"
__version__ = "1.0"

# -*- coding: utf-8 -*-

import os
import secrets
from datetime import datetime, timedelta

from flask import Flask, flash, redirect, render_template, request, url_for
from flask_login import LoginManager, UserMixin, current_user, login_required, login_user, logout_user
from flask_socketio import SocketIO
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

from utils.web.wtForm import DCForm, LoginForm

# базовые настройки flask и soketio
SECRET_KEY = secrets.token_urlsafe(32)
app = Flask(__name__)
app.config["SECRET_KEY"] = SECRET_KEY
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")


# конфигурация Flask SQL ALCHEMY
basedir = os.path.abspath(os.path.dirname(__file__))
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(basedir, "flsite.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

# Атрибуту login_view присваиваем имя функции представления для формы авторизации
login_manager = LoginManager(app)
login_manager.login_view = "login"

# формировать мгновенное сообщение для таких ситуаций.
login_manager.login_message = "Авторизуйтесь для доступа к закрытым страницам"
login_manager.login_message_category = "warning"

# время жизни сессии == 1 день
app.permanent_session_lifetime = timedelta(days=1)
app.config.from_object(__name__)


class Menu(db.Model):
    """Класс для представления таблицы Menu в БД для SQLAlchemy."""

    __tablename__ = "mainmenu"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    title = db.Column(db.String(50), unique=True, nullable=False)
    url = db.Column(db.String(500), nullable=False)

    def __repr__(self):
        return f"url {self.url}"


class User(db.Model, UserMixin):
    """Класс для представления таблицы Menu в БД для SQLAlchemy.

    Flask-Login предлагает реализацию этих методов по умолчанию с
    помощью класса UserMixin. Так, вместо определения их вручную, можно
    настроить их наследование из класса UserMixin.
    """

    __tablename__ = "users"

    id = db.Column(db.Integer(), primary_key=True)
    username = db.Column(db.String(50), nullable=False, unique=True)
    password_hash = db.Column(db.String(100), nullable=False)
    created_on = db.Column(db.DateTime(), default=datetime.utcnow)
    updated_on = db.Column(db.DateTime(), default=datetime.utcnow, onupdate=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"{self.id}:{self.username}"


@login_manager.user_loader
def load_user(user_id):
    """Заносит в сессию информацию о зарегистрированном пользователе.

    После этого сессионная информация будет присутствовать во всех
    запросах к серверу.
    """
    return db.session.query(User).get(user_id)


@app.route("/login", methods=["POST", "GET"])
def login():
    """Обработчик страницы /login."""
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    form = LoginForm()

    if form.validate_on_submit():
        user = db.session.query(User).filter(User.username == form.username.data).first()
        if user and user.check_password(form.password.data):
            login_user(user, remember=form.remember.data)

            global username
            username = form.username.data

            global password
            password = form.password.data

            return redirect(request.args.get("next") or url_for("index"))

        flash("Неверная пара логин/пароль", "error")
        return redirect(url_for("login"))

    return render_template("login.html", menu=Menu.query.all(), title="Авторизация", form=form)


@app.route("/logout")
@login_required
def logout():
    """Обработчик страницы /logout."""
    logout_user()
    flash("Вы вышли из аккаунта", "success")
    return redirect(url_for("login"))


@app.route("/index", methods=["post", "get"])
@app.route("/", methods=["post", "get"])
@login_required
def index():
    """Обработчик страницы /index."""

    # проверяем версию данных о vlan
    from alien_app import check_vlan_info_date

    vlan_ver_msg = check_vlan_info_date()
    return render_template(
        "index.html", menu=Menu.query.all(), title="Главная", form=DCForm(), vlan_ver_msg=vlan_ver_msg
    )


@app.route("/about")
@login_required
def about():
    """Обработчик страницы /about."""
    return render_template("about.html", menu=Menu.query.all(), title="О сайте")


@app.errorhandler(404)
@login_required
def pageNotFount(error):
    """Обработчик несуществующих страниц."""
    return (
        render_template("page404.html", menu=Menu.query.all(), title="Страница не найдена"),
        404,
    )


@socketio.on("start")
def start(data: dict[str, str]):
    """Функция по сообщению от socket io запускает другую функцию
    get_hosts_in_threads по сбору статистики хостов по сетевым сегментам."""

    selected_dc = data.get("dc")
    selected_vlan = data.get("vlan")

    from alien_app import get_hosts_in_threads

    get_hosts_in_threads(username, password, selected_vlan, selected_dc)


@socketio.on("updateVlanInfo")
def updateVlanInfo():
    """Функция по сообщению от socket io запускает другую функцию
    get_vlans_in_threads по сбору данных о svi со всех устройств."""

    from alien_app import get_vlans_in_threads

    get_vlans_in_threads(username, password)


if __name__ == "__main__":
    socketio.run(app, debug=True)
