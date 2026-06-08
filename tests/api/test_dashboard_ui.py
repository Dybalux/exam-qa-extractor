"""Dashboard HTML contract test.

Pins the 12 required DOM IDs that the import-export JS handler depends on.
If a Jinja refactor renames or removes any of these IDs, the JS handler
fails silently at runtime — this test catches it pre-merge.
"""

import pytest
from httpx import AsyncClient


REQUIRED_DOM_IDS = [
    "export-btn",
    "import-file-input",
    "import-pick-btn",
    "import-filename-label",
    "preview-btn",
    "import-preview-modal",
    "import-preview-title",
    "prev-create",
    "prev-update",
    "prev-delete",
    "import-errors",
    "import-cancel-btn",
    "import-confirm-btn",
]


@pytest.mark.asyncio
async def test_dashboard_renders_import_export_dom(client: AsyncClient):
    """Dashboard HTML must contain all 12 import-export DOM IDs.

    The JS handler in app/static/js/import-export.js queries these IDs
    directly. If any is missing or renamed, the handler fails at runtime
    with no user-visible error (silent failure).
    """
    response = await client.get("/")
    assert response.status_code == 200

    html = response.text
    missing = [id for id in REQUIRED_DOM_IDS if f'id="{id}"' not in html]

    assert not missing, (
        f"Dashboard is missing {len(missing)} required DOM ID(s): {missing}. "
        f"The import-export JS handler depends on these IDs."
    )
