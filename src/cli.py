"""
Command Line Interface for QRLP.

Provides comprehensive CLI for QR Live Protocol operations including
live streaming, verification, and configuration management.
"""

import json
import math
import os
import sys
import time
from copy import deepcopy
from pathlib import Path

import click

from . import __version__
from .config import QRLPConfig, TimeSettings
from .core import QRLiveProtocol
from .frame_recovery import FrameRecoveryConfig
from .live_simulator import LiveSimulator, OpticalChannelModel
from .optical_throughput import ThroughputConfig
from .serializer import QRSerializer
from .time_stamper import TimeStamper
from .time_stamper_integration import QRLPTimeStampVerifier
from .trust import TrustStore
from .web_server import QRLiveWebServer


@click.group()
@click.version_option(version=__version__)
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
    ctx.ensure_object(dict)
    try:
        settings = QRLPConfig.from_file(config) if config else QRLPConfig.from_env()
        if config and settings.security_settings.encryption_key is None:
            settings.security_settings.encryption_key = os.getenv('QRLP_ENCRYPTION_KEY') or None
    except (OSError, ValueError, ImportError) as exc:
        raise click.ClickException(str(exc)) from exc

    if debug:
        settings.logging_settings.level = 'DEBUG'
        settings.web_settings.debug = True
    ctx.obj['config'] = settings


def _live_options(command):
    """Share the same CLI overrides for both browser entry points."""
    for option in (
        click.option('--identity-file', type=click.Path(dir_okay=False), help='Identity file path'),
        click.option('--no-browser', is_flag=True, help='Do not auto-open browser'),
        click.option('--interval', '-i', type=float, help='Update interval in seconds'),
        click.option('--host', '-h', help='Web server host'),
        click.option('--port', '-p', type=click.IntRange(1, 65535), help='Web server port'),
    ):
        command = option(command)
    return command


@cli.command()
@_live_options
@click.pass_obj
def live(obj, port, host, interval, no_browser, identity_file):
    """Start live QR generation and display."""
    _serve_live(obj['config'], port, host, interval, no_browser, identity_file, dashboard=False)


@cli.command()
@_live_options
@click.pass_obj
def dashboard(obj, port, host, interval, no_browser, identity_file):
    """Start live QR generation and open the improvement dashboard."""
    _serve_live(obj['config'], port, host, interval, no_browser, identity_file, dashboard=True)


def _serve_live(config, port, host, interval, no_browser, identity_file, *, dashboard):
    web = config.web_settings
    if port is not None:
        web.port = port
    if host is not None:
        web.host = host
    if interval is not None:
        config.update_interval = interval
    if identity_file is not None:
        config.identity_settings.identity_file = identity_file

    issues = config.validate()
    if issues:
        raise click.ClickException("Configuration issues:\n  - " + "\n  - ".join(issues))

    open_browser = web.auto_open_browser and not no_browser
    web.auto_open_browser = False  # Open the selected page once, after a successful bind.
    try:
        qrlp = QRLiveProtocol(config)
        server = QRLiveWebServer(web, verifier=qrlp)
        qrlp.add_update_callback(server.update_qr_display)
        qrlp.set_user_data_callback(server.get_user_data)
        server.start_server(threaded=True)
        try:
            qrlp.start_live_generation()
            url = server.get_server_url() + ('/improve' if dashboard else '')
            service = 'improvement dashboard' if dashboard else 'server'
            click.echo(f"QRLP {service} running at: {url}")
            if open_browser:
                import webbrowser

                try:
                    webbrowser.open(url)
                except (OSError, webbrowser.Error):
                    click.echo("Could not open the browser automatically. Open the URL above.", err=True)
            click.echo("Press Ctrl+C to stop.")
            while True:
                time.sleep(1)
        finally:
            try:
                qrlp.stop_live_generation()
            finally:
                server.stop_server()
    except KeyboardInterrupt:
        click.echo("\nQRLP stopped.")
    except Exception as exc:
        raise click.ClickException(f"Could not run the live server: {exc}") from exc


@cli.command()
@click.option('--output', '-o', type=click.Path(), help='Output file for QR image')
@click.option('--format', '-f', type=click.Choice(['png', 'json', 'both']),
              default='png', help='Output format')
@click.option('--style', '-s', type=click.Choice(['live', 'professional', 'minimal']),
              help='QR code style')
@click.option('--include-text', is_flag=True, help='Include text overlay')
@click.option('--user-data', type=str, help='JSON object to include in the QR payload')
@click.option('--sign/--no-sign', default=None, help='Override signed QR generation')
@click.option('--encrypt/--no-encrypt', default=None, help='Override QR payload encryption')
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
    encrypt,
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
        parsed_user_data = _parse_user_data(user_data)
        sign_data = config.security_settings.sign_qr_data if sign is None else sign
        encrypt_data = config.security_settings.encrypt_qr_data if encrypt is None else encrypt
        if (public_key_output or trust_record_output) and not sign_data:
            raise click.ClickException("Public key/trust record export requires signing (--sign)")
        if encrypt_data and not config.security_settings.encryption_key:
            raise click.ClickException("Encrypted output requires a persistent key (QRLP_ENCRYPTION_KEY or config)")
        if encrypt_data and not sign_data:
            raise click.ClickException("Use --sign for encrypted output so another process can authenticate it")

        qrlp = QRLiveProtocol(config)
        qr_data, qr_image = qrlp.generate_single_qr(
            user_data=parsed_user_data,
            sign_data=sign_data,
            encrypt_data=encrypt_data,
            signing_key_id=key_id,
            style=style,
            include_text=include_text,
        )

        click.echo(f"Generated QR code with sequence #{qr_data.sequence_number}")
        click.echo(f"Timestamp: {qr_data.timestamp}")
        click.echo(f"Identity: {qr_data.identity_hash[:16]}...")
        click.echo(f"Issuer: {qr_data.issuer_id}")
        click.echo(f"Signed: {'yes' if qr_data.digital_signature else 'no'}")
        if qr_data.blockchain_hashes:
            click.echo(f"Blockchain tip context: {list(qr_data.blockchain_hashes.keys())}")

        if public_key_output or trust_record_output:
            if not qr_data.signing_key_id:
                raise click.ClickException("QR generation did not produce a signing key ID")
            public_key = qrlp.key_manager.export_public_key(qr_data.signing_key_id)
            if not public_key:
                raise click.ClickException(f"Could not export public key: {qr_data.signing_key_id}")
            if public_key_output:
                _write_bytes(public_key_output, public_key)
                click.echo(f"✓ Public key saved to: {public_key_output}")
            if trust_record_output:
                trust_store = TrustStore()
                trust_store.add_public_key(
                    qr_data.issuer_id, qr_data.signing_key_id, public_key, qr_data.signature_algorithm,
                )
                trust_store.to_file(trust_record_output)
                click.echo(f"✓ Trust store saved to: {trust_record_output}")

        if output:
            if format in ('png', 'both'):
                extension = config.qr_settings.image_format.lower()
                image_path = Path(output) if output.lower().endswith(f'.{extension}') else Path(f"{output}.{extension}")
                image_path.write_bytes(qr_image)
                click.echo(f"✓ QR image saved to: {image_path}")
            if format in ('json', 'both'):
                json_path = Path(output) if output.endswith('.json') else Path(f"{output}.json")
                json_path.write_bytes(qr_data.to_json().encode('utf-8'))
                click.echo(f"✓ QR data saved to: {json_path}")
        else:
            click.echo("\nQR Data:")
            click.echo(json.dumps(json.loads(qr_data.to_json()), indent=2))
        if qr_data.ots_proof_path:
            click.echo(f"OpenTimestamps proof: {qr_data.ots_proof_path}")
    except click.ClickException:
        raise
    except Exception as exc:
        raise click.ClickException(f"Error generating QR code: {exc}") from exc


@cli.command()
@click.argument('qr_data', required=False, type=str)
@click.option('--file', '-f', 'input_file', type=click.Path(exists=True),
              help='Read QR JSON from a file (single) or batch JSON array')
@click.option('--batch', is_flag=True,
              help='Treat --file as a batch JSON array of QR payloads to verify')
@click.option('--tolerance', '-t', type=float, help='Override time tolerance in seconds')
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
@click.option('--strict', is_flag=True, help='Exit with status 1 when any QR is invalid')
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
    strict,
    verbose,
):
    """Verify a QR code's data and authenticity."""
    config = ctx.obj['config']
    if tolerance is not None:
        if not math.isfinite(tolerance) or tolerance < 0:
            raise click.BadParameter('must be finite and non-negative', param_hint='--tolerance')
        config.verification_settings.max_time_drift = tolerance
    if batch and (not input_file or qr_data):
        raise click.UsageError("--batch requires --file and does not accept an argument")
    if qr_data and input_file:
        raise click.UsageError("Provide a QR argument or --file")
    if batch and public_key and not (issuer and key_id):
        raise click.UsageError("--batch --public-key requires explicit --issuer and --key-id")

    try:
        qrlp = QRLiveProtocol(config)
        if trust_store:
            qrlp.trust_store = TrustStore.from_file(trust_store)

        if batch:
            payloads = QRSerializer.deserialize(Path(input_file).read_text(encoding='utf-8'))
            if not isinstance(payloads, list):
                raise click.ClickException("--batch file must contain a JSON array")
            if public_key:
                qrlp.trust_store.add_public_key_file(issuer, key_id, public_key, algorithm)
            results = [
                qrlp.verify_qr_data(payload if isinstance(payload, str) else json.dumps(payload))
                for payload in payloads
            ]
            if json_output:
                click.echo(json.dumps(results, indent=2))
            else:
                for i, result in enumerate(results, 1):
                    click.echo(f"QR #{i}: {'✓ VALID' if result['valid'] else '✗ INVALID'}")
                click.echo(f"\nBatch: {sum(result['valid'] for result in results)}/{len(results)} valid")
            if strict and not all(result['valid'] for result in results):
                ctx.exit(1)
            return

        qr_data = _load_qr_data_argument(qr_data, input_file)
        if public_key:
            if not (issuer and key_id):
                parsed = QRSerializer.deserialize(qr_data)
                if isinstance(parsed, dict):
                    issuer = issuer or parsed.get('issuer_id')
                    key_id = key_id or parsed.get('signing_key_id')
            if not issuer or not key_id:
                raise click.ClickException(
                    "--public-key requires --issuer/--key-id or QR issuer_id/signing_key_id fields",
                )
            qrlp.trust_store.add_public_key_file(issuer, key_id, public_key, algorithm)

        result = qrlp.verify_qr_data(qr_data)
        if json_output:
            click.echo(json.dumps(result, indent=2))
        else:
            _show_verification(result, verbose)
        if strict and not result['valid']:
            ctx.exit(1)
    except (click.ClickException, click.exceptions.Exit):
        raise
    except Exception as exc:
        raise click.ClickException(f"Error verifying QR code: {exc}") from exc


def _show_verification(result, verbose):
    click.echo("Verification Results:")
    click.echo(f"  Valid JSON: {'✓' if result['valid_json'] else '✗'}")
    if result['valid_json']:
        for label, field in (
            ('Identity', 'identity_verified'), ('Time', 'time_verified'),
            ('Blockchain', 'blockchain_verified'), ('Signature', 'signature_verified'),
            ('HMAC', 'hmac_verified'),
        ):
            click.echo(f"  {label} verified: {'✓' if result[field] else '✗'}")
        click.echo(f"  Trust mode: {result.get('trust_mode', 'none')}")
    if result.get('error'):
        click.echo(f"  Error: {result['error']}")
    click.echo(f"\nOverall: {'✓ VALID' if result['valid'] else '✗ INVALID'}")
    if verbose:
        click.echo("\nRaw Results:")
        click.echo(json.dumps(result, indent=2))


@cli.group()
def keys():
    """Manage QRLP signing keys."""


@keys.command("generate")
@click.option('--algorithm', type=click.Choice(['rsa', 'ecdsa']), default='rsa')
@click.option('--key-size', type=int, help='Defaults to 2048 (RSA) or 256 (ECDSA)')
@click.option('--purpose', type=str, default='qr_signing')
@click.option('--public-key-output', type=click.Path(), help='Write generated public key PEM')
@click.pass_context
def keys_generate(ctx, algorithm, key_size, purpose, public_key_output):
    """Generate a signing key pair."""
    qrlp = QRLiveProtocol(ctx.obj['config'])
    public_key, _private_key = qrlp.key_manager.generate_keypair(
        algorithm=algorithm,
        key_size=key_size if key_size is not None else (256 if algorithm == 'ecdsa' else 2048),
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
@click.option('--key-size', type=int, help='Defaults to 2048 (RSA) or 256 (ECDSA)')
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
    if trust_store and not issuer:
        raise click.UsageError("--issuer is required with --trust-store")

    # Load and check the trust file before modifying local key material.
    store = None
    if trust_store:
        store = TrustStore.from_file(trust_store) if Path(trust_store).exists() else TrustStore()

    qrlp = QRLiveProtocol(ctx.obj['config'])
    keypair = qrlp.key_manager.get_keypair(key_id)
    if not keypair:
        raise click.ClickException(f"Key not found: {key_id}")

    # Generate the new key and archive the old one.
    new_key_id, old_public = qrlp.key_manager.rotate_signing_key(
        key_id=key_id,
        algorithm=algorithm,
        key_size=key_size if key_size is not None else (256 if algorithm == 'ecdsa' else 2048),
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
    if store is not None:
        if not old_public:
            raise click.ClickException("Could not read old key public material")
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
    config = QRLPConfig().to_dict()
    try:
        if format == 'json':
            content = json.dumps(config, indent=2, allow_nan=False) + "\n"
        else:
            try:
                import yaml
            except ImportError as exc:
                raise click.ClickException("Install the full extra for YAML support") from exc
            content = yaml.safe_dump(config, sort_keys=False)
        Path(output).write_text(content, encoding='utf-8')
    except OSError as exc:
        raise click.ClickException(f"Error creating configuration: {exc}") from exc

    click.echo(f"✓ Configuration file created: {output}")


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
@click.option('--server', default=TimeSettings().ots_server,
              help='OpenTimestamps server URL')
@click.option('--signing-key', type=click.Path(),
              hidden=True)
@click.option('--json-output', is_flag=True, help='Output result as JSON')
def stamp(qr_json_file: str, proof_dir: str, server: str, signing_key: str, json_output: bool) -> None:
    """Stamp a QR JSON file with OpenTimestamps.

    Submits a commitment to the exact file bytes and saves the calendar's
    initial receipt in the proof directory.
    """
    if signing_key is not None:
        raise click.UsageError("Sign the QR with qrlp generate --sign before stamping it")
    try:
        qr_bytes = Path(qr_json_file).read_bytes()

        stamper = TimeStamper(
            enabled=True,
            server=server,
            min_interval=0,
            proof_dir=Path(proof_dir),
        )
        proof_path = stamper.stamp(qr_bytes)

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
              hidden=True)
@click.option('--json-output', is_flag=True, help='Output result as JSON')
def verify_ots(qr_json_file: str, proof_file: str, tolerance: int, json_output: bool) -> None:
    """Verify a QR JSON file against an OpenTimestamps proof.

    Checks the exact file digest and reports the receipt's declared state.
    It does not verify a chain anchor or an attested time.
    """
    try:
        qr_json = Path(qr_json_file).read_bytes().decode('utf-8')

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

        click.echo("OpenTimestamps receipt:")
        click.echo(f"  Matching digest and attestation: {'yes' if result.get('ots_verified') else 'no'}")
        click.echo(f"  Proof path: {result.get('ots_proof_path', '')}")
        click.echo(f"  Local receipt time: {result.get('ots_timestamp') or 'unavailable'}")
        click.echo(f"  Reported chain: {result.get('ots_blockchain', '')}")
        click.echo("  Chain anchor checked: no")
    except Exception as e:
        click.echo(f"Error verifying OTS proof: {e}", err=True)
        sys.exit(1)


def _parse_user_data(user_data):
    if not user_data:
        return None
    parsed = QRSerializer.deserialize(user_data)
    if not isinstance(parsed, dict):
        raise click.ClickException("--user-data must be a JSON object")
    return parsed


def _load_qr_data_argument(qr_data, input_file=None) -> str:
    if input_file:
        with open(input_file, encoding='utf-8') as f:
            return f.read()
    if not qr_data:
        raise click.ClickException("Provide QR JSON as an argument or use --file")
    if qr_data.startswith("@"):
        with open(qr_data[1:], encoding='utf-8') as f:
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
        if json_output:
            click.echo(json.dumps(sim.run(frames).summary_json(), indent=2))
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
    config = deepcopy(ctx.obj['config'])
    config.time_settings.time_servers = []
    config.time_settings.local_fallback = True
    config.time_settings.ots_enabled = False
    config.blockchain_settings.enabled_chains.clear()
    qrlp = QRLiveProtocol(config)
    data, qr_image = qrlp.generate_single_qr({"benchmark": True}, sign_data=False, encrypt_data=False)
    server = QRLiveWebServer(config.web_settings, verifier=qrlp)
    server.update_qr_display(data, qr_image)

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
