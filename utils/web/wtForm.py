"""Представления форм для сайта."""

__author__ = "ZHEZLYAEV Aleksandr  <zhezlyaev@gmail.com>"
__version__ = "1.0"

# -*- coding: utf-8 -*-

import json
import os

from flask_wtf import FlaskForm
from wtforms import BooleanField, PasswordField, RadioField, SelectField, StringField, SubmitField
from wtforms.validators import InputRequired


class LoginForm(FlaskForm):
    """Класс для представления формы авторизации flask wtforms."""

    username = StringField(
        "Логин: ",
        validators=[
            InputRequired(),
        ],
    )
    password = PasswordField(
        "Пароль: ",
        validators=[
            InputRequired(),
        ],
    )
    remember = BooleanField("Запомнить", default=False)
    submit = SubmitField("Авторизоваться")


class DCForm(FlaskForm):
    """Класс для представления формы выбора сетевого оборудования flask
    wtforms."""

    VLAN_DATA_DIR = "Data"
    all_vlans = {}

    files = os.listdir(VLAN_DATA_DIR)
    for file in files:
        try:
            with open(VLAN_DATA_DIR + "/" + file) as f:
                all_vlans_by_dc: dict = json.load(f)
                all_vlans.update(all_vlans_by_dc)
        except FileNotFoundError:
            print(f"Файл {file} не найден")

    radio = RadioField(
        "Выберете ЦОД: ",
        choices=[
            ("ALL", "Хосты растянутых сетей."),
            ("MSK34", "Локальные хосты MSK34"),
            ("MSK70", "Локальные хосты MSK70"),
            ("MSKD8", "Локальные хосты MSKD8"),
        ],
        validators=[InputRequired()],
    )

    if all_vlans:
        vlans = list(all_vlans.keys())
        vlans.insert(0, "ALL")
        select = SelectField("Выберите VLAN ID", choices=vlans, validators=[InputRequired()])

    submit = SubmitField("Получить информацию")
