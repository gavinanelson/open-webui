import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { describe, expect, it } from 'vitest';

const readComponent = (name: string) =>
	readFileSync(resolve(process.cwd(), `src/lib/components/chat/Messages/${name}`), 'utf8');

describe('chat visibility mode props', () => {
	it('declares visibilityMode on Messages', () => {
		expect(readComponent('../Messages.svelte')).toContain("export let visibilityMode = 'compact';");
	});

	it('declares visibilityMode on Message', () => {
		expect(readComponent('Message.svelte')).toContain("export let visibilityMode = 'compact';");
	});
});
