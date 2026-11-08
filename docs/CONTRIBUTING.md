# Contributing

Set up the checkout and run the suite with the locked development dependencies:

```sh
uv sync --locked --extra dev
uv run --no-sync python -m pytest --no-cov
```

## Testing

Use temporary directories for key material and fixtures for time, blockchain, and calendar responses. Tests should run without public network access. Add regressions at the affected boundary: serialized payload, verification policy, route, CLI output, or worker lifecycle. Include the command and result when proposing a change.

For packaging changes, build a wheel and test its CLI and web template routes from outside the checkout. For browser changes, check the same-origin event stream and the page's fallback when it cannot connect.

## Code style

The package targets Python 3.11 and newer. Preserve the established Python imports, CLI entry points, and wire format unless a compatibility change is explicit. Route cryptographic serialization through the shared serializer. Describe the limits of measurements and verification results where users encounter them.
