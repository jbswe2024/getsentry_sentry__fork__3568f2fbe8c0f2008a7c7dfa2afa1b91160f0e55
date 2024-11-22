from __future__ import annotations

from copy import deepcopy
from enum import Enum

from django.db.migrations.state import ProjectState
from django.db.models import Model
from django_zero_downtime_migrations.backends.postgres.schema import UnsafeOperationException


class DeletionAction(Enum):
    MOVE_TO_PENDING = 0
    DELETE = 1


class SentryProjectState(ProjectState):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pending_deletion_models: dict[tuple[str, str], type[Model]] = {}

    def get_pending_deletion_model(self, app_label: str, model_name: str) -> type[Model]:
        model_key = (app_label.lower(), model_name.lower())
        if model_key not in self.pending_deletion_models:
            raise UnsafeOperationException(
                "Model must be in the pending deletion state before full deletion. "
                "More info: https://develop.sentry.dev/api-server/application-domains/database-migrations/#deleting-tables"
            )
        return self.pending_deletion_models[model_key]

    def remove_model(
        self, app_label: str, model_name: str, deletion_action: DeletionAction | None = None
    ) -> None:
        model_key = (app_label.lower(), model_name.lower())
        if deletion_action == DeletionAction.DELETE:
            if model_key not in self.pending_deletion_models:
                raise UnsafeOperationException(
                    "Model must be in the pending deletion state before full deletion. "
                    "More info: https://develop.sentry.dev/api-server/application-domains/database-migrations/#deleting-tables"
                )
            del self.pending_deletion_models[model_key]
            return
        if deletion_action == DeletionAction.MOVE_TO_PENDING:
            if model_key in self.pending_deletion_models:
                raise UnsafeOperationException(
                    f"{app_label}.{model_name} is already pending deletion. Use DeletionAction.DELETE to delete"
                    "More info: https://develop.sentry.dev/api-server/application-domains/database-migrations/#deleting-tables"
                )
            self.pending_deletion_models[model_key] = self.apps.get_model(app_label, model_name)
        super().remove_model(app_label, model_name)

    def clone(self) -> SentryProjectState:
        new_state = super().clone()
        new_state.pending_deletion_models = deepcopy(self.pending_deletion_models)  # type: ignore[attr-defined]
        return new_state  # type: ignore[return-value]