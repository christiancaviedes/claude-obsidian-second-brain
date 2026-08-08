# Reproducible Benchmarks

The benchmark deliberately measures the deterministic offline validation path. It
does not claim model-output quality, end-to-end latency, or API cost for a live run.

```bash
python benchmarks/benchmark_validate.py --runs 100 --output benchmarks/results/latest.json
```

| Measure | Meaning |
|---|---|
| median / p95 latency | Local validation time for the bundled synthetic export |
| API calls | Always zero for this benchmark |
| estimated API cost | Always $0 for this benchmark |

Machine, Python version, model latency, export size, and enabled stages must be
recorded before comparing end-to-end runs. See the architecture decision record for
why model quality is not represented by an invented score.
