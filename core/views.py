import os
import io
import json
import re
import datetime
from django.utils import timezone
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db import transaction
from django.db.models import Q, Sum, Avg
from django.http import HttpResponse, JsonResponse
from django.template.loader import get_template
from django.conf import settings
from django.views.decorators.csrf import csrf_protect

# External PDF Library
from xhtml2pdf import pisa

# Local Models
from .models import Student, Mark, Teacher, Allocation, Book, BorrowRecord

# =========================
# HELPERS
# =========================

def is_admin(user):
    return user.is_staff

def get_grade_num(grade_string):
    try:
        return str(grade_string).split()[-1]
    except:
        return "1"

def get_subjects_for_grade(grade_string):
    try:
        num = int(get_grade_num(grade_string))
        if 1 <= num <= 3:
            return ["Maths", "English", "Kiswahili", "Creative Art", "Environmental", "Religious Education"]
        elif 4 <= num <= 6:
            return ["Maths", "English", "Science", "Social Studies", "Agriculture", "Home Science"]
        else:
            return ["Maths", "English", "Integrated Science", "Pretechnical Studies", "CRE", "Kiswahili", "Agriculture", "Social Studies", "Creative Arts"]
    except:
        return []

def get_cbc_rubric_data(mark):
    if mark is None:
        return {'code': 'N/A', 'label': 'No Data'}
    if mark >= 90: return {'code': 'EE1'}
    elif mark >= 80: return {'code': 'EE2'}
    elif mark >= 65: return {'code': 'ME1'}
    elif mark >= 50: return {'code': 'ME2'}
    elif mark >= 40: return {'code': 'AE1'}
    elif mark >= 30: return {'code': 'AE2'}
    elif mark >= 15: return {'code': 'BE1'}
    else: return {'code': 'BE2'}

# =========================
# AUTH
# =========================

def login_view(request):
    if request.method == "POST":
        user = authenticate(
            request,
            username=request.POST.get("username"),
            password=request.POST.get("password")
        )
        if user:
            login(request, user)
            return redirect("dashboard")
    return render(request, "login.html")

@login_required
def logout_view(request):
    logout(request)
    return redirect("login")

@login_required
def dashboard(request):
    return render(request, "dashboard.html")

# =========================
# STUDENTS
# =========================

@login_required
@user_passes_test(is_admin)
def add_student(request):
    if request.method == "POST":
        Student.objects.create(
            student_name=request.POST.get("student_name"),
            admission_number=request.POST.get("admission_number"),
            grade=request.POST.get("grade"),
            parent_name=request.POST.get("parent_name"),
            parent_phone=request.POST.get("parent_phone"),
        )
        return redirect("dashboard")
    return render(request, "add_student.html", {
        "grades": [f"Grade {i}" for i in range(1, 10)]
    })

@login_required
@user_passes_test(is_admin)
def add_students_bulk(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            student_list = data.get('students', [])
            
            for s in student_list:
                clean_grade = s['grade'].replace('Grade ', '').strip()

                Student.objects.create(
                    student_name=s['student_name'].strip(),
                    admission_number=s['admission_number'].strip(),
                    grade=f"Grade {clean_grade}",
                    parent_name=s.get('parent_name', '').strip(),
                    parent_phone=s.get('parent_phone', '').strip()
                )
                
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=400)
            
    return JsonResponse({'success': False, 'message': 'Invalid request method'}, status=405)

@login_required
def grade_students(request, grade):
    grade_map = {str(i): f"Grade {i}" for i in range(1, 10)}
    grade_name = grade_map.get(str(grade), f"Grade {grade}")
    students = Student.objects.filter(grade=grade_name)
    # FIX: Pass the raw grade number 'grade' so grades.html constructs titles cleanly
    return render(request, "grade_students.html", {"grade": grade, "students": students})

@login_required
@user_passes_test(is_admin)
def delete_student(request, student_id):
    student = get_object_or_404(Student, id=student_id)
    
    # Safely extract numeric digits from "Grade X" or "X" to ensure dynamic URL redirection
    raw_grade_str = str(student.grade or "1")
    numeric_match = re.search(r'\d+', raw_grade_str)
    redirect_grade_id = numeric_match.group() if numeric_match else "1"
    
    try:
        with transaction.atomic():
            # Drop cascading dependencies manually to bypass model restrictions
            Mark.objects.filter(student=student).delete()
            student.delete()
        messages.success(request, "Successfully deleted student record.")
    except Exception as e:
        messages.error(request, f"Could not perform deletion: {str(e)}")
        
    return redirect(f"/grades/{redirect_grade_id}/")

# Placeholder for edit logic to prevent runtime path breaking
@login_required
@user_passes_test(is_admin)
def edit_student(request, student_id):
    student = get_object_or_404(Student, id=student_id)
    # Implement editing functionality here matching your layout rules
    return render(request, "edit_student.html", {"student": student})

# =========================
# MARKS ENTRY
# =========================

@login_required
def add_mark(request):
    grades = [f"Grade {i}" for i in range(1, 10)]
    current_year = datetime.datetime.now().year
    years = [str(y) for y in range(2024, current_year + 5)]

    sel_grade = request.GET.get("grade")
    sel_sub = request.GET.get("subject")
    subjects = get_subjects_for_grade(sel_grade) if sel_grade else []
    if not sel_sub and subjects:
        sel_sub = subjects[0]

    term = request.GET.get("term", "1")
    year = request.GET.get("year", str(current_year))
    students = Student.objects.filter(grade=sel_grade) if sel_grade else []
    marks_qs = Mark.objects.filter(subject=sel_sub, term=term, year=year)
    marks_map = {m.student_id: m.marks for m in marks_qs}

    if request.method == "POST":
        out_of = float(request.POST.get("out_of") or 100)
        for s in students:
            val = request.POST.get(f"marks_{s.id}")
            if val:
                perc = (float(val) / out_of) * 100
                Mark.objects.update_or_create(
                    student=s, subject=sel_sub, term=term, year=year,
                    defaults={"marks": int(perc)}
                )
        return redirect(f"/marks/add/?grade={sel_grade}&subject={sel_sub}&term={term}&year={year}")

    return render(request, "add_mark.html", {
        "grades": grades, "years": years, "subjects": subjects, "students": students,
        "marks_map": marks_map, "selected_grade": sel_grade, "selected_subject": sel_sub,
        "term": term, "year": year
    })

# =========================
# VIEW LIST & RANKING
# =========================

@login_required
def view_list(request):
    grades = [f"Grade {i}" for i in range(1, 10)]
    sel_grade = request.GET.get("grade", "Grade 1")
    sel_term = request.GET.get("term", "1")
    sel_year = request.GET.get("year", str(datetime.datetime.now().year))

    subjects = get_subjects_for_grade(sel_grade)
    students = Student.objects.filter(grade=sel_grade)
    performance_data = []

    for student in students:
        marks_qs = Mark.objects.filter(student=student, term=sel_term, year=sel_year)
        total = marks_qs.aggregate(Sum('marks'))['marks__sum'] or 0
        avg = marks_qs.aggregate(Avg('marks'))['marks__avg'] or 0
        marks_dict = {m.subject: m.marks for m in marks_qs}

        subject_marks = [
            {"score": marks_dict.get(sub), "rubric": get_cbc_rubric_data(marks_dict.get(sub))["code"]}
            for sub in subjects
        ]
        performance_data.append({
            "student": student,
            "subject_marks": subject_marks,
            "total": total,
            "overall_rubric": get_cbc_rubric_data(avg)["code"]
        })

    performance_data.sort(key=lambda x: x["total"], reverse=True)

    return render(request, "view_list.html", {
        "grades": grades, "terms": ["1", "2", "3"],
        "years": [str(y) for y in range(2024, datetime.datetime.now().year + 5)],
        "performance_data": performance_data, "subjects": subjects,
        "selected_grade": sel_grade, "selected_term": sel_term, "selected_year": sel_year,
    })

# =========================
# PDF GENERATION AND OTHER STUBS
# =========================

@login_required
def download_view_list_pdf(request):
    sel_grade = request.GET.get("grade", "Grade 1")
    sel_term = request.GET.get("term", "1")
    sel_year = request.GET.get("year", str(datetime.datetime.now().year))

    subjects = get_subjects_for_grade(sel_grade)
    students_qs = Student.objects.filter(grade=sel_grade)
    
    performance_data = []
    for student in students_qs:
        marks_qs = Mark.objects.filter(student=student, term=sel_term, year=sel_year)
        total = marks_qs.aggregate(Sum('marks'))['marks__sum'] or 0
        avg = marks_qs.aggregate(Avg('marks'))['marks__avg'] or 0
        marks_dict = {m.subject: m.marks for m in marks_qs}
        
        subject_marks = []
        for sub in subjects:
            score = marks_dict.get(sub)
            subject_marks.append({
                "score": score,
                "rubric": get_cbc_rubric_data(score)["code"] if score is not None else ""
            })

        performance_data.append({
            "student": student,
            "subject_marks": subject_marks,
            "total": total,
            "overall_rubric": get_cbc_rubric_data(avg)["code"]
        })
        
    performance_data.sort(key=lambda x: x["total"], reverse=True)
    return render(request, "view_list_pdf.html", {"performance_data": performance_data, "subjects": subjects})

@login_required
def report_card(request, id):
    return HttpResponse("Report card rendering stub")

@login_required
def teachers(request):
    return HttpResponse("Teachers rendering stub")

@login_required
def delete_teacher(request, teacher_id):
    return HttpResponse("Delete teacher rendering stub")

@login_required
def teachers_registry(request):
    return HttpResponse("Teachers registry rendering stub")

@login_required
def lesson_allocation(request):
    return HttpResponse("Lesson allocation rendering stub")

@login_required
def library(request):
    return HttpResponse("Library rendering stub")

@login_required
def return_book(request, record_id):
    return HttpResponse("Return book rendering stub")

@login_required
def course_books(request):
    return HttpResponse("Course books rendering stub")

@login_required
def story_books(request):
    return HttpResponse("Story books rendering stub")

@login_required
def schemes(request):
    return HttpResponse("Schemes rendering stub")

@login_required
def reports(request):
    return HttpResponse("Reports rendering stub")

@login_required
def fees(request):
    return HttpResponse("Fees rendering stub")

@login_required
def generate_timetable(request):
    return HttpResponse("Timetable rendering stub")

@login_required
def marks_entry(request):
    return HttpResponse("Marks entry landing stub")
