from unittest.mock import AsyncMock

import pytest

from open_webui.utils.middleware import flush_pending_stream_delta_data
from open_webui.utils.misc import inject_image_file_parts, should_emit_stream_content_snapshot


def test_should_emit_stream_content_snapshot_for_realtime_save():
	assert (
		should_emit_stream_content_snapshot(
			enable_realtime_chat_save=True,
			has_reasoning_content=False,
			detect_reasoning_tags=False,
			detect_code_interpreter=False,
			inside_tag_block=False,
		)
		is True
	)


def test_should_emit_stream_content_snapshot_for_reasoning_or_tag_blocks():
	assert (
		should_emit_stream_content_snapshot(
			enable_realtime_chat_save=False,
			has_reasoning_content=True,
			detect_reasoning_tags=False,
			detect_code_interpreter=False,
			inside_tag_block=False,
		)
		is True
	)
	assert (
		should_emit_stream_content_snapshot(
			enable_realtime_chat_save=False,
			has_reasoning_content=False,
			detect_reasoning_tags=False,
			detect_code_interpreter=False,
			inside_tag_block=True,
		)
		is True
	)


def test_should_emit_stream_content_snapshot_for_tag_detection_modes():
	assert (
		should_emit_stream_content_snapshot(
			enable_realtime_chat_save=False,
			has_reasoning_content=False,
			detect_reasoning_tags=True,
			detect_code_interpreter=False,
			inside_tag_block=False,
		)
		is True
	)
	assert (
		should_emit_stream_content_snapshot(
			enable_realtime_chat_save=False,
			has_reasoning_content=False,
			detect_reasoning_tags=False,
			detect_code_interpreter=True,
			inside_tag_block=False,
		)
		is True
	)


def test_should_emit_stream_content_snapshot_for_plain_text_streaming():
	assert (
		should_emit_stream_content_snapshot(
			enable_realtime_chat_save=False,
			has_reasoning_content=False,
			detect_reasoning_tags=False,
			detect_code_interpreter=False,
			inside_tag_block=False,
		)
		is False
	)


def test_inject_image_file_parts_converts_uploaded_image_files_to_image_url_content():
	messages = [
		{
			'role': 'user',
			'content': 'what is in this image?',
			'files': [
				{
					'type': 'file',
					'url': 'abc123',
					'content_type': 'image/png',
				}
			],
		}
	]

	result = inject_image_file_parts(messages)

	assert result == [
		{
			'role': 'user',
			'content': [
				{'type': 'text', 'text': 'what is in this image?'},
				{'type': 'image_url', 'image_url': {'url': 'abc123'}},
			],
		}
	]


@pytest.mark.asyncio
async def test_flush_pending_stream_delta_data_coalesces_saves_at_flush_threshold():
	event_emitter = AsyncMock()
	save_pending = AsyncMock()

	delta_count, last_delta_data = await flush_pending_stream_delta_data(
		event_emitter=event_emitter,
		delta_count=2,
		last_delta_data={'content': 'chunk-2'},
		threshold=2,
		save_pending=save_pending,
	)

	save_pending.assert_awaited_once()
	event_emitter.assert_awaited_once_with({'type': 'chat:completion', 'data': {'content': 'chunk-2'}})
	assert delta_count == 0
	assert last_delta_data is None


@pytest.mark.asyncio
async def test_flush_pending_stream_delta_data_skips_below_threshold():
	event_emitter = AsyncMock()
	save_pending = AsyncMock()

	delta_count, last_delta_data = await flush_pending_stream_delta_data(
		event_emitter=event_emitter,
		delta_count=1,
		last_delta_data={'content': 'chunk-1'},
		threshold=2,
		save_pending=save_pending,
	)

	save_pending.assert_not_awaited()
	event_emitter.assert_not_awaited()
	assert delta_count == 1
	assert last_delta_data == {'content': 'chunk-1'}
