/**
 * Route table: 11 primary destinations matching the Phase 12B navigation
 * contract. Pages themselves enforce honesty about backend capabilities.
 */
import type { RouteDef } from "./router";
import { OverviewPage } from "./pages/Overview";
import { ForecastsPage } from "./pages/Forecasts";
import { InventoryPage } from "./pages/Inventory";
import { SuppliersPage } from "./pages/Suppliers";
import { ProcurementPage } from "./pages/Procurement";
import { RiskPage } from "./pages/Risk";
import { SimulationPage } from "./pages/Simulation";
import { ReplayPage } from "./pages/Replay";
import { OptimizationPage } from "./pages/Optimization";
import { CopilotPage } from "./pages/Copilot";
import { SettingsPage } from "./pages/Settings";

export const routes: RouteDef[] = [
  { path: "/overview", render: () => <OverviewPage /> },
  { path: "/forecasts", render: () => <ForecastsPage /> },
  { path: "/inventory", render: () => <InventoryPage /> },
  { path: "/suppliers", render: () => <SuppliersPage /> },
  { path: "/procurement", render: () => <ProcurementPage /> },
  { path: "/risk", render: () => <RiskPage /> },
  { path: "/simulation", render: () => <SimulationPage /> },
  { path: "/replay", render: () => <ReplayPage /> },
  { path: "/optimization", render: () => <OptimizationPage /> },
  { path: "/copilot", render: () => <CopilotPage /> },
  { path: "/settings", render: () => <SettingsPage /> },
];
