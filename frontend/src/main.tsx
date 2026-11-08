import { App } from "./App";
import { AuthProvider } from "./state/AuthContext";
import "./styles/global.css";

import { createRoot } from "react-dom/client";

const container = document.getElementById("root");
if (!container) throw new Error("Missing #root element");

createRoot(container).render(
  <AuthProvider>
    <App />
  </AuthProvider>,
);
