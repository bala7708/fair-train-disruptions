# FAIRification of Dutch Railway Disruption Data (2024)

FAIR Data Engineering course project, University of Twente, 2026-1A – **Group 18** (Balachandar Gurumurthy).

This repository contains the 2024 train disruption data published by
[Rijden de Treinen](https://www.rijdendetreinen.nl/en/open-data/disruptions), before and after FAIRification.

## Persistent identifiers (W3ID)

| Artefact | Identifier | File |
|---|---|---|
| Mini-ontology | https://w3id.org/FAIR-course-UT/2026/group18/ont | [`ontology/disruptions-ontology.ttl`](ontology/disruptions-ontology.ttl) |
| FAIRified data (RDF) | https://w3id.org/FAIR-course-UT/2026/group18/data | [`data/fairified/disruptions-2024.ttl`](data/fairified/disruptions-2024.ttl) |
| Original data (CSV) | https://w3id.org/FAIR-course-UT/2026/group18/original | [`data/original/disruptions-2024.csv`](data/original/disruptions-2024.csv) |

Individual resources in the data have hash identifiers under the data base URI, e.g.
`https://w3id.org/FAIR-course-UT/2026/group18/data#disruption-51320` or `…/data#station-ES`.
The redirect rules (a copy is in [`w3id/`](w3id/)) are published through the course PID relay, folder `rules/FAIR-course-UT/2026/group18/`.

## Repository structure

| Folder | Content |
|---|---|
| `data/original/` | Unmodified CSV as downloaded from Rijden de Treinen (5,964 disruptions, 14 columns) |
| `data/prepared/` | Data after preparation in OpenRefine (exported as CSV, records layout) |
| `data/fairified/` | FAIRified data in RDF Turtle (81,756 triples) |
| `ontology/` | Mini-ontology created in Protégé |
| `openrefine/` | OpenRefine operation history incl. the RDF skeleton (re-applicable with *Undo/Redo → Apply*) and `line-names.csv` |

## How the data was produced

1. **Preparation (OpenRefine):** removed `ns_lines`; paired station codes with names and line IDs with
   names, then split them into one row per station/line; created identifiers for causes and cause groups;
   added the Dutch time zone offset to all timestamps.
2. **Triplification (OpenRefine RDF extension):** an RDF skeleton maps every column to the semantic
   data model (schema.org, SKOS and the mini-ontology); the result was exported as Turtle.

To reproduce the RDF: open the original CSV in OpenRefine (with the RDF extension), load
`openrefine/line-names.csv` as a second project named `line-names`, apply
`openrefine/openrefine-operations.json`, then *RDF → Export → Turtle*.

## Data model in short

- Each disruption is an `ont:TrainDisruption` (a `schema:Event`) with `schema:startDate`, `schema:endDate`
  (`xsd:dateTime` with time zone), `schema:duration` (ISO 8601, e.g. `PT181M`), its stations
  (`schema:location` → `schema:TrainStation`), its lines (`ont:affectsLine` → `ont:RailwayLine`) and its
  causes (`ont:hasCause`, `ont:hasStatisticalCause` → `ont:DisruptionCause`).
- Causes are SKOS concepts with Dutch and English labels; each statistical cause points to its cause group
  with `skos:broader`.

## Known limitations

- Only disruptions **announced by NS** are included (usually when several trains are delayed or cancelled).
- The source gives no time zone; timestamps were interpreted as Dutch local time (CET/CEST).
- In the source, line IDs and line names are listed in different orders. The correct name of each ID was
  recovered by elimination for 99 of 111 lines; 12 international lines always appear together and have no name.
- 11 disruptions have no end time or duration, and 2 have no cause group; these values are left out rather than guessed.

## Licence

The data is © Rijden de Treinen and released under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/); the FAIRified version is shared under the same
licence. Please credit **Rijden de Treinen** as the source.



An AI assistant was used for guidance and explanations of this readme file.
