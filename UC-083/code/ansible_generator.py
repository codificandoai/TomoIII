"""
UC-083 — Generador de playbooks Ansible para remediación de incidentes.

Genera playbooks YAML de operaciones seguras: detener reintentos,
escalar recursos, limpiar checkpoints, reiniciar workers.
"""

from typing import Dict, List, Any, Optional
from textwrap import dedent

from incident_models import RootCauseCategory


class AnsibleGenerator:
    """
    Crea playbooks Ansible idempotentes para mitigar incidentes de
inferencia batch. No ejecuta comandos reales; retorna YAML listo.
    """

    def __init__(self, hosts: str = "batch_workers"):
        self.hosts = hosts

    def generate(
        self,
        category: RootCauseCategory,
        pipeline_id: str,
        scale_memory_gb: Optional[int] = None,
        scale_workers: Optional[int] = None,
    ) -> str:
        if category == RootCauseCategory.OOM:
            return self._oom_playbook(pipeline_id, scale_memory_gb, scale_workers)
        if category == RootCauseCategory.DATA_VOLUME:
            return self._data_volume_playbook(pipeline_id, scale_workers)
        if category == RootCauseCategory.INFRASTRUCTURE:
            return self._infrastructure_playbook(pipeline_id)
        if category == RootCauseCategory.TIMEOUT:
            return self._timeout_playbook(pipeline_id, scale_workers)
        return self._generic_playbook(pipeline_id)

    def _oom_playbook(self, pipeline_id: str, scale_memory_gb: Optional[int], scale_workers: Optional[int]) -> str:
        memory_var = f"\n    worker_memory_gb: {scale_memory_gb}" if scale_memory_gb else ""
        workers_var = f"\n    worker_count: {scale_workers}" if scale_workers else ""
        template = dedent("""\
            ---
            - name: UC-083 Remediate OOM for __PIPELINE_ID__
              hosts: __HOSTS__
              become: yes
              gather_facts: no
              vars:
                pipeline_id: "__PIPELINE_ID__"__MEMORY_VAR____WORKERS_VAR__
              tasks:
                - name: Stop automatic retries
                  ansible.builtin.systemd:
                    name: "batch-inference@{{ pipeline_id }}"
                    state: stopped
                  ignore_errors: yes

                - name: Create idempotent checkpoint directory
                  ansible.builtin.file:
                    path: "/var/lib/trackprice/checkpoints/{{ pipeline_id }}"
                    state: directory
                    mode: '0755'

                - name: Drain pending jobs
                  ansible.builtin.command:
                    cmd: "prefect deployment pause --name {{ pipeline_id }} || true"
                  ignore_errors: yes

                - name: Scale worker memory
                  ansible.builtin.lineinfile:
                    path: "/etc/trackprice/worker.conf"
                    regexp: '^WORKER_MEMORY_GB='
                    line: "WORKER_MEMORY_GB={{ worker_memory_gb | default(8) }}"
                  when: scale_memory_gb is defined

                - name: Scale worker replicas
                  ansible.builtin.lineinfile:
                    path: "/etc/trackprice/worker.conf"
                    regexp: '^WORKER_COUNT='
                    line: "WORKER_COUNT={{ worker_count | default(4) }}"
                  when: scale_workers is defined

                - name: Restart workers with new limits
                  ansible.builtin.systemd:
                    name: "batch-inference-worker"
                    state: restarted
                  ignore_errors: yes

                - name: Notify reprocess playbook ready
                  ansible.builtin.debug:
                    msg: "Workers scaled; run reprocess_partitions.yml to resume."
            """)
        return (
            template
            .replace("__PIPELINE_ID__", pipeline_id)
            .replace("__HOSTS__", self.hosts)
            .replace("__MEMORY_VAR__", memory_var)
            .replace("__WORKERS_VAR__", workers_var)
        )

    def _data_volume_playbook(self, pipeline_id: str, scale_workers: Optional[int]) -> str:
        template = dedent("""\
            ---
            - name: UC-083 Remediate Data Volume Spike for __PIPELINE_ID__
              hosts: __HOSTS__
              become: yes
              gather_facts: no
              vars:
                pipeline_id: "__PIPELINE_ID__"
                worker_count: __WORKER_COUNT__
              tasks:
                - name: Pause pipeline
                  ansible.builtin.command:
                    cmd: "prefect deployment pause --name {{ pipeline_id }} || true"
                  ignore_errors: yes

                - name: Enable distributed chunking mode
                  ansible.builtin.lineinfile:
                    path: "/etc/trackprice/pipeline.conf"
                    regexp: '^CHUNKING_ENABLED='
                    line: "CHUNKING_ENABLED=true"

                - name: Scale workers horizontally
                  ansible.builtin.lineinfile:
                    path: "/etc/trackprice/worker.conf"
                    regexp: '^WORKER_COUNT='
                    line: "WORKER_COUNT={{ worker_count }}"

                - name: Restart orchestrator
                  ansible.builtin.systemd:
                    name: "batch-inference-orchestrator"
                    state: restarted
                  ignore_errors: yes
            """)
        return (
            template
            .replace("__PIPELINE_ID__", pipeline_id)
            .replace("__HOSTS__", self.hosts)
            .replace("__WORKER_COUNT__", str(scale_workers or 8))
        )

    def _infrastructure_playbook(self, pipeline_id: str) -> str:
        template = dedent("""\
            ---
            - name: UC-083 Recover Infrastructure Failure for __PIPELINE_ID__
              hosts: __HOSTS__
              become: yes
              gather_facts: no
              vars:
                pipeline_id: "__PIPELINE_ID__"
              tasks:
                - name: Mark pipeline as recovering
                  ansible.builtin.file:
                    path: "/var/lib/trackprice/{{ pipeline_id }}.recovering"
                    state: touch
                    mode: '0644'

                - name: Health check workers
                  ansible.builtin.command:
                    cmd: "systemctl is-active batch-inference-worker || true"
                  register: worker_status
                  ignore_errors: yes

                - name: Restart failed workers
                  ansible.builtin.systemd:
                    name: "batch-inference-worker"
                    state: restarted
                  when: worker_status.rc != 0
                  ignore_errors: yes

                - name: Resume orchestrator
                  ansible.builtin.systemd:
                    name: "batch-inference-orchestrator"
                    state: started
                  ignore_errors: yes
            """)
        return template.replace("__PIPELINE_ID__", pipeline_id).replace("__HOSTS__", self.hosts)

    def _timeout_playbook(self, pipeline_id: str, scale_workers: Optional[int]) -> str:
        template = dedent("""\
            ---
            - name: UC-083 Remediate Timeout for __PIPELINE_ID__
              hosts: __HOSTS__
              become: yes
              gather_facts: no
              vars:
                pipeline_id: "__PIPELINE_ID__"
                worker_count: __WORKER_COUNT__
              tasks:
                - name: Increase task timeout
                  ansible.builtin.lineinfile:
                    path: "/etc/trackprice/pipeline.conf"
                    regexp: '^TASK_TIMEOUT_MINUTES='
                    line: "TASK_TIMEOUT_MINUTES=180"

                - name: Scale workers
                  ansible.builtin.lineinfile:
                    path: "/etc/trackprice/worker.conf"
                    regexp: '^WORKER_COUNT='
                    line: "WORKER_COUNT={{ worker_count }}"

                - name: Restart orchestrator
                  ansible.builtin.systemd:
                    name: "batch-inference-orchestrator"
                    state: restarted
                  ignore_errors: yes
            """)
        return (
            template
            .replace("__PIPELINE_ID__", pipeline_id)
            .replace("__HOSTS__", self.hosts)
            .replace("__WORKER_COUNT__", str(scale_workers or 6))
        )

    def _generic_playbook(self, pipeline_id: str) -> str:
        template = dedent("""\
            ---
            - name: UC-083 Generic Remediation for __PIPELINE_ID__
              hosts: __HOSTS__
              become: yes
              gather_facts: no
              vars:
                pipeline_id: "__PIPELINE_ID__"
              tasks:
                - name: Stop pipeline
                  ansible.builtin.command:
                    cmd: "prefect deployment pause --name {{ pipeline_id }} || true"
                  ignore_errors: yes

                - name: Collect incident artifacts
                  ansible.builtin.command:
                    cmd: "tar czf /tmp/{{ pipeline_id }}-incident.tar.gz /var/log/trackprice/{{ pipeline_id }}"
                  ignore_errors: yes

                - name: Notify on-call
                  ansible.builtin.debug:
                    msg: "Incident artifacts collected; escalate to on-call SRE."
            """)
        return template.replace("__PIPELINE_ID__", pipeline_id).replace("__HOSTS__", self.hosts)

    def generate_reprocess_playbook(self, pipeline_id: str, partitions: List[str]) -> str:
        parts = "\n".join(f"      - {p}" for p in partitions)
        template = dedent(f"""\
            ---
            - name: UC-083 Reprocess Partitions for __PIPELINE_ID__
              hosts: __HOSTS__
              become: yes
              gather_facts: no
              vars:
                pipeline_id: "__PIPELINE_ID__"
                partitions:
{parts}
              tasks:
                - name: Resume from idempotent checkpoints
                  ansible.builtin.command:
                    cmd: "trackprice-inference reprocess --pipeline {{ pipeline_id }} --partition {{ item }}"
                  loop: "{{ partitions }}"
                  register: reprocess_result
                  retries: 2
                  delay: 60
                  until: reprocess_result.rc == 0
                  ignore_errors: yes

                - name: Validate output coverage
                  ansible.builtin.command:
                    cmd: "trackprice-validate-coverage --pipeline {{ pipeline_id }}"
                  ignore_errors: yes
            """)
        return template.replace("__PIPELINE_ID__", pipeline_id).replace("__HOSTS__", self.hosts)

    def list_templates(self) -> List[Dict[str, str]]:
        return [
            {"category": cat.value, "template": f"{cat.value}_remediation.yml"}
            for cat in RootCauseCategory
        ]
