#!/usr/bin/env python3
"""
Test script for Payment Orchestration MVP with MySQL
Shows the complete transaction flow
"""

import requests
import json
import uuid
from datetime import datetime


def print_payment_options(amount: float):
    """Fetch and display payment options for a given amount"""
    
    url = "http://localhost:8000/api/checkout"
    payload = {"amount": amount}
    
    print(f"\n{'='*60}")
    print(f"💰 CHECKOUT OPTIONS FOR ₹{amount:,.2f}")
    print(f"{'='*60}\n")
    
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        
        data = response.json()
        
        print(f"Original Amount: ₹{data['original_amount']:,.2f}\n")
        print(f"Available Payment Options:\n")
        
        for i, option in enumerate(data['payment_options'], 1):
            fee_indicator = "🟢 FREE" if option['fee_amount'] == 0 else f"💰 +₹{option['fee_amount']:.2f}"
            
            print(f"{i}. {option['gateway']} - {option['payment_mode'].upper().replace('_', ' ')}")
            print(f"   Base Amount: ₹{option['base_amount']:,.2f}")
            if option['fee_amount'] > 0:
                print(f"   Fee ({option['fee_percentage']}%): ₹{option['fee_amount']:.2f}")
            print(f"   Total: ₹{option['total_amount']:,.2f} {fee_indicator}\n")
        
        # Find best option (lowest total)
        best_option = min(data['payment_options'], key=lambda x: x['total_amount'])
        print(f"⭐ BEST OPTION: {best_option['gateway']} - {best_option['payment_mode'].upper().replace('_', ' ')}")
        print(f"   Total Payable: ₹{best_option['total_amount']:,.2f}\n")
        
        return data['payment_options'], best_option
        
    except requests.exceptions.ConnectionError:
        print("❌ Error: Could not connect to server. Make sure the server is running on http://localhost:8000")
        return None, None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None, None


def save_transaction(payment_option: dict, amount: float):
    """Save transaction to database"""
    
    transaction_id = f"{uuid.uuid4().hex[:8]}"
    
    print(f"\n💾 SAVING TRANSACTION TO DATABASE...")
    print(f"   Transaction ID: {transaction_id}")
    print(f"   Gateway: {payment_option['gateway']}")
    print(f"   Payment Mode: {payment_option['payment_mode']}")
    print(f"   Amount: ₹{amount:,.2f}")
    print(f"   Fee: ₹{payment_option['fee_amount']:,.2f}")
    print(f"   Total: ₹{payment_option['total_amount']:,.2f}")
    
    url = "http://localhost:8000/api/transactions"
    payload = {
        "transaction_id": transaction_id,
        "gateway": payment_option['gateway'],
        "payment_mode": payment_option['payment_mode'],
        "base_amount": amount,
        "fee_amount": payment_option['fee_amount'],
        "total_amount": payment_option['total_amount'],
        "status": "pending"
    }
    
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        
        print(f"   ✅ Transaction saved successfully!\n")
        return transaction_id
        
    except Exception as e:
        print(f"   ❌ Error saving transaction: {e}\n")
        return None


def update_transaction_status(transaction_id: str, status: str):
    """Update transaction status in database"""
    
    print(f"\n🔄 UPDATING TRANSACTION STATUS...")
    print(f"   Transaction ID: {transaction_id}")
    print(f"   New Status: {status}")
    
    url = f"http://localhost:8000/api/transactions/{transaction_id}"
    params = {
        "status": status,
        "gateway_transaction_id": f"gateway_transaction_id_{uuid.uuid4().hex[:8]}",
        "gateway_response": "Payment processed successfully"
    }
    
    try:
        response = requests.put(url, params=params)
        response.raise_for_status()
        
        print(f"   ✅ Transaction updated successfully!\n")
        
    except Exception as e:
        print(f"   ❌ Error updating transaction: {e}\n")


def get_transaction(transaction_id: str):
    """Get transaction details from database"""
    
    print(f"\n📖 FETCHING TRANSACTION DETAILS...")
    print(f"   Transaction ID: {transaction_id}")
    
    url = f"http://localhost:8000/api/transactions/{transaction_id}"
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        
        data = response.json()
        
        print(f"\n   Transaction Details:")
        print(f"   - ID: {data['id']}")
        print(f"   - Gateway: {data['gateway']}")
        print(f"   - Payment Mode: {data['payment_mode']}")
        print(f"   - Amount: ₹{data['base_amount']:,.2f}")
        print(f"   - Fee: ₹{data['fee_amount']:,.2f}")
        print(f"   - Total: ₹{data['total_amount']:,.2f}")
        print(f"   - Status: {data['status']}")
        print(f"   - Created: {data['created_at']}")
        print(f"   - Updated: {data['updated_at']}\n")
        
    except Exception as e:
        print(f"   ❌ Error fetching transaction: {e}\n")


def main():
    """Main function showing complete transaction flow"""
    
    print("""
╔════════════════════════════════════════════════════════════╗
║     Payment Orchestration MVP - MySQL                      ║
╚════════════════════════════════════════════════════════════╝
    """)
    
    # Demo with different amounts
    demo_amounts = [1500, 9000]
    
    for amount in demo_amounts:
        # Show payment options
        options, best_option = print_payment_options(amount)
        
        if best_option:
            # Save the transaction
            transaction_id = save_transaction(best_option, amount)
            
            if transaction_id:
                # Simulate waiting...
                import time
                print("⏳ Processing payment with gateway...\n")
                time.sleep(10)
                
                # Update status to success
                update_transaction_status(transaction_id, "success")
                
                # Get transaction details
                get_transaction(transaction_id)
        
        print(f"{'='*60}\n")
    
    # Show all saved transactions
    print("\n📊 ALL TRANSACTIONS IN DATABASE:\n")
    try:
        response = requests.get("http://localhost:8000/api/transactions")
        response.raise_for_status()
        
        data = response.json()
        
        for i, tx in enumerate(data['transactions'][:5], 1):  # Show first 5
            print(f"{i}. {tx['transaction_id']} - {tx['gateway']} {tx['payment_mode']} - ₹{tx['total_amount']:,.2f} - {tx['status']}")
        
        print(f"\n... and {data['count'] - min(5, data['count'])} more transactions\n")
        
    except Exception as e:
        print(f"❌ Error fetching transactions: {e}\n")
    
    print("\n Demo completed! Visit http://localhost:8000/docs for interactive API testing.")


if __name__ == "__main__":
    main()