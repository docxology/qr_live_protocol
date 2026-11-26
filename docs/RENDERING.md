# Render the technical note

Run the [offline walkthrough](OFFLINE.md) first. It generates the figure
from a local signed-payload example. The [canonical manuscript](manuscript/README.md)
uses the external [docxology/template](https://github.com/docxology/template)
engine. Install uv, Python 3.14, Pandoc with a matching `pandoc-crossref`,
and XeLaTeX with its packages.

From a committed checkout named `qr_live_protocol`, choose an unused
location for the engine checkout:

```sh
QRLP_ROOT="$(pwd -P)"
TEMPLATE_ROOT="$QRLP_ROOT/../qrlp-render-template"
git clone https://github.com/docxology/template.git "$TEMPLATE_ROOT"
git -C "$TEMPLATE_ROOT" switch --detach 87704feae0a4490ef7dad9c931d268e8c30273c2
cp docs/manuscript/figure_registry.json output/figures/figure_registry.json

cd "$TEMPLATE_ROOT"
uv sync --locked --no-dev --python 3.14
mkdir -p projects/working
ln -s "$QRLP_ROOT" projects/working/qr_live_protocol
uv run --no-sync python scripts/pipeline/stage_03_render.py --project working/qr_live_protocol --skip-manuscript-hydration
uv run --no-sync python scripts/pipeline/stage_04_validate.py --project working/qr_live_protocol
```

Read the combined PDF at `output/pdf/qr_live_protocol_combined.pdf` and the
combined HTML at `output/web/index.html` in the QRLP checkout. Validation
and provenance receipts are in `output/reports/`.
