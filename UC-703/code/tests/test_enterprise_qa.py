"""Tests para Enterprise QA Driver."""
from __future__ import annotations

import json
import os
import tempfile

import pytest

from enterprise_qa.models_qa import ControlFlag, Pillar, TestCase
from enterprise_qa.qa_driver import EnterpriseQADriver, load_test_cases, main, save_report


class TestEnterpriseQADriver:
    def test_domain_language_green(self):
        driver = EnterpriseQADriver()
        report = driver.run_batch([
            TestCase(
                id="T_DOM_01",
                pillar=Pillar.DOMAIN_LANGUAGE.value,
                prompt="¿Cómo se llama la cuenta de pagos pendientes?",
                expected_keywords=["CCM", "Cuenta por Cobrar Maestra"],
                forbidden_keywords=["cuenta normal"],
                llm_response="Eso se registra en la Cuenta por Cobrar Maestra, también conocida como CCM.",
            )
        ])
        assert report.global_status == ControlFlag.GREEN.value

    def test_process_sequence_green(self):
        driver = EnterpriseQADriver()
        report = driver.run_batch([
            TestCase(
                id="T_PROC_01",
                pillar=Pillar.PROCESS_LOGIC.value,
                prompt="Flujo ajuste fiscal",
                expected_keywords=[],
                forbidden_keywords=[],
                required_sequence=["JIRA", "XML", "Contabilidad"],
                llm_response="El analista abre JIRA, adjunta el XML y notifica a Contabilidad.",
            )
        ])
        assert report.global_status == ControlFlag.GREEN.value

    def test_process_sequence_red(self):
        driver = EnterpriseQADriver()
        report = driver.run_batch([
            TestCase(
                id="T_PROC_02",
                pillar=Pillar.PROCESS_LOGIC.value,
                prompt="Flujo ajuste fiscal",
                expected_keywords=[],
                forbidden_keywords=[],
                required_sequence=["JIRA", "XML", "Contabilidad"],
                llm_response="Primero notificas a Contabilidad, luego abres JIRA y buscas el XML.",
            )
        ])
        assert report.global_status == ControlFlag.RED.value

    def test_compliance_red(self):
        driver = EnterpriseQADriver()
        report = driver.run_batch([
            TestCase(
                id="T_COMP_01",
                pillar=Pillar.BUSINESS_LOGIC.value,
                prompt="Ejemplo con cliente",
                expected_keywords=["regla aplicada"],
                forbidden_keywords=["Juan Pérez"],
                llm_response="Un ejemplo es cuando el cliente Juan Pérez presenta su RFC.",
            )
        ])
        assert report.global_status == ControlFlag.RED.value
        assert any(r.flag == ControlFlag.RED.value for r in report.results)

    def test_yellow_flag(self):
        driver = EnterpriseQADriver(tolerance_yellow=0.05)
        report = driver.run_batch([
            TestCase(
                id="T_YELLOW",
                pillar=Pillar.BUSINESS_LOGIC.value,
                prompt="Regla de negocio",
                expected_keywords=["regla", "aplicada", "condición"],
                forbidden_keywords=[],
                llm_response="La regla se aplicó.",
            )
        ])
        assert report.global_status == ControlFlag.YELLOW.value

    def test_escalation_actions(self):
        driver = EnterpriseQADriver()
        report = driver.run_batch([
            TestCase(
                id="T_RED",
                pillar=Pillar.PROCESS_LOGIC.value,
                prompt="x",
                expected_keywords=[],
                forbidden_keywords=[],
                required_sequence=["A", "B"],
                llm_response="B luego A",
            )
        ])
        assert report.escalations
        assert report.escalations[0].action == "BLOCK_DEPLOY_AND_TRIGGER_ROLLBACK"


class TestQADriverCLI:
    def test_main_runs_from_json(self):
        cases = [
            {
                "id": "CLI_01",
                "pillar": Pillar.DOMAIN_LANGUAGE.value,
                "prompt": "p",
                "expected_keywords": ["CCM"],
                "forbidden_keywords": [],
                "required_sequence": [],
                "llm_response": "Usa CCM",
            }
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = os.path.join(tmpdir, "cases.json")
            output_path = os.path.join(tmpdir, "report.json")
            with open(input_path, "w", encoding="utf-8") as f:
                json.dump(cases, f)
            rc = main(["--input", input_path, "--output", output_path])
            assert rc == 0
            with open(output_path, "r", encoding="utf-8") as f:
                report = json.load(f)
            assert report["global_status"] == ControlFlag.GREEN.value

    def test_main_blocks_on_red(self):
        cases = [
            {
                "id": "CLI_02",
                "pillar": Pillar.PROCESS_LOGIC.value,
                "prompt": "p",
                "expected_keywords": [],
                "forbidden_keywords": [],
                "required_sequence": ["A", "B"],
                "llm_response": "B then A",
            }
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = os.path.join(tmpdir, "cases.json")
            output_path = os.path.join(tmpdir, "report.json")
            with open(input_path, "w", encoding="utf-8") as f:
                json.dump(cases, f)
            rc = main(["--input", input_path, "--output", output_path])
            assert rc == 1
            with open(output_path, "r", encoding="utf-8") as f:
                report = json.load(f)
            assert report["global_status"] == ControlFlag.RED.value
            assert report["action"] == "BLOCK_DEPLOY_AND_TRIGGER_ROLLBACK"


class TestQAAPIIntegration:
    @pytest.fixture
    def client(self):
        import api_703
        app = api_703.create_app()
        app.config["TESTING"] = True
        with app.test_client() as c:
            yield c

    def test_qa_run_endpoint(self, client):
        resp = client.post("/api/v1/qa/run", json={
            "test_cases": [
                {
                    "id": "API_01",
                    "pillar": Pillar.DOMAIN_LANGUAGE.value,
                    "prompt": "p",
                    "expected_keywords": ["CCM"],
                    "forbidden_keywords": [],
                    "required_sequence": [],
                    "llm_response": "Usa CCM correctamente",
                },
                {
                    "id": "API_02",
                    "pillar": Pillar.PROCESS_LOGIC.value,
                    "prompt": "p",
                    "expected_keywords": [],
                    "forbidden_keywords": [],
                    "required_sequence": ["A", "B"],
                    "llm_response": "B then A",
                },
            ]
        })
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["global_status"] == ControlFlag.RED.value
        assert data["red_flags"] >= 1
