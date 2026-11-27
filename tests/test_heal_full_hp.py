import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "pokemon_encounter")

from app import db, healing


def test_full_hp_blocks_heal():
    db.connect(Path(tempfile.mkdtemp()) / "test.db")
    db.init_db()
    db.upsert_user("u1", "u1")
    db.execute("INSERT INTO species (id, name, name_en, type1) VALUES (1, 'bulbasaur', 'Bulbasaur', 'grass')")
    ivs = json.dumps({key: 0 for key in ("hp", "atk", "def", "spa", "spd", "spe")})
    now = datetime.now(timezone.utc).isoformat()
    db.execute("INSERT INTO owned_pokemon (user_id, species_id, level, ivs, caught_at, current_hp) "
               "VALUES (?,?,?,?,?,?)", ("u1", 1, 10, ivs, now, None))

    assert healing.heal_status("u1")["needs_heal"] is False
    try:
        healing.heal_team("u1")
    except ValueError:
        pass
    else:
        raise AssertionError("heal_team must refuse when every Pokemon has full HP")
    assert (db.get_user("u1") or {}).get("last_team_heal_at") is None, "the cooldown must not start"

    db.execute("UPDATE owned_pokemon SET current_hp = 1 WHERE user_id = 'u1'")
    assert healing.heal_status("u1")["needs_heal"] is True
    assert healing.heal_team("u1")["healed"] == 1
    assert healing.heal_status("u1")["needs_heal"] is False


if __name__ == "__main__":
    test_full_hp_blocks_heal()
    print("ok")
