import pandas as pd
import pytest
from src.odds_engine.outcome_analysis import analyze_outcomes, normalize_match_result

@pytest.mark.parametrize(("value","expected"),[
("2-1","home"),("0:3","away"),("1–1","draw"),("HOME","home"),
("X","draw"),("2","away"),("Home Win","home"),("Away_Win","away"),
("",None),("postponed",None),("1-0 aet",None)])
def test_normalize_match_result(value,expected):
    assert normalize_match_result(value)==expected

def _analysis():
    return pd.DataFrame([
      {"date":"2026-01-01T15:00:00","home_team":"Alpha","away_team":"Beta","home_fair_prob":.6,"draw_fair_prob":.25,"away_fair_prob":.15},
      {"date":"2026-01-02T15:00:00","home_team":"Gamma","away_team":"Delta","home_fair_prob":.2,"draw_fair_prob":.3,"away_fair_prob":.5}])

def _source(match,date,result):
    import json
    return {"raw_payload":json.dumps({"Match":match,"Start Time":date,"Result":result})}

def test_outcome_metrics():
    result=analyze_outcomes(_analysis(),[
      _source("Alpha vs Beta","2026-01-01 15:00:00","2-0"),
      _source("Gamma vs Delta","2026-01-02 15:00:00","0-1")])
    assert result["matched"]==2
    assert [x["count"] for x in result["outcome_counts"]]==[1,0,1]
    assert result["top_probability_accuracy"]==100
    assert result["brier_score"]==pytest.approx((.245+.38)/2)

def test_ambiguous_fixture_is_not_guessed():
    df=pd.concat([_analysis().iloc[[0]],_analysis().iloc[[0]]],ignore_index=True)
    result=analyze_outcomes(df,[_source("Alpha vs Beta","2026-01-01 15:00:00","1-0")])
    assert result["matched"]==0 and result["ambiguous"]==1

def test_unknown_result_is_reported():
    result=analyze_outcomes(_analysis(),[_source("Alpha vs Beta","2026-01-01 15:00:00","Postponed")])
    assert result["matched"]==0 and result["unrecognized"]==1
