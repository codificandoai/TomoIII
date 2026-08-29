import threading
import time

from executor import AgentRegistry, DAGExecutor, build_default_registry
from models import AgentSpec, Goal, Task, TaskStatus
from planners import decompose


def test_executes_complete_dag():
    goal = decompose("Ship a service")
    summary = DAGExecutor(build_default_registry(), max_workers=4).execute(goal)
    assert summary.status == TaskStatus.COMPLETED
    assert summary.completed == len(goal.tasks)
    assert summary.failed == summary.blocked == 0
    assert len(summary.audit_hash()) == 64


def test_retries_then_succeeds():
    calls = 0
    registry = AgentRegistry()
    def flaky(task, context):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("transient")
        return "ok"
    registry.register(AgentSpec("worker", ["execution"]), flaky)
    task = Task("work", required_capabilities=["execution"], max_retries=1)
    goal = Goal("retry", tasks={task.id: task})
    summary = DAGExecutor(registry).execute(goal)
    assert summary.completed == 1
    assert task.attempts == 2


def test_failure_blocks_dependents():
    registry = AgentRegistry()
    registry.register(AgentSpec("worker", ["execution"]), lambda task, context: (_ for _ in ()).throw(RuntimeError("boom")))
    one = Task("fails", required_capabilities=["execution"], max_retries=0)
    two = Task("blocked", required_capabilities=["execution"], dependencies=[one.id])
    goal = Goal("failure", tasks={one.id: one, two.id: two})
    summary = DAGExecutor(registry).execute(goal)
    assert summary.failed == 1
    assert summary.blocked == 1


def test_parallel_wave_runs_concurrently():
    registry = AgentRegistry()
    barrier = threading.Barrier(2)
    def synchronized(task, context):
        barrier.wait(timeout=1)
        return task.title
    registry.register(AgentSpec("worker", ["execution"]), synchronized)
    one = Task("one", required_capabilities=["execution"])
    two = Task("two", required_capabilities=["execution"])
    goal = Goal("parallel", tasks={one.id: one, two.id: two})
    summary = DAGExecutor(registry, max_workers=2).execute(goal)
    assert summary.completed == 2
    assert summary.waves == 1


def test_checkpoint_receives_events():
    events = []
    goal = decompose("Deliver result")
    DAGExecutor(build_default_registry(), checkpoint=lambda g, e: events.append(e)).execute(goal)
    assert events[0].event_type == "goal_started"
    assert events[-1].event_type == "goal_completed"
