# The registry

One JSON file per source that enters the training workflow, in the shape schwingnet.catalog.RegistryEntry: the identity level a split must not share, the person-key rule, the access statement, the modality and device class, the regions, the grid root and the shards ingested so far. The dataset inventory under data/sources/ says what a dataset is and how to get it; a registry entry says how it enters the catalog (docs/research/data-catalog.md). `pixi run --locked python tools/catalog.py check` validates every entry against the shape.
