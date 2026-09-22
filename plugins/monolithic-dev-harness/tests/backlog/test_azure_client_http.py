"""HTTP-level tests for the Azure capacity client.

Runs a real HTTP server on localhost and points the client at it, so the actual urllib code
path executes -- URL construction, the auth header, response decoding, and every error
branch. No network access and no credentials are involved.

A mock of `urlopen` would not cover any of this: the bugs these tests catch live in the
request the client builds, not in the code around it.
"""

import base64
import json
import os
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from orchestrator_core.providers.azure_devops import AzureDevOpsProvider
from orchestrator_core.providers.azure_devops.client import API_VERSION, AzureCapacityClient

CAPACITIES_BODY = {
    "count": 1,
    "value": [
        {
            "teamMember": {"id": "u1", "displayName": "Ana"},
            "activities": [{"capacityPerDay": 6, "name": "Development"}],
            "daysOff": [],
        }
    ],
}

# path fragment -> (status, body). First match wins; anything else is a 200 with {}.
ROUTES: dict[str, tuple[int, object]] = {}
CAPTURED: list[dict] = []


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self):  # noqa: N802 - name fixed by BaseHTTPRequestHandler
        CAPTURED.append({"path": self.path, "headers": dict(self.headers)})

        status, body = 200, {}
        for fragment, route in ROUTES.items():
            if fragment in self.path:
                status, body = route
                break

        if body == "__SLOW__":
            time.sleep(2.0)
            body = {}

        payload = body if isinstance(body, str) else json.dumps(body)
        encoded = payload.encode("utf-8")
        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)
        except (BrokenPipeError, ConnectionResetError):
            # Expected in the timeout test: the client has already given up and closed.
            pass

    def log_message(self, *args):
        """Silence the default stderr logging so test output stays readable."""


class _QuietServer(ThreadingHTTPServer):
    def handle_error(self, request, client_address):
        """Suppress tracebacks for clients that disconnected on purpose."""


class AzureHttpTestCase(unittest.TestCase):
    """Base case owning the localhost server."""

    @classmethod
    def setUpClass(cls):
        cls.server = _QuietServer(("127.0.0.1", 0), _Handler)
        cls.port = cls.server.server_address[1]
        cls.base_url = f"http://127.0.0.1:{cls.port}"
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)

    def setUp(self):
        ROUTES.clear()
        CAPTURED.clear()

    def client(self, **kwargs):
        kwargs.setdefault("pat", "secret-token")
        kwargs.setdefault("base_url", self.base_url)
        return AzureCapacityClient(kwargs.pop("org", "myorg"), kwargs.pop("project", "myproj"), **kwargs)

    @property
    def last_path(self):
        return CAPTURED[-1]["path"]


class TestRequestConstruction(AzureHttpTestCase):
    """Tests for the request the client actually emits."""

    def test_capacities_url_and_api_version(self):
        """The documented capacity endpoint, with api-version appended."""
        ROUTES["capacities"] = (200, CAPACITIES_BODY)
        data, error = self.client().get_capacities("it1")
        self.assertIsNone(error)
        self.assertEqual(
            self.last_path,
            f"/myorg/myproj/_apis/work/teamsettings/iterations/it1/capacities?api-version={API_VERSION}",
        )

    def test_team_scope_is_inserted_when_given(self):
        """Capacity endpoints are team-scoped, between project and _apis."""
        self.client(team="my team").get_capacities("it1")
        self.assertIn("/myorg/myproj/my%20team/_apis/", self.last_path)

    def test_api_version_uses_ampersand_when_query_already_present(self):
        """get_work_items already has ?ids=, so api-version must join with &."""
        self.client().get_work_items(["1", "2"])
        self.assertIn("?ids=1,2", self.last_path)
        self.assertIn(f"&api-version={API_VERSION}", self.last_path)
        self.assertNotIn("?api-version", self.last_path)

    def test_auth_header_is_basic_with_empty_username(self):
        """Azure PAT auth is Basic with an empty username and the PAT as password."""
        self.client(pat="abc123").get_capacities("it1")
        expected = base64.b64encode(b":abc123").decode()
        self.assertEqual(CAPTURED[-1]["headers"]["Authorization"], f"Basic {expected}")

    def test_organization_and_iteration_are_url_quoted(self):
        """Values with spaces or slashes must not break the path."""
        self.client(org="my org").get_capacities("Sprint 42")
        self.assertIn("/my%20org/", self.last_path)
        self.assertIn("Sprint%2042", self.last_path)

    def test_empty_id_list_short_circuits_without_a_request(self):
        """Asking for no work items should not hit the network at all."""
        data, error = self.client().get_work_items([])
        self.assertIsNone(error)
        self.assertEqual(data, {"value": []})
        self.assertEqual(CAPTURED, [])


class TestResponseHandling(AzureHttpTestCase):
    """Tests for decoding and error branches."""

    def test_successful_body_is_decoded(self):
        """A 200 returns the parsed document."""
        ROUTES["capacities"] = (200, CAPACITIES_BODY)
        data, error = self.client().get_capacities("it1")
        self.assertIsNone(error)
        self.assertEqual(data["value"][0]["teamMember"]["id"], "u1")

    def test_401_reports_authentication_failure(self):
        """A bad PAT gets a message naming the actual problem."""
        ROUTES["capacities"] = (401, {})
        data, error = self.client().get_capacities("it1")
        self.assertIsNone(data)
        self.assertIn("401", error)
        self.assertIn("authentication failed", error)

    def test_404_is_reported_with_status(self):
        """A wrong iteration id surfaces as a 404, not a crash."""
        ROUTES["capacities"] = (404, {})
        data, error = self.client().get_capacities("nope")
        self.assertIsNone(data)
        self.assertIn("404", error)

    def test_500_is_reported(self):
        """A server-side failure is reported rather than raised."""
        ROUTES["capacities"] = (500, {})
        self.assertIn("500", self.client().get_capacities("it1")[1])

    def test_malformed_json_is_reported(self):
        """A 200 carrying broken JSON must not raise."""
        ROUTES["capacities"] = (200, "{not json")
        data, error = self.client().get_capacities("it1")
        self.assertIsNone(data)
        self.assertIn("malformed JSON", error)

    def test_connection_refused_is_reported(self):
        """An unreachable host is a message, not an exception."""
        client = AzureCapacityClient("org", "proj", pat="x", base_url="http://127.0.0.1:1")
        data, error = client.get_capacities("it1")
        self.assertIsNone(data)
        self.assertTrue(error)

    def test_timeout_is_reported(self):
        """A slow endpoint times out cleanly, following never-raise."""
        ROUTES["capacities"] = (200, "__SLOW__")
        data, error = self.client(timeout=1).get_capacities("it1")
        self.assertIsNone(data)
        self.assertTrue(error)

    def test_list_iterations_finds_sprints_without_a_known_id(self):
        """Discovery endpoint: lets a caller find an iteration id without knowing a GUID."""
        ROUTES["work/teamsettings/iterations?"] = (
            200,
            {"count": 1, "value": [{"id": "abc-123", "name": "Sprint 42"}]},
        )
        data, error = self.client().list_iterations()
        self.assertIsNone(error)
        self.assertEqual(data["value"][0]["name"], "Sprint 42")
        self.assertIn("/work/teamsettings/iterations?api-version=", self.last_path)

    def test_every_endpoint_returns_the_two_tuple_contract(self):
        """No endpoint may raise; all return (data, error)."""
        ROUTES["_apis"] = (500, {})
        client = self.client()
        for call in (
            lambda: client.get_capacities("it1"),
            lambda: client.get_iteration("it1"),
            lambda: client.list_iterations(),
            lambda: client.get_team_settings(),
            lambda: client.get_iteration_work_items("it1"),
            lambda: client.get_work_items(["1"]),
        ):
            data, error = call()
            self.assertIsNone(data)
            self.assertTrue(error)


class TestProviderOverHttp(AzureHttpTestCase):
    """End-to-end: provider driving the live client against the local server."""

    def test_provider_builds_an_iteration_from_http_responses(self):
        """The full read path works without any injected payload."""
        ROUTES["capacities"] = (200, CAPACITIES_BODY)
        ROUTES["teamsettings/iterations/it1?"] = (
            200,
            {"id": "it1", "attributes": {"startDate": "2026-08-03", "finishDate": "2026-08-14"}},
        )
        ROUTES["work/teamsettings?"] = (
            200,
            {"workingDays": ["monday", "tuesday", "wednesday", "thursday", "friday"]},
        )
        provider = AzureDevOpsProvider(client=self.client(), process="agile")
        result = provider.fetch_iteration("it1")
        self.assertTrue(result.ok)
        self.assertEqual(len(result.data.members), 1)
        self.assertEqual(len(result.data.working_days()), 10)

    def test_capacity_failure_fails_the_read(self):
        """Capacity is the required call; losing it fails the whole fetch."""
        ROUTES["capacities"] = (500, {})
        result = AzureDevOpsProvider(client=self.client()).fetch_iteration("it1")
        self.assertFalse(result.ok)

    def test_optional_calls_degrade_to_warnings(self):
        """Missing dates or team settings warn; they do not fail the read."""
        ROUTES["capacities"] = (200, CAPACITIES_BODY)
        ROUTES["teamsettings/iterations/it1?"] = (404, {})
        ROUTES["work/teamsettings?"] = (404, {})
        result = AzureDevOpsProvider(client=self.client()).fetch_iteration("it1")
        self.assertTrue(result.ok)
        self.assertTrue(any("iteration dates unavailable" in w for w in result.warnings))
        self.assertTrue(any("team settings unavailable" in w for w in result.warnings))

    def test_empty_iteration_reports_no_work_items(self):
        """An iteration with no contents is a warning, not an error."""
        ROUTES["teamsettings/iterations/it1/workitems"] = (200, {"workItemRelations": []})
        result = AzureDevOpsProvider(client=self.client()).fetch_work_items("it1")
        self.assertTrue(result.ok)
        self.assertEqual(result.data, [])

    def test_work_items_are_fetched_by_id_then_mapped(self):
        """The two-step listing-then-detail read produces mapped items.

        Route fragments must stay distinct: the iteration listing path and the detail path
        both end in `workitems`, so a loose fragment silently serves the wrong body.
        """
        ROUTES["teamsettings/iterations/it1/workitems"] = (
            200,
            {"workItemRelations": [{"target": {"id": 101}}, {"target": {"id": 102}}]},
        )
        ROUTES["wit/workitems"] = (
            200,
            {
                "value": [
                    {"id": 101, "fields": {"Microsoft.VSTS.Scheduling.RemainingWork": 8}},
                    {"id": 102, "fields": {"Microsoft.VSTS.Scheduling.RemainingWork": 4}},
                ]
            },
        )
        result = AzureDevOpsProvider(client=self.client()).fetch_work_items("it1")
        self.assertTrue(result.ok)
        self.assertEqual([i.remaining_hours for i in result.data], [8.0, 4.0])
        self.assertIn("ids=101,102", CAPTURED[-1]["path"])


@unittest.skipUnless(
    os.environ.get("ADO_PAT") or os.environ.get("AZURE_DEVOPS_EXT_PAT"),
    "live Azure smoke test: set ADO_PAT plus ADO_ORG, ADO_PROJECT, ADO_ITERATION to run",
)
class TestLiveAzureSmoke(unittest.TestCase):
    """Read-only smoke test against a real organisation. Skipped without credentials.

    Writes nothing. Run it once after wiring an org to confirm the fixtures in
    test_providers.py match what the API really returns.
    """

    def test_capacities_read(self):
        org = os.environ.get("ADO_ORG", "")
        project = os.environ.get("ADO_PROJECT", "")
        iteration = os.environ.get("ADO_ITERATION", "")
        if not (org and project and iteration):
            self.skipTest("set ADO_ORG, ADO_PROJECT and ADO_ITERATION")

        client = AzureCapacityClient(org, project, team=os.environ.get("ADO_TEAM"))
        data, error = client.get_capacities(iteration)
        self.assertIsNone(error, f"live read failed: {error}")
        self.assertIn("value", data)


if __name__ == "__main__":
    unittest.main()
