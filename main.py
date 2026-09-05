import os
import pandas as pd
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional


app = FastAPI(title="Student Grades API")

# Add CORS middleware to allow frontend connections
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load data at startup
FILE_PATH = "نتيجة مادة برمجة 2.xlsx"

def load_data(file_path):
    df = pd.read_excel(file_path, header=3)
    df.columns = df.columns.str.strip()
    
    student_df = df[df['رقم الامتحا'].notna()].copy()
    student_df['رقم الامتحا'] = pd.to_numeric(student_df['رقم الامتحا'], errors='coerce')
    student_df = student_df[student_df['رقم الامتحا'].notna()].copy()
    student_df['رقم الامتحا'] = student_df['رقم الامتحا'].astype(int)
    student_df['علامة النهائ'] = pd.to_numeric(student_df['علامة النهائ'], errors='coerce')
    
    return student_df

def calculate_statistics(df):
    valid_grades = df['علامة النهائ'].dropna()
    average_score = valid_grades.mean()
    
    total_students = len(df)
    passing_students = len(df[df['النتيجة'] == 'ناجح'])
    passing_rate = (passing_students / total_students) * 100 if total_students > 0 else 0.0
    
    ranked_df = df[df['علامة النهائ'].notna()].copy()
    ranked_df['الترتيب'] = ranked_df['علامة النهائ'].rank(ascending=False, method='min')
    
    return average_score, passing_rate, ranked_df

# Load data when app starts
try:
    df = load_data(FILE_PATH)
    average_score, passing_rate, ranked_df = calculate_statistics(df)
except Exception as e:
    print(f"Error loading data: {e}")
    df = pd.DataFrame()
    average_score = 0
    passing_rate = 0
    ranked_df = pd.DataFrame()

@app.get("/")
def root():
    return {"message": "Student Grades API", "docs": "/docs"}

@app.get("/stats")
def get_statistics():
    """Get general class statistics"""
    if df.empty:
        return {"error": "Data not loaded"}
    
    passing_students = len(df[df['النتيجة'] == 'ناجح'])
    failing_students = len(df) - passing_students
    
    return {
        "total_students": int(len(df)),
        "average_score": float(round(average_score, 2)),
        "passing_rate": float(round(passing_rate, 2)),
        "passing_students": int(passing_students),
        "failing_students": int(failing_students),
        "total_ranked_students": int(len(ranked_df))
    }

@app.get("/search")
def search_student(
    exam_number: Optional[int] = Query(None, description="Student exam number"),
    name: Optional[str] = Query(None, description="Student name (full or partial)")
):
    """Search for a student by exam number or name"""
    if df.empty:
        return {"error": "Data not loaded"}
    
    if exam_number is None and name is None:
        return {"error": "Please provide either exam_number or name parameter"}
    
    # Search by exam number
    if exam_number is not None:
        student_row = df[df['رقم الامتحا'] == exam_number]
    # Search by name
    else:
        # Search in both first name and father name
        student_row = df[
            df['اسم الطالب'].str.contains(name, case=False, na=False) | 
            df['اسم الأب'].str.contains(name, case=False, na=False)
        ]
    
    if student_row.empty:
        return {"error": "Student not found"}
    
    # Get all matching students
    results = []
    for _, student_data in student_row.iterrows():
        grade = student_data['علامة النهائ']
        rank = None
        comparison = "N/A"
        above_average = None
        below_average = None
        
        if not pd.isna(grade):
            grade_float = float(grade)
            rank_row = ranked_df[ranked_df['رقم الامتحا'] == student_data['رقم الامتحا']]
            if not rank_row.empty:
                rank = int(rank_row.iloc[0]['الترتيب'])
            
            if grade_float > average_score:
                comparison = f"Above Average by {grade_float - average_score:.2f} points"
                above_average = True
                below_average = False
            elif grade_float < average_score:
                comparison = f"Below Average by {average_score - grade_float:.2f} points"
                above_average = False
                below_average = True
            else:
                comparison = "Equal to Average"
                above_average = False
                below_average = False
        
        # Convert all values to native Python types
        result = {
            "exam_number": int(student_data['رقم الامتحا']),
            "full_name": f"{student_data['اسم الطالب']} {student_data['اسم الأب']}",
            "first_name": str(student_data['اسم الطالب']),
            "father_name": str(student_data['اسم الأب']),
            "result": str(student_data['النتيجة']),
            "passed": bool(student_data['النتيجة'] == 'ناجح'),
            "grade": None if pd.isna(grade) else float(round(grade, 2)),
            "rank": rank,
            "total_ranked_students": int(len(ranked_df)),
            "comparison_with_average": comparison,
            "above_average": above_average,
            "below_average": below_average,
            "average_score": float(round(average_score, 2))
        }
        results.append(result)
    
    # If searching by exam number, return single result
    if exam_number is not None:
        return results[0] if results else {"error": "Student not found"}
    
    # If searching by name, return all matches
    return {"students": results, "count": len(results)}

@app.get("/top-students")
def get_top_students(limit: int = Query(10, description="Number of top students to return")):
    """Get top performing students"""
    if ranked_df.empty:
        return {"error": "No ranked students"}
    
    top_students = ranked_df.nsmallest(min(limit, len(ranked_df)), 'الترتيب')
    
    results = []
    for _, student in top_students.iterrows():
        results.append({
            "rank": int(student['الترتيب']),
            "exam_number": int(student['رقم الامتحا']),
            "full_name": f"{student['اسم الطالب']} {student['اسم الأب']}",
            "grade": float(round(student['علامة النهائ'], 2))
        })
    
    return {"top_students": results}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
