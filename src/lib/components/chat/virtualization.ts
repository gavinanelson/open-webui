type MessageNode = {
	id: string;
	parentId: string | null;
	childrenIds?: string[];
};

type MessageMap = Record<string, MessageNode>;

export type VirtualizationLayout = {
	messageIds: string[];
	prefixSums: number[];
	firstUnmeasuredIndex: number;
};

export const buildRootMessageIds = (messagesMap: MessageMap | null | undefined): string[] => {
	if (!messagesMap) {
		return [];
	}

	return Object.values(messagesMap)
		.filter((message) => message.parentId === null)
		.map((message) => message.id);
};

export const collectRootMessageIds = buildRootMessageIds;

export const reconcileMessageHeights = ({
	messageIds,
	existingHeights,
	defaultHeight
}: {
	messageIds: string[];
	existingHeights: Map<string, number>;
	defaultHeight: number;
}): Map<string, number> => {
	const nextHeights = new Map<string, number>();

	for (const messageId of messageIds) {
		nextHeights.set(messageId, existingHeights.get(messageId) ?? defaultHeight);
	}

	return nextHeights;
};

export const updateMessageHeight = (
	existingHeights: Map<string, number>,
	messageId: string,
	height: number
): Map<string, number> => {
	if (existingHeights.get(messageId) === height) {
		return existingHeights;
	}

	const nextHeights = new Map(existingHeights);
	nextHeights.set(messageId, height);
	return nextHeights;
};

export const shouldRunInitialChatScroll = ({
	chatId,
	currentId,
	lastScrolledChatId
}: {
	chatId: string | null | undefined;
	currentId: string | null | undefined;
	lastScrolledChatId: string | null | undefined;
}) => Boolean(chatId && currentId && chatId !== lastScrolledChatId);

type BuildVirtualizationLayoutParams = {
	messageIds: string[];
	heightOf: (id: string) => number;
	hasMeasured: (id: string) => boolean;
};

type ComputeVisibleRangeParams = {
	layout: VirtualizationLayout;
	scrollTop: number;
	clientHeight: number;
	overscan: number;
	forceFullRender?: boolean;
};

export type VisibleRange = {
	visibleStart: number;
	visibleEnd: number;
	topSpacerHeight: number;
	bottomSpacerHeight: number;
};

export const buildVirtualizationLayout = ({
	messageIds,
	heightOf,
	hasMeasured
}: BuildVirtualizationLayoutParams): VirtualizationLayout => {
	const messageCount = messageIds.length;
	const prefixSums = new Array<number>(messageCount + 1);
	prefixSums[0] = 0;
	let firstUnmeasuredIndex = messageCount;

	for (let index = 0; index < messageCount; index += 1) {
		if (firstUnmeasuredIndex === messageCount && !hasMeasured(messageIds[index])) {
			firstUnmeasuredIndex = index;
		}

		prefixSums[index + 1] = prefixSums[index] + heightOf(messageIds[index]);
	}

	return {
		messageIds,
		prefixSums,
		firstUnmeasuredIndex
	};
};

const lowerBound = (values: number[], target: number, start = 0, end = values.length): number => {
	let low = start;
	let high = end;

	while (low < high) {
		const mid = Math.floor((low + high) / 2);
		if (values[mid] < target) {
			low = mid + 1;
		} else {
			high = mid;
		}
	}

	return low;
};

export const computeVisibleRange = ({
	layout,
	scrollTop,
	clientHeight,
	overscan,
	forceFullRender = false
}: ComputeVisibleRangeParams): VisibleRange => {
	const { messageIds, prefixSums, firstUnmeasuredIndex } = layout;
	const messageCount = messageIds.length;

	if (messageCount === 0) {
		return {
			visibleStart: 0,
			visibleEnd: 0,
			topSpacerHeight: 0,
			bottomSpacerHeight: 0
		};
	}

	if (forceFullRender) {
		return {
			visibleStart: 0,
			visibleEnd: messageCount,
			topSpacerHeight: 0,
			bottomSpacerHeight: 0
		};
	}

	let firstVisible = 0;
	if (scrollTop > 0) {
		firstVisible = Math.max(
			0,
			Math.min(messageCount, lowerBound(prefixSums, scrollTop + 1, 1, messageCount + 1) - 1)
		);
	}

	const viewportBottom = scrollTop + clientHeight;
	const lastVisibleExclusive =
		firstVisible >= messageCount
			? messageCount
			: Math.min(
					messageCount,
					Math.max(
						firstVisible + 1,
						lowerBound(prefixSums, viewportBottom, firstVisible + 1, messageCount + 1)
					)
				);

	const visibleStart = Math.max(0, Math.min(firstVisible - overscan, firstUnmeasuredIndex));
	const visibleEnd = Math.min(
		messageCount,
		Math.max(visibleStart + 1, lastVisibleExclusive + overscan)
	);

	return {
		visibleStart,
		visibleEnd,
		topSpacerHeight: prefixSums[visibleStart] ?? 0,
		bottomSpacerHeight: (prefixSums[messageCount] ?? 0) - (prefixSums[visibleEnd] ?? 0)
	};
};

const getDeepestLeafMessageId = (messages: MessageMap, messageId: string) => {
	let currentMessageId = messageId;
	let childMessageIds = messages[currentMessageId]?.childrenIds ?? [];

	while (childMessageIds.length !== 0) {
		currentMessageId = childMessageIds.at(-1) ?? currentMessageId;
		childMessageIds = messages[currentMessageId]?.childrenIds ?? [];
	}

	return currentMessageId;
};

const getSiblingMessageIds = (
	message: MessageNode,
	messages: MessageMap,
	rootMessageIds: string[]
) => {
	if (message.parentId !== null) {
		return messages[message.parentId]?.childrenIds ?? [];
	}

	return rootMessageIds;
};

export const resolveBranchTargetId = (
	message: MessageNode,
	idx: number,
	messages: MessageMap,
	rootMessageIds: string[]
) => {
	const siblingMessageIds = getSiblingMessageIds(message, messages, rootMessageIds);

	if (siblingMessageIds.length === 0) {
		return message.id;
	}

	const targetIndex = Math.max(0, Math.min(idx, siblingMessageIds.length - 1));
	const targetMessageId = siblingMessageIds[targetIndex];

	return getDeepestLeafMessageId(messages, targetMessageId);
};
