// Mirrors the FastAPI response models.

export type Loader = "vanilla" | "fabric";

export interface Instance {
  id: number;
  name: string;
  mc_version: string;
  loader: Loader;
  loader_version: string | null;
  java_major: number;
  game_port: number;
  rcon_port: number;
  extra_ports_json: string;
  memory: string;
  cpus: number; // CPU core cap; 0 = unlimited
  jvm_flags: string;
  backup_enabled: boolean;
  backup_interval_hours: number;
  backup_keep_count: number;
  backup_keep_days: number;
  created_at: string;
  status: string; // running | exited | created | not_created | ...
}

export interface SetupRequest {
  name: string;
  mc_version: string;
  loader: Loader;
  loader_version?: string | null;
  memory: string;
  jvm_flags?: string;
  accept_eula: boolean;
  properties: Record<string, string | number | boolean>;
  whitelist: string[];
  ops: string[];
  start: boolean;
}

export interface AddressEntry {
  name: string;
  address: string;
  public_address: string | null; // null when WAN IP detection failed
  game_port: number;
  rcon_port: number;
  status: string;
  port_forward_hint: string;
}

export interface Addresses {
  lan_ip: string;
  public_ip: string | null;
  servers: AddressEntry[];
}

export interface Player {
  id: number;
  username: string; // bedrock players are stored as ".GamerTag"
  uuid: string;
  platform: "java" | "bedrock";
  cached_at: string;
}

export interface WhitelistEntry {
  uuid: string;
  name: string;
}

export interface OpEntry extends WhitelistEntry {
  level: number;
  bypassesPlayerLimit: boolean;
}

export interface Backup {
  id: number;
  instance_id: number | null;
  instance_name: string;
  mc_version: string;
  loader: string;
  loader_version: string | null;
  filename: string;
  path: string; // absolute path on the docker host, for manual inspection
  size_bytes: number;
  kind: "manual" | "scheduled" | "pre_restore" | "pre_upgrade";
  note: string;
  created_at: string;
}

export interface BackupPolicy {
  enabled: boolean;
  interval_hours: number;
  keep_count: number;
  keep_days: number;
}

export interface InstalledMod {
  id: number;
  instance_id: number;
  project_id: string;
  slug: string;
  title: string;
  version_id: string;
  version_number: string;
  filename: string;
  enabled: boolean;
  auto_update: boolean;
  dependency_of: string | null;
  requires_json: string;
  installed_at: string;
}

export interface ModSearchHit {
  project_id: string;
  slug: string;
  title: string;
  description: string;
  downloads: number;
  icon_url: string | null;
}

export interface ModUpdate {
  project_id: string;
  title: string;
  installed: string;
  available: string;
  available_version_id: string;
  auto_update: boolean;
}

export interface McVersion {
  id: string;
  type: string;
  releaseTime: string;
}

export interface PropertiesPatch {
  properties: Record<string, string>;
  restart_required: boolean;
}

// --- version upgrades ------------------------------------------------------

export interface ModPlanEntry {
  project_id: string;
  slug: string;
  title: string;
  enabled: boolean;
  installed: string;
  available: string | null;
  // blocked = enabled with no build for the target; skipped = same but disabled
  status: "ok" | "blocked" | "skipped" | "unknown";
  available_version_id?: string;
  detail?: string;
}

export interface Preflight {
  current_version: string;
  target_version: string;
  loader: Loader;
  ready: boolean;
  blockers: string[];
  warnings: string[];
  mods: ModPlanEntry[];
  java?: { current: number; target: number; changed: boolean; image_build_required: boolean };
  loader_version?: { current: string | null; target: string };
}

export interface UpgradeResult {
  from_version: string;
  to_version: string;
  backup_id: number;
  was_running: boolean;
  preflight: Preflight;
  java_major: number;
  loader_version: string | null;
  memory: string;
  mods: {
    updated: { title: string; version: string }[];
    unchanged: string[];
    disabled: string[];
    added: string[];
  };
}

export interface HealthFinding {
  reason: string;
  recommendation: string;
}

export interface HealthCheck {
  verdict: "healthy" | "crash_loop" | "exited" | "timeout";
  healthy: boolean;
  summary: string;
  elapsed_seconds: number;
  exit_code: number | null;
  restart_count: number;
  oom_killed: boolean;
  log_tail: string;
  findings: HealthFinding[];
  rollback?: { backup_id: number; recommendation: string; endpoint: string };
}
