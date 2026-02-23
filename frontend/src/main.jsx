import React from "react";
import { createRoot } from "react-dom/client";
import { ClerkProvider } from "@clerk/clerk-react";

import App from "./App.jsx";
import "./styles.css";

const clerkPublishableKey = String(import.meta.env.VITE_CLERK_PUBLISHABLE_KEY || "").trim();

const appTree = (
  <React.StrictMode>
    <App clerkEnabled={Boolean(clerkPublishableKey)} />
  </React.StrictMode>
);

createRoot(document.getElementById("root")).render(
  clerkPublishableKey ? (
    <ClerkProvider publishableKey={clerkPublishableKey}>
      {appTree}
    </ClerkProvider>
  ) : (
    appTree
  )
);
