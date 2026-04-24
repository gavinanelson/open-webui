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

	// Flat icon stroke color per kind — no backgrounds, no rings.
	const kindColor = (kind: EntryKind) => {
		switch (kind) {
			case 'reasoning':
				return 'text-amber-500 dark:text-amber-400';
			case 'browser':
				return 'text-sky-500 dark:text-sky-400';
			case 'search':
				return 'text-indigo-500 dark:text-indigo-400';
			case 'snapshot':
				return 'text-violet-500 dark:text-violet-400';
			case 'code':
				return 'text-emerald-500 dark:text-emerald-400';
			case 'tool':
				return 'text-gray-500 dark:text-gray-400';
			default:
				return 'text-gray-400 dark:text-gray-500';
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

	const isNoiseBody = (value: string, entry: any) => {
		if (!value) return true;
		const trimmed = value.trim();
		if (!trimmed) return true;
		// Body text that just repeats the action/tool/event name adds no information.
		const noise = new Set(
			[entry?.action, entry?.tool, entry?.event]
				.filter((x): x is string => typeof x === 'string' && x.length > 0)
				.map((s) => s.toLowerCase().trim())
		);
		return noise.has(trimmed.toLowerCase());
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
		if (typeof value === 'string' && !isNoiseBody(value, entry)) return value;
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
	<div class="status-description mb-3 w-full text-left text-sm">
		<!-- Enclosing box -->
		<div
			class="overflow-hidden rounded-2xl border border-gray-200/80 bg-white/60 dark:border-white/[0.06] dark:bg-white/[0.02]"
		>
			<!-- Top cap: clickable, cycles modes -->
			<button
				type="button"
				class="group flex w-full items-center gap-2.5 px-3 py-1.5 text-left transition hover:bg-gray-50 dark:hover:bg-white/[0.03]"
				on:click={cycleViewMode}
				aria-label="Cycle status detail level"
			>
				<!-- pulse dot -->
				<div class="relative size-[7px] shrink-0">
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
				<div class="min-w-0 flex-1 truncate text-[12.5px]">
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
				<div class="flex shrink-0 items-center gap-1 text-[10.5px] text-gray-400 dark:text-gray-500">
					<span class="font-medium uppercase tracking-wide">{VIEW_LABELS[viewMode]}</span>
					<div class="transition-transform duration-200 {expanded ? 'rotate-180' : ''}">
						<ChevronDown className="size-3" strokeWidth="2.5" />
					</div>
				</div>
			</button>

			<!-- Body: timeline (no rail, just rows) -->
			{#if expanded}
				<div
					transition:slide={{ duration: 220, easing: quintOut, axis: 'y' }}
					class="border-t border-gray-200/70 dark:border-white/[0.05]"
				>
					<ul class="px-2.5 py-1.5">
						{#each history as entry, idx}
							{@const kind = entryKind(entry)}
							{@const title = entryTitle(entry)}
							{@const body = entryBody(entry)}
							{@const entryDone = isDone(entry) || messageDone}
							{@const isReasoning = kind === 'reasoning'}

							<li class="flex items-start gap-2 py-0.5">
								<!-- flat colored icon, no disc, no ring -->
								<div
									class="mt-[3px] flex size-3.5 shrink-0 items-center justify-center {kindColor(
										kind
									)} {!entryDone ? 'animate-pulse' : ''}"
								>
									{#if isReasoning}
										<Sparkles className="size-3.5" strokeWidth="2" />
									{:else if kind === 'browser'}
										<GlobeAlt className="size-3.5" strokeWidth="2" />
									{:else if kind === 'search'}
										<Search className="size-3.5" strokeWidth="2" />
									{:else if kind === 'snapshot'}
										<Camera className="size-3.5" strokeWidth="2" />
									{:else if kind === 'code'}
										<Code className="size-3.5" strokeWidth="2" />
									{:else if kind === 'tool'}
										<Wrench className="size-3.5" strokeWidth="2" />
									{:else}
										<span class="size-1 rounded-full bg-current"></span>
									{/if}
								</div>

								<!-- content -->
								<div class="min-w-0 flex-1">
									<div class="flex items-baseline gap-2 text-[12.5px] leading-[18px]">
										<span
											class="truncate {!entryDone
												? 'shimmer'
												: ''} text-gray-800 dark:text-gray-100"
										>
											{title}
										</span>
									</div>

									{#if viewMode === 'trace' && body}
										{#if isReasoning}
											<div
												class="mt-0.5 border-l-2 border-amber-300 pl-2.5 text-[12.5px] italic leading-[18px] text-gray-600 dark:border-amber-400/60 dark:text-gray-300"
											>
												<div class="whitespace-pre-wrap break-words">{body}</div>
											</div>
										{:else}
											<div
												class="break-all font-mono text-[10.5px] leading-[15px] text-gray-500 dark:text-gray-500"
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
					class="border-t border-gray-200/70 px-3 py-1 text-[12px] text-gray-500 dark:border-white/[0.05] dark:text-gray-400"
				>
					<div class="line-clamp-1">
						<StatusItem {status} compact={true} done={!active} />
					</div>
				</div>
			{/if}
		</div>
	</div>
{/if}
