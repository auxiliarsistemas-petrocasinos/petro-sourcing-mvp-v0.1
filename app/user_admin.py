from __future__ import annotations

import argparse
import getpass
import sqlite3

from .auth import (
    hash_password,
    validate_password,
    validate_username,
)
from .db import (
    create_user,
    delete_sessions_for_user,
    get_user_by_username,
    init_db,
    list_users,
    set_user_active,
    update_user_password,
)


def ask_password() -> str:
    password = getpass.getpass(
        "Contraseña: "
    )
    confirm = getpass.getpass(
        "Confirmar contraseña: "
    )

    if password != confirm:
        raise SystemExit(
            "Las contraseñas no coinciden."
        )

    try:
        validate_password(password)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    return password


def create_command(args) -> None:
    username = validate_username(
        args.username
    )
    password = ask_password()

    try:
        user_id = create_user(
            username=username,
            display_name=args.display_name.strip(),
            password_hash=hash_password(
                password
            ),
            role=args.role,
        )
    except sqlite3.IntegrityError as exc:
        raise SystemExit(
            "Ese usuario ya existe."
        ) from exc

    print(
        f"Usuario creado: {username} "
        f"(id={user_id}, rol={args.role})"
    )


def list_command(_args) -> None:
    rows = list_users()

    if not rows:
        print("No hay usuarios.")
        return

    for user in rows:
        status = (
            "activo"
            if user["active"]
            else "inactivo"
        )
        print(
            f'{user["id"]:>3}  '
            f'{user["username"]:<24} '
            f'{user["role"]:<6} '
            f'{status:<8} '
            f'{user["display_name"]}'
        )


def user_by_name(username: str) -> dict:
    normalized = validate_username(
        username
    )
    user = get_user_by_username(
        normalized
    )

    if not user:
        raise SystemExit(
            "Usuario no encontrado."
        )

    return user


def password_command(args) -> None:
    user = user_by_name(
        args.username
    )
    password = ask_password()

    update_user_password(
        user["id"],
        hash_password(password),
    )
    delete_sessions_for_user(
        user["id"]
    )

    print(
        "Contraseña actualizada y "
        "sesiones cerradas."
    )


def active_command(
    args,
    active: bool,
) -> None:
    user = user_by_name(
        args.username
    )

    set_user_active(
        user["id"],
        active,
    )
    delete_sessions_for_user(
        user["id"]
    )

    print(
        f'Usuario {user["username"]}: '
        f'{"activo" if active else "inactivo"}.'
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Administración local de usuarios "
            "de Abastecimiento AI."
        )
    )
    sub = parser.add_subparsers(
        required=True
    )

    create_parser = sub.add_parser(
        "create"
    )
    create_parser.add_argument(
        "username"
    )
    create_parser.add_argument(
        "display_name"
    )
    create_parser.add_argument(
        "--role",
        choices=("user", "admin"),
        default="user",
    )
    create_parser.set_defaults(
        handler=create_command
    )

    list_parser = sub.add_parser(
        "list"
    )
    list_parser.set_defaults(
        handler=list_command
    )

    password_parser = sub.add_parser(
        "reset-password"
    )
    password_parser.add_argument(
        "username"
    )
    password_parser.set_defaults(
        handler=password_command
    )

    disable_parser = sub.add_parser(
        "disable"
    )
    disable_parser.add_argument(
        "username"
    )
    disable_parser.set_defaults(
        handler=lambda args: active_command(
            args,
            False,
        )
    )

    enable_parser = sub.add_parser(
        "enable"
    )
    enable_parser.add_argument(
        "username"
    )
    enable_parser.set_defaults(
        handler=lambda args: active_command(
            args,
            True,
        )
    )

    args = parser.parse_args()
    init_db()
    args.handler(args)


if __name__ == "__main__":
    main()
