from src.instance import ALBInstance
import pytest


def test_roundtrip(tmp_path):
    inst = ALBInstance("t", (5, 3, 7), ((0, 1), (1, 2)), m_stations=2)
    inst.save(tmp_path / "t.alb")
    assert ALBInstance.load(tmp_path / "t.alb") == inst


def test_load_formato_benchmark_virgola_decimale(tmp_path):
    p = tmp_path / "otto.alb"
    p.write_text(
        "<number of tasks>\n3\n\n"
        "<cycle time>\n10\n\n"
        "<order strength>\n0,268\n\n"
        "<task times>\n1 2\n2 3\n3 4\n\n"
        "<precedence relations>\n1,2\n2,3\n\n"
        "<end>\n",
        encoding="utf-8",
    )
    inst = ALBInstance.load(p, m_stations=2)
    assert inst.meta["order_strength"] == pytest.approx(0.268)
    assert inst.cycle_time == 10
    assert inst.precedences == ((0, 1), (1, 2))


def test_load_senza_stazioni_richiede_m(tmp_path):
    p = tmp_path / "no_m.alb"
    p.write_text(
        "<number of tasks>\n1\n<task times>\n1 5\n<end>\n", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="numero di stazioni"):
        ALBInstance.load(p)


@pytest.mark.parametrize(
    "times, prec, m",
    [
        ((), (), 1),              # nessuna operazione
        ((1, 0), (), 1),          # tempo nullo
        ((1, -2), (), 1),         # tempo negativo
        ((1, 1), ((0, 5),), 1),   # arco fuori range
        ((1, 1), ((1, 1),), 1),   # cappio
        ((1, 1), (), 0),          # zero stazioni
    ],
)
def test_dati_non_validi_rifiutati(times, prec, m):
    with pytest.raises(ValueError):
        ALBInstance("bad", times, prec, m_stations=m)


def test_archi_duplicati_rimossi():
    inst = ALBInstance("d", (1, 1), ((0, 1), (0, 1)), m_stations=1)
    assert inst.precedences == ((0, 1),)