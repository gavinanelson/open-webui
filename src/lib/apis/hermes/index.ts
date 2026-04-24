import { WEBUI_API_BASE_URL } from '$lib/constants';

const request = async (token: string, path: string) => {
	let error = null;

	const res = await fetch(`${WEBUI_API_BASE_URL}/hermes${path}`, {
		method: 'GET',
		headers: {
			'Content-Type': 'application/json',
			Authorization: `Bearer ${token}`
		}
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			console.error(err);
			error = err.detail ?? err.message ?? String(err);
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const getHermesOverview = async (token: string) => request(token, '/overview');
export const getHermesCommands = async (token: string) => request(token, '/commands');
