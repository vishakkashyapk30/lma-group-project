"""Table rendering (Markdown, LaTeX, CSV), captions, pending columns, figures degrade gracefully (eval/scoring/render.py, cli.py)."""

from __future__ import annotations

import json
import sys

import pytest

from tests.unit.eval.scoring_fixtures import gold_row, record, write_run, write_t1
from vakeel_sahayak.eval.scoring import cli, render
from vakeel_sahayak.eval.scoring.pipeline import score_command

DEV = ["d1", "d2", "d3"]


@pytest.fixture()
def scored(tmp_path):
    root = tmp_path / "testsets"
    for src in ("agreed", "rule"):
        write_t1(root, src, [gold_row(c, ["custody_period"], g2=["D1"] if c == "d1" else None) for c in DEV], [gold_row("t1", ["custody_period"])], ["t1"], [])
    runs = tmp_path / "runs"
    write_run(runs, "full", 1, [record(c, ["custody_period"], tokens=900, retrieved=["D1#1"]) for c in DEV])
    write_run(runs, "b0", 1, [record(c, ["antecedents"], tokens=90, gates=False) for c in DEV])
    out = tmp_path / "out"
    score_command(str(runs), str(out), gold_source="both", testsets_dir=str(root))
    render.write_report(str(out))
    return out


def test_tex_escape_and_booktabs():
    t = render.Table("t", "T", "caption with 50% & x_y", ["System", "A_b"], [["full", "0.5 [0.1, 0.9] n=3"]], ["a note"])
    tex = render.to_latex(t)
    assert "\\toprule" in tex and "\\midrule" in tex and "\\bottomrule" in tex and "\\begin{tabular}{lr}" in tex
    assert "50\\% \\& x\\_y" in tex and "A\\_b & " not in tex.split("\\midrule")[1]
    md = render.to_markdown(t)
    assert md.startswith("### T") and "| System | A_b |" in md and "- a note" in md


def test_cell_formats():
    assert render.cell({"mean": 0.5, "lo": 0.25, "hi": 0.75, "n": 4}) == "0.500 [0.250, 0.750] n=4"
    assert render.cell({"mean": None, "n": 0}) == "n/a (n=0)"
    assert render.cell({"mean": 0.5, "lo": 0, "hi": 1, "n": 2}, pending=True) == "pending"


def test_report_writes_tables_for_every_format(scored):
    written = render.write_report(str(scored))
    names = {p.rsplit("/", 1)[1] for p in written["tables"]}
    for stem in ("table1_main", "table9_cost", "table_paired", "table_holm", "table_label_coverage", "table_sweep_metrics", "table_sweep_robustness"):
        assert {f"{stem}.md", f"{stem}.tex", f"{stem}.csv"} <= names
    assert (scored / "tables" / "rule" / "table1_main.tex").is_file()  # secondary gold in its own folder
    md = (scored / "tables" / "table1_main.md").read_text()
    assert "Preliminary dev result" in md and "gold source agreed" in md and "Offline stand-in models" in md
    assert "| full |" in md and "| b0 |" in md
    # full recalled custody_period on 3 cases: 1.000 [1.000, 1.000] n=3; b0 argued another factor: 0.000
    assert "1.000 [1.000, 1.000] n=3" in md and "0.000 [0.000, 0.000] n=3" in md
    assert "too few for a claim" in md  # 3 orders < 20
    tex = (scored / "tables" / "table1_main.tex").read_text()
    assert "\\caption{Preliminary dev result" in tex and "Recall@10 G2" in tex
    assert (scored / "figures" / "fig2_frontier.csv").is_file() and (scored / "figures" / "fig_per_factor.csv").is_file()


def test_recall_at_10_shows_n_and_coverage(scored):
    md = (scored / "tables" / "table1_main.md").read_text()
    assert "1.000 [1.000, 1.000] n=1 [1 of 3 orders with a resolved citation, 100% resolved]" in md


def test_pending_column_is_marked_not_faked(scored, monkeypatch, tmp_path):
    import vakeel_sahayak.eval.metrics.unsupported_fact as uf

    def stub(brief, text):
        raise NotImplementedError

    monkeypatch.setattr(uf, "unsupported_fact_rate", stub)
    root = tmp_path / "testsets"
    runs = tmp_path / "runs"
    for src in ("agreed", "rule"):
        write_t1(root, src, [gold_row("d1", ["custody_period"])], [gold_row("t1", ["custody_period"])], ["t1"], [])
    write_run(runs, "full", 1, [record("d1", ["custody_period"])])
    write_run(runs, "b0", 1, [record("d1", ["antecedents"])])
    out = tmp_path / "o2"
    score_command(str(runs), str(out), testsets_dir=str(root))
    render.write_report(str(out))
    md = (out / "tables" / "table1_main.md").read_text()
    assert "pending" in md and "unsupported_fact_rate waits for vakeel_sahayak.eval.metrics.unsupported_fact.unsupported_fact_rate" in md
    paired = (out / "tables" / "table_paired.md").read_text()
    assert "pending" in paired
    holm = (out / "tables" / "table_holm.md").read_text()
    assert "F-RQ1-halluc" in holm and "pending" in holm


def test_sweep_tables(scored):
    md = (scored / "tables" / "table_sweep_metrics.md").read_text()
    assert "Delta (agreed minus rule)" in md and "no model call" in md


def test_figures_skip_gracefully_without_matplotlib(scored, monkeypatch, tmp_path):
    monkeypatch.setitem(sys.modules, "matplotlib", None)  # makes `import matplotlib` raise ImportError
    res = json.loads((scored / "score_agreed.json").read_text())
    assert render.render_figures(res, tmp_path / "f") == []
    assert (tmp_path / "f" / "fig2_frontier.csv").is_file()


def test_figures_written_when_matplotlib_present(scored, tmp_path):
    pytest.importorskip("matplotlib")
    res = json.loads((scored / "score_agreed.json").read_text())
    paths = render.render_figures(res, tmp_path / "f")
    assert {p.suffix for p in paths} == {".pdf", ".png"}


def test_cli_score_and_report_and_blind_refusal(tmp_path, scored, capsys):
    root = tmp_path / "testsets"
    runs = tmp_path / "runs"
    write_run(runs, "full", 1, [record("d1", ["custody_period"])])
    assert cli.main(["score", "--runs", str(runs), "--out", str(tmp_path / "c"), "--testsets", str(root)]) == 0
    assert cli.main(["report", "--scores", str(tmp_path / "c")]) == 0
    assert (tmp_path / "c" / "tables" / "table1_main.md").is_file()
    assert cli.main(["score", "--runs", str(runs), "--out", str(tmp_path / "d"), "--testsets", str(root), "--slice", "blind"]) == 2
    assert "REFUSED" in capsys.readouterr().err
    assert not (tmp_path / "d").exists() or not list((tmp_path / "d").glob("score_*.json"))
    assert cli.main(["report", "--scores", str(tmp_path / "nothing")]) == 2


def test_figure_code_runs_against_a_stub_matplotlib(scored, monkeypatch, tmp_path):
    from unittest.mock import MagicMock

    mpl, plt = MagicMock(), MagicMock()
    plt.subplots.return_value = (MagicMock(), MagicMock())
    monkeypatch.setitem(sys.modules, "matplotlib", mpl)
    monkeypatch.setitem(sys.modules, "matplotlib.pyplot", plt)
    mpl.pyplot = plt
    res = json.loads((scored / "score_agreed.json").read_text())
    paths = render.render_figures(res, tmp_path / "f")
    assert [p.name for p in paths][:2] == ["fig2_frontier.pdf", "fig2_frontier.png"]
    assert plt.subplots.called
