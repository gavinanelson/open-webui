<script lang="ts">
	import { createEventDispatcher, onDestroy, onMount } from 'svelte';
	const dispatch = createEventDispatcher();

	let loaderElement: HTMLElement;

	let observer;
	let intervalId;
	let visible = false;
	let lastDispatchAt = 0;
	const MIN_VISIBLE_INTERVAL = 300;

	const dispatchVisible = () => {
		const now = Date.now();
		if (now - lastDispatchAt < MIN_VISIBLE_INTERVAL) {
			return;
		}

		lastDispatchAt = now;
		dispatch('visible');
	};

	onMount(() => {
		observer = new IntersectionObserver(
			(entries, observer) => {
				entries.forEach((entry) => {
					if (entry.isIntersecting) {
						if (visible) {
							return;
						}

						visible = true;
						dispatchVisible();
						intervalId = setInterval(() => {
							dispatchVisible();
						}, MIN_VISIBLE_INTERVAL);
					} else {
						visible = false;
						clearInterval(intervalId);
						intervalId = null;
					}
				});
			},
			{
				root: null, // viewport
				rootMargin: '0px',
				threshold: 0.1 // When 10% of the loader is visible
			}
		);

		observer.observe(loaderElement);
	});

	onDestroy(() => {
		if (observer) {
			observer.disconnect();
		}

		if (intervalId) {
			clearInterval(intervalId);
		}
	});
</script>

<div bind:this={loaderElement}>
	<slot />
</div>
