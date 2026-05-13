import os
import io
import json
import datetime
from django.utils import timezone  # Useful for handling due dates
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Q, Sum, Avg
from django.http import HttpResponse, JsonResponse
from django.template.loader import get_template
from django.conf import settings
from django.views.decorators.csrf import csrf_protect # Ensures safety for your borrow logic

# External PDF Library
from xhtml2pdf import pisa

# Local Models
# I added 'Book' and 'LibraryRecord' here. 
# Make sure these names match exactly what is in your models.py file.
from .models import Student, Mark, Teacher, Allocation, Book, BorrowRecord
# External PDF Library
from xhtml2pdf import pisa

# Local Models
from .models import Student, Mark, Teacher, Allocation

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
            student_name=request.POST.get("student_name"), # Changed from first/last name
            admission_number=request.POST.get("admission_number"),
            grade=request.POST.get("grade"),
            parent_name=request.POST.get("parent_name"),
            parent_phone=request.POST.get("parent_phone"),
        )
        return redirect("dashboard")
    return render(request, "add_student.html", {
        "grades": [f"Grade {i}" for i in range(1, 10)]
    })

#--------------------------------add students bulk-------------------
import json
from django.http import JsonResponse

@login_required
@user_passes_test(is_admin)
def add_students_bulk(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            student_list = data.get('students', [])
            
            for s in student_list:
                clean_grade = s['grade'].replace('Grade ', '').strip()

                # Creates database object parameters utilizing 'student_name'
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



#----------------------------------end of add students bulk----------

@login_required
def grade_students(request, grade):
    grade_map = {str(i): f"Grade {i}" for i in range(1, 10)}
    grade_name = grade_map.get(str(grade))
    students = Student.objects.filter(grade=grade_name)
    return render(request, "grade_students.html", {"grade": grade_name, "students": students})

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
# PDF GENERATION
# =========================

@login_required
def download_view_list_pdf(request):
    # 1. Get Filters from URL
    sel_grade = request.GET.get("grade", "Grade 1")
    sel_term = request.GET.get("term", "1")
    sel_year = request.GET.get("year", str(datetime.datetime.now().year))

    # 2. Prepare Data
    subjects = get_subjects_for_grade(sel_grade)
    students_qs = Student.objects.filter(grade=sel_grade)
    
    performance_data = []
    for student in students_qs:
        marks_qs = Mark.objects.filter(student=student, term=sel_term, year=sel_year)
        total = marks_qs.aggregate(Sum('marks'))['marks__sum'] or 0
        avg = marks_qs.aggregate(Avg('marks'))['marks__avg'] or 0
        
        marks_dict = {m.subject: m.marks for m in marks_qs}
        
        # Build subject marks list specifically for the template loops
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

    # 3. Rank Students
    performance_data.sort(key=lambda x: x["total"], reverse=True)
    for i, item in enumerate(performance_data):
        item["rank"] = i + 1

    # 4. Context for BOTH templates
    context = {
        "students_list": performance_data, # Use this key in both HTML files
        "subjects": subjects,
        "grade": sel_grade,
        "term": sel_term,
        "year": sel_year,
    }

    # 5. Handle the PDF Generation
    template = get_template("view_list_pdf.html")
    html = template.render(context)
    
    response = HttpResponse(content_type="application/pdf")
    response['Content-Disposition'] = f'attachment; filename="Ranking_{sel_grade}.pdf"'
    
    pisa_status = pisa.CreatePDF(html, dest=response)
    
    if pisa_status.err:
        return HttpResponse(f"Error: {pisa_status.err}")
    return response
#--------------------------edit students attributes------------------------------
@login_required
@user_passes_test(is_admin)
def edit_student(request, id):
    # Fetch the specific student or return a 404 error if not found
    student = get_object_or_404(Student, id=id)

    if request.method == "POST":
        # Capture the updated attributes from the POST request
        student.first_name = request.POST.get("first_name")
        student.last_name = request.POST.get("last_name")
        student.admission_number = request.POST.get("admission_number")
        student.grade = request.POST.get("grade")
        student.parent_name = request.POST.get("parent_name")
        student.parent_phone = request.POST.get("parent_phone")
        
        # Save the updated student object to the database
        student.save()
        
        messages.success(request, f"Details for {student.first_name} updated successfully!")
        return redirect("dashboard")

    # Attributes passed to the template to pre-fill the form
    return render(request, "edit_student.html", {
        "student": student,
        "grades": [f"Grade {i}" for i in range(1, 10)]
    })
#----------------------------------------------------------------------------------
#-------------------------delete students attribute--------------------------------
@login_required
@user_passes_test(is_admin)
def delete_student(request, id):
    # Fetch the student or return 404
    student = get_object_or_404(Student, id=id)
    
    if request.method == "POST":
        student_name = f"{student.first_name} {student.last_name}"
        student.delete()
        messages.warning(request, f"Student {student_name} has been deleted.")
        return redirect("dashboard")
    
    # If the user just navigates to the URL, show a confirmation page
    return render(request, "confirm_delete.html", {"student": student})
#-----------------------------------------add mark attribute------------------------
@login_required
def add_mark(request):
    # Setup standard attributes for dropdowns
    grades = [f"Grade {i}" for i in range(1, 10)]
    current_year = datetime.datetime.now().year
    years = [str(y) for y in range(2024, current_year + 5)]

    # 1. GET Attributes (Used for Filtering)
    sel_grade = request.GET.get("grade")
    sel_sub = request.GET.get("subject")
    term = request.GET.get("term", "1")
    year = request.GET.get("year", str(current_year))

    # Get subjects based on the grade helper
    subjects = get_subjects_for_grade(sel_grade) if sel_grade else []
    
    # Get students in that specific grade
    students = Student.objects.filter(grade=sel_grade) if sel_grade else []

    # Map existing marks so they show up in the input boxes
    marks_qs = Mark.objects.filter(subject=sel_sub, term=term, year=year)
    marks_map = {m.student_id: m.marks for m in marks_qs}

    # 2. POST Attributes (Used for Saving)
    if request.method == "POST":
        # The 'total possible mark' attribute
        out_of = float(request.POST.get("out_of") or 100)

        for s in students:
            # Capture the specific score for this student ID
            val = request.POST.get(f"marks_{s.id}")
            
            if val:
                # Calculate percentage attribute
                percentage_score = (float(val) / out_of) * 100
                
                # Update or create the record
                Mark.objects.update_or_create(
                    student=s,
                    subject=sel_sub,
                    term=term,
                    year=year,
                    defaults={"marks": int(percentage_score)}
                )

        messages.success(request, f"Marks for {sel_sub} updated successfully!")
        return redirect(f"/marks/add/?grade={sel_grade}&subject={sel_sub}&term={term}&year={year}")

    return render(request, "add_mark.html", {
        "grades": grades,
        "years": years,
        "subjects": subjects,
        "students": students,
        "marks_map": marks_map,
        "selected_grade": sel_grade,
        "selected_subject": sel_sub,
        "term": term,
        "year": year
    })
#-----------------------marks entry--------------------------------
@login_required
def marks_entry(request):
    return render(request, "marks_entry.html")

#------------------------generate report card attribute-------------
import datetime
from django.shortcuts import get_object_or_404
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.template.loader import get_template
from xhtml2pdf import pisa

# Ensure these are imported from your actual project structure
# from .models import Student, Mark, Allocation 
# from .utils import get_cbc_rubric_data

import datetime
from django.db.models import Sum
from django.shortcuts import get_object_or_404, render
from django.http import HttpResponse
from django.template.loader import get_template
from xhtml2pdf import pisa
from django.contrib.auth.decorators import login_required
# Import your models here (Student, Mark, Allocation, etc.)

@login_required
def report_card(request, id):
    # 1. Fetch Student
    student = get_object_or_404(Student, id=id)

    # 2. Get Filters from URL
    term = request.GET.get("term", "1")
    year = request.GET.get("year", str(datetime.datetime.now().year))
    force_download = request.GET.get("download") == "1"

    # 3. Fetch Marks
    marks_qs = Mark.objects.filter(student=student, term=term, year=year)
    
    enriched_marks = []
    total_val = 0

    for m in marks_qs:
        # Handle potential None in m.marks
        current_score = m.marks if m.marks is not None else 0
        
        # Teacher Lookup safety
        allocation = Allocation.objects.filter(subject=m.subject, grade=student.grade).first()
        teacher_name = (allocation.teacher.name if allocation and allocation.teacher else "Subject Teacher")

        # Rubric Logic safety: Ensure rubric is never None
        rubric = get_cbc_rubric_data(current_score)
        if not rubric:
            rubric = {'code': 'N/A', 'label': 'No Data'}

        enriched_marks.append({
            'subject': m.subject,
            'teacher_name': teacher_name,
            'score': current_score,
            'rubric': rubric 
        })
        total_val += current_score

    # 4. Calculations
    count = marks_qs.count()
    average_marks = round(total_val / count, 2) if count > 0 else 0
    
    # Safety check for overall rubric
    overall_grade_data = get_cbc_rubric_data(average_marks)
    overall_code = overall_grade_data.get('code', 'N/A') if overall_grade_data else 'N/A'

    # 5. Ranking Logic
    student_rankings = (
        Mark.objects.filter(student__grade=student.grade, term=term, year=year)
        .values('student')
        .annotate(total=Sum('marks'))
        .order_by('-total')
    )

    position = "N/A"
    if student_rankings.exists():
        for i, rank in enumerate(student_rankings):
            if rank['student'] == student.id:
                position = i + 1
                break

    # 6. Context for the Template
    context = {
        "student": student,
        "marks": enriched_marks,
        "term": term,
        "year": year,
        "total_marks": total_val,
        "average_marks": average_marks,
        "overall_grade": overall_code,
        "position": position,
        "class_teacher_name": "Class Teacher", 
        "head_teacher_name": "Head Teacher",
        "is_pdf": True, 
    }

    # 7. Render PDF
    template = get_template("report_card_pdf.html")
    html = template.render(context)
    
    response = HttpResponse(content_type="application/pdf")
    
    disposition = "attachment" if force_download else "inline"
    filename = f"Report_{student.admission_number}_Term{term}_{year}.pdf"
    response['Content-Disposition'] = f'{disposition}; filename="{filename}"'
    
    # Generate PDF
    pisa_status = pisa.CreatePDF(html, dest=response)
    
    if pisa_status.err:
        return HttpResponse(f"Error generating report: {pisa_status.err}", status=500)
        
    return response
#--------------------------------download pdf attribute-----------------------------------
@login_required
def download_pdf(request): return HttpResponse("OK")

#------------------------------library-----------------------------------
import json
import datetime
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_protect
from .models import Book, BorrowRecord

@login_required
@csrf_protect
def library(request):
    """
    Main View: Handles page rendering (GET) and AJAX transactions (POST).
    """
    
    if request.method == "POST":
        try:
            # Check if request body is empty
            if not request.body:
                return JsonResponse({"error": "No data received"}, status=400)

            data = json.loads(request.body)
            action = data.get("action")

            # --- CASE 1: RETURN A BOOK ---
            if action == "return":
                record_id = data.get("record_id")
                if not record_id:
                    return JsonResponse({"error": "Missing record ID"}, status=400)
                
                record = get_object_or_404(BorrowRecord, id=record_id)

                if record.status != "Returned":
                    record.status = "Returned"
                    record.return_date = datetime.date.today()
                    record.save()

                    # Restore Book Stock
                    book = record.book
                    book.available_copies += record.copies
                    book.save()

                return JsonResponse({"status": "success", "message": "Book returned"})

            # --- CASE 2: BORROW A BOOK ---
            elif action == "borrow":
                member_name = data.get("member_name", "").strip()
                member_type = data.get("member_type", "Student").strip()
                book_name = data.get("book_name", "").strip()
                copies = int(data.get("copies") or 1)
                due_date_str = data.get("due_date")

                # Validation
                if not member_name or not book_name or not due_date_str:
                    return JsonResponse({"error": "All fields (Name, Book, Date) are required"}, status=400)

                # Date Conversion
                try:
                    due_date = datetime.datetime.strptime(due_date_str, '%Y-%m-%d').date()
                except ValueError:
                    return JsonResponse({"error": "Invalid date format"}, status=400)

                # Find Book (Case Insensitive)
                book = Book.objects.filter(title__iexact=book_name).first()
                if not book:
                    book = Book.objects.filter(title__icontains=book_name).first()

                if not book:
                    return JsonResponse({"error": f"Book '{book_name}' not found"}, status=400)

                # Stock Check
                if book.available_copies < copies:
                    return JsonResponse({"error": f"Insufficient stock. Only {book.available_copies} left."}, status=400)

                # Transaction
                BorrowRecord.objects.create(
                    member_name=member_name,
                    member_type=member_type,
                    book=book,
                    copies=copies,
                    due_date=due_date,
                    status="Borrowed"
                )

                book.available_copies -= copies
                book.save()

                return JsonResponse({"status": "success"})

            # --- UNKNOWN ACTION ---
            return JsonResponse({"error": f"Invalid action: {action}"}, status=400)

        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON format"}, status=400)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

    # ==========================================
    # GET REQUEST (Page Load)
    # ==========================================
    books = Book.objects.all().order_by("title")
    records_qs = BorrowRecord.objects.all().order_by("-id")

    records_list = [
        {
            "id": r.id,
            "name": r.member_name,
            "type": r.member_type,
            "book": r.book.title,
            "copies": r.copies,
            "due_date": str(r.due_date),
            "status": r.status,
        }
        for r in records_qs
    ]

    # Return the HTML template only for GET requests
    return render(request, "library.html", {
        "books": books,
        "records": json.dumps(records_list)
    })

@login_required
def return_book(request, record_id):
    """Fallback endpoint for URL-based returns."""
    if request.method == "POST":
        record = get_object_or_404(BorrowRecord, id=record_id)
        if record.status != "Returned":
            record.status = "Returned"
            record.return_date = datetime.date.today()
            record.save()
            
            book = record.book
            book.available_copies += record.copies
            book.save()
            return JsonResponse({"status": "success"})
            
    return JsonResponse({"error": "Invalid request"}, status=400)

#------------------------------end of library ------------------------

@login_required
def reports(request): return render(request, "reports.html")
@login_required
def fees(request): return render(request, "fees.html")


#--------------------------teachers---------------------------
@login_required
def teachers(request):
    # 1. HANDLE ADDING A TEACHER (When button is clicked)
    if request.method == "POST":
        name = request.POST.get("name")
        if name:
            # This saves the teacher to your database
            Teacher.objects.create(name=name)
            return JsonResponse({"status": "success"})
        return JsonResponse({"status": "error", "message": "Name is required"}, status=400)

    # 2. FETCH ALL TEACHERS (To show in the table)
    # This sends the database records to your HTML
    all_teachers = Teacher.objects.all().order_by('name')

    return render(request, 'teachers.html', {
        'teachers': all_teachers
    })

@login_required
def delete_teacher(request, teacher_id):
    """Add this to handle the delete button"""
    if request.method == "POST":
        teacher = get_object_or_404(Teacher, id=teacher_id)
        teacher.delete()
        return JsonResponse({"status": "success"})
    return JsonResponse({"status": "error"}, status=400)





@login_required
def lesson_allocation(request):
    # Fetch data to populate the page
    teachers = Teacher.objects.all().order_by('name')
    allocations = Allocation.objects.all().order_by('-id')
    
    return render(request, "lessons_allocation.html", {
        "teachers": teachers,
        "allocations": allocations
    })

@login_required
def generate_timetable(request):
    # This view simply serves the generation page
    # The actual plotting is handled by the JavaScript we wrote
    return render(request, "generate_timetable.html")
def library(request):
    return render(request, "library.html")


def course_books(request):
    return render(request, "course_books.html")


def story_books(request):
    return render(request, "story_books.html")


def schemes(request):

    return render(request, "schemes.html")


def teachers_registry(request):
    return render(request, "teacher.html")

