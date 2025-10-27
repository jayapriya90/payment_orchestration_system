from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Optional
import uvicorn

app = FastAPI(title="Payment Orchestration MVP", version="1.0.0")


# Simple data models
class PaymentOption(BaseModel):
    gateway: str
    payment_mode: str
    base_amount: float
    fee_amount: float
    total_amount: float
    fee_percentage: float


class CheckoutRequest(BaseModel):
    amount: float


class CheckoutResponse(BaseModel):
    original_amount: float
    payment_options: List[PaymentOption]


# Simplified fee calculation
def calculate_fee(amount: float, payment_mode: str) -> tuple[float, float, float]:
    """Calculate fee based on payment mode and amount"""
    
    fee_configs = {
        "debit_card": {
            "ranges": [
                (0, 2000, 0.0),      # ≤ ₹2,000: 0%
                (2000.01, float('inf'), 0.5)  # > ₹2,000: 0.5%
            ]
        },
        "credit_card": {
            "ranges": [
                (0, 25000, 0.1),     # ≤ ₹25,000: 0.1%
                (25000.01, float('inf'), 0.5)  # > ₹25,000: 0.5%
            ]
        },
        "netbanking": {
            "ranges": [
                (0, 10000, 0.0),     # ≤ ₹10,000: 0%
                (10000.01, 50000, 0.75),  # ₹10,001-50,000: 0.75%
                (50000.01, float('inf'), 1.0)  # > ₹50,000: 1%
            ]
        },
        "upi": {
            "ranges": [
                (0, float('inf'), 0.0)  # Any amount: 0%
            ]
        }
    }
    
    config = fee_configs.get(payment_mode, fee_configs["upi"])
    
    # Find applicable range
    fee_percentage = 0.0
    for min_amount, max_amount, percentage in config["ranges"]:
        if min_amount <= amount <= max_amount:
            fee_percentage = percentage
            break
    
    # Calculate fee and total
    fee_amount = (amount * fee_percentage) / 100
    total_amount = amount + fee_amount
    
    return fee_amount, total_amount, fee_percentage


@app.get("/")
def health():
    return {"status": "healthy", "message": "Payment Orchestration MVP is running"}


@app.post("/api/checkout", response_model=CheckoutResponse)
def create_checkout(request: CheckoutRequest):
    """
    Simple checkout endpoint that shows all payment options with fees.
    """
    
    payment_options = []
    
    # Define available payment methods
    payment_methods = [
        ("Razorpay", "debit_card"),
        ("Razorpay", "credit_card"),
        ("Razorpay", "netbanking"),
        ("Razorpay", "upi"),
        ("PayU", "debit_card"),
        ("PayU", "credit_card"),
        ("PayU", "upi"),
        ("Cashfree", "debit_card"),
        ("Cashfree", "upi"),
    ]
    
    # Calculate fees for each option
    for gateway, payment_mode in payment_methods:
        fee_amount, total_amount, fee_percentage = calculate_fee(request.amount, payment_mode)
        
        payment_options.append(PaymentOption(
            gateway=gateway,
            payment_mode=payment_mode,
            base_amount=request.amount,
            fee_amount=round(fee_amount, 2),
            total_amount=round(total_amount, 2),
            fee_percentage=fee_percentage
        ))
    
    return CheckoutResponse(
        original_amount=request.amount,
        payment_options=payment_options
    )


@app.get("/api/calculate-fee")
def get_fee(amount: float, payment_mode: str):
    """Calculate fee for a specific payment mode"""
    fee_amount, total_amount, fee_percentage = calculate_fee(amount, payment_mode)
    
    return {
        "amount": amount,
        "payment_mode": payment_mode,
        "fee_amount": round(fee_amount, 2),
        "total_amount": round(total_amount, 2),
        "fee_percentage": fee_percentage
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
