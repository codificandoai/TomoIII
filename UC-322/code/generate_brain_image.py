"""Genera diagrama de arquitectura AGI con UC-322 (Resolución de Conflictos).

Muestra el ecosistema completo:
  UC-315 decide → UC-322 resuelve → UC-324 contiene → UC-317 ejecuta

Salida: /Users/utron/Documents/code-books/TomoIII/UC-322/agi_brain_architecture.png
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch


@dataclass
class Box:
    id: str
    label: str
    x: float
    y: float
    w: float = 0.11
    h: float = 0.075
    color: str = "#1a1a2e"
    edge: str = "#00d4ff"
    text: str = "#ffffff"
    fontsize: int = 8


@dataclass
class Arrow:
    src: str
    dst: str
    label: str = ""
    color: str = "#aaaaaa"
    rad: float = 0.0


def b(id_, label, x, y, **kw):
    return Box(id=id_, label=label, x=x, y=y, **kw)


# ---------------------------------------------------------------------------
# BOXES
# ---------------------------------------------------------------------------
boxes: List[Box] = [
    # --- Entorno / Percepción ---
    b("ENV", "ENTORNO\nticks / noticias / riesgo", 0.02, 0.90, w=0.10, h=0.07, edge="#00d4ff"),
    b("PER", "PERCEPCIÓN\ncentral_brain.py\nMarketPerceptionPipeline", 0.15, 0.90, w=0.13, h=0.08, edge="#00d4ff"),

    # --- Workspace Global (GWT) ---
    b("GWT", "WORKSPACE GLOBAL (GWT)\nglobal_workspace.py\nbuild + broadcast", 0.31, 0.93, w=0.16, h=0.08, edge="#bd00ff"),
    b("MON", "MONITOR\nMETACOGNITIVO\nmetacognitive_monitor.py", 0.49, 0.93, w=0.13, h=0.08, edge="#ff6b00"),
    b("SELF", "SELF-MODEL\nself_model_store.py", 0.26, 0.82, w=0.10, h=0.06, edge="#bd00ff"),
    b("EPI", "MEMORIA\nEPISÓDICA\nlong_term_memory.py", 0.37, 0.82, w=0.10, h=0.06, edge="#bd00ff"),
    b("HYP", "HIPÓTESIS\nCentralBrain / ToT", 0.48, 0.82, w=0.10, h=0.06, edge="#bd00ff"),

    # --- Cerebro Central ---
    b("CBR", "central_brain.py\nPredicción | Beliefs\nDesires | Intent\nWorld Model | Simulación", 0.31, 0.67, w=0.16, h=0.12, edge="#ff9f1c", fontsize=9),

    # --- ReAct + ToT ---
    b("TOT", "REACT + TREE OF THOUGHTS\nreact_tot.py\nexpand / prune / backtrack\nconsensus ask/bid", 0.53, 0.72, w=0.16, h=0.10, edge="#00c3ff", fontsize=8),

    # --- Agentes UC-315 (generan propuestas) ---
    b("BDI", "BDI + JUICE FILTER\nbdi.py / juice_agents.py", 0.20, 0.55, w=0.13, h=0.07, edge="#2ecc40"),
    b("TRD", "TRADING AGENTS\ntrading_agents.py\nvoto ponderado estático", 0.35, 0.55, w=0.13, h=0.07, edge="#2ecc40"),
    b("CNPO", "CNP ORIGINAL\ncnp_broadcast_middleware.py\nreliability estático", 0.50, 0.55, w=0.13, h=0.07, edge="#2ecc40"),

    # =====================================================================
    # UC-322: CAPA DE RESOLUCIÓN DE CONFLICTOS (nueva)
    # =====================================================================
    b("C322", "UC-322 — RESOLUCIÓN DE CONFLICTOS\nConflictResolutionLayer\n4 niveles | Reputación dinámica", 0.20, 0.44, w=0.46, h=0.06, edge="#ff00ff", fontsize=10),

    # Niveles internos de UC-322
    b("NEG", "Nivel 1\nNEGOCIACIÓN\nconcesiones", 0.20, 0.36, w=0.10, h=0.06, edge="#ff00ff"),
    b("VOT", "Nivel 2\nVOTACIÓN\nrep × conf", 0.31, 0.36, w=0.10, h=0.06, edge="#ff00ff"),
    b("CNPD", "Nivel 3\nCNP DINÁMICO\npujas + rep", 0.42, 0.36, w=0.10, h=0.06, edge="#ff00ff"),
    b("ESC", "Nivel 4\nESCALACIÓN\n4 veredictos", 0.53, 0.36, w=0.10, h=0.06, edge="#ff00ff"),

    # Subsistemas UC-322
    b("REP", "REPUTACIÓN\nDINÁMICA\nreputation_system.py", 0.20, 0.28, w=0.10, h=0.06, edge="#ff00ff"),
    b("DUP", "DUPLICADOS\nFingerprint SHA-256\nduplicate_detection.py", 0.31, 0.28, w=0.10, h=0.06, edge="#ff00ff"),
    b("DLK", "DEADLOCKS\nDFS ciclos\nduplicate_detection.py", 0.42, 0.28, w=0.10, h=0.06, edge="#ff00ff"),
    b("CBK", "CIRCUIT\nBREAKER\n3 conflictos → STOP", 0.53, 0.28, w=0.10, h=0.06, edge="#ff00ff"),

    # =====================================================================
    # UC-324: CONTENCIÓN Y GOBERNANZA
    # =====================================================================
    b("C324", "UC-324 — CONTENCIÓN Y GOBERNANZA\nContainmentSandbox (modo ENFORCE)\nPRE | EXEC | POST gates", 0.20, 0.18, w=0.46, h=0.06, edge="#ff3333", fontsize=10),

    b("PRE", "PRE GATE\nCapas A,B,C,E,G,H,I\nroles / injection / PII", 0.20, 0.10, w=0.14, h=0.06, edge="#ff3333"),
    b("EXEC", "EXEC GATE\nCapa F: HMAC\nnonce + anti-replay", 0.36, 0.10, w=0.14, h=0.06, edge="#ff3333"),
    b("POST", "POST GATE\nCapas D,J,K\naudit / trajectory", 0.52, 0.10, w=0.14, h=0.06, edge="#ff3333"),

    # =====================================================================
    # UC-317: KERNEL DE EJECUCIÓN
    # =====================================================================
    b("C317", "UC-317 — KERNEL DE EJECUCIÓN\nAgentKernel\nLLM + Tools + Memory + Scheduler", 0.72, 0.18, w=0.22, h=0.06, edge="#00ff88", fontsize=10),

    b("LLM", "LLM CORE\nOpenAI / Ollama\nMock", 0.72, 0.10, w=0.10, h=0.06, edge="#00ff88"),
    b("TOOL", "TOOL MANAGER\nherramientas", 0.84, 0.10, w=0.10, h=0.06, edge="#00ff88"),

    # --- Ejecución directa (SAF + EXE) ---
    b("SAF", "SAFETY SUPERVISOR\nsafety_supervisor_315.py", 0.68, 0.55, w=0.12, h=0.07, edge="#2ecc40"),
    b("EXE", "EJECUCIÓN\nexchange.py", 0.82, 0.55, w=0.10, h=0.07, edge="#2ecc40"),

    # --- Learning / World Model ---
    b("LWM", "APRENDIZAJE / WORLD MODEL\nworld_model.py\nupdate / retrain", 0.68, 0.44, w=0.14, h=0.07, edge="#00ff9f"),

    # --- UC-313 Plasticidad ---
    b("CEL", "UC-313 PLASTICIDAD\ncognitive_evolution_layer.py\nfitness / meta-red / EWC", 0.72, 0.72, w=0.15, h=0.09, edge="#ff0055", fontsize=8),
    b("CNP313", "CNP MIDDLEWARE\ncnp_broadcast_middleware.py", 0.72, 0.84, w=0.13, h=0.06, edge="#ffcc00"),
    b("CSL", "CURIOSITY\nSKILL LOOP\ncuriosity_skill_loop.py", 0.72, 0.93, w=0.11, h=0.06, edge="#ffcc00"),

    # --- Observabilidad ---
    b("OBS", "OBSERVABILIDAD\nPrometheus | Loki | Grafana\nmétricas + logs + trazas", 0.20, 0.01, w=0.46, h=0.06, edge="#ffaa00", fontsize=9),

    # --- Memoria AGI ---
    b("MEMP", "BRAIN MEMORY\nPIPELINE\nbrain_memory_pipeline.py", 0.84, 0.36, w=0.12, h=0.06, edge="#00ffcc"),
]

# ---------------------------------------------------------------------------
# ARROWS
# ---------------------------------------------------------------------------
arrows: List[Arrow] = [
    # Entorno -> Percepción -> GWT
    Arrow("ENV", "PER", "datos brutos", "#00d4ff"),
    Arrow("PER", "GWT", "snapshots", "#00d4ff", rad=0.1),
    Arrow("PER", "CBR", "ticks", "#00d4ff", rad=-0.05),

    # GWT broadcast
    Arrow("GWT", "SELF", "", "#bd00ff", rad=0.05),
    Arrow("GWT", "EPI", "", "#bd00ff"),
    Arrow("GWT", "HYP", "", "#bd00ff", rad=-0.05),
    Arrow("GWT", "MON", "workspace", "#ff6b00", rad=0.05),
    Arrow("GWT", "CBR", "hipótesis\nseleccionada", "#bd00ff", rad=-0.1),

    # Cerebro central <-> ToT
    Arrow("CBR", "TOT", "predicciones", "#00c3ff", rad=0.1),
    Arrow("TOT", "CBR", "consenso", "#00c3ff", rad=0.1),

    # Cerebro central -> Agentes
    Arrow("CBR", "BDI", "beliefs", "#2ecc40", rad=-0.05),
    Arrow("CBR", "TRD", "señales", "#2ecc40"),
    Arrow("TOT", "TRD", "síntesis", "#00c3ff", rad=-0.1),

    # Agentes -> UC-322 (propuestas conflictivas)
    Arrow("BDI", "C322", "propuestas", "#ff00ff", rad=0.0),
    Arrow("TRD", "C322", "votos", "#ff00ff", rad=0.0),
    Arrow("CNPO", "C322", "pujas", "#ff00ff", rad=0.0),

    # UC-322 internos
    Arrow("C322", "NEG", "", "#ff00ff"),
    Arrow("NEG", "VOT", "si falla →", "#ff00ff"),
    Arrow("VOT", "CNPD", "si falla →", "#ff00ff"),
    Arrow("CNPD", "ESC", "si falla →", "#ff00ff"),

    # UC-322 subsistemas
    Arrow("REP", "VOT", "pesos", "#ff00ff", rad=0.1),
    Arrow("REP", "CNPD", "scores", "#ff00ff", rad=0.1),
    Arrow("DUP", "C322", "detectar", "#ff00ff", rad=0.15),
    Arrow("DLK", "C322", "ciclos", "#ff00ff", rad=0.15),
    Arrow("CBK", "ESC", "STOP", "#ff3333", rad=0.1),

    # UC-322 -> UC-324 (resolución = evidencia, requiere validación)
    Arrow("C322", "C324", "resolución\n(evidencia)", "#ff3333", rad=0.0),

    # UC-324 gates
    Arrow("C324", "PRE", "", "#ff3333"),
    Arrow("C324", "EXEC", "", "#ff3333"),
    Arrow("C324", "POST", "", "#ff3333"),

    # UC-324 -> UC-317 (acción autorizada)
    Arrow("C324", "C317", "acción\nautorizada", "#00ff88", rad=-0.1),

    # UC-317 internos
    Arrow("C317", "LLM", "", "#00ff88"),
    Arrow("C317", "TOOL", "", "#00ff88"),

    # Safety + Ejecución directa
    Arrow("CNPO", "SAF", "candidata", "#2ecc40"),
    Arrow("SAF", "EXE", "aprobada", "#2ecc40"),

    # Ejecución -> Learning
    Arrow("EXE", "LWM", "resultado", "#00ff9f"),
    Arrow("LWM", "CBR", "feedback", "#00ff9f", rad=-0.2),

    # Feedback: resultado -> UC-322 reputación
    Arrow("EXE", "REP", "éxito/fallo →\nactualizar rep", "#ff00ff", rad=-0.2),

    # Ejecución -> Memoria
    Arrow("EXE", "MEMP", "episodios", "#00ffcc"),

    # MetacognitiveMonitor -> UC-322 escalación
    Arrow("MON", "ESC", "veredicto\nREVIEW/STOP", "#ff6b00", rad=-0.15),

    # UC-313 Plasticidad
    Arrow("MON", "CEL", "coherencia", "#ff6b00", rad=-0.05),
    Arrow("CEL", "CBR", "reescribir\nparámetros", "#ff0055", rad=-0.05),
    Arrow("CEL", "CNP313", "evaluar\nagentes", "#ffcc00"),
    Arrow("CSL", "CEL", "nuevo\nskill", "#ffcc00"),

    # UC-322 observabilidad
    Arrow("C322", "OBS", "logs + spans +\nmétricas", "#ffaa00", rad=0.0),
    Arrow("C324", "OBS", "audit log", "#ffaa00", rad=-0.05),
]


def draw_diagram(output_path: str) -> None:
    fig, ax = plt.subplots(figsize=(32, 22), facecolor="#05070a")
    ax.set_facecolor("#05070a")
    ax.set_xlim(0, 1.05)
    ax.set_ylim(-0.02, 1.05)
    ax.axis("off")

    # --- Título ---
    ax.text(
        0.50, 1.03,
        "UTRON.ai — Arquitectura AGI con UC-322 Resolución de Conflictos Multi-Agente",
        ha="center", va="center", fontsize=22, color="#ffffff", fontweight="bold",
        bbox=dict(boxstyle="round,pad=0.4", facecolor="#0d1b2a",
                  edgecolor="#ff00ff", linewidth=2),
    )

    # --- Subtítulo ---
    ax.text(
        0.50, 0.995,
        "UC-315 decide  →  UC-322 resuelve  →  UC-324 contiene  →  UC-317 ejecuta",
        ha="center", va="center", fontsize=14, color="#ff00ff", fontweight="bold",
    )

    # --- Clusters de fondo ---
    clusters = [
        (0.23, 0.78, 0.30, 0.27, "WORKSPACE GLOBAL (GWT)", "#bd00ff"),
        (0.28, 0.63, 0.22, 0.18, "CEREBRO CENTRAL (UC-315)", "#ff9f1c"),
        (0.18, 0.51, 0.52, 0.14, "AGENTES UC-315 (generan propuestas)", "#2ecc40"),
        (0.18, 0.26, 0.48, 0.26, "UC-322 RESOLUCIÓN DE CONFLICTOS", "#ff00ff"),
        (0.18, 0.08, 0.50, 0.14, "UC-324 CONTENCIÓN Y GOBERNANZA", "#ff3333"),
        (0.70, 0.08, 0.26, 0.18, "UC-317 KERNEL DE EJECUCIÓN", "#00ff88"),
        (0.70, 0.68, 0.20, 0.34, "UC-313 PLASTICIDAD + EVOLUCIÓN", "#ff0055"),
        (0.18, -0.01, 0.50, 0.09, "OBSERVABILIDAD (GRAFANA STACK)", "#ffaa00"),
    ]
    for x, y, w, h, label, color in clusters:
        rect = mpatches.FancyBboxPatch(
            (x, y), w, h, boxstyle="round,pad=0.01", facecolor=color,
            alpha=0.06, edgecolor=color, linewidth=2, linestyle="--",
        )
        ax.add_patch(rect)
        ax.text(x + 0.01, y + h - 0.01, label, ha="left", va="top",
                fontsize=10, color=color, fontweight="bold", alpha=0.90)

    box_by_id = {b.id: b for b in boxes}

    # --- Dibujar cajas ---
    for b in boxes:
        rect = FancyBboxPatch(
            (b.x, b.y), b.w, b.h, boxstyle="round,pad=0.01,rounding_size=0.012",
            facecolor=b.color, edgecolor=b.edge, linewidth=2, alpha=0.95,
        )
        ax.add_patch(rect)
        ax.text(
            b.x + b.w / 2, b.y + b.h / 2, b.label,
            ha="center", va="center", fontsize=b.fontsize, color=b.text,
            fontweight="bold",
        )

    # --- Dibujar flechas ---
    for a in arrows:
        src = box_by_id[a.src]
        dst = box_by_id[a.dst]
        sx = src.x + src.w / 2
        sy = src.y + src.h / 2
        dx = dst.x + dst.w / 2
        dy = dst.y + dst.h / 2
        arrow = FancyArrowPatch(
            (sx, sy), (dx, dy),
            connectionstyle=f"arc3,rad={a.rad}",
            arrowstyle="-|>", mutation_scale=16, color=a.color,
            linewidth=1.6, alpha=0.85,
        )
        ax.add_patch(arrow)
        if a.label:
            mx, my = (sx + dx) / 2, (sy + dy) / 2
            if a.rad > 0:
                my += 0.015
            elif a.rad < 0:
                my -= 0.015
            ax.text(mx, my, a.label, fontsize=7, color=a.color,
                    ha="center", va="center",
                    bbox=dict(boxstyle="round,pad=0.12", facecolor="#05070a",
                              edgecolor="none", alpha=0.80))

    # --- Leyenda ---
    legend_items = [
        ("#00d4ff", "Entorno / Percepción"),
        ("#bd00ff", "Workspace Global / Memoria"),
        ("#ff9f1c", "Cerebro Central (UC-315)"),
        ("#00c3ff", "ReAct + ToT"),
        ("#2ecc40", "Agentes / Decisión / Ejecución"),
        ("#ff00ff", "UC-322 Resolución de Conflictos"),
        ("#ff3333", "UC-324 Contención (PRE/EXEC/POST)"),
        ("#00ff88", "UC-317 Kernel de Ejecución"),
        ("#ff0055", "UC-313 Plasticidad Sináptica"),
        ("#ffcc00", "Curiosidad / CNP Middleware"),
        ("#ff6b00", "Monitor Metacognitivo"),
        ("#ffaa00", "Observabilidad (Prometheus/Loki/Grafana)"),
        ("#00ffcc", "Gestión Memoria AGI"),
    ]
    lx = 1.0
    ly = 0.94
    ax.text(lx, ly + 0.03, "Leyenda", fontsize=12, color="white",
            fontweight="bold", ha="right")
    for color, text in legend_items:
        ly -= 0.035
        ax.add_patch(mpatches.Rectangle(
            (lx - 0.20, ly - 0.005), 0.02, 0.02,
            facecolor=color, edgecolor="white"))
        ax.text(lx - 0.17, ly + 0.005, text,
                fontsize=9, color="white", va="center")

    # --- Nota inferior ---
    ax.text(
        0.50, -0.015,
        "UC-315 decide · UC-322 resuelve conflictos · UC-324 contiene · UC-317 ejecuta · "
        "Un modelo genera evidencia, la evidencia no es una orden.",
        ha="center", va="bottom", fontsize=10, color="#888888", style="italic",
    )

    plt.tight_layout()
    fig.savefig(output_path, dpi=200, facecolor="#05070a", bbox_inches="tight")
    plt.close(fig)
    print(f"Diagrama guardado en: {output_path}")


if __name__ == "__main__":
    draw_diagram(
        "/Users/utron/Documents/code-books/TomoIII/UC-322/agi_brain_architecture.png"
    )
