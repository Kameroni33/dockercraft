"""Minecraft version upgrades: pre-flight compatibility check, the upgrade
itself, and a post-boot health check that diagnoses a failed start.

Flow the UI drives (each step is a separate bounded request):

    preflight()    -> can we move to <target>? what happens to each mod?
    upgrade()      -> mandatory backup, re-provision, re-resolve mods, rebuild
    health_check() -> start, watch, say whether it came up and what to do next

Nothing here starts the server implicitly: upgrade() leaves the container
removed so health_check() observes a clean first boot on the new version.

Rollback is "restore the pre_upgrade backup" — restore_backup() syncs
mc_version/java_major/server_jar AND the installed-mod rows back to the
snapshot, so it is a true version rollback, not just a world rollback.
"""

import json
import re
import time
from dataclasses import dataclass

from sqlmodel import Session

from api.clients import fabric, modrinth, mojang
from api.models.instance import Loader, ServerInstance
from api.services import backups, docker_manager, instances, mods, provision

LATEST = "latest"

# MC prints this once the server is accepting connections — the only log line
# that reliably means "came up clean", on vanilla and Fabric alike.
DONE_RE = re.compile(r"Done \([0-9.]+s\)!")

HEALTH_TIMEOUT = 300  # seconds to wait for Done before calling it inconclusive
POLL_INTERVAL = 3


class UpgradeError(Exception):
    pass


class UpgradeBlockedError(UpgradeError):
    """Pre-flight found blockers and the caller didn't opt out of them."""

    def __init__(self, message: str, report: dict):
        super().__init__(message)
        self.report = report


def resolve_target(mc_version: str) -> str:
    return mojang.latest_release() if mc_version == LATEST else mc_version


# --------------------------------------------------------------------------
# Pre-flight
# --------------------------------------------------------------------------


def _mod_plan(session: Session, instance: ServerInstance, target: str) -> list[dict]:
    """Per installed mod: is there a build for the target MC version?

    status is one of:
      ok        - a compatible build exists (may be the installed one already)
      blocked   - no build for the target, and the mod is ENABLED
      skipped   - no build for the target, but the mod is disabled (won't load)
      unknown   - Modrinth couldn't be reached / project is gone
    """
    plan = []
    for mod in mods.list_mods(session, instance):
        entry = {
            "project_id": mod.project_id,
            "slug": mod.slug,
            "title": mod.title,
            "enabled": mod.enabled,
            "installed": mod.version_number,
            "available": None,
            "status": "unknown",
        }
        try:
            versions = modrinth.get_versions(mod.project_id, "fabric", target)
        except (modrinth.ProjectNotFoundError, OSError) as e:
            entry["detail"] = f"could not check Modrinth: {e}"
            plan.append(entry)
            continue
        if versions:
            entry["status"] = "ok"
            entry["available"] = versions[0]["version_number"]
            entry["available_version_id"] = versions[0]["id"]
        else:
            entry["status"] = "blocked" if mod.enabled else "skipped"
            entry["detail"] = f"no fabric build for MC {target}"
        plan.append(entry)
    return plan


def preflight(
    session: Session,
    instance: ServerInstance,
    mc_version: str,
    loader_version: str | None = None,
) -> dict:
    """Everything we can learn without touching the instance. Safe to call
    repeatedly; makes one Modrinth request per installed mod."""
    target = resolve_target(mc_version)
    report: dict = {
        "current_version": instance.mc_version,
        "target_version": target,
        "loader": instance.loader,
        "blockers": [],
        "warnings": [],
    }

    try:
        version_json = mojang.get_version(target)
    except mojang.VersionNotFoundError as e:
        report["blockers"].append(str(e))
        report["ready"] = False
        return report

    target_java = mojang.java_major(version_json)
    report["java"] = {
        "current": instance.java_major,
        "target": target_java,
        "changed": target_java != instance.java_major,
        # A new major means building the per-Java MC image — slow, not fatal.
        "image_build_required": not _image_present(target_java),
    }
    if report["java"]["image_build_required"]:
        report["warnings"].append(
            f"Java {target_java} image isn't built yet — the upgrade will build "
            "it first, which can take a few minutes."
        )

    if target == instance.mc_version:
        report["warnings"].append(f"instance is already on MC {target}")

    if instance.loader == Loader.FABRIC:
        try:
            resolved_loader = loader_version or fabric.latest_stable_loader(target)
            report["loader_version"] = {
                "current": instance.loader_version,
                "target": resolved_loader,
            }
        except (fabric.NoLoaderError, OSError) as e:
            report["blockers"].append(f"no Fabric loader for MC {target}: {e}")

        report["mods"] = _mod_plan(session, instance, target)
        blocked = [m for m in report["mods"] if m["status"] == "blocked"]
        unknown = [m for m in report["mods"] if m["status"] == "unknown"]
        skipped = [m for m in report["mods"] if m["status"] == "skipped"]
        for m in blocked:
            report["blockers"].append(f"{m['title']} has no Fabric build for MC {target}")
        for m in unknown:
            report["warnings"].append(f"{m['title']}: {m.get('detail', 'check failed')}")
        for m in skipped:
            report["warnings"].append(
                f"{m['title']} has no build for MC {target} but is disabled — "
                "it will stay disabled."
            )
    else:
        report["mods"] = []

    report["ready"] = not report["blockers"]
    return report


def _image_present(java_major: int) -> bool:
    from docker.errors import ImageNotFound

    try:
        docker_manager.get_client().images.get(docker_manager.image_tag(java_major))
    except (ImageNotFound, OSError):
        return False
    return True


# --------------------------------------------------------------------------
# Upgrade
# --------------------------------------------------------------------------


@dataclass
class _Snapshot:
    """Instance provisioning fields, for rolling the DB row back if the
    upgrade throws partway (the disk is covered by the pre_upgrade backup)."""

    mc_version: str
    loader_version: str | None
    java_major: int
    server_jar: str
    memory: str

    @classmethod
    def of(cls, instance: ServerInstance) -> "_Snapshot":
        return cls(
            instance.mc_version,
            instance.loader_version,
            instance.java_major,
            instance.server_jar,
            instance.memory,
        )

    def apply_to(self, instance: ServerInstance) -> None:
        instance.mc_version = self.mc_version
        instance.loader_version = self.loader_version
        instance.java_major = self.java_major
        instance.server_jar = self.server_jar
        instance.memory = self.memory


def upgrade(
    session: Session,
    instance: ServerInstance,
    mc_version: str,
    loader_version: str | None = None,
    memory: str | None = None,
    disable_incompatible: bool = False,
) -> dict:
    """Move an instance to a new MC version. Always takes a pre_upgrade backup
    first. Leaves the server STOPPED with its container removed — call
    health_check() to boot it and see whether it survived.

    disable_incompatible overrides pre-flight blockers by renaming mods with no
    compatible build to .disabled, so the server can at least boot without them.
    """
    report = preflight(session, instance, mc_version, loader_version)
    if not report["ready"] and not disable_incompatible:
        raise UpgradeBlockedError(
            "pre-flight found incompatible mods; resolve them, or re-run with "
            "disable_incompatible=true to turn them off and upgrade anyway",
            report,
        )
    target = report["target_version"]

    # Mandatory, and taken while still on the OLD version so it's a real
    # rollback point. Hot if running — create_backup handles save-off/flush.
    backup = backups.create_backup(
        session,
        instance,
        kind="pre_upgrade",
        note=f"auto, before upgrading {instance.mc_version} -> {target}",
    )

    was_running = docker_manager.status(instance) == "running"
    if was_running:
        docker_manager.stop(instance)

    before = _Snapshot.of(instance)
    result: dict = {
        "from_version": before.mc_version,
        "to_version": target,
        "backup_id": backup.id,
        "preflight": report,
        "was_running": was_running,
    }

    try:
        instance.mc_version = target
        # Clear the old loader pin unless one was named: a Fabric loader build
        # is per-MC-version, so carrying the old one over installs the wrong jar.
        instance.loader_version = loader_version
        if memory is not None:
            docker_manager.heap_bytes(memory)  # validate before persisting
            instance.memory = memory

        provision.provision_instance(instance)  # sets java_major, server_jar, jar on disk
        session.add(instance)
        session.commit()
        session.refresh(instance)

        # Build the per-Java-major image now so a failure surfaces here rather
        # than as a mysterious start error later.
        docker_manager.ensure_image(instance.java_major)

        result["java_major"] = instance.java_major
        result["loader_version"] = instance.loader_version
        result["memory"] = instance.memory
        result["mods"] = _migrate_mods(session, instance, report, disable_incompatible)
    except Exception as e:
        before.apply_to(instance)
        session.add(instance)
        session.commit()
        raise UpgradeError(
            f"upgrade to {target} failed and the instance record was rolled back "
            f"({e}). Files on disk may be half-written — restore backup "
            f"{backup.id} if the server misbehaves."
        ) from e

    # Rebuild from scratch: image tag and MEMORY env both may have changed.
    docker_manager.remove_container(instance)
    return result


def _migrate_mods(
    session: Session,
    instance: ServerInstance,
    report: dict,
    disable_incompatible: bool,
) -> dict:
    """Move every installed mod onto a build for the instance's (now new) MC
    version, pull in any newly-required dependencies, and disable the ones with
    no compatible build."""
    updated, unchanged, disabled, added = [], [], [], []
    if instance.loader != Loader.FABRIC:
        return {"updated": [], "unchanged": [], "disabled": [], "added": []}

    status_by_id = {m["project_id"]: m["status"] for m in report.get("mods", [])}

    for mod in mods.list_mods(session, instance):
        if status_by_id.get(mod.project_id) in ("blocked", "skipped"):
            if mod.enabled:
                mods.set_enabled(instance, mod, False)
                session.add(mod)
                disabled.append(mod.title)
            continue
        try:
            # update_mod queries Modrinth with instance.mc_version, which is
            # already the target — so "newest compatible" means the new version.
            if mods.update_mod(session, instance, mod):
                updated.append({"title": mod.title, "version": mod.version_number})
            else:
                unchanged.append(mod.title)
        except (modrinth.ProjectNotFoundError, modrinth.ChecksumError, OSError) as e:
            # Leave the old jar; flag it loudly rather than half-migrating.
            disabled.append(f"{mod.title} (update failed: {e})")
            if mod.enabled:
                mods.set_enabled(instance, mod, False)
                session.add(mod)
    session.commit()

    # A mod's new version can require a dependency its old version didn't.
    for mod in mods.list_mods(session, instance):
        if not mod.enabled:
            continue
        for dep_id in json.loads(mod.requires_json):
            if mods.get_mod(session, instance, dep_id) is None:
                try:
                    for new in mods.install_mod(session, instance, dep_id):
                        added.append(new.title)
                except mods.ModError as e:
                    raise UpgradeError(
                        f"{mod.title} now requires a dependency that can't be "
                        f"installed for MC {instance.mc_version}: {e}"
                    ) from e

    return {
        "updated": updated,
        "unchanged": unchanged,
        "disabled": disabled,
        "added": added,
    }


# --------------------------------------------------------------------------
# Health check
# --------------------------------------------------------------------------

# (pattern, what it means, what to do about it). Ordered: first match wins per
# category, but all matching entries are reported.
CRASH_SIGNATURES: list[tuple[re.Pattern, str, str]] = [
    (
        re.compile(r"UnsupportedClassVersionError|has been compiled by a more recent"),
        "A jar needs a newer Java than the container provides.",
        "The instance's java_major is wrong for this MC version — re-run the "
        "upgrade so it is re-read from piston-meta, or restore the backup.",
    ),
    (
        re.compile(r"Incompatible mod set|requires .*fabricloader|Incompatible mods found"),
        "Fabric refused the mod set: a mod wants a different loader or MC version.",
        "Check the console for the offending mod, disable it in the Mods tab, "
        "then start again. If it's essential, roll back and wait for it to update.",
    ),
    (
        re.compile(r"Mixin apply(ing)? failed|MixinApplyError|InvalidInjectionException"),
        "A mod's mixins don't match this MC version — almost always a mod built "
        "for the old version still in mods/.",
        "Disable the mod named in the stack trace and start again, or roll back.",
    ),
    (
        re.compile(r"NoSuchMethodError|NoClassDefFoundError|NoSuchFieldError"),
        "A mod is calling game code that changed in this MC version.",
        "Disable the mod named in the stack trace and start again, or roll back.",
    ),
    (
        re.compile(r"OutOfMemoryError|Java heap space|GC overhead limit"),
        "The JVM ran out of heap.",
        "Raise the memory limit in Settings (a modded 1.21+ server usually wants "
        "4G or more) and start again.",
    ),
    (
        re.compile(
            r"world was (last )?(loaded|saved) in|downgrade is not supported|Version mismatch"
        ),
        "The world was written by a newer MC version than the server is running.",
        "Minecraft can't downgrade a world. Roll back to the pre-upgrade backup; "
        "do not start the old version against this world.",
    ),
    (
        re.compile(r"Failed to bind to port|Address already in use"),
        "The game port is already taken on the host.",
        "Another process (or a leftover container) holds the port — stop it, or "
        "give this instance a different port.",
    ),
    (
        re.compile(r"You need to agree to the EULA|eula\.txt"),
        "The EULA file wasn't accepted.",
        "Unexpected after an upgrade — the instance dir may be damaged. Restore "
        "the pre-upgrade backup.",
    ),
    (
        re.compile(
            r"Could not find or load main class|Unable to access jarfile"
            r"|Invalid or corrupt jarfile"
        ),
        "The server jar is missing, truncated or unreadable.",
        "Provisioning didn't complete. Re-run the upgrade, or restore the backup.",
    ),
    (
        re.compile(
            r"Too small initial heap|Could not create the Java Virtual Machine"
            r"|Invalid maximum heap size|Error occurred during initialization of VM"
        ),
        "The JVM refused to start with the configured heap size.",
        "The memory setting is too small (or malformed) for this server. Raise it "
        "in Settings — 4G is a sane floor for a modded 1.21+ world.",
    ),
]


def diagnose(log_text: str, state: dict) -> list[dict]:
    """Map container state + log output onto human next steps."""
    findings = []
    if state.get("oom_killed"):
        findings.append(
            {
                "reason": "Docker killed the container for exceeding its memory limit.",
                "recommendation": "Raise the memory limit in Settings — the container "
                "cap is heap x1.5, so a bigger heap also raises the cap.",
            }
        )
    for pattern, reason, recommendation in CRASH_SIGNATURES:
        if pattern.search(log_text):
            findings.append({"reason": reason, "recommendation": recommendation})
    # Observed with an unusable heap size: the JVM exits before the server logs
    # anything, and the launcher's own error never reaches the container's
    # stdout. An all-but-empty log is itself the clue.
    if not findings and len(log_text.strip().splitlines()) <= 3:
        findings.append(
            {
                "reason": "The server died before producing any output — the JVM "
                "itself failed to start.",
                "recommendation": "Almost always the memory setting or a bad JVM "
                "flag. Check both in Settings (a heap under ~1G can't launch a "
                "Minecraft server at all), then start again.",
            }
        )
    return findings


def health_check(
    session: Session,
    instance: ServerInstance,
    timeout: int = HEALTH_TIMEOUT,
    rollback_backup_id: int | None = None,
) -> dict:
    """Start the instance (if needed) and watch until it reports Done, dies, or
    the timeout expires. Returns a verdict plus recommended next steps.

    Blocking by design — it is the caller's progress bar.
    """
    baseline = docker_manager.state(instance)["restart_count"]
    # A container's log outlives its restarts, so a previous boot's "Done" line
    # is still sitting there. Scope to this boot or we'd pass instantly on it.
    since: int | None = None
    if docker_manager.status(instance) != "running":
        since = int(time.time()) - 1
        instances.start_instance(instance)

    started = time.monotonic()
    verdict, state = "timeout", docker_manager.state(instance)
    while time.monotonic() - started < timeout:
        time.sleep(POLL_INTERVAL)
        state = docker_manager.state(instance)
        log_text = docker_manager.logs(instance, tail=400, since=since)

        if DONE_RE.search(log_text):
            verdict = "healthy"
            break
        # unless-stopped means a crashed server comes back up, so "exited" is a
        # narrow window — a climbing restart count is the reliable crash signal.
        if state["restart_count"] > baseline:
            verdict = "crash_loop"
            break
        if state["status"] == "exited":
            verdict = "exited"
            break

    log_text = docker_manager.logs(instance, tail=400, since=since)
    healthy = verdict == "healthy"
    result = {
        "verdict": verdict,
        "healthy": healthy,
        "elapsed_seconds": round(time.monotonic() - started, 1),
        "exit_code": state.get("exit_code"),
        "restart_count": state.get("restart_count"),
        "oom_killed": state.get("oom_killed"),
        "log_tail": "\n".join(log_text.splitlines()[-80:]),
        "findings": [] if healthy else diagnose(log_text, state),
    }

    if healthy:
        result["summary"] = (
            f"{instance.name} came up on MC {instance.mc_version} in {result['elapsed_seconds']}s."
        )
    else:
        result["summary"] = _failure_summary(instance, verdict, timeout)
        if not result["findings"]:
            result["findings"] = [
                {
                    "reason": "No known crash signature in the log.",
                    "recommendation": "Read the console output below for the first "
                    "ERROR/FATAL line.",
                }
            ]
        if rollback_backup_id is not None:
            # Crash loops keep restarting; stop before the operator reads this.
            if verdict == "crash_loop":
                docker_manager.stop(instance)
            result["rollback"] = {
                "backup_id": rollback_backup_id,
                "recommendation": (
                    f"To undo the upgrade entirely, restore backup "
                    f"{rollback_backup_id} — that puts the version, the jar, the "
                    f"mod set and the world back as they were."
                ),
                "endpoint": f"/api/backups/{rollback_backup_id}/restore",
            }
    return result


def _failure_summary(instance: ServerInstance, verdict: str, timeout: int) -> str:
    if verdict == "crash_loop":
        return f"{instance.name} crashed and Docker restarted it — stopped it to break the loop."
    if verdict == "exited":
        return f"{instance.name} exited without finishing startup."
    return (
        f"{instance.name} hadn't finished starting after {timeout}s. A big world "
        f"or a first Fabric boot can legitimately take this long — check the "
        f"console before assuming failure."
    )
