import type {
  Addresses,
  Backup,
  BackupPolicy,
  Instance,
  InstalledMod,
  McVersion,
  ModSearchHit,
  ModUpdate,
  OpEntry,
  Player,
  PropertiesPatch,
  SetupRequest,
  WhitelistEntry,
} from "./types";

export class ApiError extends Error {
  constructor(
    public status: number,
    detail: string,
  ) {
    super(detail);
  }
}

async function req<T>(method: string, path: string, body?: unknown): Promise<T> {
  const resp = await fetch(`/api${path}`, {
    method,
    headers: body !== undefined ? { "Content-Type": "application/json" } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!resp.ok) {
    let detail = resp.statusText;
    try {
      const data = await resp.json();
      detail = typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail);
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(resp.status, detail);
  }
  if (resp.status === 204) return undefined as T;
  return resp.json();
}

export const api = {
  addresses: () => req<Addresses>("GET", "/addresses"),

  servers: {
    list: () => req<Instance[]>("GET", "/servers"),
    get: (id: number) => req<Instance>("GET", `/servers/${id}`),
    setup: (body: SetupRequest) => req<Instance>("POST", "/servers/setup", body),
    delete: (id: number, deleteData: boolean) =>
      req<void>("DELETE", `/servers/${id}?delete_data=${deleteData}`),
    start: (id: number) => req<Instance>("POST", `/servers/${id}/start`),
    stop: (id: number) => req<Instance>("POST", `/servers/${id}/stop`),
    restart: (id: number) => req<Instance>("POST", `/servers/${id}/restart`),
    properties: (id: number) => req<Record<string, string>>("GET", `/servers/${id}/properties`),
    patchProperties: (id: number, updates: Record<string, unknown>) =>
      req<PropertiesPatch>("PATCH", `/servers/${id}/properties`, updates),
    command: (id: number, command: string) =>
      req<{ response: string }>("POST", `/servers/${id}/command`, { command }),
    whitelist: (id: number) => req<WhitelistEntry[]>("GET", `/servers/${id}/whitelist`),
    addWhitelist: (id: number, username: string) =>
      req<WhitelistEntry[]>("POST", `/servers/${id}/whitelist`, { username }),
    removeWhitelist: (id: number, username: string) =>
      req<void>("DELETE", `/servers/${id}/whitelist/${encodeURIComponent(username)}`),
    ops: (id: number) => req<OpEntry[]>("GET", `/servers/${id}/ops`),
    addOp: (id: number, username: string, level = 4) =>
      req<OpEntry[]>("POST", `/servers/${id}/ops`, { username, level }),
    removeOp: (id: number, username: string) =>
      req<void>("DELETE", `/servers/${id}/ops/${encodeURIComponent(username)}`),
    setExtraPorts: (id: number, ports: { host: number; container: number; proto: string }[]) =>
      req<{ extra_ports: unknown[] }>("PUT", `/servers/${id}/extra-ports`, ports),
    consoleUrl(id: number): string {
      const proto = location.protocol === "https:" ? "wss" : "ws";
      return `${proto}://${location.host}/api/servers/${id}/console`;
    },
  },

  backups: {
    listAll: () => req<Backup[]>("GET", "/backups"),
    listFor: (id: number) => req<Backup[]>("GET", `/servers/${id}/backups`),
    create: (id: number, note: string) =>
      req<Backup>("POST", `/servers/${id}/backups`, { note }),
    delete: (backupId: number) => req<void>("DELETE", `/backups/${backupId}`),
    restore: (backupId: number) => req<Backup>("POST", `/backups/${backupId}/restore`),
    clone: (backupId: number, name: string) =>
      req<Instance>("POST", `/backups/${backupId}/clone`, { name }),
    setPolicy: (id: number, policy: BackupPolicy) =>
      req<{ policy: BackupPolicy; pruned: number }>(
        "PUT",
        `/servers/${id}/backup-policy`,
        policy,
      ),
  },

  mods: {
    search: (query: string, mcVersion?: string) =>
      req<ModSearchHit[]>(
        "GET",
        `/mods/search?query=${encodeURIComponent(query)}` +
          (mcVersion ? `&mc_version=${encodeURIComponent(mcVersion)}` : ""),
      ),
    list: (id: number) => req<InstalledMod[]>("GET", `/servers/${id}/mods`),
    install: (id: number, project: string, versionId?: string) =>
      req<{ installed: InstalledMod[]; restart_required: boolean }>(
        "POST",
        `/servers/${id}/mods`,
        { project, version_id: versionId ?? null },
      ),
    uninstall: (id: number, projectId: string, force = false) =>
      req<void>("DELETE", `/servers/${id}/mods/${projectId}?force=${force}`),
    patch: (id: number, projectId: string, body: { enabled?: boolean; auto_update?: boolean }) =>
      req<InstalledMod>("PATCH", `/servers/${id}/mods/${projectId}`, body),
    checkUpdates: (id: number) => req<ModUpdate[]>("POST", `/servers/${id}/mods/check-updates`),
    update: (id: number, projectId: string) =>
      req<{ updated: boolean; version: string; restart_required: boolean }>(
        "POST",
        `/servers/${id}/mods/${projectId}/update`,
      ),
  },

  players: {
    list: () => req<Player[]>("GET", "/players"),
    lookup: (username: string) => req<Player>("POST", "/players", { username }),
  },

  versions: {
    minecraft: (type = "release") => req<McVersion[]>("GET", `/versions/minecraft?type=${type}`),
    fabric: (mcVersion: string) =>
      req<{ version: string; stable: boolean }[]>("GET", `/versions/fabric/${mcVersion}`),
  },
};
