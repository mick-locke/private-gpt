import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from private_gpt.server.ingest.ingest_router import IngestResponse


class IngestHelper:
    def __init__(self, test_client: TestClient):
        self.test_client = test_client

    def ingest_file(self, path: Path) -> IngestResponse:
        files = {"file": (path.name, path.open("rb"))}

        response = self.test_client.post("/v1/ingest/file", files=files)
        assert response.status_code == 200
        ingest_result = IngestResponse.model_validate(response.json())
        return ingest_result

    def ingest_file_with_metadata(
        self, path: Path, metadata: dict[str, Any]
    ) -> IngestResponse:
        files = {
            "file": (path.name, path.open("rb")),
            "metadata": (None, json.dumps(metadata)),
        }

        response = self.test_client.post("/v1/ingest/file", files=files)

        assert response.status_code == 200
        ingest_result = IngestResponse.model_validate(response.json())
        return ingest_result


@pytest.fixture
def ingest_helper(test_client: TestClient) -> IngestHelper:
    return IngestHelper(test_client)
