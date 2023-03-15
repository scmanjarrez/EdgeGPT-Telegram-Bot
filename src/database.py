#!/usr/bin/env python3

# SPDX-License-Identifier: MIT

# Copyright (c) 2023 scmanjarrez. All rights reserved.
# This work is licensed under the terms of the MIT license.

import sqlite3 as sql

from contextlib import closing

import utils as ut


def setup_db() -> None:
    with closing(sql.connect(ut.path("database"))) as db:
        with closing(db.cursor()) as cur:
            cur.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    cid TEXT PRIMARY KEY,
                    voice TEXT DEFAULT 'en-US-AnaNeural',
                    tts INTEGER DEFAULT -1,
                    style TEXT DEFAULT 'balanced'
                );
                """
            )


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


def voice(cid: int) -> int:
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
                "UPDATE users SET tts = -tts " "WHERE cid = ?",
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
