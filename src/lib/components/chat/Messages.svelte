<script lang="ts">
	import { v4 as uuidv4 } from 'uuid';
	import {
		chats,
		config,
		settings,
		user as _user,
		mobile,
		currentChatPage,
		temporaryChatEnabled
	} from '$lib/stores';
	import { tick, getContext, onMount, onDestroy, createEventDispatcher } from 'svelte';
	const dispatch = createEventDispatcher();

	import { toast } from 'svelte-sonner';
	import { getChatList, updateChatById } from '$lib/apis/chats';
	import { copyToClipboard, extractCurlyBraceWords } from '$lib/utils';

	import Message from './Messages/Message.svelte';
	import Loader from '../common/Loader.svelte';
	import Spinner from '../common/Spinner.svelte';
	import {
		buildRootMessageIds,
		buildVirtualizationLayout,
		computeVisibleRange,
		reconcileMessageHeights,
		resolveBranchTargetId,
		shouldRunInitialChatScroll,
		updateMessageHeight
	} from './virtualization';

	import ChatPlaceholder from './ChatPlaceholder.svelte';

	const i18n = getContext('i18n');

	export let className = 'h-full flex pt-8';

	export let chatId = '';
	export let user = $_user;

	export let prompt;
	export let history = {};
	export let selectedModels;
	export let atSelectedModel;

	let messages = [];

	export let setInputText: Function = () => {};

	export let sendMessage: Function;
	export let continueResponse: Function;
	export let regenerateResponse: Function;
	export let mergeResponses: Function;

	export let chatActionHandler: Function;
	export let showMessage: Function = () => {};
	export let submitMessage: Function = () => {};
	export let addMessages: Function = () => {};

	export let readOnly = false;
	export let editCodeBlock = true;

	export let topPadding = false;
	export let bottomPadding = false;
	export let autoScroll;

	export let onSelect = (e) => {};

	export let messagesCount: number | null = 8;
	export let visibilityMode = 'compact';
	let messagesLoading = false;
	let rootMessageIds: string[] = [];

	// Off-screen message unloading. Heights are tracked per message, and the
	// visible window is derived from cached layout data instead of scroll-time
	// DOM measurement.
	const OVERSCAN = 6;
	const DEFAULT_HEIGHT = 150;
	let visibleStart = 0;
	let visibleEnd = 0;
	let messageHeights = new Map();
	let topSpacerHeight = 0;
	let bottomSpacerHeight = 0;
	let pendingCull = null;
	let pendingVirtualizationRefresh = null;
	let virtualizationLayout = {
		messageIds: [],
		prefixSums: [0],
		firstUnmeasuredIndex: 0
	};

	const heightOf = (id) => messageHeights.get(id) ?? DEFAULT_HEIGHT;

	const refreshVirtualization = () => {
		virtualizationLayout = buildVirtualizationLayout({
			messageIds: messages.map((message) => message.id),
			heightOf,
			hasMeasured: (id) => messageHeights.has(id)
		});
		updateVisibleRange();
	};

	const scheduleVirtualizationRefresh = () => {
		if (pendingVirtualizationRefresh) return;

		pendingVirtualizationRefresh = requestAnimationFrame(() => {
			pendingVirtualizationRefresh = null;
			refreshVirtualization();
		});
	};

	const updateVisibleRange = () => {
		const container = document.getElementById('messages-container');
		if (!container || messages.length === 0) {
			visibleStart = 0;
			visibleEnd = messages.length;
			topSpacerHeight = 0;
			bottomSpacerHeight = 0;
			return;
		}

		const range = computeVisibleRange({
			layout: virtualizationLayout,
			scrollTop: container.scrollTop,
			clientHeight: container.clientHeight,
			overscan: OVERSCAN
		});

		visibleStart = range.visibleStart;
		visibleEnd = range.visibleEnd;
		topSpacerHeight = range.topSpacerHeight;
		bottomSpacerHeight = range.bottomSpacerHeight;
	};

	const handleContainerScroll = () => {
		if (!pendingCull) {
			pendingCull = requestAnimationFrame(() => {
				pendingCull = null;
				updateVisibleRange();
			});
		}
	};

	let scrollListenerAttached = false;

	const attachScrollListener = () => {
		if (scrollListenerAttached) return;
		const container = document.getElementById('messages-container');
		if (!container) return;

		container.addEventListener('scroll', handleContainerScroll, { passive: true });
		scrollListenerAttached = true;
	};

	onMount(() => {
		attachScrollListener();
		scheduleVirtualizationRefresh();
	});

	onDestroy(() => {
		const container = document.getElementById('messages-container');
		if (container && scrollListenerAttached) {
			container.removeEventListener('scroll', handleContainerScroll);
		}
		cancelAnimationFrame(pendingCull);
		cancelAnimationFrame(pendingRebuild);
		cancelAnimationFrame(pendingVirtualizationRefresh);
	});

	const loadMoreMessages = async () => {
		const element = document.getElementById('messages-container');
		const previousScrollTop = element?.scrollTop ?? 0;
		const previousScrollHeight = element?.scrollHeight ?? 0;

		messagesLoading = true;
		messagesCount += 8;

		buildMessages();
		cancelAnimationFrame(pendingVirtualizationRefresh);
		pendingVirtualizationRefresh = null;

		await tick();
		refreshVirtualization();
		await tick();

		if (element) {
			element.scrollTop = previousScrollTop + (element.scrollHeight - previousScrollHeight);
			updateVisibleRange();
		}

		messagesLoading = false;
	};

	let pendingRebuild = null;
	let lastCurrentId = null;
	let lastRootIdsMessageCount = -1;
	let lastInitialScrollChatId = null;

	const buildMessages = () => {
		let _messages = [];
		const historyMessages = history.messages ?? {};

		let message = historyMessages[history.currentId];
		const visitedMessageIds = new Set();

		while (message && (messagesCount !== null ? _messages.length <= messagesCount : true)) {
			if (visitedMessageIds.has(message.id)) {
				console.warn('Circular dependency detected in message history', message.id);
				break;
			}
			visitedMessageIds.add(message.id);

			_messages.push(message);
			message = message.parentId !== null ? historyMessages[message.parentId] : null;
		}

		messages = _messages.reverse();
		messageHeights = reconcileMessageHeights({
			messageIds: messages.map((entry) => entry.id),
			existingHeights: messageHeights,
			defaultHeight: DEFAULT_HEIGHT
		});
		const historyMessageCount = Object.keys(historyMessages).length;
		if (historyMessageCount !== lastRootIdsMessageCount) {
			rootMessageIds = buildRootMessageIds(historyMessages);
			lastRootIdsMessageCount = historyMessageCount;
		}
		scheduleVirtualizationRefresh();
	};

	// Throttle message list rebuilds to once per animation frame during streaming.
	// Structural changes (currentId change) always rebuild immediately.
	const handleHistoryChange = (currentId, _messages) => {
		if (!currentId) {
			messages = [];
			rootMessageIds = [];
			lastRootIdsMessageCount = 0;
			scheduleVirtualizationRefresh();
			return;
		}

		const currentIdChanged = currentId !== lastCurrentId;
		lastCurrentId = currentId;

		if (currentIdChanged) {
			cancelAnimationFrame(pendingRebuild);
			pendingRebuild = null;
			buildMessages();
		} else if (_messages) {
			if (!pendingRebuild) {
				pendingRebuild = requestAnimationFrame(() => {
					pendingRebuild = null;
					buildMessages();
				});
			}
		}
	};

	$: handleHistoryChange(history.currentId, history.messages);

	const scrollToBottomAfterRender = async () => {
		await tick();
		refreshVirtualization();
		await tick();
		scrollToBottom();
		updateVisibleRange();
		await tick();
		scrollToBottom();
		updateVisibleRange();
	};

	$: if (
		shouldRunInitialChatScroll({
			chatId,
			currentId: history.currentId,
			lastScrolledChatId: lastInitialScrollChatId
		})
	) {
		lastInitialScrollChatId = chatId;
		autoScroll = true;
		scrollToBottomAfterRender();
	}

	$: if (autoScroll && bottomPadding) {
		(async () => {
			await tick();
			scrollToBottom();
		})();
	}

	const scrollToBottom = () => {
		const element = document.getElementById('messages-container');
		element.scrollTop = element.scrollHeight;
	};

	const handleMessageHeightChange = (event) => {
		const { messageId, height } = event.detail ?? {};
		if (!messageId || typeof height !== 'number') {
			return;
		}

		const previousHeight = messageHeights.get(messageId);
		const messageIndex = messages.findIndex((message) => message.id === messageId);
		const heightDelta = previousHeight !== undefined ? height - previousHeight : 0;

		messageHeights = updateMessageHeight(messageHeights, messageId, height);

		if (heightDelta !== 0 && messageIndex !== -1 && messageIndex < visibleStart) {
			const element = document.getElementById('messages-container');
			if (element) {
				element.scrollTop += heightDelta;
			}
		}

		scheduleVirtualizationRefresh();
	};

	const updateChat = async () => {
		if (!$temporaryChatEnabled) {
			history = history;
			await tick();
			await updateChatById(localStorage.token, chatId, {
				history: history,
				messages: messages
			});

			currentChatPage.set(1);
			await chats.set(await getChatList(localStorage.token, $currentChatPage));
		}
	};

	const gotoMessage = async (message: { id: string; parentId: string | null }, idx: number) => {
		const historyMessages = history.messages ?? {};
		const messageId = resolveBranchTargetId(message, idx, historyMessages, rootMessageIds);

		// If we're navigating to a different message
		if (message.id !== messageId) {
			history.currentId = messageId;
		}

		await tick();

		// Optional auto-scroll
		if ($settings?.scrollOnBranchChange ?? true) {
			const element = document.getElementById('messages-container');
			autoScroll = element.scrollHeight - element.scrollTop <= element.clientHeight + 50;

			setTimeout(() => {
				scrollToBottom();
			}, 100);
		}
	};

	const showPreviousMessage = async (message: { id: string; parentId: string | null }) => {
		const historyMessages = history.messages ?? {};
		const messageId = resolveBranchTargetId(
			message,
			message.parentId !== null
				? Math.max(historyMessages[message.parentId].childrenIds.indexOf(message.id) - 1, 0)
				: Math.max(rootMessageIds.indexOf(message.id) - 1, 0),
			historyMessages,
			rootMessageIds
		);

		if (message.id !== messageId) {
			history.currentId = messageId;
		}

		await tick();

		if ($settings?.scrollOnBranchChange ?? true) {
			const element = document.getElementById('messages-container');
			autoScroll = element.scrollHeight - element.scrollTop <= element.clientHeight + 50;

			setTimeout(() => {
				scrollToBottom();
			}, 100);
		}
	};

	const showNextMessage = async (message: { id: string; parentId: string | null }) => {
		const historyMessages = history.messages ?? {};
		const messageId = resolveBranchTargetId(
			message,
			message.parentId !== null
				? Math.min(
						historyMessages[message.parentId].childrenIds.indexOf(message.id) + 1,
						historyMessages[message.parentId].childrenIds.length - 1
					)
				: Math.min(rootMessageIds.indexOf(message.id) + 1, rootMessageIds.length - 1),
			historyMessages,
			rootMessageIds
		);

		if (message.id !== messageId) {
			history.currentId = messageId;
		}

		await tick();

		if ($settings?.scrollOnBranchChange ?? true) {
			const element = document.getElementById('messages-container');
			autoScroll = element.scrollHeight - element.scrollTop <= element.clientHeight + 50;

			setTimeout(() => {
				scrollToBottom();
			}, 100);
		}
	};

	const rateMessage = async (messageId, rating) => {
		history.messages[messageId].annotation = {
			...history.messages[messageId].annotation,
			rating: rating
		};

		await updateChat();
	};

	const editMessage = async (messageId, { content, files }, submit = true) => {
		if ((selectedModels ?? []).filter((id) => id).length === 0) {
			toast.error($i18n.t('Model not selected'));
			return;
		}
		if (history.messages[messageId].role === 'user') {
			if (submit) {
				// New user message
				let userPrompt = content;
				let userMessageId = uuidv4();

				let userMessage = {
					id: userMessageId,
					parentId: history.messages[messageId].parentId,
					childrenIds: [],
					role: 'user',
					content: userPrompt,
					...(files && { files: files }),
					models: selectedModels,
					timestamp: Math.floor(Date.now() / 1000) // Unix epoch
				};

				let messageParentId = history.messages[messageId].parentId;

				if (messageParentId !== null) {
					history.messages[messageParentId].childrenIds = [
						...history.messages[messageParentId].childrenIds,
						userMessageId
					];
				}

				history.messages[userMessageId] = userMessage;
				history.currentId = userMessageId;

				await tick();
				await sendMessage(history, userMessageId);
			} else {
				// Edit user message
				history.messages[messageId].content = content;
				history.messages[messageId].files = files;
				await updateChat();
			}
		} else {
			if (submit) {
				// New response message
				const responseMessageId = uuidv4();
				const message = history.messages[messageId];
				const parentId = message.parentId;

				const responseMessage = {
					...message,
					id: responseMessageId,
					parentId: parentId,
					childrenIds: [],
					files: undefined,
					content: content,
					timestamp: Math.floor(Date.now() / 1000) // Unix epoch
				};

				history.messages[responseMessageId] = responseMessage;
				history.currentId = responseMessageId;

				// Append messageId to childrenIds of parent message
				if (parentId !== null) {
					history.messages[parentId].childrenIds = [
						...history.messages[parentId].childrenIds,
						responseMessageId
					];
				}

				await updateChat();
			} else {
				// Edit response message
				history.messages[messageId].originalContent = history.messages[messageId].content;
				history.messages[messageId].content = content;
				await updateChat();
			}
		}
	};

	const actionMessage = async (actionId, message, event = null) => {
		await chatActionHandler(chatId, actionId, message.model, message.id, event);
	};

	const saveMessage = async (messageId, message) => {
		if (!history.messages?.[messageId]) {
			return;
		}

		history.messages[messageId] = message;
		await updateChat();
	};

	const deleteMessage = async (messageId) => {
		const messageToDelete = history.messages[messageId];
		const parentMessageId = messageToDelete.parentId;
		const childMessageIds = messageToDelete.childrenIds ?? [];

		// Collect all grandchildren
		const grandchildrenIds = childMessageIds.flatMap(
			(childId) => history.messages[childId]?.childrenIds ?? []
		);

		// Update parent's children
		if (parentMessageId && history.messages[parentMessageId]) {
			history.messages[parentMessageId].childrenIds = [
				...history.messages[parentMessageId].childrenIds.filter((id) => id !== messageId),
				...grandchildrenIds
			];
		}

		// Update grandchildren's parent
		grandchildrenIds.forEach((grandchildId) => {
			if (history.messages[grandchildId]) {
				history.messages[grandchildId].parentId = parentMessageId;
			}
		});

		// Delete the message and its children
		[messageId, ...childMessageIds].forEach((id) => {
			delete history.messages[id];
		});

		showMessage({ id: parentMessageId }, false);
	};

	const triggerScroll = () => {
		if (autoScroll) {
			const element = document.getElementById('messages-container');
			autoScroll = element.scrollHeight - element.scrollTop <= element.clientHeight + 50;
			setTimeout(() => {
				scrollToBottom();
			}, 100);
		}
	};
</script>

<div class={className}>
	{#if Object.keys(history?.messages ?? {}).length == 0}
		<ChatPlaceholder modelIds={selectedModels} {atSelectedModel} {onSelect} />
	{:else}
		<div class="w-full pt-2">
			{#key chatId}
				<section class="w-full" aria-labelledby="chat-conversation">
					<h2 class="sr-only" id="chat-conversation">{$i18n.t('Chat Conversation')}</h2>
					{#if messages.at(0)?.parentId !== null}
						<Loader
							on:visible={(e) => {
								console.log('visible');
								if (!messagesLoading) {
									loadMoreMessages();
								}
							}}
						>
							<div class="w-full flex justify-center py-1 text-xs animate-pulse items-center gap-2">
								<Spinner className=" size-4" />
								<div class=" ">{$i18n.t('Loading...')}</div>
							</div>
						</Loader>
					{/if}
					<ul role="log" aria-live="polite" aria-relevant="additions" aria-atomic="false">
						<!-- Top spacer: sum of cached heights for messages above visible range -->
						{#if topSpacerHeight > 0}
							<div style="height: {topSpacerHeight}px" aria-hidden="true" />
						{/if}

						{#each messages.slice(visibleStart, visibleEnd) as message, i (message.id)}
							{@const messageIdx = visibleStart + i}
							<Message
								{chatId}
								bind:history
								{selectedModels}
								{visibilityMode}
								messageId={message.id}
								idx={messageIdx}
								{rootMessageIds}
								{user}
								{setInputText}
								{gotoMessage}
								{showPreviousMessage}
								{showNextMessage}
								{updateChat}
								{editMessage}
								{deleteMessage}
								{rateMessage}
								{actionMessage}
								{saveMessage}
								{submitMessage}
								{regenerateResponse}
								{continueResponse}
								{mergeResponses}
								{addMessages}
								{triggerScroll}
								{readOnly}
								{editCodeBlock}
								{topPadding}
								on:heightchange={handleMessageHeightChange}
							/>
						{/each}

						<!-- Bottom spacer: sum of cached heights for messages below visible range -->
						{#if bottomSpacerHeight > 0}
							<div style="height: {bottomSpacerHeight}px" aria-hidden="true" />
						{/if}
					</ul>
				</section>
				<div class="pb-18" />
				{#if bottomPadding}
					<div class="  pb-6" />
				{/if}
			{/key}
		</div>
	{/if}
</div>
