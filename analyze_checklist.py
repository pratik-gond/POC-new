import pandas as pd
import json
import requests
from PIL import Image
import tempfile
import io
from io import BytesIO
from black_image_detector import is_single_color_image
from openai import OpenAI
import os
import datetime
import time
from collections import Counter
import re

# Add at the top of the file after imports
skip_count = 0  # Global counter for skipped OpenAI analyses

# Function to load data from Excel with specific sheet
def load_data(file_path):
    try:
        df = pd.read_excel(file_path, sheet_name="Sheet1")
        return df
    except Exception as e:
        print(f"Error loading data from sheet 'HB-Categorized-Main-Sheet': {e}")
        try:
            # Try to list available sheets
            xls = pd.ExcelFile(file_path)
            print(f"Available sheets in the Excel file: {xls.sheet_names}")
            return None
        except Exception as sub_e:
            print(f"Error opening Excel file: {sub_e}")
            return None

# Function to extract unique cafes and vendors
def identify_unique_locations(df):
    # Separate cafes and vendors
    cafes_df = df[df['checklist_type'] == 'cafe']
    vendors_df = df[df['checklist_type'] == 'vendor']
    
    unique_cafes = cafes_df['location_name'].unique()
    unique_vendors = vendors_df['location_name'].unique()
    
    # Count entries for each location
    cafe_counts = cafes_df['location_name'].value_counts().to_dict()
    vendor_counts = vendors_df['location_name'].value_counts().to_dict()
    
    print(f"Found {len(unique_cafes)} unique cafes:")
    for i, cafe in enumerate(unique_cafes):
        count = cafe_counts[cafe]
        print(f"{i+1}. {cafe} ({count} entries)")
    
    print(f"\nFound {len(unique_vendors)} unique vendors:")
    for i, vendor in enumerate(unique_vendors):
        count = vendor_counts[vendor]
        print(f"{i+1}. {vendor} ({count} entries)")
    
    return unique_cafes, unique_vendors

def safe_delete_file(file_path, max_retries=3, delay=0.5):
    """Safely delete a file with retries and delay"""
    for attempt in range(max_retries):
        try:
            if os.path.exists(file_path):
                os.unlink(file_path)
            return True
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(delay)
            else:
                print(f"Could not delete temporary file {file_path}: {str(e)}")
                return False

# Improved function to get image URL (based on analysis_5.py)
def get_image_url(row):
    try:
        if 'upload_links' not in row or pd.isna(row['upload_links']) or not row['upload_links']:
            return None
        
        # Handle different representations of the URL
        url_data = row['upload_links']
        
        # If it's already a string, process it
        if isinstance(url_data, str):
            # Remove any surrounding quotes that might be present
            cleaned_url = url_data.strip('"\'')
            
            # Try parsing as JSON if it looks like JSON
            if (cleaned_url.startswith('[') and cleaned_url.endswith(']')) or (cleaned_url.startswith('{') and cleaned_url.endswith('}')):
                try:
                    parsed_data = json.loads(cleaned_url)
                    if isinstance(parsed_data, list) and parsed_data:
                        return parsed_data[0]
                    elif isinstance(parsed_data, dict) and 'url' in parsed_data:
                        return parsed_data['url']
                except json.JSONDecodeError:
                    # Not valid JSON, treat as direct URL
                    pass
            
            # Direct URL (clean it)
            return cleaned_url
            
    except Exception as e:
        print(f"Error parsing upload_links: {e}")
        return None

# Prompt templates for different categories
def get_prompt_template(categories):
    # Convert string representation of categories to list if needed
    if isinstance(categories, str):
        try:
            categories = json.loads(categories)
        except json.JSONDecodeError:
            try:
                # Try to handle formats like [Hygiene & Cleanliness, Inventory & Storage]
                categories = re.findall(r'\[(.*?)\]', categories)
                if categories:
                    categories = [c.strip() for c in categories[0].split(',')]
                else:
                    categories = [categories]
            except:
                categories = [categories]
    
    # Define prompt templates for different categories
    templates = {
        "Hygiene & Cleanliness": """
            You are a food safety manager analyzing a cleanliness image for compliance.
            
            Question to evaluate: {question}
            
            IMPORTANT INSTRUCTIONS FOR IMAGE QUALITY AND COMPLIANCE:
            1. First, assess if the image is too dark or too blurry. Include this in your analysis.
            2. CRITICAL: If the question specifically asks for or expects a blank photo, empty area, or clean surface, 
               AND the image shows an appropriate empty/blank/dark area, this should be marked as "Yes" (compliant).
            3. A dark or blurry image should ONLY be marked as compliant if:
               - The question explicitly asks for documentation of an empty, vacant, or clear area, OR
               - The question is checking if something is properly put away/not present, AND
               - The darkness or blurriness doesn't prevent you from determining compliance

            
            Analyze the image and provide a detailed evaluation in JSON format with the following fields:
            1. "criteria_met": "Yes" if compliant with cleanliness standards, "No" if not compliant. If you feel a question cannot be answered just using the image and needs an additional textual or other information mark it as unable to determine.
            2. "explanation": Detailed explanation of your assessment (2-3 sentences)
            3. "improvements": Specific actionable cleaning recommendations if issues are found
            4. "severity": Categorize as "Critical", "Major", "Minor", or "None" based on the cleanliness impact
            5. "image_quality_issues": List of quality issues in the image (e.g., ["too_dark", "too_blurry"], or ["none"])
            6. "quality_assessment": Brief comment on how image quality affected your assessment
            7. "tags": A list of 3-5 tags related to cleanliness and hygiene observations
        """,
        
        "Food Safety Compliance": """
            You are a food safety compliance auditor analyzing an image for food safety standards.
            
            Question to evaluate: {question}
            
            IMPORTANT INSTRUCTIONS FOR IMAGE QUALITY AND COMPLIANCE:
            1. First, assess if the image is too dark or too blurry. Include this in your analysis.
            2. CRITICAL: If the question specifically asks for or expects a blank photo, empty area, or clean surface, 
               AND the image shows an appropriate empty/blank/dark area, this should be marked as "Yes" (compliant).
            3. A dark or blurry image should ONLY be marked as compliant if:
               - The question explicitly asks for documentation of an empty, vacant, or clear area, OR
               - The question is checking if something is properly put away/not present, AND
               - The darkness or blurriness doesn't prevent you from determining compliance
            
            Analyze the image and provide a detailed evaluation in JSON format with the following fields:
            1. "criteria_met": "Yes" if compliant with food safety standards, "No" if not compliant. If you feel a question cannot be answered just using the image and needs an additional textual or other information mark it as unable to determine.
            2. "explanation": Detailed explanation of your assessment (2-3 sentences)
            3. "improvements": Specific actionable food safety recommendations if issues are found
            4. "severity": Categorize as "Critical", "Major", "Minor", or "None" based on the food safety impact
            5. "image_quality_issues": List of quality issues in the image (e.g., ["too_dark", "too_blurry"], or ["none"])
            6. "quality_assessment": Brief comment on how image quality affected your assessment
            7. "tags": A list of 3-5 tags related to food safety observations
        """,
        
        "Inventory & Storage": """
            You are an inventory and storage management specialist analyzing an image for compliance.
            
            Question to evaluate: {question}
            
            IMPORTANT INSTRUCTIONS FOR IMAGE QUALITY AND COMPLIANCE:
            1. First, assess if the image is too dark or too blurry. Include this in your analysis.
            2. CRITICAL: If the question specifically asks for or expects a blank photo, empty area, or clean surface, 
               AND the image shows an appropriate empty/blank/dark area, this should be marked as "Yes" (compliant).
            3. A dark or blurry image should ONLY be marked as compliant if:
               - The question explicitly asks for documentation of an empty, vacant, or clear area, OR
               - The question is checking if something is properly put away/not present, AND
               - The darkness or blurriness doesn't prevent you from determining compliance
            
            Analyze the image and provide a detailed evaluation in JSON format with the following fields:
            1. "criteria_met": "Yes" if compliant with inventory/storage standards, "No" if not compliant. If you feel a question cannot be answered just using the image and needs an additional textual or other information mark it as unable to determine.
            2. "explanation": Detailed explanation of your assessment (2-3 sentences)
            3. "improvements": Specific actionable storage recommendations if issues are found
            4. "severity": Categorize as "Critical", "Major", "Minor", or "None" based on the inventory impact
            5. "image_quality_issues": List of quality issues in the image (e.g., ["too_dark", "too_blurry"], or ["none"])
            6. "quality_assessment": Brief comment on how image quality affected your assessment
            7. "tags": A list of 3-5 tags related to inventory and storage observations
        """,
        
        "Hardware (Assets) & Other Equipment": """
            You are a equipment and asset management specialist analyzing an image for compliance.
            
            Question to evaluate: {question}
            
            IMPORTANT INSTRUCTIONS FOR IMAGE QUALITY AND COMPLIANCE:
            1. First, assess if the image is too dark or too blurry. Include this in your analysis.
            2. CRITICAL: If the question specifically asks for or expects a blank photo, empty area, or clean surface, 
               AND the image shows an appropriate empty/blank/dark area, this should be marked as "Yes" (compliant).
            3. A dark or blurry image should ONLY be marked as compliant if:
               - The question explicitly asks for documentation of an empty, vacant, or clear area, OR
               - The question is checking if something is properly put away/not present, AND
               - The darkness or blurriness doesn't prevent you from determining compliance
            
            Analyze the image and provide a detailed evaluation in JSON format with the following fields:
            1. "criteria_met": "Yes" if compliant with equipment standards, "No" if not compliant. If you feel a question cannot be answered just using the image and needs an additional textual or other information mark it as unable to determine.
            2. "explanation": Detailed explanation of your assessment (2-3 sentences)
            3. "improvements": Specific actionable equipment recommendations if issues are found
            4. "severity": Categorize as "Critical", "Major", "Minor", or "None" based on the equipment impact
            5. "image_quality_issues": List of quality issues in the image (e.g., ["too_dark", "too_blurry"], or ["none"])
            6. "quality_assessment": Brief comment on how image quality affected your assessment
            7. "tags": A list of 3-5 tags related to equipment and hardware observations
        """,
        
        "Documentation & Records": """
            You are a documentation and record-keeping specialist analyzing an image for compliance.
            
            Question to evaluate: {question}
            
            IMPORTANT INSTRUCTIONS FOR IMAGE QUALITY AND COMPLIANCE:
            1. First, assess if the image is too dark or too blurry. Include this in your analysis.
            2. CRITICAL: If the question specifically asks for or expects a blank photo, empty area, or clean surface, 
               AND the image shows an appropriate empty/blank/dark area, this should be marked as "Yes" (compliant).
            3. A dark or blurry image should ONLY be marked as compliant if:
               - The question explicitly asks for documentation of an empty, vacant, or clear area, OR
               - The question is checking if something is properly put away/not present, AND
               - The darkness or blurriness doesn't prevent you from determining compliance
            
            Analyze the image and provide a detailed evaluation in JSON format with the following fields:
            1. "criteria_met": "Yes" if compliant with documentation standards, "No" if not compliant. If you feel a question cannot be answered just using the image and needs an additional textual or other information mark it as unable to determine.
            2. "explanation": Detailed explanation of your assessment (2-3 sentences)
            3. "improvements": Specific actionable documentation recommendations if issues are found
            4. "severity": Categorize as "Critical", "Major", "Minor", or "None" based on the documentation impact
            5. "image_quality_issues": List of quality issues in the image (e.g., ["too_dark", "too_blurry"], or ["none"])
            6. "quality_assessment": Brief comment on how image quality affected your assessment
            7. "tags": A list of 3-5 tags related to documentation and record observations
        """
    }
    
    # Default template for cases where no matching category is found
    default_template = """
        You are a food safety inspector analyzing an image for compliance.
        
        Question to evaluate: {question}
        
        IMPORTANT INSTRUCTIONS FOR IMAGE QUALITY AND COMPLIANCE:
        1. First, assess if the image is too dark or too blurry. Include this in your analysis.
        2. CRITICAL: If the question specifically asks for or expects a blank photo, empty area, or clean surface, 
           AND the image shows an appropriate empty/blank/dark area, this should be marked as "Yes" (compliant).
        3. A dark or blurry image should ONLY be marked as compliant if:
           - The question explicitly asks for documentation of an empty, vacant, or clear area, OR
           - The question is checking if something is properly put away/not present, AND
           - The darkness or blurriness doesn't prevent you from determining compliance
        4. Remember: If the question specifically says to click a blank image if not applicable or a clear image, 
           this should be marked compliant. A dark image for a question that doesn't mention the image 
           to be dark or blank implies non-compliance. Make the compliance_status as a No in that case.
        
        Analyze the image and provide a detailed evaluation in JSON format with the following fields:
        1. "criteria_met": "Yes" if compliant with standards, "No" if not compliant. If you feel a question cannot be answered just using the image and needs an additional textual or other information mark it as unable to determine.
        2. "explanation": Detailed explanation of your assessment (2-3 sentences)
        3. "improvements": Specific actionable recommendations if issues are found
        4. "severity": Categorize as "Critical", "Major", "Minor", or "None" based on the impact
        5. "image_quality_issues": List of quality issues in the image (e.g., ["too_dark", "too_blurry"], or ["none"])
        6. "quality_assessment": Brief comment on how image quality affected your assessment
        7. "tags": A list of 3-5 tags related to relevant observations
    """
    
    # Find the first matching category in the templates
    for category in categories:
        category_clean = category.strip() if isinstance(category, str) else str(category)
        for template_key in templates:
            if template_key in category_clean:
                return templates[template_key]
    
    # If no matching category is found, return the default template
    return default_template

# Function to analyze an image using OpenAI
def analyze_image(client, row, max_retries=3):
    # Get the question
    question = row['question']
    
    # Skip if no image is provided
    if pd.isna(row['upload_links']) or not row['upload_links']:
        return {
            "criteria_met": "Unable to determine",
            "explanation": f"No image provided for the question: {question}",
            "improvements": "Ensure images are uploaded to verify compliance.",
            "severity": "Unknown",
            "image_quality_issues": ["no_image"],
            "quality_assessment": "No image available for assessment",
            "tags": ["missing_data", "no_visual_evidence", "incomplete_submission"]
        }
    
    # Get image URL
    image_url = get_image_url(row)
    if not image_url:
        return {
            "criteria_met": "Unable to determine",
            "explanation": f"Could not extract a valid image URL for question: {question}",
            "improvements": "Check that image URLs are properly formatted and accessible.",
            "severity": "Unknown",
            "image_quality_issues": ["invalid_url"],
            "quality_assessment": "No valid image URL found",
            "tags": ["technical_issue", "url_error", "data_issue"]
        }
    
    # Get the appropriate prompt template based on categories
    categories = row.get('categorization', [])
    prompt_template = get_prompt_template(categories)
    prompt = prompt_template.format(question=question)

    def blankallowdquestion(question): #this function is to check if the question allows a blank photo question
        if "Please click a blank photo if not applicable" in question:
            return True
        else:
            return False
    
    # Implement retry logic with proper error handling
    retries = 0
    while retries < max_retries:
        try:
            # First check if the image is accessible
            print(f"Testing image accessibility for {image_url}...")
            response = requests.get(image_url, timeout=10)
            response.raise_for_status()  # Will raise an exception for HTTP errors
            print("Image is accessible.")

            # Check if the image is a single color
            # Save image temporarily for analysis
            temp_image = BytesIO(response.content)
            img = Image.open(temp_image)
            temp_file = None
            
            # Create temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as temp_file:
                img.save(temp_file.name)
                temp_file_path = temp_file.name

            # Check if image is single color
            if not is_single_color_image(temp_file_path) or blankallowdquestion(question):
                global skip_count
                skip_count += 1
                print("Image is a single color. Skipping OpenAI analysis.")
                
                return {
                        "criteria_met": "Unable to determine",
                        "explanation": "Image is a single color and cannot be analyzed.",
                        "improvements": "Check the image for compliance.",
                        "severity": "Unknown",
                        "image_quality_issues": ["too_dark"],
                        "quality_assessment": "Could not access image for assessment",
                        "tags": ["too_dark"]
                }
            else:
                print("Image is not a single color. Proceeding with OpenAI analysis.")
                # Now proceed with OpenAI analysis
                print("Sending image to OpenAI for analysis...")
                response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": image_url,
                                },
                            },
                        ],
                    }],
                    response_format={"type": "json_object"}
                )
                
            # Parse the result
            result = json.loads(response.choices[0].message.content)
            print("Analysis completed successfully.")

            # Clean up temporary file
            if temp_file_path and os.path.exists(temp_file_path):
                safe_delete_file(temp_file_path)

            return result
            
                
            
            
            
        except requests.exceptions.RequestException as e:
            print(f"Error accessing image: {e}")
            retries += 1
            if retries < max_retries:
                print(f"Retrying in {2**retries} seconds...")
                time.sleep(2**retries)  # Exponential backoff
            else:
                print(f"Failed to access image after {max_retries} attempts.")
                return {
                    "criteria_met": "Unable to determine",
                    "explanation": f"Could not access the image after {max_retries} attempts: {str(e)}",
                    "improvements": "Ensure the image URL is accessible and try again.",
                    "severity": "Unknown",
                    "image_quality_issues": ["access_error"],
                    "quality_assessment": "Could not access image for assessment",
                    "tags": ["technical_error", "connectivity_issue", "access_denied"]
                }
        
        except Exception as e:
            print(f"Error during analysis: {e}")
            retries += 1
            if retries < max_retries:
                print(f"Retrying in {2**retries} seconds...")
                time.sleep(2**retries)  # Exponential backoff
            else:
                print(f"Analysis failed after {max_retries} attempts.")
                return {
                    "criteria_met": "Error",
                    "explanation": f"Analysis failed after {max_retries} attempts: {str(e)}",
                    "improvements": "Try again with a different image or check system configuration.",
                    "severity": "Unknown",
                    "image_quality_issues": ["analysis_error"],
                    "quality_assessment": "Error during image analysis process",
                    "tags": ["error", "analysis_failed", "technical_issue"]
                }

# Function to analyze selected locations
def analyze_selected_locations(df, selected_cafes, selected_vendors, api_key):
    # Configure OpenAI client
    client = OpenAI(api_key=api_key)
    
    # Filter data for selected cafes and vendors
    cafe_filter = (df['checklist_type'] == 'cafe') & (df['location_name'].isin(selected_cafes))
    vendor_filter = (df['checklist_type'] == 'vendor') & (df['location_name'].isin(selected_vendors))
    filtered_df = df[cafe_filter | vendor_filter].copy()
    
    # Show count of entries for each selected location
    print("\nEntries to be analyzed:")
    for location_type, location_name in [('cafe', cafe) for cafe in selected_cafes] + [('vendor', vendor) for vendor in selected_vendors]:
        location_df = filtered_df[(filtered_df['checklist_type'] == location_type) & (filtered_df['location_name'] == location_name)]
        count = len(location_df)
        print(f"{location_name} ({location_type}): {count} entries")
    
    # Create an output file path
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = f"location_analysis_{timestamp}.xlsx"
    
    # Add new columns to the dataframe for analysis results
    # We're keeping all existing columns and just adding our analysis columns
    filtered_df['compliance_status'] = None
    filtered_df['explanation'] = None
    filtered_df['improvement_suggestions'] = None
    filtered_df['severity_level'] = None
    filtered_df['image_quality_issues'] = None
    filtered_df['quality_assessment'] = None
    filtered_df['analysis_tags'] = None
    filtered_df['analysis_date'] = None
    
    # Analyze each row that has image data
    total_rows = len(filtered_df)
    analyzed_count = 0
    
    # Filter to focus only on entries with image uploads (as requested)
    image_df = filtered_df[~filtered_df['upload_links'].isna() & (filtered_df['upload_links'] != '')]
    print(f"\nFound {len(image_df)} entries with images to analyze out of {total_rows} total entries")
    
    if len(image_df) == 0:
        print("No entries with images found for analysis. Exiting.")
        return filtered_df
    
    for idx, row in image_df.iterrows():
        analyzed_count += 1
        print(f"\nAnalyzing record {analyzed_count}/{len(image_df)} for {row['location_name']} ({row['checklist_type']})")
        print(f"Question: {row['question']}")
        
        result = analyze_image(client, row)
        
        # Format image quality issues as string if it's a list
        image_quality_issues = result.get('image_quality_issues', ['none'])
        if isinstance(image_quality_issues, list):
            image_quality_issues = ', '.join(image_quality_issues)
        
        # Format tags as string if it's a list
        tags = result.get('tags', ['untagged'])
        if isinstance(tags, list):
            tags = ', '.join(tags)
        
        # Update the dataframe with analysis results
        filtered_df.at[idx, 'compliance_status'] = result.get('criteria_met', 'Unknown')
        filtered_df.at[idx, 'explanation'] = result.get('explanation', '')
        filtered_df.at[idx, 'improvement_suggestions'] = result.get('improvements', '')
        filtered_df.at[idx, 'severity_level'] = result.get('severity', 'Unknown')
        filtered_df.at[idx, 'image_quality_issues'] = image_quality_issues
        filtered_df.at[idx, 'quality_assessment'] = result.get('quality_assessment', '')
        filtered_df.at[idx, 'analysis_tags'] = tags
        filtered_df.at[idx, 'analysis_date'] = datetime.datetime.now().strftime("%Y-%m-%d")
        
        print(f"Compliance: {filtered_df.at[idx, 'compliance_status']}")
        print(f"Severity: {filtered_df.at[idx, 'severity_level']}")
        
        # Save progress after each analysis or in batches
        if analyzed_count % 5 == 0 or analyzed_count == len(image_df):
            # Save all columns including original ones to the Excel file
            filtered_df.to_excel(output_file, index=False)
            print(f"Progress saved to {output_file} ({analyzed_count}/{len(image_df)} completed)")
            
            # Show interim stats
            print("\nInterim Analysis Summary:")
            compliance_counts = filtered_df['compliance_status'].value_counts()
            print("Compliance Status:")
            print(compliance_counts)
    
    print(f"\nAnalysis complete! Results saved to {output_file}")
    return filtered_df

# Function to generate analysis summary
def generate_summary(analyzed_df):
    # Filter to focus only on rows that were analyzed
    analyzed_only = analyzed_df[~analyzed_df['compliance_status'].isna()]
    
    if len(analyzed_only) == 0:
        print("No entries were successfully analyzed.")
        return
    
    print("\n=== ANALYSIS SUMMARY ===")
    print(f"Total entries analyzed: {len(analyzed_only)}")
    
    # Overall compliance and severity
    compliance_counts = analyzed_only['compliance_status'].value_counts()
    severity_counts = analyzed_only['severity_level'].value_counts()
    
    print("\nOverall Compliance Status:")
    print(compliance_counts)
    
    print("\nOverall Severity Levels:")
    print(severity_counts)
    
    # Image quality issues
    if 'image_quality_issues' in analyzed_only.columns:
        quality_issues = analyzed_only['image_quality_issues'].str.contains('too_dark|too_blurry|no_image|image_access_error|invalid_url|access_error|analysis_error').sum()
        print(f"\nImages with quality issues: {quality_issues} of {len(analyzed_only)}")
    
    # Analysis by location type
    print("\nResults by location type:")
    for location_type in ['cafe', 'vendor']:
        type_df = analyzed_only[analyzed_only['checklist_type'] == location_type]
        if not type_df.empty:
            type_compliance = type_df['compliance_status'].value_counts()
            
            print(f"\n{location_type.capitalize()} ({len(type_df)} entries):")
            print("  Compliance:")
            for status, count in type_compliance.items():
                print(f"    {status}: {count}")
    
    # Analysis by location
    print("\nResults by location:")
    for location in analyzed_only['location_name'].unique():
        loc_df = analyzed_only[analyzed_only['location_name'] == location]
        loc_compliance = loc_df['compliance_status'].value_counts()
        
        print(f"\n{location} ({len(loc_df)} entries):")
        print("  Compliance:")
        for status, count in loc_compliance.items():
            print(f"    {status}: {count}")
    
    # Top tags
    if 'analysis_tags' in analyzed_only.columns:
        all_tags = []
        for tag_str in analyzed_only['analysis_tags'].dropna():
            all_tags.extend([tag.strip() for tag in tag_str.split(',')])
        
        if all_tags:
            top_tags = Counter(all_tags).most_common(10)
            
            print("\nTop 10 Tags:")
            for tag, count in top_tags:
                print(f"  {tag}: {count}")

def main():
    # Get file path
    file_path = input("Enter path to your Excel file: ")
    
    # Load the specific sheet
    df = pd.read_csv(file_path)
    if df is None:
        return
    
    print(f"Successfully loaded 'HB-Categorized-Main-Sheet' with {len(df)} rows and {df.shape[1]} columns")
    
    # Identify unique cafes and vendors
    unique_cafes, unique_vendors = identify_unique_locations(df)
    
    # Let user select cafes (maximum 5)
    print("\nSelect up to 5 cafes to analyze (enter numbers separated by commas):")
    cafe_selection = input("> ")
    try:
        cafe_indices = [int(idx.strip()) - 1 for idx in cafe_selection.split(',')]
        selected_cafes = [unique_cafes[idx] for idx in cafe_indices if 0 <= idx < len(unique_cafes)]
        
        # Limit to 5 cafes
        if len(selected_cafes) > 5:
            print("Warning: You selected more than 5 cafes. Only the first 5 will be analyzed.")
            selected_cafes = selected_cafes[:5]
        
        print(f"\nSelected cafes for analysis: {selected_cafes}")
    except Exception as e:
        print(f"Error selecting cafes: {e}")
        selected_cafes = []
    
    # Let user select vendors (maximum 5)
    print("\nSelect up to 5 vendors to analyze (enter numbers separated by commas):")
    vendor_selection = input("> ")
    try:
        vendor_indices = [int(idx.strip()) - 1 for idx in vendor_selection.split(',')]
        selected_vendors = [unique_vendors[idx] for idx in vendor_indices if 0 <= idx < len(unique_vendors)]
        
        # Limit to 5 vendors
        if len(selected_vendors) > 5:
            print("Warning: You selected more than 5 vendors. Only the first 5 will be analyzed.")
            selected_vendors = selected_vendors[:5]
        
        print(f"\nSelected vendors for analysis: {selected_vendors}")
    except Exception as e:
        print(f"Error selecting vendors: {e}")
        selected_vendors = []
    
    if not selected_cafes and not selected_vendors:
        print("No locations selected for analysis. Exiting.")
        return
    
    #Get OpenAI API key
    api_key = input("Enter your OpenAI API key: ")
    
    if not api_key:
        print("API key is required. Exiting.")
        return
    
    # Run analysis
    analyzed_df = analyze_selected_locations(df, selected_cafes, selected_vendors, api_key)
    
    # Generate summary
    generate_summary(analyzed_df)
    
    # Ask if user wants to export detailed non-compliant items
    export_option = input("\nDo you want to export a detailed list of non-compliant items? (y/n): ")
    if export_option.lower() == 'y':
        non_compliant_df = analyzed_df[analyzed_df['compliance_status'] == 'No']
        if not non_compliant_df.empty:
            non_compliant_file = f"non_compliant_items_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            non_compliant_df.to_excel(non_compliant_file, index=False)
            print(f"Non-compliant items exported to {non_compliant_file}")
        else:
            print("No non-compliant items found.")
    
    # Print the final skip count
    print(f"\nTotal number of times OpenAI analysis was skipped: {skip_count}")

if __name__ == "__main__":
    main()