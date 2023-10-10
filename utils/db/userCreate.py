"""Function for creating a user in database."""

__author__ = "ZHEZLYAEV Aleksandr  <zhezlyaev@gmail.com>"
__version__ = "1.0"

# -*- coding: utf-8 -*-

import typer

from main import User, app, db

typer_app = typer.Typer()


@typer_app.command()
def create(
    username: str = typer.Option(
        ...,
        "-u",
        "--username",
        prompt="Enter username",
        help="Username for authentication",
    ),
    password: str = typer.Option(
        ...,
        "-p",
        "--password",
        prompt="Enter password",
        hide_input=True,
        help="Password for authentication",
    ),
    password2: str = typer.Option(
        ...,
        "-pr",
        "--password-repeat",
        prompt="Reapet password",
        hide_input=True,
        help="Reapet password for authentication",
    ),
):
    """Create new user."""

    with app.app_context():
        if password == password2:
            try:
                new_user = User(username=username)
                new_user.set_password(password)
                db.session.add(new_user)
                db.session.commit()
                print(f"Пользователь {username} добавлен в базу.")
            except BaseException as error:
                print("An exception occurred: {}".format(error))

        else:
            print("Пароли не совпали")


if __name__ == "__main__":
    typer_app()
