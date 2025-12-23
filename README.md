MinecraftFest Ops Scripts (notes as of 12/23/25)

This repo includes two “ops” helpers for MSM-managed Paper servers:
	•	deploy-plugins.sh — syncs shared plugin .jar files into every MSM server’s plugins/ folder (without touching plugin data folders).
	•	msm-paper-update — updates the MSM paper jargroup to the latest Paper build for a given Minecraft version, downloads it, and repoints paper-current.jar.

Both scripts do not restart servers — you choose when to restart.

⸻

Prerequisites

Common
	•	You’re running MSM with servers under:
	•	MSM_SERVERS_DIR=/opt/msm/servers
	•	You have shell access on the host and can run commands with permissions to read/write under /opt/msm.

deploy-plugins.sh
	•	rsync installed
	•	A shared plugin jar staging directory exists:
	•	shared/plugin-jars/ (relative to repo root)

msm-paper-update
	•	curl
	•	python3
	•	MSM installed and msm available in PATH
	•	Outbound HTTPS access allowed to:
	•	https://api.papermc.io

⸻

Directory Layout Expectations

Shared plugin jars (source of truth)

<repo-root>/
  shared/
	plugin-jars/
	  LuckPerms.jar
	  ...etc...
	  
MSM servers
/opt/msm/servers/<server-name>/plugins/
  <plugin>.jar
  <plugin-data-folders>/   # NOT modified by deploy script
 
MSM paper jargroup storage
/opt/msm/jars/paper/
  paper-1.21.10-<build>.jar
  paper-current.jar  -> symlink to newest jar
  

1) deploy-plugins.sh
  
  What it does
	  •	Finds all MSM server directories under /opt/msm/servers
	  •	For each server:
	  •	Ensures <server>/plugins/ exists
	  •	Uses rsync to copy only *.jar from shared/plugin-jars/ into <server>/plugins/
	  •	Uses --delete within the filtered jar set (see safety notes)
  
  ✅ Does not touch plugin config/data folders in plugins/ (because it only includes *.jar).
  
  Safety notes (read this once, save future-you)
  
  This rsync block is intentionally constrained:
  rsync -rv --delete \
	--no-owner --no-group --no-perms \
	--include='*.jar' \
	--exclude='*' \
	"$SRC/" "$DST/"
	
	•	--include='*.jar' and --exclude='*' means:
		•	Only jar files are considered.
		•	Plugin folders and non-jar files are ignored (not deleted, not overwritten).
		•	--delete applies to the included set:
		•	If you remove a jar from shared/plugin-jars/, it will be removed from each server’s plugins/.
	
	Translation: manage jars centrally; plugin data stays put.
	
How to run
	
From the repo root (or wherever your script lives), run:
./scripts/deploy-plugins.sh

If it’s not executable yet:
chmod +x scripts/deploy-plugins.sh
./scripts/deploy-plugins.sh

Expected output

You’ll see something like:
==> Syncing plugin jars from:
	<repo-root>/shared/plugin-jars
==> To MSM servers under:
	/opt/msm/servers

==> whimbleton
sending incremental file list
...

Done. Restart servers manually when you want changes to take effect.

After running: apply changes

Plugins generally load on server start (or on plugin reload, which is… spicy). Best practice:

msm <server> restart now

Restart all active servers if desired:

msm restart now

Troubleshooting

“shared/plugin-jars does not exist”

Create it and add jars:

mkdir -p shared/plugin-jars

“MSM servers dir not found: /opt/msm/servers”

Confirm MSM is installed where expected:

ls -la /opt/msm

Permission denied writing to server plugins folders

Run as a user with access to /opt/msm/servers (or use sudo):

sudo ./scripts/deploy-plugins.sh