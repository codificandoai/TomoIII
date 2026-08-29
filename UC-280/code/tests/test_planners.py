import pytest

from models import Goal, PlannerType, Task
from planners import decompose, topological_waves, validate_dag


@pytest.mark.parametrize("planner", list(PlannerType))
def test_planners_create_valid_dags(planner):
    goal = decompose("Build and deploy a reliable API", {"team": "platform"}, planner)
    assert goal.planner == planner
    assert len(goal.tasks) >= 5
    waves = topological_waves(goal)
    assert sum(len(wave) for wave in waves) == len(goal.tasks)


def test_tdag_has_parallel_wave():
    goal = decompose("Analyze a market", planner=PlannerType.TDAG)
    assert max(len(wave) for wave in topological_waves(goal)) == 3


def test_reactree_has_alternatives():
    goal = decompose("Choose an implementation", planner=PlannerType.REACTREE)
    branches = [t.metadata.get("branch") for t in goal.tasks.values()]
    assert "primary" in branches and "alternative" in branches


def test_empty_goal_rejected():
    with pytest.raises(ValueError):
        decompose("  ")


def test_missing_dependency_rejected():
    task = Task("broken", dependencies=["missing"])
    goal = Goal("broken", tasks={task.id: task})
    with pytest.raises(ValueError, match="missing"):
        validate_dag(goal)


def test_cycle_rejected():
    one, two = Task("one"), Task("two")
    one.dependencies, two.dependencies = [two.id], [one.id]
    goal = Goal("cycle", tasks={one.id: one, two.id: two})
    with pytest.raises(ValueError, match="cycle"):
        topological_waves(goal)
