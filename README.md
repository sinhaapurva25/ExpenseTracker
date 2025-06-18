# Expense Tracker

A Python-based tool for analyzing bank statement PDFs and extracting transaction data.

## Overview

This tool helps you extract and analyze transaction data from password-protected bank statement PDFs. It processes the PDF files and converts the transaction data into a structured CSV format, making it easier to analyze your financial records.

## Features

- Extracts transaction data from password-protected PDF bank statements
- Processes multi-page PDFs
- Handles multiple tables within the same document
- Extracts key transaction information:
  - Value Date
  - Description
  - Withdrawal
  - Balance
- Automatically cleans and formats the data
- Exports results to CSV format

## Prerequisites

- Python 3.x
- Required Python packages:
  - PyPDF2
  - tabula-py
  - pandas

## Installation

1. Clone the repository:
```bash
git clone [repository-url]
cd ExpenseTracker
```

2. Install the required dependencies:
```bash
pip install PyPDF2 tabula-py pandas
```

## Usage

Run the PDF analyzer using the following command:

```bash
python src/main/pdf_analyzer.py "<path-to-pdf>" "<pdf-password>"
```

Example:
```bash
python src/main/pdf_analyzer.py "C:/myWork/ExpenseTracker/src/resources/Expenditures/SCB Acct Statement 2.pdf" "45711761125"
```

### Parameters

- `<path-to-pdf>`: Full path to the PDF file you want to analyze
- `<pdf-password>`: Password to open the PDF file

### Output

The program will:
1. Process the PDF file
2. Create a CSV file with the same name as the input PDF
3. Display the extracted data in the console
4. Save the structured data to the CSV file

## Project Structure

```
ExpenseTracker/
├── src/
│   ├── main/
│   │   └── pdf_analyzer.py
│   └── resources/
│       └── Expenditures/
│           └── [PDF files]
└── README.md
```

## Error Handling

The program includes error handling for:
- Missing PDF files
- Invalid passwords
- PDF processing errors
- Data extraction issues

## Contributing

Feel free to submit issues and enhancement requests!

## License

[Add your license information here]
