import asyncio
import os
from typing import Any

import aiohttp
from fastapi import APIRouter, Depends, Request

from open_webui.env import AIOHTTP_CLIENT_SESSION_SSL
from open_webui.utils.auth import get_verified_user
from open_webui.utils.session_pool import get_session

router = APIRouter()


HERMES_COMMANDS = [
    {
        'category': 'Session',
        'commands': [
            {'name': 'new', 'label': 'Start a new Hermes session', 'ui': 'button'},
            {'name': 'retry', 'label': 'Retry the last message', 'ui': 'button'},
            {'name': 'undo', 'label': 'Remove last exchange', 'ui': 'button'},
            {'name': 'branch', 'label': 'Branch current session', 'ui': 'menu'},
            {'name': 'compress', 'label': 'Compress context', 'ui': 'button'},
            {'name': 'rollback', 'label': 'Restore filesystem checkpoint', 'ui': 'menu'},
            {'name': 'snapshot', 'label': 'Create or restore config/state snapshot', 'ui': 'menu'},
            {'name': 'background', 'label': 'Run a background prompt', 'ui': 'command'},
            {'name': 'btw', 'label': 'Ask side question without persisting', 'ui': 'command'},
            {'name': 'queue', 'label': 'Queue prompt for next turn', 'ui': 'command'},
            {'name': 'status', 'label': 'Show session info', 'ui': 'status-panel'},
            {'name': 'resume', 'label': 'Resume named session', 'ui': 'menu'},
        ],
    },
    {
        'category': 'Runtime',
        'commands': [
            {'name': 'model', 'label': 'Switch model for this session', 'ui': 'composer-selector'},
            {'name': 'provider', 'label': 'Show available providers', 'ui': 'composer-selector'},
            {'name': 'reasoning', 'label': 'Set reasoning effort/display', 'ui': 'composer-selector'},
            {'name': 'fast', 'label': 'Toggle fast mode', 'ui': 'composer-selector'},
            {'name': 'yolo', 'label': 'Toggle approval mode', 'ui': 'toggle'},
            {'name': 'voice', 'label': 'Toggle voice mode', 'ui': 'toggle'},
            {'name': 'personality', 'label': 'Set personality', 'ui': 'menu'},
        ],
    },
    {
        'category': 'Tools & Skills',
        'commands': [
            {'name': 'reload', 'label': 'Reload .env into running session', 'ui': 'button'},
            {'name': 'reload-mcp', 'label': 'Reload MCP servers', 'ui': 'button'},
            {'name': 'tools', 'label': 'Manage tools', 'ui': 'dashboard'},
            {'name': 'toolsets', 'label': 'List available toolsets', 'ui': 'dashboard'},
            {'name': 'skills', 'label': 'Search/install/manage skills', 'ui': 'dashboard'},
            {'name': 'cron', 'label': 'Manage scheduled tasks', 'ui': 'dashboard'},
            {'name': 'browser', 'label': 'Connect live browser tools', 'ui': 'dashboard'},
            {'name': 'plugins', 'label': 'List installed plugins', 'ui': 'dashboard'},
        ],
    },
    {
        'category': 'Info',
        'commands': [
            {'name': 'commands', 'label': 'Browse all commands', 'ui': 'dashboard'},
            {'name': 'help', 'label': 'Show available commands', 'ui': 'dashboard'},
            {'name': 'usage', 'label': 'Show token usage and rate limits', 'ui': 'status-panel'},
            {'name': 'insights', 'label': 'Show usage analytics', 'ui': 'dashboard'},
            {'name': 'profile', 'label': 'Show active profile and home directory', 'ui': 'status-panel'},
            {'name': 'debug', 'label': 'Upload debug report', 'ui': 'button'},
            {'name': 'update', 'label': 'Update Hermes Agent', 'ui': 'button'},
        ],
    },
]


def _dashboard_base_url() -> str:
    return os.getenv('HERMES_DASHBOARD_BASE_URL', 'http://127.0.0.1:9119').rstrip('/')


def _api_base_url(request: Request) -> str:
    urls = getattr(request.app.state.config, 'OPENAI_API_BASE_URLS', []) or []
    for url in urls:
        if url and ('8642' in url or '8652' in url or 'hermes' in url.lower()):
            return url.rstrip('/').removesuffix('/v1')
    return os.getenv('HERMES_API_BASE_URL', 'http://127.0.0.1:8642').rstrip('/').removesuffix('/v1')


async def _fetch_json(url: str, headers: dict[str, str] | None = None, timeout: float = 4.0) -> dict[str, Any] | list[Any]:
    session = await get_session()
    async with session.get(
        url,
        headers=headers or {},
        ssl=AIOHTTP_CLIENT_SESSION_SSL,
        timeout=aiohttp.ClientTimeout(total=timeout),
    ) as response:
        if response.status >= 400:
            raise RuntimeError(f'{response.status}: {await response.text()}')
        return await response.json()


@router.get('/overview')
async def get_hermes_overview(request: Request, user=Depends(get_verified_user)):
    api_base = _api_base_url(request)
    dashboard_base = _dashboard_base_url()

    async def safe(name: str, coro):
        try:
            return name, await coro
        except Exception as exc:
            return name, {'available': False, 'error': str(exc)}

    results = dict(
        await asyncio.gather(
            safe('health', _fetch_json(f'{api_base}/health')),
            safe('models', _fetch_json(f'{api_base}/v1/models')),
            safe('dashboard_status', _fetch_json(f'{dashboard_base}/api/status')),
            safe('model_info', _fetch_json(f'{dashboard_base}/api/model/info')),
            safe('sessions', _fetch_json(f'{dashboard_base}/api/sessions?limit=20')),
        )
    )

    return {
        'api_base_url': api_base,
        'dashboard_base_url': dashboard_base,
        'commands': HERMES_COMMANDS,
        **results,
    }


@router.get('/commands')
async def get_hermes_commands(user=Depends(get_verified_user)):
    return {'commands': HERMES_COMMANDS}
