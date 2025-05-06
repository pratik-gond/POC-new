import streamlit as st
import pandas as pd

st.title("Excel File Processor")

# File uploader
uploaded_file = st.file_uploader("Choose an Excel file", type=['xlsx', 'xls'])

if uploaded_file is not None:
    try:
        # Read the Excel file
        df = pd.read_excel(uploaded_file)
        
        # Check if the required column exists
        st.write(df.columns)
        # st.write("Select the column you want to filter by:")
        # column_name = st.selectbox("Column Name:", df.columns)
        # st.write("distinct values in the column:")
        # st.write(df[column_name].unique())
        # st.write("select the value you want to filter by:")
        # value = st.selectbox("Value:", df[column_name].unique())
        
        # Add slider for number of rows
        max_rows = len(df)
        num_rows = st.slider("Select number of rows to include:", 
                           min_value=1, 
                           max_value=max_rows, 
                           value=min(100, max_rows))
        
        
            # Filter rows where the column value matches and limit to selected number of rows
        filtered_df = df.head(num_rows)
            
            # Display the shape of the filtered dataframe
        st.write(f"Shape of filtered dataframe: {filtered_df.shape}")
            
            # Input for output filename
        output_filename = st.text_input("Enter output filename (without extension):", "filtered_data")
            
        if st.button("Save as CSV"):
            if output_filename:
                    # Save the filtered dataframe as CSV
                filtered_df.to_csv(f"{output_filename}.csv", index=False)
                st.success(f"File saved as {output_filename}.csv")
            else:
                st.error("Please enter a filename")
    
            
    except Exception as e:
        st.error(f"An error occurred: {str(e)}")
else:
    st.info("Please upload an Excel file to begin")
