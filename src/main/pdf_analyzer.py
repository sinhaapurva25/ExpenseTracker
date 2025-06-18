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
        # Remove any currency symbols
        amount_str = re.sub(r'[^\d.-]', '', amount_str)
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
        if len(tables) > 0:
            combined_df = pd.concat(tables, ignore_index=True)
            print("\nColumns found in the PDF:")
            print(combined_df.columns.tolist())
            header_row_idx = None
            for i, row in combined_df.iterrows():
                row_str = ','.join([str(x) for x in row.values])
                if re.search(r'Date.*Value.*Description.*Balance', row_str, re.IGNORECASE):
                    header_row_idx = i
                    break
            if header_row_idx is not None:
                print(f"\nFound header row at index {header_row_idx}")
                new_header = combined_df.iloc[header_row_idx].tolist()
                print(f"\nNew header: {new_header}")
                data_df = combined_df.iloc[header_row_idx+1:].copy()
                data_df.columns = new_header
                data_df.columns = [str(col).strip() for col in data_df.columns]
                print(f"\nCleaned column names: {data_df.columns.tolist()}")
                transactions = []
                current_transaction = None
                # --- Chronological date logic ---
                month_map = {m: i for i, m in enumerate(['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'], 1)}
                prev_month = None
                prev_day = None
                year = 2024
                for idx, row in data_df.iterrows():
                    row_str = str(row['Date   Value Description'])
                    # Only match 'Month Day' (e.g., 'Jan 01')
                    match = re.search(r'([A-Za-z]{3})\s+(\d{1,2})', row_str)
                    found_date = None
                    if match:
                        month_str, day_str = match.groups()
                        month = month_map.get(month_str.capitalize())
                        if month is not None:  # Only proceed if we found a valid month
                            day = int(day_str)
                            if prev_month is not None and prev_day is not None:
                                # If month goes backward, increment year
                                if (month < prev_month) or (month == prev_month and day < prev_day):
                                    year += 1
                            prev_month = month
                            prev_day = day
                            found_date = f"{year}-{month:02d}-{day:02d}"
                    if found_date:
                        current_date = found_date
                    # Check if this row contains transaction data
                    has_transaction_data = (
                        pd.notna(row.get('Withdrawal')) or 
                        pd.notna(row.get('Balance')) or
                        (pd.notna(row['Date   Value Description']) and 
                         not re.search(r'CURRENCY|ACCOUNT|BRANCH|Date', row_str, re.IGNORECASE))
                    )
                    if has_transaction_data and found_date:
                        if current_transaction is not None:
                            transactions.append(current_transaction)
                        current_transaction = {
                            'Value Date': found_date,
                            'Description': row['Date   Value Description'],
                            'Withdrawal': row['Withdrawal'] if 'Withdrawal' in row else None,
                            'Balance': row['Balance'] if 'Balance' in row else None
                        }
                    elif current_transaction is not None:
                        if pd.notna(row['Date   Value Description']):
                            current_transaction['Description'] += ' ' + str(row['Date   Value Description'])
                        if 'Withdrawal' in row and pd.notna(row['Withdrawal']):
                            current_transaction['Withdrawal'] = row['Withdrawal']
                        if 'Balance' in row and pd.notna(row['Balance']):
                            current_transaction['Balance'] = row['Balance']
                if current_transaction is not None:
                    transactions.append(current_transaction)
                final_df = pd.DataFrame(transactions)
                if 'Description' in final_df.columns:
                    final_df['Description'] = final_df['Description'].apply(format_description)
                if 'Withdrawal' in final_df.columns:
                    final_df['Withdrawal'] = final_df['Withdrawal'].apply(clean_amount)
                if 'Balance' in final_df.columns:
                    final_df['Balance'] = final_df['Balance'].apply(clean_amount)
                final_df = final_df.dropna(how='all')
                if 'Value Date' in final_df.columns:
                    final_df = final_df.sort_values('Value Date', ascending=True)
                return final_df
            else:
                print("Could not find the transaction table header in the PDF.")
                return None
        else:
            print("No tables found in the PDF.")
            return None
    except Exception as e:
        print(f"Error processing PDF: {str(e)}")
        return None

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
        # Save the extracted data to CSV with timestamp to avoid permission issues
        output_path = Path(pdf_path).with_suffix('.csv')
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = output_path.parent / f"{output_path.stem}_processed_{timestamp}.csv"
        df.to_csv(output_path, index=False)
        print(f"\nData successfully extracted and saved to {output_path}")
        # Display first few rows
        print("\nFirst few rows of extracted data:")
        print(df.head(10))
        print(f"\nTotal transactions extracted: {len(df)}")
    else:
        print("Failed to extract data from the PDF.")

if __name__ == "__main__":
    main()