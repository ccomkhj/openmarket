import { useEffect, useState } from "react";
import { fetchBootstrapStatus, fetchMe, type Me } from "@openmarket/shared";
import { Login } from "../pages/Login";
import { Setup } from "../pages/Setup";

type State = "loading" | "setup" | "login" | { me: Me };

export function RequireAuth({ children }: { children: (me: Me) => React.ReactNode }) {
  const [state, setState] = useState<State>("loading");

  async function reload() {
    try {
      const me = await fetchMe();
      if (me) {
        setState({ me });
        return;
      }
      const status = await fetchBootstrapStatus();
      setState(status.setup_required ? "setup" : "login");
    } catch {
      setState("login");
    }
  }

  useEffect(() => { void reload(); }, []);

  if (state === "loading") return <p>Loading...</p>;
  if (state === "setup") return <Setup onComplete={reload} />;
  if (state === "login") return <Login onSuccess={reload} />;
  return <>{children(state.me)}</>;
}
