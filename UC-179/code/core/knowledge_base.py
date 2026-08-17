"""
Codificando.AI - UC-179
Base de conocimiento autónoma: única fuente de verdad persistente
(SQLite) del pipeline de reentrenamiento continuo. Almacena datos de
entrenamiento, anotaciones, historial de versiones de modelo y telemetría
de uso en producción (para retroalimentar el propio pipeline).

Es el módulo reutilizable de acceso a datos: tanto `core.data_collector`,
`models.trainer`, `core.deployment_manager` como `pipeline_service`
dependen únicamente de esta interfaz, nunca de SQL directo.
"""

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, List, Optional, Union


class KnowledgeBase:
    def __init__(self, db_path: Union[str, Path] = "knowledge_base.db"):
        self.db_path = str(db_path)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def _connection(self):
        conn = sqlite3.connect(self.db_path)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._connection() as conn:
            cursor = conn.cursor()

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS training_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    data_hash TEXT UNIQUE,
                    input_data TEXT,
                    output_data TEXT,
                    metadata TEXT,
                    source TEXT,
                    validated BOOLEAN DEFAULT 0,
                    quality_score REAL
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS annotations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    data_id INTEGER,
                    annotation_type TEXT,
                    content TEXT,
                    user_id TEXT,
                    FOREIGN KEY (data_id) REFERENCES training_data(id)
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS model_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    model_version TEXT,
                    model_path TEXT,
                    metrics TEXT,
                    training_samples INTEGER,
                    training_type TEXT DEFAULT 'full',
                    is_active BOOLEAN DEFAULT 0,
                    is_deployed BOOLEAN DEFAULT 0
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS usage_tracking (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    input_text TEXT,
                    output_text TEXT,
                    user_feedback TEXT,
                    confidence_score REAL,
                    processing_time_ms INTEGER
                )
            ''')

    # ------------------------------------------------------------------
    # Datos de entrenamiento
    # ------------------------------------------------------------------
    def add_training_data(self, input_data: str, output_data: str, source: str = "user",
                           metadata: Optional[Dict] = None, quality_score: float = 1.0) -> Optional[int]:
        data_hash = hashlib.sha256(f"{input_data}{output_data}".encode()).hexdigest()

        with self._connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute('''
                    INSERT OR IGNORE INTO training_data
                    (data_hash, input_data, output_data, metadata, source, quality_score)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (data_hash, input_data, output_data, json.dumps(metadata or {}), source, quality_score))
                return cursor.lastrowid if cursor.rowcount else None
            except sqlite3.Error:
                return None

    def add_annotation(self, data_id: int, annotation_type: str, content: str,
                        user_id: str = "system") -> int:
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO annotations (data_id, annotation_type, content, user_id)
                VALUES (?, ?, ?, ?)
            ''', (data_id, annotation_type, content, user_id))
            return cursor.lastrowid

    def track_usage(self, input_text: str, output_text: str, confidence_score: float,
                     processing_time_ms: int, user_feedback: Optional[str] = None) -> int:
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO usage_tracking
                (input_text, output_text, user_feedback, confidence_score, processing_time_ms)
                VALUES (?, ?, ?, ?, ?)
            ''', (input_text, output_text, user_feedback, confidence_score, processing_time_ms))
            return cursor.lastrowid

    def get_new_samples_count(self, since_timestamp: Optional[str] = None) -> int:
        """Cuenta muestras *validadas* (aprobadas para entrenamiento) que
        aún no han sido incorporadas a un entrenamiento — es decir, las
        que llegaron después de `since_timestamp` (normalmente el
        timestamp del último modelo entrenado). `validated=0` representa
        datos recién ingeridos pendientes de revisión/aprobación, por lo
        que deliberadamente se excluyen de este conteo."""
        with self._connection() as conn:
            cursor = conn.cursor()
            if since_timestamp:
                cursor.execute(
                    "SELECT COUNT(*) FROM training_data WHERE timestamp > ? AND validated = 1",
                    (since_timestamp,))
            else:
                cursor.execute("SELECT COUNT(*) FROM training_data WHERE validated = 1")
            return cursor.fetchone()[0]

    def get_training_data(self, validated_only: bool = True, limit: Optional[int] = None) -> List[Dict]:
        with self._connection() as conn:
            cursor = conn.cursor()
            query = "SELECT id, input_data, output_data, quality_score FROM training_data"
            if validated_only:
                query += " WHERE validated = 1"
            query += " ORDER BY quality_score DESC"
            if limit:
                query += " LIMIT ?"
                cursor.execute(query, (limit,))
            else:
                cursor.execute(query)
            rows = cursor.fetchall()

        return [{"id": row[0], "input": row[1], "output": row[2], "quality": row[3]} for row in rows]

    def get_pending_sample_ids(self) -> List[int]:
        """IDs de muestras ingeridas aún no aprobadas para entrenamiento
        (`validated = 0`)."""
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM training_data WHERE validated = 0")
            return [row[0] for row in cursor.fetchall()]

    def validate_samples(self, sample_ids: List[int]) -> None:
        if not sample_ids:
            return
        with self._connection() as conn:
            cursor = conn.cursor()
            placeholders = ",".join("?" * len(sample_ids))
            cursor.execute(f"UPDATE training_data SET validated = 1 WHERE id IN ({placeholders})", sample_ids)

    # ------------------------------------------------------------------
    # Historial de modelos
    # ------------------------------------------------------------------
    def register_model(self, model_version: str, model_path: str, metrics: Dict,
                        training_samples: int, training_type: str = "full") -> int:
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE model_history SET is_active = 0')
            cursor.execute('''
                INSERT INTO model_history
                (model_version, model_path, metrics, training_samples, training_type, is_active)
                VALUES (?, ?, ?, ?, ?, 1)
            ''', (model_version, model_path, json.dumps(metrics), training_samples, training_type))
            return cursor.lastrowid

    def mark_model_deployed(self, model_version: str) -> None:
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE model_history SET is_deployed = 0')
            cursor.execute(
                'UPDATE model_history SET is_deployed = 1 WHERE model_version = ?', (model_version,))

    def get_last_training_timestamp(self) -> Optional[str]:
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT timestamp FROM model_history ORDER BY id DESC LIMIT 1')
            result = cursor.fetchone()
            return result[0] if result else None

    def get_active_model_path(self) -> Optional[str]:
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT model_path FROM model_history WHERE is_active = 1 '
                'ORDER BY id DESC LIMIT 1')
            result = cursor.fetchone()
            return result[0] if result else None

    def get_active_model_metrics(self) -> Optional[Dict]:
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT metrics FROM model_history WHERE is_active = 1 '
                'ORDER BY id DESC LIMIT 1')
            result = cursor.fetchone()
            return json.loads(result[0]) if result else None

    def get_deployed_model(self) -> Optional[Dict]:
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT model_version, model_path, metrics, training_samples, timestamp
                FROM model_history WHERE is_deployed = 1 ORDER BY id DESC LIMIT 1
            ''')
            row = cursor.fetchone()

        if not row:
            return None
        return {
            "model_version": row[0], "model_path": row[1],
            "metrics": json.loads(row[2]), "training_samples": row[3], "timestamp": row[4],
        }

    def get_model_history(self, limit: int = 20) -> List[Dict]:
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT model_version, model_path, metrics, training_samples,
                       training_type, is_active, is_deployed, timestamp
                FROM model_history ORDER BY id DESC LIMIT ?
            ''', (limit,))
            rows = cursor.fetchall()

        return [{
            "model_version": r[0], "model_path": r[1], "metrics": json.loads(r[2]),
            "training_samples": r[3], "training_type": r[4],
            "is_active": bool(r[5]), "is_deployed": bool(r[6]), "timestamp": r[7],
        } for r in rows]
