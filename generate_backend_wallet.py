"""
generate_backend_wallet.py - Generate wallet for backend

Run this to create a wallet for your Python backend server.
This wallet needs CELO for gas fees and must be authorized in the agent wallet.
"""

import os
from eth_account import Account
import secrets

def generate_wallet():
    """Generate a new Ethereum wallet for the backend"""
    # Generate random private key
    private_key = "0x" + secrets.token_hex(32)
    
    # Create account
    account = Account.from_key(private_key)
    
    print("\n" + "="*60)
    print("BACKEND WALLET GENERATED")
    print("="*60)
    print(f"\nAddress: {account.address}")
    print(f"\nPrivate Key: {private_key}")
    print("\n" + "="*60)
    print("IMPORTANT:")
    print("1. Save these in backend/.env as AGENT_PRIVATE_KEY")
    print("2. Save address in contracts/.env as BACKEND_ADDRESS")
    print("3. Fund this address with CELO for gas fees")
    print("4. Authorize this address in your agent wallet contract")
    print("="*60 + "\n")
    
    return {
        "address": account.address,
        "private_key": private_key
    }

if __name__ == "__main__":
    wallet = generate_wallet()
    
    # Optional: Save to file
    save = input("Save to backend_wallet.txt? (y/n): ").lower().strip()
    if save == 'y':
        with open("backend_wallet.txt", "w") as f:
            f.write(f"Address: {wallet['address']}\n")
            f.write(f"Private Key: {wallet['private_key']}\n")
        print("Saved to backend_wallet.txt - DO NOT COMMIT THIS FILE!")
