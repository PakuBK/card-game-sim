import type { SimulationRequest, SimulationResponse } from "@/api/endpoints";

export type BuildSide = "player_a" | "player_b";

export type BuildItemDefinition = SimulationRequest["item_definitions"][number];
export type BuildItemAbility = BuildItemDefinition["abilities"][number];
type BuildBoardConfig = NonNullable<SimulationRequest["players"][number]["board"]>;
export type BuildPlacement = NonNullable<BuildBoardConfig["placements"]>[number];
export type BuildPlayerStats = SimulationRequest["players"][number]["stats"];
export type BuildInitialStatus = NonNullable<
  SimulationRequest["players"][number]["initial_statuses"]
>[number];
export type BuildItemEffect = BuildItemAbility["effects"][number];

export type ValidationIssue = {
  side: BuildSide;
  buildId: string;
  path: string;
  message: string;
};

export type BuildDraft = {
  id: string;
  side: BuildSide;
  name: string;
  notes: string;
  stats: BuildPlayerStats;
  board: {
    width: number;
    placements: BuildPlacement[];
  };
  initial_statuses: BuildInitialStatus[];
  item_definitions: BuildItemDefinition[];
  updated_at: string;
};

export type SimulatorSettings = {
  seed: number;
  runs: number;
  max_time_seconds: number;
  max_events: number;
  combat_log_limit: number;
};

export type CompareSelection = {
  leftBuildId: string;
  rightBuildId: string;
  leftOpponentBuildId: string;
  rightOpponentBuildId: string;
  linkOpponents: boolean;
};

export type SimulatorWorkspace = {
  builds: Record<BuildSide, BuildDraft[]>;
  selectedBuildIds: Record<BuildSide, string>;
  compare: CompareSelection;
  settings: SimulatorSettings;
};

export type DamageSeriesPoint = {
  time: number;
  value: number;
};

export type DamageSeries = {
  label: string;
  color: string;
  median: DamageSeriesPoint[];
  overlay: DamageSeriesPoint[];
  maxTime: number;
  totalDamage: number;
};

export type MatchupRequest = {
  playerA: BuildDraft;
  playerB: BuildDraft;
  settings: SimulatorSettings;
};

const STORAGE_KEY = "card-game-sim.simulator.workspace.v2";

function uid(prefix: string): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return `${prefix}-${crypto.randomUUID()}`;
  }

  return `${prefix}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

function nowIso(): string {
  return new Date().toISOString();
}

function getTimedUseAbilityIndex(abilities: BuildItemAbility[]): number {
  return abilities.findIndex((ability) => ability.trigger.type === "timed_use");
}

export function getTimedUseEffects(item: BuildItemDefinition): BuildItemEffect[] {
  const index = getTimedUseAbilityIndex(item.abilities);
  if (index === -1) return [];
  return item.abilities[index].effects;
}

function updateTimedUseEffects(
  item: BuildItemDefinition,
  updater: (effects: BuildItemEffect[]) => BuildItemEffect[],
): BuildItemDefinition {
  const index = getTimedUseAbilityIndex(item.abilities);
  if (index === -1) {
    return {
      ...item,
      abilities: [
        ...item.abilities,
        {
          trigger: { type: "timed_use" },
          effects: updater([defaultEffect("damage")]),
        },
      ],
    };
  }

  return {
    ...item,
    abilities: item.abilities.map((ability, abilityIndex) =>
      abilityIndex === index
        ? {
            ...ability,
            effects: updater(ability.effects),
          }
        : ability,
    ),
  };
}

function normalizeEffect(
  effect: Omit<BuildItemEffect, "targeting_mode"> &
    Partial<Pick<BuildItemEffect, "targeting_mode">>,
): BuildItemEffect {
  return {
    targeting_mode: "single",
    ...effect,
  };
}

function defaultEffect(type: BuildItemEffect["type"] = "damage"): BuildItemEffect {
  if (type === "damage") return normalizeEffect({ type, target: "opponent", magnitude: 5 });
  if (type === "heal") return normalizeEffect({ type, target: "self", magnitude: 3 });
  if (type === "shield") return normalizeEffect({ type, target: "self", magnitude: 4 });
  if (type === "apply_burn") return normalizeEffect({ type, target: "opponent", magnitude: 2 });
  if (type === "apply_poison") return normalizeEffect({ type, target: "opponent", magnitude: 2 });
  if (type === "apply_item_slow")
    return normalizeEffect({ type, target: "opponent_item", magnitude: 2 });
  if (type === "apply_item_haste")
    return normalizeEffect({ type, target: "self_item", magnitude: 2 });
  if (type === "apply_item_freeze")
    return normalizeEffect({ type, target: "opponent_item", magnitude: 1 });
  if (type === "apply_item_charge")
    return normalizeEffect({ type, target: "self_item", magnitude: 1 });
  return normalizeEffect({ type, target: "self_item", magnitude: 1 });
}

function makeItemDefinition(
  id: string,
  name: string,
  effect: BuildItemEffect,
  overrides?: Partial<BuildItemDefinition>,
): BuildItemDefinition {
  return {
    id,
    name,
    size: 1,
    cooldown_seconds: 2,
    abilities: [
      {
        trigger: { type: "timed_use" },
        effects: [normalizeEffect(effect)],
      },
    ],
    ...overrides,
  };
}

function makeBuild(
  side: BuildSide,
  name: string,
  itemDefinitions: BuildItemDefinition[],
  placements: BuildPlacement[],
  stats: BuildPlayerStats,
  initialStatuses: BuildInitialStatus[] = [],
  notes = "",
): BuildDraft {
  return {
    id: uid(`${side}-build`),
    side,
    name,
    notes,
    stats,
    board: {
      width: 10,
      placements,
    },
    initial_statuses: initialStatuses,
    item_definitions: itemDefinitions,
    updated_at: nowIso(),
  };
}

function createStarterBuilds(): Record<BuildSide, BuildDraft[]> {
  const playerABaseline = makeBuild(
    "player_a",
    "A Baseline",
    [
      makeItemDefinition(
        "katana",
        "Katana",
        normalizeEffect({ type: "damage", target: "opponent", magnitude: 5 }),
      ),
      makeItemDefinition(
        "lighter",
        "Lighter",
        normalizeEffect({
          type: "apply_burn",
          target: "opponent",
          magnitude: 3,
        }),
        { cooldown_seconds: 3 },
      ),
    ],
    [
      { item_instance_id: "a-katana", item_definition_id: "katana", start_slot: 0 },
      { item_instance_id: "a-lighter", item_definition_id: "lighter", start_slot: 2 },
    ],
    { max_health: 42, start_shield: 0, regeneration_per_second: 1 },
    [],
    "Timed damage baseline with burn pressure.",
  );

  const playerAAlt = makeBuild(
    "player_a",
    "A Burn Loop",
    [
      makeItemDefinition(
        "strike",
        "Strike",
        normalizeEffect({ type: "damage", target: "opponent", magnitude: 3 }),
      ),
      makeItemDefinition(
        "ember",
        "Ember Fan",
        normalizeEffect({ type: "apply_burn", target: "opponent", magnitude: 4 }),
        { cooldown_seconds: 4 },
      ),
    ],
    [
      { item_instance_id: "a-strike", item_definition_id: "strike", start_slot: 0 },
      { item_instance_id: "a-ember", item_definition_id: "ember", start_slot: 3 },
    ],
    { max_health: 45, start_shield: 1, regeneration_per_second: 0.5 },
    [],
    "Faster opener with burn follow-up.",
  );

  const playerBBaseline = makeBuild(
    "player_b",
    "B Baseline",
    [
      makeItemDefinition(
        "guard",
        "Guard",
        normalizeEffect({ type: "shield", target: "self", magnitude: 4 }),
        { cooldown_seconds: 2.5 },
      ),
      makeItemDefinition(
        "spear",
        "Spear",
        normalizeEffect({ type: "damage", target: "opponent", magnitude: 4 }),
      ),
    ],
    [
      { item_instance_id: "b-guard", item_definition_id: "guard", start_slot: 1 },
      { item_instance_id: "b-spear", item_definition_id: "spear", start_slot: 4 },
    ],
    { max_health: 44, start_shield: 2, regeneration_per_second: 0.5 },
    [],
    "Defensive baseline opponent with steady pressure.",
  );

  const playerBAlt = makeBuild(
    "player_b",
    "B Freeze Net",
    [
      makeItemDefinition(
        "net",
        "Freeze Net",
        normalizeEffect({
          type: "apply_item_freeze",
          target: "opponent_item",
          magnitude: 1,
        }),
        { cooldown_seconds: 5 },
      ),
      makeItemDefinition(
        "dart",
        "Poison Dart",
        normalizeEffect({
          type: "apply_poison",
          target: "opponent",
          magnitude: 2,
        }),
        { cooldown_seconds: 2.5 },
      ),
    ],
    [
      { item_instance_id: "b-net", item_definition_id: "net", start_slot: 0 },
      { item_instance_id: "b-dart", item_definition_id: "dart", start_slot: 3 },
    ],
    { max_health: 43, start_shield: 0, regeneration_per_second: 0.25 },
    [{ type: "poison", value: 1 }],
    "Tempo disruption opponent with poison pressure.",
  );

  return {
    player_a: [playerABaseline, playerAAlt],
    player_b: [playerBBaseline, playerBAlt],
  };
}

export function createStarterWorkspace(): SimulatorWorkspace {
  const builds = createStarterBuilds();
  return {
    builds,
    selectedBuildIds: {
      player_a: builds.player_a[0]?.id ?? "",
      player_b: builds.player_b[0]?.id ?? "",
    },
    compare: {
      leftBuildId: builds.player_a[0]?.id ?? "",
      rightBuildId: builds.player_a[1]?.id ?? builds.player_a[0]?.id ?? "",
      leftOpponentBuildId: builds.player_b[0]?.id ?? "",
      rightOpponentBuildId: builds.player_b[0]?.id ?? "",
      linkOpponents: true,
    },
    settings: {
      seed: 1337,
      runs: 5,
      max_time_seconds: 20,
      max_events: 5000,
      combat_log_limit: 120,
    },
  };
}

export function loadWorkspace(): SimulatorWorkspace {
  if (typeof window === "undefined") return createStarterWorkspace();

  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return createStarterWorkspace();
    const parsed = JSON.parse(raw) as SimulatorWorkspace;
    return normalizeWorkspace(parsed);
  } catch {
    return createStarterWorkspace();
  }
}

export function saveWorkspace(workspace: SimulatorWorkspace): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(workspace));
}

export function normalizeWorkspace(workspace: SimulatorWorkspace): SimulatorWorkspace {
  const starter = createStarterWorkspace();
  const builds: Record<BuildSide, BuildDraft[]> = {
    player_a: workspace.builds?.player_a?.length
      ? workspace.builds.player_a
      : starter.builds.player_a,
    player_b: workspace.builds?.player_b?.length
      ? workspace.builds.player_b
      : starter.builds.player_b,
  };

  const selectedBuildIds: Record<BuildSide, string> = {
    player_a: resolveSelectedBuildId(
      builds.player_a,
      workspace.selectedBuildIds?.player_a ?? starter.selectedBuildIds.player_a,
    ),
    player_b: resolveSelectedBuildId(
      builds.player_b,
      workspace.selectedBuildIds?.player_b ?? starter.selectedBuildIds.player_b,
    ),
  };

  const compare: CompareSelection = {
    leftBuildId: resolveSelectedBuildId(
      builds.player_a,
      workspace.compare?.leftBuildId ?? selectedBuildIds.player_a,
    ),
    rightBuildId: resolveSelectedBuildId(
      builds.player_a,
      workspace.compare?.rightBuildId ?? selectedBuildIds.player_a,
    ),
    leftOpponentBuildId: resolveSelectedBuildId(
      builds.player_b,
      workspace.compare?.leftOpponentBuildId ?? selectedBuildIds.player_b,
    ),
    rightOpponentBuildId: resolveSelectedBuildId(
      builds.player_b,
      workspace.compare?.rightOpponentBuildId ??
        workspace.compare?.leftOpponentBuildId ??
        selectedBuildIds.player_b,
    ),
    linkOpponents: workspace.compare?.linkOpponents ?? true,
  };

  if (compare.linkOpponents) {
    compare.rightOpponentBuildId = compare.leftOpponentBuildId;
  }

  return {
    builds,
    selectedBuildIds,
    compare,
    settings: {
      seed: workspace.settings?.seed ?? starter.settings.seed,
      runs: workspace.settings?.runs ?? starter.settings.runs,
      max_time_seconds: workspace.settings?.max_time_seconds ?? starter.settings.max_time_seconds,
      max_events: workspace.settings?.max_events ?? starter.settings.max_events,
      combat_log_limit: workspace.settings?.combat_log_limit ?? starter.settings.combat_log_limit,
    },
  };
}

export function resolveSelectedBuildId(builds: BuildDraft[], buildId: string): string {
  if (builds.some((build) => build.id === buildId)) return buildId;
  return builds[0]?.id ?? "";
}

export function getBuild(
  workspace: SimulatorWorkspace,
  side: BuildSide,
  buildId: string,
): BuildDraft | undefined {
  return workspace.builds[side].find((build) => build.id === buildId);
}

export function updateBuild(
  workspace: SimulatorWorkspace,
  side: BuildSide,
  buildId: string,
  updater: (build: BuildDraft) => BuildDraft,
): SimulatorWorkspace {
  return {
    ...workspace,
    builds: {
      ...workspace.builds,
      [side]: workspace.builds[side].map((build) =>
        build.id === buildId ? updater(build) : build,
      ),
    },
  };
}

export function duplicateBuild(
  workspace: SimulatorWorkspace,
  side: BuildSide,
  buildId: string,
): SimulatorWorkspace {
  const source = getBuild(workspace, side, buildId);
  if (!source) return workspace;

  const duplicate: BuildDraft = {
    ...structuredCloneBuild(source),
    id: uid(`${side}-build`),
    name: `${source.name} Copy`,
    updated_at: nowIso(),
  };

  return {
    ...workspace,
    builds: {
      ...workspace.builds,
      [side]: [duplicate, ...workspace.builds[side]],
    },
    selectedBuildIds: {
      ...workspace.selectedBuildIds,
      [side]: duplicate.id,
    },
  };
}

export function createBuild(side: BuildSide): BuildDraft {
  return makeBuild(
    side,
    side === "player_a" ? "New A Build" : "New B Build",
    [makeItemDefinition("starter", "Starter", defaultEffect("damage"), { cooldown_seconds: 2 })],
    [{ item_instance_id: `${side}-starter`, item_definition_id: "starter", start_slot: 0 }],
    side === "player_a"
      ? { max_health: 40, start_shield: 0, regeneration_per_second: 0.5 }
      : { max_health: 40, start_shield: 0, regeneration_per_second: 0.25 },
    [],
    "Fresh build created from the Simulator page.",
  );
}

export function addBuild(workspace: SimulatorWorkspace, side: BuildSide): SimulatorWorkspace {
  const build = createBuild(side);
  return {
    ...workspace,
    builds: {
      ...workspace.builds,
      [side]: [build, ...workspace.builds[side]],
    },
    selectedBuildIds: {
      ...workspace.selectedBuildIds,
      [side]: build.id,
    },
  };
}

export function removeBuild(
  workspace: SimulatorWorkspace,
  side: BuildSide,
  buildId: string,
): SimulatorWorkspace {
  if (workspace.builds[side].length <= 1) return workspace;
  const remaining = workspace.builds[side].filter((build) => build.id !== buildId);
  const nextSelected = resolveSelectedBuildId(
    remaining,
    workspace.selectedBuildIds[side] === buildId
      ? (remaining[0]?.id ?? "")
      : workspace.selectedBuildIds[side],
  );

  return {
    ...workspace,
    builds: {
      ...workspace.builds,
      [side]: remaining,
    },
    selectedBuildIds: {
      ...workspace.selectedBuildIds,
      [side]: nextSelected,
    },
  };
}

export function setSelectedBuild(
  workspace: SimulatorWorkspace,
  side: BuildSide,
  buildId: string,
): SimulatorWorkspace {
  return {
    ...workspace,
    selectedBuildIds: {
      ...workspace.selectedBuildIds,
      [side]: resolveSelectedBuildId(workspace.builds[side], buildId),
    },
  };
}

export function setCompareSelection(
  workspace: SimulatorWorkspace,
  patch: Partial<CompareSelection>,
): SimulatorWorkspace {
  const next = {
    ...workspace.compare,
    ...patch,
  } satisfies CompareSelection;

  if (next.linkOpponents) {
    next.rightOpponentBuildId = next.leftOpponentBuildId;
  }

  return {
    ...workspace,
    compare: next,
  };
}

export function setSettings(
  workspace: SimulatorWorkspace,
  patch: Partial<SimulatorSettings>,
): SimulatorWorkspace {
  return {
    ...workspace,
    settings: {
      ...workspace.settings,
      ...patch,
    },
  };
}

export function updateActiveBuildName(
  workspace: SimulatorWorkspace,
  side: BuildSide,
  buildId: string,
  name: string,
): SimulatorWorkspace {
  return updateBuild(workspace, side, buildId, (build) => ({
    ...build,
    name,
    updated_at: nowIso(),
  }));
}

export function updateBuildNotes(
  workspace: SimulatorWorkspace,
  side: BuildSide,
  buildId: string,
  notes: string,
): SimulatorWorkspace {
  return updateBuild(workspace, side, buildId, (build) => ({
    ...build,
    notes,
    updated_at: nowIso(),
  }));
}

export function updateBuildStats(
  workspace: SimulatorWorkspace,
  side: BuildSide,
  buildId: string,
  patch: Partial<BuildPlayerStats>,
): SimulatorWorkspace {
  return updateBuild(workspace, side, buildId, (build) => ({
    ...build,
    stats: {
      ...build.stats,
      ...patch,
    },
    updated_at: nowIso(),
  }));
}

export function updateBuildBoardWidth(
  workspace: SimulatorWorkspace,
  side: BuildSide,
  buildId: string,
  width: number,
): SimulatorWorkspace {
  return updateBuild(workspace, side, buildId, (build) => ({
    ...build,
    board: {
      ...build.board,
      width,
      placements: build.board.placements.filter((placement) => placement.start_slot < width),
    },
    updated_at: nowIso(),
  }));
}

export function addItemDefinition(
  workspace: SimulatorWorkspace,
  side: BuildSide,
  buildId: string,
): SimulatorWorkspace {
  return updateBuild(workspace, side, buildId, (build) => {
    const nextIndex = build.item_definitions.length + 1;
    const id = `item-${nextIndex}`;
    const nextSlot = findNextOpenSlot(
      build.board.width,
      build.item_definitions,
      build.board.placements,
    );
    return {
      ...build,
      item_definitions: [
        ...build.item_definitions,
        makeItemDefinition(id, `Item ${nextIndex}`, defaultEffect("damage"), {
          cooldown_seconds: 2,
        }),
      ],
      board: {
        ...build.board,
        placements: [
          ...build.board.placements,
          { item_instance_id: `${side}-${id}`, item_definition_id: id, start_slot: nextSlot },
        ],
      },
      updated_at: nowIso(),
    };
  });
}

export function updateItemDefinition(
  workspace: SimulatorWorkspace,
  side: BuildSide,
  buildId: string,
  itemId: string,
  patch: Partial<BuildItemDefinition>,
): SimulatorWorkspace {
  return updateBuild(workspace, side, buildId, (build) => ({
    ...build,
    item_definitions: build.item_definitions.map((item) =>
      item.id === itemId ? { ...item, ...patch } : item,
    ),
    updated_at: nowIso(),
  }));
}

export function removeItemDefinition(
  workspace: SimulatorWorkspace,
  side: BuildSide,
  buildId: string,
  itemId: string,
): SimulatorWorkspace {
  return updateBuild(workspace, side, buildId, (build) => ({
    ...build,
    item_definitions: build.item_definitions.filter((item) => item.id !== itemId),
    board: {
      ...build.board,
      placements: build.board.placements.filter(
        (placement) => placement.item_definition_id !== itemId,
      ),
    },
    updated_at: nowIso(),
  }));
}

export function addItemEffect(
  workspace: SimulatorWorkspace,
  side: BuildSide,
  buildId: string,
  itemId: string,
): SimulatorWorkspace {
  return updateBuild(workspace, side, buildId, (build) => ({
    ...build,
    item_definitions: build.item_definitions.map((item) =>
      item.id === itemId
        ? updateTimedUseEffects(item, (effects) => [...effects, defaultEffect("damage")])
        : item,
    ),
    updated_at: nowIso(),
  }));
}

export function removeItemEffect(
  workspace: SimulatorWorkspace,
  side: BuildSide,
  buildId: string,
  itemId: string,
  effectIndex: number,
): SimulatorWorkspace {
  return updateBuild(workspace, side, buildId, (build) => ({
    ...build,
    item_definitions: build.item_definitions.map((item) => {
      if (item.id !== itemId) return item;
      return updateTimedUseEffects(item, (effects) => {
        const nextEffects = effects.filter((_, index) => index !== effectIndex);
        return nextEffects.length > 0 ? nextEffects : [defaultEffect("damage")];
      });
    }),
    updated_at: nowIso(),
  }));
}

export function updateItemEffect(
  workspace: SimulatorWorkspace,
  side: BuildSide,
  buildId: string,
  itemId: string,
  effectIndex: number,
  patch: Partial<BuildItemEffect>,
): SimulatorWorkspace {
  return updateBuild(workspace, side, buildId, (build) => ({
    ...build,
    item_definitions: build.item_definitions.map((item) => {
      if (item.id !== itemId) return item;
      return updateTimedUseEffects(item, (effects) =>
        effects.map((effect, index) => (index === effectIndex ? { ...effect, ...patch } : effect)),
      );
    }),
    updated_at: nowIso(),
  }));
}

export function updatePlacement(
  workspace: SimulatorWorkspace,
  side: BuildSide,
  buildId: string,
  placementIndex: number,
  patch: Partial<BuildPlacement>,
): SimulatorWorkspace {
  return updateBuild(workspace, side, buildId, (build) => ({
    ...build,
    board: {
      ...build.board,
      placements: build.board.placements.map((placement, index) =>
        index === placementIndex ? { ...placement, ...patch } : placement,
      ),
    },
    updated_at: nowIso(),
  }));
}

export function getPlacementIndexByInstanceId(build: BuildDraft, itemInstanceId: string): number {
  return build.board.placements.findIndex(
    (placement) => placement.item_instance_id === itemInstanceId,
  );
}

export function getPlacementIndexAtSlot(build: BuildDraft, slot: number): number {
  if (slot < 0 || slot >= build.board.width) return -1;

  return build.board.placements.findIndex((placement) => {
    const item = getItemById(build, placement.item_definition_id);
    const size = item?.size ?? 1;
    return slot >= placement.start_slot && slot < placement.start_slot + size;
  });
}

export function canPlaceItemAtSlot(
  build: BuildDraft,
  itemDefinitionId: string,
  slot: number,
  ignorePlacementIndex?: number,
): boolean {
  const item = getItemById(build, itemDefinitionId);
  const size = item?.size ?? 1;

  if (slot < 0 || slot + size > build.board.width) return false;

  const occupiedSlots = new Set<number>();
  build.board.placements.forEach((placement, placementIndex) => {
    if (placementIndex === ignorePlacementIndex) return;
    const placedItem = getItemById(build, placement.item_definition_id);
    const placedSize = placedItem?.size ?? 1;
    for (
      let placedSlot = placement.start_slot;
      placedSlot < placement.start_slot + placedSize;
      placedSlot += 1
    ) {
      occupiedSlots.add(placedSlot);
    }
  });

  for (let targetSlot = slot; targetSlot < slot + size; targetSlot += 1) {
    if (occupiedSlots.has(targetSlot)) return false;
  }

  return true;
}

export function movePlacementToSlot(
  workspace: SimulatorWorkspace,
  side: BuildSide,
  buildId: string,
  placementIndex: number,
  slot: number,
): SimulatorWorkspace {
  return updateBuild(workspace, side, buildId, (build) => {
    const placement = build.board.placements[placementIndex];
    if (!placement) return build;
    if (!canPlaceItemAtSlot(build, placement.item_definition_id, slot, placementIndex)) {
      return build;
    }

    return {
      ...build,
      board: {
        ...build.board,
        placements: build.board.placements.map((entry, index) =>
          index === placementIndex ? { ...entry, start_slot: slot } : entry,
        ),
      },
      updated_at: nowIso(),
    };
  });
}

export function removePlacement(
  workspace: SimulatorWorkspace,
  side: BuildSide,
  buildId: string,
  placementIndex: number,
): SimulatorWorkspace {
  return updateBuild(workspace, side, buildId, (build) => ({
    ...build,
    board: {
      ...build.board,
      placements: build.board.placements.filter((_, index) => index !== placementIndex),
    },
    updated_at: nowIso(),
  }));
}

export function addPlacementForItem(
  workspace: SimulatorWorkspace,
  side: BuildSide,
  buildId: string,
  itemId: string,
): SimulatorWorkspace {
  return updateBuild(workspace, side, buildId, (build) => ({
    ...build,
    board: {
      ...build.board,
      placements: [
        ...build.board.placements,
        {
          item_instance_id: `${side}-${itemId}-${build.board.placements.length + 1}`,
          item_definition_id: itemId,
          start_slot: findNextOpenSlot(
            build.board.width,
            build.item_definitions,
            build.board.placements,
          ),
        },
      ],
    },
    updated_at: nowIso(),
  }));
}

export function addPlacementForItemAtSlot(
  workspace: SimulatorWorkspace,
  side: BuildSide,
  buildId: string,
  itemId: string,
  slot: number,
): SimulatorWorkspace {
  return updateBuild(workspace, side, buildId, (build) => {
    if (!getItemById(build, itemId)) return build;
    if (!canPlaceItemAtSlot(build, itemId, slot)) return build;

    return {
      ...build,
      board: {
        ...build.board,
        placements: [
          ...build.board.placements,
          {
            item_instance_id: nextItemInstanceId(side, itemId, build.board.placements),
            item_definition_id: itemId,
            start_slot: slot,
          },
        ],
      },
      updated_at: nowIso(),
    };
  });
}

export function validateBuild(build: BuildDraft): ValidationIssue[] {
  const issues: ValidationIssue[] = [];
  const itemIds = new Set<string>();

  build.item_definitions.forEach((item, itemIndex) => {
    if (!item.id.trim()) {
      issues.push({
        side: build.side,
        buildId: build.id,
        path: `item_definitions[${itemIndex}].id`,
        message: "Item id is required.",
      });
    }
    if (itemIds.has(item.id)) {
      issues.push({
        side: build.side,
        buildId: build.id,
        path: `item_definitions[${itemIndex}].id`,
        message: `Duplicate item id ${item.id}.`,
      });
    }
    itemIds.add(item.id);
    if (!item.name.trim()) {
      issues.push({
        side: build.side,
        buildId: build.id,
        path: `item_definitions[${itemIndex}].name`,
        message: "Item name is required.",
      });
    }
    if (item.size < 1 || item.size > 3) {
      issues.push({
        side: build.side,
        buildId: build.id,
        path: `item_definitions[${itemIndex}].size`,
        message: "Item size must be between 1 and 3.",
      });
    }
    if (item.cooldown_seconds <= 0) {
      issues.push({
        side: build.side,
        buildId: build.id,
        path: `item_definitions[${itemIndex}].cooldown_seconds`,
        message: "Cooldown must be greater than 0.",
      });
    }
    if (getTimedUseEffects(item).length === 0) {
      issues.push({
        side: build.side,
        buildId: build.id,
        path: `item_definitions[${itemIndex}].abilities[0].effects`,
        message: "At least one effect is required.",
      });
    }
  });

  const occupied = new Map<number, string>();
  build.board.placements.forEach((placement, placementIndex) => {
    const item = build.item_definitions.find(
      (candidate) => candidate.id === placement.item_definition_id,
    );
    if (!item) {
      issues.push({
        side: build.side,
        buildId: build.id,
        path: `board.placements[${placementIndex}].item_definition_id`,
        message: `Unknown item definition ${placement.item_definition_id}.`,
      });
      return;
    }

    if (placement.start_slot < 0) {
      issues.push({
        side: build.side,
        buildId: build.id,
        path: `board.placements[${placementIndex}].start_slot`,
        message: "Placement start slot must be non-negative.",
      });
    }

    if (placement.start_slot + item.size > build.board.width) {
      issues.push({
        side: build.side,
        buildId: build.id,
        path: `board.placements[${placementIndex}].start_slot`,
        message: `Placement extends beyond board width ${build.board.width}.`,
      });
    }

    for (let slot = placement.start_slot; slot < placement.start_slot + item.size; slot += 1) {
      const occupant = occupied.get(slot);
      if (occupant) {
        issues.push({
          side: build.side,
          buildId: build.id,
          path: `board.placements[${placementIndex}].start_slot`,
          message: `Slot ${slot + 1} overlaps with ${occupant}.`,
        });
        break;
      }
      occupied.set(slot, placement.item_instance_id);
    }
  });

  if (build.board.width < 1) {
    issues.push({
      side: build.side,
      buildId: build.id,
      path: "board.width",
      message: "Board width must be at least 1.",
    });
  }

  return issues;
}

export function validateWorkspace(workspace: SimulatorWorkspace): ValidationIssue[] {
  const issues: ValidationIssue[] = [];
  workspace.builds.player_a.forEach((build) => issues.push(...validateBuild(build)));
  workspace.builds.player_b.forEach((build) => issues.push(...validateBuild(build)));

  if (!getBuild(workspace, "player_a", workspace.selectedBuildIds.player_a)) {
    issues.push({
      side: "player_a",
      buildId: workspace.selectedBuildIds.player_a,
      path: "selectedBuildIds.player_a",
      message: "Selected player A build is missing.",
    });
  }
  if (!getBuild(workspace, "player_b", workspace.selectedBuildIds.player_b)) {
    issues.push({
      side: "player_b",
      buildId: workspace.selectedBuildIds.player_b,
      path: "selectedBuildIds.player_b",
      message: "Selected player B build is missing.",
    });
  }

  return issues;
}

export function materializeMatchupRequest(matchup: MatchupRequest): SimulationRequest {
  return {
    seed: matchup.settings.seed,
    runs: matchup.settings.runs,
    max_time_seconds: matchup.settings.max_time_seconds,
    max_events: matchup.settings.max_events,
    combat_log_limit: matchup.settings.combat_log_limit,
    item_definitions: [
      ...materializeBuildItemDefinitions(matchup.playerA, "a"),
      ...materializeBuildItemDefinitions(matchup.playerB, "b"),
    ],
    players: [
      materializePlayer(matchup.playerA, "player_a", "a"),
      materializePlayer(matchup.playerB, "player_b", "b"),
    ],
  };
}

function materializeBuildItemDefinitions(
  build: BuildDraft,
  sideToken: string,
): BuildItemDefinition[] {
  return build.item_definitions.map((item, index) => ({
    ...item,
    id: `${sideToken}${index}`,
  }));
}

function materializePlayer(
  build: BuildDraft,
  side: BuildSide,
  sideToken: string,
): SimulationRequest["players"][number] {
  const prefixedItems = new Map(
    build.item_definitions.map((item, index) => [item.id, `${sideToken}${index}`]),
  );

  return {
    player_id: side,
    stats: structuredClone(build.stats),
    board: {
      width: build.board.width,
      placements: build.board.placements.map((placement, index) => ({
        ...placement,
        item_instance_id: `${sideToken}i${index}`,
        item_definition_id:
          prefixedItems.get(placement.item_definition_id) ?? placement.item_definition_id,
      })),
    },
    initial_statuses: build.initial_statuses.map((status) => ({ ...status })),
  };
}

export function deriveDamageSeries(
  response: SimulationResponse | undefined,
  label: string,
  color: string,
  overlayRunIndex = 0,
): DamageSeries {
  if (!response || response.runs.length === 0) {
    return { label, color, median: [], overlay: [], maxTime: 0, totalDamage: 0 };
  }

  const perRun = response.runs.map((run) =>
    buildRunSeries(run.combat_log ?? [], run.duration_seconds),
  );
  const maxTime = Math.max(...perRun.map((series) => series[series.length - 1]?.time ?? 0), 0);
  const totalDamage = Math.max(...perRun.map((series) => series[series.length - 1]?.value ?? 0), 0);
  const median = medianSeries(perRun);
  const overlay = perRun[overlayRunIndex] ?? perRun[0] ?? [];

  return { label, color, median, overlay, maxTime, totalDamage };
}

function buildRunSeries(
  combatLog: SimulationResponse["runs"][number]["combat_log"],
  durationSeconds: number,
): DamageSeriesPoint[] {
  const points: DamageSeriesPoint[] = [{ time: 0, value: 0 }];
  let cumulative = 0;

  (combatLog ?? []).forEach((entry) => {
    const playerBDelta = entry.state_deltas?.find((delta) => delta.player_id === "player_b");
    const damage = Math.max(0, -(playerBDelta?.health_delta ?? 0));
    cumulative += damage;
    points.push({ time: entry.time_seconds, value: cumulative });
  });

  const lastTime = points[points.length - 1]?.time ?? 0;
  if (lastTime < durationSeconds) {
    points.push({ time: durationSeconds, value: cumulative });
  }

  return points;
}

function medianSeries(seriesList: DamageSeriesPoint[][]): DamageSeriesPoint[] {
  if (seriesList.length === 0) return [];

  const times = Array.from(
    new Set(seriesList.flatMap((series) => series.map((point) => point.time))),
  ).sort((a, b) => a - b);

  return times.map((time) => ({
    time,
    value: median(seriesList.map((series) => valueAt(series, time))),
  }));
}

function valueAt(series: DamageSeriesPoint[], time: number): number {
  let result = 0;
  for (const point of series) {
    if (point.time > time) break;
    result = point.value;
  }
  return result;
}

function median(values: number[]): number {
  if (values.length === 0) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  if (sorted.length % 2 === 0) return (sorted[mid - 1] + sorted[mid]) / 2;
  return sorted[mid];
}

function structuredCloneBuild(build: BuildDraft): BuildDraft {
  return JSON.parse(JSON.stringify(build)) as BuildDraft;
}

function getItemById(build: BuildDraft, itemId: string): BuildItemDefinition | undefined {
  return build.item_definitions.find((item) => item.id === itemId);
}

function findNextOpenSlot(
  width: number,
  items: BuildItemDefinition[],
  placements: BuildPlacement[],
): number {
  const occupied = new Set<number>();
  placements.forEach((placement) => {
    const item = items.find((candidate) => candidate.id === placement.item_definition_id);
    const size = item?.size ?? 1;
    for (let slot = placement.start_slot; slot < placement.start_slot + size; slot += 1) {
      occupied.add(slot);
    }
  });

  for (let slot = 0; slot < width; slot += 1) {
    if (!occupied.has(slot)) return slot;
  }

  return 0;
}

function nextItemInstanceId(side: BuildSide, itemId: string, placements: BuildPlacement[]): string {
  const base = `${side}-${itemId}`;
  let suffix = 1;
  while (placements.some((placement) => placement.item_instance_id === `${base}-${suffix}`)) {
    suffix += 1;
  }
  return `${base}-${suffix}`;
}
