from __future__ import annotations

from collections.abc import Callable
from functools import update_wrapper
from typing import TYPE_CHECKING, Generic, ParamSpec, TypeVar
from uuid import uuid4

import orjson
from django.conf import settings
from django.utils import timezone
from google.protobuf.timestamp_pb2 import Timestamp
from sentry_protos.sentry.v1.taskworker_pb2 import RetryState, TaskActivation

from sentry.taskworker.retry import Retry

if TYPE_CHECKING:
    from sentry.taskworker.registry import TaskNamespace


P = ParamSpec("P")
R = TypeVar("R")


class Task(Generic[P, R]):
    def __init__(
        self,
        name: str,
        func: Callable[P, R],
        namespace: TaskNamespace,
        retry: Retry | None,
        idempotent: bool = False,
    ):
        # TODO(taskworker) Implement task execution deadlines
        self.name = name
        self._func = func
        self._namespace = namespace
        self._retry = retry
        self._idempotent = idempotent
        update_wrapper(self, func)

    @property
    def retry(self) -> Retry | None:
        return self._retry

    @property
    def idempotent(self) -> bool:
        return self._idempotent

    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> R:
        return self._func(*args, **kwargs)

    def delay(self, *args: P.args, **kwargs: P.kwargs) -> None:
        self.apply_async(*args, **kwargs)

    def apply_async(self, *args: P.args, **kwargs: P.kwargs) -> None:
        if settings.TASK_WORKER_ALWAYS_EAGER:
            self._func(*args, **kwargs)
        else:
            self._namespace.send_task(self.create_activation(*args, **kwargs))

    def create_activation(self, *args: P.args, **kwargs: P.kwargs) -> TaskActivation:
        received_at = Timestamp()
        received_at.FromDatetime(timezone.now())

        return TaskActivation(
            id=uuid4().hex,
            namespace=self._namespace.name,
            taskname=self.name,
            parameters=orjson.dumps({"args": args, "kwargs": kwargs}).decode("utf8"),
            retry_state=self._create_retry_state(),
            received_at=received_at,
        )

    def _create_retry_state(self) -> RetryState:
        retry = self.retry or self._namespace.default_retry or None
        if not retry:
            # If the task and namespace have no retry policy,
            # make a single attempt and then discard the task.
            return RetryState(
                attempts=0,
                kind="sentry.taskworker.retry.Retry",
                discard_after_attempt=1,
            )
        return retry.initial_state()

    def should_retry(self, state: RetryState, exc: Exception) -> bool:
        # No retry policy means no retries.
        retry = self.retry
        if not retry:
            return False
        return retry.should_retry(state, exc)