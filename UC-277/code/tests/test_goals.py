"""Tests del GoalMemory para UC-277."""
import time

from goal_memory import GoalMemory
from models import GoalStatus


def test_create_goal():
    gm = GoalMemory()
    goal_id = gm.create_goal("agent1", "Reach 10% ROI", "Monthly target")
    assert goal_id in gm.goals
    assert gm.goals[goal_id].status == GoalStatus.ACTIVE


def test_update_progress():
    gm = GoalMemory()
    goal_id = gm.create_goal("agent1", "Goal", "desc")
    gm.update_progress(goal_id, 0.5, "Halfway done")
    assert gm.goals[goal_id].progress == 0.5
    assert len(gm.goals[goal_id].milestones) == 1


def test_auto_complete_at_100():
    gm = GoalMemory()
    goal_id = gm.create_goal("agent1", "Goal", "desc")
    gm.update_progress(goal_id, 1.0, "Done!")
    assert gm.goals[goal_id].status == GoalStatus.COMPLETED


def test_update_status():
    gm = GoalMemory()
    goal_id = gm.create_goal("agent1", "Goal", "desc")
    gm.update_status(goal_id, GoalStatus.PAUSED)
    assert gm.goals[goal_id].status == GoalStatus.PAUSED


def test_link_episode():
    gm = GoalMemory()
    goal_id = gm.create_goal("agent1", "Goal", "desc")
    gm.link_episode(goal_id, "ep_123")
    assert "ep_123" in gm.goals[goal_id].related_episodes


def test_link_skill():
    gm = GoalMemory()
    goal_id = gm.create_goal("agent1", "Goal", "desc")
    gm.link_skill(goal_id, "skill_abc")
    assert "skill_abc" in gm.goals[goal_id].related_skills


def test_get_active_goals():
    gm = GoalMemory()
    g1 = gm.create_goal("agent1", "Active1", "")
    g2 = gm.create_goal("agent1", "Active2", "")
    g3 = gm.create_goal("agent1", "Done", "")
    gm.update_status(g3, GoalStatus.COMPLETED)
    active = gm.get_active_goals("agent1")
    assert len(active) == 2


def test_get_overdue_goals():
    gm = GoalMemory()
    past = time.time() - 3600
    gm.create_goal("agent1", "Overdue", "", deadline=past)
    gm.create_goal("agent1", "Future", "", deadline=time.time() + 3600)
    overdue = gm.get_overdue_goals("agent1")
    assert len(overdue) == 1
    assert overdue[0].title == "Overdue"


def test_get_stats():
    gm = GoalMemory()
    gm.create_goal("agent1", "G1", "")
    g2 = gm.create_goal("agent1", "G2", "")
    gm.update_progress(g2, 0.6)
    stats = gm.get_stats("agent1")
    assert stats["total_goals"] == 2
    assert stats["by_status"]["active"] == 2


def test_get_stats_empty():
    gm = GoalMemory()
    stats = gm.get_stats("agent1")
    assert stats["total_goals"] == 0


def test_progress_bounds():
    gm = GoalMemory()
    goal_id = gm.create_goal("agent1", "G", "")
    gm.update_progress(goal_id, 1.5)  # over 1.0
    assert gm.goals[goal_id].progress == 1.0
    gm.update_progress(goal_id, -0.5)  # under 0.0
    # Already completed, but let's check bounds
    assert gm.goals[goal_id].progress >= 0.0
