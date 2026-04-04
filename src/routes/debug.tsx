import { createFileRoute } from "@tanstack/react-router";
import DebugPage from "../pages/debug/DebugPage";

export const Route = createFileRoute("/debug")({
  component: DebugPage,
});
