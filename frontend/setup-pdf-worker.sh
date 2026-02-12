#!/bin/bash
# Setup script for Linux/Mac to copy PDF.js worker file to public folder
# This is required for PDF highlighting to work

echo "Setting up PDF.js worker file..."

if [ ! -f "node_modules/pdfjs-dist/build/pdf.worker.min.mjs" ]; then
    echo "Error: PDF.js worker file not found in node_modules"
    echo "Please run 'npm install' first to install dependencies."
    exit 1
fi

cp "node_modules/pdfjs-dist/build/pdf.worker.min.mjs" "public/pdf.worker.min.mjs"

if [ $? -eq 0 ]; then
    echo "Successfully copied PDF.js worker file to public folder"
else
    echo "Error copying PDF.js worker file"
    exit 1
fi

