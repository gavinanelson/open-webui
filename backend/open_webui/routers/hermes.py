import asyncio
import os
import re
from typing import Any
from urllib.parse import urlparse

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
            {'name': 'new', 'label': 'Start a new session', 'ui': 'native-chat', 'aliases': ['reset']},
            {'name': 'retry', 'label': 'Retry the last message', 'ui': 'native-chat'},
            {'name': 'undo', 'label': 'Remove the last exchange', 'ui': 'native-chat'},
            {'name': 'title', 'label': 'Set a title for the current session', 'ui': 'native-chat', 'args_hint': '[name]'},
            {
                'name': 'branch',
                'label': 'Branch the current session',
                'ui': 'native-chat',
                'aliases': ['fork'],
                'args_hint': '[name]',
            },
            {'name': 'compress', 'label': 'Manually compress conversation context', 'ui': 'native-chat', 'args_hint': '[focus topic]'},
            {'name': 'rollback', 'label': 'List or restore filesystem checkpoints', 'ui': 'native-chat', 'args_hint': '[number]'},
            {
                'name': 'snapshot',
                'label': 'Create or restore Hermes config/state snapshots',
                'ui': 'native-chat',
                'aliases': ['snap'],
                'args_hint': '[create|restore <id>|prune]',
                'subcommands': ['create', 'restore', 'prune'],
            },
            {'name': 'stop', 'label': 'Kill all running background processes', 'ui': 'native-chat'},
            {'name': 'approve', 'label': 'Approve a pending dangerous command', 'ui': 'native-chat', 'args_hint': '[session|always]'},
            {'name': 'deny', 'label': 'Deny a pending dangerous command', 'ui': 'native-chat'},
            {'name': 'background', 'label': 'Run a prompt in the background', 'ui': 'native-chat', 'aliases': ['bg'], 'args_hint': '<prompt>'},
            {'name': 'btw', 'label': 'Ask an ephemeral side question', 'ui': 'native-chat', 'args_hint': '<question>'},
            {'name': 'queue', 'label': 'Queue a prompt for the next turn', 'ui': 'native-chat', 'aliases': ['q'], 'args_hint': '<prompt>'},
            {'name': 'status', 'label': 'Show session info', 'ui': 'dashboard'},
            {'name': 'sethome', 'label': 'Set this chat as the home channel', 'ui': 'native-chat', 'aliases': ['set-home']},
            {'name': 'resume', 'label': 'Resume a previously named session', 'ui': 'native-chat', 'args_hint': '[name]'},
            {'name': 'restart', 'label': 'Gracefully restart the gateway', 'ui': 'dashboard'},
        ],
    },
    {
        'category': 'Configuration',
        'commands': [
            {'name': 'model', 'label': 'Switch model for this session', 'ui': 'composer-selector', 'args_hint': '[model] [--global]'},
            {'name': 'provider', 'label': 'Show available providers and current provider', 'ui': 'dashboard'},
            {'name': 'personality', 'label': 'Set a predefined personality', 'ui': 'native-chat', 'args_hint': '[name]'},
            {
                'name': 'reasoning',
                'label': 'Manage reasoning effort and display',
                'ui': 'composer-selector',
                'args_hint': '[level|show|hide]',
                'subcommands': ['none', 'minimal', 'low', 'medium', 'high', 'xhigh', 'show', 'hide', 'on', 'off'],
            },
            {
                'name': 'fast',
                'label': 'Toggle fast mode',
                'ui': 'composer-selector',
                'args_hint': '[normal|fast|status]',
                'subcommands': ['normal', 'fast', 'status', 'on', 'off'],
            },
            {'name': 'yolo', 'label': 'Toggle YOLO approval mode', 'ui': 'native-chat'},
            {
                'name': 'voice',
                'label': 'Toggle voice mode',
                'ui': 'native-chat',
                'args_hint': '[on|off|tts|status]',
                'subcommands': ['on', 'off', 'tts', 'status'],
            },
        ],
    },
    {
        'category': 'Tools & Skills',
        'commands': [
            {
                'name': 'tools',
                'label': 'Manage tools',
                'ui': 'dashboard',
                'args_hint': '[list|disable|enable] [name...]',
                'subcommands': ['list', 'disable', 'enable'],
            },
            {'name': 'toolsets', 'label': 'List available toolsets', 'ui': 'dashboard'},
            {
                'name': 'skills',
                'label': 'Search, install, inspect, or manage skills',
                'ui': 'dashboard',
                'subcommands': ['search', 'browse', 'inspect', 'install'],
            },
            {
                'name': 'cron',
                'label': 'Manage scheduled tasks',
                'ui': 'dashboard',
                'args_hint': '[subcommand]',
                'subcommands': ['list', 'add', 'create', 'edit', 'pause', 'resume', 'run', 'remove'],
            },
            {'name': 'reload', 'label': 'Reload .env into the running session', 'ui': 'native-chat'},
            {'name': 'reload-mcp', 'label': 'Reload MCP servers from config', 'ui': 'native-chat', 'aliases': ['reload_mcp']},
            {
                'name': 'browser',
                'label': 'Connect browser tools to live Chrome via CDP',
                'ui': 'dashboard',
                'args_hint': '[connect|disconnect|status]',
                'subcommands': ['connect', 'disconnect', 'status'],
            },
            {'name': 'plugins', 'label': 'List installed plugins and their status', 'ui': 'dashboard'},
        ],
    },
    {
        'category': 'Info',
        'commands': [
            {'name': 'commands', 'label': 'Browse all commands and skills', 'ui': 'dashboard', 'args_hint': '[page]'},
            {'name': 'help', 'label': 'Show available commands', 'ui': 'dashboard'},
            {'name': 'usage', 'label': 'Show token usage and rate limits', 'ui': 'dashboard'},
            {'name': 'insights', 'label': 'Show usage insights and analytics', 'ui': 'dashboard', 'args_hint': '[days]'},
            {'name': 'profile', 'label': 'Show active profile and home directory', 'ui': 'dashboard'},
            {'name': 'debug', 'label': 'Upload a debug report and get shareable links', 'ui': 'dashboard'},
            {'name': 'update', 'label': 'Update Hermes Agent to the latest version', 'ui': 'dashboard'},
        ],
    },
]


def _dashboard_base_url(request: Request | None = None) -> str:
    configured_url = os.getenv('HERMES_DASHBOARD_BASE_URL')
    if configured_url:
        return configured_url.rstrip('/')

    if request:
        urls = getattr(request.app.state.config, 'OPENAI_API_BASE_URLS', []) or []
        for url in urls:
            parsed_host = urlparse(url).hostname or ''

            if parsed_host and parsed_host not in {'127.0.0.1', 'localhost'}:
                return f'http://{parsed_host}:9119'

    return 'http://127.0.0.1:9119'


def _api_base_url(request: Request) -> str:
    urls = getattr(request.app.state.config, 'OPENAI_API_BASE_URLS', []) or []
    for url in urls:
        if url and ('8642' in url or '8652' in url or 'hermes' in url.lower()):
            return url.rstrip('/').removesuffix('/v1')
    return os.getenv('HERMES_API_BASE_URL', 'http://127.0.0.1:8642').rstrip('/').removesuffix('/v1')


def _api_auth_headers(request: Request) -> dict[str, str]:
    urls = getattr(request.app.state.config, 'OPENAI_API_BASE_URLS', []) or []
    keys = getattr(request.app.state.config, 'OPENAI_API_KEYS', []) or []
    for idx, url in enumerate(urls):
        if url and ('8642' in url or '8652' in url or 'hermes' in url.lower()):
            key = keys[idx] if idx < len(keys) else ''
            if key:
                return {'Authorization': f'Bearer {key}'}

    fallback = os.getenv('HERMES_API_KEY') or os.getenv('OPENAI_API_KEY') or ''
    return {'Authorization': f'Bearer {fallback}'} if fallback else {}


def _dashboard_headers(dashboard_base: str) -> dict[str, str]:
    host = urlparse(dashboard_base).hostname or ''
    return {'Host': 'localhost'} if host == 'host.docker.internal' else {}


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


def _reasoning_option_values_for_model(model_id: str, supports_reasoning: bool | None = None) -> list[str]:
    model = str(model_id or '').strip().lower()
    model = re.sub(r'^[a-z0-9_.-]+/', '', model)

    if not model:
        return ['']

    # OpenAI publishes model-specific reasoning effort sets. Keep this scoped so
    # the harness does not offer invalid efforts for older or non-reasoning models.
    if re.search(r'\bgpt-5\.(?:4|5)(?:[-\w.]*)?$', model):
        return ['', 'none', 'low', 'medium', 'high', 'xhigh']
    if re.search(r'\bgpt-5\.[23](?:[-\w.]*)?$', model):
        return ['', 'low', 'medium', 'high', 'xhigh']
    if re.search(r'\bgpt-5\.1(?:[-\w.]*)?$', model):
        return ['', 'none', 'low', 'medium', 'high']
    if re.search(r'\bgpt-5(?:-(?:mini|nano|codex|pro).*)?$', model):
        return ['', 'minimal', 'low', 'medium', 'high']
    if re.search(r'\bo[134](?:-|$)|\bo3(?:-|$)|\bo4(?:-|$)', model):
        return ['', 'low', 'medium', 'high']

    if supports_reasoning is True:
        return ['', 'none', 'minimal', 'low', 'medium', 'high', 'xhigh']

    return ['']


def _reasoning_options_for_model(model: dict[str, str], global_options: list[dict[str, str]]) -> list[dict[str, str]]:
    supported = model.get('supports_reasoning')
    supports_reasoning = None if supported is None else str(supported).lower() in {'1', 'true', 'yes'}
    values = _reasoning_option_values_for_model(model.get('value') or '', supports_reasoning)
    by_value = {str(option.get('value') or ''): option for option in global_options}

    return _dedupe_options(
        [
            {
                'value': value,
                'label': by_value.get(value, {}).get('label') or _label_from_value(value),
                **(
                    {'description': by_value[value]['description']}
                    if value in by_value and by_value[value].get('description')
                    else {}
                ),
            }
            for value in values
        ]
    )


def _hermes_catalog_model_options(catalog: dict[str, Any]) -> list[dict[str, str]]:
    models = catalog.get('models') if isinstance(catalog, dict) else None
    if not isinstance(models, list):
        return []

    provider = str(catalog.get('provider') or '').strip() if isinstance(catalog, dict) else ''
    result = []
    for model in models:
        if isinstance(model, dict):
            value = str(model.get('id') or model.get('value') or '').strip()
            label = str(model.get('label') or value).strip()
            source = str(model.get('source') or '').strip()
            supports_reasoning = model.get('supports_reasoning')
        else:
            value = str(model or '').strip()
            label = value
            source = ''
            supports_reasoning = None
        if not value:
            continue
        result.append(
            {
                'value': value,
                'label': label or value,
                'description': source or (f'{provider} model' if provider else 'Hermes model'),
                **({'supports_reasoning': str(bool(supports_reasoning)).lower()} if supports_reasoning is not None else {}),
            }
        )
    return result


def _compat_model_options(models_payload: dict[str, Any] | list[Any]) -> list[dict[str, str]]:
    result = []
    for model in (models_payload.get('data') if isinstance(models_payload, dict) else []) or []:
        if not isinstance(model, dict) or not model.get('id'):
            continue
        model_id = str(model['id'])
        result.append(
            {
                'value': model_id,
                'label': str(model.get('name') or model_id),
                'description': str(model.get('owned_by') or 'Hermes compatibility model'),
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
    dashboard_base = _dashboard_base_url(request)
    dashboard_headers = _dashboard_headers(dashboard_base)

    async def safe(name: str, coro):
        try:
            return name, await coro
        except Exception as exc:
            return name, {'available': False, 'error': str(exc)}

    results = dict(
        await asyncio.gather(
            safe('health', _fetch_json(f'{api_base}/health')),
            safe('models', _fetch_json(f'{api_base}/v1/models', headers=_api_auth_headers(request))),
            safe('dashboard_status', _fetch_json(f'{dashboard_base}/api/status', headers=dashboard_headers)),
            safe('model_info', _fetch_json(f'{dashboard_base}/api/model/info', headers=dashboard_headers)),
            safe('sessions', _fetch_json(f'{dashboard_base}/api/sessions?limit=20', headers=dashboard_headers)),
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
    dashboard_base = _dashboard_base_url(request)
    dashboard_headers = _dashboard_headers(dashboard_base)

    async def safe(coro, default):
        try:
            return await coro
        except Exception:
            return default

    api_headers = _api_auth_headers(request)
    models_payload, catalog, model_info, config, schema = await asyncio.gather(
        safe(_fetch_json(f'{api_base}/v1/models', headers=api_headers), {}),
        safe(_fetch_json(f'{dashboard_base}/api/models/available', headers=dashboard_headers), {}),
        safe(_fetch_json(f'{dashboard_base}/api/model/info', headers=dashboard_headers), {}),
        safe(_fetch_json(f'{dashboard_base}/api/config', headers=dashboard_headers), {}),
        safe(_fetch_json(f'{dashboard_base}/api/config/schema', headers=dashboard_headers), {}),
    )

    model_options = _hermes_catalog_model_options(catalog) or _compat_model_options(models_payload)

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

    model_options = _dedupe_options(model_options)
    reasoning_options = _dedupe_options(reasoning_options)
    fast_options = _dedupe_options(fast_options)
    reasoning_options_by_model = {
        model['value']: _reasoning_options_for_model(model, reasoning_options)
        for model in model_options
        if model.get('value')
    }

    current_reasoning = _config_value(config, 'agent.reasoning_effort') if isinstance(config, dict) else ''
    current_fast = _config_value(config, 'agent.service_tier') if isinstance(config, dict) else ''
    current_fast = 'fast' if current_fast in {'fast', 'priority', 'on'} else 'normal'

    current = {
        'model': configured_model or (model_options[0]['value'] if model_options else ''),
        'reasoning': current_reasoning or (reasoning_options_by_model.get(configured_model or '', reasoning_options)[0]['value'] if (reasoning_options_by_model.get(configured_model or '', reasoning_options)) else ''),
        'fast': current_fast or (fast_options[0]['value'] if fast_options else ''),
    }
    current_model_reasoning = reasoning_options_by_model.get(current['model']) or reasoning_options
    if current_model_reasoning and current['reasoning'] not in {option['value'] for option in current_model_reasoning}:
        current['reasoning'] = current_model_reasoning[0]['value']

    config_options = [
        {
            'id': 'model',
            'name': 'Model',
            'category': 'model',
            'type': 'select',
            'currentValue': current['model'],
            'options': [
                {'value': option['value'], 'name': option['label'], 'description': option.get('description', '')}
                for option in model_options
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
                for option in current_model_reasoning
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
                for option in fast_options
            ],
        },
    ]

    return {
        'current': current,
        'model_options': model_options,
        'reasoning_options': current_model_reasoning,
        'reasoning_options_by_model': reasoning_options_by_model,
        'fast_options': fast_options,
        'config_options': config_options,
        'sources': {
            'models': f'{dashboard_base}/api/models/available',
            'compat_models': f'{api_base}/v1/models',
            'model_info': f'{dashboard_base}/api/model/info',
            'config': f'{dashboard_base}/api/config',
            'schema': f'{dashboard_base}/api/config/schema',
        },
    }
