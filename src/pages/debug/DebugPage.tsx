import { useMemo } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";

import { getHealth, getSimulationSchema, postSimulate } from "../../api/endpoints";

function formatIso(iso: string | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString();
}

export default function DebugPage() {
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
    mutationFn: async () =>
      postSimulate({
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
        ],
        players: [
          {
            player_id: "player_a",
            stats: { max_health: 30, start_shield: 0, regeneration_per_second: 1 },
            board: {
              width: 10,
              placements: [
                { item_instance_id: "a-katana", item_definition_id: "katana", start_slot: 0 },
              ],
            },
            initial_statuses: [],
          },
          {
            player_id: "player_b",
            stats: { max_health: 30, start_shield: 0, regeneration_per_second: 0 },
            board: {
              width: 10,
              placements: [
                { item_instance_id: "b-katana", item_definition_id: "katana", start_slot: 0 },
              ],
            },
            initial_statuses: [],
          },
        ],
      }),
  });

  const healthText = useMemo(() => {
    if (healthQuery.isPending) return "loading";
    if (healthQuery.isError) return `error: ${healthQuery.error.message}`;
    return `${healthQuery.data.status} (${formatIso(healthQuery.data.now)})`;
  }, [healthQuery.data, healthQuery.error, healthQuery.isError, healthQuery.isPending]);

  return (
    <div className="min-h-screen p-6">
      <div className="mx-auto flex w-full max-w-3xl flex-col gap-6">
        <header className="flex flex-col gap-2">
          <h1 className="text-2xl font-semibold">Card Game Sim</h1>
          <p className="text-sm opacity-80">
            Debug view wired to the Phase 1 simulation contract and minimal event queue backend.
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
            <div>
              <span className="font-medium">Health:</span> <span>{healthText}</span>
            </div>
          </div>
        </section>

        <section className="rounded-md border p-4">
          <h2 className="text-lg font-medium">Scope Contract</h2>
          <div className="mt-3">
            {schemaQuery.isPending ? (
              <div className="text-sm">loading…</div>
            ) : schemaQuery.isError ? (
              <div className="text-sm">error: {schemaQuery.error.message}</div>
            ) : (
              <pre className="overflow-auto text-xs">
                {JSON.stringify(schemaQuery.data.scope, null, 2)}
              </pre>
            )}
          </div>
        </section>

        <section className="rounded-md border p-4">
          <h2 className="text-lg font-medium">Simulation</h2>
          <div className="mt-3 flex flex-col gap-3">
            <div className="flex items-center gap-3">
              <button
                type="button"
                className="rounded border px-3 py-2 text-sm"
                onClick={() => simulateMutation.mutate()}
                disabled={simulateMutation.isPending}
              >
                {simulateMutation.isPending ? "Running…" : "Run Sample Sim"}
              </button>
              {simulateMutation.isError ? (
                <span className="text-sm">error: {simulateMutation.error.message}</span>
              ) : null}
              {simulateMutation.isSuccess ? <span className="text-sm">ok</span> : null}
            </div>

            <div className="rounded border p-3">
              <div className="text-xs font-medium opacity-70">Response</div>
              <pre className="mt-2 overflow-auto text-xs">
                {simulateMutation.data ? JSON.stringify(simulateMutation.data, null, 2) : "(none)"}
              </pre>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
