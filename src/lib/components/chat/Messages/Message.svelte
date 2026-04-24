<script lang="ts">
	import { tick, getContext, onMount, createEventDispatcher } from 'svelte';
	import { settings } from '$lib/stores';

	import MultiResponseMessages from './MultiResponseMessages.svelte';
	import ResponseMessage from './ResponseMessage.svelte';
	import UserMessage from './UserMessage.svelte';

	const dispatch = createEventDispatcher();
	const i18n = getContext('i18n');

	export let chatId;
	export let selectedModels = [];
	export let visibilityMode = 'compact';
	export let idx = 0;

	export let history;
	export let messageId;
	export let rootMessageIds = [];

	export let user;

	export let setInputText: Function = () => {};
	export let gotoMessage;
	export let showPreviousMessage;
	export let showNextMessage;
	export let updateChat;

	export let editMessage;
	export let saveMessage;
	export let deleteMessage;
	export let rateMessage;
	export let actionMessage;
	export let submitMessage;

	export let regenerateResponse;
	export let continueResponse;
	export let mergeResponses;

	export let addMessages;
	export let triggerScroll;
	export let readOnly = false;
	export let editCodeBlock = true;
	export let topPadding = false;

	let itemElement: HTMLDivElement | null = null;
	let resizeObserver: ResizeObserver | null = null;
	let heightRAF: number | null = null;
	let message;
	let parentMessage;

	$: message = history?.messages?.[messageId];
	$: parentMessage = message?.parentId !== null ? history?.messages?.[message.parentId] : null;

	const reportHeight = () => {
		if (!itemElement || !messageId) return;

		dispatch('heightchange', {
			messageId,
			height: Math.ceil(itemElement.getBoundingClientRect().height)
		});
	};

	const scheduleReportHeight = () => {
		if (heightRAF !== null) {
			return;
		}

		heightRAF = requestAnimationFrame(() => {
			heightRAF = null;
			reportHeight();
		});
	};

	onMount(() => {
		if (!itemElement) {
			return;
		}

		if (typeof ResizeObserver === 'undefined') {
			void tick().then(scheduleReportHeight);
			return;
		}

		resizeObserver = new ResizeObserver(() => {
			scheduleReportHeight();
		});
		resizeObserver.observe(itemElement);
		scheduleReportHeight();

		return () => {
			resizeObserver?.disconnect();
			if (heightRAF !== null) {
				cancelAnimationFrame(heightRAF);
			}
		};
	});
</script>

<div
	bind:this={itemElement}
	role="listitem"
	class="flex flex-col justify-between px-5 mb-3 w-full {($settings?.widescreenMode ?? null)
		? 'max-w-full'
		: 'max-w-5xl'} mx-auto rounded-lg group"
>
	{#if message}
		{#if message.role === 'user'}
			<UserMessage
				{user}
				{chatId}
				{history}
				{messageId}
				isFirstMessage={idx === 0}
				siblings={message.parentId !== null ? (parentMessage?.childrenIds ?? []) : rootMessageIds}
				{gotoMessage}
				{showPreviousMessage}
				{showNextMessage}
				{editMessage}
				{deleteMessage}
				{readOnly}
				{editCodeBlock}
				{topPadding}
			/>
		{:else if (parentMessage?.models?.length ?? 1) === 1}
			<ResponseMessage
				{chatId}
				{history}
				{messageId}
				{selectedModels}
				{visibilityMode}
				isLastMessage={messageId === history.currentId}
				siblings={parentMessage?.childrenIds ?? []}
				{setInputText}
				{gotoMessage}
				{showPreviousMessage}
				{showNextMessage}
				{updateChat}
				{editMessage}
				{saveMessage}
				{rateMessage}
				{actionMessage}
				{submitMessage}
				{deleteMessage}
				{continueResponse}
				{regenerateResponse}
				{addMessages}
				{readOnly}
				{editCodeBlock}
				{topPadding}
			/>
		{:else}
			{#key messageId}
				<MultiResponseMessages
					bind:history
					{chatId}
					{messageId}
					{selectedModels}
					{visibilityMode}
					isLastMessage={messageId === history?.currentId}
					{setInputText}
					{updateChat}
					{editMessage}
					{saveMessage}
					{rateMessage}
					{actionMessage}
					{submitMessage}
					{deleteMessage}
					{continueResponse}
					{regenerateResponse}
					{mergeResponses}
					{triggerScroll}
					{addMessages}
					{readOnly}
					{editCodeBlock}
					{topPadding}
				/>
			{/key}
		{/if}
	{/if}
</div>
