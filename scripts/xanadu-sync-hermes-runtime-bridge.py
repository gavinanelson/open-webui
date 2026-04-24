#!/usr/bin/env python3
"""Patch the xanadu-host Hermes runtime bridge for OpenWebUI testing.

This is intentionally scoped to the testing deploy workflow. OpenWebUI can send
structured Hermes runtime fields now; the live Hermes API server also has to
honor them until that upstream source is deployed through its own release path.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


def run(command: list[str], *, check: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=check)


def candidate_roots() -> list[Path]:
    roots = [
        Path("/Users/gavin/.local/state/paddys/hermes/src"),
        Path("/Users/gavin/.hermes/hermes-agent"),
        Path("/Users/gavin/projects/hermes-agent"),
        Path("/Users/gavin/paddys/hermes/src"),
        Path("/Users/gavin/cluster-storage/offloads/xanadu-host/home/.local/state/paddys/hermes/src"),
    ]
    found = []
    for root in roots:
        if (root / "gateway/platforms/api_server.py").exists():
            found.append(root)

    if found:
        return found

    # Bounded fallback for drifted installs. Avoid a full-disk scan.
    for base in (Path("/Users/gavin/.local"), Path("/Users/gavin/.hermes"), Path("/Users/gavin/projects")):
        if not base.exists():
            continue
        for path in base.rglob("gateway/platforms/api_server.py"):
            root = path.parents[2]
            if root not in found:
                found.append(root)
    return found


def replace_once(text: str, old: str, new: str) -> tuple[str, bool]:
    if old not in text:
        return text, False
    return text.replace(old, new, 1), True


def patch_api_server(path: Path) -> bool:
    text = path.read_text()
    original = text

    text, _ = replace_once(
        text,
        "        tool_progress_callback=None,\n    ) -> Any:",
        "        tool_progress_callback=None,\n"
        "        model_override: Optional[str] = None,\n"
        "        reasoning_config: Optional[Dict[str, Any]] = None,\n"
        "        service_tier: Optional[str] = None,\n"
        "        request_overrides: Optional[Dict[str, Any]] = None,\n"
        "    ) -> Any:",
    )
    text, _ = replace_once(
        text,
        "        model = _resolve_gateway_model()\n",
        "        model = model_override or _resolve_gateway_model()\n",
    )
    text, _ = replace_once(
        text,
        "            tool_progress_callback=tool_progress_callback,\n            session_db=self._ensure_session_db(),",
        "            tool_progress_callback=tool_progress_callback,\n"
        "            reasoning_config=reasoning_config,\n"
        "            service_tier=service_tier,\n"
        "            request_overrides=request_overrides,\n"
        "            session_db=self._ensure_session_db(),",
    )
    text, _ = replace_once(
        text,
        "        session_id = body.get(\"session_id\") or run_id\n        ephemeral_system_prompt = instructions\n\n        async def _run_and_close():",
        "        session_id = body.get(\"session_id\") or run_id\n"
        "        ephemeral_system_prompt = instructions\n"
        "        model_override = body.get(\"model\")\n"
        "        if model_override is not None:\n"
        "            model_override = str(model_override).strip() or None\n"
        "        reasoning_config = None\n"
        "        reasoning = body.get(\"reasoning\")\n"
        "        if reasoning is not None:\n"
        "            try:\n"
        "                from hermes_constants import parse_reasoning_effort\n"
        "                reasoning_config = parse_reasoning_effort(str(reasoning).strip())\n"
        "            except Exception:\n"
        "                reasoning_config = None\n\n"
        "        fast_value = str(body.get(\"fast\") or \"\").strip().lower()\n"
        "        fast_enabled = fast_value in {\"1\", \"true\", \"on\", \"fast\", \"priority\"}\n"
        "        service_tier = \"priority\" if fast_enabled else None\n"
        "        request_overrides = {\"speed\": \"fast\"} if fast_enabled else None\n\n"
        "        async def _run_and_close():",
    )
    text, _ = replace_once(
        text,
        "                    tool_progress_callback=event_cb,\n                )",
        "                    tool_progress_callback=event_cb,\n"
        "                    model_override=model_override,\n"
        "                    reasoning_config=reasoning_config,\n"
        "                    service_tier=service_tier,\n"
        "                    request_overrides=request_overrides,\n"
        "                )",
    )

    if text == original:
        print(f"api_server already patched or unknown shape: {path}")
        return False
    path.write_text(text)
    print(f"patched api_server: {path}")
    return True


def patch_web_server(path: Path) -> bool:
    if not path.exists():
        return False
    text = path.read_text()
    original = text
    text = text.replace(
        '"agent.service_tier": {\n'
        '        "type": "select",\n'
        '        "description": "API service tier (OpenAI/Anthropic)",\n'
        '        "options": ["", "auto", "default", "flex"],\n'
        "    },",
        '"agent.service_tier": {\n'
        '        "type": "select",\n'
        '        "description": "API service tier (OpenAI/Anthropic)",\n'
        '        "options": ["", "normal", "fast"],\n'
        "    },\n"
        '    "agent.reasoning_effort": {\n'
        '        "type": "select",\n'
        '        "description": "Reasoning effort for the active agent session",\n'
        '        "options": ["", "none", "minimal", "low", "medium", "high", "xhigh"],\n'
        "    },",
    )
    if text == original:
        print(f"web_server already patched or unknown shape: {path}")
        return False
    path.write_text(text)
    print(f"patched web_server: {path}")
    return True


def restart_hermes_if_possible() -> None:
    labels = run(["/bin/zsh", "-lc", "launchctl list | awk '/hermes/i {print $3}'"]).stdout.splitlines()
    labels = [label.strip() for label in labels if label.strip() and label.strip() != "-"]
    if labels:
        uid = os.getuid()
        for label in labels:
            result = run(["launchctl", "kickstart", "-k", f"gui/{uid}/{label}"])
            print(f"restart launchd {label}: exit={result.returncode}")
            if result.stdout.strip():
                print(result.stdout.strip())
        return

    print("No launchd Hermes service found; source patched, restart not attempted.")


def main() -> int:
    roots = candidate_roots()
    if not roots:
        print("No Hermes source roots found on xanadu-host.")
        return 2

    changed = False
    for root in roots:
        changed = patch_api_server(root / "gateway/platforms/api_server.py") or changed
        changed = patch_web_server(root / "hermes_cli/web_server.py") or changed

    for root in roots:
        api = root / "gateway/platforms/api_server.py"
        web = root / "hermes_cli/web_server.py"
        run(["python3", "-m", "py_compile", str(api), str(web)], check=False)

    if changed:
        restart_hermes_if_possible()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
