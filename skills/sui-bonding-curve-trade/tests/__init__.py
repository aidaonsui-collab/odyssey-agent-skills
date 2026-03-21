"""
Tests for Odyssey Bonding Curve Calculations
"""

import unittest
import sys
sys.path.insert(0, '..')

from ..trader import OdysseyTrader, VIRTUAL_TOKEN_RESERVES, VIRTUAL_SUI_START, TOKEN_DECIMALS


class TestBondingCurveCalculations(unittest.TestCase):
    """Test bonding curve math."""
    
    def setUp(self):
        self.trader = OdysseyTrader()
    
    def test_buy_1_sui(self):
        """Test buying with 1 SUI gives ~1.6M tokens."""
        tokens_raw, tokens_display = self.trader.calculate_buy_tokens(1.0)
        
        # 1 SUI should give approximately 50% of supply
        expected_min = 1_500_000  # ~1.5M minimum
        expected_max = 1_700_000  # ~1.7M maximum
        
        self.assertGreater(tokens_display, expected_min)
        self.assertLess(tokens_display, expected_max)
    
    def test_buy_10_sui(self):
        """Test buying with 10 SUI gives ~15.76M tokens."""
        tokens_raw, tokens_display = self.trader.calculate_buy_tokens(10.0)
        
        # 10 SUI should give approximately 91% of supply
        expected_min = 15_000_000  # ~15M minimum
        expected_max = 17_000_000  # ~17M maximum
        
        self.assertGreater(tokens_display, expected_min)
        self.assertLess(tokens_display, expected_max)
    
    def test_buy_50_sui(self):
        """Test buying with 50 SUI gives ~74.4M tokens."""
        tokens_raw, tokens_display = self.trader.calculate_buy_tokens(50.0)
        
        # 50 SUI should give approximately 98% of supply
        expected_min = 70_000_000  # ~70M minimum
        expected_max = 80_000_000  # ~80M maximum
        
        self.assertGreater(tokens_display, expected_min)
        self.assertLess(tokens_display, expected_max)
    
    def test_buy_small_amount(self):
        """Test small buy amounts."""
        tokens_raw, tokens_display = self.trader.calculate_buy_tokens(0.1)
        
        # Should still return some tokens
        self.assertGreater(tokens_display, 0)
    
    def test_sell_tokens(self):
        """Test selling tokens returns SUI."""
        sui_mist, sui_display = self.trader.calculate_sell_sui(1_000_000)
        
        # Selling tokens should return some SUI
        self.assertGreater(sui_display, 0)
    
    def test_sell_half_supply(self):
        """Selling 50% of supply should return approximately 0.333 SUI."""
        # Half the virtual supply = VIRTUAL_TOKEN_RESERVES / 2
        half_supply = VIRTUAL_TOKEN_RESERVES / 2
        tokens_for_half = half_supply / (10 ** TOKEN_DECIMALS)
        
        sui_mist, sui_display = self.trader.calculate_sell_sui(tokens_for_half)
        
        # Should get approximately 1/3 of the virtual SUI
        expected_min = 0.2
        expected_max = 0.5
        
        self.assertGreater(sui_display, expected_min)
        self.assertLess(sui_display, expected_max)
    
    def test_slippage(self):
        """Test slippage calculation."""
        self.trader.set_slippage(50)  # 0.5%
        
        amount = 1_000_000_000  # 1 SUI in mist
        min_amount = self.trader.apply_slippage(amount)
        
        # Should be 99.5% of original
        expected = amount * 9950 // 10000
        self.assertEqual(min_amount, expected)
    
    def test_price_decreases_with_size(self):
        """Larger buys should have worse effective price."""
        _, price1 = self.trader.calculate_buy_tokens(1.0)
        _, price10 = self.trader.calculate_buy_tokens(10.0)
        _, price50 = self.trader.calculate_buy_tokens(50.0)
        
        # Price per token should increase with larger buys
        # (you get less tokens per SUI as you buy more)
        self.assertGreater(price1, 0)
        self.assertGreater(price10, price1)
        self.assertGreater(price50, price10)


class TestValidation(unittest.TestCase):
    """Test input validation."""
    
    def setUp(self):
        self.trader = OdysseyTrader()
    
    def test_buy_zero_amount(self):
        """Zero SUI should fail validation."""
        error = self.trader.validate_buy(0.0)
        self.assertIsNotNone(error)
    
    def test_buy_negative_amount(self):
        """Negative SUI should fail validation."""
        error = self.trader.validate_buy(-1.0)
        self.assertIsNotNone(error)
    
    def test_buy_too_small(self):
        """Buy below minimum should fail."""
        error = self.trader.validate_buy(0.001)  # Below 0.01 minimum
        self.assertIsNotNone(error)
    
    def test_sell_zero_amount(self):
        """Zero tokens should fail validation."""
        error = self.trader.validate_sell(0.0)
        self.assertIsNotNone(error)
    
    def test_sell_negative_amount(self):
        """Negative tokens should fail validation."""
        error = self.trader.validate_sell(-100.0)
        self.assertIsNotNone(error)


if __name__ == "__main__":
    unittest.main()
