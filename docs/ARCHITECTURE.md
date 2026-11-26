# Package map

Generated on 2026-11-12 from the `import` statements under `src/`. An arrow from A to B means code in A imports B; arrows already implied by a longer path are left out, so the picture shows layering rather than every edge. It shows 14 of the package's 18 top-level parts: the largest ones that import or are imported by others.

```mermaid
flowchart LR
    accTitle: Internal dependency map of the src package in qr_live_protocol
    accDescr: Generated from import statements in src. Each box is a subpackage or module of the package; an arrow from A to B means code in A imports B; arrows already implied by a longer path are omitted. Most-imported: config, core, frame_recovery.
    n_crypto["crypto/"]
    n_web_server["web_server.py"]
    n_cli["cli.py"]
    n_core["core.py"]
    n_qr_generator["qr_generator.py"]
    n_async_core["async_core.py"]
    n_identity_manager["identity_manager.py"]
    n_blockchain_verifier["blockchain_verifier.py"]
    n_config["config.py"]
    n_time_stamper["time_stamper.py"]
    n_time_provider["time_provider.py"]
    n_optical_throughput["optical_throughput.py"]
    n_live_simulator["live_simulator.py"]
    n_frame_recovery["frame_recovery.py"]
    n_web_server --> n_core
    n_async_core --> n_core
    n_blockchain_verifier --> n_config
    n_cli --> n_live_simulator
    n_cli --> n_web_server
    n_core --> n_blockchain_verifier
    n_core --> n_crypto
    n_core --> n_identity_manager
    n_core --> n_qr_generator
    n_core --> n_time_provider
    n_core --> n_time_stamper
    n_identity_manager --> n_config
    n_live_simulator --> n_frame_recovery
    n_live_simulator --> n_optical_throughput
    n_qr_generator --> n_config
    n_time_provider --> n_config
```
