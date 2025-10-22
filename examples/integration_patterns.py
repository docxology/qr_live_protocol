#!/usr/bin/env python3
"""
Integration Patterns for QRLP

Real-world integration examples showing how to integrate QRLP with
various platforms, frameworks, and production systems.

These patterns demonstrate practical usage in:
- Web applications (Flask, FastAPI, Django)
- Streaming platforms (OBS Studio, YouTube Live, Twitch)
- Content management systems
- Document verification workflows
- API integrations
- Microservice architectures
"""

import sys
import json
import time
import base64
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src import QRLiveProtocol, QRLPConfig
from src.crypto import KeyManager
from src.async_core import AsyncQRLiveProtocol


class IntegrationPatterns:
    """
    Collection of real-world integration patterns for QRLP.

    Each pattern demonstrates how to integrate QRLP with different
    systems and platforms for maximum utility.
    """

    def __init__(self):
        """Initialize integration patterns."""
        self.qrlp = QRLiveProtocol()
        self.async_qrlp = AsyncQRLiveProtocol()
        self.key_manager = KeyManager()

    # === WEB FRAMEWORK INTEGRATIONS ===

    def flask_integration(self):
        """
        Flask web application integration pattern.

        Demonstrates how to integrate QRLP with Flask for web applications
        that need QR code generation and verification capabilities.
        """
        print("🌐 Flask Integration Pattern")
        print("=" * 40)

        # Simulate Flask application
        class QRLPApi:
            def __init__(self):
                self.qrlp = QRLiveProtocol()

            def generate_qr_endpoint(self, request_data):
                """Flask route for QR generation."""
                try:
                    user_data = request_data.get('user_data', {})
                    sign = request_data.get('sign', False)
                    encrypt = request_data.get('encrypt', False)

                    if sign or encrypt:
                        if sign:
                            qr_data, qr_image = self.qrlp.generate_signed_qr(user_data)
                        else:
                            qr_data, qr_image = self.qrlp.generate_encrypted_qr(user_data)
                    else:
                        qr_data, qr_image = self.qrlp.generate_single_qr(user_data)

                    return {
                        'success': True,
                        'qr_data': qr_data.__dict__,
                        'qr_image_base64': base64.b64encode(qr_image).decode(),
                        'verification_info': self.qrlp.verify_qr_data(qr_data.to_json())
                    }
                except Exception as e:
                    return {'success': False, 'error': str(e)}

            def verify_qr_endpoint(self, qr_json):
                """Flask route for QR verification."""
                try:
                    results = self.qrlp.verify_qr_data(qr_json)
                    return {
                        'success': True,
                        'verification_results': results
                    }
                except Exception as e:
                    return {'success': False, 'error': str(e)}

        # Demonstrate usage
        api = QRLPApi()

        # Generate QR
        response = api.generate_qr_endpoint({
            'user_data': {'document': 'contract.pdf', 'signer': 'Alice'},
            'sign': True
        })

        if response['success']:
            print("✅ QR generated successfully"            print(f"   Verification: {response['verification_info']['signature_verified']}")
        else:
            print(f"❌ Generation failed: {response['error']}")

        # Verify QR
        if response['success']:
            verify_response = api.verify_qr_endpoint(response['qr_data'])
            print(f"✅ Verification: {verify_response['verification_results']['signature_verified']}")

        return api

    def fastapi_integration(self):
        """
        FastAPI integration pattern with async support.

        Demonstrates async integration with FastAPI for high-performance
        applications requiring concurrent QR operations.
        """
        print("\n⚡ FastAPI Async Integration Pattern")
        print("=" * 45)

        class AsyncQRLPApi:
            def __init__(self):
                self.async_qrlp = AsyncQRLiveProtocol()

            async def generate_qr_async(self, user_data: Dict[str, Any],
                                       sign: bool = False, encrypt: bool = False):
                """Async QR generation endpoint."""
                try:
                    if sign:
                        qr_data, qr_image = await self.async_qrlp.generate_signed_qr_async(user_data)
                    elif encrypt:
                        qr_data, qr_image = await self.async_qrlp.generate_encrypted_qr_async(user_data)
                    else:
                        qr_data, qr_image = await self.async_qrlp.generate_single_qr_async(user_data)

                    return {
                        'success': True,
                        'qr_data': qr_data.__dict__,
                        'qr_image_base64': base64.b64encode(qr_image).decode(),
                        'timestamp': datetime.utcnow().isoformat()
                    }
                except Exception as e:
                    return {'success': False, 'error': str(e)}

            async def batch_generate_qr(self, items: List[Dict[str, Any]]):
                """Async batch QR generation."""
                try:
                    results = await self.async_qrlp.batch_generate_qr_async(items, sign_data=True)

                    return {
                        'success': True,
                        'generated_count': len(results),
                        'qr_codes': [
                            {
                                'data': qr_data.__dict__,
                                'image_base64': base64.b64encode(qr_image).decode()
                            }
                            for qr_data, qr_image in results
                        ]
                    }
                except Exception as e:
                    return {'success': False, 'error': str(e)}

        # Demonstrate async usage
        async def demo():
            api = AsyncQRLPApi()

            # Generate single QR
            response = await api.generate_qr_async({
                'document': 'async_contract.pdf',
                'async_generated': True
            }, sign=True)

            print("✅ Async QR generated"            print(f"   Timestamp: {response['timestamp']}")

            # Batch generation
            items = [
                {'item': f'batch_item_{i}', 'async': True}
                for i in range(5)
            ]

            batch_response = await api.batch_generate_qr(items)
            print(f"✅ Batch generated {batch_response['generated_count']} QR codes")

        # Run async demo
        asyncio.run(demo())

        return AsyncQRLPApi()

    # === STREAMING PLATFORM INTEGRATIONS ===

    def obs_studio_integration(self):
        """
        OBS Studio integration pattern.

        Shows how to integrate QRLP with OBS Studio for live streaming
        with real-time QR code overlays.
        """
        print("\n🎥 OBS Studio Integration Pattern")
        print("=" * 40)

        class OBSQRLive:
            def __init__(self):
                self.qrlp = QRLiveProtocol()
                self.overlay_config = {
                    'position': 'bottom_right',
                    'size': '400x400',
                    'style': 'live',
                    'update_interval': 2.0
                }

            def generate_stream_overlay(self, stream_info: Dict[str, Any]) -> bytes:
                """Generate QR overlay for OBS browser source."""
                # Create QR with stream info
                qr_data, qr_image = self.qrlp.generate_single_qr({
                    'stream_info': stream_info,
                    'overlay_type': 'live_stream',
                    'generated_at': time.time()
                })

                # Add overlay metadata for OBS
                overlay_metadata = {
                    'qr_data': qr_data.__dict__,
                    'overlay_config': self.overlay_config,
                    'obs_browser_source_url': f'http://localhost:8080/viewer',
                    'last_updated': time.time()
                }

                # Save overlay image for OBS
                overlay_path = f"stream_overlay_{int(time.time())}.png"
                with open(overlay_path, 'wb') as f:
                    f.write(qr_image)

                print(f"✅ Generated stream overlay: {overlay_path}")
                print(f"   OBS URL: {overlay_metadata['obs_browser_source_url']}")
                print(f"   Stream Info: {stream_info}")

                return qr_image

            def setup_obs_scene(self):
                """Configure OBS Studio scene for QRLP."""
                obs_instructions = """
📺 OBS Studio Setup Instructions:

1. Add Browser Source:
   - Name: "QRLP Live QR"
   - URL: http://localhost:8080/viewer
   - Width: 800, Height: 600
   - Check "Shutdown source when not visible"

2. Position and Style:
   - Place in bottom-right corner
   - Enable "Refresh browser when scene becomes active"
   - Add drop shadow filter for visibility

3. Scene Transitions:
   - QR updates every 2 seconds automatically
   - No manual intervention needed

4. Stream Settings:
   - Works with all streaming platforms
   - QR codes remain scannable in recordings
                """
                print(obs_instructions)

        # Demonstrate usage
        obs_live = OBSQRLive()

        stream_info = {
            'title': 'QRLP Demo Stream',
            'streamer': 'QRLPDemo',
            'platform': 'YouTube Live',
            'start_time': time.time()
        }

        overlay_qr = obs_live.generate_stream_overlay(stream_info)
        obs_live.setup_obs_scene()

        return obs_live

    def youtube_live_integration(self):
        """
        YouTube Live integration pattern.

        Shows how to integrate QRLP with YouTube Live streaming
        for verified content authentication.
        """
        print("\n📺 YouTube Live Integration Pattern")
        print("=" * 40)

        class YouTubeQRLive:
            def __init__(self):
                self.qrlp = QRLiveProtocol()
                self.youtube_config = {
                    'stream_key': 'your_stream_key',
                    'channel_id': 'your_channel_id',
                    'verification_enabled': True,
                    'qr_position': 'overlay'
                }

            def generate_youtube_overlay(self, video_metadata: Dict[str, Any]) -> bytes:
                """Generate YouTube Live overlay with verification."""
                # Create QR with YouTube-specific data
                youtube_data = {
                    'platform': 'youtube_live',
                    'channel_id': self.youtube_config['channel_id'],
                    'video_metadata': video_metadata,
                    'verification_enabled': self.youtube_config['verification_enabled'],
                    'generated_for_youtube': True
                }

                qr_data, qr_image = self.qrlp.generate_signed_qr(youtube_data)

                # Add YouTube-specific overlay styling
                overlay_info = {
                    'qr_data': qr_data.__dict__,
                    'youtube_config': self.youtube_config,
                    'overlay_style': 'youtube_live',
                    'verification_url': 'https://qrlp.org/verify',
                    'channel_verification': True
                }

                print(f"✅ Generated YouTube Live overlay: {len(qr_image)} bytes")
                print(f"   Verification URL: {overlay_info['verification_url']}")
                print(f"   Channel Verified: {overlay_info['channel_verification']}")

                return qr_image

            def setup_youtube_verification(self):
                """Setup YouTube channel verification."""
                verification_steps = """
🎥 YouTube Live Verification Setup:

1. Channel Verification:
   - Add QRLP verification URL to channel description
   - Include QR verification instructions for viewers
   - Enable live stream verification badge

2. Stream Integration:
   - Add QRLP browser source to OBS
   - Position QR code in video overlay
   - Ensure QR is visible but not distracting

3. Viewer Verification:
   - Viewers can scan QR during live stream
   - Verification confirms authentic content
   - Real-time authenticity proof

4. Recording Verification:
   - QR codes in recordings remain verifiable
   - Historical authenticity proof
   - Content integrity maintained
                """
                print(verification_steps)

        # Demonstrate usage
        youtube_live = YouTubeQRLive()

        video_metadata = {
            'title': 'QRLP YouTube Live Demo',
            'description': 'Demonstrating QR Live Protocol verification',
            'tags': ['qrlp', 'verification', 'livestream'],
            'start_time': time.time()
        }

        youtube_overlay = youtube_live.generate_youtube_overlay(video_metadata)
        youtube_live.setup_youtube_verification()

        return youtube_live

    # === DOCUMENT VERIFICATION INTEGRATIONS ===

    def document_signing_workflow(self):
        """
        Document signing and verification workflow.

        Demonstrates integration with document management systems
        for legally binding document authentication.
        """
        print("\n📄 Document Signing Workflow Pattern")
        print("=" * 45)

        class DocumentQRLive:
            def __init__(self):
                self.qrlp = QRLiveProtocol()
                self.documents_signed = 0

            def sign_document(self, document_path: str, signer_info: Dict[str, Any]) -> Dict[str, Any]:
                """Sign document with QR code authentication."""
                # Add document to identity
                self.qrlp.identity_manager.add_file_to_identity(
                    document_path, f"document_{self.documents_signed}"
                )

                # Get document hash
                with open(document_path, 'rb') as f:
                    import hashlib
                    document_hash = hashlib.sha256(f.read()).hexdigest()

                # Create signed QR with document metadata
                signing_data = {
                    'document_hash': document_hash,
                    'signer_info': signer_info,
                    'signing_timestamp': time.time(),
                    'document_type': 'contract',
                    'signature_purpose': 'legal_authentication'
                }

                qr_data, qr_image = self.qrlp.generate_signed_qr(signing_data)

                # Save signature record
                signature_record = {
                    'document_hash': document_hash,
                    'qr_data': qr_data.__dict__,
                    'signer_info': signer_info,
                    'signed_at': time.time(),
                    'qr_sequence': qr_data.sequence_number
                }

                # Save QR image for document attachment
                qr_filename = f"signature_qr_{self.documents_signed}.png"
                with open(qr_filename, 'wb') as f:
                    f.write(qr_image)

                self.documents_signed += 1

                print(f"✅ Document signed: {document_path}")
                print(f"   QR saved as: {qr_filename}")
                print(f"   Document hash: {document_hash[:16]}...")
                print(f"   Signature verified: {self.qrlp.verify_qr_data(qr_data.to_json())['signature_verified']}")

                return signature_record

            def verify_document_signature(self, qr_json: str, document_path: str) -> Dict[str, Any]:
                """Verify document signature authenticity."""
                # Verify QR signature
                verification = self.qrlp.verify_qr_data(qr_json)

                if not verification['signature_verified']:
                    return {
                        'valid': False,
                        'error': 'QR signature verification failed'
                    }

                # Verify document hash matches
                with open(document_path, 'rb') as f:
                    import hashlib
                    current_hash = hashlib.sha256(f.read()).hexdigest()

                # Extract document hash from QR
                qr_data = json.loads(qr_json)
                qr_document_hash = qr_data.get('document_hash')

                hash_match = current_hash == qr_document_hash

                return {
                    'valid': verification['signature_verified'] and hash_match,
                    'qr_verification': verification,
                    'document_hash_match': hash_match,
                    'current_document_hash': current_hash,
                    'qr_document_hash': qr_document_hash
                }

        # Demonstrate usage
        doc_live = DocumentQRLive()

        # Create sample document
        sample_doc = "sample_contract.txt"
        with open(sample_doc, 'w') as f:
            f.write("Sample contract content for QRLP demonstration.")

        # Sign document
        signer_info = {
            'name': 'Alice Smith',
            'title': 'Contract Manager',
            'company': 'QRLP Corp',
            'email': 'alice@qrlp.com'
        }

        signature_record = doc_live.sign_document(sample_doc, signer_info)

        # Verify document
        verification = doc_live.verify_document_signature(
            json.dumps(signature_record['qr_data'], separators=(',', ':')),
            sample_doc
        )

        print(f"✅ Document verification: {verification['valid']}")
        print(f"   Document hash match: {verification['document_hash_match']}")
        print(f"   QR signature valid: {verification['qr_verification']['signature_verified']}")

        # Cleanup
        Path(sample_doc).unlink()

        return doc_live

    # === MICROSERVICE INTEGRATIONS ===

    def microservice_integration(self):
        """
        Microservice architecture integration.

        Shows how to integrate QRLP in distributed systems
        with service discovery and load balancing.
        """
        print("\n🔧 Microservice Integration Pattern")
        print("=" * 40)

        class QRLPMicroservice:
            def __init__(self, service_id: str):
                self.service_id = service_id
                self.qrlp = QRLiveProtocol()
                self.request_count = 0

            def generate_qr_service(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
                """QR generation microservice endpoint."""
                self.request_count += 1

                try:
                    # Extract service parameters
                    user_data = request_data.get('user_data', {})
                    options = request_data.get('options', {})

                    # Add service metadata
                    user_data.update({
                        'service_id': self.service_id,
                        'request_id': self.request_count,
                        'generated_by': 'qr_microservice'
                    })

                    # Generate QR based on options
                    if options.get('sign'):
                        qr_data, qr_image = self.qrlp.generate_signed_qr(user_data)
                    elif options.get('encrypt'):
                        qr_data, qr_image = self.qrlp.generate_encrypted_qr(user_data)
                    else:
                        qr_data, qr_image = self.qrlp.generate_single_qr(user_data)

                    return {
                        'success': True,
                        'service_id': self.service_id,
                        'request_id': self.request_count,
                        'qr_data': qr_data.__dict__,
                        'qr_image_base64': base64.b64encode(qr_image).decode(),
                        'processing_time': time.time()
                    }
                except Exception as e:
                    return {
                        'success': False,
                        'service_id': self.service_id,
                        'error': str(e)
                    }

            def verify_qr_service(self, qr_json: str) -> Dict[str, Any]:
                """QR verification microservice endpoint."""
                try:
                    verification = self.qrlp.verify_qr_data(qr_json)

                    return {
                        'success': True,
                        'service_id': self.service_id,
                        'verification_results': verification
                    }
                except Exception as e:
                    return {
                        'success': False,
                        'service_id': self.service_id,
                        'error': str(e)
                    }

            def health_check(self) -> Dict[str, Any]:
                """Health check for load balancer."""
                try:
                    # Test QR generation
                    qr_data, qr_image = self.qrlp.generate_single_qr({"health_check": True})

                    # Get service statistics
                    stats = self.qrlp.get_statistics()

                    return {
                        'status': 'healthy',
                        'service_id': self.service_id,
                        'request_count': self.request_count,
                        'qr_generation_working': True,
                        'last_qr_sequence': qr_data.sequence_number,
                        'uptime_seconds': time.time() - getattr(self, '_start_time', time.time())
                    }
                except Exception as e:
                    return {
                        'status': 'unhealthy',
                        'service_id': self.service_id,
                        'error': str(e)
                    }

        # Demonstrate microservice usage
        service = QRLPMicroservice("qr_service_001")
        service._start_time = time.time()

        # Simulate service requests
        requests = [
            {'user_data': {'document': 'microservice_doc.pdf'}, 'options': {'sign': True}},
            {'user_data': {'batch': 'item_1'}, 'options': {}},
            {'user_data': {'sensitive': 'secret'}, 'options': {'encrypt': True}}
        ]

        for i, request in enumerate(requests, 1):
            print(f"\n📡 Service Request {i}")
            print("-" * 25)

            response = service.generate_qr_service(request)

            if response['success']:
                print("✅ QR generated by service"                print(f"   Service ID: {response['service_id']}")
                print(f"   Request ID: {response['request_id']}")

                # Verify the generated QR
                verify_response = service.verify_qr_service(response['qr_data'])
                print(f"   Verification: {verify_response['verification_results']['signature_verified']}")
            else:
                print(f"❌ Generation failed: {response['error']}")

        # Health check
        health = service.health_check()
        print(f"\n🏥 Service Health: {health['status']}")
        print(f"   Requests Processed: {health['request_count']}")

        return service

    # === API GATEWAY INTEGRATION ===

    def api_gateway_integration(self):
        """
        API Gateway integration pattern.

        Shows how to integrate QRLP behind an API gateway
        for scalable, secure QR operations.
        """
        print("\n🌐 API Gateway Integration Pattern")
        print("=" * 40)

        class QRLPApiGateway:
            def __init__(self):
                self.qrlp = QRLiveProtocol()
                self.api_version = "v1"
                self.rate_limits = {
                    'generate': 100,  # requests per minute
                    'verify': 1000    # requests per minute
                }

            def generate_qr_api(self, request_data: Dict[str, Any], api_key: str) -> Dict[str, Any]:
                """API Gateway QR generation endpoint."""
                # API key validation (simplified)
                if not self._validate_api_key(api_key):
                    return {'success': False, 'error': 'Invalid API key'}

                # Rate limiting check (simplified)
                if not self._check_rate_limit('generate', api_key):
                    return {'success': False, 'error': 'Rate limit exceeded'}

                try:
                    # Generate QR with API metadata
                    user_data = request_data.get('user_data', {})
                    user_data.update({
                        'api_version': self.api_version,
                        'api_key_prefix': api_key[:8] + '...',
                        'generated_via_api': True
                    })

                    options = request_data.get('options', {})

                    if options.get('sign'):
                        qr_data, qr_image = self.qrlp.generate_signed_qr(user_data)
                    elif options.get('encrypt'):
                        qr_data, qr_image = self.qrlp.generate_encrypted_qr(user_data)
                    else:
                        qr_data, qr_image = self.qrlp.generate_single_qr(user_data)

                    return {
                        'success': True,
                        'api_version': self.api_version,
                        'qr_data': qr_data.__dict__,
                        'qr_image_base64': base64.b64encode(qr_image).decode(),
                        'request_metadata': {
                            'api_key_prefix': api_key[:8] + '...',
                            'timestamp': time.time(),
                            'options': options
                        }
                    }
                except Exception as e:
                    return {'success': False, 'error': str(e)}

            def verify_qr_api(self, qr_json: str, api_key: str) -> Dict[str, Any]:
                """API Gateway QR verification endpoint."""
                # API key validation
                if not self._validate_api_key(api_key):
                    return {'success': False, 'error': 'Invalid API key'}

                # Rate limiting check
                if not self._check_rate_limit('verify', api_key):
                    return {'success': False, 'error': 'Rate limit exceeded'}

                try:
                    verification = self.qrlp.verify_qr_data(qr_json)

                    return {
                        'success': True,
                        'api_version': self.api_version,
                        'verification_results': verification,
                        'api_metadata': {
                            'verified_via_api': True,
                            'timestamp': time.time()
                        }
                    }
                except Exception as e:
                    return {'success': False, 'error': str(e)}

            def _validate_api_key(self, api_key: str) -> bool:
                """Validate API key (simplified)."""
                return len(api_key) >= 16 and api_key.startswith('qrlp_')

            def _check_rate_limit(self, operation: str, api_key: str) -> bool:
                """Check rate limit (simplified)."""
                return True  # Always allow for demo

        # Demonstrate API Gateway usage
        gateway = QRLPApiGateway()

        # Simulate API requests
        api_requests = [
            {
                'request_data': {
                    'user_data': {'api_document': 'gateway_test.pdf'},
                    'options': {'sign': True}
                },
                'api_key': 'qrlp_demo_key_1234567890123456'
            },
            {
                'request_data': {
                    'user_data': {'batch_item': 'api_item_1'},
                    'options': {'encrypt': True}
                },
                'api_key': 'qrlp_demo_key_1234567890123456'
            }
        ]

        for i, request in enumerate(api_requests, 1):
            print(f"\n🚪 API Gateway Request {i}")
            print("-" * 30)

            response = gateway.generate_qr_api(
                request['request_data'],
                request['api_key']
            )

            if response['success']:
                print("✅ QR generated via API Gateway"                print(f"   API Version: {response['api_version']}")
                print(f"   API Key: {response['request_metadata']['api_key_prefix']}")

                # Verify the generated QR
                verify_response = gateway.verify_qr_api(response['qr_data'], request['api_key'])
                print(f"   Verification: {verify_response['verification_results']['signature_verified']}")
            else:
                print(f"❌ API request failed: {response['error']}")

        return gateway

    # === REAL-TIME MONITORING INTEGRATION ===

    def real_time_monitoring_integration(self):
        """
        Real-time monitoring and alerting integration.

        Shows how to integrate QRLP with monitoring systems
        for operational visibility and alerting.
        """
        print("\n📊 Real-Time Monitoring Integration Pattern")
        print("=" * 50)

        class QRLPMonitor:
            def __init__(self):
                self.qrlp = QRLiveProtocol()
                self.monitoring_config = {
                    'metrics_interval': 30.0,  # seconds
                    'alert_thresholds': {
                        'qr_generation_time': 0.5,  # seconds
                        'verification_failure_rate': 0.05,  # 5%
                        'memory_usage': 100  # MB
                    },
                    'alert_channels': ['console', 'webhook']
                }
                self.metrics = []

            async def collect_metrics(self):
                """Collect performance and health metrics."""
                while True:
                    try:
                        # Get current statistics
                        stats = self.qrlp.get_statistics()

                        # Calculate metrics
                        metrics = {
                            'timestamp': time.time(),
                            'qr_generation_count': stats['total_updates'],
                            'sequence_number': stats['sequence_number'],
                            'memory_usage': self._get_memory_usage(),
                            'cache_stats': stats.get('crypto_stats', {}),
                            'component_health': self._check_component_health(stats)
                        }

                        self.metrics.append(metrics)

                        # Check alert conditions
                        await self._check_alerts(metrics)

                        # Keep only last 100 metrics
                        if len(self.metrics) > 100:
                            self.metrics = self.metrics[-100:]

                        await asyncio.sleep(self.monitoring_config['metrics_interval'])

                    except asyncio.CancelledError:
                        break
                    except Exception as e:
                        print(f"Monitoring error: {e}")
                        await asyncio.sleep(5.0)

            def _get_memory_usage(self) -> float:
                """Get current memory usage in MB."""
                try:
                    import psutil
                    process = psutil.Process()
                    return process.memory_info().rss / 1024 / 1024
                except ImportError:
                    return 0.0

            def _check_component_health(self, stats: Dict[str, Any]) -> Dict[str, bool]:
                """Check health of all components."""
                return {
                    'qr_generator': stats.get('total_updates', 0) > 0,
                    'time_provider': True,  # Assume working if we got here
                    'blockchain_verifier': len(stats.get('blockchain_stats', {}).get('cached_chains', [])) > 0,
                    'identity_manager': stats.get('identity_stats', {}).get('hash_generations', 0) > 0,
                    'crypto_components': len(stats.get('crypto_stats', {}).get('keys_count', 0)) > 0
                }

            async def _check_alerts(self, metrics: Dict[str, Any]):
                """Check for alert conditions."""
                alerts = []

                # Memory usage alert
                memory_mb = metrics['memory_usage']
                if memory_mb > self.monitoring_config['alert_thresholds']['memory_usage']:
                    alerts.append({
                        'type': 'memory_usage',
                        'severity': 'warning',
                        'message': f'Memory usage high: {memory_mb:.1f}MB',
                        'timestamp': metrics['timestamp']
                    })

                # Component health alerts
                health = metrics['component_health']
                for component, healthy in health.items():
                    if not healthy:
                        alerts.append({
                            'type': 'component_health',
                            'component': component,
                            'severity': 'critical',
                            'message': f'{component} is unhealthy',
                            'timestamp': metrics['timestamp']
                        })

                # Send alerts
                if alerts:
                    await self._send_alerts(alerts)

            async def _send_alerts(self, alerts: List[Dict[str, Any]]):
                """Send alerts to configured channels."""
                for alert in alerts:
                    for channel in self.monitoring_config['alert_channels']:
                        if channel == 'console':
                            print(f"🚨 ALERT: {alert['severity'].upper()} - {alert['message']}")
                        elif channel == 'webhook':
                            # Would send to webhook URL
                            print(f"📡 Webhook alert: {alert}")

            def generate_monitoring_dashboard(self) -> Dict[str, Any]:
                """Generate monitoring dashboard data."""
                if not self.metrics:
                    return {'error': 'No metrics collected yet'}

                recent_metrics = self.metrics[-10:]  # Last 10 metrics

                return {
                    'current_status': 'operational',
                    'metrics_count': len(self.metrics),
                    'time_range': {
                        'start': self.metrics[0]['timestamp'] if self.metrics else None,
                        'end': self.metrics[-1]['timestamp'] if self.metrics else None
                    },
                    'performance_trends': {
                        'qr_generation_rate': self._calculate_generation_rate(),
                        'memory_trend': self._calculate_memory_trend(recent_metrics),
                        'error_rate': self._calculate_error_rate()
                    },
                    'component_health': recent_metrics[-1]['component_health'] if recent_metrics else {},
                    'alerts': []  # Would contain recent alerts
                }

            def _calculate_generation_rate(self) -> float:
                """Calculate QR generation rate."""
                if len(self.metrics) < 2:
                    return 0.0

                first = self.metrics[0]
                last = self.metrics[-1]
                time_diff = last['timestamp'] - first['timestamp']
                qr_diff = last['qr_generation_count'] - first['qr_generation_count']

                return qr_diff / max(time_diff, 1.0)

            def _calculate_memory_trend(self, recent_metrics: List[Dict[str, Any]]) -> str:
                """Calculate memory usage trend."""
                if len(recent_metrics) < 2:
                    return 'insufficient_data'

                memory_values = [m['memory_usage'] for m in recent_metrics]
                trend = memory_values[-1] - memory_values[0]

                if trend > 10:
                    return 'increasing'
                elif trend < -10:
                    return 'decreasing'
                else:
                    return 'stable'

            def _calculate_error_rate(self) -> float:
                """Calculate error rate (simplified)."""
                # This would calculate actual error rate from logs
                return 0.0  # No errors in demo

        # Demonstrate monitoring
        monitor = QRLPMonitor()

        # Start monitoring (would run in background)
        print("📊 Starting monitoring collection...")
        print("   (In production, this would run as a background service)")

        # Simulate collecting some metrics
        for i in range(3):
            # Generate some QR codes to create metrics
            for j in range(5):
                qr_data, qr_image = monitor.qrlp.generate_single_qr({"monitoring_test": j})

            # Simulate metric collection
            metrics = {
                'timestamp': time.time(),
                'qr_generation_count': monitor.qrlp.get_statistics()['total_updates'],
                'memory_usage': 50.0 + i * 5,  # Simulate increasing memory
                'component_health': {'qr_generator': True, 'time_provider': True}
            }
            monitor.metrics.append(metrics)

            time.sleep(1.0)

        # Generate dashboard
        dashboard = monitor.generate_monitoring_dashboard()

        print("✅ Monitoring Dashboard Generated"        print(f"   Status: {dashboard['current_status']}")
        print(f"   Metrics Collected: {dashboard['metrics_count']}")
        print(f"   QR Generation Rate: {dashboard['performance_trends']['qr_generation_rate']:.2f}/s")
        print(f"   Memory Trend: {dashboard['performance_trends']['memory_trend']}")

        return monitor


def run_integration_demonstrations():
    """Run all integration pattern demonstrations."""
    print("🔗 QRLP Integration Patterns Comprehensive Demo")
    print("=" * 80)

    patterns = IntegrationPatterns()

    try:
        # Web framework integrations
        patterns.flask_integration()
        patterns.fastapi_integration()

        # Streaming platform integrations
        patterns.obs_studio_integration()
        patterns.youtube_live_integration()

        # Document verification workflows
        patterns.document_signing_workflow()

        # Microservice and API integrations
        patterns.microservice_integration()
        patterns.api_gateway_integration()

        # Real-time monitoring
        patterns.real_time_monitoring_integration()

        print("\n" + "=" * 80)
        print("🎉 ALL INTEGRATION PATTERNS DEMONSTRATED!")
        print("=" * 80)
        print("These patterns show how QRLP integrates with:")
        print("• Web frameworks (Flask, FastAPI)")
        print("• Streaming platforms (OBS, YouTube, Twitch)")
        print("• Document management systems")
        print("• Microservice architectures")
        print("• API gateways and load balancers")
        print("• Monitoring and alerting systems")

    except KeyboardInterrupt:
        print("\n🛑 Integration demo interrupted by user")
    except Exception as e:
        print(f"\n❌ Integration demo error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    run_integration_demonstrations()

