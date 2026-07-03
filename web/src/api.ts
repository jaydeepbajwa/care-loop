/** Minimal typed fetch wrapper. Errors carry the server's guidance message. */

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message)
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(path, {
    headers: { 'Content-Type': 'application/json', ...(init.headers ?? {}) },
    ...init,
  })
  if (!response.ok) {
    let detail = `Request failed (${response.status})`
    try {
      const body = await response.json()
      if (typeof body.detail === 'string') detail = body.detail
    } catch {
      /* non-JSON error body — keep the generic message */
    }
    throw new ApiError(response.status, detail)
  }
  return response.json() as Promise<T>
}

export const api = {
  get: <T>(path: string, headers?: Record<string, string>) =>
    request<T>(path, { headers }),
  post: <T>(path: string, body?: unknown, headers?: Record<string, string>) =>
    request<T>(path, { method: 'POST', body: body ? JSON.stringify(body) : undefined, headers }),
  patch: <T>(path: string, body: unknown) =>
    request<T>(path, { method: 'PATCH', body: JSON.stringify(body) }),
}

const MEMBER_TOKEN_KEY = 'careloop.memberToken'

export const memberToken = {
  get: () => localStorage.getItem(MEMBER_TOKEN_KEY),
  set: (token: string) => localStorage.setItem(MEMBER_TOKEN_KEY, token),
  clear: () => localStorage.removeItem(MEMBER_TOKEN_KEY),
}
