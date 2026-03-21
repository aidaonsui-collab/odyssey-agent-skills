"""
LangChain Integration Example

Shows how to wrap Odyssey skills as LangChain tools.
"""

import os
import sys
sys.path.insert(0, '../skills/sui-token-launch')
sys.path.insert(0, '../skills/sui-bonding-curve-trade')

# Note: You'll need langchain installed
# pip install langchain langchain-core

"""
from langchain_core.tools import tool
from sui_token_launch.launcher import OdysseyLauncher
from sui_bonding_curve_trade.trader import OdysseyTrader

# Initialize once (use singleton in production)
_launcher = OdysseyLauncher()
_trader = OdysseyTrader()


@tool
def odyssey_buy_token(pool_id: str, token_type: str, sui_amount: float) -> str:
    \"\"\"
    Buy tokens from Odyssey bonding curve.
    
    Args:
        pool_id: The pool ID of the token to buy
        token_type: The token type address
        sui_amount: Amount of SUI to spend
        
    Returns:
        JSON string with purchase details
    \"\"\"
    result = _trader.buy(
        pool_id=pool_id,
        token_type=token_type,
        sui_amount=sui_amount
    )
    return json.dumps({
        "success": result.success,
        "tokens_received": result.tokens_display,
        "sui_spent": result.sui_amount,
        "price_per_token": result.price_per_token,
        "error": result.error
    })


@tool  
def odyssey_sell_token(pool_id: str, token_type: str, token_amount: float) -> str:
    \"\"\"
    Sell tokens back to Odyssey bonding curve.
    
    Args:
        pool_id: The pool ID of the token to sell
        token_type: The token type address
        token_amount: Amount of tokens to sell
        
    Returns:
        JSON string with sale details
    \"\"\"
    result = _trader.sell(
        pool_id=pool_id,
        token_type=token_type,
        token_amount=token_amount
    )
    return json.dumps({
        "success": result.success,
        "sui_received": result.sui_amount,
        "tokens_sold": result.tokens_display,
        "price_per_token": result.price_per_token,
        "error": result.error
    })


@tool
def odyssey_calculate_price(sui_amount: float) -> str:
    \"\"\"
    Calculate how many tokens you'd receive for a SUI amount.
    
    Args:
        sui_amount: Amount of SUI to spend
        
    Returns:
        JSON string with calculation
    \"\"\"
    tokens_raw, tokens_display = _trader.calculate_buy_tokens(sui_amount)
    price = sui_amount / tokens_display if tokens_display > 0 else 0
    
    return json.dumps({
        "sui_amount": sui_amount,
        "tokens_received": tokens_display,
        "price_per_token": price
    })


# Create tool list for LangChain agent
odyssey_tools = [
    odyssey_buy_token,
    odyssey_sell_token,
    odyssey_calculate_price,
]


# Example LangChain agent usage:
"""
from langchain import hub
from langchain.agents import AgentExecutor, create_react_agent
from langchain_openai import OpenAI

def run_odyssey_agent():
    # Example: Create agent that can trade on Odyssey
    
    prompt = hub.pull("hwchase17/react")
    llm = OpenAI(temperature=0)
    
    agent = create_react_agent(llm, odyssey_tools, prompt)
    agent_executor = AgentExecutor(
        agent=agent, 
        tools=odyssey_tools, 
        verbose=True
    )
    
    # Example queries:
    # "Buy 10 SUI worth of TOKEN from pool 0x1234"
    # "How many tokens would I get for 50 SUI?"
    # "Sell 1000 tokens from pool 0x5678"
    
    return agent_executor
"""
