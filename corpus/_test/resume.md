# Wren Ashby — Experience

> **FIXTURE.** Fictional person. Times, employers and metrics are invented.

## Lantern Analytics — Staff Search Engineer (2022 to present)

Owns retrieval for a catalogue of roughly forty million product pages. Rebuilt
the ranking stack on a hybrid of BM25 and dense retrieval, which moved
click-through on the top ten results from 31% to 44% over two quarters.

Reduced p99 search latency from 840 ms to 190 ms by replacing a fan-out of
per-index service calls with a single batched fan-out to an ANN index.

Mentors two engineers and runs the on-call rotation for the search team.

## Cardinal Health Data — Senior Data Engineer (2019 to 2022)

Built the ingestion pipeline for clinical trial records, roughly 30,000 documents
a month arriving in mixed formats. Introduced schema validation at the boundary,
which dropped downstream data-quality incidents by about two thirds.

Owned the warehouse cost model and cut spend by 38% over three quarters, mostly
by partitioning tables that had never been partitioned.

## Tidewater Analytics — Data Engineer (2017 to 2019)

First engineering role. Wrote ETL jobs and the dashboards that consumed them.
Learned SQL the slow way.