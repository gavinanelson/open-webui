import { describe, expect, it } from 'vitest';

import {
	buildRootMessageIds,
	buildVirtualizationLayout,
	computeVisibleRange,
	collectRootMessageIds,
	reconcileMessageHeights,
	resolveBranchTargetId,
	shouldRunInitialChatScroll,
	updateMessageHeight
} from './virtualization';

describe('computeVisibleRange', () => {
	it('computes visible bounds and spacer heights with overscan', () => {
		const layout = buildVirtualizationLayout({
			messageIds: ['a', 'b', 'c', 'd'],
			heightOf: () => 100,
			hasMeasured: () => true
		});

		const result = computeVisibleRange({
			layout,
			scrollTop: 150,
			clientHeight: 150,
			overscan: 1
		});

		expect(result).toEqual({
			visibleStart: 0,
			visibleEnd: 4,
			topSpacerHeight: 0,
			bottomSpacerHeight: 0
		});
	});

	it('caps culling at the first unmeasured message', () => {
		const layout = buildVirtualizationLayout({
			messageIds: ['a', 'b', 'c', 'd'],
			heightOf: () => 100,
			hasMeasured: (id) => id === 'a' || id === 'b'
		});

		const result = computeVisibleRange({
			layout,
			scrollTop: 250,
			clientHeight: 100,
			overscan: 1
		});

		expect(result.visibleStart).toBe(1);
		expect(result.visibleEnd).toBe(4);
		expect(result.topSpacerHeight).toBe(100);
		expect(result.bottomSpacerHeight).toBe(0);
	});

	it('handles viewports near the bottom of the list', () => {
		const layout = buildVirtualizationLayout({
			messageIds: ['a', 'b', 'c'],
			heightOf: () => 120,
			hasMeasured: () => true
		});

		const result = computeVisibleRange({
			layout,
			scrollTop: 400,
			clientHeight: 100,
			overscan: 1
		});

		expect(result).toEqual({
			visibleStart: 2,
			visibleEnd: 3,
			topSpacerHeight: 240,
			bottomSpacerHeight: 0
		});
	});

	it('returns the full list when culling is disabled', () => {
		const layout = buildVirtualizationLayout({
			messageIds: ['a', 'b', 'c'],
			heightOf: () => 100,
			hasMeasured: () => false
		});

		const result = computeVisibleRange({
			layout,
			scrollTop: 100,
			clientHeight: 100,
			overscan: 1,
			forceFullRender: true
		});

		expect(result).toEqual({
			visibleStart: 0,
			visibleEnd: 3,
			topSpacerHeight: 0,
			bottomSpacerHeight: 0
		});
	});

	it('builds prefix sums and tracks the first unmeasured index', () => {
		const layout = buildVirtualizationLayout({
			messageIds: ['a', 'b', 'c', 'd'],
			heightOf: (id) => (id === 'c' ? 180 : 100),
			hasMeasured: (id) => id === 'a' || id === 'b'
		});

		expect(layout.firstUnmeasuredIndex).toBe(2);
		expect(layout.prefixSums).toEqual([0, 100, 200, 380, 480]);
	});

	it('seeds default heights for new rows while pruning removed rows', () => {
		const reconciled = reconcileMessageHeights({
			messageIds: ['b', 'c', 'd'],
			existingHeights: new Map([
				['a', 90],
				['b', 120]
			]),
			defaultHeight: 150
		});

		expect(Array.from(reconciled.entries())).toEqual([
			['b', 120],
			['c', 150],
			['d', 150]
		]);
	});

	it('collects root message ids in insertion order', () => {
		const rootIds = collectRootMessageIds({
			b: { id: 'b', parentId: 'a' },
			a: { id: 'a', parentId: null },
			d: { id: 'd', parentId: null },
			c: { id: 'c', parentId: 'b' }
		});

		expect(rootIds).toEqual(['a', 'd']);
		expect(
			buildRootMessageIds({
				b: { id: 'b', parentId: 'a' },
				a: { id: 'a', parentId: null },
				d: { id: 'd', parentId: null },
				c: { id: 'c', parentId: 'b' }
			})
		).toEqual(['a', 'd']);
	});

	it('updates one message height without rebuilding unchanged maps', () => {
		const initialHeights = new Map([
			['a', 120],
			['b', 150]
		]);

		expect(updateMessageHeight(initialHeights, 'a', 120)).toBe(initialHeights);

		const updatedHeights = updateMessageHeight(initialHeights, 'b', 180);
		expect(updatedHeights).not.toBe(initialHeights);
		expect(Array.from(updatedHeights.entries())).toEqual([
			['a', 120],
			['b', 180]
		]);
	});

	it('requests an initial bottom scroll once per chat with messages', () => {
		expect(
			shouldRunInitialChatScroll({
				chatId: 'chat-a',
				currentId: 'message-a',
				lastScrolledChatId: null
			})
		).toBe(true);

		expect(
			shouldRunInitialChatScroll({
				chatId: 'chat-a',
				currentId: 'message-a',
				lastScrolledChatId: 'chat-a'
			})
		).toBe(false);

		expect(
			shouldRunInitialChatScroll({
				chatId: 'chat-b',
				currentId: null,
				lastScrolledChatId: 'chat-a'
			})
		).toBe(false);
	});
});

describe('resolveBranchTargetId', () => {
	const historyMessages = {
		a: { id: 'a', parentId: null, childrenIds: ['b', 'c'] },
		b: { id: 'b', parentId: 'a', childrenIds: ['d'] },
		c: { id: 'c', parentId: 'a', childrenIds: [] },
		d: { id: 'd', parentId: 'b', childrenIds: [] },
		e: { id: 'e', parentId: null, childrenIds: [] }
	};

	it('follows root siblings and descends to the branch tail', () => {
		const rootMessageIds = buildRootMessageIds(historyMessages);

		expect(resolveBranchTargetId(historyMessages.a, 1, historyMessages, rootMessageIds)).toBe('e');
		expect(resolveBranchTargetId(historyMessages.b, 0, historyMessages, rootMessageIds)).toBe('d');
		expect(resolveBranchTargetId(historyMessages.b, 1, historyMessages, rootMessageIds)).toBe('c');
	});
});
