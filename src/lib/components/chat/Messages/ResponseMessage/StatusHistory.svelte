<script lang="ts">
	import { onDestroy, onMount } from 'svelte';
	import { slide } from 'svelte/transition';
	import { quintOut } from 'svelte/easing';
	import equal from 'fast-deep-equal';

	import StatusItem from './StatusHistory/StatusItem.svelte';
	import GlobeAlt from '$lib/components/icons/GlobeAlt.svelte';
	import Camera from '$lib/components/icons/Camera.svelte';
	import Sparkles from '$lib/components/icons/Sparkles.svelte';
	import Wrench from '$lib/components/icons/Wrench.svelte';
	import Code from '$lib/components/icons/Code.svelte';
	import Search from '$lib/components/icons/Search.svelte';
	import ChevronDown from '$lib/components/icons/ChevronDown.svelte';

	export let statusHistory: any[] = [];
	export let expand = false;
	export let visibilityMode = 'compact';
	export let messageDone = false;

	type ViewMode = 'compact' | 'steps' | 'trace';
	const VIEW_MODES: ViewMode[] = ['compact', 'steps', 'trace'];
	const VIEW_LABELS: Record<ViewMode, string> = {
		compact: 'Summary',
		steps: 'Steps',
		trace: 'Trace'
	};

	let viewMode: ViewMode = 'compact';
	let now = Date.now();
	let timer: ReturnType<typeof setInterval> | null = null;
	let history: any[] = [];
	let status: any = null;
	let finishedAt: number | null = null;

	const clampMode = (mode: string | null | undefined): ViewMode => {
		if (mode === 'compact' || mode === 'steps' || mode === 'trace') return mode;
		if (mode === 'medium') return 'steps';
		if (mode === 'detailed') return 'trace';
		return 'compact';
	};

	const timestampOf = (entry: any) => {
		const value = entry?.received_at ?? entry?.started_at ?? entry?.created_at ?? entry?.timestamp;
		if (typeof value !== 'number') return null;
		return value > 1_000_000_000_000 ? value : value * 1000;
	};

	const formatElapsed = (seconds: number) => {
		if (!Number.isFinite(seconds) || seconds < 0) return '0s';
		const total = Math.floor(seconds);
		const m = Math.floor(total / 60);
		const s = total % 60;
		return m > 0 ? `${m}m ${s}s` : `${s}s`;
	};

	const isDone = (entry: any) =>
		entry?.done === true ||
		['completed', 'complete', 'done'].includes(String(entry?.status ?? '').toLowerCase());

	type EntryKind = 'reasoning' | 'browser' | 'search' | 'snapshot' | 'code' | 'tool' | 'default';

	const entryKind = (entry: any): EntryKind => {
		const blob = `${entry?.event ?? ''} ${entry?.action ?? ''} ${entry?.tool ?? ''}`.toLowerCase();
		if (blob.includes('reasoning')) return 'reasoning';
		if (blob.includes('snapshot')) return 'snapshot';
		if (blob.includes('browser') || blob.includes('navigate') || blob.includes('fetch_url'))
			return 'browser';
		if (blob.includes('search') || blob.includes('query')) return 'search';
		if (blob.includes('code') || blob.includes('python') || blob.includes('exec')) return 'code';
		if (entry?.tool || blob.includes('tool')) return 'tool';
		return 'default';
	};

	// Color palette per entry kind. Each returns { ring, bg, fg } classes for the icon disc.
	const kindColor = (kind: EntryKind) => {
		switch (kind) {
			case 'reasoning':
				return 'border-amber-200 bg-amber-50 text-amber-600 dark:border-amber-400/30 dark:bg-amber-500/[0.12] dark:text-amber-300';
			case 'browser':
				return 'border-sky-200 bg-sky-50 text-sky-600 dark:border-sky-400/30 dark:bg-sky-500/[0.12] dark:text-sky-300';
			case 'search':
				return 'border-indigo-200 bg-indigo-50 text-indigo-600 dark:border-indigo-400/30 dark:bg-indigo-500/[0.12] dark:text-indigo-300';
			case 'snapshot':
				return 'border-violet-200 bg-violet-50 text-violet-600 dark:border-violet-400/30 dark:bg-violet-500/[0.12] dark:text-violet-300';
			case 'code':
				return 'border-emerald-200 bg-emerald-50 text-emerald-600 dark:border-emerald-400/30 dark:bg-emerald-500/[0.12] dark:text-emerald-300';
			case 'tool':
				return 'border-gray-200 bg-gray-50 text-gray-600 dark:border-white/[0.10] dark:bg-white/[0.05] dark:text-gray-300';
			default:
				return 'border-gray-200 bg-white text-gray-500 dark:border-white/[0.10] dark:bg-white/[0.03] dark:text-gray-400';
		}
	};

	const humanize = (s: string) =>
		s
			.replace(/[_-]+/g, ' ')
			.trim()
			.replace(/\b\w/g, (c) => c.toUpperCase());

	const hostOf = (url: unknown) => {
		if (typeof url !== 'string' || !url.startsWith('http')) return null;
		try {
			return new URL(url).hostname.replace(/^www\./, '');
		} catch {
			return null;
		}
	};

	const entryTitle = (entry: any): string => {
		const kind = entryKind(entry);
		if (kind === 'reasoning') return 'Reasoning';
		if (kind === 'browser') {
			const host = hostOf(entry?.url ?? entry?.target ?? entry?.description);
			return host ? `Visited ${host}` : 'Browsed';
		}
		if (kind === 'snapshot') return 'Captured page';
		if (kind === 'search') {
			const q = entry?.query ?? entry?.search ?? null;
			return q ? `Searched "${q}"` : 'Searched';
		}
		if (kind === 'code') return 'Ran code';
		if (entry?.tool) return humanize(String(entry.tool));
		if (entry?.action) return humanize(String(entry.action));
		return 'Step';
	};

	const entryBody = (entry: any): string => {
		const kind = entryKind(entry);
		if (kind === 'reasoning') {
			const value =
				entry?.reasoning ?? entry?.text ?? entry?.summary ?? entry?.preview ?? entry?.description;
			return typeof value === 'string' ? value : '';
		}
		const url = entry?.url ?? entry?.target;
		if (typeof url === 'string' && url.startsWith('http')) return url;
		const value = entry?.description ?? entry?.text ?? entry?.summary ?? entry?.preview;
		if (typeof value === 'string') return value;
		return '';
	};

	const setViewMode = (mode: ViewMode) => {
		viewMode = mode;
		try {
			localStorage.setItem('chat-status-view-mode', viewMode);
		} catch {}
	};

	const cycleViewMode = () => {
		const i = VIEW_MODES.indexOf(viewMode);
		setViewMode(VIEW_MODES[(i + 1) % VIEW_MODES.length]);
	};

	$: if (!equal(statusHistory ?? [], history)) {
		history = statusHistory ?? [];
	}
	$: status = history.at(-1) ?? null;
	$: if (messageDone && finishedAt === null) finishedAt = Date.now();
	$: if (!messageDone) finishedAt = null;
	$: active = !messageDone && history.some((entry) => !isDone(entry));
	$: startedAt = history.map(timestampOf).find(Boolean) ?? timestampOf(status) ?? now;
	$: elapsed = formatElapsed(((active ? now : (finishedAt ?? now)) - startedAt) / 1000);
	$: expanded = viewMode !== 'compact';
	$: if (expand && viewMode === 'compact') setViewMode('steps');

	onMount(() => {
		try {
			const stored = localStorage.getItem('chat-status-view-mode');
			setViewMode(clampMode(stored ?? visibilityMode));
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

{#if history.length > 0 && status?.hidden !== true}
	<div class="status-description w-full text-left text-sm">
		<!-- Enclosing box -->
		<div
			class="overflow-hidden rounded-2xl border border-gray-200/80 bg-white/60 dark:border-white/[0.06] dark:bg-white/[0.02]"
		>
			<!-- Top cap: clickable, cycles modes -->
			<button
				type="button"
				class="group flex w-full items-center gap-3 px-3.5 py-2 text-left transition hover:bg-gray-50 dark:hover:bg-white/[0.03]"
				on:click={cycleViewMode}
				aria-label="Cycle status detail level"
			>
				<!-- pulse dot -->
				<div class="relative size-2 shrink-0">
					{#if active}
						<span class="absolute inset-0 animate-ping rounded-full bg-sky-400 opacity-60"></span>
					{/if}
					<span
						class="absolute inset-0 rounded-full {active
							? 'bg-sky-400'
							: 'bg-gray-300 dark:bg-gray-600'}"
					></span>
				</div>

				<!-- meta -->
				<div class="min-w-0 flex-1 truncate text-[13px]">
					<span
						class="font-medium {active
							? 'shimmer text-gray-700 dark:text-gray-200'
							: 'text-gray-700 dark:text-gray-300'}"
					>
						{active ? 'Working' : 'Done'}
					</span>
					<span class="mx-1.5 text-gray-300 dark:text-gray-700">·</span>
					<span class="text-gray-500 dark:text-gray-500">{elapsed}</span>
					<span class="mx-1.5 text-gray-300 dark:text-gray-700">·</span>
					<span class="text-gray-500 dark:text-gray-500">
						{history.length}
						{history.length === 1 ? 'step' : 'steps'}
					</span>
				</div>

				<!-- mode hint + chevron -->
				<div class="flex shrink-0 items-center gap-1 text-[11px] text-gray-400 dark:text-gray-500">
					<span class="font-medium uppercase tracking-wide">{VIEW_LABELS[viewMode]}</span>
					<div class="transition-transform duration-200 {expanded ? 'rotate-180' : ''}">
						<ChevronDown className="size-3.5" strokeWidth="2.5" />
					</div>
				</div>
			</button>

			<!-- Body: timeline (no rail, just rows) -->
			{#if expanded}
				<div
					transition:slide={{ duration: 220, easing: quintOut, axis: 'y' }}
					class="border-t border-gray-200/70 dark:border-white/[0.05]"
				>
					<ul class="px-3 py-2">
						{#each history as entry, idx}
							{@const kind = entryKind(entry)}
							{@const title = entryTitle(entry)}
							{@const body = entryBody(entry)}
							{@const entryDone = isDone(entry) || messageDone}
							{@const isReasoning = kind === 'reasoning'}

							<li class="flex items-start gap-3 py-1.5">
								<!-- icon disc -->
								<div
									class="relative mt-0.5 flex size-[22px] shrink-0 items-center justify-center rounded-full border {kindColor(
										kind
									)} {!entryDone ? 'ring-2 ring-sky-300/40 dark:ring-sky-400/30' : ''}"
								>
									{#if isReasoning}
										<Sparkles className="size-3" strokeWidth="2" />
									{:else if kind === 'browser'}
										<GlobeAlt className="size-3" strokeWidth="2" />
									{:else if kind === 'search'}
										<Search className="size-3" strokeWidth="2" />
									{:else if kind === 'snapshot'}
										<Camera className="size-3" strokeWidth="2" />
									{:else if kind === 'code'}
										<Code className="size-3" strokeWidth="2" />
									{:else if kind === 'tool'}
										<Wrench className="size-3" strokeWidth="2" />
									{:else}
										<span class="size-1.5 rounded-full bg-current"></span>
									{/if}
								</div>

								<!-- content -->
								<div class="min-w-0 flex-1 pb-0.5">
									<div class="flex items-baseline gap-2 text-[13px] leading-[22px]">
										<span
											class="truncate font-medium {!entryDone
												? 'shimmer'
												: ''} text-gray-800 dark:text-gray-100"
										>
											{title}
										</span>
									</div>

									{#if viewMode === 'trace' && body}
										{#if isReasoning}
											<div
												class="mt-1 rounded-md border-l-2 border-amber-300 bg-amber-50/50 px-3 py-1.5 text-[13px] italic leading-6 text-gray-700 dark:border-amber-400/50 dark:bg-amber-500/[0.06] dark:text-gray-200"
											>
												<div class="whitespace-pre-wrap break-words">{body}</div>
											</div>
										{:else}
											<div
												class="mt-0.5 break-all font-mono text-[11.5px] leading-5 text-gray-500 dark:text-gray-500"
											>
												{body}
											</div>
										{/if}
									{/if}
								</div>
							</li>
						{/each}
					</ul>
				</div>
			{:else}
				<!-- Bottom cap in compact mode: latest status one-liner -->
				<div
					class="border-t border-gray-200/70 px-3.5 py-1.5 text-[12.5px] text-gray-500 dark:border-white/[0.05] dark:text-gray-400"
				>
					<div class="line-clamp-1">
						<StatusItem {status} compact={true} done={!active} />
					</div>
				</div>
			{/if}
		</div>
	</div>
{/if}
