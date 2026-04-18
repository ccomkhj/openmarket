import { useEffect, useState } from "react";
import { fetchMe, type Me } from "@openmarket/shared";
import { CashierLogin } from "../pages/CashierLogin";

export function RequireCashier({ children }: { children: (me: Me) => React.ReactNode }) {
  const [me, setMe] = useState<Me | null | "loading">("loading");

  async function reload() {
    try {
      setMe(await fetchMe());
    } catch {
      setMe(null);
    }
  }

  useEffect(() => {
    void reload();
  }, []);

  if (me === "loading") return <p>Loading...</p>;
  if (me === null) return <CashierLogin onSuccess={reload} />;
  return <>{children(me)}</>;
}
