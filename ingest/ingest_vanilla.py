import os, json, hashlib
from datetime import datetime, timezone
from pathlib import Path

import psycopg
from dotenv import load_dotenv

def sha256_json(obj) -> str:
	# canonical-ish hash: stable key order + compact separators
	s = json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")
	return hashlib.sha256(s).hexdigest()

def parse_uuid_from_filename(p: Path):
	# vanilla stats filename is <uuid>.json
	return p.stem

def now_utc():
	return datetime.now(timezone.utc)

def upsert_player(cur, uuid_str: str) -> int:
	cur.execute(
		"INSERT INTO players (uuid) VALUES (%s) ON CONFLICT (uuid) DO UPDATE SET uuid = EXCLUDED.uuid RETURNING id",
		(uuid_str,)
	)
	return cur.fetchone()[0]

def get_server_id(cur, code: str) -> int:
	cur.execute("SELECT id FROM servers WHERE code=%s", (code,))
	row = cur.fetchone()
	if not row:
		raise RuntimeError(f"Server code not found in DB: {code}")
	return row[0]

def create_ingest(cur, server_id: int, source: str, notes: str | None) -> int:
	cur.execute(
		"INSERT INTO ingests (server_id, source, notes) VALUES (%s,%s,%s) RETURNING id",
		(server_id, source, notes)
	)
	return cur.fetchone()[0]

def finish_ingest(cur, ingest_id: int):
	cur.execute("UPDATE ingests SET finished_at=now() WHERE id=%s", (ingest_id,))

def insert_snapshot(cur, ingest_id: int, server_id: int, player_id: int,
					observed_at: datetime, stats_json: dict, adv_json: dict | None):
	stats_hash = sha256_json(stats_json)
	adv_hash = sha256_json(adv_json) if adv_json else None

	cur.execute(
		"""
		INSERT INTO player_server_snapshots
		  (ingest_id, server_id, player_id, observed_at, stats_json, advancements_json, stats_hash, adv_hash)
		VALUES
		  (%s,%s,%s,%s,%s,%s,%s,%s)
		ON CONFLICT (server_id, player_id, stats_hash) DO NOTHING
		RETURNING id
		""",
		(ingest_id, server_id, player_id, observed_at, json.dumps(stats_json),
		 json.dumps(adv_json) if adv_json else None, stats_hash, adv_hash)
	)
	row = cur.fetchone()
	return row[0] if row else None  # None if deduped

def explode_stats(cur, snapshot_id: int, player_id: int, server_id: int, observed_at: datetime, stats_json: dict):
	stats = stats_json.get("stats", {})
	rows = []
	for category, kv in stats.items():
		if not isinstance(kv, dict):
			continue
		for stat_key, value in kv.items():
			try:
				v = int(value)
			except Exception:
				continue
			rows.append((snapshot_id, player_id, server_id, observed_at, category, stat_key, v))

	if not rows:
		return

	cur.executemany(
		"""
		INSERT INTO stat_facts
		  (snapshot_id, player_id, server_id, observed_at, category, stat_key, value)
		VALUES
		  (%s,%s,%s,%s,%s,%s,%s)
		ON CONFLICT (snapshot_id, category, stat_key) DO NOTHING
		""",
		rows
	)

def explode_advancements(cur, snapshot_id: int, player_id: int, server_id: int, observed_at: datetime, adv_json: dict | None):
	if not adv_json:
		return
	rows = []
	for adv_key, payload in adv_json.items():
		if not isinstance(payload, dict):
			continue
		done = bool(payload.get("done", False))
		done_at = None
		# criteria timestamps may exist; pick latest if present
		crit = payload.get("criteria")
		if isinstance(crit, dict) and crit:
			# best effort parse; values are usually ISO timestamps
			ts = []
			for v in crit.values():
				if isinstance(v, str):
					try:
						ts.append(datetime.fromisoformat(v.replace("Z","+00:00")))
					except Exception:
						pass
			if ts:
				done_at = max(ts)
		rows.append((snapshot_id, player_id, server_id, observed_at, adv_key, done, done_at))

	cur.executemany(
		"""
		INSERT INTO advancement_facts
		  (snapshot_id, player_id, server_id, observed_at, advancement_key, done, done_at)
		VALUES
		  (%s,%s,%s,%s,%s,%s,%s)
		ON CONFLICT (snapshot_id, advancement_key) DO NOTHING
		""",
		rows
	)

def main():
	load_dotenv()

	server_code = os.environ.get("MC_SERVER_CODE")
	stats_dir = os.environ.get("MC_STATS_DIR")
	adv_dir = os.environ.get("MC_ADV_DIR", "")

	if not server_code or not stats_dir:
		raise SystemExit("Set MC_SERVER_CODE and MC_STATS_DIR (and optionally MC_ADV_DIR)")

	stats_path = Path(stats_dir)
	adv_path = Path(adv_dir) if adv_dir else None

	conninfo = (
		f"host={os.environ['PGHOST']} port={os.environ.get('PGPORT','5432')} "
		f"dbname={os.environ['PGDATABASE']} user={os.environ['PGUSER']} password={os.environ['PGPASSWORD']}"
	)

	with psycopg.connect(conninfo) as conn:
		conn.execute("SET TIME ZONE 'UTC'")
		with conn.cursor() as cur:
			server_id = get_server_id(cur, server_code)
			ingest_id = create_ingest(cur, server_id, source="vanilla-json", notes=str(stats_path))
			conn.commit()

			for stats_file in sorted(stats_path.glob("*.json")):
				uuid_str = parse_uuid_from_filename(stats_file)
				try:
					stats_json = json.loads(stats_file.read_text(encoding="utf-8"))
				except Exception:
					continue

				adv_json = None
				if adv_path:
					af = adv_path / f"{uuid_str}.json"
					if af.exists():
						try:
							adv_json = json.loads(af.read_text(encoding="utf-8"))
						except Exception:
							adv_json = None

				observed_at = datetime.fromtimestamp(stats_file.stat().st_mtime, tz=timezone.utc)

				player_id = upsert_player(cur, uuid_str)
				snapshot_id = insert_snapshot(cur, ingest_id, server_id, player_id, observed_at, stats_json, adv_json)

				if snapshot_id:
					explode_stats(cur, snapshot_id, player_id, server_id, observed_at, stats_json)
					explode_advancements(cur, snapshot_id, player_id, server_id, observed_at, adv_json)

				conn.commit()

			with conn.cursor() as cur2:
				finish_ingest(cur2, ingest_id)
			conn.commit()

if __name__ == "__main__":
	main()