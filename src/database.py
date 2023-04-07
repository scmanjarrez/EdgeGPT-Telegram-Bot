#!/usr/bin/env python3

# SPDX-License-Identifier: MIT

# Copyright (c) 2023 scmanjarrez. All rights reserved.
# This work is licensed under the terms of the MIT license.

import sqlite3 as sql

from contextlib import closing

import utils as ut


CHAT_BACKENDS = ["bing", "chatgpt", "chatgpt4"]
ASR_BACKENDS = ["whisper", "assemblyai"]
IMAGE_BACKENDS = ["bing", "dall-e"]


def setup_db() -> None:
    with closing(sql.connect(ut.path("database"))) as db:
        with closing(db.cursor()) as cur:
            cur.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    cid INTEGER PRIMARY KEY,
                    voice TEXT DEFAULT 'en-US-AnaNeural',
                    tts INTEGER DEFAULT -1,
                    style TEXT DEFAULT 'balanced',
                    chat_backend TEXT DEFAULT 'bing',
                    asr_backend TEXT DEFAULT 'whisper',
                    image_backend TEXT DEFAULT 'bing'
                );
                """
            )


def update_db() -> None:
    with closing(sql.connect(ut.path("database"))) as db:
        with closing(db.cursor()) as cur:
            try:
                cur.execute(
                    "ALTER TABLE users "
                    "ADD COLUMN chat_backend TEXT DEFAULT 'bing'"
                )
            except sql.OperationalError:
                pass
            try:
                cur.execute(
                    "ALTER TABLE users "
                    "ADD COLUMN asr_backend TEXT DEFAULT 'whisper'"
                )
            except sql.OperationalError:
                pass
            try:
                cur.execute(
                    "ALTER TABLE users "
                    "ADD COLUMN image_backend TEXT DEFAULT 'bing'"
                )
            except sql.OperationalError:
                pass


def cached(cid: int) -> int:
    with closing(sql.connect(ut.path("database"))) as db:
        with closing(db.cursor()) as cur:
            cur.execute(
                "SELECT EXISTS (SELECT 1 FROM users WHERE cid = ?)",
                [cid],
            )
            return cur.fetchone()[0]


def add_user(cid: int) -> None:
    with closing(sql.connect(ut.path("database"))) as db:
        with closing(db.cursor()) as cur:
            cur.execute("INSERT INTO users (cid) VALUES (?)", [cid])
            db.commit()


def voice(cid: int) -> str:
    with closing(sql.connect(ut.path("database"))) as db:
        with closing(db.cursor()) as cur:
            cur.execute("SELECT voice FROM users WHERE cid = ?", [cid])
            return cur.fetchone()[0]


def set_voice(cid: int, value: str) -> None:
    with closing(sql.connect(ut.path("database"))) as db:
        with closing(db.cursor()) as cur:
            cur.execute(
                "UPDATE users SET voice = ? WHERE cid = ?",
                [value, cid],
            )
            db.commit()


def tts(cid: int) -> int:
    with closing(sql.connect(ut.path("database"))) as db:
        with closing(db.cursor()) as cur:
            cur.execute("SELECT tts FROM users WHERE cid = ?", [cid])
            return cur.fetchone()[0]


def toggle_tts(cid: int) -> None:
    with closing(sql.connect(ut.path("database"))) as db:
        with closing(db.cursor()) as cur:
            cur.execute(
                "UPDATE users SET tts = -tts WHERE cid = ?",
                [cid],
            )
            db.commit()


def style(cid: int) -> str:
    with closing(sql.connect(ut.path("database"))) as db:
        with closing(db.cursor()) as cur:
            cur.execute("SELECT style FROM users WHERE cid = ?", [cid])
            return cur.fetchone()[0]


def set_style(cid: int, value: str) -> None:
    with closing(sql.connect(ut.path("database"))) as db:
        with closing(db.cursor()) as cur:
            cur.execute(
                "UPDATE users SET style = ? WHERE cid = ?",
                [value, cid],
            )
            db.commit()


def chat_backend(cid: int) -> str:
    with closing(sql.connect(ut.path("database"))) as db:
        with closing(db.cursor()) as cur:
            cur.execute("SELECT chat_backend FROM users WHERE cid = ?", [cid])
            return cur.fetchone()[0]


def set_chat_backend(cid: int, backend: str) -> None:
    with closing(sql.connect(ut.path("database"))) as db:
        with closing(db.cursor()) as cur:
            cur.execute(
                "UPDATE users SET chat_backend = ? WHERE cid = ?",
                [backend, cid],
            )
            db.commit()


def asr_backend(cid: int) -> str:
    with closing(sql.connect(ut.path("database"))) as db:
        with closing(db.cursor()) as cur:
            cur.execute("SELECT asr_backend FROM users WHERE cid = ?", [cid])
            return cur.fetchone()[0]


def set_asr_backend(cid: int, backend: str) -> None:
    with closing(sql.connect(ut.path("database"))) as db:
        with closing(db.cursor()) as cur:
            cur.execute(
                "UPDATE users SET asr_backend = ? WHERE cid = ?",
                [backend, cid],
            )
            db.commit()


def image_backend(cid: int) -> str:
    with closing(sql.connect(ut.path("database"))) as db:
        with closing(db.cursor()) as cur:
            cur.execute("SELECT image_backend FROM users WHERE cid = ?", [cid])
            return cur.fetchone()[0]


def set_image_backend(cid: int, backend: str) -> None:
    with closing(sql.connect(ut.path("database"))) as db:
        with closing(db.cursor()) as cur:
            cur.execute(
                "UPDATE users SET image_backend = ? WHERE cid = ?",
                [backend, cid],
            )
            db.commit()
