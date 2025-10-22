#!/usr/bin/env python3
"""
QRLP Livestream Demo

This example demonstrates how to use the QR Live Protocol for livestreaming
with real-time QR code generation, verification, and web display.

Run this script to start a full QRLP demo with custom configurations.
"""

import sys
import time
import json
import signal
import threading
from pathlib import Path
from datetime import datetime
import os

# Add project root to path for imports - ensure we're at the very front
project_root = Path(__file__).parent.parent
project_src = project_root / "src"

# Remove any existing entries first to avoid conflicts
sys_path_clean = [p for p in sys.path if not p.endswith('/src') or p == str(project_root)]
sys.path[:] = sys_path_clean

# Insert the project root at the very beginning
sys.path.insert(0, str(project_root))

# Use absolute imports to avoid conflicts with other src modules
import importlib.util
import types

# Import modules directly from the current project's src directory
def import_from_src(module_name):
    """Import a module from the current project's src directory."""
    module_path = project_src / f"{module_name}.py"
    if not module_path.exists():
        raise ImportError(f"Module {module_name} not found in {project_src}")
    
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

# Load the main src package
src_init_path = project_src / "__init__.py"
spec = importlib.util.spec_from_file_location("src", src_init_path)
src_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(src_module)

# Import required classes from the loaded module
QRLiveProtocol = src_module.QRLiveProtocol
QRLPConfig = src_module.QRLPConfig
QRLiveWebServer = src_module.QRLiveWebServer

# Import config module
config_module = import_from_src("config")


class QRLPDemo:
    """
    Complete QRLP demonstration for livestreaming scenarios.
    
    Shows how to:
    - Configure QRLP for optimal livestreaming
    - Start web server for browser display
    - Handle real-time QR updates
    - Integrate with streaming software
    """
    
    def __init__(self):
        self.qrlp = None
        self.web_server = None
        self.running = False
        self.stats = {
            'start_time': None,
            'total_qr_generated': 0,
            'verification_successes': 0,
            'last_qr_data': None
        }
        
        # Setup signal handlers for clean shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def setup_configuration(self) -> QRLPConfig:
        """Create optimized configuration for livestreaming."""
        config = QRLPConfig()
        
        # Optimize for livestreaming (faster updates, reliable verification)
        config.update_interval = 1.0  # Update every 1 second 
        
        # QR code settings optimized for streaming
        config.qr_settings.error_correction_level = "M"  # Medium error correction
        config.qr_settings.box_size = 12  # Larger for better visibility
        config.qr_settings.border_size = 6
        
        # Web server settings
        config.web_settings.host = "0.0.0.0"  # Allow external connections
        config.web_settings.port = 8080
        config.web_settings.auto_open_browser = True
        config.web_settings.cors_enabled = True
        
        # Time settings for accuracy
        config.time_settings.update_interval = 1.0
        config.time_settings.timeout = 3.0
        
        # Blockchain settings for verification
        config.blockchain_settings.enabled_chains = {"bitcoin", "ethereum"}
        config.blockchain_settings.cache_duration = 180  # 3 minutes
        config.blockchain_settings.timeout = 5.0
        
        # Identity settings
        config.identity_settings.auto_generate = True
        config.identity_settings.include_system_info = True
        config.identity_settings.hash_algorithm = "sha256"
        
        # Verification settings
        config.verification_settings.max_time_drift = 60.0  # 1 minute tolerance
        config.verification_settings.require_blockchain = False  # Optional but preferred
        config.verification_settings.require_time_server = False  # Fallback to local time
        
        return config
    
    def setup_identity_files(self):
        """Setup identity files for demonstration."""
        print("🆔 Setting up identity files...")
        
        # Create a demo identity file
        identity_data = {
            "demo_type": "livestream",
            "created_at": datetime.now().isoformat(),
            "purpose": "QR Live Protocol Demonstration",
            "streaming_session": f"demo_{int(time.time())}"
        }
        
        # Create output directory structure (use absolute path from project root)
        output_dir = Path(__file__).parent.parent / "output" / "examples" / "livestream_demo"
        output_dir.mkdir(parents=True, exist_ok=True)

        demo_file = output_dir / "demo_identity.json"
        with open(demo_file, 'w') as f:
            json.dump(identity_data, f, indent=2)
        
        # Add the demo file to identity
        self.qrlp.identity_manager.add_file_to_identity(str(demo_file), "demo_session")
        
        print(f"✓ Identity file created: {demo_file}")
        print(f"✓ Identity hash: {self.qrlp.identity_manager.get_identity_hash()[:32]}...")
    
    def setup_callbacks(self):
        """Setup callbacks for monitoring QR updates."""
        def qr_update_callback(qr_data, qr_image):
            """Handle each QR code update."""
            self.stats['total_qr_generated'] += 1
            self.stats['last_qr_data'] = qr_data
            
            # Verify the QR data we just generated
            verification = self.qrlp.verify_qr_data(qr_data.to_json())
            if verification.get('valid_json', False):
                self.stats['verification_successes'] += 1
            
            # Log update with user data info
            user_data_info = f"User: {qr_data.user_data['user_text'][:20]}..." if qr_data.user_data and qr_data.user_data.get('user_text') else "No user data"
            print(f"📱 QR #{qr_data.sequence_number} | "
                  f"{qr_data.timestamp[:19]} | "
                  f"Identity: {qr_data.identity_hash[:8]}... | "
                  f"Blockchain: {len(qr_data.blockchain_hashes)} chains | "
                  f"{user_data_info}")
        
        def web_server_callback(qr_data, qr_image):
            """Handle web server updates."""
            self.web_server.update_qr_display(qr_data, qr_image)
        
        # Add callbacks
        self.qrlp.add_update_callback(qr_update_callback)
        self.qrlp.add_update_callback(web_server_callback)
    
    def print_demo_info(self):
        """Print demonstration information and instructions."""
        config = self.qrlp.config
        
        print("\n" + "="*80)
        print("🔲 QR Live Protocol - Livestream Demo")
        print("="*80)
        print(f"🌐 Web Interface: http://localhost:{config.web_settings.port}")
        print(f"📺 Viewer URL: http://localhost:{config.web_settings.port}/viewer")
        print(f"⚙️  Admin Panel: http://localhost:{config.web_settings.port}/admin")
        print()
        print("📋 Configuration:")
        print(f"   Update Interval: {config.update_interval}s")
        print(f"   QR Error Correction: {config.qr_settings.error_correction_level}")
        print(f"   Blockchain Chains: {', '.join(config.blockchain_settings.enabled_chains)}")
        print(f"   Time Servers: {len(config.time_settings.time_servers)} configured")
        print()
        print("🎥 Streaming Integration:")
        print("   1. Open OBS Studio or your streaming software")
        print("   2. Add 'Browser Source'")
        print(f"   3. Set URL to: http://localhost:{config.web_settings.port}/viewer")
        print("   4. Set Width: 800, Height: 600 (or as needed)")
        print("   5. Check 'Shutdown source when not visible' for performance")
        print()
        print("🔍 Verification:")
        print("   - Scan QR codes with your phone to see encoded data")
        print("   - Use /api/verify endpoint to verify QR data programmatically")
        print("   - Check /api/status for real-time statistics")
        print()
        print("⏹️  Press Ctrl+C to stop the demo")
        print("="*80 + "\n")
    
    def print_statistics(self):
        """Print current statistics."""
        if not self.stats['start_time']:
            return
        
        runtime = time.time() - self.stats['start_time']
        qr_rate = self.stats['total_qr_generated'] / max(runtime, 1)
        success_rate = (self.stats['verification_successes'] / 
                       max(self.stats['total_qr_generated'], 1) * 100)
        
        print(f"\n📊 Demo Statistics (Runtime: {runtime:.1f}s)")
        print(f"   QR Codes Generated: {self.stats['total_qr_generated']}")
        print(f"   Generation Rate: {qr_rate:.2f} QR/sec")
        print(f"   Verification Success: {success_rate:.1f}%")
        
        if self.stats['last_qr_data']:
            last_qr = self.stats['last_qr_data']
            print(f"   Last QR Sequence: #{last_qr.sequence_number}")
            print(f"   Blockchain Verified: {len(last_qr.blockchain_hashes)} chains")
            print(f"   Time Server Verified: {len(last_qr.time_server_verification)} servers")
        
        # QRLP component statistics
        qrlp_stats = self.qrlp.get_statistics()
        print(f"   QRLP Updates: {qrlp_stats['total_updates']}")
        
        # Web server statistics
        if self.web_server:
            web_stats = self.web_server.get_statistics()
            print(f"   Web Page Views: {web_stats['page_views']}")
            print(f"   WebSocket Connections: {web_stats['websocket_connections']}")
            print(f"   QR Updates Sent: {web_stats['qr_updates_sent']}")
    
    def run_demo(self):
        """Run the complete QRLP demonstration."""
        print("🚀 Starting QR Live Protocol Demo...")
        
        try:
            # 1. Setup configuration
            print("⚙️  Creating optimized configuration...")
            config = self.setup_configuration()
            
            # 2. Initialize QRLP
            print("🔧 Initializing QR Live Protocol...")
            self.qrlp = QRLiveProtocol(config)
            
            # 3. Setup identity
            self.setup_identity_files()
            
            # 4. Initialize web server
            print("🌐 Starting web server...")
            self.web_server = QRLiveWebServer(config.web_settings)
            
            # 5. Setup callbacks
            self.setup_callbacks()
            
            # 6. Connect user data from web server to QR generation
            print("🔗 Connecting user input to QR generation...")
            self.qrlp.set_user_data_callback(lambda: self.web_server.get_user_data())
            
            # 7. Start services
            print("▶️  Starting live QR generation...")
            self.web_server.start_server(threaded=True)
            time.sleep(1)  # Let web server start
            
            self.qrlp.start_live_generation()
            
            # 8. Mark as running
            self.running = True
            self.stats['start_time'] = time.time()
            
            # 9. Print demo information
            self.print_demo_info()
            
            # 10. Main loop - print statistics periodically
            last_stats_time = 0
            while self.running:
                current_time = time.time()
                
                # Print statistics every 30 seconds
                if current_time - last_stats_time >= 30:
                    self.print_statistics()
                    last_stats_time = current_time
                
                time.sleep(1)
        
        except KeyboardInterrupt:
            print("\n🛑 Demo interrupted by user")
        except Exception as e:
            print(f"\n❌ Demo error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Clean up resources and print final statistics."""
        print("\n🧹 Cleaning up...")
        
        if self.qrlp:
            self.qrlp.stop_live_generation()
        
        if self.web_server:
            self.web_server.stop_server()
        
        # Print final statistics
        if self.stats['start_time']:
            self.print_statistics()
        
        # Clean up demo files
        demo_file = Path("demo_identity.json")
        if demo_file.exists():
            demo_file.unlink()
            print("🗑️  Cleaned up demo files")
        
        print("✅ Demo completed successfully!")
        self.running = False
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        print(f"\n📶 Received signal {signum}, shutting down...")
        self.running = False


def main():
    """Main function to run the demo."""
    demo = QRLPDemo()
    demo.run_demo()


if __name__ == "__main__":
    main() 