"""SQLite database operations."""

from __future__ import annotations

import json
import sqlite3
from typing import Optional

from opportunity_matrix.storage.models import Opportunity, Platform, Signal


class Database:
    def __init__(self, db_path: str = "opportunity_matrix.db"):
        self.db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
        return self._conn

    def initialize(self) -> None:
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS signals (
                id TEXT PRIMARY KEY,
                platform TEXT NOT NULL,
                platform_id TEXT NOT NULL,
                title TEXT NOT NULL,
                body TEXT DEFAULT '',
                url TEXT DEFAULT '',
                author TEXT DEFAULT '',
                upvotes INTEGER DEFAULT 0,
                comments_count INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                collected_at TEXT NOT NULL,
                raw_json TEXT DEFAULT '',
                metadata TEXT DEFAULT '{}',
                UNIQUE(platform, platform_id)
            );

            CREATE TABLE IF NOT EXISTS opportunities (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT DEFAULT '',
                category TEXT DEFAULT 'other',
                engagement_score REAL DEFAULT 0.0,
                cross_platform_score REAL DEFAULT 0.0,
                feasibility_score REAL DEFAULT 0.0,
                composite_score REAL DEFAULT 0.0,
                platform_count INTEGER DEFAULT 0,
                first_seen TEXT NOT NULL,
                last_seen TEXT NOT NULL,
                status TEXT DEFAULT 'new',
                llm_analysis TEXT
            );

            CREATE TABLE IF NOT EXISTS signal_opportunities (
                signal_id TEXT NOT NULL REFERENCES signals(id),
                opportunity_id TEXT NOT NULL REFERENCES opportunities(id),
                PRIMARY KEY (signal_id, opportunity_id)
            );

            CREATE INDEX IF NOT EXISTS idx_signals_platform ON signals(platform);
            CREATE INDEX IF NOT EXISTS idx_signals_collected ON signals(collected_at);
            CREATE INDEX IF NOT EXISTS idx_opportunities_score ON opportunities(composite_score);
            CREATE INDEX IF NOT EXISTS idx_opportunities_status ON opportunities(status);
        """)

    def list_tables(self) -> list[str]:
        rows = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        return [r["name"] for r in rows]

    def insert_signal(self, signal: Signal) -> None:
        try:
            self.conn.execute(
                """INSERT INTO signals
                   (id, platform, platform_id, title, body, url, author,
                    upvotes, comments_count, created_at, collected_at, raw_json, metadata)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    signal.id, signal.platform.value, signal.platform_id,
                    signal.title, signal.body, signal.url, signal.author,
                    signal.upvotes, signal.comments_count,
                    signal.created_at.isoformat(), signal.collected_at.isoformat(),
                    signal.raw_json, json.dumps(signal.metadata),
                ),
            )
            self.conn.commit()
        except sqlite3.IntegrityError:
            pass  # duplicate platform+platform_id — skip silently

    def get_signal_by_platform_id(self, platform: Platform, platform_id: str) -> Optional[Signal]:
        row = self.conn.execute(
            "SELECT * FROM signals WHERE platform = ? AND platform_id = ?",
            (platform.value, platform_id),
        ).fetchone()
        return self._row_to_signal(row) if row else None

    def get_signals(self, platform: Optional[Platform] = None, days: int = 30) -> list[Signal]:
        query = "SELECT * FROM signals WHERE 1=1"
        params: list = []
        if platform:
            query += " AND platform = ?"
            params.append(platform.value)
        query += " ORDER BY collected_at DESC"
        rows = self.conn.execute(query, params).fetchall()
        return [self._row_to_signal(r) for r in rows]

    def get_unlinked_signals(self) -> list[Signal]:
        rows = self.conn.execute(
            """SELECT s.* FROM signals s
               LEFT JOIN signal_opportunities so ON s.id = so.signal_id
               WHERE so.signal_id IS NULL
               ORDER BY s.collected_at DESC"""
        ).fetchall()
        return [self._row_to_signal(r) for r in rows]

    def insert_opportunity(self, opp: Opportunity) -> None:
        self.conn.execute(
            """INSERT INTO opportunities
               (id, title, description, category, engagement_score, cross_platform_score,
                feasibility_score, composite_score, platform_count, first_seen, last_seen,
                status, llm_analysis)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                opp.id, opp.title, opp.description, opp.category,
                opp.engagement_score, opp.cross_platform_score,
                opp.feasibility_score, opp.composite_score,
                opp.platform_count, opp.first_seen.isoformat(),
                opp.last_seen.isoformat(), opp.status, opp.llm_analysis,
            ),
        )
        self.conn.commit()

    def update_opportunity(self, opp: Opportunity) -> None:
        self.conn.execute(
            """UPDATE opportunities SET
               title=?, description=?, category=?, engagement_score=?,
               cross_platform_score=?, feasibility_score=?, composite_score=?,
               platform_count=?, first_seen=?, last_seen=?, status=?, llm_analysis=?
               WHERE id=?""",
            (
                opp.title, opp.description, opp.category,
                opp.engagement_score, opp.cross_platform_score,
                opp.feasibility_score, opp.composite_score,
                opp.platform_count, opp.first_seen.isoformat(),
                opp.last_seen.isoformat(), opp.status, opp.llm_analysis,
                opp.id,
            ),
        )
        self.conn.commit()

    def get_opportunities(
        self,
        min_score: float = 0.0,
        min_platforms: int = 0,
        category: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> list[Opportunity]:
        query = "SELECT * FROM opportunities WHERE composite_score >= ? AND platform_count >= ?"
        params: list = [min_score, min_platforms]
        if category:
            query += " AND category = ?"
            params.append(category)
        if status:
            query += " AND status = ?"
            params.append(status)
        query += " ORDER BY composite_score DESC LIMIT ?"
        params.append(limit)
        rows = self.conn.execute(query, params).fetchall()
        return [self._row_to_opportunity(r) for r in rows]

    def link_signal_opportunity(self, signal_id: str, opportunity_id: str) -> None:
        try:
            self.conn.execute(
                "INSERT INTO signal_opportunities (signal_id, opportunity_id) VALUES (?, ?)",
                (signal_id, opportunity_id),
            )
            self.conn.commit()
        except sqlite3.IntegrityError:
            pass

    def get_signals_for_opportunity(self, opportunity_id: str) -> list[Signal]:
        rows = self.conn.execute(
            """SELECT s.* FROM signals s
               JOIN signal_opportunities so ON s.id = so.signal_id
               WHERE so.opportunity_id = ?""",
            (opportunity_id,),
        ).fetchall()
        return [self._row_to_signal(r) for r in rows]

    def get_signal_count(self, platform: Optional[Platform] = None) -> int:
        if platform:
            row = self.conn.execute(
                "SELECT COUNT(*) as cnt FROM signals WHERE platform = ?",
                (platform.value,),
            ).fetchone()
        else:
            row = self.conn.execute("SELECT COUNT(*) as cnt FROM signals").fetchone()
        return row["cnt"]

    def _row_to_signal(self, row: sqlite3.Row) -> Signal:
        return Signal(
            id=row["id"],
            platform=Platform(row["platform"]),
            platform_id=row["platform_id"],
            title=row["title"],
            body=row["body"],
            url=row["url"],
            author=row["author"],
            upvotes=row["upvotes"],
            comments_count=row["comments_count"],
            created_at=row["created_at"],
            collected_at=row["collected_at"],
            raw_json=row["raw_json"],
            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
        )

    def _row_to_opportunity(self, row: sqlite3.Row) -> Opportunity:
        return Opportunity(
            id=row["id"],
            title=row["title"],
            description=row["description"],
            category=row["category"],
            engagement_score=row["engagement_score"],
            cross_platform_score=row["cross_platform_score"],
            feasibility_score=row["feasibility_score"],
            composite_score=row["composite_score"],
            platform_count=row["platform_count"],
            first_seen=row["first_seen"],
            last_seen=row["last_seen"],
            status=row["status"],
            llm_analysis=row["llm_analysis"],
        )

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None
