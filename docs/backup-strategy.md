# Backup Strategy

How the game server (`ssh minecraft`, hostname `game-server`) protects the Minecraft
worlds, what runs when, and how to check on it or restore from it.

Set up 2026-10-17 to 2026-10-19. All scripts live on the server in `/usr/local/sbin/`
and run as root from systemd timers.

## The Layers

| Layer | Where | What | Kept | Protects against |
|---|---|---|---|---|
| 1. Live | NVMe, `/opt/msm/servers` | The running servers | n/a | n/a |
| 2. Hourly snapshots | RAID1 mirror, `/srv/mc-backup/restic` | restic snapshots of all servers and config | 24 hourly, 14 daily, 8 weekly, 12 monthly | Griefing, bad plugin updates, deleted worlds, NVMe failure |
| 3. Nightly zips | NVMe, `/opt/msm/archives/worlds` | MSM's plain zip of every world | Last 2 nights | Quick access to last night's world without restic |
| 4. Nightly NAS copy | Slartibartfast (QNAP, 10.0.24.3), share `minecraft`, folder `restic` | A separate restic repository copied from layer 2 | 30 daily, 12 weekly, 24 monthly | Losing the whole server, a failed mirror, mistakes made on the server |
| 5. NAS snapshots | Slartibartfast | QNAP snapshots of the `minecraft` share | QNAP schedule | Damage that reaches the NAS copy |

Everything is in the same building, so this is not offsite storage. For a family
server that is a deliberate tradeoff.

### Why it is built this way

- **restic stores only what changed.** Each hourly snapshot looks like a full copy but
  adds only changed chunks, usually a few megabytes. 98 GB of servers took 50 GB on the
  mirror after deduplication and compression.
- **The NAS copy is its own repository, made with `restic copy`.** A file sync would copy
  corruption from the mirror faithfully; `restic copy` reads and verifies each snapshot
  as it copies.
- **The NAS share is mounted only while the nightly copy runs.** A mistake or anything
  malicious on the server cannot reach the NAS copy the rest of the day.
- **The mirror is two 1 TB Hitachi drives in mdadm RAID1**, chosen by SMART long test
  and taken from different production batches. It is mounted with `nofail`, so a dead
  drive cannot stop the server from booting.

## The Password

Both restic repositories (mirror and NAS) use one password, stored on the server at
`/root/.config/restic/mc-backup.pass` and in Charlie's password manager.

**Without this password neither repository can be read.** If the server is lost, the
NAS copy is only usable with the copy in the password manager.

To view it, run this in your own terminal:

```
ssh -t minecraft sudo cat /root/.config/restic/mc-backup.pass
```

## Schedule

| Time | Job | Unit |
|---|---|---|
| Every hour at :35 | Snapshot to the mirror | `mc-backup.timer` |
| 03:35 nightly | Also prunes old mirror snapshots; Sundays also checks 5% of the data | part of `mc-backup` |
| 04:15 nightly | Copy new snapshots to the NAS and apply NAS retention; Sundays also prunes and checks 5% of the NAS data | `mc-backup-nas.timer` |
| 05:02 nightly | MSM zips every world | `/etc/cron.d/msm` |
| 06:15 nightly | Delete all but the newest 2 zips per world | `mc-zip-prune.timer` |

The hourly snapshot keeps worlds consistent: for each running server it sends
`save-off`, then `save-all`, waits for "Saved the game" in the server log, takes the
snapshot, and sends `save-on`. Saving is re-enabled even if the snapshot fails. A
typical hourly run takes about 30 seconds. If MSM's nightly zip is still running, the
snapshot waits for it.

### What is in each snapshot

- `/opt/msm/servers` (all nine servers: worlds, configs, plugins)
- `/opt/msm/jars`
- `/opt/velocity`
- `/etc/msm.conf`, `/etc/cron.d/msm`, and charlie's crontab
- `/usr/local/sbin` (these backup scripts and the fan curve script)
- `/etc/systemd/system/mc-*` units and their `.service.d` drop-ins, `velocity.service`,
  and `case-fan-curve.service`
- `/etc/sensomatic/checks.conf` (the Sens-o-Matic check IDs, not the tokens)

## Checking On It

All commands run on the server.

**One-page summary.** This runs without a password and changes nothing:

```
sudo mc-backup-status
```

It reports the timers, the result of the last run of each job, the hourly snapshot
count for the last 24 hours, the mirror and SMART health, free space, the newest
snapshots, the zip counts, and which servers are running. Look for `Failed`,
`WARNING`, `refusing`, or a `[U_]` mirror line. The commands below are for digging into
a specific problem.

**Did the last backups succeed?**

```
systemctl list-timers 'mc-*'
systemctl status mc-backup mc-backup-nas mc-zip-prune
journalctl -u mc-backup -u mc-backup-nas --since yesterday
```

A healthy hourly run logs `mc-backup: done`. A healthy NAS run logs
`mc-backup-nas: done; NAS repository has N snapshots`.

**Is the mirror healthy?**

```
cat /proc/mdstat
```

Healthy looks like `md127 : active raid1 sdb[1] sda[0]` followed by `[2/2] [UU]`.
`[U_]` or `[_U]` means a drive has dropped out; see "When a mirror drive fails" below.

**List snapshots on the mirror:**

```
sudo restic -r /srv/mc-backup/restic --password-file /root/.config/restic/mc-backup.pass snapshots
```

## Restoring

The examples use the mirror repository. To restore from the NAS instead, see
"Restoring from the NAS" below.

For brevity, set these once in your shell first:

```
sudo -i
export RESTIC_REPOSITORY=/srv/mc-backup/restic
export RESTIC_PASSWORD_FILE=/root/.config/restic/mc-backup.pass
```

### Put a world back the way it was

1. Pick a snapshot by time:

   ```
   restic snapshots
   ```

2. Restore that server's world into a scratch folder on the mirror. Replace `ID` with
   the snapshot ID and `Whimbleton` with the server name:

   ```
   restic restore ID --target /srv/mc-backup/restore \
     --include /opt/msm/servers/Whimbleton/worldstorage
   ```

3. Stop the server, as charlie:

   ```
   sudo -u charlie msm Whimbleton stop now
   ```

4. Move the live world aside and copy the restored one in:

   ```
   cd /opt/msm/servers/Whimbleton
   mv worldstorage worldstorage.before-restore
   cp -a /srv/mc-backup/restore/opt/msm/servers/Whimbleton/worldstorage .
   ```

5. Start the server, as charlie. Starting by name also turns its auto-start flag back on:

   ```
   sudo -u charlie msm Whimbleton start
   ```

6. Once the restored world looks right in game, delete
   `worldstorage.before-restore` and `/srv/mc-backup/restore`.

The `world` entry in each server folder is a symlink into `worldstorage/world`; the
nether and end folders sit beside it. To restore those too, add
`--include /opt/msm/servers/Whimbleton/world_nether` (and `world_the_end`) to step 2,
then move and copy them the same way in step 4.

### Get back a single file

```
restic restore latest --target /srv/mc-backup/restore \
  --include /opt/msm/servers/Lobby/server.properties
```

### Browse a snapshot like a folder

```
mkdir -p /mnt/restic && restic mount /mnt/restic
```

Snapshots appear under `/mnt/restic/snapshots/`. Press Ctrl-C to unmount.

### Restoring from the NAS

Mount the share, point restic at it, and use the same commands as above:

```
mount -t cifs //10.0.24.3/minecraft /mnt/qnap-minecraft \
  -o credentials=/root/.smb-qnap-minecraft,vers=3.0
export RESTIC_REPOSITORY=/mnt/qnap-minecraft/restic
restic snapshots
```

Unmount it when done: `umount /mnt/qnap-minecraft`.

On a replacement machine, install restic, mount the share with charlie's QNAP
credentials, and use the password from the password manager.

### From a nightly zip

MSM's zips are in `/opt/msm/archives/worlds/<server>/<world>/`, named by date. They
need no password; unzip one into the server's `worldstorage` with the server stopped.

## Alerts

Sens-o-Matic watches the server through four heartbeat checks on the host **Game
Server** (Infra, then Health Checks). The server pings a check only when things are
good, so an alert means the pings stopped: a job failed, hung, or never ran, or the
server or its network is down. The alert says only "No heartbeat within N seconds";
the reason is on the server.

| Check | Pinged by | Alerts after about |
|---|---|---|
| Minecraft hourly backup | each successful hourly snapshot | 3 to 4 hours |
| Minecraft NAS copy | each successful nightly NAS copy | 28 to 42 hours |
| Minecraft zip cleanup | each successful nightly zip cleanup | 28 to 42 hours |
| Minecraft server health | `mc-health-check`, every 15 minutes, when everything below passes | 45 to 60 minutes |

The health check passes only when the mirror shows `[UU]`, both mirror drives pass
SMART, `/` and the mirror each have at least 15% free, Velocity is active, Lobby and
Whimbleton are running, and no systemd unit has failed.

**When an alert arrives**, start with `sudo mc-backup-status`. For the health check,
`journalctl -u mc-health -n 20` lists each failing item as a `PROBLEM:` line. The check
recovers by itself on the next good run.

How it is wired:

- `/usr/local/sbin/som-ping <name>` sends the ping. It never fails the job it reports
  on; a ping that cannot be delivered is logged as `som-ping: ping for ... failed`.
- The backup jobs call it from `/etc/systemd/system/<job>.service.d/sensomatic.conf`,
  which runs only after the job succeeds.
- `/etc/sensomatic/` (root only) holds `checks.conf` (check IDs) and one `<name>.token`
  per check. To replace a token, issue a new one from the check's heartbeat setup in
  Sens-o-Matic and write it to that file; the old one stops working immediately.
- Planned maintenance (a reboot, taking Lobby down) will trip the health check if it
  lasts more than about 30 to 45 minutes. Disable the check in Sens-o-Matic first.

## When Things Go Wrong

**A backup job failed.** Read the reason with `journalctl -u mc-backup -n 30` (or
`mc-backup-nas`). Every failure message names what is wrong. The scripts refuse to run
if the mirror or the NAS share is not mounted where expected, rather than writing
backups onto the NVMe.

**A server is stuck with saving off.** Hourly backups re-enable saving even when they
fail. If a server ever reports saving is off, run `sudo -u charlie msm <server> save on`.

**When a mirror drive fails.** The mirror keeps working on one drive. Identify the
failed drive by serial number, not `sdX` name:

```
mdadm --detail /dev/md127
ls -l /dev/disk/by-id/ | grep -v part
```

The two drives are Hitachi serials `GTF002PBHGM8PF` and `GTE002PBHEW15E`. Replace the
failed one with any drive of 1 TB or more, then add it with
`mdadm --manage /dev/md127 --add /dev/disk/by-id/<new drive>`. The resync takes about
4.5 hours.

## Who Can Do What

The game servers and Velocity run as `charlie` and accept connections from the
internet, so a bad plugin could run commands as `charlie`. To keep that from reaching
root, and with it the backups, `charlie` has no passwordless root access except for
these commands (`/etc/sudoers.d/50-minecraft`):

- `sudo mc-backup-status` (no arguments)
- `sudo systemctl start|stop|restart velocity.service`
- `sudo systemctl start mc-backup.service` (take a snapshot now)

Everything else that needs root asks for `charlie`'s password. Root's own password is
locked, so **`charlie`'s password is the only way to get root**; keep it in the
password manager. `charlie` is also not in the `lxd` group, which would otherwise be a
second route to root.

Day-to-day server work (`msm`, plugins, configs, worlds) runs as `charlie` and needs
no root at all. The backup jobs run as root from systemd and are unaffected.

## Things To Know

- `msm <server> stop` clears that server's auto-start flag; `msm <server> start` sets
  it again. Before a reboot, use `msm stop now` (all servers), which leaves the flags
  alone.
- The Velocity plugin `mc-autostart` starts servers on demand and stops them after 30
  idle minutes. Backups handle this; they snapshot whatever is running.
- The mirror drives are about 108,000 hours old (12+ years). They passed SMART long
  tests in September 2026, but plan for one to fail eventually. The NAS copy is there
  for exactly that.
