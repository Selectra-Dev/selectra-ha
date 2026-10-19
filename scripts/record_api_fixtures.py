"""Record real Selectra Planning API exchanges for the replay tests.

Each scenario in tests/fixtures/api/scenarios.json walks the qualification
the way a user would in the setup dialog, then fetches /planning/details and
/planning/prices. Every request and raw response is written to
tests/fixtures/api/<scenario>.json, which tests/test_api_replay.py plays back
through the real config flow, coordinator and entities.

The hand-written fixtures elsewhere in the suite describe the API as the
integration expects it to be. These describe it as it is, so a change of
shape on the API side (the v2 /details envelope, for one) fails the suite
instead of reaching users.

    SELECTRA_API_TOKEN=... python scripts/record_api_fixtures.py [scenario ...]

SELECTRA_API_URL overrides the base URL (a local energy-core, for instance).
Standard library only, so the nightly job has nothing to install.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures" / "api"
SCENARIOS = FIXTURES / "scenarios.json"
FAILED = FIXTURES / "failed"

BASE_URL = os.environ.get("SELECTRA_API_URL", "https://api.selectra.com/api").rstrip("/")
TOKEN = os.environ.get("SELECTRA_API_TOKEN", "")
# Cloudflare in front of the API bans urllib's default "Python-urllib/x.y"
# signature (error 1010), so name the client explicitly.
VERSION = json.loads(
    (ROOT / "custom_components" / "selectra" / "manifest.json").read_text(encoding="utf-8")
)["version"]
USER_AGENT = f"selectra-ha/{VERSION} (contract recorder)"

# Questions a user answers "no" to, so the walk stays on the plain path.
DECLINED_FIELDS = ("feed_in", "custom_off_peak_hours")
MAX_STEPS = 25


class RecordError(Exception):
    """A scenario could not be walked to the end."""


def _post(path: str, payload: dict[str, Any]) -> Any:
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": USER_AGENT,
    }
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    request = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=json.dumps(payload).encode(),
        headers=headers,
        method="POST",
    )
    for attempt in range(4):
        try:
            with urllib.request.urlopen(request, timeout=60) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as err:
            if err.code == 429 and attempt < 3:
                time.sleep(int(err.headers.get("Retry-After") or 10))
                continue
            body = err.read().decode(errors="replace")[:500]
            raise RecordError(f"{path} answered {err.code}: {body}") from err
    raise RecordError(f"{path} stayed rate limited")


def _option_values(question: dict[str, Any]) -> list[str]:
    """The values a select question accepts, as the config flow offers them."""
    options = question.get("options") or []
    if isinstance(options, dict):
        return [str(key) for key in options]
    return [
        str(opt.get("value", "")) if isinstance(opt, dict) else str(opt)
        for opt in options
    ]


def _answer(question: dict[str, Any], answers: dict[str, Any]) -> Any:
    """The scenario's answer to a question, or what a user would pick."""
    field = question["field"]
    q_type = question.get("type", "text")
    if q_type == "checkbox":
        return answers.get(field, False)
    if q_type != "select":
        if field not in answers:
            raise RecordError(
                f"no answer for the {q_type} question {field!r}; add it to the scenario"
            )
        return answers[field]

    values = _option_values(question)
    if not values:
        raise RecordError(f"the select question {field!r} has no options")
    if field in answers:
        # Home Assistant only submits a listed option; so must the walk.
        if str(answers[field]) not in values:
            raise RecordError(
                f"{answers[field]!r} is not an option of {field!r}: {', '.join(values[:20])}"
            )
        return str(answers[field])
    if field in DECLINED_FIELDS and "no" in values:
        return "no"
    return values[0]


def _cast(field: str, value: Any) -> Any:
    """Cast a select answer the way the config flow does (_cast_select_values)."""
    if isinstance(value, str) and field.endswith("_id") and field != "off_peak_hours_id":
        for cast in (int, float):
            try:
                return cast(value)
            except ValueError:
                pass
    return value


def record(
    name: str, scenario: dict[str, Any], steps: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    """Walk one scenario and return its recording.

    The qualification calls go into `steps` as they happen, so a caller can
    keep how far a failed walk got.
    """
    lang = scenario.get("lang", "en")
    answers = {"country_code": scenario["country_code"], **scenario.get("answers", {})}

    steps = [] if steps is None else steps
    inputs: dict[str, Any] = {}
    feed_in_answer = None

    request = {"lang": lang}
    response = _post("/planning/qualification", request)
    steps.append({"request": request, "response": response})

    while not response.get("done"):
        if response.get("message"):
            raise RecordError(f"qualification stopped: {response['message']}")
        questions = response.get("questions") or []
        if not questions:
            raise RecordError("qualification is not done but asks nothing")
        if len(steps) > MAX_STEPS:
            raise RecordError(f"qualification did not finish in {MAX_STEPS} steps")
        errors = [q["error"] for q in questions if q.get("error")]
        if errors:
            raise RecordError(f"the API rejected an answer: {errors[0]}")

        inputs = dict(response.get("inputs") or inputs)
        step_answers: dict[str, Any] = {}
        for question in questions:
            field = question["field"]
            value = _answer(question, answers)
            step_answers[field] = value
            inputs[field] = _cast(field, value) if question.get("type") == "select" else value
        if "feed_in" in step_answers:
            feed_in_answer = step_answers["feed_in"]

        request = {**inputs, "lang": lang}
        response = _post("/planning/qualification", request)
        steps[-1]["answers"] = step_answers
        steps.append({"request": request, "response": response})

    final_inputs = dict(response.get("inputs") or inputs)
    if feed_in_answer is not None:
        final_inputs.setdefault("feed_in", feed_in_answer)

    details = _post("/planning/details", final_inputs)
    prices = _post("/planning/prices", final_inputs)
    # The integration shows nothing but a requalification error for this, so
    # the recording would test nothing; and upstream, it is worth a look.
    if prices.get("requalification_reason") or not prices.get("prices"):
        reason = prices.get("requalification_reason") or "no periods"
        offer = ((details.get("offer") or {}).get("name") or {}).get(lang)
        option = (details.get("option") or {}).get("name")
        raise RecordError(
            f"/prices: {reason} (offer {offer!r}, option {option!r}, "
            f"category {details.get('category')!r}, inputs {json.dumps(final_inputs)})"
        )

    return {
        "scenario": name,
        "recorded_from": BASE_URL,
        "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "lang": lang,
        "time_zone": scenario["time_zone"],
        "expect": scenario.get("expect", {}),
        "qualification": steps,
        "details": {"request": final_inputs, "response": details},
        "prices": {"request": final_inputs, "response": prices},
    }


def main(argv: list[str]) -> int:
    scenarios: dict[str, Any] = json.loads(SCENARIOS.read_text(encoding="utf-8"))
    names = argv or list(scenarios)
    unknown = [n for n in names if n not in scenarios]
    if unknown:
        print(f"unknown scenario(s): {', '.join(unknown)}", file=sys.stderr)
        return 2

    failed = 0
    for name in names:
        steps: list[dict[str, Any]] = []
        try:
            recording = record(name, scenarios[name], steps)
        except RecordError as err:
            failed += 1
            print(f"FAIL {name}: {err}", file=sys.stderr)
            # Kept out of the replay (it globs the top level only) but uploaded
            # with the recordings, to see which options the walk was offered.
            FAILED.mkdir(exist_ok=True)
            (FAILED / f"{name}.json").write_text(
                json.dumps({"error": str(err), "qualification": steps}, ensure_ascii=False, indent=2)
                + "\n",
                encoding="utf-8",
            )
            continue
        path = FIXTURES / f"{name}.json"
        path.write_text(
            json.dumps(recording, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        category = recording["details"]["response"].get("category")
        print(f"ok   {name}: {category}, {len(recording['qualification'])} qualification calls")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
