def test_parse_saas_contract():
    """Test parsing of a SaaS contract with specific format."""
    ocr_service = OCRService()
    
    # Sample contract text
    contract_text = '''Software as a Service (SaaS) Agreement
Contract Number: SAAS-2025-001

1. Parties of the Agreement
Provider: Taskly Inc., a corporation organized under the laws of Delaware,
with its principal place of business at 123 Innovation Drive, Wilmington, DE
19801.
Client: ABC Enterprises, a corporation organized under the laws of California,
with its principal place of business at 456 Market Street, San Francisco, CA
94105.

2. Effective Date and Expiration Date
Effective Date: January 1, 2025
Expiration Date: December 31, 2025

3. Payment Terms
Subscription Fee: $1,000 per month for up to 50 users.
Payment Terms: All payments are due within 15 days of the invoice date.
Payments shall be made via ACH transfer to the Provider's designated
account:
Bank Name: First National Bank
Account Number: 123456789
Routing Number: 987654321
Late Payment Interest Rate: 1.5% per month

4. Total Contract Value
Total Contract Value: $12,000

5. Description of Services
Provider agrees to provide Client access to the Taskly Project Management
Platform (the "Service") via the internet, subject to the terms and conditions of
this Agreement.'''

    # Parse the contract
    result = ocr_service._parse_contract_fields(contract_text)
    
    # Verify contract number
    assert result["contract_number"] == "SAAS-2025-001"
    
    # Verify parties
    assert len(result["parties"]) == 2
    vendor = next(p for p in result["parties"] if p["role"] == "vendor")
    buyer = next(p for p in result["parties"] if p["role"] == "buyer")
    
    assert vendor["name"] == "Taskly Inc."
    assert vendor["address"] == "123 Innovation Drive, Wilmington, DE 19801"
    assert buyer["name"] == "ABC Enterprises"
    assert buyer["address"] == "456 Market Street, San Francisco, CA 94105"
    
    # Verify dates
    assert result["effective_date"] == "January 1, 2025"
    assert result["expiration_date"] == "December 31, 2025"
    
    # Verify payment terms
    assert len(result["payment_terms"]) == 3
    assert "Subscription Fee: $1,000 per month for up to 50 users" in result["payment_terms"]
    assert any("15 days of the invoice date" in term for term in result["payment_terms"])
    assert any("1.5% per month" in term for term in result["payment_terms"])
    
    # Verify total value
    assert result["total_value"]["amount"] == 12000.0
    assert result["total_value"]["currency"] == "USD"
    
    # Verify items
    assert len(result["items"]) == 1
    assert result["items"][0]["name"] == "Taskly Project Management Platform"
    assert "via the internet" in result["items"][0]["description"] 