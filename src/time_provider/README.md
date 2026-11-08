# Time provider

`TimeProvider` queries only the configured NTP hostnames and explicit HTTP(S)
JSON clock endpoints. Successful observations contribute offsets; the producer
uses their median to adjust local UTC. A failed refresh clears old offsets.
When no source is available, the provider uses the local clock only if
`local_fallback` is enabled.

The defaults are NIST and Cloudflare with a 60-second refresh. Queries to
the same NIST hostname wait at least four seconds after the previous request.
A reused sample retains its original observation time.

`get_time_server_verification()` returns observations by source, with
`timestamp`, `offset`, and `last_sync`. The values are producer observations,
not signed replies from the clock services. Replay policy lives in
`QRLiveProtocol` and is independent of the time provider.

```python
from src.config import TimeSettings
from src.time_provider import TimeProvider

provider = TimeProvider(TimeSettings(time_servers=[], local_fallback=True))
print(provider.get_current_time())
assert provider.get_time_server_verification() == {}
```
