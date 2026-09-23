from src.instance import ALBInstance


def test_roundtrip(tmp_path):
    inst = ALBInstance("t", (5, 3, 7), ((0, 1), (1, 2)), m_stations=2)
    inst.save(tmp_path / "t.alb")
    assert ALBInstance.load(tmp_path / "t.alb") == inst