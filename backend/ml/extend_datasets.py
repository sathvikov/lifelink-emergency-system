import pandas as pd
import numpy as np
import os
from datetime import datetime, timedelta
import random

# Set random seeds for reproducibility
np.random.seed(42)
random.seed(42)

# Directory containing CSV files
csv_dir = os.path.dirname(os.path.abspath(__file__))
target_rows = 2000

# List of CSV files to exclude
exclude_files = ['911_calls.csv']

# Helper functions for generating synthetic data based on column types
def generate_synthetic_row(df, header):
    """Generate a synthetic row based on existing data patterns"""
    row = {}
    
    for col in header:
        if df.empty or col not in df.columns:
            row[col] = ""
            continue
            
        existing_values = df[col].dropna().unique()
        col_type = df[col].dtype
        
        # For categorical/object columns, randomly select from existing values
        if col_type == 'object' or len(existing_values) < 20:
            if len(existing_values) > 0:
                row[col] = random.choice(existing_values)
            else:
                row[col] = ""
        # For numeric columns, generate values in the range of existing data
        elif col_type in ['int64', 'float64']:
            numeric_vals = df[col].dropna()
            if len(numeric_vals) > 0:
                min_val = numeric_vals.min()
                max_val = numeric_vals.max()
                if col_type == 'int64':
                    row[col] = np.random.randint(int(min_val), int(max_val) + 1)
                else:
                    row[col] = round(np.random.uniform(min_val, max_val), 2)
            else:
                row[col] = 0
        else:
            row[col] = ""
    
    return row

def extend_csv(file_path):
    """Extend a CSV file to have target_rows entries"""
    try:
        # Read the CSV file
        df = pd.read_csv(file_path)
        current_rows = len(df)
        
        if current_rows >= target_rows:
            print(f"✓ {os.path.basename(file_path)}: Already has {current_rows} rows (target: {target_rows})")
            return True
        
        rows_to_add = target_rows - current_rows
        header = list(df.columns)
        
        print(f"  Extending {os.path.basename(file_path)}: {current_rows} → {target_rows} rows (+{rows_to_add})")
        
        # Generate synthetic rows
        new_rows = []
        for _ in range(rows_to_add):
            new_row = generate_synthetic_row(df, header)
            new_rows.append(new_row)
        
        # Create DataFrame from new rows and append
        new_df = pd.DataFrame(new_rows)
        extended_df = pd.concat([df, new_df], ignore_index=True)
        
        # Save back to CSV
        extended_df.to_csv(file_path, index=False)
        print(f"✓ {os.path.basename(file_path)}: Successfully extended to {len(extended_df)} rows")
        return True
        
    except Exception as e:
        print(f"✗ Error processing {os.path.basename(file_path)}: {str(e)}")
        return False

# Main execution
print("="*60)
print("CSV Dataset Extension Tool")
print("="*60)
print(f"Target: {target_rows} entries per dataset\n")

csv_files = [f for f in os.listdir(csv_dir) if f.endswith('.csv') and f not in exclude_files]
csv_files.sort()

success_count = 0
for csv_file in csv_files:
    file_path = os.path.join(csv_dir, csv_file)
    if extend_csv(file_path):
        success_count += 1

print("\n" + "="*60)
print(f"Completed: {success_count}/{len(csv_files)} files extended successfully")
print("="*60)
