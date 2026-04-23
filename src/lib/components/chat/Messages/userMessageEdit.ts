type UserMessageLike = {
	content?: string | null;
	files?: unknown[] | null;
};

export const createUserMessageEditDraft = (message: UserMessageLike | null | undefined) => {
	return {
		content: message?.content ?? '',
		files: structuredClone(message?.files ?? [])
	};
};
