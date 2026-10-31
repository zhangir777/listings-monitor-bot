from bot.storage import Storage


def test_searches_and_seen(tmp_path):
    db = Storage(tmp_path / "t.db")
    a = db.add_search(1, "https://krisha.kz/arenda/kvartiry/almaty/", 300000)
    b = db.add_search(2, "https://krisha.kz/prodazha/kvartiry/astana/", None)
    assert db.searches(1) == [(a, 1, "https://krisha.kz/arenda/kvartiry/almaty/", 300000)]
    assert len(db.searches()) == 2

    assert db.new_ids(a, ["1", "2"]) == ["1", "2"]
    assert db.new_ids(a, ["2", "3"]) == ["3"]
    assert db.new_ids(b, ["1"]) == ["1"]  # seen ids are per search

    assert not db.remove_search(1, b)  # not the owner
    assert db.new_ids(b, ["1"]) == []  # other user's seen ids untouched
    assert db.remove_search(1, a)
    assert db.searches(1) == []


def test_language_per_chat(tmp_path):
    db = Storage(tmp_path / "t.db")
    assert db.get_lang(1) == "en"  # English by default
    db.set_lang(1, "ru")
    db.set_lang(1, "kk")
    assert db.get_lang(1) == "kk"
    assert db.get_lang(2) == "en"
