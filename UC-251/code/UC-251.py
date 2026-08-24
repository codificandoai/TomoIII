"""Codificando.AI - UC-251: RAG híbrida empresarial.

CLI para ingesta, consulta, evaluación RAGAS y servidor API del pipeline de
búsqueda híbrida (BM25 + vectorial), re-ranking, fragmentación semántica y
generación con citas.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

from config import RAGConfig
from models import EvaluationSample
from rag_pipeline import RAGPipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("uc251-cli")


def _load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _save_json(path: str, data: Any) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)


def cmd_ingest(args: argparse.Namespace) -> int:
    config = RAGConfig()
    pipeline = RAGPipeline(config)
    metadata = {}
    if args.metadata:
        metadata = json.loads(args.metadata)

    if args.path:
        result = pipeline.ingest_document(
            args.path,
            doc_type=args.doc_type,
            title=args.title or Path(args.path).name,
            metadata=metadata,
        )
    elif args.text:
        result = pipeline.ingest_text(args.text, title=args.title or "inline", metadata=metadata)
    else:
        print("Debe especificar --path o --text", file=sys.stderr)
        return 1

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_query(args: argparse.Namespace) -> int:
    config = RAGConfig()
    pipeline = RAGPipeline(config)
    for path in args.ingest or []:
        logger.info("Ingestando: %s", path)
        pipeline.ingest_document(path, title=Path(path).name)

    filters = json.loads(args.filters) if args.filters else {}
    response = pipeline.query(
        question=args.question,
        filters=filters,
        top_k=args.top_k,
        user_clearance=args.user_clearance,
        tenant_id=args.tenant_id,
    )
    output = response.to_dict()
    if args.output:
        _save_json(args.output, output)
    else:
        print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


def cmd_evaluate(args: argparse.Namespace) -> int:
    config = RAGConfig()
    pipeline = RAGPipeline(config)
    dataset = _load_json(args.dataset)
    if not isinstance(dataset, list):
        dataset = dataset.get("samples", [])
    samples = [
        EvaluationSample(
            query=item["query"],
            ground_truth=item["ground_truth"],
            reference_contexts=item.get("reference_contexts", []),
            expected_doc_ids=item.get("expected_doc_ids", []),
            metadata=item.get("metadata", {}),
        )
        for item in dataset
    ]
    result = pipeline.evaluate(samples, tenant_id=args.tenant_id)
    if args.output:
        _save_json(args.output, result)
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    os.environ["UC251_PORT"] = str(args.port)
    import api as api_module  # noqa: F401
    from api import app

    logger.info("Servidor UC-251 iniciado en http://0.0.0.0:%d", args.port)
    app.run(host="0.0.0.0", port=args.port, debug=False)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="UC-251",
        description="Pipeline RAG híbrida empresarial: ingesta, query, evaluación y API.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    ingest = sub.add_parser("ingest", help="Ingesta un documento o texto.")
    ingest.add_argument("--path", help="Ruta al archivo")
    ingest.add_argument("--text", help="Texto plano")
    ingest.add_argument("--title", help="Título del documento")
    ingest.add_argument("--doc-type", help="Tipo de documento (pdf, docx, ...)")
    ingest.add_argument("--metadata", help="Metadatos JSON")

    query_cmd = sub.add_parser("query", help="Ejecuta una consulta RAG.")
    query_cmd.add_argument("question", help="Pregunta")
    query_cmd.add_argument("--ingest", action="append", help="Archivo a ingestar previamente")
    query_cmd.add_argument("--filters", help="Filtros JSON")
    query_cmd.add_argument("--top-k", type=int, default=None)
    query_cmd.add_argument("--user-clearance", default=None)
    query_cmd.add_argument("--tenant-id", default=None)
    query_cmd.add_argument("--output", help="Archivo JSON de salida")

    eval_cmd = sub.add_parser("evaluate", help="Evalúa con RAGAS.")
    eval_cmd.add_argument("dataset", help="JSON con lista de muestras")
    eval_cmd.add_argument("--tenant-id", default=None)
    eval_cmd.add_argument("--output", help="Archivo JSON de salida")

    serve = sub.add_parser("serve", help="Levanta la API Flask.")
    serve.add_argument("--port", type=int, default=int(os.getenv("UC251_PORT", "5251")))

    return parser


def main(argv: List[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    dispatch = {
        "ingest": cmd_ingest,
        "query": cmd_query,
        "evaluate": cmd_evaluate,
        "serve": cmd_serve,
    }
    return dispatch[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
