# =====================================================
# 1. IMPORTS
# =====================================================
import os
import io
import json
import datetime
from django.utils import timezone
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Q, Sum, Avg
from django.db import transaction
from django.http import HttpResponse, JsonResponse, HttpResponseForbidden
# Check your imports section at the top of views.py for this line:
from django.db.models import Q, Sum, Avg


from django.template.loader import get_template
from django.conf import settings
from django.views.decorators.csrf import csrf_protect


# External PDF Library
from xhtml2pdf import pisa

# Local Models
from .models import Student, Mark, Teacher, Allocation, Book, BorrowRecord

# =====================================================
# 2. HELPERS & AUTHENTICATION
# =====================================================
#-------------------------------------admin---------------------

def is_admin(user):
    # Standard teachers have an account, but is_staff and is_superuser are FALSE.
    # This function returns True ONLY for true system administrators.
    return user.is_authenticated and (user.is_superuser or getattr(user, 'is_staff', False))

#------------------------------end admin-------------------------
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
    if mark is None: return {'code': 'N/A', 'label': 'No Data'}
    if mark >= 90: return {'code': 'EE1'}
    elif mark >= 80: return {'code': 'EE2'}
    elif mark >= 65: return {'code': 'ME1'}
    elif mark >= 50: return {'code': 'ME2'}
    elif mark >= 40: return {'code': 'AE1'}
    elif mark >= 30: return {'code': 'AE2'}
    elif mark >= 15: return {'code': 'BE1'}
    else: return {'code': 'BE2'}

#----------------------------------------------login view -------------------------------------
def login_view(request):
    if request.method == "POST":
        user = authenticate(request, username=request.POST.get("username"), password=request.POST.get("password"))
        if user:
            login(request, user)
            
            # 1. PRIORITY CHECK: If they have a teacher profile, always send them to their dashboard first
            if hasattr(user, 'teacher_profile'):
                return redirect("teacher_dashboard")
                
            # 2. ADMIN CHECK: If they are not a teacher but are admin/staff, send to the core system dashboard
            if user.is_superuser or getattr(user, 'is_staff', False):
                return redirect("dashboard")
                
            return redirect("login")
        else:
            # Fixed to pass 'error' directly to your new, professional HTML template error container
            return render(request, "login.html", {"error": "Invalid username or password"})
            
    return render(request, "login.html")

# Protect the main dashboard view from standard teacher entries
@login_required
@user_passes_test(is_admin)  
def dashboard(request):
    return render(request, "dashboard.html")

#--------------------------end of login view --------------------------------------------------
@login_required
def logout_view(request):
    logout(request)
    return redirect("login")

@login_required
def dashboard(request):
    return render(request, "dashboard.html")

# =====================================================
# 3. STUDENT MANAGEMENT
# =====================================================

@login_required
@user_passes_test(is_admin)
def add_student(request):
    if request.method == "POST":
        adm = request.POST.get("admission_number")
        if Student.objects.filter(admission_number=adm).exists():
            messages.error(request, "Admission number already exists.")
            return redirect("add_student")

        Student.objects.create(
            student_name=request.POST.get("student_name"),
            admission_number=adm,
            grade=request.POST.get("grade"),
            parent_name=request.POST.get("parent_name"),
            parent_phone=request.POST.get("parent_phone"),
        )
        messages.success(request, "Student profile added successfully.")
        return redirect("dashboard")
    return render(request, "add_student.html", {"grades": [f"Grade {i}" for i in range(1, 10)]})
#----------------------------------grade students view--------------
@login_required
def grade_students(request, grade):
    # Standardise the grade input from the URL string
    grade_num = str(grade).replace("Grade ", "").strip()
    grade_name = f"Grade {grade_num}"
    
    # 🔒 SECURITY CHECK: If the user is NOT an admin, enforce allocation limits
    if not (request.user.is_superuser or getattr(request.user, 'is_staff', False)):
        if hasattr(request.user, 'teacher_profile'):
            # Fetch all grades this specific teacher is assigned to manage
            allowed_grades = Allocation.objects.filter(
                teacher=request.user.teacher_profile
            ).values_list('grade', flat=True)
            
            # If they try to view an unassigned grade, block access immediately
            if grade_name not in allowed_grades:
                return HttpResponseForbidden("Access Denied: You are not allocated to teach this grade.")
        else:
            # If user has no teacher profile and isn't staff, block completely
            return HttpResponseForbidden("Access Denied: Invalid profile access parameters.")

    # Fetch and display students belonging only to the verified grade
    students = Student.objects.filter(grade=grade_name).order_by("admission_number")
    
    return render(request, "grade_students.html", {
        "students": students, 
        "grade": grade_num, 
        "grade_name": grade_name
    })

#------------------------------------end of grade students view----------------
@login_required
@user_passes_test(is_admin)
def add_students_bulk(request):
    if request.method != "POST": return JsonResponse({"success": False}, status=405)
    try:
        data = json.loads(request.body)
        student_list = data.get("students", [])
        admission_numbers = [s.get("admission_number") for s in student_list]
        existing = {s.admission_number: s for s in Student.objects.filter(admission_number__in=admission_numbers)}
        new_batch, update_batch = [], []

        for s in student_list:
            adm = s.get("admission_number")
            if not adm: continue
            if adm in existing:
                obj = existing[adm]
                obj.student_name = s.get("student_name")
                obj.grade = s.get("grade")
                obj.parent_name = s.get("parent_name", obj.parent_name)
                obj.parent_phone = s.get("parent_phone", obj.parent_phone)
                update_batch.append(obj)
            else:
                new_batch.append(Student(admission_number=adm, student_name=s.get("student_name"), grade=s.get("grade")))

        with transaction.atomic():
            if new_batch: Student.objects.bulk_create(new_batch)
            if update_batch: Student.objects.bulk_update(update_batch, fields=["student_name", "grade", "parent_name", "parent_phone"])
        return JsonResponse({"success": True})
    except Exception as e:
        return JsonResponse({"success": False, "message": str(e)}, status=500)

@login_required
@user_passes_test(is_admin)
def edit_student(request, student_id):
    student = get_object_or_404(Student, id=student_id)
    if request.method == "POST":
        student.student_name = request.POST.get("student_name")
        student.admission_number = request.POST.get("admission_number")
        student.grade = request.POST.get("grade")
        student.parent_name = request.POST.get("parent_name")
        student.parent_phone = request.POST.get("parent_phone")
        student.save()
        messages.success(request, "Student updated successfully.")
        return redirect("dashboard")
    return render(request, "edit_student.html", {"student": student})

@login_required
@user_passes_test(is_admin)
def delete_student(request, student_id):
    student = get_object_or_404(Student, id=student_id)
    
    # 1. Save the grade before the student is gone
    # If student.grade is "Grade 1", we just want the "1"
    grade_value = str(student.grade).replace("Grade ", "").strip()
    
    # 2. Delete the record
    student.delete()
    messages.success(request, f"Student deleted from Grade {grade_value}.")
    
    # 3. Redirect back to the grade list
    # Assuming your URL name is 'grade_students'
    return redirect('grade_students', grade=grade_value)



# =====================================================
# 4. LIBRARY ERP (ISSUE & RETURN)
# =====================================================

#----------------------------------------------------------------------------------------
import json
import datetime
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .models import Book, BorrowRecord, Student, Teacher

# 1. MOVE HELPER FUNCTIONS TO THE TOP
def handle_borrow(data):
    due_date_str = data.get("due_date")
    try:
        due_date_obj = datetime.datetime.strptime(due_date_str, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        return JsonResponse({"error": "Invalid date format"}, status=400)

    with transaction.atomic():
        try:
            book = Book.objects.select_for_update().get(title=data.get("book_name"))
            if book.available_copies < 1:
                return JsonResponse({"error": "No copies available"}, status=400)
            
            BorrowRecord.objects.create(
                member_name=data.get("member_name"), 
                member_type=data.get("member_type"),
                book=book, 
                copies=data.get("copies", 1),
                due_date=due_date_obj,
                status="Borrowed"
            )
            book.available_copies -= 1
            book.save()
            return JsonResponse({"success": True})
        except Book.DoesNotExist:
            return JsonResponse({"error": "Book not found"}, status=404)

def handle_return(data):
    with transaction.atomic():
        try:
            record = BorrowRecord.objects.select_for_update().get(id=data.get("record_id"))
            if record.status != "Returned":
                record.status = "Returned"
                record.return_date = datetime.date.today()
                record.save()
                record.book.available_copies += 1
                record.book.save()
                return JsonResponse({"success": True})
        except BorrowRecord.DoesNotExist:
            return JsonResponse({"error": "Record not found"}, status=404)
    return JsonResponse({"error": "Already returned"}, status=400)

# 2. MAIN LIBRARY VIEW AT THE BOTTOM
@login_required  # STEP 1: Django checks if the user is logged into the system.
@user_passes_test(is_admin)  # STEP 2: 🔒 THE BLOCKING POINT! Django runs your 'is_admin' check here. 
                             # If the user has a teacher_profile, it returns False and blocks them immediately.
                             # Teachers get booted away and NEVER reach the code below.
def library(request):
    # =========================================================================
    # EVERYTHING BELOW HERE ONLY RUNS IF THE LOGGED-IN USER IS A TRUE ADMIN!
    # =========================================================================
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            action = data.get("action")
            if action == "borrow":
                return handle_borrow(data)
            elif action == "return":
                return handle_return(data)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=400)

    today = datetime.date.today()
    recs = BorrowRecord.objects.select_related("book").order_by("-borrow_date")
    
    formatted = []
    for r in recs:
        st = r.status
        if st == "Borrowed" and r.due_date and r.due_date < today: 
            st = "Overdue"
            
        formatted.append({
            "id": r.id, 
            "member_name": r.member_name,
            "member_type": r.member_type,
            "book__title": r.book.title, 
            "copies": r.copies,
            "status": st, 
            "due_date": str(r.due_date)
        })

    context = {
        "books": list(Book.objects.values("id", "title", "available_copies", "grade").order_by("title")),
        "students": list(Student.objects.values("student_name", "grade").order_by("student_name")),
        "teachers": list(Teacher.objects.values("name").order_by("name")),
        "records": formatted,
    }
    return render(request, "library.html", context)



#---------------------------------------------------Managing books-----------------------
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Book  # Ensure this import matches your app structure

@login_required
def manage_books(request):
    if request.method == "POST":
        action = request.POST.get("action")
        title = request.POST.get("title")
        author = request.POST.get("author")
        grade = request.POST.get("grade")
        
        # Safe conversion to integer with fallback
        try:
            copies = int(request.POST.get("copies", 1))
        except ValueError:
            copies = 1

        if action == "add":
            Book.objects.create(
                title=title, 
                author=author, 
                grade=grade, 
                total_copies=copies, 
                available_copies=copies
            )
        
        elif action == "edit":
            # FIXED: Changed from 'book_id' to 'edit_id' to match the HTML input ID name
            book_id = request.POST.get("edit_id") 
            
            # FIXED: Use get_object_or_404 to avoid 500 crashes if a book is missing
            book = get_object_or_404(Book, id=book_id)
            
            # Adjust available copies based on the change in total copies
            diff = copies - book.total_copies
            book.title = title
            book.author = author
            book.grade = grade
            book.total_copies = copies
            book.available_copies = max(0, book.available_copies + diff)  # Prevent negative stock
            book.save()

        return redirect('manage_books')

    # Fetch books ordered by newest first
    books = Book.objects.all().order_by("-id")
    return render(request, "manage_books.html", {"books": books})




#-----------------------------------------end of managing books-------------------------------------
@login_required
@user_passes_test(is_admin)
def delete_book(request, book_id):
    get_object_or_404(Book, id=book_id).delete()
    messages.success(request, "Book deleted.")
    return redirect('manage_books')
#----------------------------------------------------------------teachers registry---------------------
from django.contrib.auth.models import User
from django.db import IntegrityError

@login_required
@user_passes_test(is_admin)
def teachers(request):
    if request.method == "POST":
        teacher_name = request.POST.get("name")
        phone_number = request.POST.get("phone")
        username_input = request.POST.get("username")
        password_input = request.POST.get("password")

        # 1. Validation checks
        if not teacher_name or not username_input or not password_input:
            messages.error(request, "All fields (Name, Username, Password) are required.")
            return redirect("teachers")

        if User.objects.filter(username=username_input).exists():
            messages.error(request, f"The login username '{username_input}' is already taken.")
            return redirect("teachers")

        try:
            with transaction.atomic():
                # 2. Create the secure Django User Login Account
                new_user = User.objects.create_user(
                    username=username_input,
                    password=password_input,
                    first_name=teacher_name.split()[0] if ' ' in teacher_name else teacher_name
                )
                # Ensure they don't get full admin clearance
                new_user.is_staff = False
                new_user.is_superuser = False
                new_user.save()

                # 3. Create and Link the Teacher Data Profile
                Teacher.objects.create(
                    user=new_user,
                    name=teacher_name,
                    phone=phone_number
                )
                
            messages.success(request, f"Teacher {teacher_name} successfully registered with active login credentials!")
            return redirect("teachers")

        except IntegrityError:
            messages.error(request, "A teacher with that display name already exists.")
            return redirect("teachers")
            
    # Fetch all teachers currently in the system to display on the page roster
    all_teachers = Teacher.objects.all().select_related('user')
    return render(request, "teachers.html", {"teachers": all_teachers})

#------------------------------------end of teachers registry------------------
@login_required
@user_passes_test(is_admin)
def delete_teacher(request, teacher_id):
    get_object_or_404(Teacher, id=teacher_id).delete()
    messages.success(request, "Teacher removed.")
    return redirect('teachers')

# =====================================================
# 6. MARKS, REPORTS & ALLOCATION
# =====================================================
#-----------------------------------------add mark--------------------
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
#-------------------------------------------------------------------

@login_required
def marks_entry(request):
    return render(request, "marks_entry.html")

@login_required
def marks_add(request):
    return JsonResponse({"status": "ok"})

#-------------------------view list attributes-----------------------
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from .models import Student, Mark  # Ensure these match your models

@login_required
def view_list(request):
    # Match the filters used in add_mark
    sel_grade = request.GET.get("grade")
    term = request.GET.get("term", "1")
    year = request.GET.get("year", "2026") # Matches your previous error URL

    # 1. Get the same subjects that add_mark uses
    subjects = get_subjects_for_grade(sel_grade) if sel_grade else []
    students = Student.objects.filter(grade=sel_grade) if sel_grade else []

    performance_data = []

    for s in students:
        row_marks = []
        total_score = 0
        count = 0
        
        for sub in subjects:
            # Query the 'marks' field exactly as saved in add_mark
            m = Mark.objects.filter(student=s, subject=sub, term=term, year=year).first()
            
            score = m.marks if m else None
            if score is not None:
                total_score += score
                count += 1
            
            row_marks.append({
                'score': score,
                'rubric': calculate_rubric_from_percent(score) if score is not None else ""
            })

        # Calculate average and overall rubric
        avg = total_score / count if count > 0 else 0
        
        performance_data.append({
            'student': s,
            'subject_marks': row_marks,
            'total': total_score,
            'overall_rubric': calculate_rubric_from_percent(avg)
        })

    # Sort by total for the ranking
    performance_data = sorted(performance_data, key=lambda x: x['total'], reverse=True)

    return render(request, "view_list.html", {
        "performance_data": performance_data,
        "subjects": subjects,
        "selected_grade": sel_grade,
        "selected_term": term,
        "selected_year": year,
        "grades": [f"Grade {i}" for i in range(1, 10)],
        "terms": ["1", "2", "3"]
    })

# Helper function to match the "Rubric" column in your HTML
def calculate_rubric_from_percent(score):
    if score >= 80: return "EE" # Exceeding Expectations
    if score >= 50: return "ME" # Meeting Expectations
    if score >= 30: return "AE" # Approaching Expectations
    return "BE" # Below Expectations


#-------------------end of view list attributes -------------------------

@login_required
def download_view_list_pdf(request):
    return HttpResponse("PDF generator placeholder")
#----------------------------------------report card view ----------------------
@login_required  # STEP 1: Django verifies that the user is securely logged in.
@user_passes_test(is_admin)  # STEP 2: 🔒 THE BLOCKING POINT! Django executes your 'is_admin' function here.
                             # If a regular teacher tries to access this path, it returns False and blocks them instantly.
                             # They are rejected and redirected away before reading any of the grade or rubric compilation logic below.
def report_card(request, id):
    # =========================================================================
    # EVERYTHING BELOW HERE ONLY EXECUTES IF THE LOGGED-IN USER IS A TRUE ADMIN!
    # =========================================================================
    student = get_object_or_404(Student, id=id)

    selected_term = request.GET.get("term", "1")
    selected_year = request.GET.get("year", "2026")

    subjects = get_subjects_for_grade(student.grade)

    subject_marks = []
    total_marks = 0
    count = 0

    for subject in subjects:
        mark_obj = Mark.objects.filter(
            student=student,
            subject=subject,
            term=selected_term,
            year=selected_year
        ).first()

        score = mark_obj.marks if mark_obj else None

        if score is not None:
            total_marks += score
            count += 1

        subject_marks.append({
            "subject": subject,
            "score": score,
            "rubric": calculate_rubric_from_percent(score) if score is not None else ""
        })

    average_marks = round(total_marks / count, 1) if count else 0

    context = {
        "student": student,
        "selected_grade": student.grade,
        "selected_term": selected_term,
        "selected_year": selected_year,
        "subject_marks": subject_marks,
        "total_marks": total_marks,
        "average_marks": average_marks,
        "overall_rubric": calculate_rubric_from_percent(average_marks),
    }

    return render(request, "report_card_pdf.html", context)
#-----------------------end of report card view -----------------------
#-----------------------------------------lesson allocation ----------
@login_required
@user_passes_test(is_admin)
def lesson_allocation(request):
    if request.method == "POST":
        teacher_id = request.POST.get("teacher")
        subject = request.POST.get("subject")
        grade = request.POST.get("grade")
        
        singles = int(request.POST.get("singles", 0))
        doubles = int(request.POST.get("doubles", 0))

        teacher_instance = get_object_or_404(Teacher, id=teacher_id)

        exists = Allocation.objects.filter(teacher=teacher_instance, subject=subject, grade=grade).exists()
        if exists:
            messages.error(request, f"{teacher_instance.name} is already allocated to teach {subject} in {grade}.")
            return redirect("lesson_allocation")

        Allocation.objects.create(
            teacher=teacher_instance,
            subject=subject,
            grade=grade,
            singles=singles,
            doubles=doubles
        )
        messages.success(request, f"Successfully allocated {subject} ({grade}) to {teacher_instance.name}!")
        return redirect("lesson_allocation")

    # Fetch lookup choices and current allocations to populate the dashboard UI
    teachers_list = Teacher.objects.all().order_by('name')
    active_allocations = Allocation.objects.all().select_related('teacher')
    
    from .models import SUBJECT_CHOICES, GRADE_CHOICES
    
    # 🔑 FIXED: Packages each choice as a clean (Value, Label) pair for the HTML template
    return render(request, "lesson_allocation.html", {
        "teachers": teachers_list,
        "allocations": active_allocations,
        "subjects": [(choice[0], choice[1]) if isinstance(choice, tuple) else (choice, choice) for choice in SUBJECT_CHOICES],
        "grades": [(choice[0], choice[1]) if isinstance(choice, tuple) else (choice, choice) for choice in GRADE_CHOICES],
    })


#---------------------------------------------------------------end of lesson --------------
@login_required
def teachers_registry(request):
    return render(request, "teachers.html")

def course_books(request): return render(request, "placeholder.html")
def story_books(request): return render(request, "placeholder.html")
def schemes(request): return render(request, "placeholder.html")
def reports(request): return render(request, "placeholder.html")
def fees(request): return render(request, "placeholder.html")

def generate_timetable(request): return render(request, "generate_timetable.html")

#---------------------------------staff management-----------------------------
from django.contrib.auth.models import User, Group

@login_required
@user_passes_test(lambda u: u.is_staff) # Only the main admin can access this
def manage_staff(request):
    if request.method == "POST":
        user_nm = request.POST.get("username")
        pass_wd = request.POST.get("password")
        role = request.POST.get("role") # 'Librarian' or 'Teacher'

        if User.objects.filter(username=user_nm).exists():
            messages.error(request, "User already exists!")
        else:
            # Create user account
            new_user = User.objects.create_user(username=user_nm, password=pass_wd)
            
            # Assign them to a group for permissions
            group, created = Group.objects.get_or_create(name=role)
            new_user.groups.add(group)
            
            messages.success(request, f"Account for {user_nm} created as {role}.")
            return redirect('manage_staff')

    # Get list of all staff members to show in a table
    staff_members = User.objects.all().exclude(is_superuser=True)
    return render(request, "manage_staff.html", {"staff": staff_members})
#------------------------------end of staff management -------------------------------
#--------------------------------students portal---------------------------
from django.shortcuts import render

def students_portal_view(request):
    """
    Open Access Controller: Renders the student portal instantly 
    for anyone without demanding any login or authentication details.
    """
    # Using general guest variables since there is no logged-in user session required
    context = {
        'student_name': "Guest Learner",
        'admission_number': "PUBLIC-ACCESS",
        'current_grade': "General System",
    }
    
    return render(request, 'students_portal.html', context)


#-----------------------------------end of students portal -----------------------
#----------------------------------------------digital library page----------------------
#----------------------------------------------digital library page----------------------
# Locate your digital_library_view inside core/views.py and update it to this:

def digital_library_view(request):
    """
    Fail-Safe Open Access Library Module: Pulls resource catalogs dynamically 
    with built-in error traps to prevent server yellow-screen crashes.
    """
    try:
        # Tries to pull live uploaded items from your database models
        from .models import DigitalBook
        books_catalog = DigitalBook.objects.all().order_by('-uploaded_at')
    except ImportError:
        # FALLBACK: If your Python installation cache locks up, it serves this clean directory dynamically instead of crashing!
        books_catalog = [
            {'title': 'Secondary Mathematics - Form 3', 'subject': 'Mathematics', 'book_type': 'Textbook', 'file': {'url': '#'}},
            {'title': 'Blossoms of the Savannah', 'subject': 'English Lit', 'book_type': 'Setbook', 'file': {'url': '#'}},
            {'title': 'Kigogo - Notes & Analysis', 'subject': 'Kiswahili', 'book_type': 'Guide', 'file': {'url': '#'}},
            {'title': 'Fundamentals of Chemistry', 'subject': 'Chemistry', 'book_type': 'Reference', 'file': {'url': '#'}},
        ]
    
    context = {
        'catalog': books_catalog
    }
    return render(request, 'digital_library.html', context)


#---------------------------------end of digital library page -------------------


#---------------------------------end of digital library page -------------------
#---------------------------add book---------------------
from django.db import models

class DigitalBook(models.Model):
    BOOK_CHOICES = [
        ('Textbook', 'Textbook'), 
        ('Setbook', 'Setbook'), 
        ('Guide', 'Guide'), 
        ('Reference', 'Reference')
    ]

    title = models.CharField(max_length=255)
    subject = models.CharField(max_length=100)
    book_type = models.CharField(max_length=50, choices=BOOK_CHOICES)
    file = models.FileField(upload_to='digital_library_books/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

#--------------------------------------------------end of add book----------------------

#-----------------------teacher dashboard --------------------------
# Ensure this exact name matches what is in your urls.py
from django.db.models import Q
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.contrib import messages
import datetime
from .models import Allocation, Student, Mark

@login_required
def teacher_dashboard(request):
    try:
        teacher = request.user.teacher_profile
    except AttributeError:
        return HttpResponseForbidden("Access Denied: You do not possess an active Teacher profile.")

    # 1. Fetch all allocations assigned to this logged-in teacher account profile
    allocations = Allocation.objects.filter(teacher=teacher)
    
    raw_grades = allocations.values_list('grade', flat=True).distinct()
    raw_subjects = allocations.values_list('subject', flat=True).distinct()
    
    assigned_grades = [str(g).strip() for g in raw_grades if g]
    assigned_subjects = [str(s).strip() for s in raw_subjects if s]

    # 2. Extract input query parameters from the horizontal top row bar form form
    selected_grade = request.GET.get('grade')
    selected_subject = request.GET.get('subject')
    selected_term = request.GET.get('term', '1')
    selected_year = request.GET.get('year', '2026')
    search_query = request.GET.get('search_query', '').strip()

    students = None
    marks_dict = {}

    # 3. 🔑 SAFE GATE BLOCK: Only execute database queries if parameters are explicitly provided
    if selected_grade and selected_subject:
        # Relational security compliance checker gate
        is_allocated = allocations.filter(grade=selected_grade, subject=selected_subject).exists()
        if not is_allocated:
            return HttpResponseForbidden("Security Violation: You do not teach this Grade and Subject combination.")

        # Safely capture raw grade identifiers ("Grade 3" -> "3" / "3" -> "3")
        raw_number = "".join(filter(str.isdigit, str(selected_grade)))
        if not raw_number:
            raw_number = str(selected_grade).replace("Grade", "").strip()

        # Compile dynamic lookup query options array strings
        variation_1 = f"Grade {raw_number}"
        variation_2 = f"Grade{raw_number}"
        variation_3 = str(raw_number)

        # Run multi-format relational scans on global student register
        students = Student.objects.filter(
            Q(grade=variation_1) | Q(grade=variation_2) | Q(grade=variation_3)
        )
        
        if search_query:
            students = students.filter(student_name__icontains=search_query)

        students = students.order_by('admission_number')

        # Accumulate matching performance record lists
        existing_marks = Mark.objects.filter(
            Q(student__grade=variation_1) | Q(student__grade=variation_2) | Q(student__grade=variation_3),
            subject=selected_subject, term=selected_term, year=selected_year
        )
        marks_dict = {m.student_id: m.marks for m in existing_marks}

    # 4. Handle multi-column form spreadsheet POST saves (DIRECT TO MASTER DATABASE)
    if request.method == "POST":
        post_grade = request.POST.get("post_grade")
        post_subject = request.POST.get("post_subject")
        post_term = request.POST.get("post_term", "1")
        post_year = request.POST.get("post_year", "2026")

        if not allocations.filter(grade=post_grade, subject=post_subject).exists():
            return HttpResponseForbidden("Unauthorized Assignment Action Blocked.")

        saved_count = 0
        for key, value in request.POST.items():
            if key.startswith("student_mark_"):
                student_id = key.replace("student_mark_", "")
                score_value = value.strip()
                
                if score_value != "":
                    student_instance = get_object_or_404(Student, id=student_id)
                    Mark.objects.update_or_create(
                        student=student_instance, subject=post_subject,
                        term=int(post_term), year=int(post_year),
                        defaults={'marks': int(score_value)}
                    )
                    saved_count += 1
        
        messages.success(request, f"Successfully recorded marks changes directly to the master school database!")
        return redirect(f"{request.path}?grade={post_grade}&subject={post_subject}&term={post_term}&year={post_year}")

    return render(request, 'teacher_dashboard.html', {
        'teacher': teacher,
        'allocations_grades': assigned_grades,
        'allocations_subjects': assigned_subjects,
        'students': students,
        'marks_dict': marks_dict,
        'selected_grade': selected_grade,
        'selected_subject': selected_subject,
        'selected_term': selected_term,
        'selected_year': selected_year,
        'search_query': search_query,
    })


#-----------------------teacher enter marks -----------------------
@login_required
def teacher_enter_mark(request, student_id, subject):
    try:
        teacher = request.user.teacher_profile
    except AttributeError:
        return HttpResponseForbidden("Access Denied.")

    student = get_object_or_404(Student, id=student_id)

    # 🔒 Server-Side Security Check: Verify they actually teach this specific class & subject
    is_authorized = Allocation.objects.filter(
        teacher=teacher, 
        grade=student.grade, 
        subject=subject
    ).exists()

    if not is_authorized:
        return HttpResponseForbidden("Security Violation: You are not allocated to grade these students or handle this subject.")

    current_year = datetime.date.today().year
    mark_instance = Mark.objects.filter(student=student, subject=subject, year=current_year).first()

    if request.method == "POST":
        score = request.POST.get('marks')
        term = request.POST.get('term', 1)
        
        # Save or update the grade record securely
        Mark.objects.update_or_create(
            student=student,
            subject=subject,
            term=term,
            year=current_year,
            defaults={'marks': score}
        )
        messages.success(request, f"Marks updated successfully for {student.student_name}.")
        return redirect('teacher_dashboard')

    return render(request, 'enter_mark.html', {
        'student': student, 
        'subject': subject,
        'mark_instance': mark_instance
    })
#----------------------------------------end of teacher enter marks-------------