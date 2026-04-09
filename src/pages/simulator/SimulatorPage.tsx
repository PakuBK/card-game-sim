import { useMemo } from "react";
import { useMutation } from "@tanstack/react-query";

import { postSimulate, type SimulationRequest, type SimulationResponse } from "@/api/endpoints";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const samplePayload: SimulationRequest = {
  seed: 1337,
  runs: 3,
  max_time_seconds: 20,
  max_events: 5000,
  item_definitions: [
    {
      id: "katana",
      name: "Katana",
      size: 1,
      cooldown_seconds: 1,
      effects: [
        {
          type: "damage",
          target: "opponent",
          magnitude: 5,
        },
      ],
    },
    {
      id: "lighter",
      name: "Lighter",
      size: 1,
      cooldown_seconds: 3,
      effects: [
        {
          type: "apply_burn",
          target: "opponent",
          magnitude: 5,
        },
      ],
    },
  ],
  players: [
    {
      player_id: "player_a",
      stats: { max_health: 30, start_shield: 0, regeneration_per_second: 1 },
      board: {
        width: 10,
        placements: [
          { item_instance_id: "a-katana", item_definition_id: "katana", start_slot: 0 },
          { item_instance_id: "a-ligther", item_definition_id: "lighter", start_slot: 1 },
        ],
      },
      initial_statuses: [],
    },
    {
      player_id: "player_b",
      stats: { max_health: 30, start_shield: 0, regeneration_per_second: 0 },
      board: {
        width: 10,
        placements: [{ item_instance_id: "b-katana", item_definition_id: "katana", start_slot: 0 }],
      },
      initial_statuses: [],
    },
  ],
};

function formatSummary(payload: SimulationRequest): string[] {
  const playerA = payload.players.find((player) => player.player_id === "player_a");
  const playerB = payload.players.find((player) => player.player_id === "player_b");

  return [
    `Seed: ${payload.seed}`,
    `Runs: ${payload.runs}`,
    `Stop limits: ${payload.max_time_seconds}s or ${payload.max_events} events`,
    `Item definitions: ${payload.item_definitions.length}`,
    `Player A board placements: ${playerA?.board.placements?.length ?? 0}`,
    `Player B board placements: ${playerB?.board.placements?.length ?? 0}`,
    "Player A is the primary configuration under test; Player B is a live opponent board for interaction checks.",
  ];
}

function ResponseSummary({ response }: { response: SimulationResponse }) {
  return (
    <div className="space-y-4 text-sm">
      <div className="grid gap-2 sm:grid-cols-2">
        <div>
          <span className="font-medium">Run count:</span> {response.summary.run_count}
        </div>
        <div>
          <span className="font-medium">Player A win rate:</span>{" "}
          {response.summary.player_a_win_rate}
        </div>
        <div>
          <span className="font-medium">Player B win rate:</span>{" "}
          {response.summary.player_b_win_rate}
        </div>
        <div>
          <span className="font-medium">Draw rate:</span> {response.summary.draw_rate}
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
          const playerAItems = playerAMetrics.item_metrics ?? [];
          const playerBItems = playerBMetrics.item_metrics ?? [];
          const combatLog = run.combat_log ?? [];
          const logPreview = combatLog.slice(0, 20);

          return (
            <div key={run.run_index} className="rounded border border-border p-3">
              <div className="font-medium">Run {run.run_index + 1}</div>
              <div className="mt-1 text-xs opacity-80">
                Winner: {run.winner_player_id}, Duration: {run.duration_seconds}s, Events:{" "}
                {run.metrics.total_events_processed}
              </div>
              <div className="mt-2 grid gap-3 sm:grid-cols-2">
                <div>
                  <div className="text-xs font-medium opacity-75">Player A metrics</div>
                  <ul className="mt-1 space-y-1 text-xs">
                    <li>item uses: {playerAMetrics.item_uses}</li>
                    <li>burn ticks: {playerAMetrics.burn_ticks}</li>
                    <li>poison ticks: {playerAMetrics.poison_ticks}</li>
                    <li>regen ticks: {playerAMetrics.regen_ticks}</li>
                    <li>opponent damage total: {playerADamage.total}</li>
                    <li>opponent direct damage: {playerADamage.direct}</li>
                    <li>opponent burn damage: {playerADamage.burn}</li>
                    <li>opponent poison damage: {playerADamage.poison}</li>
                    <li>
                      statuses applied: burn{" "}
                      {playerAMetrics.status_effects_applied?.burn?.applications ?? 0}, poison{" "}
                      {playerAMetrics.status_effects_applied?.poison?.applications ?? 0}
                    </li>
                    <li>
                      statuses received: burn{" "}
                      {playerAMetrics.status_effects_received?.burn?.applications ?? 0}, poison{" "}
                      {playerAMetrics.status_effects_received?.poison?.applications ?? 0}
                    </li>
                    <li>final health: {playerA?.health ?? "n/a"}</li>
                  </ul>
                  <div className="mt-2 text-xs font-medium opacity-75">Player A item metrics</div>
                  <ul className="mt-1 space-y-1 text-xs">
                    {playerAItems.map((itemMetric) => (
                      <li key={itemMetric.item_instance_id}>
                        {itemMetric.item_instance_id}: dmg {itemMetric.damage_done?.total ?? 0}{" "}
                        (direct {itemMetric.damage_done?.direct ?? 0}, burn{" "}
                        {itemMetric.damage_done?.burn ?? 0}, poison{" "}
                        {itemMetric.damage_done?.poison ?? 0}), used{" "}
                        {itemMetric.events_triggered?.used ?? 0}
                      </li>
                    ))}
                    {playerAItems.length === 0 ? <li>none</li> : null}
                  </ul>
                </div>
                <div>
                  <div className="text-xs font-medium opacity-75">Player B metrics</div>
                  <ul className="mt-1 space-y-1 text-xs">
                    <li>item uses: {playerBMetrics.item_uses}</li>
                    <li>burn ticks: {playerBMetrics.burn_ticks}</li>
                    <li>poison ticks: {playerBMetrics.poison_ticks}</li>
                    <li>regen ticks: {playerBMetrics.regen_ticks}</li>
                    <li>opponent damage total: {playerBDamage.total}</li>
                    <li>opponent direct damage: {playerBDamage.direct}</li>
                    <li>opponent burn damage: {playerBDamage.burn}</li>
                    <li>opponent poison damage: {playerBDamage.poison}</li>
                    <li>
                      statuses applied: burn{" "}
                      {playerBMetrics.status_effects_applied?.burn?.applications ?? 0}, poison{" "}
                      {playerBMetrics.status_effects_applied?.poison?.applications ?? 0}
                    </li>
                    <li>
                      statuses received: burn{" "}
                      {playerBMetrics.status_effects_received?.burn?.applications ?? 0}, poison{" "}
                      {playerBMetrics.status_effects_received?.poison?.applications ?? 0}
                    </li>
                    <li>final health: {playerB?.health ?? "n/a"}</li>
                  </ul>
                  <div className="mt-2 text-xs font-medium opacity-75">Player B item metrics</div>
                  <ul className="mt-1 space-y-1 text-xs">
                    {playerBItems.map((itemMetric) => (
                      <li key={itemMetric.item_instance_id}>
                        {itemMetric.item_instance_id}: dmg {itemMetric.damage_done?.total ?? 0}{" "}
                        (direct {itemMetric.damage_done?.direct ?? 0}, burn{" "}
                        {itemMetric.damage_done?.burn ?? 0}, poison{" "}
                        {itemMetric.damage_done?.poison ?? 0}), used{" "}
                        {itemMetric.events_triggered?.used ?? 0}
                      </li>
                    ))}
                    {playerBItems.length === 0 ? <li>none</li> : null}
                  </ul>
                </div>
              </div>
              <div className="mt-3 rounded border border-border p-2">
                <div className="text-xs font-medium opacity-75">Combat log</div>
                <div className="mt-1 text-xs opacity-80">
                  Entries returned: {combatLog.length}
                  {typeof run.combat_log_total_events === "number"
                    ? ` / ${run.combat_log_total_events} processed`
                    : ""}
                  {run.combat_log_truncated ? " (truncated by combat_log_limit)" : ""}
                </div>
                <ul className="mt-2 space-y-1 text-xs">
                  {logPreview.map((entry) => (
                    <li key={entry.event_index}>
                      t={entry.time_seconds} [{entry.event_type}] src={entry.source_player_id}
                      {entry.source_item_instance_id
                        ? `:${entry.source_item_instance_id}`
                        : ""}{" "}
                      tgt=
                      {entry.target_id ?? "-"} delta=
                      {entry.state_deltas
                        ?.map(
                          (delta) =>
                            `${delta.player_id}(hp ${delta.health_delta}, sh ${delta.shield_delta}, b ${delta.burn_delta}, p ${delta.poison_delta})`,
                        )
                        .join("; ") || "none"}
                    </li>
                  ))}
                  {logPreview.length === 0 ? <li>none</li> : null}
                </ul>
                {combatLog.length > logPreview.length ? (
                  <div className="mt-1 text-xs opacity-70">
                    Showing first {logPreview.length} entries in preview.
                  </div>
                ) : null}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default function SimulatorPage() {
  const simulateMutation = useMutation({
    mutationFn: async () => postSimulate(samplePayload),
  });

  const requestSummary = useMemo(() => formatSummary(samplePayload), []);

  return (
    <main className="min-h-screen p-6">
      <section className="mx-auto flex w-full max-w-6xl flex-col gap-6">
        <header className="space-y-2">
          <h1 className="text-2xl font-semibold">Simulation Inspector</h1>
          <p className="text-sm opacity-80">
            View exactly what is sent to the backend, what scenario is being tested, and the
            response in both readable and raw forms.
          </p>
        </header>

        <Card>
          <CardHeader className="border-b border-border">
            <CardTitle>Request payload sent to backend</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 pt-4">
            <div className="rounded border border-border p-3">
              <div className="text-xs font-medium opacity-70">What we are trying to simulate</div>
              <ul className="mt-2 space-y-1 text-sm">
                {requestSummary.map((line) => (
                  <li key={line}>{line}</li>
                ))}
              </ul>
            </div>
            <div className="rounded border border-border p-3">
              <div className="text-xs font-medium opacity-70">Raw request JSON</div>
              <pre className="mt-2 overflow-auto text-xs">
                {JSON.stringify(samplePayload, null, 2)}
              </pre>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="border-b border-border">
            <CardTitle>Run simulation</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 pt-4">
            <div className="flex items-center gap-3">
              <button
                type="button"
                className="rounded border border-border px-3 py-2 text-sm"
                onClick={() => simulateMutation.mutate()}
                disabled={simulateMutation.isPending}
              >
                {simulateMutation.isPending ? "Running..." : "Run Sample Simulation"}
              </button>
              {simulateMutation.isError ? (
                <span className="text-sm text-destructive">
                  error: {simulateMutation.error.message}
                </span>
              ) : null}
            </div>

            <div className="rounded border border-border p-3">
              <div className="text-xs font-medium opacity-70">Prettified response</div>
              <div className="mt-2">
                {simulateMutation.data ? (
                  <ResponseSummary response={simulateMutation.data} />
                ) : (
                  <div className="text-sm opacity-80">No response yet.</div>
                )}
              </div>
            </div>

            <div className="rounded border border-border p-3">
              <div className="text-xs font-medium opacity-70">Raw response JSON</div>
              <pre className="mt-2 overflow-auto text-xs">
                {simulateMutation.data ? JSON.stringify(simulateMutation.data, null, 2) : "(none)"}
              </pre>
            </div>
          </CardContent>
        </Card>
      </section>
    </main>
  );
}
