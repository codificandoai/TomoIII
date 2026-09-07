"""
UC-083 — Reprocesador seguro de particiones batch con chunking y concurrencia.

Simula el reprocesamiento de particiones afectadas usando chunks controlados,
checkpoints idempotentes y límites de concurrencia para evitar degradar
servicios dependientes.
"""

import csv
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional, Any, Callable

from incident_models import IncidentResponseConfig, Mitigation, MitigationType, Checkpoint
from checkpoint_manager import CheckpointManager


class Reprocessor:
    """
    Reprocesa un archivo CSV dividiéndolo en chunks y ejecutando inferencia
simulada con concurrencia controlada. Registra checkpoints idempotentes.
    """

    def __init__(
        self,
        pipeline_id: str,
        config: Optional[IncidentResponseConfig] = None,
        checkpoint_manager: Optional[CheckpointManager] = None,
    ):
        self.config = config or IncidentResponseConfig()
        self.checkpoint_manager = checkpoint_manager or CheckpointManager(pipeline_id=pipeline_id)
        self.pipeline_id = pipeline_id

    def chunk_file(self, file_path: str, chunk_size_rows: Optional[int] = None) -> List[str]:
        """Divide un archivo CSV en archivos chunk temporales."""
        chunk_size = chunk_size_rows or self.config.chunk_size_rows
        chunk_files = []
        try:
            with open(file_path, "r", encoding="utf-8", newline="") as f:
                reader = csv.DictReader(f)
                fieldnames = reader.fieldnames
                chunk_index = 0
                rows = []
                for row in reader:
                    rows.append(row)
                    if len(rows) >= chunk_size:
                        chunk_path = self._write_chunk(fieldnames, rows, chunk_index)
                        chunk_files.append(chunk_path)
                        rows = []
                        chunk_index += 1
                if rows:
                    chunk_path = self._write_chunk(fieldnames, rows, chunk_index)
                    chunk_files.append(chunk_path)
        except Exception as e:
            raise ValueError(f"No se pudo leer el archivo para chunking: {e}")
        return chunk_files

    def _write_chunk(self, fieldnames: List[str], rows: List[Dict[str, str]], index: int) -> str:
        chunk_path = f"{self.pipeline_id}_chunk_{index:04d}.csv"
        with open(chunk_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        return chunk_path

    def run_chunk(
        self,
        chunk_path: str,
        partition_id: str,
        inference_fn: Optional[Callable[[List[Dict[str, str]]], List[Dict[str, Any]]]] = None,
    ) -> Checkpoint:
        """
        Ejecuta inferencia sobre un chunk si no está completado. Retorna un checkpoint.
        """
        if self.checkpoint_manager.is_completed(partition_id):
            existing = self.checkpoint_manager.get(partition_id)
            existing.metadata.setdefault("skipped", True)
            return existing

        try:
            with open(chunk_path, "r", encoding="utf-8", newline="") as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            if inference_fn is None:
                results = self._dummy_inference(rows)
            else:
                results = inference_fn(rows)

            # Simular costo computacional
            time.sleep(0.001 * len(rows))
            return self.checkpoint_manager.complete(
                partition_id=partition_id,
                records_processed=len(results),
                metadata={"chunk": chunk_path, "status": "ok"},
            )
        except Exception as e:
            return self.checkpoint_manager.fail(partition_id, str(e))

    def _dummy_inference(self, rows: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """Inferencia dummy usada para validación sin dependencias ML."""
        results = []
        for row in rows:
            out = dict(row)
            out["prediction"] = 1.0
            out["score"] = 0.95
            results.append(out)
        return results

    def reprocess(
        self,
        file_path: str,
        inference_fn: Optional[Callable[[List[Dict[str, str]]], List[Dict[str, Any]]]] = None,
    ) -> Dict[str, Any]:
        """
        Reprocesa un archivo batch de forma segura: chunking + concurrencia
controlada + checkpoints idempotentes.
        """
        chunk_files = self.chunk_file(file_path)
        partition_ids = [os.path.basename(c) for c in chunk_files]
        pending = self.checkpoint_manager.pending_partitions(partition_ids)

        completed = 0
        failed = 0
        with ThreadPoolExecutor(max_workers=self.config.max_concurrency) as executor:
            futures = {
                executor.submit(self.run_chunk, chunk, pid, inference_fn): (chunk, pid)
                for chunk, pid in zip(chunk_files, partition_ids)
                if pid in pending or not self.checkpoint_manager.is_completed(pid)
            }
            for future in as_completed(futures):
                checkpoint = future.result()
                if checkpoint.status == "completed":
                    completed += 1
                else:
                    failed += 1

        stats = self.checkpoint_manager.get_statistics()
        # Limpieza de chunks temporales
        for chunk in chunk_files:
            try:
                os.remove(chunk)
            except Exception:
                pass

        return {
            "total_chunks": len(chunk_files),
            "completed": completed,
            "failed": failed,
            "stats": stats,
        }

    def get_statistics(self) -> Dict[str, Any]:
        return self.checkpoint_manager.get_statistics()

    def reset(self) -> None:
        self.checkpoint_manager.reset()
