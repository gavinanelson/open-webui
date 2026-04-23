import { expect, test } from 'vitest';

import { createUserMessageEditDraft } from './userMessageEdit';

test('createUserMessageEditDraft clones the files array for edit state', () => {
	const source = {
		content: 'hello',
		files: [
			{
				name: 'report.pdf',
				type: 'file',
				nested: { status: 'uploaded' }
			}
		]
	};

	const draft = createUserMessageEditDraft(source);

	expect(draft.content).toBe('hello');
	expect(draft.files).not.toBe(source.files);
	expect(draft.files).toEqual(source.files);
});

test('createUserMessageEditDraft keeps the source message isolated from draft mutations', () => {
	const source = {
		content: 'hello',
		files: [
			{
				name: 'report.pdf',
				type: 'file',
				nested: { status: 'uploaded' }
			}
		]
	};

	const draft = createUserMessageEditDraft(source);

	(draft.files[0] as { nested: { status: string } }).nested.status = 'edited';

	expect(source.files[0].nested.status).toBe('uploaded');
});
