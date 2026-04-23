<script>
	import { getContext, onDestroy, onMount } from 'svelte';
	const i18n = getContext('i18n');

	import StatusItem from './StatusHistory/StatusItem.svelte';
	import Dropdown from '$lib/components/common/Dropdown.svelte';
	import equal from 'fast-deep-equal';

	export let statusHistory = [];
	export let expand = false;
	export let visibilityMode = 'compact';

	const VIEW_MODES = ['compact', 'medium', 'detailed'];
	const VIEW_LABELS = {
		compact: 'Compact',
		medium: 'Steps',
		detailed: 'Trace'
	};

	let showHistory = true;
	let viewMode = visibilityMode;
	let now = Date.now();
	let timer = null;
	let history = [];
	let status = null;

	const clampMode = (mode) => (VIEW_MODES.includes(mode) ? mode : 'compact');

	const loadViewMode = () => {
		try {
			return clampMode(localStorage.getItem('chat-status-view-mode') ?? visibilityMode);
		} catch {
			return clampMode(visibilityMode);
		}
	};

	const setViewMode = (mode) => {
		viewMode = clampMode(mode);
		showHistory = viewMode !== 'compact';
		try {
			localStorage.setItem('chat-status-view-mode', viewMode);
		} catch {}
	};

	const formatElapsed = (seconds) => {
		if (!Number.isFinite(seconds) || seconds < 0) return '0s';
		const total = Math.floor(seconds);
		const minutes = Math.floor(total / 60);
		const remaining = total % 60;
		return minutes > 0 ? `${minutes}m ${remaining}s` : `${remaining}s`;
	};

	const timestampOf = (entry) => {
		const value = entry?.received_at ?? entry?.started_at ?? entry?.created_at ?? entry?.timestamp;
		if (typeof value !== 'number') return null;
		return value > 1000000000000 ? value : value * 1000;
	};

	const isDone = (entry) => entry?.done === true || entry?.status === 'completed';
	const isActive = (entry) => entry && !isDone(entry);
	const statusLabel = (entry) => {
		const event = entry?.event ?? '';
		if (event.includes('reasoning')) return 'Reasoning';
		if (event.includes('tool')) return 'Tool';
		if (entry?.source) return entry.source;
		return 'Hermes';
	};
	const detailEntries = (entry) =>
		Object.entries(entry ?? {}).filter(
			([key, value]) =>
				!['description', 'done', 'hidden'].includes(key) &&
				value !== undefined &&
				value !== null &&
				value !== ''
		);
	const formatDetailValue = (value) => {
		if (typeof value === 'string') return value;
		try {
			return JSON.stringify(value, null, 2);
		} catch {
			return String(value);
		}
	};

	$: if (history && history.length > 0) {
		status = history.at(-1);
	}

	$: if (!equal(statusHistory ?? [], history)) {
		history = statusHistory ?? [];
	}

	$: active = history.some(isActive);
	$: startedAt = history.map(timestampOf).find(Boolean) ?? timestampOf(status) ?? now;
	$: elapsed = formatElapsed((now - startedAt) / 1000);
	$: stageCount = new Set(history.map((entry) => entry?.action).filter(Boolean)).size;
	$: panelHistory = viewMode === 'detailed' ? history : history.slice(-5);
	$: selectedViewLabel = VIEW_LABELS[viewMode] ?? VIEW_LABELS.compact;
	$: if (expand && viewMode === 'compact') {
		setViewMode('medium');
	}

	onMount(() => {
		setViewMode(loadViewMode());
		timer = setInterval(() => {
			if (active) {
				now = Date.now();
			}
		}, 1000);
	});

	onDestroy(() => {
		if (timer) {
			clearInterval(timer);
		}
	});
</script>

{#if history && history.length > 0 && status?.hidden !== true}
	<div class="status-description w-full text-left text-sm">
		<div class="grid grid-cols-[10px_minmax(0,1fr)] gap-2">
			<div class="pt-2">
				<div
					class="size-2 rounded-full {active
						? 'animate-pulse bg-emerald-500'
						: 'bg-gray-400 dark:bg-gray-600'}"
				></div>
				{#if viewMode !== 'compact'}
					<div class="mx-auto mt-1 h-full min-h-8 w-px bg-gray-200 dark:bg-gray-800"></div>
				{/if}
			</div>

			<div class="min-w-0">
				<div class="flex min-w-0 flex-col gap-1">
					<button
						class="min-w-0 flex-1 text-left"
						aria-label={$i18n.t('Toggle status history')}
						aria-expanded={showHistory}
						on:click={() => {
							if (viewMode === 'compact') {
								setViewMode('medium');
							} else {
								showHistory = !showHistory;
							}
						}}
					>
						<StatusItem {status} compact={viewMode === 'compact'} />
					</button>

					<div
						class="flex min-w-0 flex-wrap items-center gap-1 text-[11px] text-gray-500 dark:text-gray-500"
					>
						<span class="whitespace-nowrap">{active ? 'Working' : 'Done'}</span>
						<span class="text-gray-300 dark:text-gray-700">/</span>
						<span class="whitespace-nowrap">{elapsed}</span>
						<span class="text-gray-300 dark:text-gray-700">/</span>
						<span class="line-clamp-1">{statusLabel(status)}</span>
						<Dropdown
							side="top"
							align="start"
							contentClass="rounded-lg border border-gray-100 bg-white p-1 shadow-lg dark:border-gray-800 dark:bg-gray-900"
						>
							<button
								type="button"
								class="rounded px-1.5 py-0.5 font-medium text-gray-600 transition hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-gray-850"
							>
								{selectedViewLabel} v
							</button>

							<div slot="content" class="flex flex-col">
								{#each VIEW_MODES as mode}
									<button
										type="button"
										class="rounded px-2 py-1 text-left text-xs transition {viewMode === mode
											? 'bg-gray-900 text-white dark:bg-gray-100 dark:text-gray-900'
											: 'text-gray-600 hover:bg-gray-50 dark:text-gray-300 dark:hover:bg-gray-850'}"
										on:click={() => setViewMode(mode)}
										aria-pressed={viewMode === mode}
									>
										{VIEW_LABELS[mode]}
									</button>
								{/each}
							</div>
						</Dropdown>
					</div>
				</div>

				{#if viewMode !== 'compact'}
					<div class="mt-2 pl-3">
						<div class="mb-2 flex flex-wrap gap-2 text-xs text-gray-500 dark:text-gray-500">
							<span>{history.length} updates</span>
							<span>{stageCount} stages</span>
							<span>{active ? 'Working' : 'Done'}</span>
						</div>

						{#if showHistory}
							<div
								class="space-y-2 overflow-y-auto pr-1 {viewMode === 'detailed'
									? 'max-h-96'
									: 'max-h-44'}"
							>
								{#each panelHistory as entry, entryIndex}
									<div class="grid grid-cols-[12px_minmax(0,1fr)] gap-2">
										<div class="relative pt-2">
											<div
												class="size-1.5 rounded-full {isActive(entry)
													? 'bg-emerald-500'
													: 'bg-gray-400 dark:bg-gray-600'}"
											></div>
											{#if entryIndex < panelHistory.length - 1 || !active}
												<div
													class="absolute left-[3px] top-5 h-[calc(100%+2px)] w-px bg-gray-200 dark:bg-gray-800"
												></div>
											{/if}
										</div>

										<div class="min-w-0">
											<StatusItem status={entry} done={!isActive(entry)} compact={false} />

											{#if viewMode === 'detailed'}
												<div
													class="mt-1 grid gap-1 rounded-md bg-gray-50 p-2 text-[11px] dark:bg-gray-900/60"
												>
													{#each detailEntries(entry) as [key, value]}
														<div class="grid grid-cols-[96px_minmax(0,1fr)] gap-2">
															<div class="font-medium text-gray-500 dark:text-gray-500">{key}</div>
															<pre
																class="whitespace-pre-wrap break-words font-mono text-[11px] leading-4 text-gray-700 dark:text-gray-300">{formatDetailValue(
																	value
																)}</pre>
														</div>
													{/each}
												</div>
											{/if}
										</div>
									</div>
								{/each}
								{#if !active}
									<div class="grid grid-cols-[12px_minmax(0,1fr)] gap-2">
										<div class="pt-1.5">
											<div class="size-1.5 rounded-full bg-gray-300 dark:bg-gray-700"></div>
										</div>
										<div class="text-xs font-medium text-gray-500 dark:text-gray-500">
											Done after {elapsed}
										</div>
									</div>
								{/if}
							</div>
						{/if}
					</div>
				{/if}
			</div>
		</div>
	</div>
{/if}
