# Food Safety Analysis Dashboard

This project provides a comprehensive solution for analyzing food safety compliance through image analysis using AI. It includes both a command-line interface and a web-based dashboard for analyzing food safety checklists and images.

## Features

- **Data Processing Pipeline**:
  - Data trimming and preprocessing
  - Image categorization
  - AI-powered image analysis
- **Multiple Interfaces**:
  - Web-based Streamlit dashboard with interactive visualizations
  - Command-line interface for batch processing
- **Comprehensive Analysis**:
  - Compliance status evaluation
  - Severity level assessment
  - Image quality analysis
  - Detailed improvement suggestions
  - Tag-based categorization
- **Interactive Dashboard**:
  - Real-time progress tracking
  - Interactive charts and graphs
  - Filterable data views
  - Export capabilities

## Prerequisites

- Python 3.7 or higher
- OpenAI API key
- Required Python packages (see Installation section)

## Installation

1. Clone the repository
2. Navigate to the smalldataset directory
3. Install required packages:
```bash
pip install -r requirements.txt
```

Required packages:
- pandas>=1.5.0
- openpyxl>=3.0.0
- streamlit>=1.22.0
- openai>=1.0.0
- Pillow>=9.0.0
- requests>=2.28.0
- plotly>=5.13.0

## Usage

### Step 1: Data Trimming
First, run the data trimming script to preprocess your Excel file:
```bash
python trim_data.py
```
This will:
- Clean and format your input data
- Remove any invalid entries
- Prepare the data for categorization

### Step 2: Categorization
After trimming, categorize your data:
```bash
python categorize.py
```
This step will:
- Organize data by restaurant type
- Group similar items
- Prepare for analysis

### Step 3: Analysis

#### Web Dashboard (Recommended)

1. Start the Streamlit dashboard:
```bash
streamlit run streamlit_app.py
```

2. Open your web browser and navigate to the provided URL (typically http://localhost:8501)

3. In the dashboard:
   - Upload your processed Excel file
   - Enter your OpenAI API key
   - Select restaurants to analyze
   - Click "Start Analysis"
   - View results in interactive tabs:
     - Overview
     - Checklist Details
     - Quality Issues
     - Raw Data

#### Command Line Interface

1. Run the analysis script:
```bash
python simpleAnanlysis.py
```

2. Follow the prompts to:
   - Enter the path to your processed Excel file
   - Select restaurants to analyze
   - Enter your OpenAI API key

## Input Data Format

The Excel file should contain the following columns:
- `checklist_type`: Type of restaurant or vendor
- `question`: The food safety question being evaluated
- `upload_links` or `upload_links (images)`: JSON array of image URLs

## Output

The analysis generates:
1. Interactive visualizations in the dashboard
2. Excel file with detailed analysis results including:
   - Compliance status
   - Severity level
   - Image quality issues
   - Improvement suggestions
   - Tags
   - Quality assessment

## Error Handling

The system includes robust error handling for:
- Invalid image URLs
- API connection issues
- Data format inconsistencies
- Image quality problems

## Contributing

Feel free to submit issues and enhancement requests!

## License

This project is licensed under the MIT License - see the LICENSE file for details. 