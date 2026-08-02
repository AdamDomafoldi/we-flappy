#!/usr/bin/env python3
"""Minimal We Flappy web server with a MySQL-backed leaderboard."""

from __future__ import annotations

import json
import os
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import mysql.connector
from mysql.connector import Error as MySQLError

BASE_DIR = Path(__file__).resolve().parent

DB_CONFIG = {
    "host": os.getenv("MYSQL_HOST", "mysql"),
    "port": int(os.getenv("MYSQL_PORT", "3306")),
    "user": os.getenv("MYSQL_USER", "wedding"),
    "password": os.getenv("MYSQL_PASSWORD", "Berciokoses2fulevan/marica"),
    "database": os.getenv("MYSQL_DATABASE", "wedding"),
    "charset": os.getenv("MYSQL_CHARSET", "utf8"),
    "use_unicode": True,
    "autocommit": True,
}


def get_connection():
    return mysql.connector.connect(**DB_CONFIG)

class GameHandler(SimpleHTTPRequestHandler):
    server_version = "WeFlappy/1.0"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(BASE_DIR), **kwargs)

    def _send_json(self, payload: Any, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict[str, Any]:
        raw_length = self.headers.get("Content-Length", "0")
        try:
            length = int(raw_length)
        except ValueError as exc:
            raise ValueError("Érvénytelen Content-Length fejléc.") from exc
        if length <= 0 or length > 4096:
            raise ValueError("Érvénytelen kérésméret.")
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("Érvénytelen JSON-adat.") from exc

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/results":
            self._get_results()
            return
        if path == "/":
            self.path = "/index.html"
        super().do_GET()

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/results":
            self._create_result()
            return
        self._send_json({"error": "Az útvonal nem található."}, HTTPStatus.NOT_FOUND)

    def _get_results(self) -> None:
        query = """
            SELECT username, score, created_at
            FROM we_flappy_results
            ORDER BY score DESC, created_at ASC, id ASC
            LIMIT 10
        """
        try:
            with get_connection() as connection:
                with connection.cursor(dictionary=True) as cursor:
                    cursor.execute(query)
                    rows = cursor.fetchall()
            results = [
                {
                    "username": row["username"],
                    "score": row["score"],
                    "date": row["created_at"].isoformat(),
                }
                for row in rows
            ]
            self._send_json(results)
        except MySQLError:
            self.log_error("MySQL error while reading results")
            self._send_json(
                {"error": "Az adatbázis jelenleg nem érhető el."},
                HTTPStatus.INTERNAL_SERVER_ERROR,
            )

    def _create_result(self) -> None:
        try:
            data = self._read_json()
            username = str(data.get("username", "")).strip()
            score = int(data.get("score", 0))
            if not username:
                raise ValueError("A felhasználónév kötelező.")
            if len(username) > 20:
                raise ValueError("A felhasználónév legfeljebb 20 karakter lehet.")
            if score < 0 or score > 1_000_000:
                raise ValueError("Érvénytelen pontszám.")

            with get_connection() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "INSERT INTO we_flappy_results (username, score) VALUES (%s, %s)",
                        (username, score),
                    )
                    result_id = cursor.lastrowid
            self._send_json({"id": result_id}, HTTPStatus.CREATED)
        except ValueError as exc:
            self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        except MySQLError:
            self.log_error("MySQL error while saving result")
            self._send_json(
                {"error": "Az eredmény mentése adatbázishiba miatt nem sikerült."},
                HTTPStatus.INTERNAL_SERVER_ERROR,
            )

    def log_message(self, format: str, *args: Any) -> None:
        print(f"[{self.log_date_time_string()}] {self.address_string()} - {format % args}")


def main() -> None:
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    server = ThreadingHTTPServer((host, port), GameHandler)
    print(f"We Flappy fut: http://localhost:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nLeállítás.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
