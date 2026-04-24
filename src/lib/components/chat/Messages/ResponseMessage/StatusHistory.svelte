<script lang="ts">
	import { onDestroy, onMount } from 'svelte';
	import StatusItem from './StatusHistory/StatusItem.svelte';
	import equal from 'fast-deep-equal';

	export let statusHistory: any[] = [];
	export let expand = false;
	export let visibilityMode = 'compact';
	export let messageDone = false;

	const VIEW_MODES = ['compact', 'medium', 'detailed'];
	const VIEW_LABELS: Record<string, string> = {
		compact: 'Compact',
		medium: 'Steps',
		detailed: 'Trace'
	};

	let viewMode = visibilityMode;
	let layoutMode = 'expanded';
	let now = Date.now();
	let timer: ReturnType<typeof setInterval> | null = null;
	let history: any[] = [];
	let status: any = null;
	let finishedAt: number | null = null;

	const clampMode = (mode: string) => (VIEW_MODES.includes(mode) ? mode : 'compact');
	const timestampOf = (entry: any) => {
		const value = entry?.received_at ?? entry?.started_at ?? entry?.created_at ?? entry?.timestamp;
		if (typeof value !== 'number') return null;
		return value > 1000000000000 ? value : value * 1000;
	};
	const formatElapsed = (seconds: number) => {
		if (!Number.isFinite(seconds) || seconds < 0) return '0s';
		const total = Math.floor(seconds);
		const minutes = Math.floor(total / 60);
		const remaining = total % 60;
		return minutes > 0 ? `${minutes}m ${remaining}s` : `${remaining}s`;
	};
	const isDone = (entry: any) =>
		entry?.done === true ||
		['completed', 'complete', 'done'].includes(String(entry?.status ?? '').toLowerCase());
	const isReasoning = (entry: any) =>
		String(entry?.event ?? '').includes('reasoning') || entry?.action === 'reasoning';
	const isTool = (entry: any) => String(entry?.event ?? '').includes('tool') || !!entry?.tool;
	const entryTitle = (entry: any) => {
		if (isReasoning(entry)) return 'Reasoning';
		if (entry?.tool) return entry.tool;
		if (isTool(entry)) return entry?.action ?? 'Tool';
		return entry?.action ?? 'Hermes';
	};
	const entryText = (entry: any) => {
		const value =
			entry?.text ??
			entry?.reasoning ??
			entry?.summary ??
			entry?.preview ??
			entry?.label ??
			entry?.description ??
			entry?.message ??
			entry?.tool ??
			entry?.action;
		if (typeof value === 'string') return value;
		try {
			return JSON.stringify(value, null, 2);
		} catch {
			return String(value ?? '');
		}
	};
	const setViewMode = (mode: string) => {
		viewMode = clampMode(mode);
		try {
			localStorage.setItem('chat-status-view-mode', viewMode);
		} catch {}
	};
	const cycleViewMode = () => {
		const currentIndex = VIEW_MODES.indexOf(viewMode);
		setViewMode(VIEW_MODES[(currentIndex + 1) % VIEW_MODES.length]);
	};
	const setLayoutMode = (mode: string) => {
		layoutMode = mode === 'scroll' ? 'scroll' : 'expanded';
		try {
			localStorage.setItem('chat-status-layout-mode', layoutMode);
		} catch {}
	};

	$: if (!equal(statusHistory ?? [], history)) {
		history = statusHistory ?? [];
	}
	$: status = history.at(-1) ?? null;
	$: if (messageDone && finishedAt === null) {
		finishedAt = Date.now();
	}
	$: if (!messageDone) {
		finishedAt = null;
	}
	$: active = !messageDone && history.some((entry) => !isDone(entry));
	$: startedAt = history.map(timestampOf).find(Boolean) ?? timestampOf(status) ?? now;
	$: elapsed = formatElapsed(((active ? now : finishedAt ?? now) - startedAt) / 1000);
	$: stageCount = new Set(history.map((entry) => entry?.action ?? entry?.tool).filter(Boolean)).size;
	$: panelHistory = viewMode === 'compact' ? history.slice(-3) : viewMode === 'medium' ? history.slice(-6) : history;
	$: hasReasoning = history.some(isReasoning);
	$: if (expand && viewMode === 'compact') {
		setViewMode('medium');
	}

	onMount(() => {
		try {
			setViewMode(clampMode(localStorage.getItem('chat-status-view-mode') ?? visibilityMode));
			setLayoutMode(localStorage.getItem('chat-status-layout-mode') ?? 'expanded');
		} catch {
			setViewMode(clampMode(visibilityMode));
		}
		timer = setInterval(() => {
			if (active) now = Date.now();
		}, 1000);
	});

	onDestroy(() => {
		if (timer) clearInterval(timer);
	});
</script>

{#if history && history.length > 0 && status?.hidden !== true}
	<div class="status-description w-full text-left text-sm">
		<div class="border-l border-gray-200 pl-3 dark:border-gray-800">
			<button
				class="group flex w-full items-start justify-between gap-3 border border-gray-100 bg-gray-50/70 px-3 py-2.5 text-left transition hover:bg-gray-100 dark:border-gray-800 dark:bg-gray-900/40 dark:hover:bg-gray-850"
				aria-label="Cycle status detail level"
				on:click={cycleViewMode}
			>
				<div class="min-w-0 flex-1">
					<div class="mb-1 flex items-center gap-2 text-[11px] uppercase text-gray-500 dark:text-gray-500">
						<span class="size-1.5 rounded-full {active ? 'animate-pulse bg-emerald-500' : 'bg-gray-400 dark:bg-gray-600'}"></span>
						<span>{active ? 'Working' : 'Done'}</span>
						<span>{elapsed}</span>
					</div>
					<StatusItem {status} compact={true} done={!active} />
				</div>
				<div class="flex shrink-0 items-center gap-1 text-[11px] text-gray-500 dark:text-gray-400">
					<span>{VIEW_LABELS[viewMode]}</span>
				</div>
			</button>

			{#if viewMode !== 'compact'}
				<div class="mt-2">
					<div class="mb-2 flex flex-wrap items-center gap-2 text-[11px] text-gray-500 dark:text-gray-500">
						<span>{history.length} updates</span>
						<span>{stageCount} stages</span>
						<span>{hasReasoning ? 'Reasoning available' : 'No reasoning text'}</span>
						<button
							class="ml-auto border border-gray-200 px-2 py-0.5 text-[11px] text-gray-600 transition hover:bg-gray-50 dark:border-gray-800 dark:text-gray-300 dark:hover:bg-gray-900"
							on:click={() => setLayoutMode(layoutMode === 'scroll' ? 'expanded' : 'scroll')}
						>
							{layoutMode === 'scroll' ? 'Expand' : 'Scroll'}
						</button>
					</div>

					<div
						class="space-y-2 pr-1 {layoutMode === 'scroll'
							? viewMode === 'detailed'
								? 'max-h-[34rem] overflow-y-auto'
								: 'max-h-52 overflow-y-auto'
							: ''}"
					>
						{#each panelHistory as entry, entryIndex}
							<div class="grid grid-cols-[14px_minmax(0,1fr)] gap-2">
								<div class="relative pt-2">
									<div
										class="size-1.5 rounded-full {isReasoning(entry)
											? 'bg-sky-500'
											: isTool(entry)
												? 'bg-amber-500'
												: isDone(entry) || messageDone
													? 'bg-gray-400 dark:bg-gray-600'
													: 'bg-emerald-500'}"
									></div>
									{#if entryIndex < panelHistory.length - 1}
										<div class="absolute left-[3px] top-5 h-[calc(100%+4px)] w-px bg-gray-200 dark:bg-gray-800"></div>
									{/if}
								</div>

								<div
									class="{viewMode === 'detailed'
										? 'border-b border-gray-100 pb-2 dark:border-gray-850'
										: ''} min-w-0"
								>
									{#if viewMode === 'detailed'}
										<div class="mb-1 text-[11px] font-medium uppercase text-gray-500 dark:text-gray-500">
											{entryTitle(entry)}
										</div>
										<div
											class="whitespace-pre-wrap break-words text-[13px] leading-6 {isReasoning(entry)
												? 'text-gray-800 dark:text-gray-200'
													: 'text-gray-600 dark:text-gray-300'}"
										>
											{entryText(entry)}
										</div>
									{:else}
										<StatusItem status={entry} done={messageDone || isDone(entry)} compact={false} />
									{/if}
								</div>
							</div>
						{/each}

						{#if !active}
							<div class="grid grid-cols-[14px_minmax(0,1fr)] gap-2">
								<div class="pt-1.5">
									<div class="size-1.5 rounded-full bg-gray-300 dark:bg-gray-700"></div>
								</div>
								<div class="text-xs font-medium text-gray-500 dark:text-gray-500">
									Done after {elapsed}
								</div>
							</div>
						{/if}
					</div>
				</div>
			{/if}
		</div>
	</div>
{/if}
