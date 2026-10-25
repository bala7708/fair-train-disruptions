#!/usr/bin/env python3
"""
Triplification of the Dutch train disruption data (Rijden de Treinen, 2024).

Input : data/prepared/disruptions-2024-prepared.csv
        = the OpenRefine project exported as CSV (records layout: a disruption's
          extra stations and lines are on the rows below it, with an empty rdt_id).
Output: data/fairified/disruptions-2024.ttl  (RDF Turtle)

The RDF follows the semantic data model in the report (section 3.3):

  data:disruption-{rdt_id}   a ont:TrainDisruption
      schema:identifier        "{rdt_id}"
      schema:startDate         xsd:dateTime (with time zone offset)
      schema:endDate           xsd:dateTime (with time zone offset)
      schema:duration          "PT{n}M"^^xsd:duration   (ISO 8601: unit is explicit)
      schema:location          data:station-{code}       (1..n)
      ont:affectsLine          data:line-{line_id}       (1..n; see match_line_names)
      ont:hasCause             data:cause-{cause_id}
      ont:hasStatisticalCause  data:cause-{statistical_cause_id}

  data:station-{code}  a schema:TrainStation ; schema:identifier ; schema:name
  data:line-{id}       a ont:RailwayLine     ; schema:identifier ; schema:name
  data:cause-{id}      a ont:DisruptionCause ; skos:prefLabel "..."@nl , "..."@en
                       skos:broader ont:{cause_group_id}   (stated on the statistical cause)

Classes and properties with the ont: prefix come from the mini-ontology made in Protégé
(ontology/disruptions-ontology.ttl). The script checks that every ont: term it uses
is defined there.

Usage:
    pip install rdflib
    python scripts/triplify.py
"""
import csv
import re
import sys
from pathlib import Path

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF, SKOS, XSD

# ---------------------------------------------------------------- settings
GROUP = 18
W3ID = f"https://w3id.org/FAIR-course-UT/2026/group{GROUP}"
DATA = Namespace(f"{W3ID}/data#")      # base URI of the data ("Base URI" in the course)
ONT = Namespace(f"{W3ID}/ont#")        # mini-ontology made in Protégé
SCHEMA = Namespace("https://schema.org/")

ROOT = Path(__file__).resolve().parent.parent
INPUT = ROOT / "data" / "prepared" / "disruptions-2024-prepared.csv"
ONTOLOGY = ROOT / "ontology" / "disruptions-ontology.ttl"
OUTPUT = ROOT / "data" / "fairified" / "disruptions-2024.ttl"

RECORD_COLUMNS = ["cause_nl", "cause_id", "cause_en", "statistical_cause_nl",
                  "statistical_cause_id", "statistical_cause_en", "cause_group_id",
                  "start_time", "end_time", "duration_minutes"]
DATETIME = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}$")


# ---------------------------------------------------------------- 1. read the records
def read_records(path: Path) -> list[dict]:
    """Group the OpenRefine export back into one record per disruption."""
    records, current = [], None
    with open(path, encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            row = {k: (v or "").strip() for k, v in row.items()}
            if row["rdt_id"]:                      # first row of a new disruption
                current = {"id": row["rdt_id"], "stations": [], "lines": []}
                current.update({c: row[c] for c in RECORD_COLUMNS})
                records.append(current)
            elif current is None:
                sys.exit("The file starts with a row that has no rdt_id.")
            if row["station_code"]:                # every row may hold one station ...
                current["stations"].append((row["station_code"], row["station_name"]))
            if row["line_id"]:                     # ... and/or one line
                current["lines"].append((row["line_id"], row["line_name"]))
    return records


# ---------------------------------------------------------------- 2. match line IDs to line names
def match_line_names(records: list[dict]) -> dict[str, str]:
    """
    In the source file the line IDs are listed in numeric order and the line names in
    alphabetical order, so the n-th ID does NOT always belong to the n-th name
    (e.g. disruption 51322: IDs "111,161" but names "Alkmaar - Amsterdam Centraal, Haarlem - Uitgeest",
    where 111 is Haarlem - Uitgeest). Only the SETS of IDs and names per disruption are reliable.

    The true name of each ID is found by elimination: an ID can only have a name that appears in
    every disruption that lists that ID; once an ID is resolved, its name is removed from the
    candidates of the other IDs in the same disruptions. IDs that always appear together
    (some international lines) cannot be told apart and get no name.
    """
    per_record = [({i for i, _ in r["lines"]}, {n for _, n in r["lines"]}) for r in records]
    candidates: dict[str, set[str]] = {}
    for ids, names in per_record:
        for i in ids:
            candidates[i] = candidates.get(i, set(names)) & names
    changed = True
    while changed:
        changed = False
        for ids, _ in per_record:
            fixed = {next(iter(candidates[i])) for i in ids if len(candidates[i]) == 1}
            for i in ids:
                if len(candidates[i]) > 1 and (candidates[i] - fixed) and (candidates[i] - fixed) != candidates[i]:
                    candidates[i] -= fixed
                    changed = True
    return {i: next(iter(c)) for i, c in candidates.items() if len(c) == 1}


# ---------------------------------------------------------------- 3. build the graph
def build_graph(records: list[dict], line_names: dict[str, str]) -> Graph:
    g = Graph()
    for prefix, ns in (("data", DATA), ("ont", ONT), ("schema", SCHEMA), ("skos", SKOS)):
        g.bind(prefix, ns)

    for r in records:
        d = DATA[f"disruption-{r['id']}"]
        g.add((d, RDF.type, ONT.TrainDisruption))
        g.add((d, SCHEMA.identifier, Literal(r["id"])))

        # times already carry their time zone offset (added in OpenRefine)
        g.add((d, SCHEMA.startDate, Literal(r["start_time"], datatype=XSD.dateTime)))
        if r["end_time"]:                          # 11 disruptions have no end time
            g.add((d, SCHEMA.endDate, Literal(r["end_time"], datatype=XSD.dateTime)))
        if r["duration_minutes"]:
            g.add((d, SCHEMA.duration, Literal(f"PT{int(r['duration_minutes'])}M", datatype=XSD.duration)))

        # stations: one IRI per station code, shared by all disruptions at that station
        for code, name in r["stations"]:
            s = DATA[f"station-{code}"]
            g.add((d, SCHEMA.location, s))
            g.add((s, RDF.type, SCHEMA.TrainStation))
            g.add((s, SCHEMA.identifier, Literal(code)))
            g.add((s, SCHEMA.name, Literal(name)))

        # railway lines
        for line_id, _ in r["lines"]:              # name is taken from the matched list, not the row
            ln = DATA[f"line-{line_id}"]
            g.add((d, ONT.affectsLine, ln))
            g.add((ln, RDF.type, ONT.RailwayLine))
            g.add((ln, SCHEMA.identifier, Literal(line_id)))
            if line_id in line_names:
                g.add((ln, SCHEMA.name, Literal(line_names[line_id])))

        # causes: one SKOS concept per Dutch cause value, labelled in Dutch and English
        for prop, cid, nl, en in ((ONT.hasCause, r["cause_id"], r["cause_nl"], r["cause_en"]),
                                  (ONT.hasStatisticalCause, r["statistical_cause_id"],
                                   r["statistical_cause_nl"], r["statistical_cause_en"])):
            c = DATA[f"cause-{cid}"]
            g.add((d, prop, c))
            g.add((c, RDF.type, ONT.DisruptionCause))
            g.add((c, SKOS.prefLabel, Literal(nl, lang="nl")))
            g.add((c, SKOS.prefLabel, Literal(en, lang="en")))

        # cause group: belongs to the statistical cause (one group per statistical cause);
        # the 2 disruptions without a group get no group rather than a guessed one
        if r["cause_group_id"]:
            g.add((DATA[f"cause-{r['statistical_cause_id']}"], SKOS.broader, ONT[r["cause_group_id"]]))
    return g


# ---------------------------------------------------------------- 4. check the result
def validate(g: Graph, records: list[dict], ontology: Graph) -> list[tuple[str, bool, str]]:
    checks = []
    n = len(set(g.subjects(RDF.type, ONT.TrainDisruption)))
    checks.append(("One resource per disruption", n == len(records), f"{n}/{len(records)}"))

    no_station = [r["id"] for r in records if not r["stations"]]
    checks.append(("Every disruption has at least one station", not no_station, str(len(no_station))))
    no_line = [r["id"] for r in records if not r["lines"]]
    checks.append(("Every disruption has at least one line", not no_line, str(len(no_line))))

    bad_dt = [str(o) for o in g.objects(None, SCHEMA.startDate)] + [str(o) for o in g.objects(None, SCHEMA.endDate)]
    bad_dt = [v for v in bad_dt if not DATETIME.match(v)]
    checks.append(("All times are xsd:dateTime with a time zone", not bad_dt, str(len(bad_dt))))

    causes = set(g.subjects(RDF.type, ONT.DisruptionCause))
    multi = [c for c in causes if len(set(g.objects(c, SKOS.broader))) > 1]
    checks.append(("Each cause belongs to at most one cause group", not multi, str(len(multi))))

    defined = {s for s in ontology.subjects() if str(s).startswith(str(ONT))}
    used = {p for p in g.predicates() if str(p).startswith(str(ONT))}
    used |= {o for o in g.objects() if isinstance(o, URIRef) and str(o).startswith(str(ONT))}
    missing = sorted(str(u).split("#")[-1] for u in used - defined)
    checks.append(("All ont: terms are defined in the Protégé ontology", not missing, ", ".join(missing) or "ok"))

    for kind in (SCHEMA.TrainStation, ONT.RailwayLine):
        multi = [x for x in g.subjects(RDF.type, kind) if len(set(g.objects(x, SCHEMA.name))) > 1]
        checks.append((f"Each {kind.split('/')[-1].split('#')[-1]} has at most one name", not multi, str(len(multi))))

    outside = {s for s in g.subjects() if not str(s).startswith(str(DATA))}
    checks.append(("All data subjects use the W3ID data base URI", not outside, str(len(outside))))
    return checks


def main():
    records = read_records(INPUT)
    line_names = match_line_names(records)
    g = build_graph(records, line_names)
    ontology = Graph().parse(ONTOLOGY)
    checks = validate(g, records, ontology)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    g.serialize(OUTPUT, format="turtle")

    stations = len(set(g.subjects(RDF.type, SCHEMA.TrainStation)))
    lines = len(set(g.subjects(RDF.type, ONT.RailwayLine)))
    causes = len(set(g.subjects(RDF.type, ONT.DisruptionCause)))
    print(f"Disruptions: {len(records)}  stations: {stations}  lines: {lines}  causes: {causes}")
    print(f"Line names matched to IDs: {len(line_names)}/{lines} (the rest always co-occur and cannot be told apart)")
    print(f"Triples: {len(g)}  ->  {OUTPUT.relative_to(ROOT)}")
    for name, ok, detail in checks:
        print(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}")
    if not all(ok for _, ok, _ in checks):
        sys.exit(1)


if __name__ == "__main__":
    main()
