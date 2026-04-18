import { useEffect, useState } from "react";
import { fetchMe, type Me } from "@openmarket/shared";
import { Login } from "../pages/Login";
import { Setup } from "../pages/Setup";

type State = Me | null | "loading" | "setup";

export function RequireAuth({ children }: { children: (me: Me) => React.ReactNode }) {
  const [me, setMe] = useState<State>("loading");

  async function reload() {
    try {
      const m = await fetchMe();
      setMe(m);
    } catch {
      setMe(null);
    }
  }

  useEffect(() => {
    if (typeof window !== "undefined" && window.location.search.includes("setup")) {
      setMe("setup");
      return;
    }
    void reload();
  }, []);

  if (me === "loading") return <p>Loading...</p>;
  if (me === "setup") return <Setup onComplete={reload} />;
  if (me === null) {
    return <Login onSuccess={reload} />;
  }
  return <>{children(me)}</>;
}
