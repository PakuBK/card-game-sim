import { useEffect, useMemo, useState } from "react";
import { useMutation } from "@tanstack/react-query";

import { asApiErrorResponse, isHttpError } from "@/api/http";
import { postSimulate, type SimulationResponse } from "@/api/endpoints";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

import {
  addBuild,
  addItemDefinition,
  addItemEffect,
  addPlacementForItemAtSlot,
  addPlacementForItem,
  canPlaceItemAtSlot,
  deriveDamageSeries,
  duplicateBuild,
  getPlacementIndexAtSlot,
  getPlacementIndexByInstanceId,
  getBuild,
  loadWorkspace,
  materializeMatchupRequest,
  movePlacementToSlot,
  removeBuild,
  removeItemDefinition,
  removeItemEffect,
  removePlacement,
  saveWorkspace,
  setCompareSelection,
  setSelectedBuild,
  setSettings,
  updateBuildBoardWidth,
  updateBuildNotes,
  updateBuildStats,
  updateBuild,
  updateItemDefinition,
  updateItemEffect,
  updatePlacement,
  updateActiveBuildName,
  validateWorkspace,
  type BuildDraft,
  type BuildSide,
  type DamageSeries,
  type DamageSeriesPoint,
  type SimulatorWorkspace,
  type ValidationIssue,
} from "./simulator-workspace";

const EFFECT_TYPES = [
  "damage",
  "heal",
  "shield",
  "apply_burn",
  "apply_poison",
  "apply_item_slow",
  "apply_item_haste",
  "apply_item_freeze",
  "apply_item_charge",
  "apply_item_flight",
] as const;

const EFFECT_TARGETS = [
  "self",
  "opponent",
  "self_item",
  "opponent_item",
  "enemy_adjacent",
  "enemy_random",
  "self_random",
  "any_random",
  "self_small_item",
  "self_medium_item",
  "self_large_item",
  "self_left_most",
  "self_right_most",
  "enemy_small_item",
  "enemy_medium_item",
  "enemy_large_item",
  "enemy_left_most",
  "enemy_right_most",
  "any_small_item",
  "any_medium_item",
  "any_large_item",
  "any_left_most",
  "any_right_most",
] as const;

const STATUS_TYPES = ["burn", "poison"] as const;

type ItemMetric = NonNullable<
  SimulationResponse["runs"][number]["metrics"]["player_a"]["item_metrics"]
>[number];

type CompareMutationResult = {
  leftResponse: SimulationResponse;
  rightResponse: SimulationResponse;
};

type BuildEditorSection =
  | "stats"
  | "board"
  | "placements"
  | "item_definitions"
  | "initial_statuses"
  | "settings"
  | "request";

type BuildApiIssue = {
  side?: BuildSide;
  section: BuildEditorSection;
  message: string;
};

type BoardPainterProps = {
  build: BuildDraft;
  selectedItemId?: string;
  selectedPlacementId?: string;
  onSlotClick?: (slot: number) => void;
  onPlacementClick?: (itemInstanceId: string) => void;
};

function formatIso(iso: string | undefined): string {
  if (!iso) return "";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleString();
}

function formatNumber(value: number | undefined, digits = 1): string {
  if (typeof value !== "number") return "-";
  return value.toFixed(digits);
}

function sideLabel(side: BuildSide): string {
  return side === "player_a" ? "Player A" : "Player B";
}

function formatIssueKey(issue: ValidationIssue): string {
  return `${issue.side}:${issue.buildId}:${issue.path}`;
}

function summarizeIssueCount(issues: ValidationIssue[]): string {
  if (issues.length === 0) return "No validation issues";
  return `${issues.length} issue${issues.length === 1 ? "" : "s"}`;
}

function getBuildIssues(
  issues: ValidationIssue[],
  side: BuildSide,
  buildId: string,
): ValidationIssue[] {
  return issues.filter((issue) => issue.side === side && issue.buildId === buildId);
}

function getBuildIssueSummary(issues: ValidationIssue[], side: BuildSide, buildId: string): string {
  const count = getBuildIssues(issues, side, buildId).length;
  return count === 0 ? "clean" : `${count} issue${count === 1 ? "" : "s"}`;
}

function getItemById(build: BuildDraft, itemId: string) {
  return build.item_definitions.find((item) => item.id === itemId);
}

function sectionTitle(section: BuildEditorSection): string {
  if (section === "stats") return "Stats";
  if (section === "board") return "Board";
  if (section === "placements") return "Placements";
  if (section === "item_definitions") return "Item definitions";
  if (section === "initial_statuses") return "Initial statuses";
  if (section === "settings") return "Simulation settings";
  return "Request";
}

function mapLocationToIssue(
  location: (string | number)[] | undefined | null,
  message: string,
): BuildApiIssue {
  if (!location || location.length === 0) {
    return { section: "request", message };
  }

  const normalized = location[0] === "body" ? location.slice(1) : [...location];
  if (normalized.length === 0) return { section: "request", message };

  const first = normalized[0];
  if (
    first === "seed" ||
    first === "runs" ||
    first === "max_time_seconds" ||
    first === "max_events" ||
    first === "combat_log_limit"
  ) {
    return { section: "settings", message };
  }

  if (first !== "players") {
    if (first === "item_definitions") return { section: "item_definitions", message };
    return { section: "request", message };
  }

  const side = normalized[1] === 0 ? "player_a" : normalized[1] === 1 ? "player_b" : undefined;
  const sectionToken = normalized[2];

  if (sectionToken === "stats") return { side, section: "stats", message };
  if (sectionToken === "board") {
    if (normalized[3] === "placements") return { side, section: "placements", message };
    return { side, section: "board", message };
  }
  if (sectionToken === "item_definitions") return { side, section: "item_definitions", message };
  if (sectionToken === "initial_statuses") return { side, section: "initial_statuses", message };

  return { side, section: "request", message };
}

function parseApiIssues(error: unknown): BuildApiIssue[] {
  if (!isHttpError(error)) return [];

  const payload = asApiErrorResponse(error.body);
  if (!payload?.error) {
    return [{ section: "request", message: error.message }];
  }

  const issues = payload.error.details?.map((detail) =>
    mapLocationToIssue(detail.location ?? undefined, detail.message),
  );

  if (issues && issues.length > 0) return issues;

  return [{ section: "request", message: payload.error.message || error.message }];
}

function issueFingerprint(issue: BuildApiIssue): string {
  return `${issue.side ?? "all"}:${issue.section}:${issue.message}`;
}

function sectionIssuesForSide(
  issues: BuildApiIssue[],
  side: BuildSide,
  section: BuildEditorSection,
): string[] {
  return issues
    .filter((issue) => issue.section === section && (!issue.side || issue.side === side))
    .map((issue) => issue.message);
}

function SectionErrorList({
  section,
  messages,
}: {
  section: BuildEditorSection;
  messages: string[];
}) {
  if (messages.length === 0) return null;
  return (
    <div className="rounded-lg border border-destructive/40 bg-destructive/5 px-3 py-2 text-xs text-destructive">
      <div className="font-medium">API guidance: {sectionTitle(section)}</div>
      <ul className="mt-1 space-y-1">
        {messages.map((message, index) => (
          <li key={`${section}-${index}`}>{message}</li>
        ))}
      </ul>
    </div>
  );
}

function buildBoardSlots(
  build: BuildDraft,
): Array<{ slot: number; label: string; occupied: boolean }> {
  const slots = Array.from({ length: build.board.width }, (_, slot) => ({
    slot,
    label: String(slot + 1),
    occupied: false,
  }));

  build.board.placements.forEach((placement) => {
    const item = getItemById(build, placement.item_definition_id);
    const size = item?.size ?? 1;
    for (let slot = placement.start_slot; slot < placement.start_slot + size; slot += 1) {
      if (slots[slot]) {
        slots[slot] = { ...slots[slot], occupied: true };
      }
    }
  });

  return slots;
}

function BoardPainter({
  build,
  selectedItemId,
  selectedPlacementId,
  onSlotClick,
  onPlacementClick,
}: BoardPainterProps) {
  const slots = buildBoardSlots(build);
  const selectedPlacementIndex = selectedPlacementId
    ? getPlacementIndexByInstanceId(build, selectedPlacementId)
    : -1;

  return (
    <div className="rounded-2xl border border-border/70 bg-[linear-gradient(180deg,var(--card),var(--muted)/45%)] p-3 shadow-sm">
      <div className="mb-3 flex items-center justify-between gap-3 text-xs uppercase tracking-wide text-muted-foreground">
        <span>{build.name}</span>
        <span>{build.board.width} slots</span>
      </div>
      <div
        className="grid gap-1"
        style={{ gridTemplateColumns: `repeat(${build.board.width}, minmax(0, 1fr))` }}
      >
        {slots.map((slot) => (
          <div
            key={`slot-${slot.slot}`}
            className={[
              "flex h-12 items-end justify-center rounded-lg border px-1 pb-1 text-[10px] transition-colors",
              slot.occupied
                ? "border-primary/35 bg-primary/8"
                : "border-border/70 bg-background/60",
              onSlotClick ? "cursor-pointer hover:border-primary/60" : "",
              !slot.occupied && selectedItemId
                ? canPlaceItemAtSlot(build, selectedItemId, slot.slot)
                  ? "ring-1 ring-emerald-500/35"
                  : "ring-1 ring-destructive/25"
                : "",
            ].join(" ")}
            onClick={() => onSlotClick?.(slot.slot)}
          >
            {slot.label}
          </div>
        ))}
        {build.board.placements.map((placement) => {
          const item = getItemById(build, placement.item_definition_id);
          if (!item) return null;

          return (
            <div
              key={placement.item_instance_id}
              className={[
                "z-10 flex h-12 items-center justify-between gap-2 rounded-lg border px-2 text-[11px] font-medium shadow-sm transition-colors",
                selectedPlacementIndex >= 0 &&
                build.board.placements[selectedPlacementIndex]?.item_instance_id ===
                  placement.item_instance_id
                  ? "border-amber-500 bg-amber-500/20"
                  : "border-primary/50 bg-primary/14",
                onPlacementClick ? "cursor-pointer" : "",
              ].join(" ")}
              style={{ gridColumn: `${placement.start_slot + 1} / span ${item.size}` }}
              onClick={() => onPlacementClick?.(placement.item_instance_id)}
            >
              <span className="truncate">{item.name}</span>
              <span className="shrink-0 rounded-full bg-background/80 px-1.5 py-0.5 text-[10px]">
                {placement.item_instance_id}
              </span>
            </div>
          );
        })}
      </div>
      <div className="mt-3 flex flex-wrap gap-2 text-[11px] text-muted-foreground">
        {build.board.placements.map((placement) => {
          const item = getItemById(build, placement.item_definition_id);
          return (
            <span
              key={`legend-${placement.item_instance_id}`}
              className="rounded-full border border-border/70 px-2 py-1"
            >
              {placement.item_instance_id} = {item?.name ?? placement.item_definition_id} at slot{" "}
              {placement.start_slot + 1}
            </span>
          );
        })}
        {build.board.placements.length === 0 ? <span>No placements yet.</span> : null}
      </div>
    </div>
  );
}

function SeriesPath({
  series,
  width,
  height,
  color,
  dash,
}: {
  series: DamageSeriesPoint[];
  width: number;
  height: number;
  color: string;
  dash?: string;
}) {
  if (series.length === 0) return null;
  const padding = { top: 12, right: 12, bottom: 26, left: 44 };
  const usableWidth = width - padding.left - padding.right;
  const usableHeight = height - padding.top - padding.bottom;
  const maxTime = Math.max(series[series.length - 1]?.time ?? 0, 1);
  const maxValue = Math.max(...series.map((point) => point.value), 1);

  const path = series
    .map((point, index) => {
      const x = padding.left + (point.time / maxTime) * usableWidth;
      const y = padding.top + usableHeight - (point.value / maxValue) * usableHeight;
      return `${index === 0 ? "M" : "L"}${x.toFixed(2)} ${y.toFixed(2)}`;
    })
    .join(" ");

  return <path d={path} fill="none" stroke={color} strokeWidth="2.5" strokeDasharray={dash} />;
}

function DamageComparisonChart({
  leftSeries,
  rightSeries,
  overlayIndex,
}: {
  leftSeries: DamageSeries;
  rightSeries: DamageSeries;
  overlayIndex: number;
}) {
  const width = 720;
  const height = 300;
  const leftOverlay = leftSeries.overlay;
  const rightOverlay = rightSeries.overlay;
  const xMax = Math.max(leftSeries.maxTime, rightSeries.maxTime, 1);
  const yMax = Math.max(leftSeries.totalDamage, rightSeries.totalDamage, 1);
  const padding = { top: 12, right: 12, bottom: 26, left: 44 };
  const usableWidth = width - padding.left - padding.right;
  const usableHeight = height - padding.top - padding.bottom;
  const ticks = [0, 0.25, 0.5, 0.75, 1];

  function xFor(time: number): number {
    return padding.left + (time / xMax) * usableWidth;
  }

  function yFor(value: number): number {
    return padding.top + usableHeight - (value / yMax) * usableHeight;
  }

  return (
    <div className="overflow-hidden rounded-2xl border border-border/70 bg-background/80">
      <div className="border-b border-border/70 px-4 py-3 text-sm font-medium">
        Damage over time
      </div>
      <div className="overflow-auto px-4 py-4">
        <svg viewBox={`0 0 ${width} ${height}`} className="h-auto w-full" style={{ minWidth: 680 }}>
          <rect x={0} y={0} width={width} height={height} rx={18} fill="transparent" />
          {ticks.map((tick) => {
            const y = yFor(yMax * tick);
            const label = `${Math.round(yMax * tick)}`;
            return (
              <g key={tick}>
                <line
                  x1={padding.left}
                  x2={width - padding.right}
                  y1={y}
                  y2={y}
                  stroke="color-mix(in srgb, var(--border) 55%, transparent)"
                  strokeDasharray="3 4"
                />
                <text
                  x={padding.left - 8}
                  y={y + 4}
                  textAnchor="end"
                  className="fill-muted-foreground text-[10px]"
                >
                  {label}
                </text>
              </g>
            );
          })}
          {[0, 0.25, 0.5, 0.75, 1].map((tick) => {
            const x = xFor(xMax * tick);
            const label = `${(xMax * tick).toFixed(1)}s`;
            return (
              <g key={tick}>
                <line
                  x1={x}
                  x2={x}
                  y1={padding.top}
                  y2={height - padding.bottom}
                  stroke="color-mix(in srgb, var(--border) 40%, transparent)"
                  strokeDasharray="3 4"
                />
                <text
                  x={x}
                  y={height - 8}
                  textAnchor="middle"
                  className="fill-muted-foreground text-[10px]"
                >
                  {label}
                </text>
              </g>
            );
          })}
          <SeriesPath
            series={leftSeries.median}
            width={width}
            height={height}
            color="var(--chart-1)"
          />
          <SeriesPath
            series={rightSeries.median}
            width={width}
            height={height}
            color="var(--chart-3)"
          />
          {leftOverlay.length > 0 ? (
            <SeriesPath
              series={leftOverlay}
              width={width}
              height={height}
              color="var(--chart-1)"
              dash="6 4"
            />
          ) : null}
          {rightOverlay.length > 0 ? (
            <SeriesPath
              series={rightOverlay}
              width={width}
              height={height}
              color="var(--chart-3)"
              dash="6 4"
            />
          ) : null}
        </svg>
      </div>
      <div className="flex flex-wrap gap-3 border-t border-border/70 px-4 py-3 text-xs text-muted-foreground">
        <span className="inline-flex items-center gap-2">
          <span
            className="h-2.5 w-2.5 rounded-full"
            style={{ backgroundColor: "var(--chart-1)" }}
          />
          Left median
        </span>
        <span className="inline-flex items-center gap-2">
          <span
            className="h-2.5 w-2.5 rounded-full"
            style={{ backgroundColor: "var(--chart-3)" }}
          />
          Right median
        </span>
        <span className="inline-flex items-center gap-2">
          <span
            className="h-2.5 w-2.5 rounded-full border"
            style={{ borderColor: "var(--chart-1)" }}
          />
          Left overlay run {overlayIndex + 1}
        </span>
        <span className="inline-flex items-center gap-2">
          <span
            className="h-2.5 w-2.5 rounded-full border"
            style={{ borderColor: "var(--chart-3)" }}
          />
          Right overlay run {overlayIndex + 1}
        </span>
      </div>
    </div>
  );
}

function MetricList({ items }: { items: ItemMetric[] }) {
  if (items.length === 0) return <li>none</li>;

  return items.map((itemMetric) => (
    <li key={itemMetric.item_instance_id}>
      {itemMetric.item_instance_id}: total {formatNumber(itemMetric.damage_done?.total, 1)} (direct{" "}
      {formatNumber(itemMetric.damage_done?.direct, 1)}, burn{" "}
      {formatNumber(itemMetric.damage_done?.burn, 1)}, poison{" "}
      {formatNumber(itemMetric.damage_done?.poison, 1)})
    </li>
  ));
}

function SummaryCard({ title, response }: { title: string; response: SimulationResponse }) {
  return (
    <Card size="sm">
      <CardHeader className="border-b border-border/70">
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 pt-4 text-sm">
        <div className="grid gap-2 sm:grid-cols-2">
          <div>Runs: {response.summary.run_count}</div>
          <div>Player A win rate: {response.summary.player_a_win_rate}</div>
          <div>Player B win rate: {response.summary.player_b_win_rate}</div>
          <div>Draw rate: {response.summary.draw_rate}</div>
          <div>Duration p50: {response.summary.duration_seconds.p50}</div>
          <div>Duration p95: {response.summary.duration_seconds.p95}</div>
        </div>
      </CardContent>
    </Card>
  );
}

function BuildSelectorPanel({
  workspace,
  setWorkspace,
  issues,
  apiIssues,
}: {
  workspace: SimulatorWorkspace;
  setWorkspace: React.Dispatch<React.SetStateAction<SimulatorWorkspace>>;
  issues: ValidationIssue[];
  apiIssues: BuildApiIssue[];
}) {
  const settingsApiIssues = apiIssues.filter((issue) => issue.section === "settings");

  return (
    <Card>
      <CardHeader className="border-b border-border/70">
        <CardTitle>Build Library</CardTitle>
      </CardHeader>
      <CardContent className="space-y-5 pt-4 text-sm">
        {(["player_a", "player_b"] as const).map((side) => {
          const builds = workspace.builds[side];
          const selectedId = workspace.selectedBuildIds[side];
          return (
            <div
              key={side}
              className="space-y-3 rounded-2xl border border-border/70 bg-background/50 p-3"
            >
              <div className="flex items-center justify-between gap-2">
                <div>
                  <div className="font-medium">{sideLabel(side)}</div>
                  <div className="text-xs text-muted-foreground">
                    {builds.length} version{builds.length === 1 ? "" : "s"}
                  </div>
                </div>
                <button
                  type="button"
                  className="rounded-full border border-border px-3 py-1.5 text-xs"
                  onClick={() => setWorkspace((current) => addBuild(current, side))}
                >
                  New version
                </button>
              </div>
              <div className="space-y-2">
                {builds.map((build) => {
                  const selected = build.id === selectedId;
                  const issueSummary = getBuildIssueSummary(issues, side, build.id);
                  return (
                    <div
                      key={build.id}
                      className={[
                        "rounded-xl border p-3 transition-colors",
                        selected
                          ? "border-primary/70 bg-primary/8"
                          : "border-border/70 bg-background/70",
                      ].join(" ")}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div>
                          <div className="font-medium">{build.name}</div>
                          <div className="text-xs text-muted-foreground">
                            Updated {formatIso(build.updated_at)}
                          </div>
                          <div className="mt-1 text-xs text-muted-foreground">{issueSummary}</div>
                        </div>
                        <div className="flex flex-wrap justify-end gap-2">
                          <button
                            type="button"
                            className="rounded-full border border-border px-2.5 py-1 text-xs"
                            onClick={() =>
                              setWorkspace((current) => setSelectedBuild(current, side, build.id))
                            }
                          >
                            Select
                          </button>
                          <button
                            type="button"
                            className="rounded-full border border-border px-2.5 py-1 text-xs"
                            onClick={() =>
                              setWorkspace((current) => duplicateBuild(current, side, build.id))
                            }
                          >
                            Save copy
                          </button>
                          <button
                            type="button"
                            className="rounded-full border border-border px-2.5 py-1 text-xs"
                            onClick={() =>
                              setWorkspace((current) => removeBuild(current, side, build.id))
                            }
                            disabled={builds.length <= 1}
                          >
                            Delete
                          </button>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })}

        <div className="rounded-2xl border border-border/70 bg-background/50 p-3">
          <div className="font-medium">Simulation Settings</div>
          <div className="mt-2">
            <SectionErrorList
              section="settings"
              messages={settingsApiIssues.map((issue) => issue.message)}
            />
          </div>
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            <label className="space-y-1 text-xs">
              <span className="text-muted-foreground">Seed</span>
              <input
                className="w-full rounded-lg border border-border px-3 py-2 text-sm"
                type="number"
                value={workspace.settings.seed}
                onChange={(event) =>
                  setWorkspace((current) =>
                    setSettings(current, { seed: Number(event.target.value) }),
                  )
                }
              />
            </label>
            <label className="space-y-1 text-xs">
              <span className="text-muted-foreground">Runs</span>
              <input
                className="w-full rounded-lg border border-border px-3 py-2 text-sm"
                type="number"
                min={1}
                value={workspace.settings.runs}
                onChange={(event) =>
                  setWorkspace((current) =>
                    setSettings(current, { runs: Number(event.target.value) }),
                  )
                }
              />
            </label>
            <label className="space-y-1 text-xs">
              <span className="text-muted-foreground">Max time</span>
              <input
                className="w-full rounded-lg border border-border px-3 py-2 text-sm"
                type="number"
                min={1}
                step={0.5}
                value={workspace.settings.max_time_seconds}
                onChange={(event) =>
                  setWorkspace((current) =>
                    setSettings(current, { max_time_seconds: Number(event.target.value) }),
                  )
                }
              />
            </label>
            <label className="space-y-1 text-xs">
              <span className="text-muted-foreground">Max events</span>
              <input
                className="w-full rounded-lg border border-border px-3 py-2 text-sm"
                type="number"
                min={1}
                value={workspace.settings.max_events}
                onChange={(event) =>
                  setWorkspace((current) =>
                    setSettings(current, { max_events: Number(event.target.value) }),
                  )
                }
              />
            </label>
            <label className="space-y-1 text-xs sm:col-span-2">
              <span className="text-muted-foreground">Combat log limit</span>
              <input
                className="w-full rounded-lg border border-border px-3 py-2 text-sm"
                type="number"
                min={1}
                value={workspace.settings.combat_log_limit}
                onChange={(event) =>
                  setWorkspace((current) =>
                    setSettings(current, { combat_log_limit: Number(event.target.value) }),
                  )
                }
              />
            </label>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function BuildEditor({
  setWorkspace,
  side,
  build,
  issues,
  apiIssues,
  selectedItemId,
  selectedPlacementId,
  onSelectedItemChange,
  onBoardSlotClick,
  onPlacementSelect,
}: {
  setWorkspace: React.Dispatch<React.SetStateAction<SimulatorWorkspace>>;
  side: BuildSide;
  build: BuildDraft;
  issues: ValidationIssue[];
  apiIssues: BuildApiIssue[];
  selectedItemId?: string;
  selectedPlacementId?: string;
  onSelectedItemChange: (itemId: string) => void;
  onBoardSlotClick: (slot: number) => void;
  onPlacementSelect: (itemInstanceId: string) => void;
}) {
  const buildIssues = getBuildIssues(issues, side, build.id);
  const statsApiIssues = sectionIssuesForSide(apiIssues, side, "stats");
  const boardApiIssues = sectionIssuesForSide(apiIssues, side, "board");
  const placementApiIssues = sectionIssuesForSide(apiIssues, side, "placements");
  const itemApiIssues = sectionIssuesForSide(apiIssues, side, "item_definitions");
  const statusApiIssues = sectionIssuesForSide(apiIssues, side, "initial_statuses");
  const requestApiIssues = sectionIssuesForSide(apiIssues, side, "request");

  return (
    <Card>
      <CardHeader className="border-b border-border/70">
        <CardTitle>{sideLabel(side)} build editor</CardTitle>
      </CardHeader>
      <CardContent className="space-y-5 pt-4">
        <div className="grid gap-3 md:grid-cols-2">
          <label className="space-y-1 text-xs">
            <span className="text-muted-foreground">Build name</span>
            <input
              className="w-full rounded-lg border border-border px-3 py-2 text-sm"
              value={build.name}
              onChange={(event) =>
                setWorkspace((current) =>
                  updateActiveBuildName(current, side, build.id, event.target.value),
                )
              }
            />
          </label>
          <label className="space-y-1 text-xs">
            <span className="text-muted-foreground">Notes</span>
            <input
              className="w-full rounded-lg border border-border px-3 py-2 text-sm"
              value={build.notes}
              onChange={(event) =>
                setWorkspace((current) =>
                  updateBuildNotes(current, side, build.id, event.target.value),
                )
              }
            />
          </label>
          <label className="space-y-1 text-xs">
            <span className="text-muted-foreground">Max health</span>
            <input
              className="w-full rounded-lg border border-border px-3 py-2 text-sm"
              type="number"
              min={1}
              value={build.stats.max_health}
              onChange={(event) =>
                setWorkspace((current) =>
                  updateBuildStats(current, side, build.id, {
                    max_health: Number(event.target.value),
                  }),
                )
              }
            />
          </label>
          <label className="space-y-1 text-xs">
            <span className="text-muted-foreground">Start shield</span>
            <input
              className="w-full rounded-lg border border-border px-3 py-2 text-sm"
              type="number"
              min={0}
              value={build.stats.start_shield}
              onChange={(event) =>
                setWorkspace((current) =>
                  updateBuildStats(current, side, build.id, {
                    start_shield: Number(event.target.value),
                  }),
                )
              }
            />
          </label>
          <label className="space-y-1 text-xs">
            <span className="text-muted-foreground">Regen / second</span>
            <input
              className="w-full rounded-lg border border-border px-3 py-2 text-sm"
              type="number"
              min={0}
              step={0.25}
              value={build.stats.regeneration_per_second}
              onChange={(event) =>
                setWorkspace((current) =>
                  updateBuildStats(current, side, build.id, {
                    regeneration_per_second: Number(event.target.value),
                  }),
                )
              }
            />
          </label>
          <label className="space-y-1 text-xs">
            <span className="text-muted-foreground">Board width</span>
            <input
              className="w-full rounded-lg border border-border px-3 py-2 text-sm"
              type="number"
              min={1}
              max={20}
              value={build.board.width}
              onChange={(event) =>
                setWorkspace((current) =>
                  updateBuildBoardWidth(current, side, build.id, Number(event.target.value)),
                )
              }
            />
          </label>
        </div>
        <SectionErrorList section="stats" messages={statsApiIssues} />

        <div className="space-y-2">
          <div className="flex items-center justify-between gap-2">
            <div className="text-sm font-medium">Board preview</div>
            <div className="flex flex-wrap items-center gap-2">
              <select
                className="rounded-full border border-border px-3 py-1.5 text-xs"
                value={selectedItemId}
                onChange={(event) => onSelectedItemChange(event.target.value)}
              >
                {build.item_definitions.map((item) => (
                  <option key={item.id} value={item.id}>
                    Place: {item.name}
                  </option>
                ))}
              </select>
              <button
                type="button"
                className="rounded-full border border-border px-3 py-1.5 text-xs"
                onClick={() =>
                  setWorkspace((current) =>
                    addPlacementForItem(
                      current,
                      side,
                      build.id,
                      selectedItemId ?? build.item_definitions[0]?.id ?? "starter",
                    ),
                  )
                }
              >
                Add placement
              </button>
            </div>
          </div>
          <div className="text-xs text-muted-foreground">
            Click an occupied slot to pick a move source, then click an empty slot to move it. Click
            an empty slot with a selected item to place a new item instance.
          </div>
          <SectionErrorList section="board" messages={boardApiIssues} />
          <BoardPainter
            build={build}
            selectedItemId={selectedItemId}
            selectedPlacementId={selectedPlacementId}
            onSlotClick={onBoardSlotClick}
            onPlacementClick={onPlacementSelect}
          />
        </div>

        <div className="space-y-2">
          <div className="flex items-center justify-between gap-2">
            <div className="text-sm font-medium">Item definitions</div>
            <button
              type="button"
              className="rounded-full border border-border px-3 py-1.5 text-xs"
              onClick={() => setWorkspace((current) => addItemDefinition(current, side, build.id))}
            >
              Add item
            </button>
          </div>
          <SectionErrorList section="item_definitions" messages={itemApiIssues} />
          <div className="space-y-3">
            {build.item_definitions.map((item) => (
              <div
                key={item.id}
                className="rounded-2xl border border-border/70 bg-background/50 p-3"
              >
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div className="grid flex-1 gap-2 md:grid-cols-2">
                    <label className="space-y-1 text-xs">
                      <span className="text-muted-foreground">Id</span>
                      <input
                        className="w-full rounded-lg border border-border px-3 py-2 text-sm"
                        value={item.id}
                        onChange={(event) =>
                          setWorkspace((current) =>
                            updateItemDefinition(current, side, build.id, item.id, {
                              id: event.target.value,
                            }),
                          )
                        }
                      />
                    </label>
                    <label className="space-y-1 text-xs">
                      <span className="text-muted-foreground">Name</span>
                      <input
                        className="w-full rounded-lg border border-border px-3 py-2 text-sm"
                        value={item.name}
                        onChange={(event) =>
                          setWorkspace((current) =>
                            updateItemDefinition(current, side, build.id, item.id, {
                              name: event.target.value,
                            }),
                          )
                        }
                      />
                    </label>
                    <label className="space-y-1 text-xs">
                      <span className="text-muted-foreground">Size</span>
                      <input
                        className="w-full rounded-lg border border-border px-3 py-2 text-sm"
                        type="number"
                        min={1}
                        max={3}
                        value={item.size}
                        onChange={(event) =>
                          setWorkspace((current) =>
                            updateItemDefinition(current, side, build.id, item.id, {
                              size: Number(event.target.value),
                            }),
                          )
                        }
                      />
                    </label>
                    <label className="space-y-1 text-xs">
                      <span className="text-muted-foreground">Cooldown</span>
                      <input
                        className="w-full rounded-lg border border-border px-3 py-2 text-sm"
                        type="number"
                        min={0.1}
                        step={0.1}
                        value={item.cooldown_seconds}
                        onChange={(event) =>
                          setWorkspace((current) =>
                            updateItemDefinition(current, side, build.id, item.id, {
                              cooldown_seconds: Number(event.target.value),
                            }),
                          )
                        }
                      />
                    </label>
                  </div>
                  <button
                    type="button"
                    className="rounded-full border border-border px-3 py-1.5 text-xs"
                    onClick={() =>
                      setWorkspace((current) =>
                        removeItemDefinition(current, side, build.id, item.id),
                      )
                    }
                  >
                    Remove item
                  </button>
                </div>

                <div className="mt-3 flex items-center justify-between gap-2">
                  <div className="text-xs font-medium text-muted-foreground">Effects</div>
                  <button
                    type="button"
                    className="rounded-full border border-border px-3 py-1.5 text-xs"
                    onClick={() =>
                      setWorkspace((current) => addItemEffect(current, side, build.id, item.id))
                    }
                  >
                    Add effect
                  </button>
                </div>
                <div className="mt-2 space-y-2">
                  {item.effects.map((effect, effectIndex) => (
                    <div
                      key={`${item.id}-effect-${effectIndex}`}
                      className="grid gap-2 md:grid-cols-[160px_1fr_120px_auto]"
                    >
                      <select
                        className="rounded-lg border border-border px-3 py-2 text-sm"
                        value={effect.type}
                        onChange={(event) =>
                          setWorkspace((current) =>
                            updateItemEffect(current, side, build.id, item.id, effectIndex, {
                              type: event.target.value as (typeof EFFECT_TYPES)[number],
                            }),
                          )
                        }
                      >
                        {EFFECT_TYPES.map((type) => (
                          <option key={type} value={type}>
                            {type}
                          </option>
                        ))}
                      </select>
                      <select
                        className="rounded-lg border border-border px-3 py-2 text-sm"
                        value={effect.target}
                        onChange={(event) =>
                          setWorkspace((current) =>
                            updateItemEffect(current, side, build.id, item.id, effectIndex, {
                              target: event.target.value as (typeof EFFECT_TARGETS)[number],
                            }),
                          )
                        }
                      >
                        {EFFECT_TARGETS.map((target) => (
                          <option key={target} value={target}>
                            {target}
                          </option>
                        ))}
                      </select>
                      <input
                        className="rounded-lg border border-border px-3 py-2 text-sm"
                        type="number"
                        min={0.1}
                        step={0.1}
                        value={effect.magnitude}
                        onChange={(event) =>
                          setWorkspace((current) =>
                            updateItemEffect(current, side, build.id, item.id, effectIndex, {
                              magnitude: Number(event.target.value),
                            }),
                          )
                        }
                      />
                      <button
                        type="button"
                        className="rounded-lg border border-border px-3 py-2 text-xs"
                        onClick={() =>
                          setWorkspace((current) =>
                            removeItemEffect(current, side, build.id, item.id, effectIndex),
                          )
                        }
                      >
                        Remove
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            ))}
            {build.item_definitions.length === 0 ? (
              <div className="text-xs text-muted-foreground">No items defined yet.</div>
            ) : null}
          </div>
        </div>

        <div className="space-y-2">
          <div className="flex items-center justify-between gap-2">
            <div className="text-sm font-medium">Placements</div>
            <button
              type="button"
              className="rounded-full border border-border px-3 py-1.5 text-xs"
              onClick={() =>
                setWorkspace((current) =>
                  addPlacementForItem(
                    current,
                    side,
                    build.id,
                    build.item_definitions[0]?.id ?? "starter",
                  ),
                )
              }
            >
              Add placement row
            </button>
          </div>
          <SectionErrorList section="placements" messages={placementApiIssues} />
          <div className="space-y-2">
            {build.board.placements.map((placement, placementIndex) => (
              <div
                key={placement.item_instance_id}
                className="grid gap-2 md:grid-cols-[1.4fr_1fr_1fr_auto]"
              >
                <input
                  className="rounded-lg border border-border px-3 py-2 text-sm"
                  value={placement.item_instance_id}
                  onChange={(event) =>
                    setWorkspace((current) =>
                      updatePlacement(current, side, build.id, placementIndex, {
                        item_instance_id: event.target.value,
                      }),
                    )
                  }
                />
                <select
                  className="rounded-lg border border-border px-3 py-2 text-sm"
                  value={placement.item_definition_id}
                  onChange={(event) =>
                    setWorkspace((current) =>
                      updatePlacement(current, side, build.id, placementIndex, {
                        item_definition_id: event.target.value,
                      }),
                    )
                  }
                >
                  {build.item_definitions.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.name}
                    </option>
                  ))}
                </select>
                <input
                  className="rounded-lg border border-border px-3 py-2 text-sm"
                  type="number"
                  min={0}
                  value={placement.start_slot}
                  onChange={(event) =>
                    setWorkspace((current) =>
                      updatePlacement(current, side, build.id, placementIndex, {
                        start_slot: Number(event.target.value),
                      }),
                    )
                  }
                />
                <button
                  type="button"
                  className="rounded-lg border border-border px-3 py-2 text-xs"
                  onClick={() =>
                    setWorkspace((current) =>
                      removePlacement(current, side, build.id, placementIndex),
                    )
                  }
                >
                  Remove
                </button>
              </div>
            ))}
            {build.board.placements.length === 0 ? (
              <div className="text-xs text-muted-foreground">No placements yet.</div>
            ) : null}
          </div>
        </div>

        <div className="space-y-2">
          <div className="flex items-center justify-between gap-2">
            <div className="text-sm font-medium">Initial statuses</div>
            <button
              type="button"
              className="rounded-full border border-border px-3 py-1.5 text-xs"
              onClick={() =>
                setWorkspace((current) =>
                  updateBuild(current, side, build.id, (draft) => ({
                    ...draft,
                    initial_statuses: [...draft.initial_statuses, { type: "burn", value: 1 }],
                  })),
                )
              }
            >
              Add status
            </button>
          </div>
          <SectionErrorList section="initial_statuses" messages={statusApiIssues} />
          <div className="space-y-2">
            {build.initial_statuses.map((status, statusIndex) => (
              <div
                key={`${status.type}-${statusIndex}`}
                className="grid gap-2 md:grid-cols-[1fr_1fr_auto]"
              >
                <select
                  className="rounded-lg border border-border px-3 py-2 text-sm"
                  value={status.type}
                  onChange={(event) =>
                    setWorkspace((current) =>
                      updateBuild(current, side, build.id, (draft) => ({
                        ...draft,
                        initial_statuses: draft.initial_statuses.map((entry, index) =>
                          index === statusIndex
                            ? {
                                ...entry,
                                type: event.target.value as (typeof STATUS_TYPES)[number],
                              }
                            : entry,
                        ),
                      })),
                    )
                  }
                >
                  {STATUS_TYPES.map((type) => (
                    <option key={type} value={type}>
                      {type}
                    </option>
                  ))}
                </select>
                <input
                  className="rounded-lg border border-border px-3 py-2 text-sm"
                  type="number"
                  min={0.1}
                  step={0.1}
                  value={status.value}
                  onChange={(event) =>
                    setWorkspace((current) =>
                      updateBuild(current, side, build.id, (draft) => ({
                        ...draft,
                        initial_statuses: draft.initial_statuses.map((entry, index) =>
                          index === statusIndex
                            ? { ...entry, value: Number(event.target.value) }
                            : entry,
                        ),
                      })),
                    )
                  }
                />
                <button
                  type="button"
                  className="rounded-lg border border-border px-3 py-2 text-xs"
                  onClick={() =>
                    setWorkspace((current) =>
                      updateBuild(current, side, build.id, (draft) => ({
                        ...draft,
                        initial_statuses: draft.initial_statuses.filter(
                          (_, index) => index !== statusIndex,
                        ),
                      })),
                    )
                  }
                >
                  Remove
                </button>
              </div>
            ))}
            {build.initial_statuses.length === 0 ? (
              <div className="text-xs text-muted-foreground">No starting statuses.</div>
            ) : null}
          </div>
        </div>

        {buildIssues.length > 0 ? (
          <div className="rounded-2xl border border-destructive/40 bg-destructive/5 p-3 text-xs text-destructive">
            <div className="font-medium">Validation issues</div>
            <ul className="mt-2 space-y-1">
              {buildIssues.slice(0, 6).map((issue) => (
                <li key={formatIssueKey(issue)}>
                  {issue.path}: {issue.message}
                </li>
              ))}
            </ul>
          </div>
        ) : null}
        <SectionErrorList section="request" messages={requestApiIssues} />
      </CardContent>
    </Card>
  );
}

function ResponseSummaryList({ response }: { response: SimulationResponse }) {
  return (
    <div className="space-y-4">
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <div className="rounded-2xl border border-border/70 bg-background/70 p-3 text-sm">
          Runs: {response.summary.run_count}
        </div>
        <div className="rounded-2xl border border-border/70 bg-background/70 p-3 text-sm">
          A win rate: {response.summary.player_a_win_rate}
        </div>
        <div className="rounded-2xl border border-border/70 bg-background/70 p-3 text-sm">
          B win rate: {response.summary.player_b_win_rate}
        </div>
        <div className="rounded-2xl border border-border/70 bg-background/70 p-3 text-sm">
          Draw rate: {response.summary.draw_rate}
        </div>
      </div>

      <div className="space-y-3">
        {response.runs.map((run) => {
          const playerA = run.players.find((player) => player.player_id === "player_a");
          const playerB = run.players.find((player) => player.player_id === "player_b");
          const playerAMetrics = run.metrics.player_a;
          const playerBMetrics = run.metrics.player_b;
          const playerADamage = playerAMetrics.damage_to_opponent ?? {
            total: 0,
            direct: 0,
            burn: 0,
            poison: 0,
          };
          const playerBDamage = playerBMetrics.damage_to_opponent ?? {
            total: 0,
            direct: 0,
            burn: 0,
            poison: 0,
          };

          return (
            <Card key={run.run_index} size="sm">
              <CardHeader className="border-b border-border/70">
                <CardTitle>Run {run.run_index + 1}</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4 pt-4 text-sm">
                <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-4">
                  <div>Winner: {run.winner_player_id}</div>
                  <div>Duration: {formatNumber(run.duration_seconds, 2)}s</div>
                  <div>Events: {run.metrics.total_events_processed}</div>
                  <div>Stop: {run.stop_reason}</div>
                </div>
                <div className="grid gap-4 xl:grid-cols-2">
                  <div className="space-y-2 rounded-2xl border border-border/70 bg-background/60 p-3">
                    <div className="font-medium">Player A</div>
                    <div className="text-xs text-muted-foreground">
                      damage {formatNumber(playerADamage.total, 1)} / direct{" "}
                      {formatNumber(playerADamage.direct, 1)} / burn{" "}
                      {formatNumber(playerADamage.burn, 1)} / poison{" "}
                      {formatNumber(playerADamage.poison, 1)}
                    </div>
                    <div className="text-xs text-muted-foreground">
                      final health {playerA?.health ?? "n/a"}
                    </div>
                    <div className="text-xs text-muted-foreground">
                      items: {playerAMetrics.item_uses}
                    </div>
                    <div className="text-xs text-muted-foreground">
                      statuses applied burn{" "}
                      {playerAMetrics.status_effects_applied?.burn?.applications ?? 0} / poison{" "}
                      {playerAMetrics.status_effects_applied?.poison?.applications ?? 0}
                    </div>
                    <ul className="space-y-1 text-xs text-muted-foreground">
                      <MetricList items={playerAMetrics.item_metrics ?? []} />
                    </ul>
                  </div>
                  <div className="space-y-2 rounded-2xl border border-border/70 bg-background/60 p-3">
                    <div className="font-medium">Player B</div>
                    <div className="text-xs text-muted-foreground">
                      damage {formatNumber(playerBDamage.total, 1)} / direct{" "}
                      {formatNumber(playerBDamage.direct, 1)} / burn{" "}
                      {formatNumber(playerBDamage.burn, 1)} / poison{" "}
                      {formatNumber(playerBDamage.poison, 1)}
                    </div>
                    <div className="text-xs text-muted-foreground">
                      final health {playerB?.health ?? "n/a"}
                    </div>
                    <div className="text-xs text-muted-foreground">
                      items: {playerBMetrics.item_uses}
                    </div>
                    <div className="text-xs text-muted-foreground">
                      statuses applied burn{" "}
                      {playerBMetrics.status_effects_applied?.burn?.applications ?? 0} / poison{" "}
                      {playerBMetrics.status_effects_applied?.poison?.applications ?? 0}
                    </div>
                    <ul className="space-y-1 text-xs text-muted-foreground">
                      <MetricList items={playerBMetrics.item_metrics ?? []} />
                    </ul>
                  </div>
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>
    </div>
  );
}

export default function SimulatorPage() {
  const [workspace, setWorkspace] = useState<SimulatorWorkspace>(() => loadWorkspace());
  const [overlayRunIndex, setOverlayRunIndex] = useState(0);
  const [selectedItemBySide, setSelectedItemBySide] = useState<Record<BuildSide, string>>({
    player_a: "",
    player_b: "",
  });
  const [selectedMoveSourceBySide, setSelectedMoveSourceBySide] = useState<
    Partial<Record<BuildSide, string>>
  >({});

  useEffect(() => {
    saveWorkspace(workspace);
  }, [workspace]);

  const validationIssues = useMemo(() => validateWorkspace(workspace), [workspace]);
  const hasBlockingIssues = validationIssues.length > 0;

  const activePlayerABuild =
    getBuild(workspace, "player_a", workspace.selectedBuildIds.player_a) ??
    workspace.builds.player_a[0];
  const activePlayerBBuild =
    getBuild(workspace, "player_b", workspace.selectedBuildIds.player_b) ??
    workspace.builds.player_b[0];
  const currentRequest = useMemo(() => {
    if (!activePlayerABuild || !activePlayerBBuild) return null;
    return materializeMatchupRequest({
      playerA: activePlayerABuild,
      playerB: activePlayerBBuild,
      settings: workspace.settings,
    });
  }, [activePlayerABuild, activePlayerBBuild, workspace.settings]);

  const leftBuild =
    getBuild(workspace, "player_a", workspace.compare.leftBuildId) ?? activePlayerABuild;
  const rightBuild =
    getBuild(workspace, "player_a", workspace.compare.rightBuildId) ?? activePlayerABuild;
  const leftOpponentBuild =
    getBuild(workspace, "player_b", workspace.compare.leftOpponentBuildId) ?? activePlayerBBuild;
  const rightOpponentBuild = workspace.compare.linkOpponents
    ? leftOpponentBuild
    : (getBuild(workspace, "player_b", workspace.compare.rightOpponentBuildId) ??
      activePlayerBBuild);

  const comparisonRequests = useMemo(() => {
    if (!leftBuild || !rightBuild || !leftOpponentBuild || !rightOpponentBuild) return null;
    return {
      leftRequest: materializeMatchupRequest({
        playerA: leftBuild,
        playerB: leftOpponentBuild,
        settings: workspace.settings,
      }),
      rightRequest: materializeMatchupRequest({
        playerA: rightBuild,
        playerB: rightOpponentBuild,
        settings: workspace.settings,
      }),
    };
  }, [leftBuild, rightBuild, leftOpponentBuild, rightOpponentBuild, workspace.settings]);

  const runMutation = useMutation({
    mutationFn: async (request: NonNullable<typeof currentRequest>) => postSimulate(request),
  });

  const compareMutation = useMutation({
    mutationFn: async ({
      leftRequest,
      rightRequest,
    }: {
      leftRequest: NonNullable<typeof currentRequest>;
      rightRequest: NonNullable<typeof currentRequest>;
    }) => {
      const [leftResponse, rightResponse] = await Promise.all([
        postSimulate(leftRequest),
        postSimulate(rightRequest),
      ]);
      return { leftResponse, rightResponse } satisfies CompareMutationResult;
    },
    onSuccess: () => setOverlayRunIndex(0),
  });

  useEffect(() => {
    if (overlayRunIndex < 0) {
      setOverlayRunIndex(0);
    }
  }, [overlayRunIndex]);

  const leftDamageSeries = useMemo(
    () =>
      deriveDamageSeries(
        compareMutation.data?.leftResponse,
        "Build A",
        "var(--chart-1)",
        overlayRunIndex,
      ),
    [overlayRunIndex, compareMutation.data?.leftResponse],
  );
  const rightDamageSeries = useMemo(
    () =>
      deriveDamageSeries(
        compareMutation.data?.rightResponse,
        "Build B",
        "var(--chart-3)",
        overlayRunIndex,
      ),
    [overlayRunIndex, compareMutation.data?.rightResponse],
  );

  const currentRunOptions = runMutation.data?.runs.map((run) => run.run_index) ?? [];
  const compareRunOptions =
    compareMutation.data?.leftResponse.runs.map((run) => run.run_index) ?? [];
  const selectedOverlayMax = Math.max(
    0,
    currentRunOptions.length > 0 ? currentRunOptions.length - 1 : 0,
    compareRunOptions.length > 0 ? compareRunOptions.length - 1 : 0,
  );

  const currentRunIssues = summarizeIssueCount(validationIssues);
  const runApiIssues = useMemo(() => parseApiIssues(runMutation.error), [runMutation.error]);
  const compareApiIssues = useMemo(
    () => parseApiIssues(compareMutation.error),
    [compareMutation.error],
  );
  const apiIssues = useMemo(() => {
    const deduped = new Map<string, BuildApiIssue>();
    [...runApiIssues, ...compareApiIssues].forEach((issue) => {
      deduped.set(issueFingerprint(issue), issue);
    });
    return Array.from(deduped.values());
  }, [runApiIssues, compareApiIssues]);

  useEffect(() => {
    if (!activePlayerABuild || !activePlayerBBuild) return;

    setSelectedItemBySide((current) => ({
      player_a: activePlayerABuild.item_definitions.some((item) => item.id === current.player_a)
        ? current.player_a
        : (activePlayerABuild.item_definitions[0]?.id ?? ""),
      player_b: activePlayerBBuild.item_definitions.some((item) => item.id === current.player_b)
        ? current.player_b
        : (activePlayerBBuild.item_definitions[0]?.id ?? ""),
    }));

    setSelectedMoveSourceBySide((current) => ({
      player_a:
        current.player_a && getPlacementIndexByInstanceId(activePlayerABuild, current.player_a) >= 0
          ? current.player_a
          : undefined,
      player_b:
        current.player_b && getPlacementIndexByInstanceId(activePlayerBBuild, current.player_b) >= 0
          ? current.player_b
          : undefined,
    }));
  }, [activePlayerABuild, activePlayerBBuild]);

  function handleBoardSlotClick(side: BuildSide, build: BuildDraft, slot: number): void {
    const occupiedPlacementIndex = getPlacementIndexAtSlot(build, slot);
    if (occupiedPlacementIndex >= 0) {
      const occupiedPlacement = build.board.placements[occupiedPlacementIndex];
      if (!occupiedPlacement) return;
      setSelectedMoveSourceBySide((current) => ({
        ...current,
        [side]: occupiedPlacement.item_instance_id,
      }));
      setSelectedItemBySide((current) => ({
        ...current,
        [side]: occupiedPlacement.item_definition_id,
      }));
      return;
    }

    const selectedMoveSource = selectedMoveSourceBySide[side];
    if (selectedMoveSource) {
      const moveIndex = getPlacementIndexByInstanceId(build, selectedMoveSource);
      if (moveIndex >= 0) {
        setWorkspace((current) => movePlacementToSlot(current, side, build.id, moveIndex, slot));
        setSelectedMoveSourceBySide((current) => ({ ...current, [side]: undefined }));
        return;
      }
    }

    const selectedItemId = selectedItemBySide[side];
    if (!selectedItemId || !canPlaceItemAtSlot(build, selectedItemId, slot)) {
      return;
    }

    setWorkspace((current) =>
      addPlacementForItemAtSlot(current, side, build.id, selectedItemId, slot),
    );
  }

  function handlePlacementSelect(side: BuildSide, itemInstanceId: string): void {
    setSelectedMoveSourceBySide((current) => ({
      ...current,
      [side]: itemInstanceId,
    }));
  }

  function runCurrentMatchup(): void {
    if (!currentRequest || hasBlockingIssues) return;
    runMutation.mutate(currentRequest);
  }

  function runComparison(): void {
    if (!comparisonRequests || hasBlockingIssues) return;
    compareMutation.mutate(
      comparisonRequests as {
        leftRequest: NonNullable<typeof currentRequest>;
        rightRequest: NonNullable<typeof currentRequest>;
      },
    );
  }

  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top,rgba(163,230,53,0.12),transparent_34%),linear-gradient(180deg,var(--background),color-mix(in srgb,var(--background) 72%,var(--muted)))] p-4 md:p-6">
      <section className="mx-auto flex w-full flex-col gap-5" style={{ maxWidth: 1600 }}>
        <header className="rounded-3xl border border-border/70 bg-background/80 p-5 shadow-sm backdrop-blur">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
            <div className="space-y-2">
              <div className="text-xs uppercase tracking-[0.25em] text-muted-foreground">
                Simulator Workspace
              </div>
              <h1 className="font-heading text-3xl font-semibold">
                Visual build authoring and comparison
              </h1>
              <p className="max-w-3xl text-sm text-muted-foreground">
                Create multiple versions of Player A and Player B, place items on visual boards,
                then run the same opponent or a different opponent against your builds to compare
                damage curves and outcomes.
              </p>
            </div>
            <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
              <span className="rounded-full border border-border/70 px-3 py-1.5">
                {currentRunIssues}
              </span>
              <span className="rounded-full border border-border/70 px-3 py-1.5">
                local save enabled
              </span>
              <span className="rounded-full border border-border/70 px-3 py-1.5">
                median damage graph
              </span>
            </div>
          </div>
        </header>

        {validationIssues.length > 0 ? (
          <div className="rounded-2xl border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
            <div className="font-medium">Validation blocks are active</div>
            <div className="mt-1 text-xs">
              Fix the listed build issues before running a matchup or comparison.
            </div>
          </div>
        ) : null}

        <div className="grid gap-5 xl:grid-cols-[330px_minmax(0,1fr)_390px]">
          <BuildSelectorPanel
            workspace={workspace}
            setWorkspace={setWorkspace}
            issues={validationIssues}
            apiIssues={apiIssues}
          />

          <div className="space-y-5">
            <Card>
              <CardHeader className="border-b border-border/70">
                <CardTitle>Battlefield</CardTitle>
              </CardHeader>
              <CardContent className="space-y-5 pt-4">
                <div className="grid gap-3 text-xs text-muted-foreground md:grid-cols-2">
                  <div>
                    Top board: Player B build version
                    <div className="mt-1 font-medium text-foreground">
                      {workspace.selectedBuildIds.player_b}
                    </div>
                  </div>
                  <div>
                    Bottom board: Player A build version
                    <div className="mt-1 font-medium text-foreground">
                      {workspace.selectedBuildIds.player_a}
                    </div>
                  </div>
                </div>

                {activePlayerBBuild ? (
                  <BuildEditor
                    setWorkspace={setWorkspace}
                    side="player_b"
                    build={activePlayerBBuild}
                    issues={validationIssues}
                    apiIssues={apiIssues}
                    selectedItemId={selectedItemBySide.player_b}
                    selectedPlacementId={selectedMoveSourceBySide.player_b}
                    onSelectedItemChange={(itemId) =>
                      setSelectedItemBySide((current) => ({ ...current, player_b: itemId }))
                    }
                    onBoardSlotClick={(slot) =>
                      handleBoardSlotClick("player_b", activePlayerBBuild, slot)
                    }
                    onPlacementSelect={(itemInstanceId) =>
                      handlePlacementSelect("player_b", itemInstanceId)
                    }
                  />
                ) : null}
                <div className="rounded-full border border-border/60 bg-muted/40 py-2 text-center text-xs uppercase tracking-[0.25em] text-muted-foreground">
                  versus
                </div>
                {activePlayerABuild ? (
                  <BuildEditor
                    setWorkspace={setWorkspace}
                    side="player_a"
                    build={activePlayerABuild}
                    issues={validationIssues}
                    apiIssues={apiIssues}
                    selectedItemId={selectedItemBySide.player_a}
                    selectedPlacementId={selectedMoveSourceBySide.player_a}
                    onSelectedItemChange={(itemId) =>
                      setSelectedItemBySide((current) => ({ ...current, player_a: itemId }))
                    }
                    onBoardSlotClick={(slot) =>
                      handleBoardSlotClick("player_a", activePlayerABuild, slot)
                    }
                    onPlacementSelect={(itemInstanceId) =>
                      handlePlacementSelect("player_a", itemInstanceId)
                    }
                  />
                ) : null}
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="border-b border-border/70">
                <CardTitle>Current matchup</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4 pt-4">
                <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                  <div className="rounded-2xl border border-border/70 bg-background/70 p-3 text-sm">
                    Player A: {activePlayerABuild?.name ?? "n/a"}
                  </div>
                  <div className="rounded-2xl border border-border/70 bg-background/70 p-3 text-sm">
                    Player B: {activePlayerBBuild?.name ?? "n/a"}
                  </div>
                  <div className="rounded-2xl border border-border/70 bg-background/70 p-3 text-sm">
                    Seed: {workspace.settings.seed}
                  </div>
                  <div className="rounded-2xl border border-border/70 bg-background/70 p-3 text-sm">
                    Runs: {workspace.settings.runs}
                  </div>
                </div>

                <div className="flex flex-wrap gap-3">
                  <button
                    type="button"
                    className="rounded-full border border-border bg-foreground px-4 py-2 text-sm text-background shadow-sm disabled:opacity-50"
                    onClick={runCurrentMatchup}
                    disabled={hasBlockingIssues || runMutation.isPending || !currentRequest}
                  >
                    {runMutation.isPending ? "Running matchup..." : "Run current matchup"}
                  </button>
                  {runMutation.isError ? (
                    <span className="self-center text-sm text-destructive">
                      {runMutation.error.message}
                    </span>
                  ) : null}
                </div>

                {runMutation.data ? (
                  <SummaryCard title="Current matchup summary" response={runMutation.data} />
                ) : null}
              </CardContent>
            </Card>
          </div>

          <div className="space-y-5">
            <Card>
              <CardHeader className="border-b border-border/70">
                <CardTitle>Build comparison</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4 pt-4 text-sm">
                <div className="grid gap-3">
                  <label className="space-y-1 text-xs">
                    <span className="text-muted-foreground">Left build version</span>
                    <select
                      className="w-full rounded-lg border border-border px-3 py-2 text-sm"
                      value={workspace.compare.leftBuildId}
                      onChange={(event) =>
                        setWorkspace((current) =>
                          setCompareSelection(current, { leftBuildId: event.target.value }),
                        )
                      }
                    >
                      {workspace.builds.player_a.map((build) => (
                        <option key={build.id} value={build.id}>
                          {build.name}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="space-y-1 text-xs">
                    <span className="text-muted-foreground">Right build version</span>
                    <select
                      className="w-full rounded-lg border border-border px-3 py-2 text-sm"
                      value={workspace.compare.rightBuildId}
                      onChange={(event) =>
                        setWorkspace((current) =>
                          setCompareSelection(current, { rightBuildId: event.target.value }),
                        )
                      }
                    >
                      {workspace.builds.player_a.map((build) => (
                        <option key={build.id} value={build.id}>
                          {build.name}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="space-y-1 text-xs">
                    <span className="text-muted-foreground">Left opponent</span>
                    <select
                      className="w-full rounded-lg border border-border px-3 py-2 text-sm"
                      value={workspace.compare.leftOpponentBuildId}
                      onChange={(event) =>
                        setWorkspace((current) =>
                          setCompareSelection(current, {
                            leftOpponentBuildId: event.target.value,
                            rightOpponentBuildId: current.compare.linkOpponents
                              ? event.target.value
                              : current.compare.rightOpponentBuildId,
                          }),
                        )
                      }
                    >
                      {workspace.builds.player_b.map((build) => (
                        <option key={build.id} value={build.id}>
                          {build.name}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="space-y-1 text-xs">
                    <span className="text-muted-foreground">Right opponent</span>
                    <select
                      className="w-full rounded-lg border border-border px-3 py-2 text-sm"
                      value={workspace.compare.rightOpponentBuildId}
                      onChange={(event) =>
                        setWorkspace((current) =>
                          setCompareSelection(current, {
                            rightOpponentBuildId: event.target.value,
                            linkOpponents: false,
                          }),
                        )
                      }
                      disabled={workspace.compare.linkOpponents}
                    >
                      {workspace.builds.player_b.map((build) => (
                        <option key={build.id} value={build.id}>
                          {build.name}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-xs">
                    <input
                      type="checkbox"
                      checked={workspace.compare.linkOpponents}
                      onChange={(event) =>
                        setWorkspace((current) =>
                          setCompareSelection(current, {
                            linkOpponents: event.target.checked,
                            rightOpponentBuildId: event.target.checked
                              ? current.compare.leftOpponentBuildId
                              : current.compare.rightOpponentBuildId,
                          }),
                        )
                      }
                    />
                    Compare against the same opponent
                  </label>
                </div>

                <div className="flex flex-wrap gap-3">
                  <button
                    type="button"
                    className="rounded-full border border-border bg-primary px-4 py-2 text-sm text-primary-foreground shadow-sm disabled:opacity-50"
                    onClick={runComparison}
                    disabled={hasBlockingIssues || compareMutation.isPending || !comparisonRequests}
                  >
                    {compareMutation.isPending ? "Comparing..." : "Run comparison"}
                  </button>
                  {compareMutation.isError ? (
                    <span className="self-center text-sm text-destructive">
                      {compareMutation.error.message}
                    </span>
                  ) : null}
                </div>

                <label className="space-y-1 text-xs">
                  <span className="text-muted-foreground">Overlay run</span>
                  <input
                    className="w-full"
                    type="range"
                    min={0}
                    max={selectedOverlayMax}
                    value={overlayRunIndex}
                    onChange={(event) => setOverlayRunIndex(Number(event.target.value))}
                    disabled={selectedOverlayMax === 0}
                  />
                </label>

                {compareMutation.data ? (
                  <>
                    <SummaryCard
                      title="Left build summary"
                      response={compareMutation.data.leftResponse}
                    />
                    <SummaryCard
                      title="Right build summary"
                      response={compareMutation.data.rightResponse}
                    />
                    <DamageComparisonChart
                      leftSeries={leftDamageSeries}
                      rightSeries={rightDamageSeries}
                      overlayIndex={overlayRunIndex}
                    />
                  </>
                ) : null}
              </CardContent>
            </Card>
          </div>
        </div>

        <Card>
          <CardHeader className="border-b border-border/70">
            <CardTitle>Current response details</CardTitle>
          </CardHeader>
          <CardContent className="pt-4">
            {runMutation.data ? (
              <ResponseSummaryList response={runMutation.data} />
            ) : (
              <div className="text-sm text-muted-foreground">
                Run the current matchup to inspect per-run metrics and logs.
              </div>
            )}
          </CardContent>
        </Card>
      </section>
    </main>
  );
}
