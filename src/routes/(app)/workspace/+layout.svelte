<script lang="ts">
	import { WEBUI_NAME, mobile, showSidebar } from '$lib/stores';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import { onMount } from 'svelte';
	import Sidebar from '$lib/components/icons/Sidebar.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';

	const title = `Hermes • ${WEBUI_NAME}`;

	onMount(() => {
		if ($page.url.pathname !== '/workspace') {
			goto('/workspace');
		}
	});
</script>

<svelte:head>
	<title>{title}</title>
</svelte:head>

<div
	class="relative flex h-screen max-h-[100dvh] w-full max-w-full flex-col transition-width duration-200 ease-in-out {$showSidebar
		? 'md:max-w-[calc(100%-var(--sidebar-width))]'
		: ''}"
>
	<nav class="drag-region px-2.5 pt-1.5 backdrop-blur-xl">
		<div class="flex items-center gap-2">
			{#if $mobile}
				<div class="{$showSidebar ? 'md:hidden' : ''} flex flex-none items-center self-center">
					<Tooltip content={$showSidebar ? 'Close Sidebar' : 'Open Sidebar'} interactive={true}>
						<button
							id="sidebar-toggle-button"
							class="flex cursor-pointer rounded-lg transition hover:bg-gray-100 dark:hover:bg-gray-850"
							aria-label={$showSidebar ? 'Close Sidebar' : 'Open Sidebar'}
							on:click={() => {
								showSidebar.set(!$showSidebar);
							}}
						>
							<div class="self-center p-1.5">
								<Sidebar />
							</div>
						</button>
					</Tooltip>
				</div>
			{/if}

			<div class="py-2 text-sm font-semibold text-gray-900 dark:text-gray-100">Hermes</div>
		</div>
	</nav>

	<div class="min-h-0 flex-1 overflow-y-auto px-3 pb-4 md:px-[18px]">
		<slot />
	</div>
</div>
