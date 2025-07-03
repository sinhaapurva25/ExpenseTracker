import sys
import os
from PyPDF2 import PdfReader
import tabula
import pandas as pd
from pathlib import Path
import re
from datetime import datetime

def clean_amount(amount_str):
    """Clean and convert amount string to float."""
    if pd.isna(amount_str):
        return None
    try:
        # Remove commas and convert to float
        amount_str = str(amount_str).replace(',', '').strip()
        # Remove any currency symbols and extra spaces
        amount_str = re.sub(r'[^\d.-]', '', amount_str)
        # Handle negative amounts
        if amount_str.startswith('-'):
            return -float(amount_str[1:]) if amount_str[1:] else None
        return float(amount_str) if amount_str else None
    except ValueError:
        return None

def clean_date(date_str):
    """Clean and standardize date format."""
    if pd.isna(date_str):
        return None
    
    date_str = str(date_str).strip()
    
    # Try different date patterns
    patterns = [
        (r'(\d{2})[/-](\d{2})[/-](\d{4})', '%d/%m/%Y'),  # DD/MM/YYYY
        (r'(\d{2})[/-](\d{2})[/-](\d{2})', '%d/%m/%y'),  # DD/MM/YY
        (r'([A-Za-z]{3})\s+(\d{1,2})(?:\s+(\d{4}))?', '%b %d %Y'),  # MMM DD YYYY
        (r'(\d{1,2})\s+([A-Za-z]{3})(?:\s+(\d{4}))?', '%d %b %Y'),  # DD MMM YYYY
    ]
    
    for pattern, date_format in patterns:
        match = re.search(pattern, date_str)
        if match:
            try:
                date_str = match.group(0)
                # If year is not in the pattern, use current year
                if '%Y' not in date_format and len(match.groups()) == 2:
                    date_str += f" {datetime.now().year}"
                return datetime.strptime(date_str, date_format).strftime('%Y-%m-%d')
            except ValueError:
                continue
    
    # Try to extract date from description if it contains a date
    date_in_desc = re.search(r'(\d{1,2})\s+([A-Za-z]{3})', date_str)
    if date_in_desc:
        try:
            date_str = date_in_desc.group(0) + f" {datetime.now().year}"
            return datetime.strptime(date_str, '%d %b %Y').strftime('%Y-%m-%d')
        except ValueError:
            pass
    
    return None

def format_description(desc):
    """Format transaction description for better readability."""
    if pd.isna(desc):
        return None
    
    desc = str(desc).strip()
    
    # Handle UPI transactions
    if '/' in desc:
        parts = desc.split('/')
        if len(parts) > 1:
            # Format as: "Recipient Name (UPI ID) - Reference"
            recipient = parts[0].strip()
            upi_id = parts[1].strip() if len(parts) > 1 else ""
            reference = parts[-1].strip() if len(parts) > 2 else ""
            
            formatted = f"{recipient}"
            if upi_id:
                formatted += f" ({upi_id})"
            if reference:
                formatted += f" - {reference}"
            return formatted
    
    # Handle RTGS/NEFT transactions
    rtgs_match = re.search(r'(RTGS|NEFT)\s+(CRED|DEB)', desc, re.IGNORECASE)
    if rtgs_match:
        return desc
    
    # Handle other transactions
    return desc

def extract_withdrawal_amount(row_str, withdrawal_col_value, balance_col_value):
    """Extract withdrawal amount from row data, ensuring it's different from balance."""
    # First check the withdrawal column
    if pd.notna(withdrawal_col_value):
        withdrawal_amount = clean_amount(withdrawal_col_value)
        balance_amount = clean_amount(balance_col_value)
        
        # Only return withdrawal if it's different from balance and positive
        if withdrawal_amount is not None and withdrawal_amount > 0:
            if balance_amount is None or withdrawal_amount != balance_amount:
                return withdrawal_amount
    
    # Look for withdrawal patterns in the description
    # Common patterns: "WITHDRAWAL", "DEBIT", "PAYMENT", "PURCHASE"
    withdrawal_keywords = ['WITHDRAWAL', 'DEBIT', 'PAYMENT', 'PURCHASE', 'PAYTM', 'UPI', 'NEFT', 'RTGS']
    if any(keyword in row_str.upper() for keyword in withdrawal_keywords):
        # Look for amount patterns in the description
        amount_patterns = [
            r'(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',  # Numbers with commas and decimals
            r'(\d+\.\d{2})',  # Decimal amounts
            r'(\d+)',  # Whole numbers
        ]
        
        for pattern in amount_patterns:
            matches = re.findall(pattern, row_str)
            for match in matches:
                amount = clean_amount(match)
                balance_amount = clean_amount(balance_col_value)
                if amount is not None and amount > 0:
                    if balance_amount is None or amount != balance_amount:
                        return amount
    
    return None

def extract_deposit_amount(row_str, deposit_col_value, balance_col_value):
    """Extract deposit amount from row data, ensuring it's different from balance."""
    # First check the deposit column
    if pd.notna(deposit_col_value):
        deposit_amount = clean_amount(deposit_col_value)
        balance_amount = clean_amount(balance_col_value)
        
        # Only return deposit if it's different from balance and positive
        if deposit_amount is not None and deposit_amount > 0:
            if balance_amount is None or deposit_amount != balance_amount:
                return deposit_amount
    
    # Look for deposit patterns in the description
    # Common patterns: "CREDIT", "DEPOSIT", "CHEQUE", "NEFT CREDIT", "RTGS CREDIT"
    deposit_keywords = ['CREDIT', 'DEPOSIT', 'CHEQUE', 'NEFT CREDIT', 'RTGS CREDIT', 'SALARY', 'REFUND']
    if any(keyword in row_str.upper() for keyword in deposit_keywords):
        # Look for amount patterns in the description
        amount_patterns = [
            r'(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',  # Numbers with commas and decimals
            r'(\d+\.\d{2})',  # Decimal amounts
            r'(\d+)',  # Whole numbers
        ]
        
        for pattern in amount_patterns:
            matches = re.findall(pattern, row_str)
            for match in matches:
                amount = clean_amount(match)
                balance_amount = clean_amount(balance_col_value)
                if amount is not None and amount > 0:
                    if balance_amount is None or amount != balance_amount:
                        return amount
    
    return None

def extract_bank_statement(pdf_path, password):
    """
    Extract table data from a password-protected PDF bank statement.
    Args:
        pdf_path (str): Path to the PDF file
        password (str): Password for the PDF file
    Returns:
        pandas.DataFrame: Extracted table data
    """
    try:
        reader = PdfReader(pdf_path)
        if reader.is_encrypted:
            reader.decrypt(password)
        print("\nExtracting tables from PDF...")
        tables = tabula.read_pdf(
            pdf_path,
            pages='all',
            password=password,
            multiple_tables=True,
            guess=True,
            pandas_options={'dtype': str}
        )
        print(f"\nFound {len(tables)} tables in the PDF")
        # Debug: Print column names for the first 30 tables
        for i, table in enumerate(tables[:30]):
            print(f"Table {i} columns: {list(table.columns)}")
        if len(tables) > 0:
            # Standard column names we want
            standard_cols = {
                'date_desc': ['date   value description', 'date', 'value date', 'description'],
                'deposit': ['cheque deposit', 'deposit', 'credit', 'deposits'],
                'withdrawal': ['withdrawal', 'debit', 'payment', 'withdrawals'],
                'balance': ['balance', 'closing balance', 'available balance']
            }
            
            all_transactions = []
            month_map = {m: i for i, m in enumerate(['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'], 1)}
            prev_month = None
            prev_day = None
            year = 2024
            
            for table in tables:
                df = table.copy()
                df.columns = [str(col).strip().lower() for col in df.columns]
                col_map = {}
                for key, options in standard_cols.items():
                    for col in df.columns:
                        if any(opt in col for opt in options):
                            col_map[key] = col
                            break
                # Skip tables that don't have at least date/desc and balance
                if 'date_desc' not in col_map or 'balance' not in col_map:
                    continue
                for idx, row in df.iterrows():
                    row_str = str(row[col_map['date_desc']])
                    match = re.search(r'([A-Za-z]{3})\s+(\d{1,2})', row_str)
                    found_date = None
                    if match:
                        month_str, day_str = match.groups()
                        month = month_map.get(month_str.capitalize())
                        if month is not None:
                            day = int(day_str)
                            if prev_month is not None and prev_day is not None:
                                if (month < prev_month) or (month == prev_month and day < prev_day):
                                    year += 1
                            prev_month = month
                            prev_day = day
                            found_date = f"{year}-{month:02d}-{day:02d}"
                    if found_date:
                        current_date = found_date
                    # Filtering
                    has_transaction_data = (
                        (col_map.get('withdrawal') and pd.notna(row.get(col_map['withdrawal']))) or
                        (col_map.get('deposit') and pd.notna(row.get(col_map['deposit']))) or
                        pd.notna(row.get(col_map['balance'])) or
                        (pd.notna(row.get(col_map['date_desc'])) and not re.search(r'CURRENCY|ACCOUNT|BRANCH|Date|STATEMENT|NOMINEE|ADDRESS|IFSC|MICR|Phone|Brought Forward|ABR Complex|EPIP Zone|Whitefield|Bengaluru|Karnataka|560066|560036004|9036002402', row_str, re.IGNORECASE))
                    )
                    desc_str = str(row.get(col_map['date_desc'], ''))
                    if re.search(r'STATEMENT DATE|CURRENCY|ACCOUNT TYPE|ACCOUNT NO|NOMINEE REGISTERED|BRANCH ADDRESS|ABR Complex|EPIP Zone|Whitefield|Bengaluru|Karnataka|560066|IFSC|MICR CODE|Phone No|Balance Brought Forward', desc_str, re.IGNORECASE):
                        has_transaction_data = False
                    if has_transaction_data and found_date:
                        deposit_amount = clean_amount(row.get(col_map.get('deposit'), None)) if col_map.get('deposit') else None
                        withdrawal_amount = clean_amount(row.get(col_map.get('withdrawal'), None)) if col_map.get('withdrawal') else None
                        balance_amount = clean_amount(row.get(col_map.get('balance'), None)) if col_map.get('balance') else None
                        all_transactions.append({
                            'Value Date': found_date,
                            'Description': row.get(col_map['date_desc'], None),
                            'Deposit': deposit_amount,
                            'Withdrawal': withdrawal_amount,
                            'Balance': balance_amount
                        })
            final_df = pd.DataFrame(all_transactions)
            if 'Description' in final_df.columns:
                final_df['Description'] = final_df['Description'].apply(clean_description)
                final_df['Description'] = final_df['Description'].apply(format_description)
            if 'Deposit' in final_df.columns:
                final_df['Deposit'] = final_df['Deposit'].apply(clean_amount)
            if 'Withdrawal' in final_df.columns:
                final_df['Withdrawal'] = final_df['Withdrawal'].apply(clean_amount)
            if 'Balance' in final_df.columns:
                final_df['Balance'] = final_df['Balance'].apply(clean_amount)
            column_order = ['Value Date', 'Description', 'Deposit', 'Withdrawal', 'Balance']
            final_df = final_df.reindex(columns=column_order, fill_value=None)
            final_df = final_df.dropna(how='all')
            if 'Value Date' in final_df.columns:
                final_df = final_df.sort_values('Value Date', ascending=True)
            return final_df
        else:
            print("No tables found in the PDF.")
            return None
    except Exception as e:
        print(f"Error processing PDF: {str(e)}")
        return None

def clean_description(desc):
    """Clean description by removing account information and header text."""
    if pd.isna(desc):
        return None
    
    desc = str(desc).strip()
    
    # Remove account information patterns
    patterns_to_remove = [
        r'STATEMENT DATE.*?Phone No\.: \d+',
        r'CURRENCY.*?Phone No\.: \d+',
        r'ACCOUNT TYPE.*?Phone No\.: \d+',
        r'ACCOUNT NO.*?Phone No\.: \d+',
        r'NOMINEE REGISTERED.*?Phone No\.: \d+',
        r'BRANCH ADDRESS.*?Phone No\.: \d+',
        r'ABR Complex.*?Phone No\.: \d+',
        r'EPIP Zone.*?Phone No\.: \d+',
        r'Whitefield.*?Phone No\.: \d+',
        r'Bengaluru.*?Phone No\.: \d+',
        r'Karnataka.*?Phone No\.: \d+',
        r'560066.*?Phone No\.: \d+',
        r'IFSC.*?Phone No\.: \d+',
        r'MICR CODE.*?Phone No\.: \d+',
        r'Phone No\.: \d+',
        r'Balance Brought Forward',
        r'Date   Value Description Date',
    ]
    
    for pattern in patterns_to_remove:
        desc = re.sub(pattern, '', desc, flags=re.IGNORECASE | re.DOTALL)
    
    # Clean up extra whitespace
    desc = re.sub(r'\s+', ' ', desc).strip()
    
    return desc if desc else None

def main():
    if len(sys.argv) != 3:
        print("Usage: python pdf_analyzer.py <pdf_path> <password>")
        sys.exit(1)
    pdf_path = sys.argv[1]
    password = sys.argv[2]
    if not os.path.exists(pdf_path):
        print(f"Error: PDF file not found at {pdf_path}")
        sys.exit(1)
    # Extract the data
    df = extract_bank_statement(pdf_path, password)
    if df is not None:
        # Save the extracted data to CSV with original name
        output_path = Path(pdf_path).with_suffix('.csv')
        try:
            df.to_csv(output_path, index=False)
            print(f"\nData successfully extracted and saved to {output_path}")
        except PermissionError:
            # If permission denied, try with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = output_path.parent / f"{output_path.stem}_processed_{timestamp}.csv"
            df.to_csv(output_path, index=False)
            print(f"\nData successfully extracted and saved to {output_path}")
            print("Note: Original filename was in use, so timestamp was added.")
        
        # Display first few rows
        print("\nFirst few rows of extracted data:")
        print(df.head(10))
        print(f"\nTotal transactions extracted: {len(df)}")
    else:
        print("Failed to extract data from the PDF.")

if __name__ == "__main__":
    main()