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
        return float(str(amount_str).replace(',', ''))
    except ValueError:
        return None

def clean_date(date_str):
    """Clean and standardize date format."""
    if pd.isna(date_str):
        return None
    date_str = str(date_str).strip()
    # Try to extract date in format "MMM DD" or "MMM DD YYYY"
    date_match = re.search(r'([A-Za-z]{3}\s+\d{1,2}(?:\s+\d{4})?)', date_str)
    if date_match:
        date_str = date_match.group(1)
        try:
            # Try parsing with year
            return datetime.strptime(date_str, '%b %d %Y').strftime('%Y-%m-%d')
        except ValueError:
            try:
                # Try parsing without year (assume current year)
                return datetime.strptime(date_str, '%b %d').strftime('%Y-%m-%d')
            except ValueError:
                return date_str
    return date_str

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
        # First verify if the PDF is password protected and can be opened
        reader = PdfReader(pdf_path)
        if reader.is_encrypted:
            reader.decrypt(password)
        
        # Extract tables from the PDF using tabula-py
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
        
        # Combine all tables if multiple tables are found
        if len(tables) > 0:
            combined_df = pd.concat(tables, ignore_index=True)
            
            # Print the actual columns found in the PDF
            print("\nColumns found in the PDF:")
            print(combined_df.columns.tolist())
            
            # Find the header row
            header_row_idx = None
            for i, row in combined_df.iterrows():
                row_str = ','.join([str(x) for x in row.values])
                if re.search(r'Date.*Value.*Description.*Balance', row_str, re.IGNORECASE):
                    header_row_idx = i
                    break
            
            if header_row_idx is not None:
                print(f"\nFound header row at index {header_row_idx}")
                # Use this row as header
                new_header = combined_df.iloc[header_row_idx].tolist()
                print(f"\nNew header: {new_header}")
                # Remove rows above header
                data_df = combined_df.iloc[header_row_idx+1:].copy()
                data_df.columns = new_header
                
                # Clean up column names
                data_df.columns = [str(col).strip() for col in data_df.columns]
                print(f"\nCleaned column names: {data_df.columns.tolist()}")
                
                # Extract transactions
                transactions = []
                current_transaction = None
                
                for _, row in data_df.iterrows():
                    # Check if this is a new transaction (has a date)
                    if pd.notna(row['Date   Value Description']) and re.search(r'[A-Za-z]{3}\s+\d{1,2}', str(row['Date   Value Description'])):
                        if current_transaction is not None:
                            transactions.append(current_transaction)
                        
                        # Start new transaction
                        current_transaction = {
                            'Value Date': row['Date   Value Description'],
                            'Description': '',
                            'Withdrawal': row['Withdrawal'] if 'Withdrawal' in row else None,
                            'Balance': row['Balance'] if 'Balance' in row else None
                        }
                    else:
                        # This is a continuation of the previous transaction
                        if current_transaction is not None:
                            # Append to description
                            if pd.notna(row['Date   Value Description']):
                                current_transaction['Description'] += ' ' + str(row['Date   Value Description'])
                            # Update withdrawal if present
                            if 'Withdrawal' in row and pd.notna(row['Withdrawal']):
                                current_transaction['Withdrawal'] = row['Withdrawal']
                            # Update balance if present
                            if 'Balance' in row and pd.notna(row['Balance']):
                                current_transaction['Balance'] = row['Balance']
                
                if current_transaction is not None:
                    transactions.append(current_transaction)
                
                # Convert to DataFrame
                final_df = pd.DataFrame(transactions)
                
                # Clean up the data
                if 'Value Date' in final_df.columns:
                    final_df['Value Date'] = final_df['Value Date'].apply(clean_date)
                if 'Withdrawal' in final_df.columns:
                    final_df['Withdrawal'] = final_df['Withdrawal'].apply(clean_amount)
                if 'Balance' in final_df.columns:
                    final_df['Balance'] = final_df['Balance'].apply(clean_amount)
                
                # Remove rows where all values are NaN
                final_df = final_df.dropna(how='all')
                
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
        # Save the extracted data to CSV
        output_path = Path(pdf_path).with_suffix('.csv')
        df.to_csv(output_path, index=False)
        print(f"\nData successfully extracted and saved to {output_path}")
        # Display first few rows
        print("\nFirst few rows of extracted data:")
        print(df.head())
    else:
        print("Failed to extract data from the PDF.")

if __name__ == "__main__":
    main()