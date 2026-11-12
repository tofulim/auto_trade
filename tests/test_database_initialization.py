import os
import sqlite3
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


class DatabaseInitializationTests(unittest.TestCase):
    """예전 DB 모듈이 볼륨으로 연결된 배포 환경의 테이블 생성을 검증한다."""

    def test_legacy_database_module_creates_new_tables_without_losing_data(self) -> None:
        """새 프로세스에서도 예전 볼륨의 DB 초기화가 신규 테이블을 생성한다."""
        source = Path(__file__).resolve().parents[1] / "fastapi_server"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            module = root / "database"
            module.mkdir()
            (module / "__init__.py").write_text("")
            (module / "database.py").write_text(
                textwrap.dedent(
                    """\
                from entity.asset import Asset
                from entity.portfolio import Portfolio
                from sqlmodel import SQLModel, create_engine

                class Database:
                    def __init__(self, db_name):
                        self.engine = create_engine(f"sqlite:///{db_name}")
                        SQLModel.metadata.create_all(self.engine)
                """
                )
            )
            path = root / "auto_trade.db"
            with sqlite3.connect(path) as connection:
                connection.execute("CREATE TABLE asset (id INTEGER PRIMARY KEY, budget INTEGER NOT NULL)")
                connection.execute("INSERT INTO asset VALUES (1, 12345)")
            script = textwrap.dedent(
                """\
                import sys
                from database.database import Database
                Database(sys.argv[1])
                Database(sys.argv[1])
                """
            )
            subprocess.run(
                [sys.executable, "-c", script, str(path)],
                cwd=root,
                env=dict(os.environ, PYTHONPATH=os.pathsep.join([str(root), str(source)])),
                check=True,
                capture_output=True,
                text=True,
            )
            with sqlite3.connect(path) as connection:
                tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                self.assertTrue({"asset", "portfolio", "tradingsettings", "takeprofit"}.issubset(tables))
                self.assertEqual(connection.execute("SELECT budget FROM asset WHERE id=1").fetchone(), (12345,))


if __name__ == "__main__":
    unittest.main()
