"""领域实体单元测试。"""

from __future__ import annotations

from domain.routing.entity import (
    AgentPerformance,
    CandidateScore,
    FeedbackType,
    RoutingDecision,
    RoutingStatus,
    RoutingStrategy,
    UserFeedback,
)


class TestRoutingDecision:
    def test_default_strategy(self) -> None:
        d = RoutingDecision()
        assert d.routing_strategy == RoutingStrategy.SEMANTIC

    def test_default_status(self) -> None:
        d = RoutingDecision()
        assert d.status == RoutingStatus.SUCCESS

    def test_to_dict_excludes_none(self) -> None:
        d = RoutingDecision(task_description="测试任务", selected_agent="be-dev")
        data = d.to_dict()
        assert data["task_description"] == "测试任务"
        assert data["selected_agent"] == "be-dev"
        assert "id" not in data  # None 值被排除

    def test_to_dict_serializes_enums(self) -> None:
        d = RoutingDecision(task_description="测试", selected_agent="qa")
        data = d.to_dict()
        assert data["routing_strategy"] == "semantic"
        assert data["status"] == "success"

    def test_from_dict_roundtrip(self) -> None:
        original = RoutingDecision(
            task_description="测试任务",
            selected_agent="be-dev",
            routing_strategy=RoutingStrategy.ADAPTIVE,
            status=RoutingStatus.SUCCESS,
            confidence_score=0.85,
        )
        data = original.to_dict()
        restored = RoutingDecision.from_dict(data)
        assert restored.task_description == original.task_description
        assert restored.selected_agent == original.selected_agent
        assert restored.routing_strategy == original.routing_strategy
        assert restored.status == original.status
        assert restored.confidence_score == original.confidence_score


class TestCandidateScore:
    def test_default_values(self) -> None:
        c = CandidateScore()
        assert c.score == 0.0
        assert c.rank == 0


class TestUserFeedback:
    def test_default_type(self) -> None:
        f = UserFeedback()
        assert f.feedback_type == FeedbackType.CORRECT

    def test_default_rating(self) -> None:
        f = UserFeedback()
        assert f.rating is None


class TestAgentPerformance:
    def test_default_values(self) -> None:
        p = AgentPerformance()
        assert p.total_tasks == 0
        assert p.success_count == 0
        assert p.failure_count == 0

    def test_success_rate_default(self) -> None:
        """验证新智能体性能对象的默认成功率。"""
        p = AgentPerformance(agent_name="be-dev")
        assert p.agent_name == "be-dev"
