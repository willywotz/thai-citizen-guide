import { createRoot } from "react-dom/client";

import App from "./App.tsx";
import "./index.css";

async function enableMocking(): Promise<void> {
  if (import.meta.env.VITE_USE_MOCKS !== "true") return;
  const { worker } = await import("./mocks/browser");
  await worker.start({ onUnhandledRequest: "bypass" });
}

enableMocking().then(() => {
  createRoot(document.getElementById("root")!).render(<App />);
});
