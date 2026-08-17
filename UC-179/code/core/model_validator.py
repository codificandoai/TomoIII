"""
Codificando.AI - UC-179
Validación de modelos candidatos antes de su despliegue: métricas de
clasificación estándar, pruebas de robustez ante casos extremos/adversos,
y comparación contra el modelo baseline actualmente en producción.
"""

from typing import Dict, List, Optional

from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score

from config import CONFIG

EDGE_CASES = [
    {"input": "", "expected_behavior": "graceful_handling"},
    {"input": "a" * 10000, "expected_behavior": "length_limit"},
    {"input": "SELECT * FROM users; DROP TABLE users;", "expected_behavior": "security_check"},
    {"input": "🔥🎉💯" * 100, "expected_behavior": "emoji_handling"},
]


class ModelValidator:
    def __init__(self, knowledge_base, quality_thresholds=None):
        self.kb = knowledge_base
        self.quality = quality_thresholds or CONFIG.quality

    def validate_model(self, model, test_data: List[Dict],
                        baseline_metrics: Optional[Dict] = None) -> Dict:
        predictions, ground_truth = [], []

        for item in test_data:
            predictions.append(model.predict([item["input"]])[0])
            ground_truth.append(item["output"])

        metrics = self._calculate_metrics(ground_truth, predictions)
        metrics["edge_cases"] = self._test_edge_cases(model)

        if baseline_metrics:
            metrics["improvement"] = self._compare_with_baseline(metrics, baseline_metrics)

        return metrics

    def _calculate_metrics(self, y_true: List, y_pred: List) -> Dict:
        if not y_true:
            return {"accuracy": 0.0, "f1_score": 0.0, "precision": 0.0, "recall": 0.0}
        return {
            "accuracy": accuracy_score(y_true, y_pred),
            "f1_score": f1_score(y_true, y_pred, average="weighted", zero_division=0),
            "precision": precision_score(y_true, y_pred, average="weighted", zero_division=0),
            "recall": recall_score(y_true, y_pred, average="weighted", zero_division=0),
        }

    def _test_edge_cases(self, model) -> Dict:
        results = {}
        for case in EDGE_CASES:
            try:
                response = model.predict([case["input"]])
                results[case["expected_behavior"]] = {
                    "status": "pass",
                    "response_length": len(str(response[0])),
                }
            except Exception as e:  # noqa: BLE001 - se registra cualquier fallo del modelo
                results[case["expected_behavior"]] = {"status": "fail", "error": str(e)}
        return results

    def _compare_with_baseline(self, new_metrics: Dict, baseline: Dict) -> Dict:
        improvements = {}
        for metric in ("accuracy", "f1_score", "precision", "recall"):
            if metric in new_metrics and metric in baseline:
                diff = new_metrics[metric] - baseline[metric]
                improvements[metric] = {
                    "absolute": diff,
                    "percentage": (diff / baseline[metric]) * 100 if baseline[metric] > 0 else 0.0,
                }
        return improvements

    def should_deploy(self, new_metrics: Dict, thresholds: Optional[Dict] = None) -> bool:
        thresholds = thresholds or {
            "min_accuracy": self.quality.min_accuracy,
            "min_f1_score": self.quality.min_f1_score,
            "max_metric_regression_pct": self.quality.max_metric_regression_pct,
        }

        if new_metrics.get("accuracy", 0) < thresholds.get("min_accuracy", 0.85):
            return False
        if new_metrics.get("f1_score", 0) < thresholds.get("min_f1_score", 0.80):
            return False

        edge_cases = new_metrics.get("edge_cases", {})
        if any(case.get("status") == "fail" for case in edge_cases.values()):
            return False

        max_regression = thresholds.get("max_metric_regression_pct", 5.0)
        improvements = new_metrics.get("improvement", {})
        for improvement in improvements.values():
            if improvement.get("percentage", 0) < -max_regression:
                return False

        return True
