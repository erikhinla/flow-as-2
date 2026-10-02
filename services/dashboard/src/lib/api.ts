export function apiFetch(url: string, opts: RequestInit = {}): Promise<Response> {
  const stored = localStorage.getItem('flow_api_token')
  const token = stored || (import.meta.env.DEV ? 'change-me' : null)
  return fetch(url, {
    ...opts,
    headers: {
      ...(token ? { 'X-API-Token': token } : {}),
      Accept: 'application/json',
      ...opts.headers,
    },
  })
}

/** Parse JSON API responses; never throw cryptic "Unexpected token '<'" on HTML errors. */
export async function parseApiJson<T = unknown>(response: Response): Promise<T> {
  const text = await response.text()
  const trimmed = text.trim()
  if (!trimmed) {
    throw new Error(`Empty response from ${response.url} (HTTP ${response.status})`)
  }
  if (trimmed.startsWith('<') || trimmed.toLowerCase().startsWith('<!doctype')) {
    throw new Error(
      `Expected JSON from FAAS API but received HTML (HTTP ${response.status}). ` +
        `This is often an auth/proxy error page. Body: ${trimmed.slice(0, 160)}`,
    )
  }
  try {
    return JSON.parse(text) as T
  } catch {
    throw new Error(
      `Invalid JSON from FAAS API (HTTP ${response.status}): ${trimmed.slice(0, 200)}`,
    )
  }
}
