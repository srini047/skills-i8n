---
name: pdf-processing
description: Extract text and tables from PDF files, fill PDF forms, merge and split documents. Use when the user mentions PDFs, forms, document extraction, or needs to combine multiple PDF files.
license: Apache-2.0
metadata:
  author: example-org
  version: "1.0"
---

# PDF Processing Skill

## Overview

This skill enables working with PDF documents: extracting text, filling forms, merging files, and splitting pages.

## When to Use

Activate this skill when the user:
- Asks to read, extract, or summarize content from a PDF
- Needs to fill in a PDF form programmatically
- Wants to merge multiple PDFs into one document
- Needs to split a PDF into individual pages

## Step 1: Identify the Task

Determine which operation is needed:

| Task | Tool |
|------|------|
| Extract text | `pdfplumber` |
| Fill forms | `pypdf` |
| Merge files | `pypdf` |
| Split pages | `pypdf` |

## Step 2: Install Dependencies

```bash
pip install pdfplumber pypdf
```

## Step 3: Extract Text

```python
import pdfplumber

with pdfplumber.open("document.pdf") as pdf:
    for page in pdf.pages:
        text = page.extract_text()
        print(text)
```

## Step 4: Merge PDFs

```python
from pypdf import PdfWriter

writer = PdfWriter()
for filename in ["file1.pdf", "file2.pdf"]:
    writer.append(filename)

with open("merged.pdf", "wb") as output:
    writer.write(output)
```

## Edge Cases

- Password-protected PDFs require the password to be passed to the reader
- Scanned PDFs (image-based) require OCR — use `pytesseract` with `pdf2image`
- Very large PDFs should be processed page-by-page to avoid memory issues

## Notes

Always close file handles after processing. Use context managers (`with` statements) wherever possible.
