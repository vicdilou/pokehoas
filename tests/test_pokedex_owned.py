"""Tests fuer das owned_now-Flag im Pokedex (/api/pokedex): markiert Arten,
von denen der Spieler aktuell mindestens ein Exemplar im Team oder in der Box
hat - Grundlage fuer das kleine Pokeball-Icon im Dex-Grid sowie die
"not in box"-Option im Status-Dropdown der Dex-Sortierung (beide
www/index.html).

Aufruf:  python3 tests/test_pokedex_owned.py
"""

from __future__ import annotations

import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "pokemon_encounter"))

TMP = tempfile.mkdtemp(prefix="pokemon-dex-owned-test-")
os.environ["POKEMON_DATA_DIR"] = TMP
os.environ["SUPERVISOR_TOKEN"] = "dummy"

from app import db, seed  # noqa: E402
from app.api import team as team_api  # noqa: E402

failures: list[str] = []


def check(label: str, condition: bool, detail: object = "") -> None:
    status = "ok  " if condition else "FAIL"
    print(f"[{status}] {label}{(' - ' + str(detail)) if detail != '' else ''}")
    if not condition:
        failures.append(label)


NOW = datetime.now(timezone.utc).isoformat()
IVS = {k: 10 for k in ("hp", "atk", "def", "spa", "spd", "spe")}

db.init_db()
seed.seed_from_fallback()
alice = db.upsert_user("alice", "Alice")
species_ids = [r["id"] for r in db.query("SELECT id FROM species ORDER BY id")]
owned_species = species_ids[0]
unowned_species = species_ids[1]

owned_id = db.execute(
    "INSERT INTO owned_pokemon (user_id, species_id, level, exp, shiny, ivs, nature, gender, "
    "current_hp, caught_at, hp_updated_at) VALUES (?,?,5,0,0,'{}','hardy','male',10,?,?)",
    (alice["id"], owned_species, NOW, NOW),
)

dex = team_api.get_pokedex(current_user=alice)
by_id = {row["id"]: row for row in dex["entries"]}

check("owned species flagged owned_now", by_id[owned_species]["owned_now"] is True)
check("unowned species not flagged", by_id[unowned_species]["owned_now"] is False)

# "stage" and "max_level" feed the box-style filter bar reused by the
# Pokédex (www/index.html boxFilterControlsHtml/boxFilterMatches).
check("owned species reports its highest owned level", by_id[owned_species]["max_level"] == 5)
check("unowned species has no max_level", by_id[unowned_species]["max_level"] is None)
check("dex entry carries an evolution stage", isinstance(by_id[owned_species]["stage"], int))

# Releasing the only copy clears the flag again.
db.execute("DELETE FROM owned_pokemon WHERE id = ?", (owned_id,))
dex_after = team_api.get_pokedex(current_user=alice)
by_id_after = {row["id"]: row for row in dex_after["entries"]}
check("released species no longer owned_now", by_id_after[owned_species]["owned_now"] is False)

# The Pokédex filter bar's status dropdown (boxFilterControlsHtml /
# boxFilterMatches / wireBoxFilters, www/index.html) has a "not in box"
# option next to caught/seen/undiscovered that reads this same owned_now
# flag - a structural check that the wiring is actually in place, since the
# frontend has no test runner of its own.
html = (ROOT / "pokemon_encounter" / "www" / "index.html").read_text(encoding="utf-8")
check("status select offers a not_owned option", 'value="not_owned"' in html and "pokedex.not_in_box_only" in html)
check("boxFilterMatches filters on owned_now for not_owned status", "view.status === 'not_owned' ? !p.owned_now" in html)

if failures:
    print(f"\n{len(failures)} FAIL(s): {failures}")
    sys.exit(1)
print("\nAll pokedex owned_now checks passed.")
