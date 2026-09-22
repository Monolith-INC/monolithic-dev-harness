"""Optional direct reader for the Azure DevOps work/capacity API.

Exists because the Azure DevOps MCP server is `wit_*`-focused and capacity lives under a
different API area. Uses `urllib.request` from the standard library, so the runtime keeps
its zero-dependency promise.

This is the fallback path. The primary path is injection: a skill fetches the JSON through
MCP or curl and hands it to `mapping.py`, which is pure and needs no credentials.
"""

from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

API_VERSION = "7.1"
DEFAULT_TIMEOUT = 30

PAT_ENV_VARS = ("AZURE_DEVOPS_EXT_PAT", "ADO_PAT", "AZURE_DEVOPS_PAT")


class AzureCapacityClient:
    """Read-only client. It has no method that writes -- writes go through WriteOp review."""

    def __init__(
        self,
        organization: str,
        project: str,
        *,
        team: str | None = None,
        pat: str | None = None,
        base_url: str = "https://dev.azure.com",
        timeout: int = DEFAULT_TIMEOUT,
    ) -> None:
        self.organization = organization.strip().strip("/")
        self.project = project.strip().strip("/")
        self.team = (team or "").strip().strip("/")
        self.pat = pat or self._pat_from_env()
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    @staticmethod
    def _pat_from_env() -> str | None:
        for key in PAT_ENV_VARS:
            value = os.environ.get(key, "").strip()
            if value:
                return value
        return None

    @property
    def configured(self) -> bool:
        return bool(self.organization and self.project and self.pat)

    def _scope(self) -> str:
        parts = [self.base_url, urllib.parse.quote(self.organization), urllib.parse.quote(self.project)]
        if self.team:
            parts.append(urllib.parse.quote(self.team))
        return "/".join(parts)

    def _headers(self) -> dict[str, str]:
        # PAT auth is Basic with an empty username.
        token = base64.b64encode(f":{self.pat}".encode()).decode()
        return {"Authorization": f"Basic {token}", "Accept": "application/json"}

    def _get(self, path: str) -> tuple[Any | None, str | None]:
        """GET a JSON document. Returns (data, error) -- never raises."""
        if not self.configured:
            missing = "organization/project" if not (self.organization and self.project) else "PAT"
            return None, f"Azure client not configured: missing {missing}"

        url = f"{self._scope()}/_apis/{path.lstrip('/')}"
        separator = "&" if "?" in url else "?"
        url = f"{url}{separator}api-version={API_VERSION}"

        request = urllib.request.Request(url, headers=self._headers(), method="GET")
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8")), None
        except urllib.error.HTTPError as exc:
            detail = "authentication failed" if exc.code in (401, 203) else exc.reason
            return None, f"HTTP {exc.code} from {path}: {detail}"
        except urllib.error.URLError as exc:
            return None, f"network error calling {path}: {exc.reason}"
        except (json.JSONDecodeError, ValueError) as exc:
            return None, f"malformed JSON from {path}: {exc}"
        except OSError as exc:
            return None, f"transport error calling {path}: {exc}"

    # -- endpoints ---------------------------------------------------------

    def get_capacities(self, iteration_id: str) -> tuple[Any | None, str | None]:
        return self._get(f"work/teamsettings/iterations/{urllib.parse.quote(iteration_id)}/capacities")

    def get_iteration(self, iteration_id: str) -> tuple[Any | None, str | None]:
        return self._get(f"work/teamsettings/iterations/{urllib.parse.quote(iteration_id)}")

    def list_iterations(self) -> tuple[Any | None, str | None]:
        """List the team's iterations, so a caller can find an id without hunting for a GUID."""
        return self._get("work/teamsettings/iterations")

    def get_current_iteration(self) -> tuple[Any | None, str | None]:
        """The active sprint, so nobody has to pass an id for the common case."""
        return self._get("work/teamsettings/iterations?$timeframe=current")

    def get_team_settings(self) -> tuple[Any | None, str | None]:
        return self._get("work/teamsettings")

    def get_iteration_work_items(self, iteration_id: str) -> tuple[Any | None, str | None]:
        return self._get(f"work/teamsettings/iterations/{urllib.parse.quote(iteration_id)}/workitems")

    def get_work_items(self, ids: list[str]) -> tuple[Any | None, str | None]:
        if not ids:
            return {"value": []}, None
        joined = ",".join(urllib.parse.quote(str(i)) for i in ids)
        return self._get(f"wit/workitems?ids={joined}&$expand=Fields")
