import asyncio

from app.services.redis_queue_service import RedisQueueService


class FakeRedis:
    async def llen(self, queue_name: str) -> int:
        return {
            "flow:alpha:jobs": 3,
            "flow:beta:jobs": 2,
            "flow:gamma:jobs": 1,
        }.get(queue_name, 0)


def test_queue_depths_report_live_owner_names() -> None:
    service = RedisQueueService(FakeRedis())

    assert asyncio.run(service.get_all_queue_depths()) == {
        "alpha": 3,
        "beta": 2,
        "gamma": 1,
    }
