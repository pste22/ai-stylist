import { createElement } from "react";
import { createRoot } from "react-dom/client";
import { FullLookPanel } from "./App.jsx";

/** Test-only mount for the Complete the Look page. Not imported by the app. */
export function renderLook(look) {
  const host = document.createElement("div");
  host.id = "look-harness";
  document.body.appendChild(host);
  createRoot(host).render(createElement(FullLookPanel, {
    look,
    loved: new Set(),
    onLove: () => {},
    onBuy: () => {},
    inCart: () => false,
    onAddToCart: () => {},
    onAddAllToCart: () => {},
    onSelect: () => {},
    onClose: () => {},
    hasPhoto: true,
  }));
}
