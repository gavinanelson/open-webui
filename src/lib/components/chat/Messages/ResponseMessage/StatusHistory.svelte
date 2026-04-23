<script>
	import { getContext, onDestroy, onMount } from 'svelte';
	const i18n = getContext('i18n');

	import StatusItem from './StatusHistory/StatusItem.svelte';
	import equal from 'fast-deep-equal';

	export let statusHistory = [];
	export let expand = false;
	export let visibilityMode = 'compact';

	const VIEW_MODES = ['compact', 'medium', 'detailed'];
	const VIEW_LABELS = {
		compact: 'Compact',
		medium: 'Medium',
		detailed: 'Detailed'
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
	$: toolCount = new Set(history.map((entry) => entry?.action).filter(Boolean)).size;
	$: recentHistory = history.slice(-4);
	$: panelHistory = viewMode === 'detailed' ? history : recentHistory;
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
		<div
			class="overflow-hidden rounded-lg border border-gray-100 bg-gray-50/70 text-gray-700 transition-all duration-200 dark:border-gray-800 dark:bg-gray-900/40 dark:text-gray-300"
		>
			<div class="flex items-start justify-between gap-3 px-3 py-2">
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
					<div class="flex items-center gap-2">
						<span
							class="mt-0.5 size-2 shrink-0 rounded-full {active
								? 'animate-pulse bg-emerald-500'
								: 'bg-gray-400 dark:bg-gray-600'}"
						></span>
						<div class="min-w-0 flex-1">
							<StatusItem {status} compact={viewMode === 'compact'} />
						</div>
					</div>
				</button>

				<div class="flex shrink-0 items-center gap-1">
					<div
						class="whitespace-nowrap rounded-md bg-white px-1.5 py-0.5 text-[11px] font-medium text-gray-500 dark:bg-gray-850 dark:text-gray-400"
					>
						{elapsed}
					</div>
					{#each VIEW_MODES as mode}
						<button
							type="button"
							class="rounded-md px-1.5 py-0.5 text-[11px] font-medium transition {viewMode === mode
								? 'bg-gray-900 text-white dark:bg-white dark:text-gray-900'
								: 'text-gray-500 hover:bg-white dark:text-gray-400 dark:hover:bg-gray-850'}"
							on:click={() => setViewMode(mode)}
							aria-pressed={viewMode === mode}
						>
							{VIEW_LABELS[mode]}
						</button>
					{/each}
				</div>
			</div>

			{#if viewMode !== 'compact'}
				<div class="border-t border-gray-100 px-3 py-2 dark:border-gray-800">
					<div class="mb-2 flex flex-wrap gap-2 text-xs text-gray-500 dark:text-gray-400">
						<span>{history.length} updates</span>
						<span>{toolCount} stages</span>
						<span>{active ? 'Working' : 'Idle'}</span>
					</div>

					{#if showHistory}
						<div
							class="space-y-2 overflow-y-auto pr-1 {viewMode === 'detailed'
								? 'max-h-96'
								: 'max-h-44'}"
						>
							{#each panelHistory as entry, idx}
								<div class="grid grid-cols-[12px_minmax(0,1fr)] gap-2">
									<div class="pt-2">
										<div
											class="size-1.5 rounded-full {isActive(entry)
												? 'bg-emerald-500'
												: 'bg-gray-400 dark:bg-gray-600'}"
										></div>
									</div>
									<div class="min-w-0">
										<StatusItem status={entry} done={!isActive(entry)} compact={false} />
										{#if viewMode === 'detailed'}
											<div
												class="mt-1 grid gap-1 rounded-md bg-white/70 p-2 text-[11px] dark:bg-gray-950/40"
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
						</div>
					{/if}
				</div>
			{/if}
		</div>
	</div>
{/if}
