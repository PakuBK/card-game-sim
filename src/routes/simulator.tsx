import { createFileRoute } from "@tanstack/react-router";
import SimulatorPage from "../pages/simulator/SimulatorPage";

export const Route = createFileRoute("/simulator")({
  component: SimulatorPage,
});
