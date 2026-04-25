import { useMemo, useState, type ReactNode } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";

import {
  getHealth,
  getSimulationSchema,
  postSimulate,
  type SimulationRequest,
  type SimulationResponse,
} from "../../api/endpoints";

type SimulationPreset = {
  id: string;
  name: string;
  description: string;
  request: SimulationRequest;
};

type TableRow = {
  key: string;
  cells: ReactNode[];
};

const BASELINE_DUEL: SimulationRequest = {
  seed: 1337,
  runs: 3,
  max_time_seconds: 20,
  max_events: 5000,
  combat_log_limit: 80,
  item_definitions: [
    {
      id: "katana",
      name: "Katana",
      size: 1,
      cooldown_seconds: 1,
      effects: [{ type: "damage", target: "opponent", magnitude: 5 }],
    },
  ],
  players: [
    {
      player_id: "player_a",
      stats: { max_health: 45, start_shield: 0, regeneration_per_second: 1 },
      board: {
        width: 10,
        placements: [{ item_instance_id: "a-katana", item_definition_id: "katana", start_slot: 0 }],
      },
      initial_statuses: [],
    },
    {
      player_id: "player_b",
      stats: { max_health: 45, start_shield: 0, regeneration_per_second: 0 },
      board: {
        width: 10,
        placements: [{ item_instance_id: "b-katana", item_definition_id: "katana", start_slot: 0 }],
      },
      initial_statuses: [],
    },
  ],
};

const ITEM_STATUS_EFFECT_PRESETS: SimulationPreset[] = [
  {
    id: "baseline-duel",
    name: "Baseline duel",
    description: "Straight timed weapon duel for control comparisons.",
    request: BASELINE_DUEL,
  },
  {
    id: "slow-vs-haste",
    name: "Slow vs haste",
    description:
      "A support item applies random slow to enemy items while the opponent self-hastes.",
    request: {
      seed: 4001,
      runs: 5,
      max_time_seconds: 25,
      max_events: 7000,
      combat_log_limit: 120,
      item_definitions: [
        {
          id: "striker",
          name: "Striker",
          size: 1,
          cooldown_seconds: 10,
          effects: [{ type: "damage", target: "opponent", magnitude: 10 }],
        },
        {
          id: "tar-net",
          name: "Tar Net",
          size: 1,
          cooldown_seconds: 4,
          effects: [{ type: "apply_item_slow", target: "enemy_random", magnitude: 5 }],
        },
        {
          id: "engine-tune",
          name: "Engine Tune",
          size: 1,
          cooldown_seconds: 4,
          effects: [{ type: "apply_item_haste", target: "self_item", magnitude: 2 }],
        },
      ],
      players: [
        {
          player_id: "player_a",
          stats: { max_health: 50, regeneration_per_second: 0, start_shield: 0 },
          board: {
            width: 10,
            placements: [
              { item_instance_id: "a-striker", item_definition_id: "striker", start_slot: 0 },
              { item_instance_id: "a-tar-net", item_definition_id: "tar-net", start_slot: 2 },
            ],
          },
          initial_statuses: [],
        },
        {
          player_id: "player_b",
          stats: { max_health: 50, regeneration_per_second: 0, start_shield: 0 },
          board: {
            width: 10,
            placements: [
              { item_instance_id: "b-striker", item_definition_id: "striker", start_slot: 0 },
              { item_instance_id: "b-engine", item_definition_id: "engine-tune", start_slot: 2 },
            ],
          },
          initial_statuses: [],
        },
      ],
    },
  },
  {
    id: "freeze-charge-cycle",
    name: "Freeze and charge cycle",
    description: "Player A freezes opponent timers while player B charges its own cannon.",
    request: {
      seed: 7821,
      runs: 5,
      max_time_seconds: 30,
      max_events: 9000,
      combat_log_limit: 140,
      item_definitions: [
        {
          id: "ice-beam",
          name: "Ice Beam",
          size: 1,
          cooldown_seconds: 5,
          effects: [{ type: "apply_item_freeze", target: "opponent_item", magnitude: 1.5 }],
        },
        {
          id: "pulse-blade",
          name: "Pulse Blade",
          size: 1,
          cooldown_seconds: 1.2,
          effects: [{ type: "damage", target: "opponent", magnitude: 3.5 }],
        },
        {
          id: "charge-link",
          name: "Charge Link",
          size: 1,
          cooldown_seconds: 4.2,
          effects: [{ type: "apply_item_charge", target: "self_item", magnitude: 1.5 }],
        },
        {
          id: "heavy-cannon",
          name: "Heavy Cannon",
          size: 2,
          cooldown_seconds: 4.6,
          effects: [{ type: "damage", target: "opponent", magnitude: 8 }],
        },
      ],
      players: [
        {
          player_id: "player_a",
          stats: { max_health: 58, regeneration_per_second: 0.8, start_shield: 1 },
          board: {
            width: 10,
            placements: [
              { item_instance_id: "a-pulse", item_definition_id: "pulse-blade", start_slot: 0 },
              { item_instance_id: "a-ice", item_definition_id: "ice-beam", start_slot: 2 },
            ],
          },
          initial_statuses: [],
        },
        {
          player_id: "player_b",
          stats: { max_health: 58, regeneration_per_second: 0.4, start_shield: 4 },
          board: {
            width: 10,
            placements: [
              { item_instance_id: "b-cannon", item_definition_id: "heavy-cannon", start_slot: 0 },
              { item_instance_id: "b-charge", item_definition_id: "charge-link", start_slot: 3 },
            ],
          },
          initial_statuses: [],
        },
      ],
    },
  },
  {
    id: "flight-adjacent-burn",
    name: "Flight and adjacency pressure",
    description: "Random targeting with burn and poison pressure.",
    request: {
      seed: 9907,
      runs: 4,
      max_time_seconds: 22,
      max_events: 7000,
      combat_log_limit: 120,
      item_definitions: [
        {
          id: "wing-lash",
          name: "Wing Lash",
          size: 1,
          cooldown_seconds: 1.3,
          effects: [
            { type: "damage", target: "opponent", magnitude: 3 },
            { type: "apply_item_flight", target: "self_item", magnitude: 1.5 },
          ],
        },
        {
          id: "ember-fan",
          name: "Ember Fan",
          size: 1,
          cooldown_seconds: 3.5,
          effects: [{ type: "apply_burn", target: "opponent", magnitude: 3 }],
        },
        {
          id: "venom-dart",
          name: "Venom Dart",
          size: 1,
          cooldown_seconds: 2,
          effects: [{ type: "apply_poison", target: "opponent", magnitude: 2.5 }],
        },
        {
          id: "shock-orb",
          name: "Shock Orb",
          size: 1,
          cooldown_seconds: 2.8,
          effects: [{ type: "damage", target: "enemy_random", magnitude: 4.5 }],
        },
      ],
      players: [
        {
          player_id: "player_a",
          stats: { max_health: 52, regeneration_per_second: 0.3, start_shield: 0 },
          board: {
            width: 10,
            placements: [
              { item_instance_id: "a-wing", item_definition_id: "wing-lash", start_slot: 0 },
              { item_instance_id: "a-ember", item_definition_id: "ember-fan", start_slot: 2 },
            ],
          },
          initial_statuses: [{ type: "burn", value: 1 }],
        },
        {
          player_id: "player_b",
          stats: { max_health: 52, regeneration_per_second: 0.3, start_shield: 0 },
          board: {
            width: 10,
            placements: [
              { item_instance_id: "b-dart", item_definition_id: "venom-dart", start_slot: 0 },
              { item_instance_id: "b-orb", item_definition_id: "shock-orb", start_slot: 2 },
            ],
          },
          initial_statuses: [{ type: "poison", value: 1 }],
        },
      ],
    },
  },
];

function formatJson(value: unknown): string {
  return JSON.stringify(value, null, 2);
}

function parseRequest(text: string): { request: SimulationRequest | null; error: string | null } {
  try {
    const parsed = JSON.parse(text) as SimulationRequest;
    return { request: parsed, error: null };
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unknown JSON parse error";
    return { request: null, error: message };
  }
}

function summarizeMap(values: Record<string, number> | undefined): string {
  if (!values) return "none";
  const pairs = Object.entries(values).filter(([, value]) => value > 0);
  if (pairs.length === 0) return "none";
  return pairs.map(([name, value]) => `${name}:${value}`).join(", ");
}

function describeResponse(response: SimulationResponse | undefined): string {
  if (!response) return "No simulation yet";
  const summary = response.summary;
  return `runs=${summary.run_count} A=${(summary.player_a_win_rate * 100).toFixed(1)}% B=${(
    summary.player_b_win_rate * 100
  ).toFixed(1)}% draw=${(summary.draw_rate * 100).toFixed(1)}%`;
}

function formatIso(iso: string | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString();
}

function DataTable({
  emptyMessage,
  headers,
  rows,
}: {
  emptyMessage: string;
  headers: string[];
  rows: TableRow[];
}) {
  if (rows.length === 0) {
    return <div>{emptyMessage}</div>;
  }

  return (
    <table className="min-w-full text-left text-xs">
      <thead>
        <tr>
          {headers.map((header, index) => (
            <th key={`${index}-${header}`} className="px-2 py-1">
              {header}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.key}>
            {row.cells.map((cell, index) => (
              <td key={`${row.key}-${index}`} className="px-2 py-1">
                {cell}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export default function DebugPage() {
  const [selectedPresetId, setSelectedPresetId] = useState<string>(
    ITEM_STATUS_EFFECT_PRESETS[0].id,
  );
  const [requestText, setRequestText] = useState<string>(
    formatJson(ITEM_STATUS_EFFECT_PRESETS[0].request),
  );
  const [parseError, setParseError] = useState<string | null>(null);
  const [activeRunIndex, setActiveRunIndex] = useState<number>(0);
  const [combatLogFilter, setCombatLogFilter] = useState<string>("");
  const [modifierTraceFilter, setModifierTraceFilter] = useState<string>("");

  const healthQuery = useQuery({
    queryKey: ["health"],
    queryFn: getHealth,
    refetchInterval: 30_000,
  });

  const schemaQuery = useQuery({
    queryKey: ["simulation-schema"],
    queryFn: getSimulationSchema,
  });

  const simulateMutation = useMutation({
    mutationFn: async (request: SimulationRequest) => postSimulate(request),
    onSuccess: () => {
      setActiveRunIndex(0);
    },
  });

  const healthText = useMemo(() => {
    if (healthQuery.isPending) return "loading";
    if (healthQuery.isError) return `error: ${healthQuery.error.message}`;
    return `${healthQuery.data.status} (${formatIso(healthQuery.data.now)})`;
  }, [healthQuery.data, healthQuery.error, healthQuery.isError, healthQuery.isPending]);

  const selectedPreset = useMemo(
    () => ITEM_STATUS_EFFECT_PRESETS.find((preset) => preset.id === selectedPresetId),
    [selectedPresetId],
  );

  const activeRun = useMemo(() => {
    const runs = simulateMutation.data?.runs ?? [];
    if (runs.length === 0) return null;
    return runs[Math.min(activeRunIndex, runs.length - 1)] ?? null;
  }, [activeRunIndex, simulateMutation.data?.runs]);

  const filteredCombatLog = useMemo(() => {
    if (!activeRun) return [];
    const filter = combatLogFilter.trim().toLowerCase();
    if (!filter) return activeRun.combat_log ?? [];
    return (activeRun.combat_log ?? []).filter((entry) =>
      [entry.event_type, entry.source_item_instance_id ?? "", entry.target_id ?? ""]
        .join(" ")
        .toLowerCase()
        .includes(filter),
    );
  }, [activeRun, combatLogFilter]);

  const filteredModifierTrace = useMemo(() => {
    if (!activeRun) return [];
    const trace = activeRun.modifier_timer_trace ?? [];
    const filter = modifierTraceFilter.trim().toLowerCase();
    if (!filter) return trace;
    return trace.filter((entry) =>
      [entry.operation, entry.modifier ?? "", entry.modifier_instance_id ?? "", entry.item_id]
        .join(" ")
        .toLowerCase()
        .includes(filter),
    );
  }, [activeRun, modifierTraceFilter]);

  const itemMetricRows = useMemo(() => {
    if (!activeRun) return [];
    const players = [activeRun.metrics.player_a, activeRun.metrics.player_b];
    return players.flatMap((playerMetrics) =>
      (playerMetrics.item_metrics ?? []).map((metric) => ({
        key: `${metric.owner_player_id}-${metric.item_instance_id}`,
        cells: [
          metric.item_instance_id,
          metric.owner_player_id,
          summarizeMap(metric.events_triggered),
          summarizeMap(metric.status_effects_received),
        ],
      })),
    );
  }, [activeRun]);

  const combatLogRows = useMemo(() => {
    return filteredCombatLog.map((entry) => ({
      key: `${entry.event_index}-${entry.time_seconds}-${entry.event_type}`,
      cells: [
        entry.time_seconds.toFixed(3),
        entry.event_type,
        entry.source_item_instance_id ?? "-",
        entry.target_id ?? "-",
      ],
    }));
  }, [filteredCombatLog]);

  const modifierTraceRows = useMemo(() => {
    return filteredModifierTrace.map((entry, index) => ({
      key: `${entry.time}-${entry.item_id}-${entry.operation}-${entry.modifier_instance_id ?? "none"}-${index}`,
      cells: [
        entry.time.toFixed(3),
        entry.operation,
        entry.modifier ?? "-",
        entry.item_id,
        `${entry.old_modifier ?? "-"} → ${entry.new_modifier ?? "-"}`,
        `${entry.pending_event_before ?? "-"} → ${entry.pending_event_after ?? "-"}`,
      ],
    }));
  }, [filteredModifierTrace]);

  const runPayloadSummary = useMemo(() => {
    const parsed = parseRequest(requestText);
    if (!parsed.request) return "invalid request JSON";
    return `seed=${parsed.request.seed} runs=${parsed.request.runs} defs=${parsed.request.item_definitions.length}`;
  }, [requestText]);

  function loadPreset(presetId: string): void {
    const preset = ITEM_STATUS_EFFECT_PRESETS.find((entry) => entry.id === presetId);
    if (!preset) return;
    setSelectedPresetId(presetId);
    setRequestText(formatJson(preset.request));
    setParseError(null);
  }

  function runSimulation(): void {
    const parsed = parseRequest(requestText);
    if (!parsed.request) {
      setParseError(parsed.error);
      return;
    }
    setParseError(null);
    simulateMutation.mutate(parsed.request);
  }

  return (
    <div className="min-h-screen p-6">
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-6">
        <header className="flex flex-col gap-2">
          <h1 className="text-2xl font-semibold">Card Game Sim Debug Console</h1>
          <p className="text-sm opacity-80">
            Simulation tooling for contract checks, status-effect scenarios, and targeted run
            inspection.
          </p>
        </header>

        <section className="rounded-md border p-4">
          <div className="flex items-center justify-between gap-4">
            <h2 className="text-lg font-medium">Backend</h2>
            <button
              type="button"
              className="rounded border px-3 py-2 text-sm"
              onClick={() => void healthQuery.refetch()}
            >
              Refresh
            </button>
          </div>
          <div className="mt-3 text-sm">
            <span className="font-medium">Health:</span> <span>{healthText}</span>
          </div>
        </section>

        <section className="rounded-md border p-4">
          <h2 className="text-lg font-medium">Scope Contract</h2>
          <div className="mt-3">
            {schemaQuery.isPending ? (
              <div className="text-sm">loading...</div>
            ) : schemaQuery.isError ? (
              <div className="text-sm">error: {schemaQuery.error.message}</div>
            ) : (
              <div className="grid gap-3">
                <div className="grid gap-2 text-sm md:grid-cols-2">
                  <div>
                    <span className="font-medium">Effect types:</span>{" "}
                    {schemaQuery.data.scope?.effect_types?.join(", ") ?? "none"}
                  </div>
                  <div>
                    <span className="font-medium">Statuses:</span>{" "}
                    {schemaQuery.data.scope?.statuses?.join(", ") ?? "none"}
                  </div>
                </div>
                <pre className="overflow-auto text-xs">{formatJson(schemaQuery.data.scope)}</pre>
              </div>
            )}
          </div>
        </section>

        <section className="rounded-md border p-4">
          <h2 className="text-lg font-medium">Simulation</h2>
          <div className="mt-3 grid gap-4 lg:grid-cols-2">
            <div className="flex flex-col gap-3">
              <div className="rounded border p-3">
                <div className="text-xs font-medium opacity-70">Preset</div>
                <div className="mt-2 flex flex-col gap-2">
                  <select
                    className="rounded border px-2 py-2 text-sm"
                    value={selectedPresetId}
                    onChange={(event) => loadPreset(event.target.value)}
                  >
                    {ITEM_STATUS_EFFECT_PRESETS.map((preset) => (
                      <option key={preset.id} value={preset.id}>
                        {preset.name}
                      </option>
                    ))}
                  </select>
                  <div className="text-xs opacity-80">{selectedPreset?.description}</div>
                  <div className="flex gap-2">
                    <button
                      type="button"
                      className="rounded border px-3 py-2 text-sm"
                      onClick={() => loadPreset(selectedPresetId)}
                    >
                      Reset Payload
                    </button>
                    <button
                      type="button"
                      className="rounded border px-3 py-2 text-sm"
                      onClick={() => setRequestText(formatJson(BASELINE_DUEL))}
                    >
                      Load Baseline
                    </button>
                  </div>
                </div>
              </div>

              <div className="rounded border p-3">
                <div className="text-xs font-medium opacity-70">Simulation Request JSON</div>
                <textarea
                  className="mt-2 h-105 w-full rounded border p-2 font-mono text-xs"
                  value={requestText}
                  onChange={(event) => setRequestText(event.target.value)}
                />
                <div className="mt-2 flex flex-wrap items-center gap-3 text-xs">
                  <span className="opacity-80">{runPayloadSummary}</span>
                  {parseError ? (
                    <span className="text-red-600">JSON parse error: {parseError}</span>
                  ) : null}
                </div>
              </div>

              <div className="flex items-center gap-3">
                <button
                  type="button"
                  className="rounded border px-3 py-2 text-sm"
                  onClick={runSimulation}
                  disabled={simulateMutation.isPending}
                >
                  {simulateMutation.isPending ? "Running..." : "Run Simulation"}
                </button>
                {simulateMutation.isError ? (
                  <span className="text-sm">error: {simulateMutation.error.message}</span>
                ) : null}
                {simulateMutation.isSuccess ? <span className="text-sm">ok</span> : null}
              </div>
            </div>

            <div className="flex flex-col gap-3">
              <div className="rounded border p-3">
                <div className="text-xs font-medium opacity-70">Batch Summary</div>
                <div className="mt-2 text-sm">{describeResponse(simulateMutation.data)}</div>
                {simulateMutation.data ? (
                  <pre className="mt-2 overflow-auto text-xs">
                    {formatJson(simulateMutation.data.summary)}
                  </pre>
                ) : null}
              </div>

              <div className="rounded border p-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="text-xs font-medium opacity-70">Run Detail</div>
                  <select
                    className="rounded border px-2 py-1 text-xs"
                    value={String(activeRunIndex)}
                    onChange={(event) => setActiveRunIndex(Number(event.target.value))}
                    disabled={!simulateMutation.data || simulateMutation.data.runs.length === 0}
                  >
                    {(simulateMutation.data?.runs ?? []).map((run) => (
                      <option key={run.run_index} value={run.run_index}>
                        Run {run.run_index} ({run.stop_reason})
                      </option>
                    ))}
                  </select>
                </div>
                {activeRun ? (
                  <div className="mt-2 text-xs">
                    <div>winner: {activeRun.winner_player_id}</div>
                    <div>duration: {activeRun.duration_seconds.toFixed(3)}s</div>
                    <div>
                      combat log: {activeRun.combat_log?.length ?? 0} /{" "}
                      {activeRun.combat_log_total_events} events
                      {activeRun.combat_log_truncated ? " (truncated)" : ""}
                    </div>
                  </div>
                ) : (
                  <div className="mt-2 text-xs">No run selected</div>
                )}
              </div>

              <div className="rounded border p-3">
                <div className="text-xs font-medium opacity-70">Item Status Metrics</div>
                <div className="mt-2 overflow-auto">
                  <DataTable
                    emptyMessage="No item metrics captured yet."
                    headers={["item", "owner", "events triggered", "received statuses"]}
                    rows={itemMetricRows}
                  />
                </div>
              </div>

              <div className="rounded border p-3">
                <div className="flex items-center justify-between gap-2">
                  <div className="text-xs font-medium opacity-70">Combat Log Filter</div>
                  <input
                    className="w-48 rounded border px-2 py-1 text-xs"
                    value={combatLogFilter}
                    placeholder="event, item id, or target"
                    onChange={(event) => setCombatLogFilter(event.target.value)}
                  />
                </div>
                <div className="mt-2 max-h-55 overflow-auto text-xs">
                  <DataTable
                    emptyMessage="No combat log entries."
                    headers={["t", "event", "source item", "target"]}
                    rows={combatLogRows}
                  />
                </div>
              </div>

              <div className="rounded border p-3">
                <div className="flex items-center justify-between gap-2">
                  <div className="text-xs font-medium opacity-70">Modifier Timer Trace</div>
                  <input
                    className="w-48 rounded border px-2 py-1 text-xs"
                    value={modifierTraceFilter}
                    placeholder="operation, modifier, item"
                    onChange={(event) => setModifierTraceFilter(event.target.value)}
                  />
                </div>
                <div className="mt-2 text-xs opacity-80">
                  shown {filteredModifierTrace.length} /{" "}
                  {activeRun?.modifier_timer_trace?.length ?? 0}
                </div>
                <div className="mt-2 max-h-55 overflow-auto text-xs">
                  <DataTable
                    emptyMessage="No modifier trace entries."
                    headers={[
                      "t",
                      "operation",
                      "modifier",
                      "item",
                      "old → new",
                      "pending before → after",
                    ]}
                    rows={modifierTraceRows}
                  />
                </div>
              </div>
            </div>
          </div>

          <div className="mt-3 rounded border p-3">
            <div className="text-xs font-medium opacity-70">Raw Response</div>
            <pre className="mt-2 overflow-auto text-xs">
              {simulateMutation.data ? formatJson(simulateMutation.data) : "(none)"}
            </pre>
          </div>
        </section>
      </div>
    </div>
  );
}
