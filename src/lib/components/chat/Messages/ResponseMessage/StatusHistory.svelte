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
	const nextViewMode = () => {
		const currentIndex = VIEW_MODES.indexOf(viewMode);
		return VIEW_MODES[(currentIndex + 1) % VIEW_MODES.length];
	};

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
	const entryKind = (entry) => {
		const event = entry?.event ?? '';
		if (event.includes('reasoning')) return 'Reasoning';
		if (event.includes('tool')) return 'Tool';
		if (entry?.action) return entry.action;
		return 'Hermes';
	};
	const entryText = (entry) => {
		const value =
			entry?.text ??
			entry?.reasoning ??
			entry?.summary ??
			entry?.preview ??
			entry?.label ??
			entry?.description ??
			entry?.tool ??
			entry?.action;
		if (typeof value === 'string') return value;
		try {
			return JSON.stringify(value);
		} catch {
			return String(value ?? '');
		}
	};
	const cycleViewMode = () => {
		setViewMode(nextViewMode());
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
	$: hasReasoning = history.some(
		(entry) => (entry?.event ?? '').includes('reasoning') || entry?.text
	);
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
				<button
					class="w-full rounded-lg border border-gray-100 bg-gray-50/70 px-2.5 py-2 text-left transition hover:bg-gray-100 dark:border-gray-800 dark:bg-gray-900/40 dark:hover:bg-gray-850"
					aria-label={$i18n.t('Cycle status detail level')}
					aria-pressed={viewMode !== 'compact'}
					on:click={cycleViewMode}
				>
					<div class="flex min-w-0 items-start justify-between gap-3">
						<div class="min-w-0 flex-1">
							<StatusItem {status} compact={true} />
						</div>
						<div
							class="shrink-0 rounded-md bg-white px-1.5 py-0.5 text-[11px] font-medium text-gray-600 shadow-xs dark:bg-gray-800 dark:text-gray-300"
						>
							{selectedViewLabel}
						</div>
					</div>
				</button>

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
											{#if viewMode === 'detailed'}
												<div class="rounded-md bg-gray-50 p-2 dark:bg-gray-900/60">
													<div
														class="mb-1 text-[11px] font-medium text-gray-500 dark:text-gray-500"
													>
														{entryKind(entry)}
													</div>
													<div
														class="whitespace-pre-wrap break-words text-xs leading-5 text-gray-700 dark:text-gray-300"
													>
														{entryText(entry)}
													</div>
												</div>
											{:else}
												<StatusItem status={entry} done={!isActive(entry)} compact={false} />
											{/if}
										</div>
									</div>
								{/each}
								{#if viewMode === 'detailed' && !hasReasoning}
									<div
										class="rounded-md border border-dashed border-gray-200 px-2.5 py-2 text-xs text-gray-500 dark:border-gray-800 dark:text-gray-500"
									>
										Reasoning text is not present on this Hermes chat-completions stream yet.
									</div>
								{/if}
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

				<div class="mt-1.5 text-[11px] text-gray-500 dark:text-gray-500">
					{active ? 'Working' : 'Done'} for {elapsed}
				</div>
			</div>
		</div>
	</div>
{/if}
