"""
Tests for OnlyFence Guardrails

These tests mock the OnlyFence database to test guardrail logic.
"""

import unittest
import sys
from unittest.mock import patch, MagicMock
from pathlib import Path

# Add skills to path
sys.path.insert(0, '..')

# Mock the sqlite3 connection before importing guardrails
mock_conn = MagicMock()
mock_cursor = MagicMock()

with patch('sqlite3.connect') as mock_connect:
    mock_connect.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor
    
    from onlyfence_guardrails.guardrails import OnlyFenceGuardrails, GuardrailConfig


class TestGuardrailConfig(unittest.TestCase):
    """Test guardrail configuration."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = GuardrailConfig(
            max_single_trade=200.0,
            max_24h_volume=500.0,
            allowed_tokens=["SUI", "0x2::sui::SUI"]
        )
        
        self.assertEqual(config.max_single_trade, 200.0)
        self.assertEqual(config.max_24h_volume, 500.0)
        self.assertIn("SUI", config.allowed_tokens)
    
    def test_custom_limits(self):
        """Test custom limits."""
        config = GuardrailConfig(
            max_single_trade=1000.0,
            max_24h_volume=5000.0,
            allowed_tokens=["SUI", "USDC", "AIDA"]
        )
        
        self.assertEqual(config.max_single_trade, 1000.0)
        self.assertEqual(config.max_24h_volume, 5000.0)


class TestGuardrailChecks(unittest.TestCase):
    """Test guardrail check logic."""
    
    def setUp(self):
        """Set up test fixtures."""
        with patch('sqlite3.connect') as mock_connect:
            mock_connect.return_value = mock_conn
            mock_conn.cursor.return_value = mock_cursor
            mock_cursor.fetchone.return_value = [0]  # No volume
            self.guardrails = OnlyFenceGuardrails()
    
    def test_token_in_allowlist(self):
        """Test that only allowlisted tokens pass."""
        result = self.guardrails.check_trade(
            token_address="SUI",
            amount_usd=50.0
        )
        self.assertTrue(result.allowed)
    
    def test_token_not_in_allowlist(self):
        """Test that non-allowlisted tokens are blocked."""
        result = self.guardrails.check_trade(
            token_address="UNKNOWN_TOKEN",
            amount_usd=50.0
        )
        self.assertFalse(result.allowed)
        self.assertIn("not in allowlist", result.reason)
    
    def test_amount_exceeds_single_limit(self):
        """Test that amounts over single trade limit are blocked."""
        result = self.guardrails.check_trade(
            token_address="SUI",
            amount_usd=300.0  # Over 200 limit
        )
        self.assertFalse(result.allowed)
        self.assertIn("exceeds max", result.reason)
    
    def test_amount_under_single_limit(self):
        """Test that amounts under limit pass."""
        result = self.guardrails.check_trade(
            token_address="SUI",
            amount_usd=150.0  # Under 200 limit
        )
        self.assertTrue(result.allowed)
    
    def test_24h_volume_exceeded(self):
        """Test that 24h volume limit is enforced."""
        # Mock existing volume
        mock_cursor.fetchone.return_value = [400.0]  # $400 already traded
        
        result = self.guardrails.check_trade(
            token_address="SUI",
            amount_usd=150.0  # Would bring total to $550
        )
        self.assertFalse(result.allowed)
        self.assertIn("24h volume", result.reason)
    
    def test_24h_volume_ok(self):
        """Test that 24h volume under limit passes."""
        # Mock existing volume
        mock_cursor.fetchone.return_value = [100.0]  # $100 already traded
        
        result = self.guardrails.check_trade(
            token_address="SUI",
            amount_usd=150.0  # Would bring total to $250
        )
        self.assertTrue(result.allowed)


class TestTradeLogging(unittest.TestCase):
    """Test trade logging."""
    
    def test_log_trade(self):
        """Test that trades are logged."""
        with patch('sqlite3.connect') as mock_connect:
            mock_connect.return_value = mock_conn
            mock_conn.cursor.return_value = mock_cursor
            
            guardrails = OnlyFenceGuardrails()
            guardrails.log_trade("SUI", 50.0, "buy")
            
            # Verify insert was called
            mock_cursor.execute.assert_called_once()
    
    def test_24h_volume_calculation(self):
        """Test 24h volume is calculated correctly."""
        with patch('sqlite3.connect') as mock_connect:
            mock_connect.return_value = mock_conn
            mock_cursor.fetchone.return_value = [250.5]
            
            guardrails = OnlyFenceGuardrails()
            volume = guardrails.get_24h_volume()
            
            self.assertEqual(volume, 250.5)


class TestEdgeCases(unittest.TestCase):
    """Test edge cases."""
    
    def test_zero_amount(self):
        """Test zero amount trade."""
        with patch('sqlite3.connect') as mock_connect:
            mock_connect.return_value = mock_conn
            mock_conn.cursor.return_value = mock_cursor
            mock_cursor.fetchone.return_value = [0]
            
            guardrails = OnlyFenceGuardrails()
            result = guardrails.check_trade("SUI", 0.0)
            
            self.assertTrue(result.allowed)  # $0 should be allowed
    
    def test_exactly_at_limit(self):
        """Test amount exactly at limit."""
        with patch('sqlite3.connect') as mock_connect:
            mock_connect.return_value = mock_conn
            mock_conn.cursor.return_value = mock_cursor
            mock_cursor.fetchone.return_value = [0]
            
            guardrails = OnlyFenceGuardrails()
            
            # Exactly at $200
            result = guardrails.check_trade("SUI", 200.0)
            self.assertTrue(result.allowed)
    
    def test_just_over_limit(self):
        """Test amount just over limit."""
        with patch('sqlite3.connect') as mock_connect:
            mock_connect.return_value = mock_conn
            mock_conn.cursor.return_value = mock_cursor
            mock_cursor.fetchone.return_value = [0]
            
            guardrails = OnlyFenceGuardrails()
            
            # Just over $200
            result = guardrails.check_trade("SUI", 200.01)
            self.assertFalse(result.allowed)


if __name__ == "__main__":
    unittest.main()
