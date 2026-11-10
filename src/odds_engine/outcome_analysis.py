"""Compare archived match outcomes with stored fair 1X2 probabilities."""
import json
import re
import pandas as pd

MATCH_PATTERN = re.compile(r"^\s*(.*?)\s+vs\.?\s+(.*?)\s*$", re.IGNORECASE)
SCORE_PATTERN = re.compile(r"^\s*(\d{1,2})\s*[-:–—]\s*(\d{1,2})\s*$")
RESULT_LABELS = {"1":"home","h":"home","home":"home","home win":"home","2":"away","a":"away","away":"away","away win":"away","x":"draw","d":"draw","draw":"draw","tie":"draw"}


def normalize_match_result(value):
    if value is None:
        return None
    text = str(value).strip()
    score = SCORE_PATTERN.fullmatch(text)
    if score:
        home, away = map(int, score.groups())
        return "home" if home > away else "away" if home < away else "draw"
    label = re.sub(r"\s+", " ", re.sub(r"[_-]+", " ", text.casefold())).strip()
    return RESULT_LABELS.get(label)


def _key_text(value):
    if value is None or pd.isna(value):
        return ""
    return re.sub(r"\s+", " ", str(value)).strip().casefold()


def _datetime(value):
    try:
        stamp = pd.Timestamp(value)
        return None if pd.isna(stamp) else stamp.strftime("%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError, OverflowError):
        return None


def _raw(payload, *names):
    fields = {re.sub(r"[^a-z0-9]", "", str(k).casefold()): v for k,v in payload.items()}
    for name in names:
        key = re.sub(r"[^a-z0-9]", "", name.casefold())
        if key in fields:
            return fields[key]
    return None


def analyze_outcomes(analysis_df, source_records):
    empty = {"matched":0,"unmatched":0,"ambiguous":0,"unrecognized":0,
             "outcome_counts":[],"probability_comparison":[],"brier_score":None,
             "top_probability_accuracy":None}
    required = {"date","home_team","away_team","home_fair_prob","draw_fair_prob","away_fair_prob"}
    if analysis_df.empty or not source_records or not required.issubset(analysis_df.columns):
        return empty
    indexed = {}
    for idx,row in analysis_df.iterrows():
        key = (_datetime(row["date"]),_key_text(row["home_team"]),_key_text(row["away_team"]))
        if all(key):
            indexed.setdefault(key,[]).append(idx)
    matched=[]; unmatched=ambiguous=unrecognized=0; seen=set()
    for source in source_records:
        payload=source.get("raw_payload",{})
        if isinstance(payload,str):
            try: payload=json.loads(payload)
            except (TypeError,json.JSONDecodeError):
                unmatched+=1; continue
        if not isinstance(payload,dict):
            unmatched+=1; continue
        match=MATCH_PATTERN.fullmatch(str(_raw(payload,"match") or ""))
        key=(_datetime(_raw(payload,"start_time","start time","date")),
             _key_text(match.group(1)) if match else "",
             _key_text(match.group(2)) if match else "")
        if not all(key):
            unmatched+=1; continue
        candidates=indexed.get(key,[])
        if len(candidates)!=1 or key in seen:
            if len(candidates)>1 or key in seen: ambiguous+=1
            else: unmatched+=1
            continue
        seen.add(key)
        outcome=normalize_match_result(_raw(payload,"result"))
        if outcome is None:
            unrecognized+=1; continue
        matched.append((candidates[0],outcome))
    if not matched:
        return {**empty,"unmatched":unmatched,"ambiguous":ambiguous,"unrecognized":unrecognized}
    cols=["home_fair_prob","draw_fair_prob","away_fair_prob"]
    rows=[]; counts={"home":0,"draw":0,"away":0}; briers=[]; correct=0
    for idx,outcome in matched:
        probs=pd.to_numeric(analysis_df.loc[idx,cols],errors="coerce").to_numpy(dtype=float)
        if not pd.Series(probs).notna().all(): continue
        actual=["home","draw","away"].index(outcome)
        target=[float(i==actual) for i in range(3)]
        briers.append(sum((probs[i]-target[i])**2 for i in range(3)))
        correct+=int(probs.argmax()==actual); counts[outcome]+=1
        rows.append((probs,actual))
    n=len(rows)
    if not n:
        return {**empty,"unmatched":unmatched,"ambiguous":ambiguous,"unrecognized":unrecognized}
    labels=["Home","Draw","Away"]
    comparison=[]
    for i,label in enumerate(labels):
        predicted=sum(r[0][i] for r in rows)/n*100
        observed=sum(r[1]==i for r in rows)/n*100
        comparison.append({"outcome":label,"average_fair_probability":predicted,
                           "observed_frequency":observed,"difference_pp":observed-predicted})
    return {"matched":n,"unmatched":unmatched,"ambiguous":ambiguous,"unrecognized":unrecognized,
            "outcome_counts":[{"outcome":k.title(),"count":counts[k],"share":counts[k]/n*100}
                              for k in ("home","draw","away")],
            "probability_comparison":comparison,"brier_score":sum(briers)/n,
            "top_probability_accuracy":correct/n*100}
