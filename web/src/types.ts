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
  jvm_flags: string;
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
  username: string;
  uuid: string;
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
  size_bytes: number;
  kind: "manual" | "scheduled" | "pre_restore";
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
