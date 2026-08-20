"""
Command Line Interface for QRLP.

Provides comprehensive CLI for QR Live Protocol operations including
live streaming, verification, and configuration management.
"""

import json
import sys
import threading
import time
from pathlib import Path

import click

from .config import QRLPConfig
from .core import QRLiveProtocol
from .frame_recovery import FrameRecoveryConfig
from .live_simulator import LiveSimulator, OpticalChannelModel
from .optical_throughput import ThroughputConfig
from .time_stamper import TimeStamper
from .time_stamper_integration import QRLPTimeStampVerifier
from .trust import TrustStore
from .web_server import QRLiveWebServer


@click.group()
@click.version_option(version="1.5.0")
@click.option('--config', '-c', type=click.Path(exists=True),
              help='Configuration file path (JSON or YAML)')
@click.option('--debug', '-d', is_flag=True, help='Enable debug mode')
@click.pass_context
def cli(ctx, config, debug):
    """
    QR Live Protocol (QRLP) - Generate live, verifiable QR codes for streaming.

    QRLP creates cryptographically verifiable QR codes with timestamps,
    blockchain verification, and identity confirmation for livestreaming
    and official video releases.
    """
    # Initialize context
    ctx.ensure_object(dict)

    # Load configuration
    if config:
        ctx.obj['config'] = QRLPConfig.from_file(config)
    else:
        ctx.obj['config'] = QRLPConfig.from_env()

    # Set debug mode
    if debug:
        ctx.obj['config'].logging_settings.level = 'DEBUG'
        ctx.obj['config'].web_settings.debug = True


@cli.command()
@click.option('--port', '-p', type=int, help='Web server port')
@click.option('--host', '-h', default='localhost', help='Web server host')
@click.option('--interval', '-i', type=float, help='Update interval in seconds')
@click.option('--no-browser', is_flag=True, help='Do not auto-open browser')
@click.option('--identity-file', type=click.Path(), help='Identity file path')
@click.pass_context
def live(ctx, port, host, interval, no_browser, identity_file):
    """Start live QR code generation and web display."""
    config = ctx.obj['config']

    # Override settings from command line
    if port:
        config.web_settings.port = port
    if host:
        config.web_settings.host = host
    if interval:
        config.update_interval = interval
    if no_browser:
        config.web_settings.auto_open_browser = False
    if identity_file:
        config.identity_settings.identity_file = identity_file

    # Validate configuration
    issues = config.validate()
    if issues:
        click.echo("Configuration issues found:", err=True)
        for issue in issues:
            click.echo(f"  - {issue}", err=True)
        sys.exit(1)

    click.echo(f"Starting QRLP live server on {config.web_settings.host}:{config.web_settings.port}")

    try:
        # Initialize QRLP
        qrlp = QRLiveProtocol(config)

        # Initialize web server
        web_server = QRLiveWebServer(config.web_settings, verifier=qrlp)

        # Connect QRLP updates to web server
        qrlp.add_update_callback(web_server.update_qr_display)

        # Start services
        web_server.start_server(threaded=True)
        qrlp.start_live_generation()

        click.echo(f"✓ QRLP server running at: {web_server.get_server_url()}")
        click.echo("Press Ctrl+C to stop...")

        # Keep running until interrupted
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            click.echo("\nShutting down...")
            qrlp.stop_live_generation()
            web_server.stop_server()
            click.echo("QRLP stopped.")

    except Exception as e:
        click.echo(f"Error starting QRLP: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option('--port', '-p', type=int, help='Web server port')
@click.option('--host', '-h', default='localhost', help='Web server host')
@click.option('--interval', '-i', type=float, help='Update interval in seconds')
@click.option('--no-browser', is_flag=True, help='Do not auto-open browser')
@click.option('--identity-file', type=click.Path(), help='Identity file path')
@click.pass_context
def dashboard(ctx, port, host, interval, no_browser, identity_file):
    """Start QRLP and open the improvement dashboard."""
    config = ctx.obj['config']

    if port:
        config.web_settings.port = port
    if host:
        config.web_settings.host = host
    if interval:
        config.update_interval = interval
    if identity_file:
        config.identity_settings.identity_file = identity_file

    config.web_settings.auto_open_browser = False

    issues = config.validate()
    if issues:
        click.echo("Configuration issues found:", err=True)
        for issue in issues:
            click.echo(f"  - {issue}", err=True)
        sys.exit(1)

    click.echo(
        f"Starting QRLP improvement dashboard on "
        f"{config.web_settings.host}:{config.web_settings.port}"
    )

    try:
        qrlp = QRLiveProtocol(config)
        web_server = QRLiveWebServer(config.web_settings, verifier=qrlp)
        qrlp.add_update_callback(web_server.update_qr_display)

        web_server.start_server(threaded=True)
        qrlp.start_live_generation()

        dashboard_url = f"{web_server.get_server_url()}/improve"
        click.echo(f"✓ Improve dashboard running at: {dashboard_url}")
        if not no_browser:
            threading.Timer(1.0, web_server.open_improve_dashboard).start()
        click.echo("Press Ctrl+C to stop...")

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            click.echo("\nShutting down...")
            qrlp.stop_live_generation()
            web_server.stop_server()
            click.echo("QRLP dashboard stopped.")

    except Exception as e:
        click.echo(f"Error starting QRLP dashboard: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option('--output', '-o', type=click.Path(), help='Output file for QR image')
@click.option('--format', '-f', type=click.Choice(['png', 'json', 'both']),
              default='png', help='Output format')
@click.option('--style', '-s', type=click.Choice(['live', 'professional', 'minimal']),
              help='QR code style')
@click.option('--include-text', is_flag=True, help='Include text overlay')
@click.option('--user-data', type=str, help='JSON object to include in the QR payload')
@click.option('--sign/--no-sign', default=None, help='Override signed QR generation')
@click.option('--key-id', type=str, help='Signing key ID to use when signing')
@click.option('--issuer-id', type=str, help='Issuer ID to embed in the QR payload')
@click.option('--public-key-output', type=click.Path(), help='Write signing public key PEM')
@click.option('--trust-record-output', type=click.Path(), help='Write JSON trust store for this QR issuer/key')
@click.pass_context
def generate(
    ctx,
    output,
    format,
    style,
    include_text,
    user_data,
    sign,
    key_id,
    issuer_id,
    public_key_output,
    trust_record_output,
):
    """Generate a single QR code with current verification data."""
    config = ctx.obj['config']
    if issuer_id:
        config.security_settings.issuer_id = issuer_id

    try:
        # Initialize QRLP
        qrlp = QRLiveProtocol(config)
        parsed_user_data = _parse_user_data(user_data)
        sign_data = config.security_settings.sign_qr_data if sign is None else sign

        # Generate QR code
        qr_data, qr_image = qrlp.generate_single_qr(
            user_data=parsed_user_data,
            sign_data=sign_data,
            signing_key_id=key_id,
        )

        click.echo(f"Generated QR code with sequence #{qr_data.sequence_number}")
        click.echo(f"Timestamp: {qr_data.timestamp}")
        click.echo(f"Identity: {qr_data.identity_hash[:16]}...")
        click.echo(f"Issuer: {qr_data.issuer_id}")
        click.echo(f"Signed: {'yes' if qr_data.digital_signature else 'no'}")

        if qr_data.blockchain_hashes:
            click.echo(f"Blockchain verification: {list(qr_data.blockchain_hashes.keys())}")

        if (public_key_output or trust_record_output) and not qr_data.signing_key_id:
            raise click.ClickException("Public key/trust record export requires --sign")

        if public_key_output:
            public_key = qrlp.key_manager.export_public_key(qr_data.signing_key_id)
            if not public_key:
                raise click.ClickException(f"Could not export public key: {qr_data.signing_key_id}")
            _write_bytes(public_key_output, public_key)
            click.echo(f"✓ Public key saved to: {public_key_output}")

        if trust_record_output:
            public_key = qrlp.key_manager.export_public_key(qr_data.signing_key_id)
            if not public_key:
                raise click.ClickException(f"Could not export public key: {qr_data.signing_key_id}")
            trust_store = TrustStore()
            trust_store.add_public_key(
                qr_data.issuer_id,
                qr_data.signing_key_id,
                public_key,
                qr_data.signature_algorithm,
            )
            trust_store.to_file(trust_record_output)
            click.echo(f"✓ Trust store saved to: {trust_record_output}")

        # Handle output
        if output:
            if format in ['png', 'both']:
                png_path = output if output.endswith('.png') else f"{output}.png"
                with open(png_path, 'wb') as f:
                    f.write(qr_image)
                click.echo(f"✓ QR image saved to: {png_path}")

            if format in ['json', 'both']:
                json_path = output if output.endswith('.json') else f"{output}.json"
                with open(json_path, 'w') as f:
                    json.dump(qr_data.__dict__, f, indent=2, default=str)
                click.echo(f"✓ QR data saved to: {json_path}")
        else:
            # Print QR data to console
            click.echo("\nQR Data:")
            click.echo(json.dumps(qr_data.__dict__, indent=2, default=str))

    except Exception as e:
        click.echo(f"Error generating QR code: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument('qr_data', required=False, type=str)
@click.option('--file', '-f', 'input_file', type=click.Path(exists=True),
              help='Read QR JSON from a file (single) or batch JSON array')
@click.option('--batch', is_flag=True,
              help='Treat --file as a batch JSON array of QR payloads to verify')
@click.option('--tolerance', '-t', type=float, default=30.0,
              help='Time tolerance in seconds')
@click.option('--public-key', type=click.Path(exists=True),
              help='Trusted issuer public key PEM for external signature verification')
@click.option('--trust-store', type=click.Path(exists=True),
              help='JSON trust store with issuer public keys')
@click.option('--issuer', type=str,
              help='Issuer ID for the trusted public key (defaults to QR issuer_id)')
@click.option('--key-id', type=str,
              help='Signing key ID for the trusted public key (defaults to QR signing_key_id)')
@click.option('--algorithm', type=click.Choice(['rsa', 'ecdsa']), default='rsa',
              help='Signature algorithm for --public-key')
@click.option('--json-output', is_flag=True, help='Print raw verification JSON')
@click.option('--verbose', '-v', is_flag=True, help='Show raw verification JSON after summary')
@click.pass_context
def verify(
    ctx,
    qr_data,
    input_file,
    batch,
    tolerance,
    public_key,
    trust_store,
    issuer,
    key_id,
    algorithm,
    json_output,
    verbose,
):
    """Verify a QR code's data and authenticity."""
    config = ctx.obj['config']
    config.verification_settings.max_time_drift = tolerance

    try:
        # Batch verification mode
        if batch and input_file:
            with open(input_file) as f:
                payloads = json.load(f)
            if not isinstance(payloads, list):
                raise click.ClickException("--batch file must contain a JSON array")

            qrlp = QRLiveProtocol(config)
            if trust_store:
                qrlp.trust_store = TrustStore.from_file(trust_store)

            results_list = []
            valid_count = 0
            for i, payload in enumerate(payloads):
                payload_str = payload if isinstance(payload, str) else json.dumps(payload)
                result = qrlp.verify_qr_data(payload_str)
                results_list.append(result)
                if result.get('valid'):
                    valid_count += 1
                click.echo(f"QR #{i+1}: {'✓ VALID' if result.get('valid') else '✗ INVALID'}")

            click.echo(f"\nBatch: {valid_count}/{len(payloads)} valid")
            if json_output:
                click.echo(json.dumps(results_list, indent=2, default=str))
            return

        qr_data = _load_qr_data_argument(qr_data, input_file)

        # Initialize QRLP
        qrlp = QRLiveProtocol(config)

        if trust_store:
            qrlp.trust_store = TrustStore.from_file(trust_store)

        if public_key:
            parsed = json.loads(qr_data)
            issuer = issuer or parsed.get('issuer_id')
            key_id = key_id or parsed.get('signing_key_id')
            if not issuer or not key_id:
                click.echo("--public-key requires --issuer/--key-id or QR issuer_id/signing_key_id fields", err=True)
                sys.exit(1)
            qrlp.trust_store.add_public_key_file(issuer, key_id, public_key, algorithm)

        # Verify QR data
        results = qrlp.verify_qr_data(qr_data)

        if json_output:
            click.echo(json.dumps(results, indent=2, default=str))
            return

        click.echo("Verification Results:")
        click.echo(f"  Valid JSON: {'✓' if results['valid_json'] else '✗'}")

        if results['valid_json']:
            click.echo(f"  Identity verified: {'✓' if results['identity_verified'] else '✗'}")
            click.echo(f"  Time verified: {'✓' if results['time_verified'] else '✗'}")
            click.echo(f"  Blockchain verified: {'✓' if results['blockchain_verified'] else '✗'}")
            click.echo(f"  Signature verified: {'✓' if results['signature_verified'] else '✗'}")
            click.echo(f"  HMAC verified: {'✓' if results['hmac_verified'] else '✗'}")
            click.echo(f"  Trust mode: {results.get('trust_mode', 'none')}")
        else:
            click.echo(f"  Error: {results.get('error', 'Unknown error')}")

        # Overall result
        overall_valid = results.get('valid', False)

        click.echo(f"\nOverall: {'✓ VALID' if overall_valid else '✗ INVALID'}")
        if verbose:
            click.echo("\nRaw Results:")
            click.echo(json.dumps(results, indent=2, default=str))

    except Exception as e:
        click.echo(f"Error verifying QR code: {e}", err=True)
        sys.exit(1)


@cli.group()
def keys():
    """Manage QRLP signing keys."""


@keys.command("generate")
@click.option('--algorithm', type=click.Choice(['rsa', 'ecdsa']), default='rsa')
@click.option('--key-size', type=int, default=2048)
@click.option('--purpose', type=str, default='qr_signing')
@click.option('--public-key-output', type=click.Path(), help='Write generated public key PEM')
@click.pass_context
def keys_generate(ctx, algorithm, key_size, purpose, public_key_output):
    """Generate a signing key pair."""
    qrlp = QRLiveProtocol(ctx.obj['config'])
    public_key, _private_key = qrlp.key_manager.generate_keypair(
        algorithm=algorithm,
        key_size=key_size,
        purpose=purpose,
    )
    key_id = next(reversed(qrlp.key_manager.list_keys()))
    click.echo(f"Generated key: {key_id}")
    if public_key_output:
        _write_bytes(public_key_output, public_key)
        click.echo(f"✓ Public key saved to: {public_key_output}")


@keys.command("list")
@click.pass_context
def keys_list(ctx):
    """List local signing keys."""
    qrlp = QRLiveProtocol(ctx.obj['config'])
    keys_info = qrlp.key_manager.list_keys()
    if not keys_info:
        click.echo("No keys found.")
        return

    for key_id, info in keys_info.items():
        click.echo(
            f"{key_id} algorithm={info.algorithm} size={info.key_size} "
            f"purpose={info.purpose} usage={info.usage_count}"
        )


@keys.command("export-public")
@click.argument('key_id', type=str)
@click.option('--output', '-o', type=click.Path(), required=True)
@click.pass_context
def keys_export_public(ctx, key_id, output):
    """Export a local key's public PEM."""
    qrlp = QRLiveProtocol(ctx.obj['config'])
    public_key = qrlp.key_manager.export_public_key(key_id)
    if not public_key:
        raise click.ClickException(f"Key not found: {key_id}")
    _write_bytes(output, public_key)
    click.echo(f"✓ Public key saved to: {output}")


@keys.command("rotate")
@click.argument('key_id', type=str)
@click.option('--algorithm', type=click.Choice(['rsa', 'ecdsa']), default='rsa')
@click.option('--key-size', type=int, default=2048)
@click.option('--public-key-output', type=click.Path(), help='Write new public key PEM')
@click.option('--archive-dir', type=click.Path(), help='Archive directory for the old key (default: key_dir/archive)')
@click.option('--trust-store', type=click.Path(), help='Add the old public key to this trust store for continued verification')
@click.option('--issuer', type=str, help='Trusted issuer ID (required with --trust-store)')
@click.pass_context
def keys_rotate(ctx, key_id, algorithm, key_size, public_key_output,
                archive_dir, trust_store, issuer):
    """Rotate a signing key: generate a new key pair and archive the old one.

    The old key is archived (not destroyed) so previously signed QRs remain
    verifiable. Use --trust-store to register the old public key for an
    external verifier.
    """
    qrlp = QRLiveProtocol(ctx.obj['config'])
    keypair = qrlp.key_manager.get_keypair(key_id)
    if not keypair:
        raise click.ClickException(f"Key not found: {key_id}")

    # Generate the new key and archive the old one.
    new_key_id, old_public = qrlp.key_manager.rotate_signing_key(
        key_id=key_id,
        algorithm=algorithm,
        key_size=key_size,
        archive_dir=archive_dir,
    )
    click.echo(f"✓ New key generated: {new_key_id}")
    click.echo(f"✓ Old key archived: {key_id}")

    # Optionally write the new public key PEM.
    if public_key_output:
        new_public = qrlp.key_manager.export_public_key(new_key_id)
        if new_public:
            _write_bytes(public_key_output, new_public)
            click.echo(f"✓ New public key saved to: {public_key_output}")

    # Optionally register the old public key with a trust store.
    if trust_store:
        if not issuer:
            raise click.ClickException("--issuer is required with --trust-store")
        if not old_public:
            raise click.ClickException("Could not read old key public material")
        store = TrustStore()
        if Path(trust_store).exists():
            store = TrustStore.from_file(trust_store)
        store.add_public_key(issuer, key_id, old_public, keypair.algorithm)
        store.to_file(trust_store)
        click.echo(f"✓ Old public key added to trust store: {trust_store}")


@cli.group()
def trust():
    """Manage JSON trust stores for external verification."""


@trust.command("add")
@click.option('--issuer', required=True, help='Trusted issuer ID')
@click.option('--key-id', required=True, help='Trusted signing key ID')
@click.option('--public-key', required=True, type=click.Path(exists=True), help='Public key PEM')
@click.option('--algorithm', type=click.Choice(['rsa', 'ecdsa']), default='rsa')
@click.option('--store', required=True, type=click.Path(), help='Trust store JSON to create/update')
def trust_add(issuer, key_id, public_key, algorithm, store):
    """Add an issuer public key to a trust store."""
    if store and click.format_filename(store):
        try:
            trust_store = TrustStore.from_file(store)
        except FileNotFoundError:
            trust_store = TrustStore()
    else:
        trust_store = TrustStore()

    trust_store.add_public_key_file(issuer, key_id, public_key, algorithm)
    trust_store.to_file(store)
    click.echo(f"✓ Trusted {issuer}/{key_id} in {store}")


@trust.command("list")
@click.argument('store', type=click.Path(exists=True))
def trust_list(store):
    """List trusted issuer public keys in a trust store."""
    trust_store = TrustStore.from_file(store)
    if len(trust_store) == 0:
        click.echo("No trusted keys found.")
        return

    for key in trust_store.list_public_keys():
        click.echo(f"{key.issuer_id} {key.key_id} algorithm={key.algorithm}")


@cli.command()
@click.option('--output', '-o', type=click.Path(), required=True,
              help='Output configuration file path')
@click.option('--format', '-f', type=click.Choice(['json', 'yaml']),
              default='json', help='Configuration format')
@click.pass_context
def config_init(ctx, output, format):
    """Initialize a new configuration file with defaults."""
    try:
        config = QRLPConfig()

        if format == 'json':
            with open(output, 'w') as f:
                json.dump(config.to_dict(), f, indent=2, default=str)
        elif format == 'yaml':
            try:
                import yaml
                with open(output, 'w') as f:
                    yaml.dump(config.to_dict(), f, default_flow_style=False)
            except ImportError:
                click.echo("PyYAML required for YAML format", err=True)
                sys.exit(1)

        click.echo(f"✓ Configuration file created: {output}")

    except Exception as e:
        click.echo(f"Error creating configuration: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option('--json-output', is_flag=True, help='Output status as JSON')
@click.pass_context
def status(ctx, json_output):
    """Show current QRLP status and statistics."""
    config = ctx.obj['config']

    try:
        # Initialize QRLP (without starting live generation)
        qrlp = QRLiveProtocol(config)

        stats = qrlp.get_statistics()

        if json_output:
            click.echo(json.dumps(stats, indent=2, default=str))
            return

        click.echo("QRLP Status:")
        click.echo(f"  Running: {'Yes' if stats['running'] else 'No'}")
        click.echo(f"  Total updates: {stats['total_updates']}")
        click.echo(f"  Sequence number: {stats['sequence_number']}")

        if stats['current_qr_data']:
            qr_data = stats['current_qr_data']
            click.echo(f"  Current timestamp: {qr_data['timestamp']}")
            click.echo(f"  Identity hash: {qr_data['identity_hash'][:16]}...")

        # Component statistics
        click.echo("\nComponent Statistics:")

        time_stats = stats.get('time_provider_stats', {})
        click.echo("  Time provider:")
        click.echo(f"    Success rate: {time_stats.get('success_rate', 0):.2%}")
        click.echo(f"    Active servers: {time_stats.get('active_servers', 0)}")

        blockchain_stats = stats.get('blockchain_stats', {})
        click.echo("  Blockchain verifier:")
        click.echo(f"    Success rate: {blockchain_stats.get('success_rate', 0):.2%}")
        click.echo(f"    Cached chains: {blockchain_stats.get('cached_chains', [])}")

        identity_stats = stats.get('identity_stats', {})
        click.echo("  Identity manager:")
        click.echo(f"    Hash generations: {identity_stats.get('hash_generations', 0)}")
        click.echo(f"    File count: {identity_stats.get('file_count', 0)}")

    except Exception as e:
        click.echo(f"Error getting status: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument('file_path', type=click.Path(exists=True))
@click.option('--alias', '-a', type=str, help='Alias for the file')
@click.pass_context
def add_file(ctx, file_path, alias):
    """Add a file to the identity for verification."""
    config = ctx.obj['config']

    try:
        qrlp = QRLiveProtocol(config)

        success = qrlp.identity_manager.add_file_to_identity(file_path, alias)

        if success:
            click.echo(f"✓ File added to identity: {file_path}")
            if alias:
                click.echo(f"  Alias: {alias}")
        else:
            click.echo(f"✗ Failed to add file: {file_path}", err=True)
            sys.exit(1)

    except Exception as e:
        click.echo(f"Error adding file: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument('config_path', type=click.Path(exists=True))
@click.pass_context
def config_validate(ctx, config_path):
    """Validate a configuration file without starting QRLP."""
    try:
        config = QRLPConfig.from_file(config_path)
        issues = config.validate()

        if issues:
            click.echo(f"✗ Configuration has {len(issues)} issue(s):", err=True)
            for issue in issues:
                click.echo(f"  - {issue}", err=True)
            sys.exit(1)
        else:
            click.echo(f"✓ Configuration is valid: {config_path}")
            click.echo(f"  Update interval: {config.update_interval}s")
            click.echo(f"  Web port: {config.web_settings.port}")
            click.echo(f"  Error correction: {config.qr_settings.error_correction_level}")
            click.echo(f"  Enabled chains: {config.blockchain_settings.enabled_chains or 'none'}")
            click.echo(f"  Max time drift: {config.verification_settings.max_time_drift}s")

    except Exception as e:
        click.echo(f"Error validating configuration: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument('qr_json_file', type=click.Path(exists=True))
@click.option('--proof-dir', type=click.Path(), default='output/timestamps',
              help='Where to save .ots proof files (default: output/timestamps/)')
@click.option('--server', default='https://stamp.opentimestamps.org',
              help='OpenTimestamps server URL')
@click.option('--signing-key', type=click.Path(),
              help='Optional: sign the QR before stamping (PEM private key)')
@click.option('--json-output', is_flag=True, help='Output result as JSON')
def stamp(qr_json_file: str, proof_dir: str, server: str, signing_key: str, json_output: bool) -> None:
    """Stamp a QR JSON file with OpenTimestamps.

    Computes the SHA-256 of the QR payload, submits it to an OpenTimestamps
    calendar server, and saves the ``.ots`` proof file alongside the input.
    The proof can later be verified with ``qrlp verify-ots``.
    """
    try:
        with open(qr_json_file, encoding='utf-8') as f:
            qr_json = f.read()

        stamper = TimeStamper(
            enabled=True,
            server=server,
            min_interval=0,
            proof_dir=Path(proof_dir),
        )
        proof_path = stamper.stamp(qr_json.encode('utf-8'))

        if proof_path is None:
            click.echo("✗ Timestamping failed or disabled.", err=True)
            sys.exit(1)

        result = {
            "ots_proof_path": str(proof_path),
            "qr_file": qr_json_file,
            "server": server,
        }
        if json_output:
            click.echo(json.dumps(result, indent=2))
        else:
            click.echo(f"✓ OTS proof saved to: {proof_path}")
            click.echo(f"  QR file: {qr_json_file}")
            click.echo(f"  Server: {server}")
    except Exception as e:
        click.echo(f"Error stamping QR: {e}", err=True)
        sys.exit(1)


@cli.command(name='verify-ots')
@click.argument('qr_json_file', type=click.Path(exists=True))
@click.argument('proof_file', type=click.Path(exists=True))
@click.option('--tolerance', '-t', type=int, default=60,
              help='Acceptable time drift in seconds (default: 60)')
@click.option('--json-output', is_flag=True, help='Output result as JSON')
def verify_ots(qr_json_file: str, proof_file: str, tolerance: int, json_output: bool) -> None:
    """Verify a QR JSON file against an OpenTimestamps proof.

    Checks that the QR data matches the ``.ots`` proof and reports the
    attested timestamp and blockchain.
    """
    try:
        with open(qr_json_file, encoding='utf-8') as f:
            qr_json = f.read()

        stamper = TimeStamper(enabled=False)
        verifier = QRLPTimeStampVerifier(stamper)
        result = verifier.verify_qr_with_timestamp(
            qr_json,
            Path(proof_file),
            tolerance_seconds=tolerance,
        )

        if json_output:
            click.echo(json.dumps(result, indent=2, default=str))
            return

        click.echo("OpenTimestamps Verification:")
        click.echo(f"  OTS verified: {'✓' if result.get('ots_verified') else '✗'}")
        click.echo(f"  Proof path: {result.get('ots_proof_path', '')}")
        click.echo(f"  Timestamp: {result.get('ots_timestamp', '')}")
        click.echo(f"  Blockchain: {result.get('ots_blockchain', '')}")
        click.echo(
            f"\nOverall: {'✓ VERIFIED' if result.get('ots_verified') else '✗ NOT VERIFIED'}"
        )
    except Exception as e:
        click.echo(f"Error verifying OTS proof: {e}", err=True)
        sys.exit(1)


def _parse_user_data(user_data):
    if not user_data:
        return None
    parsed = json.loads(user_data)
    if not isinstance(parsed, dict):
        raise click.ClickException("--user-data must be a JSON object")
    return parsed


def _load_qr_data_argument(qr_data, input_file=None) -> str:
    if input_file:
        with open(input_file) as f:
            return f.read()
    if not qr_data:
        raise click.ClickException("Provide QR JSON as an argument or use --file")
    if qr_data.startswith("@"):
        with open(qr_data[1:]) as f:
            return f.read()
    return qr_data


def _write_bytes(path: str, data: bytes) -> None:
    with open(path, 'wb') as f:
        f.write(data)


@cli.command("simulate-live")
@click.option('--frames', '-n', type=int, default=100,
              help='Number of frames to simulate (default: 100)')
@click.option('--drop-rate', type=float, default=0.15,
              help='Fraction of frames dropped by the optical channel (0..1)')
@click.option('--reorder-rate', type=float, default=0.0,
              help='Fraction of received frames delivered out of order (0..1)')
@click.option('--seed', type=int, default=None,
              help='PRNG seed for a deterministic simulation')
@click.option('--json-output', is_flag=True,
              help='Output the report as JSON')
def simulate_live(frames, drop_rate, reorder_rate, seed, json_output):
    """Run an end-to-end live streaming simulation (no hardware required)."""
    try:
        sim = LiveSimulator(
            config=ThroughputConfig(),
            recovery_config=FrameRecoveryConfig(),
            channel=OpticalChannelModel(
                drop_rate=drop_rate,
                reorder_rate=reorder_rate,
                seed=seed,
            ),
        )
        report = sim.run(frames)
        if json_output:
            click.echo(json.dumps(report.summary_json(), indent=2))
        else:
            click.echo(sim.summary(frames))
    except ValueError as e:
        raise click.ClickException(str(e)) from e


@cli.command("benchmark-ws")
@click.option('--iterations', '-n', type=int, default=100,
              help='Number of simulated WebSocket client updates (default: 100)')
@click.option('--json-output', is_flag=True, help='Output results as JSON')
@click.pass_context
def benchmark_ws(ctx, iterations, json_output):
    """Benchmark WebSocket QR-update throughput (in-process, no network)."""
    qrlp = QRLiveProtocol(ctx.obj['config'])
    # Generate a baseline QR so the server has data to broadcast.
    _, qr_image = qrlp.generate_single_qr({"benchmark": True})
    server = QRLiveWebServer(ctx.obj['config'].web_settings, verifier=qrlp)
    server.current_qr_data = qrlp.get_current_qr_data()
    server.current_qr_image = qr_image

    try:
        results = server.benchmark_websocket_throughput(iterations)
    except ValueError as e:
        raise click.ClickException(str(e)) from e

    if json_output:
        click.echo(json.dumps(results, indent=2))
    else:
        click.echo("WebSocket QR-update throughput benchmark")
        click.echo("=" * 45)
        click.echo(f"  Iterations       : {results['iterations']}")
        click.echo(f"  Avg latency      : {results['avg_ms']:.3f} ms")
        click.echo(f"  p50 latency      : {results['p50_ms']:.3f} ms")
        click.echo(f"  p95 latency      : {results['p95_ms']:.3f} ms")
        click.echo(f"  Updates / second : {results['updates_per_second']:.1f}")
        click.echo(f"  Payload size     : {results['payload_bytes']} bytes")


if __name__ == '__main__':
    cli()
