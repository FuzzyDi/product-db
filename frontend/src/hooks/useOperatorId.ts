import { useState } from 'react';

const KEY = 'operator_id';

export function useOperatorId() {
  const [operatorId, setOperatorIdState] = useState<string>(
    () => localStorage.getItem(KEY) ?? '',
  );

  function setOperatorId(id: string) {
    localStorage.setItem(KEY, id);
    setOperatorIdState(id);
  }

  return { operatorId, setOperatorId };
}
