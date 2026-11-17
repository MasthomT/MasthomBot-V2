from app.services.theme_auto_service import DEFAULT, clean, theme_for
from app.routes.label_style import PRESETS


def test_default_rules_point_to_existing_themes():
    assert all(r["theme"] in PRESETS for r in DEFAULT["rules"])


def test_matching_real_categories():
    cases = {
        "The Legend of Zelda: Ocarina of Time": "zelda", "Phasmophobia": "horror", "SILENT HILL 2": "fog",
        "R.E.P.O.": "repo", "ELDEN RING NIGHTREIGN": "darkfantasy", "Clair Obscur: Expedition 33": "clairobscur",
        "Dead by Daylight": "werewolf", "Sea of Thieves": "pirate", "Pokémon Legends: Z-A": "pokemon",
        "HELLDIVERS 2": "vault", "Grand Theft Auto V": "gta6", "Super Mario Odyssey": "arcade",
        "Just Chatting": "",
    }
    for cat, theme in cases.items():
        assert theme_for(cat, DEFAULT) == theme, cat


def test_fallback_and_validation():
    cfg = clean({"enabled": True, "fallback": "classique", "rules": [{"match": " Zelda ", "theme": "zelda"}, {"match": "", "theme": "x"}]}, PRESETS)
    assert cfg["rules"] == [{"match": "Zelda", "theme": "zelda"}]
    assert theme_for("Just Chatting", cfg) == "classique"
    try:
        clean({"rules": [{"match": "A", "theme": "nope"}]}, PRESETS)
        assert False
    except ValueError:
        pass
