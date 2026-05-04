import { useEffect } from "react";

const SITE_NAME = "OpenMarket";

function setMetaDescription(description: string) {
  let tag = document.querySelector<HTMLMetaElement>('meta[name="description"]');
  if (!tag) {
    tag = document.createElement("meta");
    tag.name = "description";
    document.head.appendChild(tag);
  }
  tag.content = description;
}

export function usePageMeta(title: string, description?: string) {
  useEffect(() => {
    document.title = title ? `${title} · ${SITE_NAME}` : SITE_NAME;
    if (description) setMetaDescription(description);
  }, [title, description]);
}
