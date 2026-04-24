<script lang="ts">
	import { createEventDispatcher, getContext } from 'svelte';
	const dispatch = createEventDispatcher();
	const i18n = getContext('i18n');

	import RecursiveFolder from './RecursiveFolder.svelte';
	import { chatId, selectedFolder } from '$lib/stores';

	export let folderRegistry = {};

	export let folders = {};
	export let shiftKey = false;

	export let onDelete = (folderId) => {};

	let folderList = [];
	let showAllFolders = false;
	const VISIBLE_FOLDER_LIMIT = 5;

	const folderActivity = (folder) =>
		folder?.activity_at ?? folder?.updated_at ?? folder?.created_at ?? 0;

	$: folderList = Object.keys(folders)
		.filter((key) => folders[key].parent_id === null)
		.sort((a, b) => {
			const activityDiff = folderActivity(folders[b]) - folderActivity(folders[a]);
			if (activityDiff !== 0) return activityDiff;

			return folders[a].name.localeCompare(folders[b].name, undefined, {
				numeric: true,
				sensitivity: 'base'
			});
		});

	$: visibleFolderList = showAllFolders ? folderList : folderList.slice(0, VISIBLE_FOLDER_LIMIT);

	const onItemMove = (e) => {
		if (e.originFolderId) {
			folderRegistry[e.originFolderId]?.setFolderItems();
		}
	};

	const loadFolderItems = () => {
		for (const folderId of Object.keys(folders)) {
			folderRegistry[folderId]?.setFolderItems();
		}
	};

	$: if (folders || ($selectedFolder && $chatId)) {
		loadFolderItems();
	}
</script>

{#each visibleFolderList as folderId (folderId)}
	<RecursiveFolder
		className=""
		bind:folderRegistry
		{folders}
		{folderId}
		{shiftKey}
		{onDelete}
		{onItemMove}
		on:import={(e) => {
			dispatch('import', e.detail);
		}}
		on:update={(e) => {
			dispatch('update', e.detail);
		}}
		on:change={(e) => {
			dispatch('change', e.detail);
		}}
		on:activity={(e) => {
			const { folderId, activityAt, status } = e.detail;
			if (!folders[folderId]) return;

			if (folders[folderId].activity_at !== activityAt) {
				folders[folderId].activity_at = activityAt;
			}

			if (folders[folderId].status !== status) {
				folders[folderId].status = status;
			}

			folders = folders;
		}}
	/>
{/each}

{#if folderList.length > VISIBLE_FOLDER_LIMIT}
	<button
		type="button"
		class="mt-1 ml-1 w-[calc(100%-0.25rem)] rounded-xl px-3 py-1.5 text-left text-xs font-medium text-sky-700 hover:bg-sky-50 dark:text-sky-300 dark:hover:bg-sky-950/40 transition"
		on:click={() => {
			showAllFolders = !showAllFolders;
		}}
	>
		{showAllFolders ? $i18n.t('See Less') : $i18n.t('See More')}
	</button>
{/if}
