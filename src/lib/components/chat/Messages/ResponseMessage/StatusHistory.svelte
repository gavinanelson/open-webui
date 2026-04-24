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
		<button
			class="group flex w-full items-start gap-3 rounded-2xl bg-gray-50/80 px-3.5 py-3 text-left transition hover:bg-gray-100/90 dark:bg-white/[0.035] dark:hover:bg-white/[0.055]"
			aria-label="Cycle status detail level"
			on:click={cycleViewMode}
		>
			<span
				class="mt-1.5 size-2 shrink-0 rounded-full {active
					? 'animate-pulse bg-sky-400'
					: 'bg-gray-400 dark:bg-gray-600'}"
			></span>
			<div class="min-w-0 flex-1">
				<div class="mb-1 flex min-w-0 items-center gap-2 text-[11px] font-medium uppercase text-gray-500 dark:text-gray-500">
					<span>{active ? 'Working' : 'Done'}</span>
					<span class="text-gray-300 dark:text-gray-700">/</span>
					<span>{VIEW_LABELS[viewMode]}</span>
				</div>
				<StatusItem {status} compact={true} done={!active} />
			</div>
		</button>

		{#if viewMode !== 'compact'}
			<div class="mt-2">
				<div class="mb-2 flex flex-wrap items-center gap-2 px-1 text-[11px] text-gray-500 dark:text-gray-500">
					<span>{history.length} updates</span>
					<span>{stageCount} stages</span>
					<span>{hasReasoning ? 'Reasoning available' : 'No reasoning text'}</span>
					<span class="ml-auto">{active ? `Working ${elapsed}` : `Done after ${elapsed}`}</span>
					<button
						class="rounded-md px-2 py-0.5 text-[11px] text-gray-600 transition hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-white/[0.06]"
						on:click={() => setLayoutMode(layoutMode === 'scroll' ? 'expanded' : 'scroll')}
					>
						{layoutMode === 'scroll' ? 'Expand' : 'Scroll'}
					</button>
				</div>

				<div
					class="space-y-1.5 pr-1 {layoutMode === 'scroll'
						? viewMode === 'detailed'
							? 'max-h-[34rem] overflow-y-auto'
							: 'max-h-52 overflow-y-auto'
						: ''}"
				>
					{#each panelHistory as entry}
						<div
							class="grid grid-cols-[16px_minmax(0,1fr)] gap-2 rounded-xl px-1.5 py-1.5 {isReasoning(entry) && viewMode === 'detailed'
								? 'bg-sky-50/70 dark:bg-sky-500/[0.06]'
								: 'bg-transparent'}"
						>
							<div class="pt-2">
								<div
									class="size-1.5 rounded-full {isReasoning(entry)
										? 'bg-sky-400'
										: isTool(entry)
											? 'bg-amber-400'
											: isDone(entry) || messageDone
												? 'bg-gray-400 dark:bg-gray-600'
												: 'bg-emerald-400'}"
								></div>
							</div>

							<div class="min-w-0">
								{#if viewMode === 'detailed'}
									<div class="mb-1 text-[11px] font-medium uppercase text-gray-500 dark:text-gray-500">
										{entryTitle(entry)}
									</div>
									<div
										class="whitespace-pre-wrap break-words text-[13px] leading-6 {isReasoning(entry)
											? 'text-gray-800 dark:text-gray-100'
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
				</div>
			</div>
		{:else}
			<div class="mt-1 px-1 text-[11px] text-gray-500 dark:text-gray-500">
				{active ? elapsed : `Done after ${elapsed}`}
			</div>
		{/if}
	</div>
{/if}
