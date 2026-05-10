const BASE = '/api/v1';

interface ApiResponse<T> {
  success: boolean;
  data: T;
  meta: Record<string, unknown>;
  error: string | null;
}

async function request<T>(
  path: string,
  options?: RequestInit & { operatorId?: string },
): Promise<T> {
  const { operatorId, ...init } = options ?? {};
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(operatorId ? { 'X-Operator-Id': operatorId } : {}),
    ...(init.headers as Record<string, string>),
  };
  const res = await fetch(`${BASE}${path}`, { ...init, headers });
  const json: ApiResponse<T> = await res.json();
  if (!json.success) throw new Error(json.error ?? 'API error');
  return json.data;
}

export const api = {
  get<T>(path: string) {
    return request<T>(path);
  },
  post<T>(path: string, body: unknown, operatorId?: string) {
    return request<T>(path, {
      method: 'POST',
      body: JSON.stringify(body),
      operatorId,
    });
  },
  put<T>(path: string, body: unknown) {
    return request<T>(path, { method: 'PUT', body: JSON.stringify(body) });
  },
};
