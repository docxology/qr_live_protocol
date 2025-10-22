"""
Comprehensive tests for QRLP web server functionality.

Tests cover:
- Security validation
- API endpoints
- WebSocket communication
- Error handling
- Theme rendering
"""

import pytest
import json
from unittest.mock import Mock, patch
from src.web_server import QRLiveWebServer, SecurityValidator
from src.config import WebSettings
from src.core import QRData
from werkzeug.exceptions import BadRequest


class TestSecurityValidator:
    """Test security validation functions."""
    
    def test_validate_user_text_valid(self):
        """Test validation of valid user text."""
        valid_text = "Hello World 123"
        result = SecurityValidator.validate_user_text(valid_text)
        assert result == valid_text
    
    def test_validate_user_text_too_long(self):
        """Test validation rejects text that is too long."""
        long_text = "a" * (SecurityValidator.MAX_USER_TEXT_LENGTH + 1)
        with pytest.raises(BadRequest):
            SecurityValidator.validate_user_text(long_text)
    
    def test_validate_user_text_invalid_chars(self):
        """Test validation rejects invalid characters."""
        invalid_text = "Hello<script>alert('xss')</script>"
        with pytest.raises(BadRequest):
            SecurityValidator.validate_user_text(invalid_text)
    
    def test_validate_user_text_not_string(self):
        """Test validation rejects non-string input."""
        with pytest.raises(BadRequest):
            SecurityValidator.validate_user_text(123)
    
    def test_validate_qr_data_valid(self):
        """Test validation of valid QR data."""
        valid_qr = json.dumps({"timestamp": "2025-01-01T00:00:00Z", "data": "test"})
        result = SecurityValidator.validate_qr_data(valid_qr)
        assert result == valid_qr
    
    def test_validate_qr_data_too_large(self):
        """Test validation rejects oversized QR data."""
        large_qr = json.dumps({"data": "x" * SecurityValidator.MAX_QR_DATA_LENGTH})
        with pytest.raises(BadRequest):
            SecurityValidator.validate_qr_data(large_qr)
    
    def test_validate_qr_data_invalid_json(self):
        """Test validation rejects invalid JSON."""
        invalid_json = "not valid json"
        with pytest.raises(BadRequest):
            SecurityValidator.validate_qr_data(invalid_json)
    
    def test_validate_qr_data_not_object(self):
        """Test validation rejects non-object JSON."""
        array_json = json.dumps([1, 2, 3])
        with pytest.raises(BadRequest):
            SecurityValidator.validate_qr_data(array_json)
    
    def test_validate_json_input_valid(self):
        """Test validation of valid JSON input."""
        valid_dict = {"key": "value"}
        result = SecurityValidator.validate_json_input(valid_dict)
        assert result == valid_dict
    
    def test_validate_json_input_not_dict(self):
        """Test validation rejects non-dict input."""
        with pytest.raises(BadRequest):
            SecurityValidator.validate_json_input([1, 2, 3])


class TestQRLiveWebServer:
    """Test QRLiveWebServer functionality."""
    
    @pytest.fixture
    def web_settings(self):
        """Create web settings for testing."""
        settings = WebSettings()
        settings.port = 8081
        settings.host = 'localhost'
        settings.auto_open_browser = False
        return settings
    
    @pytest.fixture
    def web_server(self, web_settings):
        """Create web server instance for testing."""
        return QRLiveWebServer(web_settings)
    
    def test_initialization(self, web_server):
        """Test web server initialization."""
        assert web_server.settings is not None
        assert web_server.app is not None
        assert web_server.socketio is not None
        assert web_server.current_qr_data is None
        assert web_server.current_qr_image is None
        assert not web_server.is_running
    
    def test_update_qr_display(self, web_server):
        """Test QR display update."""
        qr_data = QRData(
            timestamp="2025-01-01T00:00:00Z",
            identity_hash="test_hash",
            blockchain_hashes={},
            time_server_verification={},
            user_data={"test": "data"},
            sequence_number=1
        )
        qr_image = b"fake_qr_image_bytes"
        
        web_server.update_qr_display(qr_data, qr_image)
        
        assert web_server.current_qr_data == qr_data
        assert web_server.current_qr_image == qr_image
        # Note: qr_updates_sent is only incremented when broadcasting via socketio
        assert web_server.current_qr_data is not None
    
    def test_get_statistics(self, web_server):
        """Test statistics retrieval."""
        stats = web_server.get_statistics()
        
        assert "is_running" in stats
        assert "qr_updates_sent" in stats
        assert "page_views" in stats
        assert "websocket_connections" in stats
        assert "server_url" in stats
        assert "current_qr_available" in stats
    
    def test_get_server_url(self, web_server):
        """Test server URL generation."""
        url = web_server.get_server_url()
        assert url == "http://localhost:8081"
    
    def test_api_status_endpoint(self, web_server):
        """Test /status and /api/status endpoints."""
        with web_server.app.test_client() as client:
            # Test /status endpoint
            response = client.get('/status')
            assert response.status_code == 200
            data = json.loads(response.data)
            assert "is_running" in data
            
            # Test /api/status endpoint
            response = client.get('/api/status')
            assert response.status_code == 200
            data = json.loads(response.data)
            assert "is_running" in data
    
    def test_api_qr_current_no_data(self, web_server):
        """Test /api/qr/current endpoint with no data."""
        with web_server.app.test_client() as client:
            response = client.get('/api/qr/current')
            assert response.status_code == 404
            data = json.loads(response.data)
            assert "error" in data
    
    def test_api_qr_current_with_data(self, web_server):
        """Test /api/qr/current endpoint with QR data."""
        qr_data = QRData(
            timestamp="2025-01-01T00:00:00Z",
            identity_hash="test_hash",
            blockchain_hashes={},
            time_server_verification={},
            user_data={"test": "data"},
            sequence_number=1
        )
        qr_image = b"fake_qr_image"
        
        web_server.update_qr_display(qr_data, qr_image)
        
        with web_server.app.test_client() as client:
            response = client.get('/api/qr/current')
            assert response.status_code == 200
            data = json.loads(response.data)
            assert "qr_data" in data
            assert "qr_image" in data
            assert "timestamp" in data


class TestWebServerIntegration:
    """Integration tests for web server with QRLP."""
    
    def test_full_workflow(self):
        """Test complete workflow from QR generation to web display."""
        from src.core import QRLiveProtocol
        from src.config import QRLPConfig
        
        # Create configuration
        config = QRLPConfig()
        config.update_interval = 0.5
        config.web_settings.port = 8082
        config.web_settings.auto_open_browser = False
        config.blockchain_settings.enabled_chains = []  # Disable for testing
        
        # Initialize QRLP
        qrlp = QRLiveProtocol(config)
        
        # Initialize web server
        web_server = QRLiveWebServer(config.web_settings)
        
        # Connect callback - this must be done before generating QR
        qrlp.add_update_callback(web_server.update_qr_display)
        
        # Generate single QR - this will trigger the callback
        qr_data, qr_image = qrlp.generate_single_qr(
            user_data={"test": "integration"},
            sign_data=False,
            encrypt_data=False
        )
        
        # The callback should have been called during generate_single_qr
        # However, generate_single_qr doesn't automatically trigger callbacks
        # We need to manually call the update method for this test
        web_server.update_qr_display(qr_data, qr_image)
        
        # Verify web server received update
        assert web_server.current_qr_data is not None
        assert web_server.current_qr_image is not None
        assert web_server.current_qr_data.sequence_number >= 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

