import { useState } from 'react';

const KEY = 'api_key';

export function getStoredApiKey(): string {
  return localStorage.getItem(KEY) ?? '';
}

export function useApiKey() {
  const [apiKey, setApiKeyState] = useState<string>(() => getStoredApiKey());

  function setApiKey(value: string) {
    localStorage.setItem(KEY, value);
    setApiKeyState(value);
  }

  return { apiKey, setApiKey };
}
