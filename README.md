MinecraftFest Ops Scripts

## Quick Reference

All commands below are run **on the game server**. SSH in first:

```
ssh minecraft
```

### 1. Pull Latest Config Changes to the Server

```
cd /srv/minecraftfest-config && git pull
```

Or as a one-liner from your local machine:

```
ssh minecraft "cd /srv/minecraftfest-config && git pull"
```

### 2. Deploy Plugins to All Servers

Syncs jar files from `shared/plugin-jars/` into every MSM server's `plugins/` folder. Does **not** touch plugin data/config folders — only `.jar` files.

```
cd /srv/minecraftfest-config
./scripts/deploy-plugins.sh
```

Then restart servers to apply:

```
msm <server> restart now    # one server
msm restart now             # all active servers
```

### 3. Update Paper to Latest Build

Downloads the latest Paper build for the configured Minecraft version (currently defaults to `1.21.11`) and repoints the `paper-current.jar` symlink.

```
cd /srv/minecraftfest-config
./scripts/msm-paper-update
```

To target a specific Minecraft version:

```
./scripts/msm-paper-update 1.21.11
```

Then restart servers to apply:

```
msm <server> restart now    # one server
msm restart now             # all active servers
```

### Typical Workflow

1. Make changes locally (add/remove plugin jars, edit scripts, etc.)
2. Commit and push to GitHub
3. Pull to the server: `ssh minecraft "cd /srv/minecraftfest-config && git pull"`
4. Run the relevant script(s) on the server
5. Restart servers when ready

---

## Prerequisites

### Common
- MSM installed with servers under `/opt/msm/servers`
- Shell access on the host with read/write permissions under `/opt/msm`

### deploy-plugins.sh
- `rsync` installed
- Shared plugin jar staging directory at `shared/plugin-jars/` (relative to repo root)

### msm-paper-update
- `curl`
- `python3`
- MSM installed and `msm` available in PATH
- Outbound HTTPS access to `https://api.papermc.io`

---

## Directory Layout

```
/srv/minecraftfest-config/          <-- this repo on the server
  shared/
    plugin-jars/
      LuckPerms.jar
      ...
  scripts/
    deploy-plugins.sh
    msm-paper-update

/opt/msm/servers/<server>/plugins/  <-- where deploy-plugins.sh syncs to
  <plugin>.jar
  <plugin-data-folders>/            <-- NOT modified by deploy script

/opt/msm/jars/paper/                <-- where msm-paper-update downloads to
  paper-1.21.11-<build>.jar
  paper-current.jar                 <-- symlink to newest jar
```

---

## Script Details

### deploy-plugins.sh

Uses a constrained rsync to copy only `.jar` files:

```
rsync -rv --delete \
  --no-owner --no-group --no-perms \
  --include='*.jar' \
  --exclude='*' \
  "$SRC/" "$DST/"
```

- `--include='*.jar'` + `--exclude='*'` means only jar files are considered
- Plugin folders and non-jar files are ignored (not deleted, not overwritten)
- `--delete` applies only to the included set — if you remove a jar from `shared/plugin-jars/`, it gets removed from each server's `plugins/`

**Translation:** manage jars centrally; plugin data stays put.

### msm-paper-update

1. Queries the PaperMC Fill v3 API for the latest build
2. Updates the MSM jargroup URL via `msm jargroup changeurl`
3. Downloads the jar via `msm jargroup getlatest`
4. Repoints `paper-current.jar` symlink to the newest downloaded jar

---

## Troubleshooting

**"shared/plugin-jars does not exist"** — Create it and add jars:
```
mkdir -p shared/plugin-jars
```

**"MSM servers dir not found: /opt/msm/servers"** — Confirm MSM is installed:
```
ls -la /opt/msm
```

**Permission denied writing to server plugins folders** — Run as a user with access to `/opt/msm/servers` (or use sudo):
```
sudo ./scripts/deploy-plugins.sh
```
