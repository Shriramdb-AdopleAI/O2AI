# Workflow Change: Manual Low-Confidence Processing

## Overview
Changed the workflow so that low-confidence field analysis is **manual** instead of automatic.

## Previous Workflow (Automatic)
1. Upload file → Click "Process"
2. Azure Document Intelligence extracts OCR + key-value pairs
3. **Automatically** analyzes low-confidence fields (<95%) using GPT-4 Vision
4. Shows results with auto-corrections already applied

## New Workflow (Manual - On Demand)
1. Upload file → Click "Process"
2. Azure Document Intelligence extracts OCR + key-value pairs
3. **Identifies** low-confidence fields (<95%) but does NOT analyze them yet
4. Results page shows **"Process Low Score"** button (amber/yellow color)
5. User clicks **"Process Low Score"** button
6. GPT-4 Vision analyzes the low-confidence fields with the original image
7. Shows auto-corrections and suggestions

## Changes Made

### Backend (`/backend/api/router.py`)

#### 1. Single File Processing (`process_enhanced_ocr`)
- **Removed**: Automatic low-confidence analysis (lines 232-268)
- **Added**: Identification of low-confidence pairs only
- **Changed**: Response now includes `low_confidence_data` instead of `low_confidence_analysis`

```python
# New response structure
"low_confidence_data": {
    "has_low_confidence_pairs": True/False,
    "low_confidence_pairs": {...},
    "low_confidence_scores": {...},
    "source_file_base64": "...",  # Pre-encoded for later use
    "source_file_content_type": "application/pdf",
    "count": 3
}
```

#### 2. Batch Processing (`process_enhanced_batch_ocr`)
- Same changes as single file processing
- Each file in batch gets its own `low_confidence_data`

#### 3. Celery Tasks (Async Processing)
- **`process_document`** - Updated for manual workflow
- **`process_bulk_file`** - Updated for manual workflow
- Both tasks now only identify low-confidence pairs
- Store base64 file data for later manual analysis
- Return `low_confidence_data` instead of `low_confidence_analysis`

#### 4. Existing Endpoint (No Changes)
- `/api/v1/ocr/enhanced/analyze-low-confidence` - Already exists, no changes needed
- This endpoint is called when user clicks "Process Low Score" button

### Frontend (`/frontend/src/components/EnhancedOCRResults.jsx`)

#### 1. Added "Process Low Score" Button
- **Location**: In the Key-Value Pairs section, after Edit/Save/Cancel buttons
- **Appearance**: Amber/yellow color with Brain icon
- **Visibility**: Only shows when:
  - There are low-confidence pairs (<95%)
  - Analysis has not been performed yet
- **States**:
  - Normal: "Process Low Score" with Brain icon
  - Loading: "Analyzing..." with spinner

#### 2. Updated `analyzeLowConfidencePairs` Function
- **New**: Checks for `result.low_confidence_data` first
- **Benefit**: Uses pre-computed data from backend (including base64 file)
- **Fallback**: If `low_confidence_data` not available, uses old method

```javascript
if (result.low_confidence_data) {
  // Use pre-computed data - faster, no need to download file
  lowConfidencePairs = result.low_confidence_data.low_confidence_pairs;
  sourceFileBase64 = result.low_confidence_data.source_file_base64;
} else {
  // Fallback: Download file from blob storage (old workflow)
}
```

## Benefits

1. **Faster Initial Processing**: No automatic GPT-4 Vision calls during upload
2. **Cost Savings**: Only analyze when user requests it
3. **User Control**: User decides which files need low-confidence review
4. **Better UX**: Clear indication of which files have low-confidence fields
5. **Efficient**: File is already base64-encoded during initial processing

## User Experience

### Before (Automatic)
```
Upload → Process → Wait (OCR + Auto-Analysis) → Results with corrections
```

### After (Manual)
```
Upload → Process → Wait (OCR only) → Results
                                        ↓
                            See "Process Low Score" button
                                        ↓
                            Click button → GPT-4 Vision analysis
                                        ↓
                            See corrections and suggestions
```

## Technical Details

### Low-Confidence Detection
- Confidence threshold: **95%**
- Fields with confidence < 0.95 are flagged
- Confidence can be in decimal (0.95) or percentage (95) format

### GPT-4 Vision Analysis
- Uses the original source file image
- Provides:
  - Extraction status (correct/incorrect/incomplete/missing)
  - Suggested corrected value
  - Issues found
  - Explanation

### Data Flow
1. **Initial Processing**: File → Azure DI → Extract → Store base64
2. **Manual Analysis**: Click button → Send base64 + low-conf pairs → GPT-4 Vision → Corrections

## Testing

To test the new workflow:

1. Upload a file with some low-quality text (will have <95% confidence)
2. Click "Process Files"
3. Wait for results
4. Look for amber "Process Low Score" button in results
5. Click the button
6. Wait for GPT-4 Vision analysis
7. See corrections displayed below each low-confidence field

## Files Modified

- `/backend/api/router.py` - Backend processing logic (single & batch)
- `/backend/core/celery_tasks.py` - Celery async tasks (process_document, process_bulk_file)
- `/frontend/src/components/EnhancedOCRResults.jsx` - Results display and "Process Low Score" button
