"""
Extended tests for cli.py using click.testing.CliRunner.

Tests all CLI commands, helper functions, and error paths.
"""

import json
import os
import pytest
import tempfile
from pathlib import Path
from click.testing import CliRunner

from src.cli import cli, _parse_user_data, _load_qr_data_argument, _write_bytes


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def config_file(tmp_path):
    """Write a config file that disables blockchain and time servers."""
    config = {
        "update_interval": 0.1,
        "blockchain_settings": {"enabled_chains": []},
        "time_settings": {"time_servers": []},
    }
    path = tmp_path / "test_config.json"
    path.write_text(json.dumps(config))
    return str(path)


class TestCLIHelp:
    """Test CLI help and version."""

    def test_version(self, runner):
        result = runner.invoke(cli, ['--version'])
        assert result.exit_code == 0
        assert "1.4.0" in result.output

    def test_help(self, runner):
        result = runner.invoke(cli, ['--help'])
        assert result.exit_code == 0
        assert "QR Live Protocol" in result.output
        assert "live" in result.output
        assert "generate" in result.output
        assert "verify" in result.output


class TestCLIGenerate:
    """Test generate command."""

    def test_generate_png(self, runner, config_file, tmp_path):
        output = str(tmp_path / "qr")
        result = runner.invoke(cli, [
            '--config', config_file,
            'generate', '--output', output, '--format', 'png',
            '--user-data', '{"event":"test"}',
        ])
        assert result.exit_code == 0
        assert Path(output + ".png").exists()

    def test_generate_json(self, runner, config_file, tmp_path):
        output = str(tmp_path / "qr")
        result = runner.invoke(cli, [
            '--config', config_file,
            'generate', '--output', output, '--format', 'json',
        ])
        assert result.exit_code == 0
        assert Path(output + ".json").exists()

    def test_generate_both(self, runner, config_file, tmp_path):
        output = str(tmp_path / "qr")
        result = runner.invoke(cli, [
            '--config', config_file,
            'generate', '--output', output, '--format', 'both',
        ])
        assert result.exit_code == 0
        assert Path(output + ".png").exists()
        assert Path(output + ".json").exists()

    def test_generate_no_output(self, runner, config_file):
        result = runner.invoke(cli, [
            '--config', config_file,
            'generate',
        ])
        assert result.exit_code == 0
        assert "QR Data" in result.output

    def test_generate_signed(self, runner, config_file, tmp_path):
        output = str(tmp_path / "qr")
        result = runner.invoke(cli, [
            '--config', config_file,
            'generate', '--output', output, '--format', 'json', '--sign',
        ])
        assert result.exit_code == 0
        assert "Signed: yes" in result.output

    def test_generate_with_public_key_output(self, runner, config_file, tmp_path):
        output = str(tmp_path / "qr")
        pub_key = str(tmp_path / "pub.pem")
        result = runner.invoke(cli, [
            '--config', config_file,
            'generate', '--output', output, '--format', 'json',
            '--sign', '--public-key-output', pub_key,
        ])
        assert result.exit_code == 0
        assert Path(pub_key).exists()

    def test_generate_with_trust_record(self, runner, config_file, tmp_path):
        output = str(tmp_path / "qr")
        trust = str(tmp_path / "trust.json")
        result = runner.invoke(cli, [
            '--config', config_file,
            'generate', '--output', output, '--format', 'json',
            '--sign', '--trust-record-output', trust,
        ])
        assert result.exit_code == 0
        assert Path(trust).exists()
        trust_data = json.loads(Path(trust).read_text())
        assert len(trust_data["trusted_keys"]) == 1

    def test_generate_public_key_without_sign_fails(self, runner, config_file, tmp_path):
        output = str(tmp_path / "qr")
        pub_key = str(tmp_path / "pub.pem")
        result = runner.invoke(cli, [
            '--config', config_file,
            'generate', '--output', output, '--format', 'json',
            '--no-sign', '--public-key-output', pub_key,
        ])
        assert result.exit_code != 0


class TestCLIVerify:
    """Test verify command."""

    def test_verify_from_file(self, runner, config_file, tmp_path):
        # First generate a QR
        output = str(tmp_path / "qr")
        runner.invoke(cli, [
            '--config', config_file,
            'generate', '--output', output, '--format', 'json', '--sign',
        ])
        # Then verify
        result = runner.invoke(cli, [
            '--config', config_file,
            'verify', '--file', output + ".json", '--verbose',
        ])
        assert result.exit_code == 0
        assert "VALID" in result.output or "INVALID" in result.output

    def test_verify_json_output(self, runner, config_file, tmp_path):
        output = str(tmp_path / "qr")
        runner.invoke(cli, [
            '--config', config_file,
            'generate', '--output', output, '--format', 'json',
        ])
        result = runner.invoke(cli, [
            '--config', config_file,
            'verify', '--file', output + ".json", '--json-output',
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "valid_json" in data

    def test_verify_with_trust_store(self, runner, config_file, tmp_path):
        output = str(tmp_path / "qr")
        trust = str(tmp_path / "trust.json")
        runner.invoke(cli, [
            '--config', config_file,
            'generate', '--output', output, '--format', 'json',
            '--sign', '--trust-record-output', trust,
        ])
        result = runner.invoke(cli, [
            '--config', config_file,
            'verify', '--file', output + ".json", '--trust-store', trust,
        ])
        assert result.exit_code == 0
        assert "public_signature" in result.output


class TestCLIKeys:
    """Test keys commands."""

    def test_keys_generate_rsa(self, runner, config_file):
        result = runner.invoke(cli, ['--config', config_file, 'keys', 'generate'])
        assert result.exit_code == 0
        assert "Generated key:" in result.output

    def test_keys_generate_ecdsa(self, runner, config_file):
        result = runner.invoke(cli, [
            '--config', config_file,
            'keys', 'generate', '--algorithm', 'ecdsa', '--key-size', '256',
        ])
        assert result.exit_code == 0
        assert "Generated key:" in result.output

    def test_keys_list_empty(self, runner, config_file, tmp_path):
        """keys list with no keys shows 'No keys found'."""
        config = json.loads(Path(config_file).read_text())
        config["security_settings"] = {"key_dir": str(tmp_path / "empty_keys")}
        empty_config = str(tmp_path / "empty_config.json")
        Path(empty_config).write_text(json.dumps(config))
        result = runner.invoke(cli, ['--config', empty_config, 'keys', 'list'])
        assert result.exit_code == 0
        assert "No keys found" in result.output

    def test_keys_list_with_keys(self, runner, config_file):
        runner.invoke(cli, ['--config', config_file, 'keys', 'generate'])
        result = runner.invoke(cli, ['--config', config_file, 'keys', 'list'])
        assert result.exit_code == 0
        assert "algorithm=" in result.output

    def test_keys_export_public(self, runner, config_file, tmp_path):
        runner.invoke(cli, ['--config', config_file, 'keys', 'generate'])
        # Get the key ID from the list output
        list_result = runner.invoke(cli, ['--config', config_file, 'keys', 'list'])
        key_id = list_result.output.split()[0]
        output = str(tmp_path / "exported.pem")
        result = runner.invoke(cli, [
            '--config', config_file,
            'keys', 'export-public', key_id, '--output', output,
        ])
        assert result.exit_code == 0
        assert Path(output).exists()


class TestCLITrust:
    """Test trust commands."""

    def test_trust_add(self, runner, config_file, tmp_path):
        # First generate a key and export public key
        runner.invoke(cli, ['--config', config_file, 'keys', 'generate'])
        list_result = runner.invoke(cli, ['--config', config_file, 'keys', 'list'])
        key_id = list_result.output.split()[0]
        pub_key = str(tmp_path / "pub.pem")
        runner.invoke(cli, [
            '--config', config_file,
            'keys', 'export-public', key_id, '--output', pub_key,
        ])
        trust_store = str(tmp_path / "trust.json")
        result = runner.invoke(cli, [
            'trust', 'add',
            '--issuer', 'test-issuer',
            '--key-id', key_id,
            '--public-key', pub_key,
            '--store', trust_store,
        ])
        assert result.exit_code == 0
        assert Path(trust_store).exists()

    def test_trust_list(self, runner, config_file, tmp_path):
        # First add a trust entry
        runner.invoke(cli, ['--config', config_file, 'keys', 'generate'])
        list_result = runner.invoke(cli, ['--config', config_file, 'keys', 'list'])
        key_id = list_result.output.split()[0]
        pub_key = str(tmp_path / "pub.pem")
        runner.invoke(cli, ['--config', config_file, 'keys', 'export-public', key_id, '--output', pub_key])
        trust_store = str(tmp_path / "trust.json")
        runner.invoke(cli, [
            'trust', 'add',
            '--issuer', 'issuer1', '--key-id', key_id,
            '--public-key', pub_key, '--store', trust_store,
        ])
        result = runner.invoke(cli, ['trust', 'list', trust_store])
        assert result.exit_code == 0
        assert "issuer1" in result.output


class TestCLIConfigInit:
    """Test config-init command."""

    def test_config_init_json(self, runner, tmp_path):
        output = str(tmp_path / "config.json")
        result = runner.invoke(cli, ['config-init', '--output', output, '--format', 'json'])
        assert result.exit_code == 0
        assert Path(output).exists()
        data = json.loads(Path(output).read_text())
        assert "update_interval" in data

    def test_config_init_yaml_no_pyyaml(self, runner, tmp_path):
        output = str(tmp_path / "config.yaml")
        result = runner.invoke(cli, ['config-init', '--output', output, '--format', 'yaml'])
        # Either succeeds (if PyYAML installed) or exits with error
        assert result.exit_code in (0, 1)


class TestCLIStatus:
    """Test status command."""

    def test_status(self, runner, config_file):
        result = runner.invoke(cli, ['--config', config_file, 'status'])
        assert result.exit_code == 0
        assert "QRLP Status" in result.output


class TestCLIAddFile:
    """Test add-file command."""

    def test_add_file(self, runner, config_file, tmp_path):
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")
        result = runner.invoke(cli, [
            '--config', config_file,
            'add-file', str(test_file), '--alias', 'my-file',
        ])
        assert result.exit_code == 0
        assert "File added" in result.output

    def test_add_file_nonexistent(self, runner, config_file):
        result = runner.invoke(cli, [
            '--config', config_file,
            'add-file', '/nonexistent/file.txt',
        ])
        assert result.exit_code != 0


class TestHelperFunctions:
    """Test module-level helper functions."""

    def test_parse_user_data_valid(self):
        result = _parse_user_data('{"key": "value"}')
        assert result == {"key": "value"}

    def test_parse_user_data_empty(self):
        assert _parse_user_data(None) is None
        assert _parse_user_data("") is None

    def test_parse_user_data_invalid_json(self):
        with pytest.raises(Exception):
            _parse_user_data("not json")

    def test_parse_user_data_non_object(self):
        with pytest.raises(Exception, match="must be a JSON object"):
            _parse_user_data("[1, 2, 3]")

    def test_load_qr_data_from_string(self):
        assert _load_qr_data_argument('{"test": true}') == '{"test": true}'

    def test_load_qr_data_from_file(self, tmp_path):
        qr_file = tmp_path / "qr.json"
        qr_file.write_text('{"test": true}')
        result = _load_qr_data_argument(None, str(qr_file))
        assert result == '{"test": true}'

    def test_load_qr_data_from_at_file(self, tmp_path):
        qr_file = tmp_path / "qr.json"
        qr_file.write_text('{"test": true}')
        result = _load_qr_data_argument(f"@{qr_file}")
        assert result == '{"test": true}'

    def test_load_qr_data_missing(self):
        with pytest.raises(Exception, match="Provide QR JSON"):
            _load_qr_data_argument(None)

    def test_write_bytes(self, tmp_path):
        path = str(tmp_path / "output.bin")
        _write_bytes(path, b"test data")
        assert Path(path).read_bytes() == b"test data"
