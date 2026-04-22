from ipaddress import ip_address
from urllib.parse import quote, urlparse

from open_webui.env import (
    FORWARD_SESSION_INFO_HEADER_CHAT_ID,
    FORWARD_SESSION_INFO_HEADER_MESSAGE_ID,
    FORWARD_USER_INFO_HEADER_USER_NAME,
    FORWARD_USER_INFO_HEADER_USER_ID,
    FORWARD_USER_INFO_HEADER_USER_EMAIL,
    FORWARD_USER_INFO_HEADER_USER_ROLE,
)


def include_user_info_headers(headers, user):
    return {
        **headers,
        FORWARD_USER_INFO_HEADER_USER_NAME: quote(user.name, safe=' '),
        FORWARD_USER_INFO_HEADER_USER_ID: user.id,
        FORWARD_USER_INFO_HEADER_USER_EMAIL: user.email,
        FORWARD_USER_INFO_HEADER_USER_ROLE: user.role,
    }


def should_forward_session_info_headers(url, config=None):
    if isinstance(config, dict) and config.get('forward_session_info') is not None:
        return bool(config.get('forward_session_info'))

    host = (urlparse(url).hostname or '').strip().lower()
    if not host:
        return False

    if host in {'localhost', 'host.docker.internal'}:
        return True

    try:
        addr = ip_address(host)
    except ValueError:
        return False

    return addr.is_loopback or addr.is_private or addr.is_link_local


def include_session_info_headers(headers, metadata=None, *, url=None, config=None):
    if not metadata or not url or not should_forward_session_info_headers(url, config=config):
        return headers

    out = dict(headers)

    chat_id = metadata.get('chat_id')
    if chat_id:
        out[FORWARD_SESSION_INFO_HEADER_CHAT_ID] = str(chat_id)

    message_id = metadata.get('message_id')
    if message_id:
        out[FORWARD_SESSION_INFO_HEADER_MESSAGE_ID] = str(message_id)

    return out
