-- Payment Orchestration System Database Schema
-- MySQL Database Setup

-- Create database if not exists
CREATE DATABASE IF NOT EXISTS payment_orchestration;

USE payment_orchestration;

-- Drop table if it exists (for clean setup)
DROP TABLE IF EXISTS transactions;

-- Create transactions table
CREATE TABLE transactions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    transaction_id VARCHAR(100) UNIQUE NOT NULL,
    gateway VARCHAR(50) NOT NULL,
    payment_mode VARCHAR(50) NOT NULL,
    base_amount DECIMAL(10, 2) NOT NULL,
    fee_amount DECIMAL(10, 2) NOT NULL,
    total_amount DECIMAL(10, 2) NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    gateway_transaction_id VARCHAR(200),
    gateway_response TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    -- Indexes for performance
    INDEX idx_transaction_id (transaction_id),
    INDEX idx_status (status),
    INDEX idx_gateway (gateway),
    INDEX idx_payment_mode (payment_mode)
) ENGINE=InnoDB;

-- Add comments to columns
ALTER TABLE transactions MODIFY COLUMN id INT AUTO_INCREMENT COMMENT 'Primary key';
ALTER TABLE transactions MODIFY COLUMN transaction_id VARCHAR(100) COMMENT 'Unique transaction identifier';
ALTER TABLE transactions MODIFY COLUMN gateway VARCHAR(50) COMMENT 'Payment gateway: Razorpay, PayU, Cashfree';
ALTER TABLE transactions MODIFY COLUMN payment_mode VARCHAR(50) COMMENT 'Payment mode: debit_card, credit_card, netbanking, upi';
ALTER TABLE transactions MODIFY COLUMN base_amount DECIMAL(10, 2) COMMENT 'Original transaction amount';
ALTER TABLE transactions MODIFY COLUMN fee_amount DECIMAL(10, 2) COMMENT 'Calculated fee amount';
ALTER TABLE transactions MODIFY COLUMN total_amount DECIMAL(10, 2) COMMENT 'Total amount (base + fee)';
ALTER TABLE transactions MODIFY COLUMN status VARCHAR(20) COMMENT 'Transaction status: pending, success, failed, cancelled';
ALTER TABLE transactions MODIFY COLUMN gateway_transaction_id VARCHAR(200) COMMENT 'Transaction ID from payment gateway';
ALTER TABLE transactions MODIFY COLUMN gateway_response TEXT COMMENT 'Response from payment gateway';
ALTER TABLE transactions MODIFY COLUMN created_at TIMESTAMP COMMENT 'Transaction creation timestamp';
ALTER TABLE transactions MODIFY COLUMN updated_at TIMESTAMP COMMENT 'Transaction update timestamp';

-- Insert sample data (optional - for testing)
INSERT INTO transactions (
    transaction_id, 
    gateway, 
    payment_mode, 
    base_amount, 
    fee_amount, 
    total_amount, 
    status
) VALUES
('transaction_001', 'Razorpay', 'upi', 1500.00, 0.00, 1500.00, 'success'),
('transaction_002', 'PayU', 'debit_card', 9300.00, 46.00, 9346.00, 'pending'),
('transaction_003', 'Cashfree', 'credit_card', 30000.00, 150.00, 30150.00, 'success');

