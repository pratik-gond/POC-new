import pandas as pd
import openai
import os
import streamlit as st
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Set OpenAI API key
# 
openai.api_key = os.getenv("OPENAI_API_KEY")

def categorize_questions(data):
    # Create categories list
    categories = [
        "Hygiene & Cleanliness",
        "Inventory & Storage",
        "Food Safety Compliance",
        "Hardware (Assets) & Other Equipment",
        "Marketing"
    ]
    
    # Create an empty list to store categorization results
    all_categorizations = []
    
    questions_df = pd.DataFrame(data)
    # Iterate through each question
    for index, row in questions_df.iterrows():
        question = row['question']  # Changed from 'question' to 'questions' to match the column name
        # Skip empty questions
        if pd.isna(question) or question.strip() == '':
            all_categorizations.append('')
            continue
        
        # Create prompt for OpenAI
        prompt = f"""
        Categorize the following question into one or more of these categories. 
        Return only the categories separated by commas, without any other text.
        
        Question: "{question}"
        
        Categories:
        - Hygiene & Cleanliness
        - Inventory & Storage
        - Food Safety Compliance
        - Hardware (Assets) & Other Equipment
        - Marketing
        
        Output format should be only the category names separated by commas, for example: "Hygiene & Cleanliness, Food Safety Compliance"
        """
        
        # Call OpenAI API
        try:
            response = openai.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that categorizes questions about food service operations."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=100
            )
            
            # Extract categorization
            categorization = response.choices[0].message.content.strip()
            
            # Format categorization with square brackets
            categories_list = [cat.strip() for cat in categorization.split(',')]
            formatted_categorization = f"[{', '.join(categories_list)}]"
            
            all_categorizations.append(formatted_categorization)
            
            # Print progress
            print(f"Processed question {index+1}: {formatted_categorization}")
            
        except Exception as e:
            print(f"Error processing question {index+1}: {e}")
            all_categorizations.append("Error")
    
    # Add categorizations to the dataframe
    questions_df['categorization'] = all_categorizations
    
    return questions_df

def trimDatatoQuestion(df): #Assuming no null value is given for question column
    df = df['question']
    st.write(df.sample(5))
    return df


def newdf():
    # Get CSV file from user through Streamlit uploader
    uploaded_file = st.file_uploader("Upload your CSV file", type=['csv'])
    
    if uploaded_file is not None:
        # Read the uploaded CSV file
        current_df = pd.read_csv(uploaded_file)
        
        df = trimDatatoQuestion(current_df)
        categorized_df = categorize_questions(df)

        #question_to_category = dict(zip(df['questions'], categorized_df['categorization']))

        # Create a new dataframe with the question and category columns
        current_df['categorization'] = categorized_df['categorization']
        
        # Save the new dataframe to an Excel file
        current_df.to_csv('new_categorized_df.csv', index=False)

        return df
    else:
        st.warning("Please upload a CSV file")
        return None


if __name__ == "__main__":
    newdf()
