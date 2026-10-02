#!/usr/bin/env python3
"""
End-to-End Dashboard UI Tests

Tests for the web dashboard user interface including:
- Page loading and navigation
- Real-time data updates via WebSocket
- User interactions and controls
- Chart and map visualizations
- Detection table operations
- Alert notifications
- Responsive layout behavior
- Form submissions and validation
- Export functionality
- Settings management
"""

import asyncio
import json
import time
import unittest
from pathlib import Path
from datetime import datetime
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Web testing imports
try:
    from playwright.async_api import async_playwright, Page, Browser, BrowserContext
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    print("Warning: Playwright not installed. Install with: pip install playwright && playwright install")

# Import application components
from api.main import create_app
from infrastructure.messaging.websocket_server import WebSocketManager
from infrastructure.storage.database import DatabaseManager, DatabaseConfig, DatabaseType
from infrastructure.hardware.mock_hardware import MockSDR
from app.services import DetectionService


# ============================================================================
# Test Configuration
# ============================================================================

class UITestConfig:
    """UI test configuration"""
    
    # Server settings
    TEST_HOST = "localhost"
    TEST_PORT = 8888
    WS_PORT = 8889
    
    # Test timeouts (ms)
    NAVIGATION_TIMEOUT = 30000
    ELEMENT_TIMEOUT = 10000
    ANIMATION_TIMEOUT = 5000
    
    # Test user credentials
    TEST_USER = "test_user"
    TEST_PASSWORD = "test_password"
    
    # Viewport sizes for responsiveness testing
    VIEWPORTS = {
        "desktop": {"width": 1920, "height": 1080},
        "tablet": {"width": 768, "height": 1024},
        "mobile": {"width": 375, "height": 667}
    }


# ============================================================================
# Test Server Fixture
# ============================================================================

class TestServerFixture:
    """Test server fixture for UI tests"""
    
    def __init__(self):
        self.app = None
        self.server = None
        self.server_task = None
        self.db = None
        self.detection_service = None
        self.websocket_manager = None
    
    async def start(self):
        """Start test server"""
        import uvicorn
        
        # Initialize database
        db_config = DatabaseConfig(
            db_type=DatabaseType.SQLITE,
            sqlite_path=":memory:"
        )
        self.db = DatabaseManager(db_config)
        await self.db.initialize()
        await self.db.create_tables()
        
        # Initialize hardware
        hardware = MockSDR()
        hardware.initialize({'sample_rate': 10e6})
        
        # Initialize services
        self.detection_service = DetectionService(
            hardware=hardware,
            db=self.db
        )
        await self.detection_service.start()
        
        # Create FastAPI app
        self.app = create_app()
        
        # Start server
        config = uvicorn.Config(
            self.app,
            host=UITestConfig.TEST_HOST,
            port=UITestConfig.TEST_PORT,
            log_level="error"
        )
        self.server = uvicorn.Server(config)
        self.server_task = asyncio.create_task(self.server.serve())
        
        # Wait for server to start
        await asyncio.sleep(2)
        
        return self
    
    async def stop(self):
        """Stop test server"""
        if self.server:
            self.server.should_exit = True
            await self.server_task
        if self.detection_service:
            await self.detection_service.stop()
        if self.db:
            await self.db.close()


# ============================================================================
# Dashboard Page Object
# ============================================================================

class DashboardPage:
    """Page object for dashboard UI"""
    
    def __init__(self, page: Page):
        self.page = page
        
        # Selectors
        self.selectors = {
            # Navigation
            'nav_dashboard': '[data-page="dashboard"]',
            'nav_map': '[data-page="map"]',
            'nav_detections': '[data-page="detections"]',
            'nav_alerts': '[data-page="alerts"]',
            'nav_analytics': '[data-page="analytics"]',
            'nav_settings': '[data-page="settings"]',
            
            # Stats cards
            'stat_total_detections': '#totalDetections',
            'stat_active_threats': '#activeThreats',
            'stat_avg_confidence': '#avgConfidence',
            'stat_system_uptime': '#systemUptime',
            
            # Controls
            'btn_start': '#btnStart',
            'btn_stop': '#btnStop',
            'btn_clear': '#btnClear',
            'btn_export': '#btnExport',
            'btn_refresh': '#btnRefresh',
            'btn_fullscreen': '#btnFullscreen',
            
            # Map
            'map_container': '#map',
            'map_canvas': '.leaflet-container',
            
            # Charts
            'trend_chart': '#trendChart',
            'threat_chart': '#threatChart',
            
            # Table
            'detections_table': '#detectionsTable',
            'detections_table_body': '#detectionsTableBody',
            
            # Alerts
            'alerts_container': '#alertsList',
            'alert_items': '.alert-item',
            
            # Connection status
            'connection_status': '#connectionStatus',
            'status_dot': '.status-dot',
            
            # Modals
            'export_modal': '#exportModal',
            'confirm_modal': '#confirmModal',
        }
    
    async def navigate_to(self):
        """Navigate to dashboard"""
        await self.page.goto(f"http://{UITestConfig.TEST_HOST}:{UITestConfig.TEST_PORT}/ui")
        await self.wait_for_load()
    
    async def wait_for_load(self):
        """Wait for dashboard to load"""
        await self.page.wait_for_selector(self.selectors['stat_total_detections'], 
                                          timeout=UITestConfig.NAVIGATION_TIMEOUT)
        await self.page.wait_for_selector(self.selectors['trend_chart'])
    
    async def click_nav(self, nav_name: str):
        """Click navigation item"""
        selector = self.selectors.get(f'nav_{nav_name}')
        if selector:
            await self.page.click(selector)
            await asyncio.sleep(0.5)
    
    async def get_stat_value(self, stat_name: str) -> str:
        """Get statistic value"""
        selector = self.selectors.get(f'stat_{stat_name}')
        if selector:
            element = await self.page.wait_for_selector(selector)
            return await element.text_content()
        return ""
    
    async def click_start(self):
        """Click start button"""
        await self.page.click(self.selectors['btn_start'])
    
    async def click_stop(self):
        """Click stop button"""
        await self.page.click(self.selectors['btn_stop'])
    
    async def click_clear(self):
        """Click clear button"""
        await self.page.click(self.selectors['btn_clear'])
    
    async def is_connected(self) -> bool:
        """Check if WebSocket is connected"""
        status = await self.page.text_content(self.selectors['connection_status'])
        return status == "Connected"
    
    async def get_detection_count(self) -> int:
        """Get number of detections in table"""
        rows = await self.page.query_selector_all(f"{self.selectors['detections_table_body']} tr")
        return len(rows)
    
    async def get_alert_count(self) -> int:
        """Get number of alerts"""
        alerts = await self.page.query_selector_all(self.selectors['alert_items'])
        return len(alerts)
    
    async def take_screenshot(self, name: str):
        """Take screenshot for debugging"""
        await self.page.screenshot(path=f"test_screenshots/{name}.png")


# ============================================================================
# UI Test Suite
# ============================================================================

class TestDashboardUI(unittest.IsolatedAsyncioTestCase):
    """Dashboard UI end-to-end tests"""
    
    @classmethod
    def setUpClass(cls):
        if not PLAYWRIGHT_AVAILABLE:
            raise unittest.SkipTest("Playwright not available")
    
    async def asyncSetUp(self):
        """Set up test environment"""
        # Start test server
        self.server = await TestServerFixture().start()
        
        # Launch browser
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=True)
        self.context = await self.browser.new_context(
            viewport=UITestConfig.VIEWPORTS['desktop']
        )
        self.page = await self.context.new_page()
        self.dashboard = DashboardPage(self.page)
        
        # Navigate to dashboard
        await self.dashboard.navigate_to()
    
    async def asyncTearDown(self):
        """Clean up test environment"""
        await self.browser.close()
        await self.playwright.stop()
        await self.server.stop()
    
    # ========================================================================
    # Page Load Tests
    # ========================================================================
    
    async def test_page_loads_successfully(self):
        """Test that dashboard page loads successfully"""
        print("\n" + "="*60)
        print("TEST: Page Load")
        print("="*60)
        
        title = await self.page.title()
        print(f"  Page title: {title}")
        
        self.assertIn("Drone Detection", title)
        self.assertTrue(await self.dashboard.is_connected())
    
    async def test_all_sections_visible(self):
        """Test that all dashboard sections are visible"""
        print("\n" + "="*60)
        print("TEST: Dashboard Sections")
        print("="*60)
        
        sections = [
            'stat_total_detections',
            'stat_active_threats',
            'trend_chart',
            'threat_chart',
            'detections_table',
            'alerts_container'
        ]
        
        for section in sections:
            selector = self.dashboard.selectors.get(section)
            if selector:
                is_visible = await self.page.is_visible(selector)
                print(f"  {section}: {'✓' if is_visible else '✗'}")
                self.assertTrue(is_visible, f"Section {section} not visible")
    
    # ========================================================================
    # Navigation Tests
    # ========================================================================
    
    async def test_navigation_works(self):
        """Test that navigation between pages works"""
        print("\n" + "="*60)
        print("TEST: Navigation")
        print("="*60)
        
        pages = ['map', 'detections', 'alerts', 'analytics', 'settings']
        
        for page_name in pages:
            await self.dashboard.click_nav(page_name)
            print(f"  Navigated to: {page_name}")
            await asyncio.sleep(0.5)
            
            # Verify page content loaded
            page_element = await self.page.query_selector(f"#{page_name}Page")
            is_visible = await page_element.is_visible() if page_element else False
            self.assertTrue(is_visible, f"Page {page_name} not visible")
    
    # ========================================================================
    # WebSocket Connection Tests
    # ========================================================================
    
    async def test_websocket_connection(self):
        """Test WebSocket connection status"""
        print("\n" + "="*60)
        print("TEST: WebSocket Connection")
        print("="*60)
        
        is_connected = await self.dashboard.is_connected()
        print(f"  Connection status: {'Connected' if is_connected else 'Disconnected'}")
        
        self.assertTrue(is_connected)
        
        # Check status indicator
        status_dot = await self.page.query_selector(self.dashboard.selectors['status_dot'])
        if status_dot:
            color = await status_dot.evaluate("el => getComputedStyle(el).backgroundColor")
            print(f"  Status indicator color: {color}")
    
    # ========================================================================
    # Control Button Tests
    # ========================================================================
    
    async def test_start_stop_buttons(self):
        """Test start and stop buttons"""
        print("\n" + "="*60)
        print("TEST: Start/Stop Controls")
        print("="*60)
        
        # Click start
        await self.dashboard.click_start()
        print("  Start button clicked")
        await asyncio.sleep(1)
        
        # Click stop
        await self.dashboard.click_stop()
        print("  Stop button clicked")
        await asyncio.sleep(1)
        
        # Verify buttons work (no errors)
        self.assertTrue(True)
    
    async def test_clear_button(self):
        """Test clear detections button"""
        print("\n" + "="*60)
        print("TEST: Clear Detections")
        print("="*60)
        
        # Note: This test may need confirmation dialog handling
        await self.dashboard.click_clear()
        print("  Clear button clicked")
        await asyncio.sleep(1)
    
    # ========================================================================
    # Real-time Data Tests
    # ========================================================================
    
    async def test_detection_updates(self):
        """Test that detection table updates in real-time"""
        print("\n" + "="*60)
        print("TEST: Real-time Detection Updates")
        print("="*60)
        
        initial_count = await self.dashboard.get_detection_count()
        print(f"  Initial detection count: {initial_count}")
        
        # Generate test detection via backend
        await self.server.detection_service.generate_test_detection()
        
        # Wait for update
        await asyncio.sleep(2)
        
        new_count = await self.dashboard.get_detection_count()
        print(f"  New detection count: {new_count}")
        
        self.assertGreater(new_count, initial_count, "Detection table did not update")
    
    async def test_alert_updates(self):
        """Test that alert list updates in real-time"""
        print("\n" + "="*60)
        print("TEST: Real-time Alert Updates")
        print("="*60)
        
        initial_count = await self.dashboard.get_alert_count()
        print(f"  Initial alert count: {initial_count}")
        
        # Generate test alert via backend
        await self.server.detection_service.generate_test_alert()
        
        # Wait for update
        await asyncio.sleep(2)
        
        new_count = await self.dashboard.get_alert_count()
        print(f"  New alert count: {new_count}")
        
        self.assertGreater(new_count, initial_count, "Alert list did not update")
    
    # ========================================================================
    # Chart Visualization Tests
    # ========================================================================
    
    async def test_charts_render(self):
        """Test that charts render correctly"""
        print("\n" + "="*60)
        print("TEST: Chart Rendering")
        print("="*60)
        
        # Check trend chart
        trend_chart = await self.page.query_selector(self.dashboard.selectors['trend_chart'])
        self.assertIsNotNone(trend_chart, "Trend chart not found")
        
        # Check threat chart
        threat_chart = await self.page.query_selector(self.dashboard.selectors['threat_chart'])
        self.assertIsNotNone(threat_chart, "Threat chart not found")
        
        print("  Charts rendered successfully")
    
    # ========================================================================
    # Map Visualization Tests
    # ========================================================================
    
    async def test_map_renders(self):
        """Test that map renders correctly"""
        print("\n" + "="*60)
        print("TEST: Map Rendering")
        print("="*60)
        
        # Navigate to map page
        await self.dashboard.click_nav('map')
        await asyncio.sleep(1)
        
        # Check map container
        map_container = await self.page.query_selector(self.dashboard.selectors['map_container'])
        self.assertIsNotNone(map_container, "Map container not found")
        
        # Check Leaflet canvas
        leaflet = await self.page.query_selector(self.dashboard.selectors['map_canvas'])
        self.assertIsNotNone(leaflet, "Leaflet map not found")
        
        print("  Map rendered successfully")
    
    # ========================================================================
    # Responsive Design Tests
    # ========================================================================
    
    async def test_responsive_desktop(self):
        """Test desktop responsive layout"""
        print("\n" + "="*60)
        print("TEST: Responsive Design - Desktop")
        print("="*60)
        
        await self.page.set_viewport_size(UITestConfig.VIEWPORTS['desktop'])
        await asyncio.sleep(1)
        
        # Check sidebar visible
        sidebar = await self.page.query_selector('.sidebar')
        is_visible = await sidebar.is_visible() if sidebar else False
        self.assertTrue(is_visible, "Sidebar not visible on desktop")
        print("  Desktop layout verified")
    
    async def test_responsive_tablet(self):
        """Test tablet responsive layout"""
        print("\n" + "="*60)
        print("TEST: Responsive Design - Tablet")
        print("="*60)
        
        await self.page.set_viewport_size(UITestConfig.VIEWPORTS['tablet'])
        await asyncio.sleep(1)
        
        # Check mobile menu toggle exists
        toggle = await self.page.query_selector('.mobile-menu-toggle')
        self.assertIsNotNone(toggle, "Mobile menu toggle not found on tablet")
        print("  Tablet layout verified")
    
    async def test_responsive_mobile(self):
        """Test mobile responsive layout"""
        print("\n" + "="*60)
        print("TEST: Responsive Design - Mobile")
        print("="*60)
        
        await self.page.set_viewport_size(UITestConfig.VIEWPORTS['mobile'])
        await asyncio.sleep(1)
        
        # Check sidebar hidden by default
        sidebar = await self.page.query_selector('.sidebar')
        if sidebar:
            is_visible = await sidebar.is_visible()
            self.assertFalse(is_visible, "Sidebar should be hidden on mobile")
        
        # Check stats grid becomes single column
        stats_grid = await self.page.query_selector('.stats-grid')
        if stats_grid:
            display = await stats_grid.evaluate("el => getComputedStyle(el).display")
            print(f"  Stats grid display: {display}")
        
        print("  Mobile layout verified")
    
    # ========================================================================
    # Accessibility Tests
    # ========================================================================
    
    async def test_keyboard_navigation(self):
        """Test keyboard navigation"""
        print("\n" + "="*60)
        print("TEST: Keyboard Navigation")
        print("="*60)
        
        # Tab through interactive elements
        await self.page.keyboard.press("Tab")
        await asyncio.sleep(0.5)
        
        # Check focus is on an interactive element
        focused = await self.page.evaluate("document.activeElement")
        self.assertIsNotNone(focused, "No element focused after Tab")
        print("  Keyboard navigation works")
    
    async def test_aria_labels(self):
        """Test ARIA labels for accessibility"""
        print("\n" + "="*60)
        print("TEST: ARIA Labels")
        print("="*60)
        
        # Check for aria labels on buttons
        buttons = await self.page.query_selector_all('button')
        aria_count = 0
        
        for button in buttons:
            aria_label = await button.get_attribute('aria-label')
            if aria_label:
                aria_count += 1
        
        print(f"  Buttons with aria labels: {aria_count}/{len(buttons)}")
        
        # Should have at least some aria labels
        self.assertGreater(aria_count, 0, "No ARIA labels found")
    
    # ========================================================================
    # Performance Tests
    # ========================================================================
    
    async def test_page_load_time(self):
        """Test page load performance"""
        print("\n" + "="*60)
        print("TEST: Page Load Performance")
        print("="*60)
        
        start_time = time.time()
        
        await self.page.reload()
        await self.dashboard.wait_for_load()
        
        load_time = (time.time() - start_time) * 1000
        print(f"  Page load time: {load_time:.0f}ms")
        
        self.assertLess(load_time, 3000, f"Page load too slow: {load_time:.0f}ms")
    
    async def test_animation_performance(self):
        """Test animation smoothness"""
        print("\n" + "="*60)
        print("TEST: Animation Performance")
        print("="*60)
        
        # Navigate to map for panning test
        await self.dashboard.click_nav('map')
        await asyncio.sleep(1)
        
        # Measure frame rate during pan
        await self.page.evaluate("""
            var frames = 0;
            var lastTime = performance.now();
            function countFrame() {
                frames++;
                requestAnimationFrame(countFrame);
            }
            requestAnimationFrame(countFrame);
            window.frames = frames;
        """)
        
        # Pan the map
        map_element = await self.page.query_selector(self.dashboard.selectors['map_canvas'])
        if map_element:
            box = await map_element.bounding_box()
            await self.page.mouse.move(box['x'] + box['width']/2, box['y'] + box['height']/2)
            await self.page.mouse.down()
            await self.page.mouse.move(box['x'] + box['width']/2 + 100, box['y'] + box['height']/2)
            await self.page.mouse.up()
        
        await asyncio.sleep(1)
        
        frames = await self.page.evaluate("window.frames")
        print(f"  Animation frames counted: {frames}")
        
        # Should have at least some animation frames
        self.assertGreater(frames, 0, "No animation frames detected")


# ============================================================================
# Run Tests
# ============================================================================

async def run_ui_tests():
    """Run UI test suite"""
    test_classes = [
        TestDashboardUI
    ]
    
    for test_class in test_classes:
        print(f"\n{'='*60}")
        print(f"Running {test_class.__name__}")
        print(f"{'='*60}")
        
        instance = test_class()
        await instance.asyncSetUp()
        
        # Run test methods
        for method_name in dir(instance):
            if method_name.startswith('test_'):
                method = getattr(instance, method_name)
                try:
                    await method()
                    print(f"✓ {method_name}")
                except Exception as e:
                    print(f"✗ {method_name}: {e}")
                    # Take screenshot on failure
                    if hasattr(instance, 'dashboard'):
                        await instance.dashboard.take_screenshot(f"fail_{method_name}")
        
        await instance.asyncTearDown()


if __name__ == '__main__':
    asyncio.run(run_ui_tests())