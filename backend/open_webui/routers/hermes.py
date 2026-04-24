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


def _label_from_value(value: str) -> str:
    cleaned = str(value or '').strip()
    if not cleaned:
        return 'Default'
    return cleaned.replace('_', ' ').replace('-', ' ').title()


def _dedupe_options(options: list[dict[str, str]]) -> list[dict[str, str]]:
    seen = set()
    result = []
    for option in options:
        value = str(option.get('value') or '').strip()
        if value in seen:
            continue
        seen.add(value)
        result.append(
            {
                'value': value,
                'label': str(option.get('label') or _label_from_value(value)),
                **({'description': option['description']} if option.get('description') else {}),
            }
        )
    return result


def _schema_options(schema: dict[str, Any], key: str) -> list[dict[str, str]]:
    field = (schema.get('fields') or {}).get(key) if isinstance(schema, dict) else None
    values = field.get('options') if isinstance(field, dict) else None
    if not isinstance(values, list):
        return []
    return [{'value': str(value), 'label': _label_from_value(str(value))} for value in values]


def _config_value(config: dict[str, Any], key: str) -> str:
    current: Any = config
    for part in key.split('.'):
        if not isinstance(current, dict) or part not in current:
            return ''
        current = current.get(part)
    if isinstance(current, dict):
        return str(current.get('default') or current.get('name') or '')
    return str(current or '')


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


@router.get('/runtime-options')
async def get_hermes_runtime_options(request: Request, user=Depends(get_verified_user)):
    api_base = _api_base_url(request)
    dashboard_base = _dashboard_base_url()

    async def safe(coro, default):
        try:
            return await coro
        except Exception:
            return default

    models_payload, model_info, config, schema = await asyncio.gather(
        safe(_fetch_json(f'{api_base}/v1/models'), {}),
        safe(_fetch_json(f'{dashboard_base}/api/model/info'), {}),
        safe(_fetch_json(f'{dashboard_base}/api/config'), {}),
        safe(_fetch_json(f'{dashboard_base}/api/config/schema'), {}),
    )

    model_options = []
    for model in (models_payload.get('data') if isinstance(models_payload, dict) else []) or []:
        if isinstance(model, dict) and model.get('id'):
            model_options.append(
                {
                    'value': str(model['id']),
                    'label': str(model.get('name') or model.get('id')),
                    'description': str(model.get('owned_by') or 'Hermes model'),
                }
            )

    configured_model = (
        (model_info.get('model') if isinstance(model_info, dict) else None)
        or (_config_value(config, 'model') if isinstance(config, dict) else '')
    )
    if configured_model:
        model_options.insert(0, {'value': configured_model, 'label': configured_model, 'description': 'Configured Hermes model'})

    reasoning_options = _schema_options(schema, 'agent.reasoning_effort')
    fast_options = _schema_options(schema, 'agent.service_tier')
    if not reasoning_options:
        reasoning_options = [
            {'value': value, 'label': _label_from_value(value)}
            for value in ('', 'none', 'minimal', 'low', 'medium', 'high', 'xhigh')
        ]
    if not fast_options:
        fast_options = [
            {'value': 'normal', 'label': 'Normal'},
            {'value': 'fast', 'label': 'Fast'},
        ]

    current_reasoning = _config_value(config, 'agent.reasoning_effort') if isinstance(config, dict) else ''
    current_fast = _config_value(config, 'agent.service_tier') if isinstance(config, dict) else ''
    current_fast = 'fast' if current_fast in {'fast', 'priority', 'on'} else 'normal'

    current = {
        'model': configured_model or (model_options[0]['value'] if model_options else ''),
        'reasoning': current_reasoning or (reasoning_options[0]['value'] if reasoning_options else ''),
        'fast': current_fast or (fast_options[0]['value'] if fast_options else ''),
    }

    config_options = [
        {
            'id': 'model',
            'name': 'Model',
            'category': 'model',
            'type': 'select',
            'currentValue': current['model'],
            'options': [
                {'value': option['value'], 'name': option['label'], 'description': option.get('description', '')}
                for option in _dedupe_options(model_options)
            ],
        },
        {
            'id': 'reasoning',
            'name': 'Reasoning',
            'category': 'thought_level',
            'type': 'select',
            'currentValue': current['reasoning'],
            'options': [
                {'value': option['value'], 'name': option['label'], 'description': option.get('description', '')}
                for option in _dedupe_options(reasoning_options)
            ],
        },
        {
            'id': 'fast',
            'name': 'Fast Mode',
            'category': '_hermes_fast_mode',
            'type': 'select',
            'currentValue': current['fast'],
            'options': [
                {'value': option['value'], 'name': option['label'], 'description': option.get('description', '')}
                for option in _dedupe_options(fast_options)
            ],
        },
    ]

    return {
        'current': current,
        'model_options': _dedupe_options(model_options),
        'reasoning_options': _dedupe_options(reasoning_options),
        'fast_options': _dedupe_options(fast_options),
        'config_options': config_options,
        'sources': {
            'models': f'{api_base}/v1/models',
            'model_info': f'{dashboard_base}/api/model/info',
            'config': f'{dashboard_base}/api/config',
            'schema': f'{dashboard_base}/api/config/schema',
        },
    }
