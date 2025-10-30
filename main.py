from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import uvicorn
import pymysql
from contextlib import contextmanager
import uuid

app = FastAPI(title="Payment Orchestration MVP", version="1.0.0")

# Database configuration
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': 'root',
    'database': 'payment_orchestration',
}


@contextmanager
def get_db_connection():
    """Context manager for database connections"""
    connection = None
    try:
        connection = pymysql.connect(
            host=DB_CONFIG['host'],
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password'],
            database=DB_CONFIG['database'],
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=False
        )
        yield connection
        connection.commit()
    except Exception as e:
        if connection:
            connection.rollback()
        print(f"Database error: {e}")
        raise
    finally:
        if connection  and connection.open:
            connection.close()


# Data models
class PaymentOption(BaseModel):
    gateway: str
    payment_mode: str
    base_amount: float
    fee_amount: float
    total_amount: float
    fee_percentage: float
    success_rate: Optional[float] = None


class CheckoutRequest(BaseModel):
    amount: float


class CheckoutResponse(BaseModel):
    original_amount: float
    payment_options: List[PaymentOption]
    recommended_option: Optional[PaymentOption] = None


class TransactionRequest(BaseModel):
    transaction_id: str
    gateway: str
    payment_mode: str
    base_amount: float
    fee_amount: float
    total_amount: float
    status: str = "pending"


class TransactionResponse(BaseModel):
    id: int
    transaction_id: str
    gateway: str
    payment_mode: str
    base_amount: float
    fee_amount: float
    total_amount: float
    status: str
    gateway_transaction_id: Optional[str]
    created_at: datetime
    updated_at: datetime


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


def get_success_rate_from_db(gateway: str, payment_mode: str) -> float:
    """Get success rate for a (gateway, mode) pair from database"""
    try:
        with get_db_connection() as connection:
            cursor = connection.cursor()

            cursor.execute("""
                SELECT
                    SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) / COUNT(*) * 100 as success_rate
                FROM transactions
                WHERE gateway = %s AND payment_mode = %s
                AND created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)
            """, (gateway, payment_mode))

            result = cursor.fetchone()

            if result and result['success_rate'] is not None:
                return float(result['success_rate'])

            # Default success rate if no data
            return 95.0

    except Exception as e:
        print(f"Error fetching success rate: {e}")
        return 95.0  # Default success rate


@app.post("/api/checkout", response_model=CheckoutResponse)
def create_checkout(request: CheckoutRequest):
    """
    Simple checkout endpoint that shows all payment options with fees.
    Includes recommended option based on lowest fee and highest success rate.
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

    # Calculate fees for each option and fetch success rates
    for gateway, payment_mode in payment_methods:
        fee_amount, total_amount, fee_percentage = calculate_fee(request.amount, payment_mode)
        success_rate = get_success_rate_from_db(gateway, payment_mode)

        payment_options.append(PaymentOption(
            gateway=gateway,
            payment_mode=payment_mode,
            base_amount=request.amount,
            fee_amount=round(fee_amount, 2),
            total_amount=round(total_amount, 2),
            fee_percentage=fee_percentage,
            success_rate=round(success_rate, 2)
        ))

    # Find recommended option: lowest fee AND highest success rate
    # Score = (1 / total_amount) * 100 + success_rate
    # Lower total_amount and higher success_rate = higher score
    best_option = None
    best_score = -1

    for option in payment_options:
        # Calculate score: inverse of total amount (lower is better) + success rate (higher is better)
        # We get success rate from database
        success_rate = get_success_rate_from_db(option.gateway, option.payment_mode)

        # Score: Lower total_amount and higher success_rate is better
        # Normalize: (1 / total_amount * 1000) + success_rate
        score = (1 / option.total_amount * 1000) + success_rate

        if score > best_score:
            best_score = score
            best_option = option

    return CheckoutResponse(
        original_amount=request.amount,
        payment_options=payment_options,
        recommended_option=best_option
    )


@app.post("/api/transactions", response_model=TransactionResponse)
def create_transaction(transaction: TransactionRequest):
    """
    Create a new transaction record when user selects a payment option.
    This persists the transaction to the database.
    """

    transaction_id = transaction.transaction_id if transaction.transaction_id else uuid.uuid4().hex

    # Get current timestamp for created_at and updated_at
    current_time = datetime.now()

    try:
        with get_db_connection() as connection:
            cursor = connection.cursor()

            # Insert transaction into database
            cursor.execute("""
                INSERT INTO transactions
                (transaction_id, gateway, payment_mode, base_amount, fee_amount, total_amount, status, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                transaction_id,
                transaction.gateway,
                transaction.payment_mode,
                transaction.base_amount,
                transaction.fee_amount,
                transaction.total_amount,
                transaction.status,
                current_time,
                current_time
            ))

            # Get the created transaction
            cursor.execute("""
                SELECT * FROM transactions WHERE transaction_id = %s
            """, (transaction_id,))

            result = cursor.fetchone()
            connection.commit()

            if result:
                return TransactionResponse(
                    id=result['id'],
                    transaction_id=result['transaction_id'],
                    gateway=result['gateway'],
                    payment_mode=result['payment_mode'],
                    base_amount=float(result['base_amount']),
                    fee_amount=float(result['fee_amount']),
                    total_amount=float(result['total_amount']),
                    status=result['status'],
                    gateway_transaction_id=result.get('gateway_transaction_id'),
                    created_at=result['created_at'] or current_time,
                    updated_at=result['updated_at'] or current_time
                )
            else:
                raise HTTPException(status_code=500, detail="Failed to create transaction")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@app.put("/api/transactions/{transaction_id}")
def update_transaction(transaction_id: str, status: str, gateway_transaction_id: Optional[str] = None, gateway_response: Optional[str] = None):
    """
    Update transaction status (e.g., when payment succeeds or fails).
    Use this after processing the payment with the gateway.
    """

    try:
        with get_db_connection() as connection:
            cursor = connection.cursor()

            # Update transaction
            update_fields = []
            params = []

            if status:
                update_fields.append("status = %s")
                params.append(status)
            if gateway_transaction_id:
                update_fields.append("gateway_transaction_id = %s")
                params.append(gateway_transaction_id)
            if gateway_response:
                update_fields.append("gateway_response = %s")
                params.append(gateway_response)

            if update_fields:
                update_fields.append("updated_at = CURRENT_TIMESTAMP")
                params.append(transaction_id)

                cursor.execute(f"""
                    UPDATE transactions
                    SET {', '.join(update_fields)}
                    WHERE transaction_id = %s
                """, tuple(params))

                connection.commit()

                if cursor.rowcount > 0:
                    return {"message": "Transaction updated successfully", "transaction_id": transaction_id}
                else:
                    raise HTTPException(status_code=404, detail="Transaction not found")
            else:
                raise HTTPException(status_code=400, detail="No fields to update")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@app.get("/api/transactions/{transaction_id}", response_model=TransactionResponse)
def get_transaction(transaction_id: str):
    """Get transaction details by transaction ID"""

    try:
        with get_db_connection() as connection:
            cursor = connection.cursor()

            cursor.execute("""
                SELECT * FROM transactions WHERE transaction_id = %s
            """, (transaction_id,))

            result = cursor.fetchone()

            if result:
                return TransactionResponse(
                    id=result['id'],
                    transaction_id=result['transaction_id'],
                    gateway=result['gateway'],
                    payment_mode=result['payment_mode'],
                    base_amount=float(result['base_amount']),
                    fee_amount=float(result['fee_amount']),
                    total_amount=float(result['total_amount']),
                    status=result['status'],
                    gateway_transaction_id=result.get('gateway_transaction_id'),
                    created_at=result['created_at'],
                    updated_at=result['updated_at']
                )
            else:
                raise HTTPException(status_code=404, detail="Transaction not found")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@app.get("/api/transactions")
def list_transactions(status: Optional[str] = None, limit: int = 50):
    """List all transactions, optionally filtered by status"""

    try:
        with get_db_connection() as connection:
            cursor = connection.cursor()

            query = "SELECT * FROM transactions"
            params = []

            if status:
                query += " WHERE status = %s"
                params.append(status)

            query += " ORDER BY created_at DESC LIMIT %s"
            params.append(limit)

            cursor.execute(query, tuple(params))
            results = cursor.fetchall()

            return {"transactions": results, "count": len(results)}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


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


@app.get("/api/success-rates")
def get_success_rates(days: int = 30):
    """
    Calculate success rates for each (gateway, payment_mode) pair.
    Returns statistics for the last N days.
    """

    try:
        with get_db_connection() as connection:
            cursor = connection.cursor()

            # Calculate success rates grouped by gateway and payment_mode
            cursor.execute("""
                SELECT
                    gateway,
                    payment_mode,
                    COUNT(*) as total_transactions,
                    SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as successful_transactions,
                    SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) / COUNT(*) * 100 as success_rate,
                    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed_transactions,
                    SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending_transactions,
                    MAX(created_at) as last_transaction
                FROM transactions
                WHERE created_at >= DATE_SUB(NOW(), INTERVAL %s DAY)
                GROUP BY gateway, payment_mode
                ORDER BY success_rate DESC, total_transactions DESC
            """, (days,))

            results = cursor.fetchall()

            # Format results
            success_rates = []
            for row in results:
                success_rates.append({
                    "gateway": row['gateway'],
                    "payment_mode": row['payment_mode'],
                    "total_transactions": int(row['total_transactions']),
                    "successful_transactions": int(row['successful_transactions']),
                    "failed_transactions": int(row['failed_transactions']),
                    "pending_transactions": int(row['pending_transactions']),
                    "success_rate": round(float(row['success_rate']), 2),
                    "last_transaction": row['last_transaction'].isoformat() if row['last_transaction'] else None
                })

            return {
                "period_days": days,
                "total_combinations": len(success_rates),
                "success_rates": success_rates
            }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@app.get("/api/success-rates/{gateway}")
def get_gateway_success_rates(gateway: str, days: int = 30):
    """
    Get success rates for a specific gateway across all payment modes.
    """

    try:
        with get_db_connection() as connection:
            cursor = connection.cursor()

            cursor.execute("""
                SELECT
                    payment_mode,
                    COUNT(*) as total_transactions,
                    SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as successful_transactions,
                    SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) / COUNT(*) * 100 as success_rate
                FROM transactions
                WHERE gateway = %s AND created_at >= DATE_SUB(NOW(), INTERVAL %s DAY)
                GROUP BY payment_mode
                ORDER BY success_rate DESC
            """, (gateway, days))

            results = cursor.fetchall()

            rates = []
            for row in results:
                rates.append({
                    "payment_mode": row['payment_mode'],
                    "total_transactions": int(row['total_transactions']),
                    "successful_transactions": int(row['successful_transactions']),
                    "success_rate": round(float(row['success_rate']), 2)
                })

            return {
                "gateway": gateway,
                "period_days": days,
                "payment_modes": rates
            }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)