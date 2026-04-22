from open_webui.utils.headers import (
    include_session_info_headers,
    should_forward_session_info_headers,
)


class TestSessionInfoHeaders:
    def test_should_forward_for_local_agent_hosts(self):
        assert should_forward_session_info_headers('http://127.0.0.1:8642/v1') is True
        assert should_forward_session_info_headers('http://host.docker.internal:8642/v1') is True
        assert should_forward_session_info_headers('http://192.168.1.20:11434') is True

    def test_should_not_forward_for_public_hosts_by_default(self):
        assert should_forward_session_info_headers('https://api.openai.com/v1') is False
        assert should_forward_session_info_headers('https://openrouter.ai/api/v1') is False

    def test_explicit_config_can_force_forwarding(self):
        assert should_forward_session_info_headers(
            'https://api.openai.com/v1',
            config={'forward_session_info': True},
        ) is True

    def test_include_session_info_headers_adds_chat_and_message_ids(self):
        headers = include_session_info_headers(
            {'Authorization': 'Bearer test'},
            {'chat_id': 'chat-123', 'message_id': 'msg-456'},
            url='http://127.0.0.1:8642/v1',
        )
        assert headers['X-OpenWebUI-Chat-Id'] == 'chat-123'
        assert headers['X-OpenWebUI-Message-Id'] == 'msg-456'

    def test_include_session_info_headers_skips_public_hosts_without_opt_in(self):
        headers = include_session_info_headers(
            {'Authorization': 'Bearer test'},
            {'chat_id': 'chat-123', 'message_id': 'msg-456'},
            url='https://api.openai.com/v1',
        )
        assert 'X-OpenWebUI-Chat-Id' not in headers
        assert 'X-OpenWebUI-Message-Id' not in headers
