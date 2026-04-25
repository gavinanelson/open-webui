from open_webui.utils.middleware import _fallback_chat_title


def test_fallback_chat_title_uses_first_message_text():
    assert (
        _fallback_chat_title(
            [
                {
                    'role': 'user',
                    'content': '  Help me plan a small workshop agenda  ',
                }
            ]
        )
        == 'Help me plan a small workshop agenda'
    )


def test_fallback_chat_title_handles_multimodal_content():
    assert (
        _fallback_chat_title(
            [
                {
                    'role': 'user',
                    'content': [
                        {'type': 'text', 'text': 'Name this UI screenshot'},
                        {'type': 'image_url', 'image_url': {'url': 'https://example.test/image.png'}},
                    ],
                }
            ]
        )
        == 'Name this UI screenshot'
    )


def test_fallback_chat_title_uses_user_message_when_messages_empty():
    assert _fallback_chat_title([], 'Explain async database sessions') == 'Explain async database sessions'


def test_fallback_chat_title_truncates_long_prompts():
    title = _fallback_chat_title([{'content': 'x' * 120}])

    assert len(title) == 80
    assert title.endswith('...')
