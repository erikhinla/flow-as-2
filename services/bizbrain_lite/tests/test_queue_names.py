import asyncio

from app.services.redis_queue_service import RedisQueueService


class FakeRedis:
    def __init__(self) -> None:
        self.removals: list[tuple[str, int, str]] = []

    async def llen(self, queue_name: str) -> int:
        return {
            "flow:alpha:jobs": 3,
            "flow:beta:jobs": 2,
            "flow:gamma:jobs": 1,
        }.get(queue_name, 0)

    async def lrem(self, queue_name: str, count: int, job_id: str) -> int:
        self.removals.append((queue_name, count, job_id))
        return 1


def test_queue_depths_report_live_owner_names() -> None:
    service = RedisQueueService(FakeRedis())

    assert asyncio.run(service.get_all_queue_depths()) == {
        "alpha": 3,
        "beta": 2,
        "gamma": 1,
    }


def test_remove_job_targets_only_the_owning_queue() -> None:
    redis = FakeRedis()
    service = RedisQueueService(redis)

    assert asyncio.run(service.remove_job("gamma", "job-123")) == 1
    assert redis.removals == [("flow:gamma:jobs", 0, "job-123")]
