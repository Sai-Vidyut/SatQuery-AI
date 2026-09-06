# Ground-truth readiness (Phase 10)

This document describes how public benchmarks could plug into the existing
`evaluation/metrics.py` harness without downloading large datasets in Phase 10.

## Highest-value public benchmarks

| Benchmark | Domain fit | Format | License / access |
|-----------|------------|--------|------------------|
| [EuroMineNet](https://doi.org/10.14278/rodare.4656) | Mining | Sentinel-2 footprints, expert polygons | Open (RODAre) |
| [INPE PRODES](http://terrabrasilis.dpi.inpe.br/) | Deforestation | Amazon biome vectors | Government open data |
| [Dynamic World](https://developers.google.com/earth-engine/datasets/catalog/GOOGLE_DYNAMICWORLD_V1) | Urban / water / vegetation | EE image collection | Google Terms of Use |
| [Zenodo Urban S2 monthly](https://doi.org/10.5281/zenodo.10846426) | Urban land-cover classes | Raster tiles | CC BY |

## Wiring into `metrics.py`

`compute_region_metrics(predicted_regions, ground_truth_geometry)` already accepts:

- `predicted_regions`: list of `EvidenceRegion` from a completed query
- `ground_truth_geometry`: single `GeoJSONGeometry` polygon

To run quantitative evaluation:

1. Add `ground_truth` to an `EvaluationCase` in `evaluation/cases/catalog_cases.json`
2. Set `evaluation_type` to `quantitative` and `ground_truth_available` to `true`
3. `EvaluationRunner.run_case()` will call `compute_region_metrics` automatically

## Fixture adapter example

See `evaluation/fixtures/ground_truth_example.json` — a minimal polygon reference
for the mining Saxony AOI. Load with:

```python
from pathlib import Path
import json
from evaluation.models import GroundTruthSpec

payload = json.loads(Path("evaluation/fixtures/ground_truth_example.json").read_text())
gt = GroundTruthSpec.model_validate(payload)
# Pass gt.geometry to compute_region_metrics(...)
```

## Limitations

- No automatic GT download or co-registration pipeline in Phase 10
- Single-polygon GT only (union of multiple features must be pre-merged)
- IoU uses planar degree approximation at centroid latitude
