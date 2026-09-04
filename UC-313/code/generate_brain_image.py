"""Genera un diagrama de arquitectura AGI con todas las capas y sus interacciones.

Salida: /Users/utron/Documents/code-books/TomoIII/UC-313/agi_brain_architecture.png
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


# -----------------------------------------------------------------------------
# Cajas: disposición en columnas funcionales
# -----------------------------------------------------------------------------
boxes: List[Box] = [
    # Entorno / percepción
    b("ENV", "ENTORNO\nticks / noticias / riesgo", 0.02, 0.88, w=0.10, h=0.08, edge="#00d4ff"),
    b("PER", "PERCEPCIÓN\ncentral_brain.py\nMarketPerceptionPipeline", 0.16, 0.88, w=0.13, h=0.10, edge="#00d4ff"),

    # Workspace Global
    b("GWT", "WORKSPACE GLOBAL (GWT)\nglobal_workspace.py\nbuild + broadcast", 0.32, 0.93, w=0.16, h=0.09, edge="#bd00ff"),
    b("MON", "MONITOR\nMETACOGNITIVO\nmetacognitive_monitor.py", 0.50, 0.93, w=0.13, h=0.09, edge="#ff6b00"),
    b("SELF", "SELF-MODEL\nself_model_store.py", 0.26, 0.80, w=0.10, h=0.07, edge="#bd00ff"),
    b("EPI", "MEMORIA\nEPISÓDICA\nlong_term_memory.py", 0.37, 0.80, w=0.10, h=0.07, edge="#bd00ff"),
    b("HYP", "HIPÓTESIS\nCentralBrain / ToT", 0.48, 0.80, w=0.10, h=0.07, edge="#bd00ff"),

    # Cerebro central
    b("CBR", "central_brain.py\nPredicción | Beliefs\nDesires | Intent\nWorld Model | Simulación", 0.32, 0.62, w=0.16, h=0.14, edge="#ff9f1c", fontsize=9),

    # ReAct + ToT
    b("TOT", "REACT + TREE OF THOUGHTS\nreact_tot.py\nexpand / prune / backtrack\nconsensus ask/bid", 0.54, 0.70, w=0.16, h=0.12, edge="#00c3ff", fontsize=8),

    # Decisión / seguridad / ejecución
    b("BDI", "BDI + JUICE FILTER\nbdi.py / juice_agents.py", 0.54, 0.52, w=0.14, h=0.08, edge="#2ecc40"),
    b("SAF", "SAFETY SUPERVISOR\nsam.py", 0.72, 0.52, w=0.12, h=0.08, edge="#2ecc40"),
    b("EXE", "EJECUCIÓN\nexchange.py", 0.88, 0.52, w=0.10, h=0.08, edge="#2ecc40"),

    # Learning / World Model
    b("LWM", "APRENDIZAJE / WORLD MODEL\nworld_model.py\nupdate_from_tick / retrain", 0.72, 0.38, w=0.14, h=0.09, edge="#00ff9f"),

    # Memoria AGI
    b("MEMP", "BRAIN MEMORY PIPELINE\nbrain_memory_pipeline.py", 0.32, 0.32, w=0.16, h=0.08, edge="#00ffcc"),
    b("MROUT", "INTELLIGENT\nMEMORY ROUTER\nmemory_router.py", 0.32, 0.20, w=0.13, h=0.07, edge="#00ffcc"),
    b("STN", "SHORT-TERM\nNOTEPAD", 0.06, 0.20, w=0.10, h=0.07, edge="#00ffcc"),
    b("STR", "STRUCTURED\nMEMORY\nSQLite", 0.18, 0.20, w=0.10, h=0.07, edge="#00ffcc"),
    b("LTV", "LONG-TERM\nVECTOR MEMORY", 0.48, 0.20, w=0.10, h=0.07, edge="#00ffcc"),
    b("SMEM", "SELF-MODEL\nSTORE", 0.60, 0.20, w=0.10, h=0.07, edge="#00ffcc"),

    # Autoevaluación / metas
    b("CSE", "CONTINUOUS\nSELF-EVALUATOR", 0.70, 0.28, w=0.12, h=0.07, edge="#ffcc00"),
    b("GM", "GOAL MANAGER\nmetacognitive_goals.py", 0.86, 0.28, w=0.11, h=0.07, edge="#ffcc00"),

    # UC-313: plasticidad + evolución (columna derecha)
    b("CEL", "UC-313 PLASTICIDAD\ncognitive_evolution_layer.py\nfitness / meta-red / EWC", 0.82, 0.85, w=0.16, h=0.11, edge="#ff0055", fontsize=8),
    b("PC", "PREFRONTAL\nCONTROLLER\nbrain_plasticity_interface.py", 0.82, 0.70, w=0.14, h=0.08, edge="#ff0055"),
    b("CNP", "CNP MIDDLEWARE\ncnp_broadcast_middleware.py", 0.82, 0.96, w=0.14, h=0.07, edge="#ffcc00"),
    b("CSL", "CURIOSITY\nSKILL LOOP\ncuriosity_skill_loop.py", 0.66, 0.96, w=0.12, h=0.07, edge="#ffcc00"),

    # Bucle recursivo
    b("SAL", "SELF-AWARENESS LOOP\nself_awareness_loop.py\nnarrativa + persistencia", 0.84, 0.10, w=0.16, h=0.10, edge="#cc00ff", fontsize=8),
]

arrows: List[Arrow] = [
    # Entorno -> percepción
    Arrow("ENV", "PER", "datos brutos", "#00d4ff", rad=0.0),

    # Percepción -> GWT / Cerebro central
    Arrow("PER", "GWT", "snapshots / señales", "#00d4ff", rad=0.1),
    Arrow("PER", "CBR", "ticks / beliefs", "#00d4ff", rad=-0.05),

    # GWT broadcast
    Arrow("GWT", "SELF", "", "#bd00ff", rad=0.05),
    Arrow("GWT", "EPI", "", "#bd00ff", rad=0.0),
    Arrow("GWT", "HYP", "", "#bd00ff", rad=-0.05),
    Arrow("GWT", "MON", "workspace", "#ff6b00", rad=0.05),

    # GWT -> Cerebro central
    Arrow("GWT", "CBR", "hipótesis\nseleccionada", "#bd00ff", rad=-0.1),

    # Cerebro central <-> ToT
    Arrow("CBR", "TOT", "predicciones", "#00c3ff", rad=0.1),
    Arrow("TOT", "CBR", "ask/bid\nconfianza", "#00c3ff", rad=0.1),

    # Cerebro central -> Decisión
    Arrow("CBR", "BDI", "beliefs / desires\n/ intent", "#2ecc40", rad=-0.05),
    Arrow("TOT", "BDI", "síntesis\nconsensuada", "#00c3ff", rad=-0.1),

    # Decisión -> Safety -> Ejecución
    Arrow("BDI", "SAF", "estrategia\ncandidata", "#2ecc40", rad=0.0),
    Arrow("SAF", "EXE", "estrategia\naprobada", "#2ecc40", rad=0.0),

    # Ejecución -> Learning/WorldModel
    Arrow("EXE", "LWM", "resultado /\nobservación", "#00ff9f", rad=0.05),
    Arrow("LWM", "CBR", "feedback /\nretrain", "#00ff9f", rad=-0.2),

    # Ejecución -> Memoria AGI
    Arrow("EXE", "MEMP", "episodios /\nresultados", "#00ffcc", rad=0.05),
    Arrow("MEMP", "MROUT", "ruteo", "#00ffcc", rad=0.0),
    Arrow("MROUT", "STN", "", "#00ffcc", rad=0.0),
    Arrow("MROUT", "STR", "", "#00ffcc", rad=0.0),
    Arrow("MROUT", "LTV", "", "#00ffcc", rad=0.0),
    Arrow("MROUT", "SMEM", "", "#00ffcc", rad=0.0),

    # Memoria -> GWT (recall)
    Arrow("MROUT", "GWT", "recuerdos\nrelevantes", "#bd00ff", rad=-0.25),

    # Ejecución -> Autoevaluación -> Metas -> BDI
    Arrow("EXE", "CSE", "métricas", "#ffcc00", rad=0.05),
    Arrow("CSE", "GM", "reflexión", "#ffcc00", rad=0.0),
    Arrow("GM", "BDI", "nuevo\nobjetivo", "#ffcc00", rad=0.2),

    # UC-313 Plasticidad
    Arrow("MON", "CEL", "coherencia /\nveredicto", "#ff6b00", rad=-0.05),
    Arrow("CSE", "CEL", "fitness /\nepisodios", "#ff0055", rad=0.15),
    Arrow("EXE", "CEL", "observación de\nejecución", "#ff0055", rad=0.25),
    Arrow("CEL", "PC", "propuesta", "#ff0055", rad=0.0),
    Arrow("PC", "CBR", "reescribir\nparámetros", "#ff0055", rad=-0.05),
    Arrow("PC", "LWM", "retrain /\nreset", "#ff0055", rad=0.1),

    # CNP / Curiosidad
    Arrow("CEL", "CNP", "evaluar\nagentes", "#ffcc00", rad=0.05),
    Arrow("CNP", "EXE", "adjudicar\ntarea", "#ffcc00", rad=-0.05),
    Arrow("CSL", "CEL", "evaluar\nskill", "#ffcc00", rad=0.05),
    Arrow("MEMP", "CSL", "memorias /\nfallos", "#ffcc00", rad=0.2),

    # Bucle recursivo
    Arrow("CEL", "SAL", "decisiones /\npesos", "#cc00ff", rad=0.05),
    Arrow("MROUT", "SAL", "episodios", "#cc00ff", rad=-0.1),
    Arrow("SAL", "PER", "nuevo ciclo", "#cc00ff", rad=-0.3),
    Arrow("SAL", "SELF", "narrativa", "#cc00ff", rad=0.25),
]


def draw_diagram(output_path: str) -> None:
    fig, ax = plt.subplots(figsize=(32, 20), facecolor="#05070a")
    ax.set_facecolor("#05070a")
    ax.set_xlim(0, 1.05)
    ax.set_ylim(0, 1.05)
    ax.axis("off")

    # Título
    ax.text(
        0.52, 1.02,
        "UTRON.ai — Arquitectura AGI Autoconsciente con Plasticidad Sináptica Digital (UC-313)",
        ha="center", va="center", fontsize=22, color="#ffffff", fontweight="bold",
        bbox=dict(boxstyle="round,pad=0.4", facecolor="#0d1b2a", edgecolor="#00d4ff", linewidth=2),
    )

    # Clusters de fondo
    clusters = [
        (0.23, 0.76, 0.30, 0.32, "WORKSPACE GLOBAL (GWT)", "#bd00ff"),
        (0.30, 0.56, 0.20, 0.22, "CEREBRO CENTRAL", "#ff9f1c"),
        (0.52, 0.46, 0.48, 0.46, "RAZONAMIENTO + DECISIÓN + EJECUCIÓN", "#2ecc40"),
        (0.03, 0.08, 0.69, 0.30, "GESTIÓN DE MEMORIA AGI (UC-296)", "#00ffcc"),
        (0.78, 0.58, 0.24, 0.52, "UC-313 PLASTICIDAD + EVOLUCIÓN", "#ff0055"),
    ]
    for x, y, w, h, label, color in clusters:
        rect = mpatches.FancyBboxPatch(
            (x, y), w, h, boxstyle="round,pad=0.01", facecolor=color,
            alpha=0.05, edgecolor=color, linewidth=2, linestyle="--",
        )
        ax.add_patch(rect)
        # Etiqueta en esquina superior izquierda, dentro del rectángulo
        ax.text(x + 0.01, y + h - 0.01, label, ha="left", va="top",
                fontsize=10, color=color, fontweight="bold", alpha=0.85)

    box_by_id = {b.id: b for b in boxes}

    # Dibujar cajas
    for b in boxes:
        rect = FancyBboxPatch(
            (b.x, b.y), b.w, b.h, boxstyle="round,pad=0.01,rounding_size=0.015",
            facecolor=b.color, edgecolor=b.edge, linewidth=2, alpha=0.95,
        )
        ax.add_patch(rect)
        ax.text(
            b.x + b.w / 2, b.y + b.h / 2, b.label,
            ha="center", va="center", fontsize=b.fontsize, color=b.text,
            fontweight="bold",
        )

    # Dibujar flechas
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
                my += 0.018
            elif a.rad < 0:
                my -= 0.018
            ax.text(mx, my, a.label, fontsize=7, color=a.color,
                    ha="center", va="center",
                    bbox=dict(boxstyle="round,pad=0.15", facecolor="#05070a",
                              edgecolor="none", alpha=0.75))

    # Leyenda vertical (lado derecho)
    legend_items = [
        ("#00d4ff", "Entorno / Percepción"),
        ("#bd00ff", "Workspace Global / Memoria"),
        ("#ff9f1c", "Cerebro Central"),
        ("#00c3ff", "ReAct + ToT"),
        ("#2ecc40", "Decisión / Seguridad / Ejecución"),
        ("#00ff9f", "Aprendizaje / World Model"),
        ("#00ffcc", "Gestión Memoria AGI"),
        ("#ffcc00", "Autoevaluación / Metas / Curiosidad / CNP"),
        ("#ff0055", "Plasticidad Sináptica Digital"),
        ("#cc00ff", "Bucle de Autoconciencia"),
        ("#ff6b00", "Monitor Metacognitivo"),
    ]
    lx = 1.0
    ly = 0.92
    ax.text(lx, ly + 0.03, "Leyenda", fontsize=11, color="white",
            fontweight="bold", ha="right")
    for color, text in legend_items:
        ly -= 0.038
        ax.add_patch(mpatches.Rectangle((lx - 0.18, ly - 0.005), 0.02, 0.02, facecolor=color, edgecolor="white"))
        ax.text(lx - 0.15, ly + 0.005, text, fontsize=9, color="white", va="center")

    # Nota inferior
    ax.text(
        0.52, 0.01,
        "Autoconciencia funcional computacional: self-model persistente, memoria episódica, monitor metacognitivo y narrativas internas. No se atribuye conciencia subjetiva.",
        ha="center", va="bottom", fontsize=10, color="#888888", style="italic",
    )

    plt.tight_layout()
    fig.savefig(output_path, dpi=200, facecolor="#05070a", bbox_inches="tight")
    plt.close(fig)
    print(f"Diagrama guardado en: {output_path}")


if __name__ == "__main__":
    draw_diagram("/Users/utron/Documents/code-books/TomoIII/UC-313/agi_brain_architecture.png")
