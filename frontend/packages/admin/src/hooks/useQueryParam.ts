import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";

/** Local state seeded from `?<key>=…` and re-synced when the URL changes
 * (e.g. from a Cmd+K palette navigation back to the same page). */
export function useQueryParam(key: string, fallback = ""): [string, (next: string) => void] {
  const [searchParams] = useSearchParams();
  const [value, setValue] = useState(() => searchParams.get(key) ?? fallback);
  useEffect(() => { setValue(searchParams.get(key) ?? fallback); }, [searchParams, key, fallback]);
  return [value, setValue];
}
