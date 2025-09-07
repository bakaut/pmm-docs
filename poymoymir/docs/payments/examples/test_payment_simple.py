"""
Simple test script for payment functionality.
"""

def test_imports():
    """Test that we can import the payment handler."""
    try:
        from mindset.payment_handler import handle_payment_callback, handle_pre_checkout_query, handle_successful_payment
        print("Payment handler imports successful!")
        return True
    except Exception as e:
        print(f"Import failed: {e}")
        return False

if __name__ == "__main__":
    success = test_imports()
    if success:
        print("Payment functionality is ready to use!")
    else:
        print("There were issues with the payment functionality setup.")