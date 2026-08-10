import asyncio

from app.api.agent_zero_reviews import DeclineReviewRequest, decline_review
from app.api.flow_control import ArchiveRequest, archive_model_job
from app.models.flow_job_record import JobRecord, JobStatus


class FakeResult:
    def __init__(self, job: JobRecord) -> None:
        self.job = job

    def scalar_one_or_none(self) -> JobRecord:
        return self.job


class FakeDb:
    def __init__(self, job: JobRecord) -> None:
        self.job = job
        self.commits = 0

    async def execute(self, _statement) -> FakeResult:
        return FakeResult(self.job)

    def add(self, _job: JobRecord) -> None:
        return None

    async def commit(self) -> None:
        self.commits += 1

    async def refresh(self, _job: JobRecord) -> None:
        return None


class FakeQueue:
    def __init__(self) -> None:
        self.removed: list[tuple[str, str]] = []

    async def remove_job(self, owner: str, job_id: str) -> int:
        self.removed.append((owner, job_id))
        return 1


def job(status: str) -> JobRecord:
    return JobRecord(
        job_id="job-1",
        task_id="task-1",
        owner="gamma",
        status=status,
        task_type="implementation",
        risk_tier="downtime_security_money",
        title="Guarded change",
        goal="Make the guarded change without widening its scope.",
        source="dashboard",
        output_required="A verified implementation artifact.",
        inputs={},
        review_required=True,
    )


def test_decline_review_is_terminal_and_removes_queued_copies() -> None:
    record = job(JobStatus.REVIEW_REQUIRED.value)
    db = FakeDb(record)
    queue = FakeQueue()

    response = asyncio.run(
        decline_review(
            "job-1",
            DeclineReviewRequest(reason="The rollback proof is not credible."),
            db,
            queue,
        )
    )

    assert response["status"] == "declined"
    assert record.status == JobStatus.DECLINED.value
    assert "rollback proof" in record.error_message
    assert queue.removed == [("gamma", "job-1")]
    assert db.commits == 1


def test_archive_removes_task_without_deleting_its_record() -> None:
    record = job(JobStatus.COMPLETED.value)
    record.result_pointer = "/app/runtime/reviews/job-1/output.md"
    db = FakeDb(record)
    queue = FakeQueue()

    response = asyncio.run(
        archive_model_job(
            "job-1",
            ArchiveRequest(reason="The proof is obsolete."),
            db,
            queue,
        )
    )

    assert response["status"] == "archived"
    assert record.status == JobStatus.ARCHIVED.value
    assert record.result_pointer.endswith("output.md")
    assert queue.removed == [("gamma", "job-1")]
    assert db.commits == 1
