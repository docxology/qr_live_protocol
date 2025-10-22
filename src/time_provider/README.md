# TimeProvider Module

## Overview

The TimeProvider module handles accurate time synchronization with multiple time servers and provides timestamp verification capabilities for QR code authenticity. This module ensures temporal integrity and prevents replay attacks.

## Architecture

```
TimeProvider
├── NTP Client (Network Time Protocol synchronization)
├── HTTP Time APIs (Fallback time sources)
├── Time Synchronization (Multiple server coordination)
├── Timestamp Validation (Drift detection and tolerance)
└── Statistics Tracking (Synchronization metrics)
```

## Key Features

### ⏰ Time Synchronization
- **Multi-server NTP synchronization** for accuracy and redundancy
- **HTTP time API fallbacks** when NTP is unavailable
- **Median offset calculation** for robust time accuracy
- **Configurable time drift tolerance** for verification
- **Automatic failover** between time sources

### 🔍 Time Verification
- **Timestamp validation** against current time
- **Drift detection** for replay attack prevention
- **Time server diversity** for reliability
- **Historical verification** for audit trails

### 📊 Monitoring & Statistics
- **Synchronization success rates** for each time server
- **Offset tracking** for accuracy monitoring
- **Failure analysis** for troubleshooting
- **Performance metrics** for optimization

## Usage Examples

### Basic Time Synchronization
```python
from src.time_provider import TimeProvider
from src.config import TimeSettings

# Configure time settings
time_settings = TimeSettings()
time_settings.time_servers = [
    "time.nist.gov",
    "pool.ntp.org",
    "time.google.com"
]
time_settings.update_interval = 60.0  # Update every minute

# Initialize time provider
time_provider = TimeProvider(time_settings)

# Get current synchronized time
current_time = time_provider.get_current_time()
print(f"Current time: {current_time}")

# Get time server verification data
verification = time_provider.get_time_server_verification()
print(f"Time servers verified: {len(verification)}")
```

### Time Verification
```python
from src.time_provider import TimeProvider

# Initialize time provider
time_provider = TimeProvider()

# Verify timestamp
timestamp_str = "2025-01-11T15:30:45.123Z"
result = time_provider.verify_timestamp(timestamp_str, tolerance=30.0)

print(f"Timestamp valid: {result['valid']}")
print(f"Time difference: {result['time_difference']:.3f} seconds")

if not result['valid']:
    print(f"Timestamp outside tolerance: {result['tolerance']} seconds")
```

### Custom Time Server Configuration
```python
from src.config import TimeSettings

# Configure multiple time servers for redundancy
time_settings = TimeSettings()
time_settings.time_servers = [
    "0.pool.ntp.org",      # Primary NTP pool
    "1.pool.ntp.org",      # Secondary NTP pool
    "time.nist.gov",       # NIST time server
    "time.google.com",     # Google time service
    "time.cloudflare.com"  # Cloudflare time service
]
time_settings.update_interval = 30.0  # Update every 30 seconds
time_settings.timeout = 5.0         # 5 second timeout per server

time_provider = TimeProvider(time_settings)
```

### Error Handling and Fallbacks
```python
from src.time_provider import TimeProvider

# Initialize with fallback configuration
time_settings = TimeSettings()
time_settings.time_servers = ["time.nist.gov"]  # Single server
time_settings.local_fallback = True             # Use local time if servers fail

time_provider = TimeProvider(time_settings)

try:
    # Get synchronized time
    current_time = time_provider.get_current_time()
    print(f"Synchronized time: {current_time}")
except Exception as e:
    print(f"Time synchronization failed: {e}")
    # Falls back to local time automatically
    local_time = time_provider.get_current_time()
    print(f"Using local time: {local_time}")
```

## API Reference

### TimeProvider Class

#### Initialization
```python
TimeProvider(settings: TimeSettings)
```
Initialize time provider with time synchronization settings.

#### Core Methods

**`get_current_time() -> datetime`**
Get current time with best available synchronization accuracy.

**`get_time_server_verification() -> Dict[str, str]`**
Get verification data from all configured time servers.

**`verify_timestamp(timestamp_str: str, tolerance: float = 30.0) -> Dict[str, bool]`**
Verify if timestamp is within acceptable range of current time.

**`get_statistics() -> Dict`**
Get time provider statistics and performance metrics.

#### Advanced Methods

**`get_ntp_time(server: str) -> Optional[TimeServerResponse]`**
Get time from specific NTP server with detailed response information.

**`get_http_time(url: str = "http://worldtimeapi.org/api/timezone/UTC") -> Optional[TimeServerResponse]`**
Get time from HTTP time API with fallback support.

**`sync_all_servers() -> List[TimeServerResponse]`**
Synchronize with all configured time servers and return responses.

**`force_sync() -> bool`**
Force immediate synchronization with all time servers.

## Configuration

### TimeSettings Configuration
```python
from src.config import TimeSettings

time_settings = TimeSettings()
time_settings.update_interval = 60.0        # Seconds between updates
time_settings.time_servers = [              # List of time servers
    "time.nist.gov",
    "pool.ntp.org",
    "time.google.com"
]
time_settings.timeout = 5.0                 # Timeout per server request
time_settings.local_fallback = True         # Use local time if servers fail
time_settings.timezone = "UTC"              # Target timezone
```

### Environment Variables
```bash
export QRLP_TIME_UPDATE_INTERVAL=30.0
export QRLP_TIME_TIMEOUT=3.0
export QRLP_TIME_SERVERS="time.nist.gov,pool.ntp.org,time.google.com"
```

## Performance Characteristics

### Synchronization Performance
- **NTP Query**: 50-200ms per server
- **HTTP API**: 100-500ms per request
- **Median Calculation**: < 1ms
- **Cache Hit**: < 1ms (cached responses)

### Memory Usage
- **Base memory**: ~2MB for time provider
- **Server cache**: ~1KB per cached server response
- **Statistics tracking**: ~500KB for metrics history

### Scalability
- **Concurrent requests**: Thread-safe with proper locking
- **Server diversity**: Multiple servers for redundancy
- **Cache efficiency**: Intelligent caching reduces API calls

## Error Handling

### Time Synchronization Errors
```python
from src.time_provider import TimeProvider

time_provider = TimeProvider()

try:
    current_time = time_provider.get_current_time()
    print(f"Time synchronized: {current_time}")
except Exception as e:
    print(f"Time sync failed: {e}")
    # Falls back to local time automatically
```

### Server Failure Handling
```python
# Configure multiple servers for redundancy
time_settings = TimeSettings()
time_settings.time_servers = [
    "time.nist.gov",       # Primary
    "pool.ntp.org",        # Secondary
    "time.google.com",     # Tertiary
    "time.cloudflare.com"  # Quaternary
]

time_provider = TimeProvider(time_settings)

# Will try servers in order, falling back gracefully
verification = time_provider.get_time_server_verification()
print(f"Successful servers: {len(verification)}")
```

## Integration Examples

### QRLiveProtocol Integration
```python
from src import QRLiveProtocol

# QRLiveProtocol automatically uses TimeProvider
qrlp = QRLiveProtocol()

# Time synchronization is handled automatically
qr_data, qr_image = qrlp.generate_single_qr()

# Verification includes time validation
verification = qrlp.verify_qr_data(qr_data.to_json())
print(f"Time verified: {verification['time_verified']}")
```

### Custom Application Integration
```python
from src.time_provider import TimeProvider

# Use in custom applications requiring time synchronization
time_provider = TimeProvider()

# Get synchronized time for transactions
transaction_time = time_provider.get_current_time()

# Verify timestamp for security
result = time_provider.verify_timestamp("2025-01-11T15:30:45Z", tolerance=60.0)
if result['valid']:
    print("Timestamp is within acceptable range")
else:
    print("Timestamp verification failed")
```

### Monitoring Integration
```python
from src.time_provider import TimeProvider

# Monitor time synchronization health
time_provider = TimeProvider()
stats = time_provider.get_statistics()

print(f"Sync attempts: {stats['total_syncs']}")
print(f"Success rate: {stats['success_rate']:.1%}")
print(f"Active servers: {stats['active_servers']}")

# Check individual server performance
for server, offset in stats['time_offsets'].items():
    print(f"{server}: offset {offset:.3f}s")
```

## Testing

### Time Provider Testing
```python
import pytest
from src.time_provider import TimeProvider
from src.config import TimeSettings

def test_time_provider_initialization():
    """Test time provider initializes correctly."""
    settings = TimeSettings()
    provider = TimeProvider(settings)

    assert provider.settings == settings
    assert provider.time_offsets == {}
    assert provider.last_sync_time == 0

def test_time_synchronization():
    """Test time synchronization functionality."""
    settings = TimeSettings()
    settings.time_servers = ["time.nist.gov"]  # Use reliable server
    settings.update_interval = 1.0  # Fast updates for testing

    provider = TimeProvider(settings)

    # Force synchronization
    provider.force_sync()

    # Should have synchronized with server
    assert len(provider.time_offsets) > 0

    # Get current time
    current_time = provider.get_current_time()
    assert current_time is not None

def test_timestamp_verification():
    """Test timestamp verification functionality."""
    provider = TimeProvider()

    # Test current timestamp (should be valid)
    current_time = provider.get_current_time()
    result = provider.verify_timestamp(current_time.isoformat(), tolerance=60.0)
    assert result['valid'] == True

    # Test old timestamp (should fail)
    old_time = "2020-01-01T00:00:00Z"
    result = provider.verify_timestamp(old_time, tolerance=60.0)
    assert result['valid'] == False
```

### Test Coverage Goals
- **Time synchronization**: 95%+ coverage
- **Server communication**: 95%+ coverage
- **Error handling**: 100% coverage
- **Performance monitoring**: 90%+ coverage

## Troubleshooting

### Common Issues

**Time Synchronization Fails**
```python
# Check time server connectivity
provider = TimeProvider()
provider.force_sync()

# Check which servers are working
verification = provider.get_time_server_verification()
print(f"Working servers: {len(verification)}")

# Check individual server status
stats = provider.get_statistics()
print(f"Success rate: {stats['success_rate']:.1%}")
```

**Large Time Drift Detected**
```python
# Check time server offsets
provider = TimeProvider()
offsets = provider.time_offsets

for server, offset in offsets.items():
    if abs(offset) > 1.0:  # More than 1 second drift
        print(f"Large drift detected for {server}: {offset:.3f}s")

# Verify system time is correct
import time
local_time = time.time()
sync_time = provider.get_current_time().timestamp()
drift = abs(local_time - sync_time)

if drift > 5.0:  # More than 5 seconds
    print("System clock may be incorrect")
```

**Performance Issues**
```python
# Monitor synchronization performance
provider = TimeProvider()
stats = provider.get_statistics()

print(f"Sync attempts: {stats['total_syncs']}")
print(f"Successful syncs: {stats['successful_syncs']}")
print(f"Failed syncs: {stats['failed_syncs']}")

# Optimize configuration
if stats['success_rate'] < 0.8:
    print("Consider adding more time servers or increasing timeout")
```

## Advanced Features

### Custom Time Sources
```python
# Add custom time servers
settings = TimeSettings()
settings.time_servers = [
    "ntp.yourcompany.com",
    "time.internal.network",
    "secure-timeserver.corp"
]

provider = TimeProvider(settings)
```

### Precision Timing
```python
# High-precision time for financial applications
settings = TimeSettings()
settings.update_interval = 1.0  # Very frequent updates
settings.timeout = 1.0         # Fast timeout for precision

provider = TimeProvider(settings)

# Get microsecond precision time
precise_time = provider.get_current_time()
microseconds = precise_time.microsecond
print(f"Precision: {microseconds} microseconds")
```

### Time Zone Handling
```python
# Configure for specific time zones
settings = TimeSettings()
settings.timezone = "America/New_York"  # Eastern Time
settings.time_servers = ["time.nist.gov"]  # Use reliable source

provider = TimeProvider(settings)

# Get time in configured timezone
local_time = provider.get_current_time()
print(f"Local time: {local_time}")
```

## Security Considerations

### Time-Based Attacks
```python
# Prevent replay attacks with strict time validation
provider = TimeProvider()

# Very strict tolerance for high-security applications
result = provider.verify_timestamp(timestamp, tolerance=5.0)  # 5 second tolerance

if not result['valid']:
    print("Timestamp outside acceptable range - potential replay attack")
```

### Secure Time Sources
```python
# Use only trusted time sources
settings = TimeSettings()
settings.time_servers = [
    "time.nist.gov",       # US Government time
    "time.google.com",     # Google time service
    "ntp.ubuntu.com"       # Ubuntu NTP pool
]
settings.local_fallback = False  # Don't fall back to local time

provider = TimeProvider(settings)
```

## Performance Optimization

### Caching Strategy
```python
# Configure caching for performance
settings = TimeSettings()
settings.update_interval = 300.0  # Cache for 5 minutes
settings.timeout = 3.0           # Fast timeout

provider = TimeProvider(settings)

# Time is cached and reused
start = time.time()
time1 = provider.get_current_time()
time2 = provider.get_current_time()  # Uses cache
end = time.time()

print(f"First call: {(time1.timestamp() - start)*1000:.1f}ms")
print(f"Second call: {(time2.timestamp() - start)*1000:.1f}ms")
```

### Load Balancing
```python
# Distribute load across multiple time servers
settings = TimeSettings()
settings.time_servers = [
    "0.pool.ntp.org",
    "1.pool.ntp.org",
    "2.pool.ntp.org",
    "3.pool.ntp.org"
]

provider = TimeProvider(settings)

# Provider automatically balances across servers
verification = provider.get_time_server_verification()
print(f"Servers used: {len(verification)}")
```

This TimeProvider module ensures accurate, reliable time synchronization for QR Live Protocol with comprehensive error handling, performance optimization, and security features.

