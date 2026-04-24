<script lang="ts">
	import { onMount } from 'svelte';
	import { getHermesOverview } from '$lib/apis/hermes';

	let overview: any = null;
	let error = '';
	let loading = true;

	const load = async () => {
		loading = true;
		error = '';
		try {
			overview = await getHermesOverview(localStorage.token);
		} catch (e) {
			error = String(e);
		} finally {
			loading = false;
		}
	};

	onMount(() => {
		load();
		const interval = setInterval(load, 5000);
		return () => clearInterval(interval);
	});

	$: dashboardStatus =
		overview?.dashboard_status?.available === false ? null : overview?.dashboard_status;
	$: modelInfo = overview?.model_info?.available === false ? null : overview?.model_info;
	$: health = overview?.health?.available === false ? null : overview?.health;
	$: sessions = overview?.sessions?.sessions ?? [];
	$: activeSessions = sessions.filter((session: any) => session.is_active);

	const stateLabel = (value: any) => {
		if (value === undefined || value === null || value === '') return 'Unknown';
		return String(value);
	};
</script>

<div class="mx-auto flex w-full max-w-6xl flex-col gap-4 py-3">
	<div class="flex flex-wrap items-end justify-between gap-3">
		<div>
			<div class="text-2xl font-semibold tracking-normal text-gray-950 dark:text-gray-50">
				Hermes Control
			</div>
			<div class="mt-1 text-sm text-gray-500 dark:text-gray-400">
				Native agent status, runtime controls, sessions, and command surface.
			</div>
		</div>

		<button
			class="rounded-md border border-gray-200 px-3 py-1.5 text-sm text-gray-700 transition hover:bg-gray-50 dark:border-gray-800 dark:text-gray-200 dark:hover:bg-gray-900"
			on:click={load}
		>
			Refresh
		</button>
	</div>

	{#if error}
		<div
			class="border border-red-300 bg-red-50 p-3 text-sm text-red-700 dark:border-red-900/60 dark:bg-red-950/30 dark:text-red-200"
		>
			{error}
		</div>
	{/if}

	{#if loading && !overview}
		<div class="py-16 text-center text-sm text-gray-500">Loading Hermes…</div>
	{:else}
		<div class="grid gap-3 md:grid-cols-3">
			<div class="border border-gray-200 p-4 dark:border-gray-800">
				<div class="text-xs uppercase text-gray-500 dark:text-gray-400">API Server</div>
				<div class="mt-2 text-lg font-medium text-gray-950 dark:text-gray-50">
					{health ? stateLabel(health.status) : 'Unavailable'}
				</div>
				<div class="mt-1 truncate text-xs text-gray-500 dark:text-gray-400">
					{overview?.api_base_url}
				</div>
			</div>

			<div class="border border-gray-200 p-4 dark:border-gray-800">
				<div class="text-xs uppercase text-gray-500 dark:text-gray-400">Gateway</div>
				<div class="mt-2 text-lg font-medium text-gray-950 dark:text-gray-50">
					{dashboardStatus
						? dashboardStatus.gateway_running
							? `Running · PID ${dashboardStatus.gateway_pid}`
							: stateLabel(dashboardStatus.gateway_state)
						: 'Dashboard API unavailable'}
				</div>
				<div class="mt-1 text-xs text-gray-500 dark:text-gray-400">
					{dashboardStatus?.active_sessions ?? activeSessions.length} active sessions
				</div>
			</div>

			<div class="border border-gray-200 p-4 dark:border-gray-800">
				<div class="text-xs uppercase text-gray-500 dark:text-gray-400">Runtime Model</div>
				<div class="mt-2 truncate text-lg font-medium text-gray-950 dark:text-gray-50">
					{modelInfo?.model ?? overview?.models?.data?.[0]?.id ?? 'Unknown'}
				</div>
				<div class="mt-1 truncate text-xs text-gray-500 dark:text-gray-400">
					{modelInfo?.provider
						? `${modelInfo.provider} · `
						: ''}{modelInfo?.effective_context_length
						? `${modelInfo.effective_context_length} context`
						: 'Hermes model endpoint'}
				</div>
			</div>
		</div>

		<div class="grid gap-4 lg:grid-cols-[1.1fr_0.9fr]">
			<section class="border border-gray-200 dark:border-gray-800">
				<div class="border-b border-gray-200 px-4 py-3 dark:border-gray-800">
					<div class="text-sm font-semibold text-gray-950 dark:text-gray-50">Sessions</div>
					<div class="mt-1 text-xs text-gray-500 dark:text-gray-400">
						From the Hermes dashboard/session database when available.
					</div>
				</div>

				<div class="divide-y divide-gray-200 dark:divide-gray-800">
					{#if sessions.length === 0}
						<div class="p-4 text-sm text-gray-500 dark:text-gray-400">
							No Hermes dashboard sessions available from this Open WebUI process.
						</div>
					{:else}
						{#each sessions.slice(0, 8) as session}
							<div class="flex items-center justify-between gap-3 p-4">
								<div class="min-w-0">
									<div class="truncate text-sm font-medium text-gray-950 dark:text-gray-50">
										{session.title || session.id}
									</div>
									<div class="mt-1 text-xs text-gray-500 dark:text-gray-400">
										{session.source ?? 'api'} · {session.message_count ?? 0} messages
									</div>
								</div>
								<div
									class="shrink-0 rounded-full border px-2 py-0.5 text-xs {session.is_active
										? 'border-emerald-500/40 text-emerald-600 dark:text-emerald-300'
										: 'border-gray-300 text-gray-500 dark:border-gray-700 dark:text-gray-400'}"
								>
									{session.is_active ? 'Active' : 'Idle'}
								</div>
							</div>
						{/each}
					{/if}
				</div>
			</section>

			<section class="border border-gray-200 dark:border-gray-800">
				<div class="border-b border-gray-200 px-4 py-3 dark:border-gray-800">
					<div class="text-sm font-semibold text-gray-950 dark:text-gray-50">Runtime Config</div>
					<div class="mt-1 text-xs text-gray-500 dark:text-gray-400">
						These are Hermes-owned settings, not Open WebUI workspace models.
					</div>
				</div>

				<div class="grid gap-3 p-4 text-sm">
					<div class="flex justify-between gap-4">
						<span class="text-gray-500 dark:text-gray-400">Version</span>
						<span class="text-right text-gray-950 dark:text-gray-50">
							{dashboardStatus?.version ?? 'Unavailable'}
						</span>
					</div>
					<div class="flex justify-between gap-4">
						<span class="text-gray-500 dark:text-gray-400">Home</span>
						<span class="truncate text-right text-gray-950 dark:text-gray-50">
							{dashboardStatus?.hermes_home ?? 'Unavailable'}
						</span>
					</div>
					<div class="flex justify-between gap-4">
						<span class="text-gray-500 dark:text-gray-400">Config</span>
						<span class="truncate text-right text-gray-950 dark:text-gray-50">
							{dashboardStatus?.config_path ?? 'Unavailable'}
						</span>
					</div>
					<div class="flex justify-between gap-4">
						<span class="text-gray-500 dark:text-gray-400">Dashboard API</span>
						<span class="truncate text-right text-gray-950 dark:text-gray-50">
							{overview?.dashboard_base_url}
						</span>
					</div>
				</div>
			</section>
		</div>

		<section class="border border-gray-200 dark:border-gray-800">
			<div class="border-b border-gray-200 px-4 py-3 dark:border-gray-800">
				<div class="text-sm font-semibold text-gray-950 dark:text-gray-50">Hermes Commands</div>
				<div class="mt-1 text-xs text-gray-500 dark:text-gray-400">
					Grouped from Hermes' command registry into native UI surfaces.
				</div>
			</div>

			<div class="grid gap-3 p-4 md:grid-cols-2">
				{#each overview?.commands ?? [] as group}
					<div class="border border-gray-200 p-3 dark:border-gray-800">
						<div class="mb-3 text-xs font-semibold uppercase text-gray-500 dark:text-gray-400">
							{group.category}
						</div>
						<div class="grid gap-2">
							{#each group.commands as command}
								<div class="flex items-center justify-between gap-3 text-sm">
									<div class="min-w-0">
										<div class="font-mono text-gray-950 dark:text-gray-50">/{command.name}</div>
										<div class="truncate text-xs text-gray-500 dark:text-gray-400">
											{command.label}
										</div>
									</div>
									<div
										class="shrink-0 rounded border border-gray-200 px-1.5 py-0.5 text-[11px] text-gray-500 dark:border-gray-800 dark:text-gray-400"
									>
										{command.ui}
									</div>
								</div>
							{/each}
						</div>
					</div>
				{/each}
			</div>
		</section>
	{/if}
</div>
